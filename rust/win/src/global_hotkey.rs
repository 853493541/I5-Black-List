//! A Windows global hotkey (hotkey.py's GlobalHotkey): RegisterHotKey on a message-only window of this thread. The
//! key is not synthesized into the lobby. Ident tells two apart: 检查's is 1, the 场景 hotkey's 2.
//!
//! Not a thread hotkey (no window): its WM_HOTKEY lands in the thread's queue with no window, and the window's event
//! loop (winit) takes every message off that queue and dispatches it, which drops a message with no window. The 50 ms
//! timer's PeekMessage found nothing, so the hotkey did nothing. A window of our own gets the message dispatched to
//! its procedure by whatever loop runs the thread, which queues the id for [`poll`].
#![allow(unsafe_code)]

use crate::hotkey::HotkeySpec;
use std::cell::{Cell, RefCell};
use std::collections::VecDeque;
use windows::core::w;
use windows::Win32::Foundation::{HWND, LPARAM, LRESULT, WPARAM};
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::Input::KeyboardAndMouse::{RegisterHotKey, UnregisterHotKey, HOT_KEY_MODIFIERS};
use windows::Win32::UI::WindowsAndMessaging::{
    CreateWindowExW, DefWindowProcW, PeekMessageW, RegisterClassW, HWND_MESSAGE, MSG, PM_REMOVE, WINDOW_EX_STYLE,
    WINDOW_STYLE, WM_HOTKEY, WNDCLASSW,
};

pub const CHECK_ID: i32 = 1;
pub const SCENE_ID: i32 = 2;

#[derive(Debug, PartialEq, Eq)]
pub enum HotkeyError {
    Taken,
}

thread_local! {
    /// This thread's message-only window for WM_HOTKEY (0 until the first registration), and the presses it got.
    static WINDOW: Cell<isize> = const { Cell::new(0) };
    static PRESSED: RefCell<VecDeque<i32>> = const { RefCell::new(VecDeque::new()) };
}

extern "system" fn proc(hwnd: HWND, msg: u32, w: WPARAM, l: LPARAM) -> LRESULT {
    if msg == WM_HOTKEY {
        PRESSED.with(|pressed| pressed.borrow_mut().push_back(w.0 as i32));
        return LRESULT(0);
    }
    // SAFETY: the default handling of a message sent to our own window.
    unsafe { DefWindowProcW(hwnd, msg, w, l) }
}

/// This thread's hotkey window, made on first use; None when Windows refuses to make it.
pub fn window() -> Option<HWND> {
    let made = WINDOW.with(Cell::get);
    if made != 0 {
        return Some(HWND(made as *mut core::ffi::c_void));
    }
    static CLASS: std::sync::Once = std::sync::Once::new();
    // SAFETY: the module handle of this exe; a class registered once; a message-only window owned by this thread.
    let hwnd = unsafe {
        let instance = GetModuleHandleW(None).ok()?;
        CLASS.call_once(|| {
            let class = WNDCLASSW { lpfnWndProc: Some(proc), hInstance: instance.into(), lpszClassName: w!("BlacklistDetectHotkeys"), ..Default::default() };
            RegisterClassW(&class);
        });
        CreateWindowExW(
            WINDOW_EX_STYLE(0),
            w!("BlacklistDetectHotkeys"),
            w!(""),
            WINDOW_STYLE(0),
            0,
            0,
            0,
            0,
            Some(HWND_MESSAGE),
            None,
            Some(instance.into()),
            None,
        )
        .ok()?
    };
    WINDOW.with(|cell| cell.set(hwnd.0 as isize));
    Some(hwnd)
}

/// A registered hotkey; dropping it unregisters it. Belongs to the thread that registered it, whose hotkey window
/// receives WM_HOTKEY.
#[derive(Debug)]
pub struct Registration {
    id: i32,
    display: String,
    hwnd: isize,
    _thread_bound: std::marker::PhantomData<*const ()>,
}

impl Registration {
    /// Registers the key for this thread's hotkey window; Taken when another program (or this one) holds it.
    pub fn register(id: i32, spec: &HotkeySpec) -> Result<Registration, HotkeyError> {
        let hwnd = window().ok_or(HotkeyError::Taken)?;
        // SAFETY: registers a hotkey for our own window.
        unsafe { RegisterHotKey(Some(hwnd), id, HOT_KEY_MODIFIERS(spec.win_modifiers()), spec.vk) }.map_err(|_| HotkeyError::Taken)?;
        Ok(Registration { id, display: spec.display.clone(), hwnd: hwnd.0 as isize, _thread_bound: std::marker::PhantomData })
    }

    pub fn id(&self) -> i32 {
        self.id
    }

    pub fn display(&self) -> &str {
        &self.display
    }
}

impl Drop for Registration {
    fn drop(&mut self) {
        // SAFETY: unregisters what `register` registered for the same window.
        let _ = unsafe { UnregisterHotKey(Some(HWND(self.hwnd as *mut core::ffi::c_void)), self.id) };
    }
}

/// The hotkey id of a message, when it is WM_HOTKEY.
pub fn hotkey_id(msg: &MSG) -> Option<i32> {
    (msg.message == WM_HOTKEY).then_some(msg.wParam.0 as i32)
}

/// One waiting press, without blocking: the ones the hotkey window was handed (by any loop that dispatched them),
/// then a WM_HOTKEY still in this thread's queue (no event loop ran since).
pub fn poll() -> Option<i32> {
    if let Some(id) = PRESSED.with(|pressed| pressed.borrow_mut().pop_front()) {
        return Some(id);
    }
    let mut msg = MSG::default();
    // SAFETY: takes at most one WM_HOTKEY of this thread's into the local.
    let got = unsafe { PeekMessageW(&mut msg, None, WM_HOTKEY, WM_HOTKEY, PM_REMOVE) }.as_bool();
    if got {
        if msg.hwnd.0.is_null() {
            return hotkey_id(&msg);
        }
        proc(msg.hwnd, msg.message, msg.wParam, msg.lParam);
        return PRESSED.with(|pressed| pressed.borrow_mut().pop_front());
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hotkey::parse_hotkey;
    use windows::Win32::Foundation::{LPARAM, WPARAM};
    use windows::Win32::System::Threading::GetCurrentThreadId;
    use windows::Win32::UI::WindowsAndMessaging::PostThreadMessageW;

    #[test]
    fn registering_and_unregistering_a_hotkey() {
        // A key nobody uses, so the runner (or a desktop) has it free.
        let spec = parse_hotkey("Ctrl+Alt+Shift+F11").unwrap();
        let first = Registration::register(41, &spec).expect("a free key registers");
        assert_eq!((first.id(), first.display()), (41, "Ctrl+Alt+Shift+F11"));
        // The same key twice is refused while the first holds it.
        assert_eq!(Registration::register(42, &spec).unwrap_err(), HotkeyError::Taken);
        drop(first);
        // Unregistered: it can be taken again.
        let again = Registration::register(43, &spec).expect("freed by drop");
        drop(again);
    }

    #[test]
    fn a_hotkey_message_reaches_its_id() {
        assert_eq!(poll(), None);
        // SAFETY: posts a plain message to this thread's own queue.
        unsafe { PostThreadMessageW(GetCurrentThreadId(), WM_HOTKEY, WPARAM(SCENE_ID as usize), LPARAM(0)) }.unwrap();
        assert_eq!(poll(), Some(SCENE_ID));
        assert_eq!(poll(), None);
    }

    #[test]
    fn a_press_survives_an_event_loop_that_dispatches_it_first() {
        // winit's loop takes every message and dispatches it before the timer polls; the press must still arrive.
        let hwnd = window().expect("the hotkey window");
        unsafe { windows::Win32::UI::WindowsAndMessaging::PostMessageW(Some(hwnd), WM_HOTKEY, WPARAM(CHECK_ID as usize), LPARAM(0)) }.unwrap();
        let mut msg = MSG::default();
        while unsafe { PeekMessageW(&mut msg, None, 0, 0, PM_REMOVE) }.as_bool() {
            unsafe { windows::Win32::UI::WindowsAndMessaging::DispatchMessageW(&msg) };
        }
        assert_eq!(poll(), Some(CHECK_ID));
        assert_eq!(poll(), None);
    }
}
