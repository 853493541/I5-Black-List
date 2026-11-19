//! The check flow of ui.py MainWindow, without the drawing: hotkey or 自动检查 glance → screen copy → check → the
//! marks, the corner message, the 嘉宾 scene and its music. A state machine with time passed in, so it is tested
//! with fakes; the runner does the jobs it asks for on a worker thread and hands back what they found.

use super::stubs::{CheckError, CheckResult, Look, Rect, Notice, NoticeKind, Overlay, Player, ScenePlayer, Stage, Target};
use super::watch::LobbyWatch;

/// Work for the worker thread: one at a time (CheckWorker).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Job {
    /// Copy every screen and read the lobby.
    Check,
    /// Copy the top band and look for 推演成功.
    Glance,
}

/// What a job brought back.
#[derive(Debug, Clone, PartialEq)]
pub enum Done {
    Checked(Result<CheckResult, CheckError>),
    Glanced(Result<bool, CheckError>),
}

/// The 设置 the flow reads: 方式, 显示, 直播模式, and whether 使用声明 was agreed to.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Mode {
    pub auto: bool,
    pub safe: bool,
    pub stream: bool,
    pub disclaimer: bool,
}

impl Mode {
    /// Where the marks go (_overlay_target): over the game in 完整模式, only into 直播模式's window in 基础模式
    /// with 直播模式, nowhere in plain 基础模式.
    pub fn target(&self) -> Option<Target> {
        match (self.safe, self.stream) {
            (false, _) => Some(Target::Screen),
            (true, true) => Some(Target::Stream),
            (true, false) => None,
        }
    }
}

/// Who greets a lobby (guests.lobby_scene): "combo", "guest", "me" or nobody, and the scene picked for it.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Greeting {
    pub who: String,
    pub scene: String,
}

/// The lists, as the flow needs them.
pub trait Records {
    /// Save the check in 记录 (Store.add_scan).
    fn add_scan(&mut self, result: &CheckResult, elapsed: Option<f64>);
    /// The 嘉宾 in this lobby, in seat order, each once; a 黑名单 seat is no 嘉宾's (_likes_in).
    fn likes_in(&self, result: &CheckResult) -> Vec<String>;
    /// The scene for this lobby (_choice_for).
    fn greeting(&self, likes: &[String], blacklisted: bool) -> Greeting;
    /// The lobby is gone: the next one draws its own scene from a choice of several (LoveBorder.draw_again).
    fn new_lobby(&mut self) {}
}

/// What the main window's status line says.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub enum Status {
    #[default]
    Idle,
    Checking,
    /// 检查失败, with the plain reason.
    Failed(String),
    NoLobby,
    Shown(Look),
}

/// The parts the flow drives.
pub struct Ports {
    pub overlay: Box<dyn Overlay>,
    pub notice: Box<dyn Notice>,
    pub scenes: Box<dyn ScenePlayer>,
    pub player: Box<dyn Player>,
    pub records: Box<dyn Records>,
}

pub struct Flow {
    pub mode: Mode,
    pub ports: Ports,
    pub watch: LobbyWatch,
    pub status: Status,
    /// What happened, in the log's words.
    pub log: Vec<String>,
    pub check_number: u32,
    busy: bool,
    manual: bool,
    live: bool,
    rescan: bool,
    panel_shown: bool,
    glance_pause_until: f64,
    check_started: Option<f64>,
    played: Option<Greeting>,
    /// The last lobby's game and button, as a check found them (the 场景 hotkey plays there).
    pub(super) last_game: Option<(Rect, Rect)>,
    /// When the 场景 hotkey's play ends.
    pub(super) quick_until: Option<f64>,
}

impl Flow {
    pub fn new(mode: Mode, ports: Ports) -> Self {
        Flow {
            mode,
            ports,
            watch: LobbyWatch::default(),
            status: Status::Idle,
            log: Vec::new(),
            check_number: 0,
            busy: false,
            manual: false,
            live: false,
            rescan: false,
            panel_shown: false,
            glance_pause_until: 0.0,
            check_started: None,
            played: None,
            last_game: None,
            quick_until: None,
        }
    }

    pub fn busy(&self) -> bool {
        self.busy
    }

    /// Whether a lobby's marks are up.
    pub fn marks_shown(&self) -> bool {
        self.panel_shown
    }

    /// Whether the 400 ms glance timer runs: in 自动检查, and while marks are up (to take them down).
    pub fn watching(&self) -> bool {
        self.mode.auto || self.panel_shown
    }

    fn say(&mut self, line: impl Into<String>) {
        self.log.push(line.into());
    }

    /// The 检查 hotkey, or 立即检查 in the tray (check_now).
    pub fn hotkey(&mut self, now: f64) -> Option<Job> {
        self.say("Hotkey: checking.");
        if !self.mode.disclaimer {
            // Not "busy": nothing runs, the data folder has not agreed to 使用声明 yet.
            self.say("Hotkey: 使用声明 not agreed to yet, no check.");
            return None;
        }
        self.rescan = false;
        if self.start(now) {
            self.manual = true;
            return Some(Job::Check);
        }
        self.say("Hotkey: busy, the press was ignored.");
        None
    }

    /// The glance timer (_auto_tick).
    pub fn tick(&mut self, now: f64) -> Option<Job> {
        if self.quick_until.is_some_and(|until| now >= until) {
            self.end_quick();
        }
        if self.panel_shown {
            self.ports.overlay.follow();
        }
        if !self.watching() || now < self.glance_pause_until || self.ports.scenes.covers_screen() || self.busy {
            return None;
        }
        self.busy = true;
        Some(Job::Glance)
    }

    /// A check may start (_start): not before 使用声明, nor while a check or a glance runs.
    fn start(&mut self, now: f64) -> bool {
        if !self.mode.disclaimer || self.busy {
            return false;
        }
        // A real lobby comes first: the 场景 hotkey's play gives way.
        self.end_quick();
        self.ports.scenes.stop();
        self.live = true;
        self.busy = true;
        self.check_started = Some(now);
        if !self.rescan {
            if let (true, Some((_, button))) = (self.panel_shown, self.last_game) {
                // The marks up turn into 检查中 at once.
                self.ports.overlay.checking(button);
            }
            self.status = Status::Checking;
            if self.mode.safe {
                self.ports.notice.show(NoticeKind::Checking);
            }
        }
        true
    }

    /// The worker is done (_on_worker). Returns the next job when a second look or an automatic check starts.
    pub fn done(&mut self, done: Done, now: f64) -> Option<Job> {
        self.busy = false;
        match done {
            Done::Glanced(seen) => self.glanced(seen, now),
            Done::Checked(found) => self.checked(found, now),
        }
    }

    fn glanced(&mut self, seen: Result<bool, CheckError>, now: f64) -> Option<Job> {
        let present = match seen {
            Err(error) => {
                // Do not reload a missing model or retry a dead screen copy every 0.4 seconds.
                self.glance_pause_until = now + if error.models { 15.0 } else { 5.0 };
                self.status = Status::Failed(error.message);
                return None;
            }
            Ok(present) => present,
        };
        if matches!(self.status, Status::Failed(_)) {
            self.status = Status::Idle;
        }
        if !present {
            if self.ports.scenes.covers_screen() {
                return None;
            }
            if self.panel_shown {
                self.hide_marks();
            }
        }
        if !self.mode.auto || !self.watch.wants_check(present, now) {
            return None;
        }
        self.say("Auto check: 推演成功 is on screen; checking.");
        self.watch.arm(now);
        self.rescan = false;
        if self.start(now) {
            return Some(Job::Check);
        }
        self.watch.retry_after(now);
        None
    }

    /// A failed or empty check gets one second look at once (_rescan_now).
    fn second_look(&mut self, now: f64) -> Option<Job> {
        if self.rescan || !self.live {
            return None;
        }
        self.rescan = true;
        if self.mode.auto {
            self.watch.arm(now);
        }
        if self.start(now) {
            return Some(Job::Check);
        }
        self.rescan = false;
        None
    }

    fn checked(&mut self, found: Result<CheckResult, CheckError>, now: f64) -> Option<Job> {
        let rescan = self.rescan;
        self.rescan = false;
        if !rescan {
            self.check_number += 1;
        }
        let how = if rescan { "second look" } else if self.manual { "hotkey" } else { "auto" };
        let elapsed = self.check_started.take().map(|started| now - started);
        let result = match found {
            Err(error) => {
                if !rescan {
                    if let Some(job) = self.second_look(now) {
                        return Some(job);
                    }
                }
                let manual = std::mem::take(&mut self.manual);
                self.say(format!("Check {} ({how}) failed: {}", self.check_number, error.message));
                self.status = Status::Failed(error.message.clone());
                if self.mode.auto {
                    self.watch.retry_after(now);
                }
                self.hide_marks();
                if self.mode.safe && manual {
                    self.ports.notice.show(NoticeKind::Failed(plain_error(&error, "等会儿再试")));
                } else {
                    self.ports.notice.hide();
                }
                return None;
            }
            Ok(result) => result,
        };
        if !result.header_found {
            if !rescan {
                if let Some(job) = self.second_look(now) {
                    return Some(job);
                }
            }
            let manual = std::mem::take(&mut self.manual);
            self.say(format!("Check {} ({how}): no lobby on screen: {}", self.check_number, result.message));
            self.status = Status::NoLobby;
            if self.mode.auto {
                self.watch.retry_after(now);
            }
            self.hide_marks();
            if manual {
                self.ports.notice.show(NoticeKind::Missing);
            } else {
                self.ports.notice.hide();
            }
            return None;
        }
        self.manual = false;
        self.say(format!("Check {} ({how}): {} seats read, {} 黑名单.", self.check_number, result.names.len(), result.hits.len()));
        if self.mode.auto {
            self.watch.hold();
        }
        if !result.names.is_empty() {
            self.ports.records.add_scan(&result, elapsed);
        }
        self.show(&result);
        None
    }

    /// The marks for a lobby (_show_result).
    fn show(&mut self, result: &CheckResult) {
        let likes = self.ports.records.likes_in(result);
        let greeting = self.ports.records.greeting(&likes, !result.hits.is_empty());
        if self.played.as_ref().is_some_and(|played| *played != greeting) {
            // Checked again and another greets it now: its own scene, not the one that played.
            self.ports.scenes.stop();
            self.played = None;
        }
        let greets = !greeting.who.is_empty();
        let fresh = greets && self.played.is_none();
        if fresh {
            self.ports.player.play_tune(&greeting.scene);
        }
        let unclear = result.names.iter().filter(|slot| slot.unclear).count();
        if self.mode.safe {
            self.ports.notice.people(result, &likes);
            self.ports.notice.show(NoticeKind::Result { hits: result.hits.len(), unclear });
            self.say(format!("Check {} shown: the corner message (基础模式).", self.check_number));
        }
        let look = match (result.hits.is_empty(), likes.is_empty()) {
            (false, false) => Look::Both,
            (false, true) => Look::Hit,
            (true, _) if !likes.is_empty() || greeting.who == "me" => Look::Liked,
            (true, _) => Look::Clear,
        };
        self.status = Status::Shown(look);
        let Some(target) = self.mode.target() else { return };
        let Some(game) = result.button_box else {
            self.hide_marks();
            return;
        };
        self.last_game = Some((result.game_box.unwrap_or(game), game));
        self.ports.overlay.dress(&greeting.scene);
        self.ports.overlay.show(game, result, look, target);
        self.panel_shown = true;
        if !result.hits.is_empty() {
            self.ports.player.play_alert();
        }
        if fresh {
            self.ports.scenes.play(&greeting.scene, Stage { game: result.game_box.unwrap_or(game), button: game, target });
            self.played = Some(greeting);
        }
        self.say(format!("Check {} shown: {look:?}.", self.check_number));
    }

    /// The check found the lobby and its button, before reading the names (_on_lobby_placed): 检查中 on it.
    pub fn lobby_placed(&mut self, button: Rect) {
        if !self.live || !self.busy || self.mode.target().is_none() {
            return;
        }
        self.ports.overlay.checking(button);
    }

    /// Everything over the game comes down (_hide_panel_after_title).
    pub fn hide_marks(&mut self) {
        self.ports.overlay.hide();
        self.ports.scenes.stop();
        self.ports.records.new_lobby();
        self.played = None;
        self.panel_shown = false;
    }

    /// 设置 changed. 基础模式 takes everything off the game at once and turns 自动检查 off until 完整模式 (_set_safe_mode).
    pub fn set_mode(&mut self, mode: Mode) {
        let safe_now = mode.safe && !self.mode.safe;
        if self.mode.target() != mode.target() || safe_now {
            self.hide_marks();
        }
        if mode.auto && !self.mode.auto {
            self.watch = LobbyWatch::default();
        }
        self.mode = mode;
    }
}

/// What a player may read about a failure (_plain_error): the app's own plain message, else the fallback.
pub fn plain_error(error: &CheckError, fallback: &str) -> String {
    let message = error.message.trim();
    if error.plain && !message.is_empty() {
        message.to_string()
    } else {
        fallback.to_string()
    }
}
