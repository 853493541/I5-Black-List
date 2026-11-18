//! Copy the desktop once (capture.py): one GDI BitBlt of the whole virtual screen. No capture window, no
//! display-mode change, no game window looked up, no input sent. Plus the foreground helpers it carries.

use crate::frame::{Frame, VirtualScreen, TITLE_BAND_FRACTION};
use std::ffi::c_void;
use windows::Win32::Foundation::HWND;
use windows::Win32::Graphics::Gdi::{
    BitBlt, CreateCompatibleDC, CreateDIBSection, DeleteDC, DeleteObject, GetDC, ReleaseDC, SelectObject, BITMAPINFO,
    BITMAPINFOHEADER, BI_RGB, DIB_RGB_COLORS, HBITMAP, HDC, HGDIOBJ, SRCCOPY,
};
use windows::Win32::System::Threading::GetCurrentThreadId;
use windows::Win32::UI::HiDpi::{SetProcessDpiAwarenessContext, DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2};
use windows::Win32::UI::WindowsAndMessaging::{
    AllowSetForegroundWindow, BringWindowToTop, GetForegroundWindow, GetSystemMetrics, GetWindowThreadProcessId, IsIconic,
    LockSetForegroundWindow, SetForegroundWindow, ShowWindow, ASFW_ANY, LSFW_LOCK, LSFW_UNLOCK, SM_CXVIRTUALSCREEN,
    SM_CYVIRTUALSCREEN, SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SW_RESTORE,
};

#[derive(Debug, PartialEq, Eq)]
pub enum CaptureError {
    /// "截屏失败，再试一次": the copy failed this time.
    Failed,
}

/// Per-monitor (v2) DPI awareness, as the Qt app runs: screen pixels, not scaled ones. Call before any
/// window opens. False when the process already had an awareness set (by its manifest, for example).
pub fn set_dpi_awareness() -> bool {
    // SAFETY: takes a constant awareness context and touches no memory of ours.
    unsafe { SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2) }.is_ok()
}

/// The virtual screen: every monitor's union.
pub fn virtual_screen() -> VirtualScreen {
    // SAFETY: GetSystemMetrics reads a system value; no pointers.
    let metric = |index| unsafe { GetSystemMetrics(index) };
    VirtualScreen {
        left: metric(SM_XVIRTUALSCREEN),
        top: metric(SM_YVIRTUALSCREEN),
        width: metric(SM_CXVIRTUALSCREEN),
        height: metric(SM_CYVIRTUALSCREEN),
    }
}

/// Top-left of the desktop copy, in screen pixels.
pub fn virtual_origin() -> (i32, i32) {
    let screen = virtual_screen();
    (screen.left, screen.top)
}

/// One RGB frame of the whole desktop.
pub fn capture_displays() -> Result<Vec<Frame>, CaptureError> {
    grab(1.0).map(|frame| vec![frame])
}

/// The top of the desktop, where the match-found title is.
pub fn capture_top_band() -> Result<Frame, CaptureError> {
    grab(TITLE_BAND_FRACTION)
}

/// The screen's device context, released on drop.
struct ScreenDc(HDC);

impl Drop for ScreenDc {
    fn drop(&mut self) {
        // SAFETY: self.0 came from GetDC(None) and is released once.
        unsafe { ReleaseDC(None, self.0) };
    }
}

/// A memory DC with a DIB section selected into it, undone on drop.
struct DibCopy {
    memory: HDC,
    bitmap: HBITMAP,
    old: HGDIOBJ,
    bits: *mut c_void,
}

impl Drop for DibCopy {
    fn drop(&mut self) {
        // SAFETY: each object was created by DibCopy::new and is put back and deleted once, bitmap after it
        // is deselected.
        unsafe {
            if !self.old.is_invalid() {
                SelectObject(self.memory, self.old);
            }
            if !self.bitmap.is_invalid() {
                let _ = DeleteObject(self.bitmap.into());
            }
            if !self.memory.is_invalid() {
                let _ = DeleteDC(self.memory);
            }
        }
    }
}

impl DibCopy {
    /// A top-down 32-bit DIB of width x height, compatible with the screen.
    fn new(screen: HDC, width: i32, height: i32) -> Option<DibCopy> {
        let header = BITMAPINFOHEADER {
            biSize: size_of::<BITMAPINFOHEADER>() as u32,
            biWidth: width,
            biHeight: -height,
            biPlanes: 1,
            biBitCount: 32,
            biCompression: BI_RGB.0,
            ..Default::default()
        };
        let info = BITMAPINFO { bmiHeader: header, ..Default::default() };
        // SAFETY: screen is a live DC; the DibCopy owns what is created and frees it on drop, also when a
        // later step fails. `bits` is written by CreateDIBSection and lives as long as the bitmap.
        unsafe {
            let mut copy = DibCopy { memory: CreateCompatibleDC(Some(screen)), bitmap: HBITMAP::default(), old: HGDIOBJ::default(), bits: std::ptr::null_mut() };
            copy.bitmap = CreateDIBSection(Some(screen), &info, DIB_RGB_COLORS, &mut copy.bits, None, 0).ok()?;
            if copy.memory.is_invalid() || copy.bits.is_null() {
                return None;
            }
            copy.old = SelectObject(copy.memory, copy.bitmap.into());
            Some(copy)
        }
    }
}

fn grab(fraction: f64) -> Result<Frame, CaptureError> {
    let screen_rect = virtual_screen();
    let height = screen_rect.band_height(fraction).ok_or(CaptureError::Failed)?;
    let width = screen_rect.width;
    // SAFETY: GetDC(None) is the whole screen's DC; ScreenDc releases it.
    let screen = ScreenDc(unsafe { GetDC(None) });
    if screen.0.is_invalid() {
        return Err(CaptureError::Failed);
    }
    let copy = DibCopy::new(screen.0, width, height).ok_or(CaptureError::Failed)?;
    // SAFETY: both DCs are live; the blit stays inside the DIB's width x height.
    unsafe { BitBlt(copy.memory, 0, 0, width, height, Some(screen.0), screen_rect.left, screen_rect.top, SRCCOPY) }
        .map_err(|_| CaptureError::Failed)?;
    let length = width as usize * height as usize * 4;
    // SAFETY: the DIB section is width x height x 4 bytes, top-down, alive until `copy` drops below.
    let bgra = unsafe { std::slice::from_raw_parts(copy.bits as *const u8, length) };
    let frame = Frame::from_bgra(width as usize, height as usize, bgra);
    drop(copy);
    Ok(frame)
}

/// Let another process take the front: a second launch calls this before it asks the open copy to show.
pub fn allow_any_foreground() {
    // SAFETY: no pointers; ASFW_ANY is a constant.
    let _ = unsafe { AllowSetForegroundWindow(ASFW_ANY) };
}

/// Stop (or allow again) other programs pulling a window to the front.
pub fn lock_foreground(locked: bool) {
    // SAFETY: no pointers.
    let _ = unsafe { LockSetForegroundWindow(if locked { LSFW_LOCK } else { LSFW_UNLOCK }) };
}

/// Put a window in front with the focus, the way clicking it would; joins the input of the window now in
/// front for a moment, since Windows keeps a background app from pulling itself forward.
pub fn bring_to_front(hwnd: HWND) -> bool {
    // SAFETY: every call takes window handles by value; a stale handle makes the calls fail, not crash.
    // AttachThreadInput is undone in the same block.
    unsafe {
        if IsIconic(hwnd).as_bool() {
            let _ = ShowWindow(hwnd, SW_RESTORE);
        }
        let front = GetForegroundWindow();
        if !front.is_invalid() && front == hwnd {
            return true;
        }
        let ours = GetCurrentThreadId();
        let theirs = if front.is_invalid() { 0 } else { GetWindowThreadProcessId(front, None) };
        let joined = theirs != 0 && theirs != ours && windows::Win32::System::Threading::AttachThreadInput(theirs, ours, true).as_bool();
        let _ = BringWindowToTop(hwnd);
        let _ = SetForegroundWindow(hwnd);
        if joined {
            let _ = windows::Win32::System::Threading::AttachThreadInput(theirs, ours, false);
        }
        GetForegroundWindow() == hwnd
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_copy_of_the_desktop_has_the_screen_size() {
        set_dpi_awareness();
        let screen = virtual_screen();
        let frames = capture_displays().expect("the runner has a desktop");
        assert_eq!(frames.len(), 1);
        let full = &frames[0];
        assert_eq!((full.width, full.height), (screen.width as usize, screen.height as usize));
        assert_eq!(full.rgb.len(), full.width * full.height * 3);
        let band = capture_top_band().unwrap();
        assert_eq!(band.width, full.width);
        assert_eq!(band.height as i32, screen.band_height(TITLE_BAND_FRACTION).unwrap());
        assert_eq!(virtual_origin(), (screen.left, screen.top));
    }
}
