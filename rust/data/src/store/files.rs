//! Where the files live (paths.py's app_dir) and how they are written: atomically, a copy a day kept for a week, and an
//! unreadable one moved aside under a new name.

use super::py::{dumps, loads, Res};
use chrono::NaiveDateTime;
use serde_json::Value;
use std::io;
use std::path::{Path, PathBuf};

const BACKUP_DAYS: usize = 7;

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

fn with_suffix(path: &Path, extra: &str) -> PathBuf {
    let mut name = path.file_name().unwrap_or_default().to_os_string();
    name.push(extra);
    path.with_file_name(name)
}

fn stem_suffix(path: &Path) -> (String, String) {
    let stem = path.file_stem().and_then(|s| s.to_str()).unwrap_or_default().to_string();
    let suffix = path.extension().and_then(|s| s.to_str()).map_or(String::new(), |e| format!(".{e}"));
    (stem, suffix)
}

/// storage._atomic_write: the JSON to <name>.tmp, then over the file.
pub fn atomic_write(path: &Path, payload: &Value) -> io::Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let temporary = with_suffix(path, ".tmp");
    std::fs::write(&temporary, dumps(payload))?;
    std::fs::rename(&temporary, path)
}

/// Read a file as storage.py does; Err(None) when it is not there, Err(Some) when it does not read.
pub fn read_json(path: &Path) -> Result<Value, Option<String>> {
    let bytes = match std::fs::read(path) {
        Ok(b) => b,
        Err(e) if e.kind() == io::ErrorKind::NotFound => return Err(None),
        Err(e) => return Err(Some(e.to_string())),
    };
    let parsed: Res<Value> = loads(&bytes);
    parsed.map_err(|e| Some(e.0))
}

/// storage._daily_backup: the list as it was before today's first change; the last week of copies kept.
pub fn daily_backup(path: &Path, now: NaiveDateTime) {
    if !path.exists() {
        return;
    }
    let folder = path.parent().unwrap_or(Path::new(".")).join("backups");
    let (stem, suffix) = stem_suffix(path);
    let target = folder.join(format!("{stem}-{}{suffix}", now.format("%Y-%m-%d")));
    if target.exists() {
        return;
    }
    let copy = || -> io::Result<()> {
        std::fs::create_dir_all(&folder)?;
        std::fs::write(&target, std::fs::read(path)?)?;
        let mut old: Vec<PathBuf> = std::fs::read_dir(&folder)?
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|p| {
                let name = p.file_name().and_then(|n| n.to_str()).unwrap_or_default();
                name.starts_with(&format!("{stem}-")) && name.ends_with(&suffix) && name.len() >= stem.len() + 1 + suffix.len()
            })
            .collect();
        old.sort();
        let keep = old.len().saturating_sub(BACKUP_DAYS);
        for gone in &old[..keep] {
            std::fs::remove_file(gone)?;
        }
        Ok(())
    };
    let _ = copy();
}

/// storage._set_aside: an unreadable file moved out of the way; None when it cannot be moved.
pub fn set_aside(path: &Path, now: NaiveDateTime) -> Option<PathBuf> {
    let (stem, suffix) = stem_suffix(path);
    let target = path.with_file_name(format!("{stem}.unreadable-{}{suffix}", now.format("%Y%m%d-%H%M%S")));
    std::fs::rename(path, &target).ok().map(|_| target)
}
