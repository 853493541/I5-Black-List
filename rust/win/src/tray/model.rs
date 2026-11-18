//! The tray menu and clicks as plain data, the same on every system and tested against the Python app.

use super::TrayAction;

/// The tooltip on the icon. Python never sets one (QSystemTrayIcon's toolTip() is empty), so hovering shows none.
pub const TOOLTIP: &str = "";

/// The app state the menu could depend on. In Python it does not: the menu is the same in every state.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TrayState {
    /// 关闭窗口时: 最小化到托盘 (true, the default) or 退出程序.
    pub close_to_tray: bool,
    /// 深色 (true) or 浅色.
    pub dark: bool,
}

impl Default for TrayState {
    fn default() -> Self {
        Self { close_to_tray: true, dark: false }
    }
}

/// One menu row.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MenuItem {
    pub text: &'static str,
    pub enabled: bool,
    pub checkable: bool,
    pub checked: bool,
    pub separator: bool,
    /// What choosing it sends; None for a separator.
    pub action: Option<TrayAction>,
}

impl MenuItem {
    const fn action(text: &'static str, action: TrayAction) -> Self {
        Self { text, enabled: true, checkable: false, checked: false, separator: false, action: Some(action) }
    }
}

/// The menu, top to bottom, as ui.py adds it: 显示主窗口, 退出.
pub fn menu(_state: &TrayState) -> Vec<MenuItem> {
    vec![
        MenuItem::action("显示主窗口", TrayAction::ShowMainWindow),
        MenuItem::action("退出", TrayAction::Quit),
    ]
}

/// The command id a menu row has in the Win32 menu: its place plus one (0 means "nothing chosen").
pub fn command_id(index: usize) -> usize {
    index + 1
}

/// The action for a command id TrackPopupMenuEx returned.
pub fn action_for_command(state: &TrayState, id: usize) -> Option<TrayAction> {
    let index = id.checked_sub(1)?;
    menu(state).get(index).filter(|item| item.enabled).and_then(|item| item.action)
}

/// A click on the icon, as Qt names them (QSystemTrayIcon::ActivationReason).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Click {
    Unknown,
    /// Right click (or the menu key): the menu opens.
    Context,
    DoubleClick,
    /// A left click (or Enter / space on the focused icon).
    Trigger,
    MiddleClick,
}

impl Click {
    pub const ALL: [Click; 5] = [Click::Unknown, Click::Context, Click::DoubleClick, Click::Trigger, Click::MiddleClick];

    /// Qt's name for it, as tray.json has it.
    pub fn qt_name(self) -> &'static str {
        match self {
            Click::Unknown => "Unknown",
            Click::Context => "Context",
            Click::DoubleClick => "DoubleClick",
            Click::Trigger => "Trigger",
            Click::MiddleClick => "MiddleClick",
        }
    }
}

/// What a click does: ui.py's `_on_tray` (Trigger and DoubleClick show the window; Context opens the menu).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ClickOutcome {
    Send(TrayAction),
    OpenMenu,
    Nothing,
}

pub fn on_click(click: Click) -> ClickOutcome {
    match click {
        Click::Trigger | Click::DoubleClick => ClickOutcome::Send(TrayAction::ShowMainWindow),
        Click::Context => ClickOutcome::OpenMenu,
        Click::Unknown | Click::MiddleClick => ClickOutcome::Nothing,
    }
}

// The icon's callback events, NOTIFYICON_VERSION_4 (the low word of lParam), the ones Qt maps.
pub const WM_CONTEXTMENU: u32 = 0x007B;
pub const WM_LBUTTONDBLCLK: u32 = 0x0203;
pub const WM_MBUTTONUP: u32 = 0x0208;
pub const NIN_SELECT: u32 = 0x0400;
pub const NIN_KEYSELECT: u32 = 0x0401;

/// The click for a tray callback event, as Qt's Windows tray maps it (qwindowssystemtrayicon.cpp).
pub fn click_for_event(event: u32) -> Option<Click> {
    match event {
        NIN_SELECT | NIN_KEYSELECT => Some(Click::Trigger),
        WM_LBUTTONDBLCLK => Some(Click::DoubleClick),
        WM_CONTEXTMENU => Some(Click::Context),
        WM_MBUTTONUP => Some(Click::MiddleClick),
        _ => None,
    }
}

/// What the main window's X does (ui.py's closeEvent, for a click by the player).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CloseOutcome {
    /// Hide the window and keep checking from the tray.
    HideToTray,
    /// Close for real.
    Quit,
}

/// Without a tray icon there would be no way back, so X quits then.
pub fn x_button(close_to_tray: bool, tray_shown: bool) -> CloseOutcome {
    if close_to_tray && tray_shown {
        CloseOutcome::HideToTray
    } else {
        CloseOutcome::Quit
    }
}

/// `text` as a NUL-ended UTF-16 array of N units, cut to fit (NOTIFYICONDATAW.szTip is 128).
pub fn wide_fixed<const N: usize>(text: &str) -> [u16; N] {
    let mut out = [0u16; N];
    for (slot, unit) in out.iter_mut().take(N.saturating_sub(1)).zip(text.encode_utf16()) {
        *slot = unit;
    }
    out
}
