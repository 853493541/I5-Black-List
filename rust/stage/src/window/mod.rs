//! The see-through window a scene plays in, over the game (Windows): topmost, never focused, clicks
//! pass through it to the game, and only the scene's own pixels show.
//!
//! Two ways to put the GPU's frames in it, picked at run time:
//! - Composition (main): DirectComposition. A visual on the window gets a premultiplied-alpha swap chain
//!   made by wgpu's DX12 backend (`SurfaceTargetUnsafe::CompositionVisual`); the frames never leave the
//!   GPU and the desktop composes them over the game.
//! - Layered (fallback, where DirectComposition or DX12 swap chains fail): each frame is drawn offscreen,
//!   read back, and handed to UpdateLayeredWindow as a premultiplied DIB.
#![allow(unsafe_code)]

mod dcomp;
mod layered;

pub use layered::capture;

use std::sync::Once;

use scenes::prim::Frame;
use windows::core::w;
use windows::Win32::Foundation::{HWND, LPARAM, LRESULT, WPARAM};
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::WindowsAndMessaging::{
    CreateWindowExW, DefWindowProcW, DestroyWindow, DispatchMessageW, PeekMessageW, RegisterClassW,
    SetWindowPos, ShowWindow, TranslateMessage, HTTRANSPARENT, HWND_TOPMOST, MSG, PM_REMOVE,
    SWP_NOACTIVATE, SWP_SHOWWINDOW, SW_HIDE, SW_SHOWNOACTIVATE, WM_NCHITTEST, WNDCLASSW,
    WS_EX_LAYERED, WS_EX_NOACTIVATE, WS_EX_NOREDIRECTIONBITMAP, WS_EX_TOOLWINDOW, WS_EX_TOPMOST,
    WS_EX_TRANSPARENT, WS_POPUP,
};

use crate::geom::ScreenRect;
use crate::paint::{Gpu, Painter};

/// How the frames reach the screen.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Path {
    Composition,
    Layered,
}

enum Target {
    Composition(dcomp::Composition),
    Layered(layered::Layered),
}

/// The scene's window over the game's screen.
pub struct Overlay {
    hwnd: HWND,
    area: ScreenRect,
    target: Target,
    painter: Painter,
    /// Why the paths tried before this one failed (for the log).
    pub tried: Vec<String>,
}

/// BLACKLIST_DETECT_STAGE_PATH=layered / composition forces one path (a player's PC that shows nothing one way).
pub fn forced_path() -> Option<Path> {
    match std::env::var("BLACKLIST_DETECT_STAGE_PATH").ok()?.trim().to_ascii_lowercase().as_str() {
        "layered" => Some(Path::Layered),
        "composition" => Some(Path::Composition),
        _ => None,
    }
}

/// The PCI ids (vendor, device) of the DXGI adapters with a monitor: the chips the desktop is shown on.
pub fn display_ids() -> Vec<(u32, u32)> {
    use windows::Win32::Graphics::Dxgi::{CreateDXGIFactory1, IDXGIFactory1};
    let Ok(factory) = (unsafe { CreateDXGIFactory1::<IDXGIFactory1>() }) else { return Vec::new() };
    let mut ids = Vec::new();
    for i in 0.. {
        let Ok(adapter) = (unsafe { factory.EnumAdapters1(i) }) else { break };
        let has_monitor = unsafe { adapter.EnumOutputs(0) }.is_ok();
        if let (true, Ok(desc)) = (has_monitor, unsafe { adapter.GetDesc1() }) {
            ids.push((desc.VendorId, desc.DeviceId));
        }
    }
    ids
}

/// The primary monitor's size in desktop pixels.
pub fn screen_size() -> (i32, i32) {
    use windows::Win32::UI::WindowsAndMessaging::{GetSystemMetrics, SM_CXSCREEN, SM_CYSCREEN};
    unsafe { (GetSystemMetrics(SM_CXSCREEN), GetSystemMetrics(SM_CYSCREEN)) }
}

/// An opaque picture in a window of its own (a test's stand-in for the game).
pub struct Backdrop {
    hwnd: HWND,
}

impl Backdrop {
    /// bgra: area's width x height pixels, top-down.
    pub fn show(area: ScreenRect, bgra: &[u8]) -> Result<Self, String> {
        let hwnd = create_window(area, Path::Layered)?;
        let backdrop = Self { hwnd };
        let mut dib = layered::Dib::new(area[2], area[3])?;
        let bytes = dib.bytes();
        if bytes.len() != bgra.len() {
            return Err(format!("{} bytes, want {}", bgra.len(), bytes.len()));
        }
        bytes.copy_from_slice(bgra);
        layered::update(hwnd, area, dib.dc)?;
        show_at(hwnd, area)?;
        Ok(backdrop)
    }
}

impl Drop for Backdrop {
    fn drop(&mut self) {
        let _ = unsafe { DestroyWindow(self.hwnd) };
    }
}

fn show_at(hwnd: HWND, area: ScreenRect) -> Result<(), String> {
    let [x, y, w, h] = area;
    unsafe {
        let _ = ShowWindow(hwnd, SW_SHOWNOACTIVATE);
        SetWindowPos(hwnd, Some(HWND_TOPMOST), x, y, w, h, SWP_NOACTIVATE | SWP_SHOWWINDOW).map_err(|e| e.to_string())
    }
}

extern "system" fn proc(hwnd: HWND, msg: u32, w: WPARAM, l: LPARAM) -> LRESULT {
    if msg == WM_NCHITTEST {
        // Clicks belong to the game.
        return LRESULT(HTTRANSPARENT as isize);
    }
    unsafe { DefWindowProcW(hwnd, msg, w, l) }
}

fn create_window(area: ScreenRect, path: Path) -> Result<HWND, String> {
    static CLASS: Once = Once::new();
    let instance = unsafe { GetModuleHandleW(None) }.map_err(|e| e.to_string())?;
    CLASS.call_once(|| {
        let class = WNDCLASSW {
            lpfnWndProc: Some(proc),
            hInstance: instance.into(),
            lpszClassName: w!("BlacklistDetectStage"),
            ..Default::default()
        };
        unsafe { RegisterClassW(&class) };
    });
    // Layered + transparent: hit testing skips it, for every process's clicks, not only ours.
    let mut ex =
        WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT | WS_EX_LAYERED;
    if path == Path::Composition {
        ex |= WS_EX_NOREDIRECTIONBITMAP;
    }
    let [x, y, w, h] = area;
    unsafe {
        CreateWindowExW(
            ex,
            w!("BlacklistDetectStage"),
            w!(""),
            WS_POPUP,
            x,
            y,
            w,
            h,
            None,
            None,
            Some(instance.into()),
            None,
        )
    }
    .map_err(|e| e.to_string())
}

impl Overlay {
    /// A window over `area` (the game's screen, desktop pixels), hidden until the first frame.
    /// prefer: force one path; None tries Composition, then Layered.
    pub fn open(gpu: &Gpu, area: ScreenRect, prefer: Option<Path>) -> Result<Self, String> {
        let order: &[Path] = match prefer {
            Some(Path::Composition) => &[Path::Composition],
            Some(Path::Layered) => &[Path::Layered],
            None => &[Path::Composition, Path::Layered],
        };
        let mut why = Vec::new();
        for &path in order {
            let hwnd = create_window(area, path)?;
            let made = match path {
                Path::Composition => dcomp::Composition::new(gpu, hwnd, area).map(|c| {
                    let format = c.format;
                    (Target::Composition(c), format)
                }),
                Path::Layered => layered::Layered::new(gpu, hwnd, area)
                    .map(|l| (Target::Layered(l), layered::FORMAT)),
            };
            match made {
                Ok((target, format)) => {
                    let painter = Painter::new(gpu, area[2] as u32, area[3] as u32, format, None);
                    return Ok(Self {
                        hwnd,
                        area,
                        target,
                        painter,
                        tried: why,
                    });
                }
                Err(e) => {
                    why.push(format!("{path:?}: {e}"));
                    let _ = unsafe { DestroyWindow(hwnd) };
                }
            }
        }
        Err(why.join("; "))
    }

    pub fn path(&self) -> Path {
        match self.target {
            Target::Composition(_) => Path::Composition,
            Target::Layered(_) => Path::Layered,
        }
    }

    /// The scene's still picture (layer 1), drawn once for this stage.
    pub fn set_still(&self, gpu: &Gpu, frame: &Frame) {
        self.painter.set_still(gpu, frame);
    }

    /// The still texture, for `stage::scene::shoot_into` (a scene from `make_on` copies its frame in).
    pub fn still_texture(&self) -> &wgpu::Texture {
        self.painter.still_texture()
    }

    /// A frame the scene drew itself (`stage::scene::shoot`), set before `present`.
    pub fn set_still_pixels(&self, gpu: &Gpu, rgba: &[u8]) {
        self.painter.set_still_pixels(gpu, rgba);
    }

    /// Shows the window, topmost, without taking focus (the first frame).
    pub fn show(&self) -> Result<(), String> {
        show_at(self.hwnd, self.area)
    }

    pub fn area(&self) -> ScreenRect {
        self.area
    }

    /// The frame as read_back gives it, in GDI's BGRA order (to compare with `capture`).
    pub fn read_back_bgra(&self, gpu: &Gpu, frame: &Frame) -> Vec<u8> {
        let mut px = self.read_back(gpu, frame);
        if let Target::Composition(c) = &self.target {
            if c.format == wgpu::TextureFormat::Rgba8Unorm {
                crate::seen::swap_red_blue(&mut px);
            }
        }
        px
    }

    pub fn hide(&self) {
        let _ = unsafe { ShowWindow(self.hwnd, SW_HIDE) };
    }

    /// Draws one frame and puts it on the screen.
    pub fn present(&mut self, gpu: &Gpu, frame: &Frame) -> Result<(), String> {
        match &mut self.target {
            Target::Composition(c) => c.present(gpu, &self.painter, frame),
            Target::Layered(l) => l.present(gpu, &self.painter, frame, self.hwnd, self.area),
        }
    }

    /// The last frame's premultiplied BGRA bytes, where this path keeps them (Layered: always;
    /// Composition: drawn again offscreen in the swap chain's format).
    pub fn read_back(&self, gpu: &Gpu, frame: &Frame) -> Vec<u8> {
        match &self.target {
            Target::Composition(c) => c.read_back(gpu, &self.painter, frame, self.area),
            Target::Layered(l) => l.last().to_vec(),
        }
    }
}

impl Drop for Overlay {
    fn drop(&mut self) {
        let _ = unsafe { DestroyWindow(self.hwnd) };
    }
}

/// Handles this thread's window messages without waiting (call once a tick).
pub fn pump() {
    let mut msg = MSG::default();
    unsafe {
        while PeekMessageW(&mut msg, None, 0, 0, PM_REMOVE).as_bool() {
            let _ = TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    }
}
