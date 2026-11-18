//! The interfaces the wiring builds against; the real parts are in `engine`, `marks`, `scenes` and `parts`, and
//! `Quiet` stands in where a part cannot run (off Windows, or when it failed to start).

use win::frame::Frame;

/// A rectangle on the virtual screen, in physical pixels: x, y, width, height.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Rect {
    pub x: i32,
    pub y: i32,
    pub w: i32,
    pub h: i32,
}

/// One seat as read (pipeline.NameSlot): index 0..12, raw text, what is shown, cut by the game, too unclear to use.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Slot {
    pub index: usize,
    pub raw: String,
    pub visible: String,
    pub truncated: bool,
    pub unclear: bool,
}

/// A 黑名单 player found at a seat (pipeline.Hit).
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Hit {
    pub index: usize,
    pub name: String,
    pub line: String,
}

/// What one check found (pipeline.CheckResult), the parts the flow reads.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct CheckResult {
    pub header_found: bool,
    pub names: Vec<Slot>,
    pub hits: Vec<Hit>,
    /// Where the marks go: the lobby's button box. None when the lobby was read but not placed.
    pub button_box: Option<Rect>,
    /// The game's picture on the screen.
    pub game_box: Option<Rect>,
    pub message: String,
    /// Every seat as the marks show it, on the virtual desktop.
    pub seats: Vec<SeatMark>,
    /// The 嘉宾 in this lobby, in seat order, each once, as the check matched them (a 黑名单 seat is no 嘉宾's).
    pub likes: Vec<String>,
}

/// What a seat is marked as.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub enum MarkKind {
    /// A 黑名单 player, with the entry's tags.
    Blacklist { tags: Vec<String> },
    Guest,
    #[default]
    None,
}

/// One seat for the marks: the name on its card (the entry's name, a 嘉宾's 昵称), where it is, how marked.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct SeatMark {
    pub name: String,
    pub rect: Rect,
    pub kind: MarkKind,
}

/// Why a check could not run. `models`: the OCR models could not load (OcrUnavailable). `plain`: the message is
/// the app's own, in plain Chinese, fit to show (OcrUnavailable, CaptureUnavailable); anything else is only logged.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct CheckError {
    pub message: String,
    pub models: bool,
    pub plain: bool,
}

/// Reads the copies of the screen (pipeline, in `engine`).
pub trait Checker: Send {
    fn check(&mut self, frame: &Frame) -> Result<CheckResult, CheckError>;
    /// Each screen in turn: the first with a lobby wins, else the last answer (pipeline.check_frames).
    fn check_frames(&mut self, frames: &[Frame]) -> Result<CheckResult, CheckError> {
        let mut last = Ok(CheckResult { message: "没有找到大厅".into(), ..CheckResult::default() });
        for frame in frames {
            last = self.check(frame);
            if matches!(&last, Ok(result) if result.header_found) {
                break;
            }
        }
        last
    }
    /// Whether 推演成功 is on the top band (watch.glance_title).
    fn glance(&mut self, band: &Frame) -> Result<bool, CheckError>;
}

/// The look of the marks over the game (ui_overlay: the panel's modes).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Look {
    /// A 黑名单 player: the red ring and the 黑名单 card.
    Hit,
    /// 黑名单 and 嘉宾 players: the red ring, both cards.
    Both,
    /// 嘉宾 players, or 我's 场景: the rose ring and the heart.
    Liked,
    /// Nobody listed: the ring and 未发现黑名单.
    Clear,
}

/// Where the marks and scenes go: over the game (完整模式) or only into 直播模式's window (基础模式 with 直播模式).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Target {
    Screen,
    Stream,
}

/// The marks over the game (the overlay crate, in `marks`).
pub trait Overlay {
    /// The scene that greets the lobby about to be shown ("" for none): its look dresses the 嘉宾 marks.
    fn dress(&mut self, _scene: &str) {}
    /// One turn of the window's timer.
    fn tick(&mut self) {}
    fn show(&mut self, game_rect: Rect, result: &CheckResult, look: Look, target: Target);
    fn hide(&mut self);
}

/// Where a 嘉宾 scene plays.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Stage {
    pub game: Rect,
    /// 准备案件还原 and its marks, left bare.
    pub button: Rect,
    pub target: Target,
}

/// The 嘉宾 scenes (the stage crate, in `scenes`).
pub trait ScenePlayer {
    fn play(&mut self, scene_key: &str, stage: Stage);
    fn stop(&mut self);
    /// One turn of the window's timer: the next frame of a scene that plays.
    fn tick(&mut self) {}
    /// The flower border plays where a screen copy sees it: a glance then cannot tell anything.
    fn covers_screen(&self) -> bool {
        false
    }
}

/// The sound (the sound crate, in `sound`). Silent until `allow_sound` is called, which only the real app does (ui_music.allow_sound).
pub trait Player {
    fn play_tune(&mut self, scene_key: &str);
    fn play_alert(&mut self);
    fn set_muted(&mut self, muted: bool);
}

/// The corner message (ui_notice): 基础模式's whole answer, and a manual check's 没有找到大厅 / 检查失败.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NoticeKind {
    Checking,
    Missing,
    /// 检查失败, with the plain reason.
    Failed(String),
    /// The answer in 基础模式: how many 黑名单 players, how many unread.
    Result { hits: usize, unclear: usize },
}

/// The corner message (app/src/notices).
pub trait Notice {
    /// The 黑名单 players and 嘉宾 of the result about to be shown (the cards name them).
    fn people(&mut self, _result: &CheckResult, _likes: &[String]) {}
    /// One turn of the window's timer.
    fn tick(&mut self) {}
    fn show(&mut self, kind: NoticeKind);
    fn hide(&mut self);
}

/// The tray menu (ui.py's tray): what a click asks for, sent over a channel.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TrayAction {
    Show,
    Check,
    Settings,
    Quit,
}

/// The tray (win::tray). Whether the icon is up; a real tray sends `TrayAction`s on the channel it was given.
pub trait Tray {
    fn visible(&self) -> bool;
}

/// 直播姬's state for 直播模式 (livehime.status).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum LiveHime {
    #[default]
    Unknown,
    NotRunning,
    NoWindow,
    Covered,
    Ok,
}

/// 直播姬's state (win::livehime).
pub trait LiveHimeWatch {
    fn state(&mut self) -> LiveHime;
}

/// The updater (data::update). One look for a new version, answered later through the runner.
pub trait UpdateCheck {
    /// Starts a look; false when one is already running.
    fn check(&mut self) -> bool;
    /// The answer of the look that ran, once.
    fn poll(&mut self) -> Option<super::updates::Found> {
        None
    }
}

// ---- the stand-ins -------------------------------------------------------------------------------

/// Nothing at all: off Windows, and where a part could not start. Each does nothing.
#[derive(Default)]
pub struct Quiet;

impl Overlay for Quiet {
    fn show(&mut self, _game_rect: Rect, _result: &CheckResult, _look: Look, _target: Target) {}
    fn hide(&mut self) {}
}

impl ScenePlayer for Quiet {
    fn play(&mut self, _scene_key: &str, _stage: Stage) {}
    fn stop(&mut self) {}
}

impl Player for Quiet {
    fn play_tune(&mut self, _scene_key: &str) {}
    fn play_alert(&mut self) {}
    fn set_muted(&mut self, _muted: bool) {}
}

impl Notice for Quiet {
    fn show(&mut self, _kind: NoticeKind) {}
    fn hide(&mut self) {}
}

impl Tray for Quiet {
    fn visible(&self) -> bool {
        false
    }
}

impl LiveHimeWatch for Quiet {
    fn state(&mut self) -> LiveHime {
        LiveHime::Unknown
    }
}

impl UpdateCheck for Quiet {
    fn check(&mut self) -> bool {
        false
    }
}
