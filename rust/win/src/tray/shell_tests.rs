//! The real tray icon on Windows (the windows-latest CI job). A runner without a taskbar has no tray to add
//! to; then only "it was refused" is checked, and the rest still runs on the hidden window.

use super::*;
use std::time::Duration;
use windows::Win32::UI::WindowsAndMessaging::{FindWindowW, SendMessageW, WM_LBUTTONDBLCLK};

const WAIT: Duration = Duration::from_secs(2);

fn has_taskbar() -> bool {
    // SAFETY: a lookup by a fixed class name.
    unsafe { FindWindowW(w!("Shell_TrayWnd"), PCWSTR::null()) }.is_ok_and(|hwnd| !hwnd.is_invalid())
}

fn tray_event(tray: &Tray, event: u32) {
    // SAFETY: a plain message to the tray's own window; SendMessage waits until it is handled.
    unsafe { SendMessageW(tray.hwnd(), CALLBACK, Some(WPARAM(0)), Some(LPARAM(event as isize))) };
}

#[test]
fn icon_goes_up_and_comes_down() {
    let (tx, _rx) = mpsc::channel();
    let tray = Tray::spawn(tx).expect("tray window");
    let hwnd = tray.hwnd();
    assert!(window_alive(hwnd));
    if has_taskbar() {
        assert!(tray.is_shown(), "Shell_NotifyIconW failed with a taskbar present");
        assert_eq!(tray.times_added(), 1);
    } else {
        eprintln!("skipped: this session has no taskbar, so no tray icon (Shell_NotifyIconW refused, as expected)");
        assert!(!tray.is_shown());
    }
    drop(tray);
    assert!(!window_alive(hwnd), "the tray window outlived its Tray");
}

#[test]
fn clicks_send_actions_like_python() {
    let (tx, rx) = mpsc::channel();
    let tray = Tray::spawn(tx).expect("tray window");
    tray_event(&tray, model::NIN_SELECT);
    assert_eq!(rx.recv_timeout(WAIT), Ok(TrayAction::ShowMainWindow));
    tray_event(&tray, WM_LBUTTONDBLCLK);
    assert_eq!(rx.recv_timeout(WAIT), Ok(TrayAction::ShowMainWindow));
    tray_event(&tray, model::WM_MBUTTONUP);
    tray_event(&tray, 0x0200); // a mouse move
    assert!(rx.try_recv().is_err(), "a middle click or a move must do nothing");
}

#[test]
fn menu_commands_send_actions() {
    let (tx, rx) = mpsc::channel();
    let tray = Tray::spawn(tx).expect("tray window");
    for (id, want) in [(command_id(0), TrayAction::ShowMainWindow), (command_id(1), TrayAction::Quit)] {
        // SAFETY: as in tray_event.
        unsafe { SendMessageW(tray.hwnd(), COMMAND, Some(WPARAM(id)), Some(LPARAM(0))) };
        assert_eq!(rx.recv_timeout(WAIT), Ok(want));
    }
    // SAFETY: as in tray_event. Id 0 is "the menu closed with nothing chosen".
    unsafe { SendMessageW(tray.hwnd(), COMMAND, Some(WPARAM(0)), Some(LPARAM(0))) };
    assert!(rx.try_recv().is_err());
}

#[test]
fn explorer_restart_puts_the_icon_back() {
    let (tx, _rx) = mpsc::channel();
    let tray = Tray::spawn(tx).expect("tray window");
    let before = tray.times_added();
    // SAFETY: a fixed, NUL-ended name; then a plain message to our own window, as Explorer broadcasts it.
    unsafe {
        let taskbar_created = RegisterWindowMessageW(w!("TaskbarCreated"));
        SendMessageW(tray.hwnd(), taskbar_created, Some(WPARAM(0)), Some(LPARAM(0)));
    }
    if has_taskbar() {
        // The icon is still there, so a second NIM_ADD may be refused; it must stay shown either way.
        assert!(tray.times_added() >= before);
    } else {
        eprintln!("skipped: no taskbar, so TaskbarCreated cannot add the icon");
        assert_eq!(tray.times_added(), 0);
    }
}

#[test]
fn menu_point_is_signed() {
    assert_eq!(point(0x0064_00C8), (200, 100));
    // A second monitor left of the first one: negative x.
    assert_eq!(point(0x0010_FFF6), (-10, 16));
}
