//! 直播模式, the stream side of the UI (blacklist_detect/ui_stream.py and the parts of ui.py that drive it).
//!
//! What the player sees while 直播模式 is on:
//! - [`StreamPanel`](ui/stream/panel.slint): the 检查 panel's 直播模式 row, right of its name: 关闭 | 开启,
//!   the ⓘ that opens the guide, and 直播姬's state in words (green when it shows 直播画面, red and
//!   underlined until it does). ui-shell places it in the row; [`row_status`] fills its words.
//! - `StreamGuideDialog` (ui/stream/guide.slint): 直播模式说明, what viewers see and how to add the window in
//!   直播姬. It opens from the ⓘ, and by itself the first time 直播模式 is turned on ([`on_choice`]).
//! - `StreamMirrorWindow` (ui/stream/mirror.slint): 直播画面, the window a streaming app captures. The marks
//!   are copied into it where they are on the game, never the card with the 黑名单 names. Its size and
//!   where it sits are [`mirror`]; the marks themselves are the overlay package's pictures.
//! - Masked 黑名单 names: always while 直播模式 is on ([`names_hidden`], [`masked_name`]).
//!
//! Actions the app performs go out as [`StreamAction`]; app-wiring runs them.

// The app is a binary and app-wiring does not call this yet: nothing here counts as dead meanwhile.
#![allow(dead_code)]

pub mod mirror;
pub mod render;

/// 直播姬's state, from the livehime package (its detection and its scene file).
// stub: livehime
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum LivehimeState {
    /// 直播姬 is not running (Python `livehime.CLOSED`).
    NotFound,
    /// 直播姬 runs, and its current scene does not show 直播画面 yet, for this reason.
    Found(SceneIssue),
    /// The current scene shows 直播画面, nothing of the game's over it (Python `livehime.OK`).
    Capturing,
    /// Its log or scene could not be read (Python: no log file): the row says nothing, the log has it.
    Error(String),
}

/// Why 直播姬's current scene does not show 直播画面.
// stub: livehime
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SceneIssue {
    /// The scene is not known yet (Python `""`): nothing is said.
    Unknown,
    /// No capture of 直播画面 in the scene (`livehime.MISSING`).
    Missing,
    /// It is there, hidden: the eye in 直播姬's list (`livehime.HIDDEN`).
    Hidden,
    /// The game's capture is over it, so the marks are under the game (`livehime.BEHIND`).
    Behind,
}

/// How the state's words are drawn: green, or red and underlined.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum Tone {
    Ok,
    #[default]
    Warn,
}

/// The window's title, as 直播姬 lists it (`ui_stream.TITLE`).
pub const TITLE: &str = "模仿者小工具·直播画面";
/// How often the marks are copied, in ms (`ui_stream.FRAME_MS`).
pub const FRAME_MS: u64 = 45;
/// After the window shows or moves, before Windows is asked whether it captures it (`ASK_MS`).
pub const ASK_MS: u64 = 300;
/// How often 直播姬's scene file is read again (`FOLLOW_MS`).
pub const FOLLOW_MS: u64 = 3_000;
/// How often 直播姬's state is checked while 直播模式 is on (ui.py `_stream_watch`).
pub const WATCH_MS: u64 = 2_000;

impl LivehimeState {
    /// The Python key of this state (`livehime.OK` …), "" where Python has none.
    pub fn key(&self) -> &'static str {
        match self {
            Self::NotFound => "closed",
            Self::Capturing => "ok",
            Self::Found(SceneIssue::Missing) => "missing",
            Self::Found(SceneIssue::Hidden) => "hidden",
            Self::Found(SceneIssue::Behind) => "behind",
            Self::Found(SceneIssue::Unknown) | Self::Error(_) => "",
        }
    }

    /// Everything said of this state (`livehime.WORDS`), "" when nothing is.
    pub fn words(&self) -> &'static str {
        match self.key() {
            "ok" => "✓ 已连上直播姬",
            "missing" => "直播姬场景里还没有「直播画面」",
            "hidden" => "「直播画面」被隐藏了，显示后切换一次直播姬场景",
            "behind" => "「直播画面」被游戏挡住了，置顶后切换一次直播姬场景",
            "closed" => "直播姬没有打开",
            _ => "",
        }
    }

    pub fn tone(&self) -> Tone {
        if *self == Self::Capturing {
            Tone::Ok
        } else {
            Tone::Warn
        }
    }
}

/// What the row says, without how to set it right after the comma (ui.py `_said_first`).
pub fn said_first(words: &str) -> &str {
    words.split('，').next().unwrap_or_default()
}

/// The 直播模式 row's words and tone; None hides them (their room is kept). None while 直播模式 is off.
pub fn row_status(stream_mode: bool, state: &LivehimeState) -> Option<(String, Tone)> {
    let words = said_first(state.words());
    (stream_mode && !words.is_empty()).then(|| (words.to_string(), state.tone()))
}

/// 黑名单's names masked: by the eye, or always while 直播模式 is on (ui.py `_names_hidden`).
pub fn names_hidden(eye_closed: bool, stream_mode: bool) -> bool {
    eye_closed || stream_mode
}

/// First character, then a star for every character after it, and always at least one star.
pub fn masked_name(name: &str) -> String {
    let mut chars = name.chars();
    match chars.next() {
        None => String::new(),
        Some(first) => format!("{first}{}", "*".repeat(chars.count().max(1))),
    }
}

/// A 黑名单 name as shown on a page that may be on stream: masked whenever the pages mask it.
pub fn listed(name: &str, eye_closed: bool, stream_mode: bool) -> String {
    if names_hidden(eye_closed, stream_mode) {
        masked_name(name)
    } else {
        name.to_string()
    }
}

/// What the app must do for the stream UI; app-wiring performs these.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum StreamAction {
    /// Save `stream_mode` ("on" / "") and open or close 直播画面; start or stop watching 直播姬 every [`WATCH_MS`].
    SetStreamMode(bool),
    /// Save `stream_guided = true` (the guide has been shown once).
    MarkGuided,
    /// Open `StreamGuideDialog`.
    ShowGuide,
    /// In 基础模式: end a 场景 hotkey play, its marks now go where a check's go.
    EndQuickPlay,
    /// Put the marks where [`overlay_target`] says.
    SyncOverlayTarget,
    /// Mask or unmask 黑名单's names on the pages (黑名单, 记录) and lock the eye while 直播模式 is on.
    SyncNameHiding,
    /// Check 直播姬's state now and show it with [`row_status`].
    CheckSetup,
}

/// Where the marks go (ui.py `_overlay_target`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum OverlayTarget {
    /// Over the game (完整模式).
    Screen,
    /// Made but never put on the screen, only into 直播画面 (基础模式 with 直播模式).
    Stream,
    /// Nowhere (基础模式).
    Nowhere,
}

pub fn overlay_target(safe_mode: bool, stream_mode: bool) -> OverlayTarget {
    match (safe_mode, stream_mode) {
        (false, _) => OverlayTarget::Screen,
        (true, true) => OverlayTarget::Stream,
        (true, false) => OverlayTarget::Nowhere,
    }
}

/// 直播模式 turned on or off (ui.py `_set_stream_mode`), in the order the app does it.
pub fn set_stream_mode(on: bool, safe_mode: bool) -> Vec<StreamAction> {
    let mut actions = vec![StreamAction::SetStreamMode(on)];
    if safe_mode {
        actions.push(StreamAction::EndQuickPlay);
    }
    actions.extend([StreamAction::SyncOverlayTarget, StreamAction::SyncNameHiding, StreamAction::CheckSetup]);
    actions
}

/// 关闭 | 开启 clicked (ui.py `_on_stream_choice`): the first time it is turned on, the guide comes with it.
pub fn on_choice(on: bool, guided: bool, safe_mode: bool) -> Vec<StreamAction> {
    let mut actions = set_stream_mode(on, safe_mode);
    if on && !guided {
        actions.extend([StreamAction::MarkGuided, StreamAction::ShowGuide]);
    }
    actions
}

#[cfg(test)]
mod tests;
