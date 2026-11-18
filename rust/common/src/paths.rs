//! paths.py: where the lists and settings live, the environment a started program gets, and the OCR's threads.

use std::path::{Path, PathBuf};

/// paths.app_dir: Windows %APPDATA%\BlackListDetect, elsewhere the XDG config dir. `windows` and `var` stand for
/// sys.platform and os.environ, so both sides are testable anywhere.
pub fn app_dir_for(windows: bool, var: impl Fn(&str) -> Option<String>, home: &Path) -> PathBuf {
    let set = |name: &str| var(name).filter(|v| !v.is_empty());
    let base = if windows {
        set("APPDATA").map_or_else(|| home.join("AppData").join("Roaming"), PathBuf::from)
    } else {
        set("XDG_CONFIG_HOME").map_or_else(|| home.join(".config"), PathBuf::from)
    };
    base.join("BlackListDetect")
}

/// paths.app_dir for this PC.
pub fn app_dir() -> PathBuf {
    let home = std::env::var_os(if cfg!(windows) { "USERPROFILE" } else { "HOME" }).map_or_else(PathBuf::new, PathBuf::from);
    app_dir_for(cfg!(windows), |name| std::env::var(name).ok(), &home)
}

/// paths.custom_sound_dir: the player's own 场景 sounds.
pub fn custom_sound_dir(root: &Path) -> PathBuf {
    root.join("custom_sounds")
}

/// paths._NOT_INHERITED: set for this process only. Paddle's OMP_NUM_THREADS=1 left a child's OCR one core.
const NOT_INHERITED: [&str; 1] = ["OMP_NUM_THREADS"];
/// paths._NOT_INHERITED_PREFIX: Intel OpenMP's marker that it is loaded.
const NOT_INHERITED_PREFIX: &str = "__KMP_REGISTERED_LIB_";

/// paths.child_env over the given variables: all but this process's own OCR settings.
pub fn child_env_from(vars: impl IntoIterator<Item = (String, String)>) -> Vec<(String, String)> {
    vars.into_iter()
        .filter(|(key, _)| {
            let upper = key.to_uppercase();
            !NOT_INHERITED.contains(&upper.as_str()) && !upper.starts_with(NOT_INHERITED_PREFIX)
        })
        .collect()
}

/// paths.child_env: this process's environment for a program it starts, the next copy of the app above all.
/// Give it to `Command::env_clear().envs(..)`.
pub fn child_env() -> Vec<(String, String)> {
    child_env_from(std::env::vars_os().filter_map(|(k, v)| Some((k.into_string().ok()?, v.into_string().ok()?))))
}

/// paths.ocr_threads(cores): one thread per core, as Intel advises for oneDNN, 2 to 8. Never 1 (5 times slower);
/// past 8, a check beside a game got slower.
pub fn ocr_threads_for(cores: usize) -> usize {
    cores.clamp(2, 8)
}

/// The OCR's threads on this PC: PADDLE_PDX_CPU_NUM_THREADS when it sets a count (the app sets it from
/// paths.ocr_threads), else paths.ocr_threads() over the physical cores.
pub fn ocr_threads() -> usize {
    match std::env::var("PADDLE_PDX_CPU_NUM_THREADS").ok().and_then(|v| v.parse::<usize>().ok()) {
        Some(count) if count > 0 => count,
        _ => ocr_threads_for(num_cpus::get_physical()),
    }
}
