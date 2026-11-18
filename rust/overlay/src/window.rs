//! The marks' window on Windows: topmost, click-through, layered, a tool window that never takes focus, per-monitor
//! DPI aware, its pixels given whole with UpdateLayeredWindow (premultiplied BGRA), as Qt's translucent windows
//! over the game were. The thin Win32 edge of the crate: every unsafe call is here.

use std::ffi::c_void;
use std::sync::Once;

use tiny_skia::Pixmap;
use windows::core::{w, Result, PCWSTR};
use windows::Win32::Foundation::{COLORREF, HWND, LPARAM, LRESULT, POINT, RECT, SIZE, WPARAM};
use windows::Win32::Graphics::Gdi::{
    CreateCompatibleDC, CreateDIBSection, DeleteDC, DeleteObject, GetDC, GetMonitorInfoW, MonitorFromRect, ReleaseDC, SelectObject,
    AC_SRC_ALPHA, AC_SRC_OVER, BITMAPINFO, BITMAPINFOHEADER, BI_RGB, BLENDFUNCTION, DIB_RGB_COLORS, MONITORINFO,
    MONITOR_DEFAULTTONEAREST,
};
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::HiDpi::{GetDpiForMonitor, SetThreadDpiAwarenessContext, DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2, MDT_EFFECTIVE_DPI};
use windows::Win32::UI::WindowsAndMessaging::{
    CreateWindowExW, DefWindowProcW, DestroyWindow, GetWindowLongPtrW, RegisterClassExW, SetWindowPos, ShowWindow, UpdateLayeredWindow,
    GWL_EXSTYLE, HWND_TOPMOST, SWP_NOACTIVATE, SWP_NOMOVE, SWP_NOSIZE, SW_HIDE, SW_SHOWNOACTIVATE, ULW_ALPHA, WINDOW_EX_STYLE,
    WNDCLASSEXW, WS_EX_LAYERED, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_EX_TRANSPARENT, WS_POPUP,
};

use crate::layout::{CheckResult, Extras};
use crate::look::Look;
use crate::marks::{Moment, Style};
use crate::text::Face;

/// Layered (per-pixel alpha), transparent to the mouse, kept off the taskbar and Alt+Tab, never activated, on top.
pub const EX_STYLE: WINDOW_EX_STYLE =
    WINDOW_EX_STYLE(WS_EX_LAYERED.0 | WS_EX_TRANSPARENT.0 | WS_EX_TOOLWINDOW.0 | WS_EX_NOACTIVATE.0 | WS_EX_TOPMOST.0);
const CLASS: PCWSTR = w!("BlacklistDetectMarks");

unsafe extern "system" fn proc(hwnd: HWND, msg: u32, wparam: WPARAM, lparam: LPARAM) -> LRESULT {
    unsafe { DefWindowProcW(hwnd, msg, wparam, lparam) }
}

/// One layered window. Destroyed when dropped.
pub struct LayeredWindow {
    hwnd: HWND,
}

impl LayeredWindow {
    pub fn new() -> Result<LayeredWindow> {
        static CLASS_ONCE: Once = Once::new();
        unsafe {
            // Device pixels on every monitor: the marks are drawn at each monitor's own scale, never stretched.
            SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
            let instance = GetModuleHandleW(None)?;
            CLASS_ONCE.call_once(|| {
                let class = WNDCLASSEXW {
                    cbSize: std::mem::size_of::<WNDCLASSEXW>() as u32,
                    lpfnWndProc: Some(proc),
                    hInstance: instance.into(),
                    lpszClassName: CLASS,
                    ..Default::default()
                };
                RegisterClassExW(&class);
            });
            let hwnd = CreateWindowExW(EX_STYLE, CLASS, w!("黑名单检测"), WS_POPUP, -32000, -32000, 1, 1, None, None, Some(instance.into()), None)?;
            Ok(LayeredWindow { hwnd })
        }
    }

    pub fn hwnd(&self) -> HWND {
        self.hwnd
    }

    /// The window's extended styles as Windows has them.
    pub fn ex_style(&self) -> u32 {
        unsafe { GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE) as u32 }
    }

    /// Show `pixmap` (premultiplied RGBA) with its top-left at (x, y) device pixels, at `opacity` 0..=255.
    pub fn update(&self, x: i32, y: i32, pixmap: &Pixmap, opacity: u8) -> Result<()> {
        let (w, h) = (pixmap.width() as i32, pixmap.height() as i32);
        unsafe {
            let screen = GetDC(None);
            let memory = CreateCompatibleDC(Some(screen));
            let info = BITMAPINFO {
                bmiHeader: BITMAPINFOHEADER {
                    biSize: std::mem::size_of::<BITMAPINFOHEADER>() as u32,
                    biWidth: w,
                    biHeight: -h,
                    biPlanes: 1,
                    biBitCount: 32,
                    biCompression: BI_RGB.0,
                    ..Default::default()
                },
                ..Default::default()
            };
            let mut bits: *mut c_void = std::ptr::null_mut();
            let result = CreateDIBSection(Some(memory), &info, DIB_RGB_COLORS, &mut bits, None, 0).and_then(|bitmap| {
                let out = std::slice::from_raw_parts_mut(bits as *mut u8, (w * h * 4) as usize);
                to_bgra(pixmap.data(), out);
                let old = SelectObject(memory, bitmap.into());
                let blend = BLENDFUNCTION {
                    BlendOp: AC_SRC_OVER as u8,
                    BlendFlags: 0,
                    SourceConstantAlpha: opacity,
                    AlphaFormat: AC_SRC_ALPHA as u8,
                };
                let shown = UpdateLayeredWindow(
                    self.hwnd,
                    Some(screen),
                    Some(&POINT { x, y }),
                    Some(&SIZE { cx: w, cy: h }),
                    Some(memory),
                    Some(&POINT { x: 0, y: 0 }),
                    COLORREF(0),
                    Some(&blend),
                    ULW_ALPHA,
                );
                SelectObject(memory, old);
                let _ = DeleteObject(bitmap.into());
                shown
            });
            let _ = DeleteDC(memory);
            ReleaseDC(None, screen);
            result?;
            let _ = ShowWindow(self.hwnd, SW_SHOWNOACTIVATE);
            SetWindowPos(self.hwnd, Some(HWND_TOPMOST), 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        }
    }

    /// Move without redrawing (the game window moved).
    pub fn move_to(&self, x: i32, y: i32) -> Result<()> {
        unsafe { SetWindowPos(self.hwnd, Some(HWND_TOPMOST), x, y, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE) }
    }

    pub fn hide(&self) {
        unsafe {
            let _ = ShowWindow(self.hwnd, SW_HIDE);
        }
    }
}

impl Drop for LayeredWindow {
    fn drop(&mut self) {
        unsafe {
            let _ = DestroyWindow(self.hwnd);
        }
    }
}

/// tiny-skia's premultiplied RGBA to the DIB's premultiplied BGRA.
pub fn to_bgra(rgba: &[u8], out: &mut [u8]) {
    for (s, d) in rgba.chunks_exact(4).zip(out.chunks_exact_mut(4)) {
        d.copy_from_slice(&[s[2], s[1], s[0], s[3]]);
    }
}

/// The monitor under `rect` (device pixels): its work area and its scale (1.5 at 150 %).
pub fn monitor(rect: [i32; 4]) -> ([i32; 4], f32) {
    unsafe {
        let r = RECT { left: rect[0], top: rect[1], right: rect[2], bottom: rect[3] };
        let handle = MonitorFromRect(&r, MONITOR_DEFAULTTONEAREST);
        let mut info = MONITORINFO { cbSize: std::mem::size_of::<MONITORINFO>() as u32, ..Default::default() };
        let work = if GetMonitorInfoW(handle, &mut info).as_bool() { info.rcWork } else { r };
        let (mut dx, mut dy) = (96u32, 96u32);
        let ratio = if GetDpiForMonitor(handle, MDT_EFFECTIVE_DPI, &mut dx, &mut dy).is_ok() { dx as f32 / 96.0 } else { 1.0 };
        ([work.left, work.top, work.right, work.bottom], ratio)
    }
}

/// The marks over the game: what the app-wiring package calls.
pub struct Overlay {
    window: LayeredWindow,
    face: Option<Face>,
    /// Where the frame is and the game rect it was laid out for, while shown.
    shown: Option<([i32; 2], [i32; 4])>,
    /// The picture shown, kept to fade it in.
    pixmap: Option<Pixmap>,
}

impl Overlay {
    pub fn new() -> Result<Overlay> {
        Ok(Overlay { window: LayeredWindow::new()?, face: Face::system(), shown: None, pixmap: None })
    }

    pub fn window(&self) -> &LayeredWindow {
        &self.window
    }

    /// The marks for a check over the game at `game_rect` (device pixels, virtual desktop): false when there is
    /// nothing to show (no 准备案件还原), and the marks are hidden.
    pub fn show(&mut self, game_rect: [i32; 4], result: &CheckResult, look: &Look) -> Result<bool> {
        self.show_with(game_rect, result, look, Extras::default())
    }

    /// The gold block with `text` (检查中) on 准备案件还原 while a check runs.
    pub fn show_checking(&mut self, game_rect: [i32; 4], button: [i32; 4], text: &str) -> Result<bool> {
        let result = CheckResult { button_box: Some(button), ..CheckResult::default() };
        self.show_with(game_rect, &result, &crate::look::rose(), Extras { checking: Some(text), mine: false })
    }

    pub fn show_with(&mut self, game_rect: [i32; 4], result: &CheckResult, look: &Look, extras: Extras) -> Result<bool> {
        self.show_faded(game_rect, result, look, extras, 255)
    }

    /// As `show_with`, at `opacity` (0 to 255); `set_opacity` then fades it in.
    pub fn show_faded(&mut self, game_rect: [i32; 4], result: &CheckResult, look: &Look, extras: Extras, opacity: u8) -> Result<bool> {
        let (area, ratio) = monitor(game_rect);
        let style = Style { look, face: self.face.as_ref(), at: Moment::default(), ratio };
        let Some(frame) = crate::render(result, extras, area, &style) else {
            self.hide();
            return Ok(false);
        };
        self.window.update(frame.x, frame.y, &frame.pixmap, opacity)?;
        self.shown = Some(([frame.x, frame.y], game_rect));
        self.pixmap = Some(frame.pixmap);
        Ok(true)
    }

    /// The picture shown, again at `opacity` (the 120 ms fade-in's steps).
    pub fn set_opacity(&mut self, opacity: u8) -> Result<()> {
        if let (Some(([x, y], _)), Some(pixmap)) = (self.shown, self.pixmap.as_ref()) {
            self.window.update(x, y, pixmap, opacity)?;
        }
        Ok(())
    }

    /// The game window is now at `game_rect`: the marks move by as much (call it on the app's 400 ms glance).
    pub fn follow(&mut self, game_rect: [i32; 4]) -> Result<()> {
        if let Some(([x, y], old)) = self.shown {
            let (dx, dy) = (game_rect[0] - old[0], game_rect[1] - old[1]);
            if dx != 0 || dy != 0 {
                self.window.move_to(x + dx, y + dy)?;
                self.shown = Some(([x + dx, y + dy], game_rect));
            }
        }
        Ok(())
    }

    pub fn hide(&mut self) {
        self.window.hide();
        self.shown = None;
        self.pixmap = None;
    }

    pub fn is_shown(&self) -> bool {
        self.shown.is_some()
    }
}
