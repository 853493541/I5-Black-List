//! The running app without its windows: the check flow, the worker thread, the hotkeys, the glance and update
//! timers, the tray, saving 设置 and quitting. The window's 50 ms timer calls `pump`.

use super::flow::{Flow, Job, Ports};
use super::life::{self, Close, Do, UpdateClock, UpdateLook};
use super::startup::AppLog;
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
    pub store: Rc<RefCell<Store>>,
    pub log: AppLog,
    pub root: PathBuf,
    pub updates: UpdateClock,
    worker: Worker,
    keys: Box<dyn Keys>,
    update_check: Box<dyn UpdateCheck>,
    before_check: Option<BeforeCheck>,
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
}

impl Runner {
    pub fn new(root: PathBuf, log: AppLog, claim: Option<Box<dyn std::any::Any>>, store: Rc<RefCell<Store>>, parts: Parts) -> Runner {
        let mode = life::mode_of(&store.borrow().settings);
        Runner {
            flow: Flow::new(mode, parts.ports),
            store,
            log,
            root,
            updates: UpdateClock::new(parts.installed),
            worker: parts.worker,
            keys: parts.keys,
            update_check: parts.update_check,
            before_check: parts.before_check,
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
        while let Ok(done) = self.worker.results.try_recv() {
            let next = self.flow.done(done, seconds);
            self.request(next);
        }
        while let Some(id) = self.keys.poll() {
            if id == CHECK_HOTKEY {
                self.check_now();
            }
            // stub: stage (the 场景 hotkey's quick play, play_quick_scene)
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

