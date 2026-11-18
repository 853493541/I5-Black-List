//! The Windows half of game_area.py: which window draws under the lobby's button, asked of user32 and dwmapi only.
#![allow(unsafe_code)]

use windows::Win32::Foundation::{HWND, POINT, RECT};
use windows::Win32::Graphics::Dwm::{DwmGetWindowAttribute, DWMWA_CLOAKED};
use windows::Win32::Graphics::Gdi::{ClientToScreen, ScreenToClient};
use windows::Win32::System::Threading::GetCurrentProcessId;
use windows::Win32::UI::Shell::{SHQueryUserNotificationState, QUNS_RUNNING_D3D_FULL_SCREEN};
use windows::Win32::UI::WindowsAndMessaging::{
    ChildWindowFromPointEx, GetClientRect, GetTopWindow, GetWindow, GetWindowLongW, GetWindowRect,
    GetWindowThreadProcessId, IsIconic, IsWindow, IsWindowVisible, CWP_SKIPINVISIBLE, CWP_SKIPTRANSPARENT,
    GWL_EXSTYLE, GW_HWNDNEXT, WS_EX_LAYERED, WS_EX_TRANSPARENT,
};

use super::ScreenRect;

fn handle(value: isize) -> HWND {
    HWND(value as *mut core::ffi::c_void)
}

/// The top-level windows, front to back, as they are now: noted with each screenshot.
pub fn window_order() -> Vec<isize> {
    let mut order = Vec::new();
    // SAFETY: plain window-list queries on handles Windows hands back.
    let mut hwnd = unsafe { GetTopWindow(None) }.ok();
    while let Some(h) = hwnd.filter(|h| !h.is_invalid()) {
        if order.len() >= 4096 {
            break;
        }
        order.push(h.0 as isize);
        hwnd = unsafe { GetWindow(h, GW_HWNDNEXT) }.ok();
    }
    order
}

fn inner_rect(mut hwnd: HWND, x: i32, y: i32, innermost: bool) -> Option<ScreenRect> {
    // SAFETY: each call gets a live handle and pointers to locals.
    unsafe {
        for _ in 0..if innermost { 16 } else { 0 } {
            let mut point = POINT { x, y };
            let _ = ScreenToClient(hwnd, &mut point);
            let child = ChildWindowFromPointEx(hwnd, point, CWP_SKIPINVISIBLE | CWP_SKIPTRANSPARENT);
            if child.is_invalid() || child == hwnd {
                break;
            }
            hwnd = child;
        }
        let mut client = RECT::default();
        GetClientRect(hwnd, &mut client).ok()?;
        let mut corner = POINT { x: 0, y: 0 };
        let _ = ClientToScreen(hwnd, &mut corner);
        let (left, top) = (i64::from(corner.x), i64::from(corner.y));
        let (right, bottom) = (left + i64::from(client.right), top + i64::from(client.bottom));
        (right > left && bottom > top).then_some([left, top, right, bottom])
    }
}

fn cloaked(hwnd: HWND) -> bool {
    let mut value: i32 = 0;
    // SAFETY: DWMWA_CLOAKED writes one i32 into `value`.
    let asked = unsafe {
        DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, (&mut value as *mut i32).cast(), std::mem::size_of::<i32>() as u32)
    };
    asked.is_ok() && value != 0
}

fn takes(hwnd: HWND, x: i32, y: i32, own: u32) -> bool {
    // SAFETY: queries on a window handle; pointers to locals.
    unsafe {
        if !IsWindowVisible(hwnd).as_bool() || IsIconic(hwnd).as_bool() || cloaked(hwnd) {
            return false;
        }
        let mut pid = 0u32;
        GetWindowThreadProcessId(hwnd, Some(&mut pid));
        if pid == own {
            return false;
        }
        let style = GetWindowLongW(hwnd, GWL_EXSTYLE) as u32;
        if style & WS_EX_TRANSPARENT.0 != 0 && style & WS_EX_LAYERED.0 != 0 {
            return false;
        }
        let mut rect = RECT::default();
        if GetWindowRect(hwnd, &mut rect).is_err() {
            return false;
        }
        rect.left <= x && x < rect.right && rect.top <= y && y < rect.bottom
    }
}

/// The client area of what draws at (x, y): the innermost window there, this app's passed over. `order`: the
/// windows front to back at the screenshot (window_order); empty, as they are now. `innermost` false stops at the
/// top-level window.
pub fn window_rect_at(x: i32, y: i32, order: &[isize], innermost: bool) -> Option<ScreenRect> {
    // SAFETY: as window_order.
    let own = unsafe { GetCurrentProcessId() };
    let hwnd = if order.is_empty() {
        let mut hwnd = unsafe { GetTopWindow(None) }.ok();
        while let Some(h) = hwnd.filter(|h| !h.is_invalid()) {
            if takes(h, x, y, own) {
                break;
            }
            hwnd = unsafe { GetWindow(h, GW_HWNDNEXT) }.ok();
        }
        hwnd.filter(|h| !h.is_invalid())
    } else {
        order.iter().map(|&h| handle(h)).find(|&h| unsafe { IsWindow(Some(h)) }.as_bool() && takes(h, x, y, own))
    }?;
    inner_rect(hwnd, x, y, innermost)
}

/// The innermost window of hwnd's own that draws at (x, y), or hwnd itself; None when hwnd is not a shown window.
pub fn inner_rect_of(hwnd: isize, x: i32, y: i32) -> Option<ScreenRect> {
    let window = handle(hwnd);
    // SAFETY: queries on a handle that may be stale; Windows answers false for those.
    let shown = hwnd != 0
        && unsafe { IsWindow(Some(window)).as_bool() && IsWindowVisible(window).as_bool() && !IsIconic(window).as_bool() };
    if !shown {
        return None;
    }
    inner_rect(window, x, y, true)
}

/// Whether a Direct3D program holds the screen in exclusive full screen, as Windows tells it.
pub fn exclusive_fullscreen() -> bool {
    // SAFETY: a state query with no arguments.
    unsafe { SHQueryUserNotificationState() }.is_ok_and(|state| state == QUNS_RUNNING_D3D_FULL_SCREEN)
}
