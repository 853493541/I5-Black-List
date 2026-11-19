//! The main window's frame: the header (page tabs, 有更新, the 检查 pill and its panel, the player's name) and the
//! page area (blacklist_detect/ui.py MainWindow._build, ui_header.py). ui/shell/main.slint draws it.
//!
//! For the app-wiring package: build a [`ShellModel`] from the store ([`ShellModel::from_settings`]), show it with
//! [`apply`], and take what the player does from [`connect`] as [`ShellAction`]s. The frame's own rules are here
//! as plain functions: [`window_size`] at start, [`close_outcome`] on the window's X, [`status_key`] for the pill.

// The app-wiring package calls these; until it lands only the tests do.
#![allow(dead_code)]

pub mod render;

use data::store::settings::Settings;
use data::store::text::parse_hotkey;
use slint::{ComponentHandle, ModelRc, SharedString, VecModel};

use crate::{MainWindow, ShellTab};

/// The window's smallest and first size, in logical pixels (MainWindow.setMinimumSize(900, 560)).
pub const MIN_SIZE: (u32, u32) = (900, 560);

/// The pages, in the header's order.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Page {
    History = 0,
    Blacklist = 1,
    Guests = 2,
    Settings = 3,
}

impl Page {
    pub const ALL: [Page; 4] = [Page::History, Page::Blacklist, Page::Guests, Page::Settings];

    pub fn label(self) -> &'static str {
        ["记录", "黑名单", "嘉宾", "设置"][self as usize]
    }

    pub fn from_index(index: i32) -> Option<Page> {
        usize::try_from(index).ok().and_then(|i| Page::ALL.get(i).copied())
    }
}

/// The pill's look: ui_header.StatusChip's tones.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Tone {
    /// 正在准备识别 and the like: gray dot.
    Idle,
    /// 手动检查, waiting for its hotkey: a hollow ring, the hotkey after the words.
    WatchOff,
    /// 自动检查中: the accent's wash.
    WatchOn,
    /// Something went wrong: red.
    Hit,
}

impl Tone {
    fn name(self) -> &'static str {
        match self {
            Tone::Idle => "idle",
            Tone::WatchOff => "watchOff",
            Tone::WatchOn => "watchOn",
            Tone::Hit => "hit",
        }
    }
}

/// 直播姬's state on the 直播模式 row, while 直播模式 is on.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StreamState {
    pub words: String,
    /// It shows the window: green. Otherwise red and underlined.
    pub ok: bool,
}

/// Everything the frame shows.
#[derive(Debug, Clone, PartialEq)]
pub struct ShellModel {
    pub page: Page,
    /// 黑名单's and 嘉宾's counts on their tabs (0 shows no badge).
    pub blacklist_count: usize,
    pub guests_count: usize,
    pub status_text: String,
    pub tone: Tone,
    /// The hotkey after the words: only while 手动检查 waits for it (MainWindow._set_result, kind "idle").
    pub status_key: String,
    pub has_update: bool,
    pub player_name: String,
    pub safe_mode: bool,
    pub auto_capture: bool,
    pub hotkey: String,
    pub hotkey_waiting: bool,
    pub hotkey_note: String,
    pub stream_on: bool,
    pub stream: Option<StreamState>,
    pub dark: bool,
    pub version: String,
}

impl ShellModel {
    /// The frame as the store's settings leave it at start: 手动检查 with its hotkey, or 自动检查中.
    pub fn from_settings(settings: &Settings) -> ShellModel {
        let shown_key = parse_hotkey(&settings.hotkey).map(|(display, _)| display).unwrap_or_default();
        let (status_text, tone, status_key) = if settings.auto_capture {
            ("自动检查中".to_string(), Tone::WatchOn, String::new())
        } else {
            ("手动检查".to_string(), Tone::WatchOff, shown_key.clone())
        };
        ShellModel {
            page: Page::History,
            blacklist_count: 0,
            guests_count: 0,
            status_text,
            tone,
            status_key,
            has_update: false,
            player_name: settings.player_name.trim().to_string(),
            safe_mode: settings.safe_mode,
            auto_capture: settings.auto_capture,
            hotkey: shown_key,
            hotkey_waiting: false,
            hotkey_note: String::new(),
            stream_on: !settings.stream_mode.is_empty(),
            stream: None,
            dark: settings.appearance == "dark",
            version: String::new(),
        }
    }
}

/// ui_header._initial: the name's first letter, upper-cased; "" for no name.
pub fn initial(name: &str) -> String {
    name.trim().chars().next().map(|c| c.to_uppercase().collect()).unwrap_or_default()
}

/// The hotkey after the pill's words: the store's hotkey as shown, never one that is none.
pub fn status_key(hotkey: &str) -> String {
    parse_hotkey(hotkey).map(|(display, _)| display).unwrap_or_default()
}

/// The window's first size: the saved one (never under the minimum), else 900 x 560.
pub fn window_size(settings: &Settings) -> (u32, u32) {
    match settings.window_size {
        Some((w, h)) => (clamp(w, MIN_SIZE.0), clamp(h, MIN_SIZE.1)),
        None => MIN_SIZE,
    }
}

fn clamp(value: i64, least: u32) -> u32 {
    u32::try_from(value).unwrap_or(0).max(least)
}

/// What the window's X does.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CloseOutcome {
    /// Keep checking from the tray.
    HideToTray,
    /// Save the size, stop everything, quit.
    Quit,
}

/// MainWindow.closeEvent: the player's X with 关闭窗口时 最小化到托盘 hides to the tray, if there is one; without a
/// tray icon there would be no way back, so it quits. A close the app asks for (退出, an update) always quits.
pub fn close_outcome(by_player: bool, close_to_tray: bool, tray_shown: bool) -> CloseOutcome {
    if by_player && close_to_tray && tray_shown {
        CloseOutcome::HideToTray
    } else {
        CloseOutcome::Quit
    }
}

/// A key pressed in the hotkey box, as slint gives it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Pressed {
    /// Escape, or the box lost the focus: the wait ends, the key stays.
    Escape,
    /// Ctrl, Alt, Shift or Win alone: wait for the key that goes with it.
    Modifier,
    /// A-Z, 0-9 or F1-F12; None for any other key.
    Key(Option<String>),
}

/// The key of a press in the hotkey box (ui._qt_key_name).
pub fn pressed_key(text: &str) -> Pressed {
    use slint::platform::Key;
    let mut chars = text.chars();
    let (Some(c), None) = (chars.next(), chars.next()) else { return Pressed::Key(None) };
    if c == char::from(Key::Escape) {
        return Pressed::Escape;
    }
    let modifiers = [Key::Shift, Key::ShiftR, Key::Control, Key::ControlR, Key::Alt, Key::AltGr, Key::Meta, Key::MetaR];
    if modifiers.into_iter().any(|key| c == char::from(key)) {
        return Pressed::Modifier;
    }
    if c.is_ascii_alphanumeric() {
        return Pressed::Key(Some(c.to_ascii_uppercase().to_string()));
    }
    let f_keys = [Key::F1, Key::F2, Key::F3, Key::F4, Key::F5, Key::F6, Key::F7, Key::F8, Key::F9, Key::F10, Key::F11, Key::F12];
    Pressed::Key(f_keys.into_iter().position(|key| c == char::from(key)).map(|n| format!("F{}", n + 1)))
}

/// What the player does in the frame, for the app to carry out.
#[derive(Debug, Clone, PartialEq)]
pub enum ShellAction {
    /// A tab: the page is shown already and the panel closed; reload what the page needs.
    PageShown(Page),
    /// 有更新: open 发现新版本 under it.
    OpenUpdate,
    /// The player's name, typed in the header (trimmed; "" clears it).
    RenamePlayer(String),
    /// 显示: true for 基础模式 (safe_mode), false for 完整模式.
    SetSafeMode(bool),
    /// 方式: true for 自动. Asks for consent first where the Python app does (MainWindow._consent).
    SetAutoCapture(bool),
    /// The hotkey box: wait for a key (MainWindow._begin_hotkey).
    BeginHotkey,
    /// A key pressed in the waiting hotkey box (MainWindow._take_hotkey): its text and Ctrl, Alt, Shift, Win.
    TakeHotkey { text: String, ctrl: bool, alt: bool, shift: bool, win: bool },
    /// 直播模式: 开启 or 关闭.
    SetStreamMode(bool),
    /// 使用声明 at the first start (MainWindow.show_first_run_guide): agreed to, or declined (the app closes).
    AnswerDisclaimer(bool),
    /// ⓘ beside 显示: the two modes in pictures.
    ShowDisplayGuide,
    /// ⓘ beside 直播模式: how to set it up in 直播姬.
    ShowStreamGuide,
}

/// Shows the model in the window.
pub fn apply(window: &MainWindow, model: &ShellModel) {
    let tabs: Vec<ShellTab> = Page::ALL
        .iter()
        .map(|page| ShellTab {
            label: SharedString::from(page.label()),
            count: match page {
                Page::Blacklist => count(model.blacklist_count),
                Page::Guests => count(model.guests_count),
                _ => 0,
            },
        })
        .collect();
    window.set_tabs(ModelRc::new(VecModel::from(tabs)));
    window.set_page(model.page as i32);
    window.set_dark(model.dark);
    window.set_version(model.version.as_str().into());
    window.set_status_text(model.status_text.as_str().into());
    window.set_status_tone(model.tone.name().into());
    window.set_status_key(model.status_key.as_str().into());
    window.set_has_update(model.has_update);
    window.set_player_name(model.player_name.as_str().into());
    window.set_player_initial(initial(&model.player_name).into());
    window.set_safe_mode(model.safe_mode);
    window.set_auto_capture(model.auto_capture);
    window.set_hotkey(model.hotkey.as_str().into());
    window.set_hotkey_waiting(model.hotkey_waiting);
    window.set_hotkey_note(model.hotkey_note.as_str().into());
    window.set_stream_on(model.stream_on);
    let (words, ok) = model.stream.as_ref().map(|s| (s.words.as_str(), s.ok)).unwrap_or(("", false));
    window.set_stream_state(words.into());
    window.set_stream_ok(ok);
    window.set_font_family(font_family().into());
}

fn count(n: usize) -> i32 {
    i32::try_from(n).unwrap_or(i32::MAX)
}

/// The app's font: Microsoft YaHei on Windows, Noto Sans CJK SC elsewhere (CI, the headless pictures).
pub fn font_family() -> &'static str {
    if cfg!(windows) {
        "Microsoft YaHei"
    } else {
        "Noto Sans CJK SC"
    }
}

/// Sends what the player does in the frame to `act`.
pub fn connect(window: &MainWindow, act: impl Fn(ShellAction) + 'static) {
    let act = std::rc::Rc::new(act);
    let a = act.clone();
    window.on_page_changed(move |index| {
        if let Some(page) = Page::from_index(index) {
            a(ShellAction::PageShown(page));
        }
    });
    let a = act.clone();
    window.on_update_clicked(move || a(ShellAction::OpenUpdate));
    let a = act.clone();
    let weak = window.as_weak();
    window.on_player_renamed(move |name| {
        let name = name.trim().to_string();
        if let Some(window) = weak.upgrade() {
            window.set_player_initial(initial(&name).into());
            window.set_player_name(name.as_str().into());
        }
        a(ShellAction::RenamePlayer(name));
    });
    let a = act.clone();
    window.on_display_changed(move |safe| a(ShellAction::SetSafeMode(safe)));
    let a = act.clone();
    window.on_auto_changed(move |on| a(ShellAction::SetAutoCapture(on)));
    let a = act.clone();
    window.on_hotkey_clicked(move || a(ShellAction::BeginHotkey));
    let a = act.clone();
    window.on_hotkey_key(move |text, ctrl, alt, shift, win| {
        a(ShellAction::TakeHotkey { text: text.to_string(), ctrl, alt, shift, win })
    });
    let a = act.clone();
    window.on_stream_changed(move |on| a(ShellAction::SetStreamMode(on)));
    let a = act.clone();
    window.on_display_guide(move || a(ShellAction::ShowDisplayGuide));
    window.on_stream_guide(move || act(ShellAction::ShowStreamGuide));
}

#[cfg(test)]
mod tests;
