//! The windows behind 直播姬's captures, on the desktop (the Windows half of livehime.py and livehime_layout.py),
//! and the state the header panel shows beside 直播模式.

use std::ffi::c_void;

use windows::core::{HSTRING, PCWSTR};
use windows::Win32::Foundation::{HWND, POINT, RECT};
use windows::Win32::Graphics::Dwm::{DwmGetWindowAttribute, DWMWA_EXTENDED_FRAME_BOUNDS};
use windows::Win32::Graphics::Gdi::ClientToScreen;
use windows::Win32::UI::WindowsAndMessaging::{FindWindowW, GetClientRect, GetWindowRect, IsIconic, IsWindowVisible};

use super::follow::Rect;
use super::layout::Placement;
use super::{status, Capture, SceneWatch, Status, PROCESS};

/// The window a capture is set to (by class, when it names one, and title), or 0 when it is not open.
pub fn window_of(title: &str, window_class: &str) -> isize {
    if title.is_empty() {
        return 0;
    }
    let (title, class) = (HSTRING::from(title), HSTRING::from(window_class));
    let class = if window_class.is_empty() { PCWSTR::null() } else { PCWSTR(class.as_ptr()) };
    // SAFETY: both strings outlive the call, which only looks the window up.
    unsafe { FindWindowW(class, PCWSTR(title.as_ptr())) }.map_or(0, |found| found.0 as isize)
}

fn hwnd(value: isize) -> HWND {
    HWND(value as *mut c_void)
}

/// (left, top, right, bottom) in desktop pixels of the window a capture is set to, its client area as 直播姬
/// captures it; None when it is not open, hidden or minimized.
pub fn client_rect(title: &str, window_class: &str) -> Option<Rect> {
    let found = window_of(title, window_class);
    if found == 0 {
        return None;
    }
    let h = hwnd(found);
    // SAFETY: reads the state and client area of a window looked up above into locals.
    unsafe {
        if !IsWindowVisible(h).as_bool() || IsIconic(h).as_bool() {
            return None;
        }
        let mut client = RECT::default();
        GetClientRect(h, &mut client).ok()?;
        let mut corner = POINT::default();
        let _ = ClientToScreen(h, &mut corner);
        if client.right <= 0 || client.bottom <= 0 {
            return None;
        }
        Some((corner.x as i64, corner.y as i64, (corner.x + client.right) as i64, (corner.y + client.bottom) as i64))
    }
}

/// A window's bounds in desktop pixels as the desktop draws it (without its invisible resize border); None where
/// there is no such window.
pub fn window_rect(window: isize) -> Option<Rect> {
    if window == 0 {
        return None;
    }
    let mut rect = RECT::default();
    // SAFETY: rect is a local the calls fill in.
    unsafe {
        let size = std::mem::size_of::<RECT>() as u32;
        if DwmGetWindowAttribute(hwnd(window), DWMWA_EXTENDED_FRAME_BOUNDS, &mut rect as *mut _ as *mut c_void, size).is_err() {
            GetWindowRect(hwnd(window), &mut rect).ok()?;
        }
    }
    (rect.right > rect.left && rect.bottom > rect.top).then_some((rect.left as i64, rect.top as i64, rect.right as i64, rect.bottom as i64))
}

/// What a 窗口捕获 takes of its window: the client area, or the window as the desktop draws it; None when the
/// window is not open.
pub fn captured_rect(placement: &Placement) -> Option<Rect> {
    if placement.client_area {
        client_rect(&placement.title, &placement.window_class)
    } else {
        window_rect(window_of(&placement.title, &placement.window_class))
    }
}

/// Whether the window a capture is set to is shown at this desktop point (the game's button).
pub fn window_over(capture: &Capture, point: (i32, i32)) -> bool {
    let found = window_of(&capture.title, &capture.window_class);
    if found == 0 {
        return false;
    }
    let mut rect = RECT::default();
    // SAFETY: reads a window's state and rect into a local.
    unsafe {
        if !IsWindowVisible(hwnd(found)).as_bool() || GetWindowRect(hwnd(found), &mut rect).is_err() {
            return false;
        }
    }
    rect.left <= point.0 && point.0 < rect.right && rect.top <= point.1 && point.1 < rect.bottom
}

/// The state beside 直播模式 in the header (MainWindow's stream check): 直播姬 running, its current scene, and
/// whether the game's capture is over 直播画面 at the game's button `point`. None while it is not known yet.
pub fn header_status(title: &str, watch: &mut SceneWatch, point: Option<(i32, i32)>) -> Option<Status> {
    let running = crate::process::running(PROCESS);
    let scene = if running { watch.scene() } else { None };
    let covers = point.map(|point| move |capture: &Capture| window_over(capture, point));
    status(title, running, scene.as_deref(), covers.as_ref().map(|c| c as &dyn Fn(&Capture) -> bool))
}
