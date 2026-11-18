//! A Windows global hotkey (hotkey.py's GlobalHotkey): RegisterHotKey on this thread, no window. The key
//! is not synthesized into the lobby. Ident tells two apart: 检查's is 1, the 场景 hotkey's 2.

use crate::hotkey::HotkeySpec;
use windows::Win32::UI::Input::KeyboardAndMouse::{RegisterHotKey, UnregisterHotKey, HOT_KEY_MODIFIERS};
use windows::Win32::UI::WindowsAndMessaging::{PeekMessageW, MSG, PM_REMOVE, WM_HOTKEY};

pub const CHECK_ID: i32 = 1;
pub const SCENE_ID: i32 = 2;

#[derive(Debug, PartialEq, Eq)]
pub enum HotkeyError {
    /// "这个键用不了，换一个": Windows or another program holds it.
    Taken,
}

/// A registered hotkey; dropping it unregisters it. Belongs to the thread that registered it, whose
/// message queue receives WM_HOTKEY.
#[derive(Debug)]
pub struct Registration {
    id: i32,
    display: String,
    _thread_bound: std::marker::PhantomData<*const ()>,
}

impl Registration {
    pub fn register(id: i32, spec: &HotkeySpec) -> Result<Registration, HotkeyError> {
        // SAFETY: no window handle and no pointers; the id and key codes are plain numbers.
        unsafe { RegisterHotKey(None, id, HOT_KEY_MODIFIERS(spec.win_modifiers()), spec.vk) }.map_err(|_| HotkeyError::Taken)?;
        Ok(Registration { id, display: spec.display.clone(), _thread_bound: std::marker::PhantomData })
    }

    pub fn id(&self) -> i32 {
        self.id
    }

    /// The key in its display form, as 设置 shows it.
    pub fn display(&self) -> &str {
        &self.display
    }
}

impl Drop for Registration {
    fn drop(&mut self) {
        // SAFETY: unregisters the id this thread registered; no pointers.
        let _ = unsafe { UnregisterHotKey(None, self.id) };
    }
}

/// The hotkey id of a message, when it is WM_HOTKEY.
pub fn hotkey_id(msg: &MSG) -> Option<i32> {
    (msg.message == WM_HOTKEY).then_some(msg.wParam.0 as i32)
}

/// Take one waiting WM_HOTKEY off this thread's queue, without blocking; its id.
pub fn poll() -> Option<i32> {
    let mut msg = MSG::default();
    // SAFETY: msg is a valid MSG this function owns; only WM_HOTKEY messages are removed.
    let got = unsafe { PeekMessageW(&mut msg, None, WM_HOTKEY, WM_HOTKEY, PM_REMOVE) }.as_bool();
    if got { hotkey_id(&msg) } else { None }
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
}
