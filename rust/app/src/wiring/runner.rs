//! The running app without its windows: the check flow, the worker thread, the hotkeys, the glance and update
//! timers, the tray, saving 设置 and quitting. The window's 50 ms timer calls `pump`.

use super::flow::{Flow, Job, Ports};
use super::life::{self, Close, Do, UpdateClock, UpdateLook};
use super::startup::AppLog;
use super::startup::VERSION;
use super::stubs::{Tray, TrayAction, UpdateCheck};
use super::watch::GLANCE_INTERVAL_MS;
use super::worker::Worker;
use data::store::settings::Settings;
use data::store::Store;
use std::cell::RefCell;
use std::path::PathBuf;
use std::rc::Rc;
use std::sync::mpsc::Receiver;
use std::time::Instant;

/// The 检查 hotkey's id; the 场景 hotkey is 2 (GlobalHotkey(..., 2)).
pub const CHECK_HOTKEY: i32 = 1;
pub const SCENE_HOTKEY: i32 = 2;

/// Where hotkey presses come from: the system's global hotkeys, or a script in tests.
pub trait Keys {
    /// The id of one press waiting, if any.
    fn poll(&mut self) -> Option<i32>;
}

/// No hotkeys (off Windows, or none set).
pub struct NoKeys;

impl Keys for NoKeys {
    fn poll(&mut self) -> Option<i32> {
        None
    }
}

/// The global hotkeys of 设置 (hotkey.py GlobalHotkey), registered on this thread.
#[cfg(windows)]
pub struct SystemKeys {
    _held: Vec<win::global_hotkey::Registration>,
}

#[cfg(windows)]
impl SystemKeys {
    /// Registers the 检查 and 场景 hotkeys; a key taken by another program is left out and said in the log.
    pub fn register(settings: &Settings, log: &AppLog) -> SystemKeys {
        let mut held = Vec::new();
        for (id, text) in [(CHECK_HOTKEY, &settings.hotkey), (SCENE_HOTKEY, &settings.effect_hotkey)] {
            let Some(spec) = win::hotkey::parse_hotkey(text) else { continue };
            match win::global_hotkey::Registration::register(id, &spec) {
                Ok(registration) => held.push(registration),
                Err(error) => log.warn(&format!("Hotkey {} not registered: {error:?}", spec.display)),
            }
        }
        SystemKeys { _held: held }
    }
}

#[cfg(windows)]
impl Keys for SystemKeys {
    fn poll(&mut self) -> Option<i32> {
        win::global_hotkey::poll()
    }
}

pub struct Runner {
    pub flow: Flow,
    /// A newer release the last look found, for 发现新版本 to offer.
    pub offer: Option<data::update::Release>,
    /// The update being downloaded, and what it said since the window last took it (for the update dialog).
    installing: Option<Receiver<super::updates::Install>>,
    pub install_events: Vec<super::updates::Install>,
    pub store: Rc<RefCell<Store>>,
    pub log: AppLog,
    pub root: PathBuf,
    pub updates: UpdateClock,
    worker: Worker,
    keys: Box<dyn Keys>,
    update_check: Box<dyn UpdateCheck>,
    before_check: Option<BeforeCheck>,
    placed: Option<Receiver<super::stubs::Rect>>,
    tester: Option<(MakeChecker, std::path::PathBuf)>,
    testing: Option<Receiver<data::diag::FlowTest>>,
    /// The last 环境测试's report, for 设置 and 导出日志.
    pub flow_report: Option<String>,
    tray: Box<dyn Tray>,
    tray_actions: Receiver<TrayAction>,
    started_at: Instant,
    next_glance: u64,
    logged: usize,
    /// The single-instance mutex, held for the life of the app.
    _claim: Option<Box<dyn std::any::Any>>,
}

/// Copies what the worker reads from the store, before a check.
pub type BeforeCheck = Box<dyn Fn(&Store)>;

/// The parts the runner is given (the real ones in main.rs, fakes in tests).
pub struct Parts {
    pub ports: Ports,
    pub worker: Worker,
    pub keys: Box<dyn Keys>,
    pub update_check: Box<dyn UpdateCheck>,
    pub tray: Box<dyn Tray>,
    pub tray_actions: Receiver<TrayAction>,
    pub installed: bool,
    /// Copies what the worker reads from the store (the lists, the scenes' sounds) before each check.
    pub before_check: Option<BeforeCheck>,
    /// The button's box from a check that found the lobby (the checker's `placed`).
    pub placed: Option<Receiver<super::stubs::Rect>>,
    /// Makes a checker for 环境测试, and where the sample lobby is.
    pub tester: Option<(MakeChecker, std::path::PathBuf)>,
}

/// A fresh pipeline checker (环境测试 runs on a thread of its own).
pub type MakeChecker = Box<dyn Fn() -> super::engine::PipelineChecker>;

impl Runner {
    pub fn new(root: PathBuf, log: AppLog, claim: Option<Box<dyn std::any::Any>>, store: Rc<RefCell<Store>>, parts: Parts) -> Runner {
        let mode = life::mode_of(&store.borrow().settings);
        Runner {
            flow: Flow::new(mode, parts.ports),
            offer: None,
            installing: None,
            install_events: Vec::new(),
            store,
            log,
            root,
            updates: UpdateClock::new(parts.installed),
            worker: parts.worker,
            keys: parts.keys,
            update_check: parts.update_check,
            before_check: parts.before_check,
            placed: parts.placed,
            tester: parts.tester,
            testing: None,
            flow_report: None,
            tray: parts.tray,
            tray_actions: parts.tray_actions,
            started_at: Instant::now(),
            next_glance: GLANCE_INTERVAL_MS,
            logged: 0,
            _claim: claim,
        }
    }

    fn now_ms(&self) -> u64 {
        self.started_at.elapsed().as_millis() as u64
    }

    fn request(&self, job: Option<Job>) {
        if let (Some(Job::Check), Some(copy)) = (job, &self.before_check) {
            copy(&self.store.borrow());
        }
        if let Some(job) = job {
            self.worker.request(job);
        }
    }

    /// 立即检查: the hotkey, the tray's item.
    pub fn check_now(&mut self) {
        let job = self.flow.hotkey(self.now_ms() as f64 / 1000.0);
        self.request(job);
    }

    /// One turn of the loop. Returns what the window has to do (show itself, 设置, quit).
    pub fn pump(&mut self) -> Vec<Do> {
        let now = self.now_ms();
        let seconds = now as f64 / 1000.0;
        while let Some(button) = self.placed.as_ref().and_then(|placed| placed.try_recv().ok()) {
            self.flow.lobby_placed(button);
        }
        while let Ok(done) = self.worker.results.try_recv() {
            let next = self.flow.done(done, seconds);
            self.request(next);
        }
        while let Some(id) = self.keys.poll() {
            if id == CHECK_HOTKEY {
                self.check_now();
            }
            if id == SCENE_HOTKEY {
                let scene = self.store.borrow().settings.quick_scene.clone();
                self.flow.quick_play(&scene, screen_rect(), seconds);
            }
        }
        if now >= self.next_glance {
            self.next_glance = now + GLANCE_INTERVAL_MS;
            let job = self.flow.tick(seconds);
            self.request(job);
        }
        if let Some(look) = self.updates.tick(now) {
            self.look_for_update(look);
        }
        self.flow.ports.scenes.tick();
        self.flow.ports.overlay.tick();
        self.flow.ports.notice.tick();
        if let Some(events) = &self.installing {
            let said: Vec<_> = events.try_iter().collect();
            if said.iter().any(|event| !matches!(event, super::updates::Install::Progress(..))) {
                self.installing = None;
            }
            for event in &said {
                if !matches!(event, super::updates::Install::Progress(..)) {
                    self.log.info(&format!("Update: {event:?}"));
                }
            }
            self.install_events.extend(said);
        }
        if let Some(test) = self.testing.as_ref().and_then(|testing| testing.try_recv().ok()) {
            self.testing = None;
            let report = test.text();
            self.log.info(&format!("环境测试:\n{report}"));
            self.flow_report = Some(report);
        }
        match self.update_check.poll() {
            Some(Ok(Some(release))) => {
                self.log.info(&format!("Update: {} is out.", release.version));
                self.offer = Some(release);
            }
            Some(Ok(None)) => self.log.info("Update: this is the newest."),
            Some(Err(error)) => self.log.warn(&format!("Update: {}", error.message())),
            None => {}
        }
        let mut asks = Vec::new();
        while let Ok(action) = self.tray_actions.try_recv() {
            match life::on_tray(action) {
                Do::CheckNow => self.check_now(),
                other => asks.push(other),
            }
        }
        self.flush_log();
        asks
    }

    fn look_for_update(&mut self, look: UpdateLook) {
        if self.update_check.check() {
            self.log.info(&format!("Update: looking ({look:?})."));
        }
    }

    /// 检查更新 in 设置: a look now.
    pub fn check_updates_now(&mut self) {
        self.look_for_update(UpdateLook::Install);
    }

    /// 更新: download the release offered and stage it; false when there is none, or no release folder to stage in.
    pub fn start_install(&mut self) -> bool {
        let (Some(release), Some(install)) = (self.offer.clone(), super::startup::install_root()) else { return false };
        if self.installing.is_some() {
            return false;
        }
        let agent = VERSION.to_string();
        let connect: super::updates::Connect = Box::new(move || Box::new(data::update::net::Net::new(&agent)));
        self.log.info(&format!("Update: downloading {}.", release.version));
        self.installing = Some(super::updates::install(release, self.root.clone(), install, connect));
        true
    }

    /// 环境测试 › 开始: the test on a thread of its own; false while one runs or there is no checker.
    pub fn start_env_test(&mut self) -> bool {
        let Some((make, assets)) = &self.tester else { return false };
        if self.testing.is_some() {
            return false;
        }
        let Some(lobby) = super::envtest::sample(assets) else {
            self.log.warn("环境测试: no sample lobby in the assets.");
            return false;
        };
        let mut checker = make();
        let (sender, answer) = std::sync::mpsc::channel();
        let started = std::thread::Builder::new().name("EnvironmentTest".into()).spawn(move || {
            let _ = sender.send(super::envtest::run(&mut checker, &mut super::worker::RealScreen, &lobby, 3));
        });
        if started.is_err() {
            return false;
        }
        self.testing = Some(answer);
        self.log.info("环境测试: started.");
        true
    }

    /// 全局声音: 静音 stops what plays now.
    pub fn set_muted(&mut self, muted: bool) {
        self.flow.ports.player.set_muted(muted);
    }

    /// The hotkeys changed in 设置: the new ones replace the old.
    pub fn set_keys(&mut self, keys: Box<dyn Keys>) {
        self.keys = keys;
    }

    /// The window is in front again.
    pub fn window_returned(&mut self) {
        if let Some(look) = self.updates.on_return(self.now_ms()) {
            self.look_for_update(look);
        }
    }

    fn flush_log(&mut self) {
        for line in &self.flow.log[self.logged..] {
            self.log.info(line);
        }
        self.logged = self.flow.log.len();
    }

    /// A change in 设置, saved at once (store.save_settings), and the flow told.
    pub fn change_settings(&mut self, change: impl FnOnce(&mut Settings) -> bool) -> bool {
        let mut store = self.store.borrow_mut();
        if !change(&mut store.settings) {
            return false;
        }
        if let Err(error) = store.save_settings() {
            self.log.warn(&format!("Settings not saved: {error}"));
        }
        let mode = life::mode_of(&store.settings);
        drop(store);
        self.flow.set_mode(mode);
        true
    }

    /// The window's X, or 退出.
    pub fn close(&mut self, by_player: bool) -> Close {
        let close = life::on_close(&self.store.borrow().settings, self.tray.visible(), by_player);
        match close {
            Close::ToTray => self.log.info("Window: closed to the tray."),
            Close::Quit => self.log.info("Asked to quit."),
        }
        close
    }

    /// Everything stops: the marks, the scene, the worker (after its job), and the log says the app closed.
    pub fn quit(&mut self, code: i32) {
        self.flow.hide_marks();
        self.flow.ports.scenes.stop();
        self.worker.stop();
        self.flush_log();
        self.log.info(&format!("Exit {code}"));
        data::logs::mark_closed(&self.root);
    }
}


/// The whole desktop, where the 场景 hotkey plays with no lobby found yet.
#[cfg(windows)]
fn screen_rect() -> super::stubs::Rect {
    let screen = win::capture::virtual_screen();
    super::stubs::Rect { x: screen.left, y: screen.top, w: screen.width, h: screen.height }
}

#[cfg(not(windows))]
fn screen_rect() -> super::stubs::Rect {
    super::stubs::Rect { x: 0, y: 0, w: 1920, h: 1080 }
}
