//! The interfaces the wiring builds against, each with a stand-in so the exe builds and runs before the package
//! that owns it lands. Every stand-in is marked `// stub: <package>`; the master swaps in the real one.

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
}

/// Why a check could not run. `models`: the OCR models could not load (OcrUnavailable). `plain`: the message is
/// the app's own, in plain Chinese, fit to show (OcrUnavailable, CaptureUnavailable); anything else is only logged.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct CheckError {
    pub message: String,
    pub models: bool,
    pub plain: bool,
}

/// stub: pipeline. Reads one copy of the screen.
pub trait Checker: Send {
    fn check(&mut self, frame: &Frame) -> Result<CheckResult, CheckError>;
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

/// stub: overlay. The marks over the game.
pub trait Overlay {
    fn show(&mut self, game_rect: Rect, result: &CheckResult, look: Look, target: Target);
    fn hide(&mut self);
}

/// Where a 嘉宾 scene plays.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Stage {
    pub game: Rect,
    pub target: Target,
}

/// stub: stage. The 嘉宾 scenes.
pub trait ScenePlayer {
    fn play(&mut self, scene_key: &str, stage: Stage);
    fn stop(&mut self);
    /// The flower border plays where a screen copy sees it: a glance then cannot tell anything.
    fn covers_screen(&self) -> bool {
        false
    }
}

/// stub: sound. Silent until `allow_sound` is called, which only the real app does (ui_music.allow_sound).
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

/// stub: notice.
pub trait Notice {
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

/// stub: tray. Whether the icon is up; a real tray sends `TrayAction`s on the channel it was given.
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

/// stub: livehime.
pub trait LiveHimeWatch {
    fn state(&mut self) -> LiveHime;
}

/// stub: updater. One look for a new version, answered later through the runner.
pub trait UpdateCheck {
    /// Starts a look; false when one is already running.
    fn check(&mut self) -> bool;
}

// ---- the stand-ins -------------------------------------------------------------------------------

/// stub: pipeline. Never finds a lobby, so the exe runs end to end without models.
pub struct NoChecker;

impl Checker for NoChecker {
    fn check(&mut self, _frame: &Frame) -> Result<CheckResult, CheckError> {
        Ok(CheckResult { message: "没有找到大厅".into(), ..CheckResult::default() })
    }
    fn glance(&mut self, _band: &Frame) -> Result<bool, CheckError> {
        Ok(false)
    }
}

/// stub: overlay, notice, stage, sound, tray, livehime, updater. Each does nothing.
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
