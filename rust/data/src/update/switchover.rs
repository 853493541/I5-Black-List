//! The one-shot switch from the Python app (v1.0.1) to the Rust app, and the clean-up after every
//! confirmed start from then on (docs/dev/research/rust-switchover.md).
//!
//! The release folder keeps the layout v1.0.1's updater and launcher know: the launcher beside runtime\
//! and blacklist_detect\, and the app's process at runtime\模仿者小工具.exe. That exe is now the Rust app,
//! which the launcher (unchanged) still starts as `runtime\模仿者小工具.exe -m blacklist_detect [args]`.
//! blacklist_detect\ holds the Rust app's files (onnxruntime.dll, the OCR models under ocr\) and
//! FILES_LIST, the list of every file the release ships. Once a start is confirmed, whatever else is
//! under runtime\ and blacklist_detect\ (the Python runtime, the Python app, files a later release
//! dropped) is deleted. The data folder (%APPDATA%\BlackListDetect) is never touched here.

use std::collections::HashSet;
use std::path::{Path, PathBuf};

use super::stage::{self, PARTIAL, PENDING, STAGED};

/// The list of the release's files, one folder-relative path per line with `/` between parts.
pub const FILES_LIST: &str = "blacklist_detect/files.txt";
/// The app's exe, where v1.0.1's launcher starts it.
pub const APP_EXE: &str = "runtime/模仿者小工具.exe";
/// The file v1.0.1's updater insists an update carries; the Rust release keeps a one-line one.
pub const MARKER: &str = "blacklist_detect/__init__.py";
/// The folders the clean-up may delete in; everything else in the folder is left alone.
pub const SWEPT: [&str; 2] = ["runtime", "blacklist_detect"];

/// The arguments the app was given, without the `-m blacklist_detect` v1.0.1's launcher puts first.
pub fn app_args<I: IntoIterator<Item = String>>(args: I) -> Vec<String> {
    let mut args: Vec<String> = args.into_iter().collect();
    if args.len() >= 2 && args[0] == "-m" && args[1] == "blacklist_detect" {
        args.drain(..2);
    }
    args
}

/// The release folder the exe runs from: exe is root\runtime\<name>.exe and root has a launcher.
/// None for a build run from the source tree.
pub fn install_root(exe: &Path) -> Option<PathBuf> {
    let runtime = exe.parent()?;
    if runtime.file_name()? != "runtime" {
        return None;
    }
    let root = runtime.parent()?;
    stage::LAUNCHERS.iter().any(|name| root.join(name).is_file()).then(|| root.to_path_buf())
}

/// What a confirmed start did.
#[derive(Debug, Default, PartialEq, Eq)]
pub struct Cleaned {
    /// The launcher was told the new version runs (update.check was there).
    pub confirmed: bool,
    /// Files deleted under runtime\ and blacklist_detect\.
    pub files: usize,
    /// Files that could not be deleted (in use, read-only); the next start tries again.
    pub failed: usize,
}

/// The release's files from FILES_LIST, or None when there is no usable list (a build from the
/// source tree, a damaged folder): then nothing is deleted.
pub fn release_files(root: &Path) -> Option<HashSet<String>> {
    let text = std::fs::read_to_string(root.join(FILES_LIST)).ok()?;
    let files: HashSet<String> =
        text.lines().map(|line| line.trim().trim_start_matches('\u{feff}').to_string()).filter(|line| !line.is_empty()).collect();
    // A list without the app's own exe and the list itself is not one this code wrote.
    (files.contains(APP_EXE) && files.contains(FILES_LIST) && files.contains(MARKER)).then_some(files)
}

/// The app started well: tell the launcher (stage::confirm_started), then delete what the release does
/// not ship. Nothing is deleted while an update is waiting or unconfirmed, so a failed start can still
/// be rolled back. Safe to call on every start; it does nothing once the folder is clean.
pub fn after_good_start(root: &Path, current: &str) -> Cleaned {
    let mut done = Cleaned { confirmed: stage::confirm_started(Some(root), current), ..Cleaned::default() };
    let busy = [STAGED, PARTIAL, PENDING].iter().any(|name| root.join(name).exists());
    if busy {
        return done;
    }
    if let Some(keep) = release_files(root) {
        for folder in SWEPT {
            sweep(root, &root.join(folder), &keep, &mut done);
        }
    }
    done
}

fn rel_of(root: &Path, path: &Path) -> Option<String> {
    let rel = path.strip_prefix(root).ok()?;
    let parts: Option<Vec<&str>> = rel.components().map(|part| part.as_os_str().to_str()).collect();
    Some(parts?.join("/"))
}

/// Delete every file under folder that keep does not name, then the folders left empty. Links are
/// removed as links, never followed.
fn sweep(root: &Path, folder: &Path, keep: &HashSet<String>, done: &mut Cleaned) -> bool {
    let Ok(entries) = std::fs::read_dir(folder) else { return false };
    let mut empty = true;
    for entry in entries.flatten() {
        let path = entry.path();
        let Ok(kind) = entry.file_type() else {
            empty = false;
            continue;
        };
        if kind.is_dir() {
            if sweep(root, &path, keep, done) {
                let _ = std::fs::remove_dir(&path);
            } else {
                empty = false;
            }
            continue;
        }
        if rel_of(root, &path).is_some_and(|rel| keep.contains(&rel)) {
            empty = false;
        } else if std::fs::remove_file(&path).is_ok() {
            done.files += 1;
        } else {
            done.failed += 1;
            empty = false;
        }
    }
    empty
}

#[cfg(test)]
#[path = "switchover_tests.rs"]
mod tests;
