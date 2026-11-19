//! Small windows that float over the game (ui_notice's cards): topmost, never taking the focus, out of the
//! taskbar, and the screen's free area to place them in.
#![allow(unsafe_code)]

use windows::Win32::Foundation::{HWND, RECT};
use windows::Win32::UI::HiDpi::GetDpiForSystem;
use windows::Win32::UI::WindowsAndMessaging::{
    GetWindowLongPtrW, SetWindowLongPtrW, SetWindowPos, SystemParametersInfoW, GWL_EXSTYLE, GWL_STYLE, HWND_TOPMOST,
    SPI_GETWORKAREA, SWP_FRAMECHANGED, SWP_NOACTIVATE, SWP_NOMOVE, SWP_NOSIZE, SWP_NOZORDER, SYSTEM_PARAMETERS_INFO_UPDATE_FLAGS,
    WS_BORDER, WS_CAPTION, WS_DLGFRAME, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_MAXIMIZEBOX, WS_MINIMIZEBOX,
    WS_SYSMENU, WS_THICKFRAME,
};

/// ui_kit.Modal's window: no caption, border or resize frame (Qt.FramelessWindowHint), at (x, y) and `width` x `height`
/// desktop pixels. The frame change is applied with SWP_FRAMECHANGED, so the client area is the whole window.
pub fn frameless_at(hwnd: isize, x: i32, y: i32, width: i32, height: i32) -> bool {
    let hwnd = HWND(hwnd as *mut core::ffi::c_void);
    let frame = (WS_CAPTION | WS_THICKFRAME | WS_BORDER | WS_DLGFRAME | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX).0 as isize;
    // SAFETY: reads and sets the style of a window handle the caller owns, then moves it.
    unsafe {
        let style = GetWindowLongPtrW(hwnd, GWL_STYLE);
        SetWindowLongPtrW(hwnd, GWL_STYLE, style & !frame);
        SetWindowPos(hwnd, None, x, y, width, height, SWP_FRAMECHANGED | SWP_NOZORDER | SWP_NOACTIVATE).is_ok()
    }
}

/// Makes the window `hwnd` topmost, never activated, and a tool window (no taskbar button).
pub fn float_window(hwnd: isize) -> bool {
    let hwnd = HWND(hwnd as *mut core::ffi::c_void);
    // SAFETY: reads and sets the extended style of a window handle the caller owns, then raises it.
    unsafe {
        let style = GetWindowLongPtrW(hwnd, GWL_EXSTYLE);
        let wanted = (WS_EX_TOPMOST | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW).0 as isize;
        SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style | wanted);
        SetWindowPos(hwnd, Some(HWND_TOPMOST), 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE).is_ok()
    }
}

/// Brings the app's own window back from the taskbar or the tray (the tray's 显示, a second launch): restored when
/// minimised, shown when hidden, in front. Slint's show() leaves a minimised window minimised, so 显示 did nothing.
/// True when it is on screen and not minimised afterwards.
pub fn bring_back(hwnd: isize) -> bool {
    use windows::Win32::UI::WindowsAndMessaging::{
        IsIconic, IsWindowVisible, SetForegroundWindow, ShowWindow, SW_RESTORE, SW_SHOW,
    };
    let hwnd = HWND(hwnd as *mut core::ffi::c_void);
    // SAFETY: shows and raises a window handle the caller owns.
    unsafe {
        let _ = ShowWindow(hwnd, if IsIconic(hwnd).as_bool() { SW_RESTORE } else { SW_SHOW });
        let _ = SetForegroundWindow(hwnd);
        IsWindowVisible(hwnd).as_bool() && !IsIconic(hwnd).as_bool()
    }
}

/// Whether the window is minimised (for the log).
pub fn minimised(hwnd: isize) -> bool {
    // SAFETY: reads the state of a window handle.
    unsafe { windows::Win32::UI::WindowsAndMessaging::IsIconic(HWND(hwnd as *mut core::ffi::c_void)).as_bool() }
}

/// The primary screen's area without the taskbar, in logical pixels (x, y, width, height).
pub fn work_area() -> Option<(i32, i32, i32, i32)> {
    let mut rect = RECT::default();
    // SAFETY: SPI_GETWORKAREA writes one RECT into the local.
    let read = unsafe {
        SystemParametersInfoW(SPI_GETWORKAREA, 0, Some(&mut rect as *mut RECT as *mut _), SYSTEM_PARAMETERS_INFO_UPDATE_FLAGS(0))
    };
    read.ok()?;
    // SAFETY: no arguments.
    let dpi = unsafe { GetDpiForSystem() }.max(96) as f64;
    let logical = |v: i32| (f64::from(v) * 96.0 / dpi).round() as i32;
    Some((logical(rect.left), logical(rect.top), logical(rect.right - rect.left), logical(rect.bottom - rect.top)))
}

#[cfg(test)]
mod tests {
    use super::*;
    use windows::core::w;
    use windows::Win32::UI::WindowsAndMessaging::{
        CreateWindowExW, DestroyWindow, IsIconic, ShowWindow, SW_MINIMIZE, WINDOW_EX_STYLE, WS_OVERLAPPEDWINDOW,
    };

    /// The tray's 显示 on a window the player minimised to go back to the game: it comes back, not left minimised.
    #[test]
    fn a_minimised_window_is_brought_back() {
        // SAFETY: a plain window of the system's STATIC class, made, minimised and destroyed here.
        let hwnd = unsafe {
            CreateWindowExW(WINDOW_EX_STYLE(0), w!("STATIC"), w!("bring back"), WS_OVERLAPPEDWINDOW, 100, 100, 320, 200, None, None, None, None)
        }
        .expect("a window");
        unsafe {
            let _ = ShowWindow(hwnd, SW_MINIMIZE);
        }
        assert!(minimised(hwnd.0 as isize), "minimised first");
        assert!(bring_back(hwnd.0 as isize), "not brought back");
        assert!(!unsafe { IsIconic(hwnd) }.as_bool());
        // A window already up stays up.
        assert!(bring_back(hwnd.0 as isize));
        let _ = unsafe { DestroyWindow(hwnd) };
    }
}
