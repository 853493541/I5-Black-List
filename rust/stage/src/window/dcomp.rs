//! The main path: a DirectComposition visual on the window, with a premultiplied-alpha swap chain
//! that wgpu's DX12 backend makes for it (CreateSwapChainForComposition).

use scenes::prim::Frame;
use windows::core::{IUnknown, Interface};
use windows::Win32::Foundation::{COLORREF, HWND};
use windows::Win32::Graphics::DirectComposition::{
    DCompositionCreateDevice2, IDCompositionDevice, IDCompositionTarget, IDCompositionVisual,
};
use windows::Win32::UI::WindowsAndMessaging::{SetLayeredWindowAttributes, LWA_ALPHA};

use crate::geom::ScreenRect;
use crate::paint::{Gpu, Offscreen, Painter};

pub struct Composition {
    surface: wgpu::Surface<'static>,
    pub format: wgpu::TextureFormat,
    // Kept alive with the window: the visual holds the swap chain, the target ties it to the window.
    _visual: IDCompositionVisual,
    _target: IDCompositionTarget,
    _device: IDCompositionDevice,
}

impl Composition {
    pub fn new(gpu: &Gpu, hwnd: HWND, area: ScreenRect) -> Result<Self, String> {
        let err = |e: windows::core::Error| e.to_string();
        // A layered window shows nothing until it has its attributes; fully opaque, so the visual's own
        // alpha is what the desktop sees.
        unsafe { SetLayeredWindowAttributes(hwnd, COLORREF(0), 255, LWA_ALPHA) }.map_err(err)?;
        let device: IDCompositionDevice =
            unsafe { DCompositionCreateDevice2(None::<&IUnknown>) }.map_err(err)?;
        let target = unsafe { device.CreateTargetForHwnd(hwnd, true) }.map_err(err)?;
        let visual = unsafe { device.CreateVisual() }.map_err(err)?;
        unsafe { target.SetRoot(&visual) }.map_err(err)?;
        let raw = wgpu::SurfaceTargetUnsafe::CompositionVisual(visual.as_raw());
        let surface =
            unsafe { gpu.instance.create_surface_unsafe(raw) }.map_err(|e| e.to_string())?;
        let caps = surface.get_capabilities(&gpu.adapter);
        if !caps
            .alpha_modes
            .contains(&wgpu::CompositeAlphaMode::PreMultiplied)
        {
            return Err(format!(
                "no premultiplied alpha on this swap chain: {:?}",
                caps.alpha_modes
            ));
        }
        let format = [
            wgpu::TextureFormat::Bgra8Unorm,
            wgpu::TextureFormat::Rgba8Unorm,
        ]
        .into_iter()
        .find(|f| caps.formats.contains(f))
        .ok_or_else(|| format!("no 8-bit format: {:?}", caps.formats))?;
        let config = wgpu::SurfaceConfiguration {
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            format,
            width: area[2].max(1) as u32,
            height: area[3].max(1) as u32,
            present_mode: wgpu::PresentMode::Fifo,
            desired_maximum_frame_latency: 2,
            alpha_mode: wgpu::CompositeAlphaMode::PreMultiplied,
            view_formats: vec![],
        };
        surface.configure(&gpu.device, &config);
        // wgpu set the swap chain as the visual's content; the desktop takes it on commit.
        unsafe { device.Commit() }.map_err(err)?;
        Ok(Self {
            surface,
            format,
            _visual: visual,
            _target: target,
            _device: device,
        })
    }

    pub fn present(&mut self, gpu: &Gpu, painter: &Painter, frame: &Frame) -> Result<(), String> {
        let texture = self
            .surface
            .get_current_texture()
            .map_err(|e| e.to_string())?;
        let view = texture.texture.create_view(&Default::default());
        painter.render(gpu, frame, &view);
        texture.present();
        Ok(())
    }

    /// The swap chain cannot be read back; the same frame drawn offscreen in its format stands in.
    pub fn read_back(
        &self,
        gpu: &Gpu,
        painter: &Painter,
        frame: &Frame,
        area: ScreenRect,
    ) -> Vec<u8> {
        let off = Offscreen::new(gpu, area[2] as u32, area[3] as u32, self.format);
        painter.render(gpu, frame, &off.view);
        off.read(gpu)
    }
}
