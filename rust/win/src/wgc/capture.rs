//! Windows Graphics Capture of one window: whether Windows would capture it (wgc.answer), and one frame of it.
//!
//! Each `unsafe` call is a COM or Win32 call on handles made here, with a SAFETY note.

use std::time::{Duration, Instant};

use windows::core::{factory, Interface};
use windows::Graphics::Capture::{Direct3D11CaptureFramePool, GraphicsCaptureItem, GraphicsCaptureSession};
use windows::Graphics::DirectX::Direct3D11::IDirect3DDevice;
use windows::Graphics::DirectX::DirectXPixelFormat;
use windows::Win32::Foundation::{HMODULE, HWND};
use windows::Win32::Graphics::Direct3D::{D3D_DRIVER_TYPE, D3D_DRIVER_TYPE_HARDWARE, D3D_DRIVER_TYPE_WARP};
use windows::Win32::Graphics::Direct3D11::{
    D3D11CreateDevice, ID3D11Device, ID3D11DeviceContext, ID3D11Texture2D, D3D11_CPU_ACCESS_READ, D3D11_CREATE_DEVICE_BGRA_SUPPORT,
    D3D11_MAPPED_SUBRESOURCE, D3D11_MAP_READ, D3D11_SDK_VERSION, D3D11_TEXTURE2D_DESC, D3D11_USAGE_STAGING,
};
use windows::Win32::Graphics::Dxgi::IDXGIDevice;
use windows::Win32::System::WinRT::Direct3D11::{CreateDirect3D11DeviceFromDXGIDevice, IDirect3DDxgiInterfaceAccess};
use windows::Win32::System::WinRT::Graphics::Capture::IGraphicsCaptureItemInterop;
use windows::Win32::System::WinRT::{RoInitialize, RO_INIT_MULTITHREADED};

/// One frame of a window, RGBA, row by row, 4 bytes a pixel.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RgbaFrame {
    pub width: usize,
    pub height: usize,
    pub rgba: Vec<u8>,
}

impl RgbaFrame {
    pub fn pixel(&self, x: usize, y: usize) -> [u8; 4] {
        let at = (y * self.width + x) * 4;
        [self.rgba[at], self.rgba[at + 1], self.rgba[at + 2], self.rgba[at + 3]]
    }
}

fn init() {
    // SAFETY: initialises WinRT for this thread; a second call only reports that it was done already.
    let _ = unsafe { RoInitialize(RO_INIT_MULTITHREADED) };
}

/// Whether this Windows has Windows.Graphics.Capture at all (Windows 10 1903 and up).
pub fn supported() -> bool {
    init();
    GraphicsCaptureSession::IsSupported().unwrap_or(false)
}

fn item_for(hwnd: isize) -> windows::core::Result<GraphicsCaptureItem> {
    let interop = factory::<GraphicsCaptureItem, IGraphicsCaptureItemInterop>()?;
    // SAFETY: CreateForWindow only reads the handle; Windows checks that it is a window it can capture.
    unsafe { interop.CreateForWindow(HWND(hwnd as *mut _)) }
}

/// CreateForWindow's HRESULT for `hwnd`: ACCEPTED (0) when Windows would capture it. None where there is no
/// Windows.Graphics.Capture to ask (Windows 10 before 1903).
pub fn answer(hwnd: isize) -> Option<u32> {
    init();
    if factory::<GraphicsCaptureItem, IGraphicsCaptureItemInterop>().is_err() {
        return None;
    }
    Some(match item_for(hwnd) {
        Ok(_) => super::ACCEPTED,
        Err(error) => error.code().0 as u32,
    })
}

fn device() -> windows::core::Result<ID3D11Device> {
    let mut last = windows::core::Error::empty();
    for kind in [D3D_DRIVER_TYPE_HARDWARE, D3D_DRIVER_TYPE_WARP] {
        match make_device(kind) {
            Ok(device) => return Ok(device),
            Err(error) => last = error,
        }
    }
    Err(last)
}

fn make_device(kind: D3D_DRIVER_TYPE) -> windows::core::Result<ID3D11Device> {
    let mut device = None;
    // SAFETY: every out-pointer is a local Option that outlives the call.
    unsafe {
        D3D11CreateDevice(None, kind, HMODULE::default(), D3D11_CREATE_DEVICE_BGRA_SUPPORT, None, D3D11_SDK_VERSION, Some(&mut device), None, None)
    }?;
    device.ok_or_else(windows::core::Error::empty)
}

/// One frame of the window `hwnd` by Windows Graphics Capture, waiting up to `wait` for it. The error says
/// which step failed, for the log.
pub fn grab(hwnd: isize, wait: Duration) -> Result<RgbaFrame, String> {
    init();
    let step = |what: &'static str| move |error: windows::core::Error| format!("{what}: {error}");
    let item = item_for(hwnd).map_err(step("CreateForWindow"))?;
    let d3d = device().map_err(step("D3D11CreateDevice"))?;
    let dxgi: IDXGIDevice = d3d.cast().map_err(step("IDXGIDevice"))?;
    // SAFETY: dxgi is a live DXGI device made above.
    let inspectable = unsafe { CreateDirect3D11DeviceFromDXGIDevice(&dxgi) }.map_err(step("CreateDirect3D11DeviceFromDXGIDevice"))?;
    let winrt: IDirect3DDevice = inspectable.cast().map_err(step("IDirect3DDevice"))?;
    let size = item.Size().map_err(step("item size"))?;
    let pool = Direct3D11CaptureFramePool::CreateFreeThreaded(&winrt, DirectXPixelFormat::B8G8R8A8UIntNormalized, 1, size)
        .map_err(step("CreateFreeThreaded"))?;
    let session = pool.CreateCaptureSession(&item).map_err(step("CreateCaptureSession"))?;
    let _ = session.SetIsCursorCaptureEnabled(false);
    let _ = session.SetIsBorderRequired(false);
    session.StartCapture().map_err(step("StartCapture"))?;
    let end = Instant::now() + wait;
    let frame = loop {
        if let Ok(frame) = pool.TryGetNextFrame() {
            break frame;
        }
        if Instant::now() >= end {
            let _ = session.Close();
            let _ = pool.Close();
            return Err(format!("no frame within {} ms", wait.as_millis()));
        }
        std::thread::sleep(Duration::from_millis(10));
    };
    let surface = frame.Surface().map_err(step("Surface"))?;
    let access: IDirect3DDxgiInterfaceAccess = surface.cast().map_err(step("IDirect3DDxgiInterfaceAccess"))?;
    // SAFETY: the surface is a live D3D11 texture of the frame held above.
    let texture: ID3D11Texture2D = unsafe { access.GetInterface() }.map_err(step("GetInterface"))?;
    let out = read_texture(&d3d, &texture).map_err(step("copy to the CPU"));
    let _ = frame.Close();
    let _ = session.Close();
    let _ = pool.Close();
    out
}

fn read_texture(d3d: &ID3D11Device, texture: &ID3D11Texture2D) -> windows::core::Result<RgbaFrame> {
    let mut desc = D3D11_TEXTURE2D_DESC::default();
    // SAFETY: desc is a local the call fills in.
    unsafe { texture.GetDesc(&mut desc) };
    desc.Usage = D3D11_USAGE_STAGING;
    desc.BindFlags = 0;
    desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ.0 as u32;
    desc.MiscFlags = 0;
    let mut staging = None;
    // SAFETY: desc describes a CPU-readable copy of the texture; staging is a local Option.
    unsafe { d3d.CreateTexture2D(&desc, None, Some(&mut staging)) }?;
    let staging = staging.ok_or_else(windows::core::Error::empty)?;
    // SAFETY: the device's immediate context, used on this thread only.
    let context: ID3D11DeviceContext = unsafe { d3d.GetImmediateContext() }?;
    let mut mapped = D3D11_MAPPED_SUBRESOURCE::default();
    // SAFETY: both textures have the same size and format; the copy is mapped for reading and unmapped below.
    unsafe {
        context.CopyResource(&staging, texture);
        context.Map(&staging, 0, D3D11_MAP_READ, 0, Some(&mut mapped))?;
    }
    let (width, height, pitch) = (desc.Width as usize, desc.Height as usize, mapped.RowPitch as usize);
    let mut rgba = Vec::with_capacity(width * height * 4);
    for row in 0..height {
        // SAFETY: the mapped copy holds `height` rows of `pitch` bytes, each with `width` BGRA pixels.
        let line = unsafe { std::slice::from_raw_parts((mapped.pData as *const u8).add(row * pitch), width * 4) };
        rgba.extend(line.chunks_exact(4).flat_map(|p| [p[2], p[1], p[0], p[3]]));
    }
    // SAFETY: mapped above.
    unsafe { context.Unmap(&staging, 0) };
    Ok(RgbaFrame { width, height, rgba })
}
