//! The icon in the Windows notification area: Shell_NotifyIconW on a hidden window of its own thread.
//!
//! The window is a hidden top-level popup, not a message-only window: Explorer broadcasts `TaskbarCreated`
//! (sent when it restarts) to top-level windows only, and that is when the icon is put back.

use super::icon::{pick, APP_ICO};
use super::model::{self, action_for_command, click_for_event, command_id, menu, on_click, ClickOutcome, TrayState};
use super::TrayAction;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::mpsc::{self, Sender};
use std::sync::Arc;
use std::thread::JoinHandle;
use windows::core::{w, PCWSTR};
use windows::Win32::Foundation::{GetLastError, ERROR_CLASS_ALREADY_EXISTS, HWND, LPARAM, LRESULT, WPARAM};
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::Shell::{
    Shell_NotifyIconW, NIF_ICON, NIF_MESSAGE, NIF_SHOWTIP, NIF_TIP, NIM_ADD, NIM_DELETE, NIM_SETVERSION, NOTIFYICONDATAW,
    NOTIFYICON_VERSION_4,
};
use windows::Win32::UI::WindowsAndMessaging::{
    AppendMenuW, CreateIconFromResourceEx, CreatePopupMenu, CreateWindowExW, DefWindowProcW, DestroyIcon, DestroyMenu,
    DestroyWindow, DispatchMessageW, GetMessageW, GetSystemMetrics, GetWindowLongPtrW, PostMessageW,
    PostQuitMessage, RegisterClassExW, RegisterWindowMessageW, SetForegroundWindow, SetWindowLongPtrW, TrackPopupMenuEx,
    TranslateMessage, GWLP_USERDATA, HICON, LR_DEFAULTCOLOR, MF_CHECKED, MF_GRAYED, MF_SEPARATOR, MF_STRING, MSG,
    SM_CXSMICON, TPM_NONOTIFY, TPM_RETURNCMD, TPM_RIGHTBUTTON, WINDOW_EX_STYLE, WM_APP, WM_CLOSE, WM_DESTROY, WM_NULL,
    WNDCLASSEXW, WS_POPUP,
};

/// The icon's callback message.
pub(crate) const CALLBACK: u32 = WM_APP + 1;
/// A menu command, as if chosen in the menu (wParam is the command id). Used by the menu and by tests.
pub(crate) const COMMAND: u32 = WM_APP + 2;
const ICON_ID: u32 = 1;
const CLASS: PCWSTR = w!("BlacklistDetectTray");

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TrayError {
    /// The hidden window could not be made (the Win32 error text).
    Window(String),
    /// The tray thread stopped before it was ready.
    Thread,
}

/// The tray icon, up while this lives. Dropping it removes the icon.
pub struct Tray {
    hwnd: isize,
    shown: Arc<AtomicBool>,
    adds: Arc<AtomicUsize>,
    thread: Option<JoinHandle<()>>,
}

struct State {
    sender: Sender<TrayAction>,
    shown: Arc<AtomicBool>,
    adds: Arc<AtomicUsize>,
    icon: HICON,
    taskbar_created: u32,
}

impl Tray {
    /// Puts the icon up and sends each click or menu choice to `sender`. The icon may not show at once (no
    /// taskbar yet, as at 开机启动); it then comes up when the taskbar does.
    pub fn spawn(sender: Sender<TrayAction>) -> Result<Tray, TrayError> {
        let shown = Arc::new(AtomicBool::new(false));
        let adds = Arc::new(AtomicUsize::new(0));
        let (ready_tx, ready_rx) = mpsc::channel();
        let (thread_shown, thread_adds) = (shown.clone(), adds.clone());
        let thread = std::thread::Builder::new()
            .name("tray".into())
            .spawn(move || run(sender, thread_shown, thread_adds, ready_tx))
            .map_err(|_| TrayError::Thread)?;
        let hwnd = ready_rx.recv().map_err(|_| TrayError::Thread)??;
        Ok(Tray { hwnd, shown, adds, thread: Some(thread) })
    }

    /// Whether the icon is in the tray now (so the window's X may hide to it, see `model::x_button`).
    pub fn is_shown(&self) -> bool {
        self.shown.load(Ordering::SeqCst)
    }

    /// How many times the icon was added: 1, plus one per Explorer restart.
    pub fn times_added(&self) -> usize {
        self.adds.load(Ordering::SeqCst)
    }

    pub(crate) fn hwnd(&self) -> HWND {
        HWND(self.hwnd as *mut _)
    }
}

impl Drop for Tray {
    fn drop(&mut self) {
        // SAFETY: posts a plain message to the tray window; if it is already gone the call just fails.
        let _ = unsafe { PostMessageW(Some(self.hwnd()), WM_CLOSE, WPARAM(0), LPARAM(0)) };
        if let Some(thread) = self.thread.take() {
            let _ = thread.join();
        }
    }
}

fn run(sender: Sender<TrayAction>, shown: Arc<AtomicBool>, adds: Arc<AtomicUsize>, ready: Sender<Result<isize, TrayError>>) {
    let hwnd = match make_window() {
        Ok(hwnd) => hwnd,
        Err(error) => {
            let _ = ready.send(Err(error));
            return;
        }
    };
    // SAFETY: a fixed, NUL-ended name.
    let taskbar_created = unsafe { RegisterWindowMessageW(w!("TaskbarCreated")) };
    let state = Box::new(State { sender, shown, adds, icon: load_icon(), taskbar_created });
    let state = Box::into_raw(state);
    // SAFETY: the window is ours and alive; the pointer is freed once, in WM_DESTROY, on this thread.
    unsafe { SetWindowLongPtrW(hwnd, GWLP_USERDATA, state as isize) };
    // SAFETY: state was just made from a Box and is not freed until WM_DESTROY.
    add_icon(hwnd, unsafe { &*state });
    let _ = ready.send(Ok(hwnd.0 as isize));
    let mut msg = MSG::default();
    // SAFETY: msg is a valid MSG this function owns.
    while unsafe { GetMessageW(&mut msg, None, 0, 0) }.0 > 0 {
        // SAFETY: msg came from GetMessageW just above.
        unsafe {
            let _ = TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    }
}

fn make_window() -> Result<HWND, TrayError> {
    let error = |e: windows::core::Error| TrayError::Window(e.message());
    // SAFETY: no pointers but the class name, a static string, and the window procedure below.
    unsafe {
        let instance = GetModuleHandleW(None).map_err(error)?;
        let class = WNDCLASSEXW {
            cbSize: std::mem::size_of::<WNDCLASSEXW>() as u32,
            lpfnWndProc: Some(window_proc),
            hInstance: instance.into(),
            lpszClassName: CLASS,
            ..Default::default()
        };
        if RegisterClassExW(&class) == 0 && GetLastError() != ERROR_CLASS_ALREADY_EXISTS {
            return Err(TrayError::Window(windows::core::Error::from_win32().message()));
        }
        CreateWindowExW(WINDOW_EX_STYLE(0), CLASS, w!(""), WS_POPUP, 0, 0, 0, 0, None, None, Some(instance.into()), None)
            .map_err(error)
    }
}

/// app.ico at the small-icon size of this screen (16 px at 100 %, 24 at 150 %).
fn load_icon() -> HICON {
    // SAFETY: a plain query.
    let size = unsafe { GetSystemMetrics(SM_CXSMICON) }.max(16);
    let Some(bits) = pick(APP_ICO, size as u32) else { return HICON::default() };
    // SAFETY: bits is one whole PNG picture from the icon file; Windows copies it.
    unsafe { CreateIconFromResourceEx(bits, true, 0x0003_0000, size, size, LR_DEFAULTCOLOR) }.unwrap_or_default()
}

fn icon_data(hwnd: HWND) -> NOTIFYICONDATAW {
    NOTIFYICONDATAW {
        cbSize: std::mem::size_of::<NOTIFYICONDATAW>() as u32,
        hWnd: hwnd,
        uID: ICON_ID,
        ..Default::default()
    }
}

fn add_icon(hwnd: HWND, state: &State) {
    let mut data = icon_data(hwnd);
    data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_SHOWTIP;
    data.uCallbackMessage = CALLBACK;
    data.hIcon = state.icon;
    data.szTip = model::wide_fixed(model::TOOLTIP);
    // SAFETY: data is a whole NOTIFYICONDATAW with its size set, alive for the call.
    let added = unsafe { Shell_NotifyIconW(NIM_ADD, &data) }.as_bool();
    if added {
        data.Anonymous.uVersion = NOTIFYICON_VERSION_4;
        // SAFETY: as above.
        let _ = unsafe { Shell_NotifyIconW(NIM_SETVERSION, &data) };
        state.adds.fetch_add(1, Ordering::SeqCst);
    }
    state.shown.store(added, Ordering::SeqCst);
}

fn remove_icon(hwnd: HWND, state: &State) {
    let data = icon_data(hwnd);
    // SAFETY: as in add_icon; removing an icon that is not there just fails.
    let _ = unsafe { Shell_NotifyIconW(NIM_DELETE, &data) };
    state.shown.store(false, Ordering::SeqCst);
}

/// The menu at (x, y) on the screen; returns the chosen command id, 0 for none.
fn show_menu(hwnd: HWND, x: i32, y: i32) -> usize {
    let items = menu(&TrayState::default());
    // SAFETY: the menu is made, shown and destroyed here; each text is a NUL-ended buffer alive for its call.
    unsafe {
        let Ok(popup) = CreatePopupMenu() else { return 0 };
        for (index, item) in items.iter().enumerate() {
            let text: Vec<u16> = item.text.encode_utf16().chain([0]).collect();
            let mut flags = if item.separator { MF_SEPARATOR } else { MF_STRING };
            if !item.enabled {
                flags |= MF_GRAYED;
            }
            if item.checked {
                flags |= MF_CHECKED;
            }
            let _ = AppendMenuW(popup, flags, command_id(index), PCWSTR(text.as_ptr()));
        }
        // Without this the menu stays open when the player clicks elsewhere (KB135788).
        let _ = SetForegroundWindow(hwnd);
        let chosen = TrackPopupMenuEx(popup, (TPM_RETURNCMD | TPM_RIGHTBUTTON | TPM_NONOTIFY).0, x, y, hwnd, None);
        let _ = PostMessageW(Some(hwnd), WM_NULL, WPARAM(0), LPARAM(0));
        let _ = DestroyMenu(popup);
        usize::try_from(chosen.0).unwrap_or(0)
    }
}

/// The signed x and y packed in the low and high words (GET_X_LPARAM / GET_Y_LPARAM).
fn point(packed: usize) -> (i32, i32) {
    (i32::from(packed as u16 as i16), i32::from((packed >> 16) as u16 as i16))
}

fn send_command(state: &State, id: usize) {
    if let Some(action) = action_for_command(&TrayState::default(), id) {
        let _ = state.sender.send(action);
    }
}

unsafe extern "system" fn window_proc(hwnd: HWND, msg: u32, wparam: WPARAM, lparam: LPARAM) -> LRESULT {
    // SAFETY: GWLP_USERDATA holds our State from run() until WM_DESTROY clears it; null before and after.
    let state = unsafe { (GetWindowLongPtrW(hwnd, GWLP_USERDATA) as *const State).as_ref() };
    let Some(state) = state else {
        // SAFETY: the default handling for a message we do not take.
        return unsafe { DefWindowProcW(hwnd, msg, wparam, lparam) };
    };
    match msg {
        CALLBACK => {
            let event = (lparam.0 as u32) & 0xFFFF;
            match click_for_event(event).map(on_click) {
                Some(ClickOutcome::Send(action)) => {
                    let _ = state.sender.send(action);
                }
                Some(ClickOutcome::OpenMenu) => {
                    // NOTIFYICON_VERSION_4: wParam holds where the menu goes, in screen coordinates.
                    let (x, y) = point(wparam.0);
                    send_command(state, show_menu(hwnd, x, y));
                }
                Some(ClickOutcome::Nothing) | None => {}
            }
            LRESULT(0)
        }
        COMMAND => {
            send_command(state, wparam.0);
            LRESULT(0)
        }
        WM_CLOSE => {
            // SAFETY: our own window, on its own thread.
            let _ = unsafe { DestroyWindow(hwnd) };
            LRESULT(0)
        }
        WM_DESTROY => {
            remove_icon(hwnd, state);
            // SAFETY: the pointer came from Box::into_raw in run() and is cleared before it is freed, once.
            unsafe {
                SetWindowLongPtrW(hwnd, GWLP_USERDATA, 0);
                let state = Box::from_raw(state as *const State as *mut State);
                if !state.icon.is_invalid() {
                    let _ = DestroyIcon(state.icon);
                }
                PostQuitMessage(0);
            }
            LRESULT(0)
        }
        _ if msg == state.taskbar_created && msg != 0 => {
            // Explorer restarted: its new taskbar has no icon of ours.
            add_icon(hwnd, state);
            LRESULT(0)
        }
        // SAFETY: the default handling for a message we do not take.
        _ => unsafe { DefWindowProcW(hwnd, msg, wparam, lparam) },
    }
}

/// Whether the tray window still exists (tests).
#[cfg(test)]
fn window_alive(hwnd: HWND) -> bool {
    // SAFETY: IsWindow takes any handle, even a stale one.
    unsafe { windows::Win32::UI::WindowsAndMessaging::IsWindow(Some(hwnd)) }.as_bool()
}

#[cfg(test)]
#[path = "shell_tests.rs"]
mod tests;
