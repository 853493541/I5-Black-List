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
    /// The release folder (root\runtime\模仿者小工具.exe beside a launcher); None for a build run from source.
    pub install: Option<PathBuf>,
}

/// How start-up ended.
pub enum Outcome {
    Run(Box<Started>),
    /// Another copy is open and was asked to show itself (or, started with Windows, left alone).
    AlreadyRunning,
}

/// The folder the exe is in, as the file system names it (links and 8.3 names resolved, no \\?\ prefix).
pub fn exe_dir() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let exe = std::fs::canonicalize(&exe).map(plain_path).unwrap_or(exe);
    exe.parent().map(Path::to_path_buf)
}

/// A canonical Windows path without its \\?\ prefix, as a player would type it (\\?\UNC\server → \\server).
pub fn plain_path(path: PathBuf) -> PathBuf {
    let text = path.to_string_lossy();
    if let Some(rest) = text.strip_prefix(r"\\?\UNC\") {
        return PathBuf::from(format!(r"\\{rest}"));
    }
    if let Some(rest) = text.strip_prefix(r"\\?\") {
        return PathBuf::from(rest);
    }
    path
}

/// The models are missing because the zip was not unpacked: the exe runs from inside it (Explorer copies only the exe
/// to %TEMP%\Temp1_<name>.zip\, 7-Zip and WinRAR to 7zO… / Rar$EX…), from the temp folder, or, outside a release,
/// from a folder with no models beside it. The pill then says 请先把压缩包全部解压，再运行.
pub fn needs_unzip(exe_dir: &Path, install: Option<&Path>, temp: Option<&Path>) -> bool {
    let packed = exe_dir.components().any(|part| {
        let part = part.as_os_str().to_string_lossy().to_lowercase();
        [".zip", ".rar", ".7z"].iter().any(|end| part.ends_with(end)) || part.starts_with("rar$ex") || part.starts_with("7zo")
    });
    let in_temp = temp.is_some_and(|temp| exe_dir.starts_with(temp));
    packed || in_temp || (install.is_none() && !exe_dir.join("models").is_dir())
}

/// needs_unzip for this exe.
pub fn unzip_first(install: Option<&Path>) -> bool {
    let temp = std::env::temp_dir();
    let temp = std::fs::canonicalize(&temp).map(plain_path).unwrap_or(temp);
    exe_dir().is_some_and(|dir| needs_unzip(&dir, install, Some(&temp)))
}

/// A Debug line with every quoted text taken out ("…"): names, reasons and tags never reach the log.
pub fn without_text(debug: &str) -> String {
    let mut out = String::with_capacity(debug.len());
    let (mut quoted, mut escaped) = (false, false);
    for c in debug.chars() {
        if quoted {
            match (escaped, c) {
                (true, _) => escaped = false,
                (false, '\\') => escaped = true,
                (false, '"') => {
                    quoted = false;
                    out.push_str("…\"");
                }
                _ => {}
            }
        } else {
            out.push(c);
            quoted = c == '"';
        }
    }
    out
}

/// The release folder this exe runs from (switchover.install_root), None for a build run from source.
pub fn install_root() -> Option<PathBuf> {
    // The preview runs from a plain folder and never takes part in a release's switch-over or sweep.
    if crate::preview::ON {
        return None;
    }
    data::update::switchover::install_root(&std::env::current_exe().ok()?)
}

pub fn start(options: &Options) -> Result<Outcome, String> {
    let root = options.root.clone().unwrap_or_else(files::app_dir);
    std::fs::create_dir_all(&root).map_err(|error| format!("data folder {}: {error}", root.display()))?;
    let log = AppLog::open(&root);
    let build = if crate::preview::ON { crate::preview::NAME } else { "Rust" };
    log.info(&format!("==== Start {VERSION} ({build}, {}) ====", std::env::consts::OS));
    log.info("Start-up: data folder ok");
    if crate::preview::ON && options.root.is_none() {
        let old = crate::preview::old_folder();
        match crate::preview::copy_old_data(&root, &old) {
            Ok(copied) => log.info(&copied.line(&old)),
            Err(error) => log.warn(&format!("Preview: copy from {} stopped: {error}", old.display())),
        }
    }
    if mark_running(&root) {
        log.warn("The last run ended without closing: it was ended from outside (Task Manager, a tool, or a power loss).");
    }
    log.info("Start-up: logs ok");
    let install = install_root();
    let claim = match one_copy(options, install.clone(), &log) {
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
    if crate::preview::ON {
        // The preview never adds, moves or removes a Run entry: v1.0.1's stays as it is.
        log.info("Start-up: autostart ok (off in the preview)");
    } else {
        autostart_refresh(install.as_deref());
        log.info("Start-up: autostart ok");
    }
    let exe = std::env::current_exe().map(|exe| exe.display().to_string()).unwrap_or_default();
    let here = std::env::current_dir().map(|dir| dir.display().to_string()).unwrap_or_default();
    log.info(&format!("Start-up: exe {exe} (folder {}), working folder {here}", exe_dir().unwrap_or_default().display()));
    let roots = model_roots(install.as_deref());
    let models = model_dirs(&roots);
    match &models {
        Some((det, rec)) => log.info(&format!("Start-up: models ok ({}, {})", det.display(), rec.display())),
        // Not fatal: the window opens and says the models are missing, as the Python app does.
        None => {
            let checked: Vec<String> = roots.iter().map(|root| root.display().to_string()).collect();
            let unzip = if unzip_first(install.as_deref()) { "; the zip looks not unpacked" } else { "" };
            log.warn(&format!("Start-up: models missing (checked {}){unzip}", checked.join(", ")));
        }
    }
    // Where the pictures and tunes come from, and whether 环境测试 will find its sample lobby there.
    let assets = super::assemble::assets_dir(install.as_deref());
    let sample = assets.join("sample-lobby.jpg").is_file();
    let (state, found) = if sample { ("ok", "found") } else { ("missing", "not found") };
    log.info(&format!("Start-up: assets {state} ({}, sample lobby {found})", assets.display()));
    Ok(Outcome::Run(Box::new(Started { root, log, store, models, claim, install })))
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

/// The single-instance key this build answers on (the preview's own, never v1.0.1's).
#[cfg(windows)]
pub fn instance_key() -> String {
    crate::preview::instance_key(&win::instance::instance_key(), crate::preview::ON)
}

/// One copy (single.claim, single.settle): Some(claim) to go on, None when another copy answered.
#[cfg(windows)]
fn one_copy(options: &Options, install: Option<PathBuf>, log: &AppLog) -> Option<Option<Box<dyn std::any::Any>>> {
    let key = instance_key();
    let claim = win::process::claim(&key);
    let message: &[u8] = if options.background { b"" } else { b"show" };
    let mut host = win::process::SystemHost {
        root: install,
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
fn one_copy(_options: &Options, _install: Option<PathBuf>, log: &AppLog) -> Option<Option<Box<dyn std::any::Any>>> {
    log.info("Start-up: single instance ok (no mutex off Windows)");
    Some(None)
}

/// 开机启动: an existing entry follows this copy when the app moved (autostart.refresh).
fn autostart_refresh(_install: Option<&Path>) {
    #[cfg(windows)]
    {
        let launcher = _install.and_then(win::autostart::launcher_in);
        win::autostart::RunEntry::app().refresh(launcher.as_deref());
    }
}

/// Where the models may be (ocr_engine.model_dirs): BLACKLIST_DETECT_MODEL_DIR, the release's blacklist_detect\ocr
/// (rust-switchover.md), models beside the exe, models here.
pub fn model_roots(install: Option<&Path>) -> Vec<PathBuf> {
    let mut roots: Vec<PathBuf> = std::env::var_os("BLACKLIST_DETECT_MODEL_DIR").map(PathBuf::from).into_iter().collect();
    roots.extend(install.map(|root| root.join("blacklist_detect").join("ocr")));
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
    fn an_exe_run_from_inside_the_zip_asks_to_unpack_it_first() {
        let path = |parts: &[&str]| parts.iter().collect::<PathBuf>();
        let temp = path(&["C:", "Users", "p", "AppData", "Local", "Temp"]);
        let inside = temp.join("Temp1_模仿者小工具 预览.zip").join("模仿者小工具 预览");
        assert!(needs_unzip(&inside, None, Some(&temp)));
        assert!(needs_unzip(&inside, Some(&temp), None), "the .zip folder alone tells");
        assert!(needs_unzip(&temp.join("7zO8A1B2C3"), Some(&temp), None));
        assert!(needs_unzip(&temp.join("x"), Some(&temp), Some(&temp)), "anywhere in the temp folder");
        let temp = temp.as_path();
        let dir = tempfile::tempdir().unwrap();
        let unpacked = dir.path().join("解压 后").join("模仿者 小工具");
        std::fs::create_dir_all(unpacked.join("models")).unwrap();
        assert!(!needs_unzip(&unpacked, None, Some(temp)), "unpacked, models beside the exe");
        std::fs::remove_dir(unpacked.join("models")).unwrap();
        assert!(needs_unzip(&unpacked, None, Some(temp)), "the exe alone: the rest of the zip is not there");
        assert!(!needs_unzip(&unpacked, Some(dir.path()), Some(temp)), "a release keeps its models elsewhere");
    }

    #[test]
    fn a_canonical_path_is_shown_without_its_prefix() {
        assert_eq!(plain_path(PathBuf::from(r"\\?\C:\游戏\模仿者")), PathBuf::from(r"C:\游戏\模仿者"));
        assert_eq!(plain_path(PathBuf::from(r"\\?\UNC\nas\share")), PathBuf::from(r"\\nas\share"));
        assert_eq!(plain_path(PathBuf::from("/home/x")), PathBuf::from("/home/x"));
    }

    #[test]
    fn debug_text_loses_every_quoted_text() {
        assert_eq!(without_text(r#"Seat { name: "示例坏人 \"x\"", tags: ["炸房"], seat: 3 }"#), r#"Seat { name: "…", tags: ["…"], seat: 3 }"#);
    }

    #[test]
    fn the_pill_says_to_unpack_the_zip_when_that_is_why_models_are_missing() {
        let problem = crate::wiring::flow::Problem::of(&crate::wiring::engine::no_models_for(true));
        assert_eq!((problem.label.as_str(), problem.tip.as_str()), ("请先把压缩包全部解压，再运行", "请先把压缩包全部解压，再运行"));
        let problem = crate::wiring::flow::Problem::of(&crate::wiring::engine::no_models_for(false));
        assert_eq!(problem.label, "识别还没准备好");
    }

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
