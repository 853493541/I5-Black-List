//! Start-up, in run_app's order: data folder, logs, one copy, 设置, 开机启动, the OCR models. Each step says in the
//! log that it passed ("Start-up: <step> ok"), which the CI start-up test reads back.

use data::logs::{format_line, log_dir, mark_closed, mark_running, RotatingLog};
use data::store::{files, Clock, Store};
use std::path::{Path, PathBuf};

pub const VERSION: &str = env!("CARGO_PKG_VERSION");
/// Started with Windows (autostart.BACKGROUND): stay in the tray.
pub const BACKGROUND: &str = "--background";
/// Run the start-up steps, then quit before any window opens (the CI start-up test).
pub const QUIT_AFTER_START: &str = "--quit-after-start";

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Options {
    pub background: bool,
    pub quit_after_start: bool,
    /// `--data <folder>`: the data folder, instead of %APPDATA%'s.
    pub root: Option<PathBuf>,
}

impl Options {
    pub fn parse(args: &[String]) -> Options {
        let mut options = Options::default();
        let mut words = args.iter();
        while let Some(word) = words.next() {
            match word.as_str() {
                BACKGROUND => options.background = true,
                QUIT_AFTER_START => options.quit_after_start = true,
                "--data" => options.root = words.next().map(PathBuf::from),
                _ => {}
            }
        }
        options
    }
}

/// The app's log, logs/app.log (five files of 1 MB at most), in logs.py's line format.
pub struct AppLog {
    file: Option<RotatingLog>,
}

impl AppLog {
    pub fn open(root: &Path) -> AppLog {
        let folder = log_dir(root);
        let file = std::fs::create_dir_all(&folder).ok().map(|_| RotatingLog::new(folder.join("app.log")));
        AppLog { file }
    }

    pub fn none() -> AppLog {
        AppLog { file: None }
    }

    fn write(&self, level: &str, message: &str) {
        if let Some(file) = &self.file {
            let line = format_line(chrono::Local::now().naive_local(), level, "MainThread", message);
            let _ = file.write(&line);
        }
    }

    pub fn info(&self, message: &str) {
        self.write("INFO", message);
    }

    pub fn warn(&self, message: &str) {
        self.write("WARNING", message);
    }
}

/// What start-up leaves for the running app.
pub struct Started {
    pub root: PathBuf,
    pub log: AppLog,
    pub store: Store,
    /// The detection and recognition model folders, when found.
    pub models: Option<(PathBuf, PathBuf)>,
    /// The single-instance mutex: held while this lives.
    pub claim: Option<Box<dyn std::any::Any>>,
}

/// How start-up ended.
pub enum Outcome {
    Run(Box<Started>),
    /// Another copy is open and was asked to show itself (or, started with Windows, left alone).
    AlreadyRunning,
}

/// The folder the exe is in: the install folder.
pub fn exe_dir() -> Option<PathBuf> {
    std::env::current_exe().ok()?.parent().map(Path::to_path_buf)
}

pub fn start(options: &Options) -> Result<Outcome, String> {
    let root = options.root.clone().unwrap_or_else(files::app_dir);
    std::fs::create_dir_all(&root).map_err(|error| format!("data folder {}: {error}", root.display()))?;
    let log = AppLog::open(&root);
    log.info(&format!("==== Start {VERSION} (Rust, {}) ====", std::env::consts::OS));
    log.info("Start-up: data folder ok");
    if mark_running(&root) {
        log.warn("The last run ended without closing: it was ended from outside (Task Manager, a tool, or a power loss).");
    }
    log.info("Start-up: logs ok");
    let claim = match one_copy(options, &log) {
        Some(claim) => claim,
        None => {
            log.info(if options.background { "Already running." } else { "Already running. Brought the open window forward." });
            return Ok(Outcome::AlreadyRunning);
        }
    };
    let store = Store::open(Some(root.clone()), Clock::default());
    if !store.load_warning.is_empty() {
        log.warn(&format!("Settings: {}", store.load_warning));
    }
    log.info(&format!("Settings: {}", settings_line(&store)));
    log.info("Start-up: settings ok");
    autostart_refresh();
    log.info("Start-up: autostart ok");
    let models = model_dirs(&model_roots());
    match &models {
        Some((det, rec)) => log.info(&format!("Start-up: models ok ({}, {})", det.display(), rec.display())),
        // Not fatal: the window opens and says the models are missing, as the Python app does.
        None => log.warn("Start-up: models missing (checked BLACKLIST_DETECT_MODEL_DIR, models beside the exe and here)"),
    }
    Ok(Outcome::Run(Box::new(Started { root, log, store, models, claim })))
}

/// The end of a run: the marker that says the app closed by itself goes (logs.mark_closed).
pub fn finish(started: &Started, code: i32) {
    started.log.info(&format!("Exit {code}"));
    mark_closed(&started.root);
}

/// 设置 for the log (settings_line).
pub fn settings_line(store: &Store) -> String {
    let s = &store.settings;
    format!(
        "hotkey {}, 方式 {}, 显示 {}, 直播模式 {}, sound {}, close to tray {}",
        s.hotkey,
        if s.auto_capture { "自动" } else { "手动" },
        if s.safe_mode { "基础模式" } else { "完整模式" },
        if s.stream_mode.is_empty() { "off" } else { "on" },
        if s.sound_muted { "muted" } else { "on" },
        s.close_to_tray,
    )
}

/// One copy (single.claim, single.settle): Some(claim) to go on, None when another copy answered.
#[cfg(windows)]
fn one_copy(options: &Options, log: &AppLog) -> Option<Option<Box<dyn std::any::Any>>> {
    let key = win::instance::instance_key();
    let claim = win::process::claim(&key);
    let message: &[u8] = if options.background { b"" } else { b"show" };
    let mut host = win::process::SystemHost {
        root: exe_dir(),
        logs: data::logs::log_dir(&options.root.clone().unwrap_or_else(files::app_dir)),
        answers: || win::instance::message_running_copy(message, &key),
        start: std::time::Instant::now(),
    };
    if win::settle::settle(&mut host, claim.first, win::settle::WAIT_OTHER_OWNS) {
        return None;
    }
    log.info("Start-up: single instance ok");
    Some(Some(Box::new(claim)))
}

#[cfg(not(windows))]
fn one_copy(_options: &Options, log: &AppLog) -> Option<Option<Box<dyn std::any::Any>>> {
    log.info("Start-up: single instance ok (no mutex off Windows)");
    Some(None)
}

/// 开机启动: an existing entry follows this copy when the app moved (autostart.refresh).
fn autostart_refresh() {
    #[cfg(windows)]
    {
        let launcher = exe_dir().and_then(|dir| win::autostart::launcher_in(&dir));
        win::autostart::RunEntry::app().refresh(launcher.as_deref());
    }
}

/// Where the models may be (ocr_engine.model_dirs): BLACKLIST_DETECT_MODEL_DIR, models beside the exe, models here.
pub fn model_roots() -> Vec<PathBuf> {
    let mut roots: Vec<PathBuf> = std::env::var_os("BLACKLIST_DETECT_MODEL_DIR").map(PathBuf::from).into_iter().collect();
    roots.extend(exe_dir().map(|dir| dir.join("models")));
    roots.extend(std::env::current_dir().ok().map(|dir| dir.join("models")));
    roots
}

/// The first root holding both a detection and a recognition model.
pub fn model_dirs(roots: &[PathBuf]) -> Option<(PathBuf, PathBuf)> {
    roots.iter().filter(|root| root.is_dir()).find_map(|root| Some((find_model_dir(root, "det")?, find_model_dir(root, "rec")?)))
}

const MODEL_FILES: [&str; 5] = ["inference.yml", "inference.json", "inference.pdmodel", "inference.pdiparams", "inference.onnx"];

/// ocr_engine._find_model_dir: the root itself when it is that model, else the first child folder named for it.
fn find_model_dir(root: &Path, kind: &str) -> Option<PathBuf> {
    let has_model = |dir: &Path| MODEL_FILES.iter().any(|name| dir.join(name).exists());
    let named = |dir: &Path| dir.file_name().is_some_and(|name| name.to_string_lossy().to_lowercase().contains(kind));
    if named(root) && MODEL_FILES[..3].iter().any(|name| root.join(name).exists()) {
        return Some(root.to_path_buf());
    }
    let mut children: Vec<PathBuf> = std::fs::read_dir(root).ok()?.flatten().map(|entry| entry.path()).collect();
    children.sort();
    children.into_iter().filter(|child| child.is_dir() && named(child)).find(|child| {
        has_model(child) || std::fs::read_dir(child).map(|mut items| items.next().is_some()).unwrap_or(false)
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn options_read_the_flags() {
        let args: Vec<String> = ["--background", "--data", "x", "--quit-after-start"].iter().map(|s| s.to_string()).collect();
        let options = Options::parse(&args);
        assert!(options.background && options.quit_after_start);
        assert_eq!(options.root, Some(PathBuf::from("x")));
        assert_eq!(Options::parse(&[]), Options::default());
    }

    #[test]
    fn models_are_found_by_folder_name() {
        let dir = tempfile::tempdir().unwrap();
        let root = dir.path().join("models");
        assert_eq!(model_dirs(std::slice::from_ref(&root)), None);
        std::fs::create_dir_all(root.join("PP-OCRv5_mobile_det")).unwrap();
        std::fs::create_dir_all(root.join("PP-OCRv5_mobile_rec")).unwrap();
        assert_eq!(model_dirs(std::slice::from_ref(&root)), None, "empty folders are no model");
        std::fs::write(root.join("PP-OCRv5_mobile_det/inference.onnx"), b"x").unwrap();
        std::fs::write(root.join("PP-OCRv5_mobile_rec/weights.bin"), b"x").unwrap();
        let (det, rec) = model_dirs(&[dir.path().join("none"), root.clone()]).unwrap();
        assert!(det.ends_with("PP-OCRv5_mobile_det") && rec.ends_with("PP-OCRv5_mobile_rec"));
    }
}
