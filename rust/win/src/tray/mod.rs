//! The tray icon and its menu, as blacklist_detect/ui.py builds them (MainWindow.__init__, `_on_tray`,
//! `_show_from_tray`, `closeEvent`).
//!
//! What the player sees, the same as the Python app (tests/golden/tray.json, written by
//! tools/rust_golden_tray.py):
//! - the icon is blacklist_detect/assets/app.ico; it has no tooltip and shows no balloon notices;
//! - the menu (right click) is 显示主窗口, 退出, in that order, both always enabled, no check marks, in every
//!   app state (关闭窗口时 either way, light or dark);
//! - a left click or a double click brings the main window back; a middle click does nothing;
//! - the window's X hides it to the tray when 关闭窗口时 is 最小化到托盘 and the icon shows; otherwise it quits.
//!
//! # Wiring (for the app package)
//!
//! On Windows, [`Tray::spawn`] puts the icon up on a thread of its own and sends each [`TrayAction`] over the
//! `std::sync::mpsc::Sender` it is given. The app's loop receives them:
//!
//! | `TrayAction` | from | the app does (ui.py) |
//! |---|---|---|
//! | `ShowMainWindow` | 显示主窗口, a left click, a double click | `_show_from_tray`: show, un-minimize, raise, focus |
//! | `Quit` | 退出 | `close()` not spontaneous: the real quit (stop the check, hotkeys, ...) |
//!
//! `Tray::is_shown` tells the X button (see [`model::x_button`]) whether hiding to the tray is safe. Dropping
//! the `Tray` removes the icon and ends its thread. When Explorer restarts, the icon is put back by itself
//! (the `TaskbarCreated` message).

pub mod icon;
pub mod model;

#[cfg(windows)]
mod shell;
#[cfg(windows)]
pub use shell::{Tray, TrayError};

#[cfg(test)]
mod tests;

/// What a tray click or a menu item asks the app to do. Sent over the channel given to `Tray::spawn`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum TrayAction {
    /// 显示主窗口, or a left / double click on the icon: bring the main window back, in front.
    ShowMainWindow,
    /// 退出: close the app for real, as the menu's 退出 does in Python.
    Quit,
}
