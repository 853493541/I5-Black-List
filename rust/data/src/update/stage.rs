//! Unpacking the update zip for the launcher, and the files the launcher and the app leave each other
//! (updater.stage, staged_version, launcher_result, note_restart, confirm_started).

use std::path::Path;

use serde_json::Value;

use super::{parse_version, py, UpdateError};

pub const FOLDER: &str = "BlackListDetect";
pub const STAGED: &str = "update.new";
/// Where stage() unpacks, renamed to update.new once whole: the launcher never sees half an update.
pub const PARTIAL: &str = "update.part";
pub const BACKUP: &str = "update.old";
pub const PENDING: &str = "update.check";
pub const VERSION_FILE: &str = ".version";
pub const RESULT: &str = "update.result";
pub const TRIES: &str = "update.tries";
pub const MAX_TRIES: i64 = 2;
pub const TRIES_FORGET_S: f64 = 600.0;
/// names.LAUNCHERS and names.PROCESSES: what an update may put in the folder besides the app.
pub const LAUNCHERS: [&str; 2] = ["模仿者小工具.exe", "黑名单检测.exe"];
pub const PROCESSES: [&str; 2] = ["模仿者小工具.exe", "I5黑名单.exe"];
const ALLOWED_DIR: &str = "blacklist_detect";

/// PurePosixPath(name).parts: "/" for a leading slash, then the parts, without empty ones and ".".
fn posix_parts(name: &str) -> Vec<&str> {
    let mut parts = Vec::new();
    if name.starts_with("//") && !name.starts_with("///") {
        parts.push("//");
    } else if name.starts_with('/') {
        parts.push("/");
    }
    parts.extend(name.split('/').filter(|part| !part.is_empty() && *part != "."));
    parts
}

/// What an update may lay over the folder: the app, the launcher, the app's exe, the instructions.
pub fn allowed(rel: &[&str]) -> bool {
    if rel.is_empty() || rel.contains(&"..") || rel[0].starts_with('/') {
        return false;
    }
    // Not in Python (which joins on a POSIX path): a part Windows would read as a drive or a stream.
    if rel.iter().any(|part| part.contains(':')) {
        return false;
    }
    if rel[0] == ALLOWED_DIR {
        return !rel.contains(&"models") && !rel.contains(&"__pycache__");
    }
    let joined = rel.join("/");
    LAUNCHERS.contains(&joined.as_str()) || PROCESSES.iter().any(|name| joined == format!("runtime/{name}")) || joined == "使用说明.txt"
}

fn io(error: impl std::fmt::Display) -> UpdateError {
    UpdateError::Io(error.to_string())
}

/// Unpack the update zip into root/update.new, through update.part, so an app stopped halfway leaves
/// no update.new to lay over.
pub fn stage(zip_path: &Path, root: &Path, version: &str) -> Result<std::path::PathBuf, UpdateError> {
    let (staged, partial) = (root.join(STAGED), root.join(PARTIAL));
    for old in [&partial, &staged] {
        if old.exists() {
            std::fs::remove_dir_all(old).map_err(io)?;
        }
    }
    std::fs::create_dir(&partial).map_err(io)?;
    match unpack(zip_path, &partial, version).and_then(|()| std::fs::rename(&partial, &staged).map_err(|_| UpdateError::Broken)) {
        Ok(()) => Ok(staged),
        Err(error) => {
            let _ = std::fs::remove_dir_all(&partial);
            Err(error)
        }
    }
}

fn unpack(zip_path: &Path, partial: &Path, version: &str) -> Result<(), UpdateError> {
    let file = std::fs::File::open(zip_path).map_err(|_| UpdateError::Broken)?;
    let mut bundle = zip::ZipArchive::new(file).map_err(|_| UpdateError::Broken)?;
    for index in 0..bundle.len() {
        let mut item = bundle.by_index(index).map_err(|_| UpdateError::Broken)?;
        // zipfile on Windows reads \ as /, and ends a name at a NUL.
        let name = item.name().split('\0').next().unwrap_or_default().replace('\\', "/");
        if name.ends_with('/') {
            continue;
        }
        let parts = posix_parts(&name);
        if parts.first() != Some(&FOLDER) {
            continue;
        }
        if !allowed(&parts[1..]) {
            continue;
        }
        let target = parts[1..].iter().fold(partial.to_path_buf(), |path, part| path.join(part));
        if let Some(parent) = target.parent() {
            std::fs::create_dir_all(parent).map_err(|_| UpdateError::Broken)?;
        }
        let mut out = std::fs::File::create(&target).map_err(|_| UpdateError::Broken)?;
        std::io::copy(&mut item, &mut out).map_err(|_| UpdateError::Broken)?;
    }
    if !partial.join(ALLOWED_DIR).join("__init__.py").is_file() {
        return Err(UpdateError::Incomplete);
    }
    std::fs::write(partial.join(VERSION_FILE), version).map_err(|_| UpdateError::Broken)
}

/// The version waiting in update.new, or "".
pub fn staged_version(root: Option<&Path>) -> String {
    root.and_then(|root| std::fs::read(root.join(STAGED).join(VERSION_FILE)).ok())
        .and_then(|bytes| String::from_utf8(bytes).ok())
        .map(|text| py::strip(&text).to_string())
        .unwrap_or_default()
}

/// What the launcher did at the last start, if it did anything, once: the file goes once read.
pub fn launcher_result(root: Option<&Path>) -> String {
    let Some(path) = root.map(|root| root.join(RESULT)) else { return String::new() };
    let Some(said) = std::fs::read(&path).ok().and_then(|bytes| String::from_utf8(bytes).ok()) else {
        return String::new();
    };
    if std::fs::remove_file(&path).is_err() {
        return String::new();
    }
    py::strip(&said).to_string()
}

fn read_json(path: &Path) -> Option<Value> {
    serde_json::from_str(&String::from_utf8(std::fs::read(path).ok()?).ok()?).ok()
}

/// Count a restart into version, at `now` (seconds since 1970). False when it has been tried MAX_TRIES
/// times lately: the launcher could not lay it over the folder, and restarting again would only loop.
pub fn note_restart(root: Option<&Path>, version: &str, now: f64) -> bool {
    let Some(root) = root else { return true };
    let path = root.join(TRIES);
    let count = read_json(&path)
        .and_then(|saved| {
            let saved = saved.as_object()?;
            let same = saved.get("version").and_then(Value::as_str) == Some(version);
            let at = saved.get("at").map_or(Some(0.0), py::float_of)?;
            if same && now - at < TRIES_FORGET_S {
                py::int_of(saved.get("count")?)
            } else {
                Some(0)
            }
        })
        .unwrap_or(0);
    if count >= MAX_TRIES {
        return false;
    }
    let text = format!(
        "{{\"version\": {}, \"count\": {}, \"at\": {}}}",
        super::mirrors::quoted(version),
        count + 1,
        py::float_repr(now)
    );
    let _ = std::fs::write(&path, text);
    true
}

/// The new version (`current`) is running: the launcher need not put the old one back. True if it had
/// to be told. The restart count goes once the version it counts has gone in.
pub fn confirm_started(root: Option<&Path>, current: &str) -> bool {
    let Some(root) = root else { return false };
    let saved = read_json(&root.join(TRIES))
        .and_then(|saved| Some(py::str_of(saved.as_object()?.get("version").unwrap_or(&Value::String(String::new())))?))
        .unwrap_or_default();
    if parse_version(&saved) <= parse_version(current) {
        let _ = std::fs::remove_file(root.join(TRIES));
    }
    if !root.join(PENDING).exists() {
        return false;
    }
    let _ = std::fs::remove_file(root.join(PENDING));
    let _ = std::fs::remove_dir_all(root.join(BACKUP));
    true
}
