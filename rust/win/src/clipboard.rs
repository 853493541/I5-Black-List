//! The Windows clipboard as text (ui._copy_text's QApplication.clipboard): 复制名字 and 复制名单.
#![allow(unsafe_code)]

use windows::Win32::Foundation::{HANDLE, HGLOBAL};
use windows::Win32::System::DataExchange::{CloseClipboard, EmptyClipboard, GetClipboardData, OpenClipboard, SetClipboardData};
use windows::Win32::System::Memory::{GlobalAlloc, GlobalLock, GlobalUnlock, GMEM_MOVEABLE};

/// CF_UNICODETEXT: UTF-16 text ending in a 0.
const UNICODE_TEXT: u32 = 13;

/// Puts `text` on the clipboard; false when Windows would not let us (another program holds it open).
pub fn set_text(text: &str) -> bool {
    let wide: Vec<u16> = text.encode_utf16().chain(std::iter::once(0)).collect();
    // SAFETY: the clipboard is opened and closed here; the memory is ours until SetClipboardData hands it to Windows.
    unsafe {
        if OpenClipboard(None).is_err() {
            return false;
        }
        let put = || -> windows::core::Result<()> {
            EmptyClipboard()?;
            let memory: HGLOBAL = GlobalAlloc(GMEM_MOVEABLE, wide.len() * 2)?;
            let target = GlobalLock(memory) as *mut u16;
            if target.is_null() {
                return Err(windows::core::Error::from_win32());
            }
            std::ptr::copy_nonoverlapping(wide.as_ptr(), target, wide.len());
            let _ = GlobalUnlock(memory);
            SetClipboardData(UNICODE_TEXT, Some(HANDLE(memory.0)))?;
            Ok(())
        };
        let done = put().is_ok();
        let _ = CloseClipboard();
        done
    }
}

/// The clipboard's text, if it holds any.
pub fn get_text() -> Option<String> {
    // SAFETY: the clipboard is opened and closed here; the text is copied out while its memory is locked.
    unsafe {
        OpenClipboard(None).ok()?;
        let read = || -> Option<String> {
            let handle = GetClipboardData(UNICODE_TEXT).ok()?;
            let memory = HGLOBAL(handle.0);
            let source = GlobalLock(memory) as *const u16;
            if source.is_null() {
                return None;
            }
            let length = (0..).take_while(|&i| *source.add(i) != 0).count();
            let text = String::from_utf16_lossy(std::slice::from_raw_parts(source, length));
            let _ = GlobalUnlock(memory);
            Some(text)
        };
        let text = read();
        let _ = CloseClipboard();
        text
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn clipboard_text_goes_in_and_comes_back() {
        assert!(set_text("示例坏人"));
        assert_eq!(get_text().as_deref(), Some("示例坏人"));
    }
}
