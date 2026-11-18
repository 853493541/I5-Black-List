//! The Rust preview (cargo feature `preview`, docs/dev/preview.md): a copy of the app the player tries beside v1.0.1.
//! It has a name, a data folder, a single-instance key and no 开机启动 of its own, never looks for updates and never
//! sweeps an install folder. On its first run it copies everything of the player's from v1.0.1's data folder (all but
//! logs, caches, update staging and locks), opening each file read-only. Every choice here takes `on` so both builds are tested in one `cargo test`.

use std::io;
use std::path::{Path, PathBuf};

/// Built with `--features preview`.
pub const ON: bool = cfg!(feature = "preview");
/// The preview's name: window title, tray, log.
/// The preview's name: window title, tray, log, folder and artifact. Each preview has its own (this is the user's
/// "Nov v2"); the data folder and key stay the same, so a later preview keeps the data this one copied.
pub const NAME: &str = "模仿者小工具 Rust 预览 11月 v2";
/// Its data folder in %APPDATA%, beside v1.0.1's BlackListDetect.
pub const FOLDER: &str = "BlackListDetect-RustPreview";
/// What its single-instance key ends with, so it never answers for v1.0.1 or the other way round.
pub const KEY_SUFFIX: &str = "-RustPreview";
/// Written once the first-run copy has run; while it is there, nothing is copied again.
pub const COPIED_MARK: &str = "preview-copied.txt";
/// What the first-run copy leaves behind in the old folder: the logs (and their running marker and crash dumps), the
/// 场景 tunes made again from the assets (ui_music.sound_dir), an update's staging, the updater's mirror list and the
/// debug captures. Everything else of the player's is copied: the lists, 嘉宾, 组合, 我, records, 设置, custom sounds,
/// backups and any file a later version added.
pub const SKIPPED: [&str; 5] = ["logs", "sounds", "updates", "mirrors.json", "debug"];
/// Half-written files (storage.atomic_write's .tmp) and locks, anywhere.
pub const SKIPPED_ENDINGS: [&str; 3] = [".tmp", ".lock", ".part"];

fn skipped(name: &str, top: bool) -> bool {
    (top && (SKIPPED.contains(&name) || name == COPIED_MARK)) || SKIPPED_ENDINGS.iter().any(|end| name.ends_with(end))
}

/// Called first in main: the data folder and the tray follow the preview's name.
pub fn install() {
    if ON {
        common::paths::use_folder_name(FOLDER);
        win::tray::model::set_tooltip(NAME);
    }
}

/// The version as the window title ("模仿者小工具 " + this) and 关于 show it: "Rust 预览 11月 v2 (0.1.0)".
pub fn shown_version(version: &str, on: bool) -> String {
    if on {
        format!("{} ({version})", NAME.trim_start_matches("模仿者小工具 "))
    } else {
        version.to_string()
    }
}

/// The single-instance key: the preview's never matches the normal build's.
pub fn instance_key(base: &str, on: bool) -> String {
    if on {
        format!("{base}{KEY_SUFFIX}")
    } else {
        base.to_string()
    }
}

/// The data folder's name for a build.
pub fn folder_name(on: bool) -> &'static str {
    if on {
        FOLDER
    } else {
        common::paths::FOLDER_NAME
    }
}

/// v1.0.1's data folder, the one the preview copies from (never written).
pub fn old_folder() -> PathBuf {
    common::paths::base_dir().join(common::paths::FOLDER_NAME)
}

/// What the first-run copy did.
#[derive(Debug, Default, PartialEq, Eq)]
pub struct Copied {
    /// The paths copied, relative to the data folder, with / between folders.
    pub files: Vec<String>,
    /// Why it copied nothing, when it did not run.
    pub skipped: Option<&'static str>,
}

impl Copied {
    pub fn line(&self, old: &Path) -> String {
        match self.skipped {
            Some(why) => format!("Preview: nothing copied from {} ({why}).", old.display()),
            None if self.files.is_empty() => format!("Preview: nothing to copy in {}.", old.display()),
            None => format!("Preview: copied {} files from {} (read-only): {}.", self.files.len(), old.display(), self.files.join(", ")),
        }
    }
}

/// The first-run copy: when `new` holds nothing of the player's yet (only logs) and no mark, everything in `old` but
/// `SKIPPED` is read (each file opened read-only) and written into `new`. The old files are never written, renamed or
/// held open past their read. The mark is written after, so a second run copies nothing.
pub fn copy_old_data(new: &Path, old: &Path) -> io::Result<Copied> {
    if new.join(COPIED_MARK).exists() {
        return Ok(Copied { skipped: Some("copied before"), ..Copied::default() });
    }
    let own = std::fs::read_dir(new).map(|items| items.flatten().any(|item| !skipped(&item.file_name().to_string_lossy(), true)));
    if own.unwrap_or(false) {
        return Ok(Copied { skipped: Some("the preview has data of its own"), ..Copied::default() });
    }
    if same_folder(new, old) {
        return Ok(Copied { skipped: Some("same folder"), ..Copied::default() });
    }
    let mut files = Vec::new();
    if old.is_dir() {
        copy_tree(old, new, "", &mut files)?;
    }
    std::fs::create_dir_all(new)?;
    let note = format!("Copied once from {}:\n{}\n", old.display(), files.join("\n"));
    std::fs::write(new.join(COPIED_MARK), note)?;
    Ok(Copied { files, skipped: None })
}

fn same_folder(a: &Path, b: &Path) -> bool {
    match (a.canonicalize(), b.canonicalize()) {
        (Ok(a), Ok(b)) => a == b,
        _ => a == b,
    }
}

/// Opens `source` read-only (File::open) and writes its bytes to `target`.
fn copy_read_only(source: &Path, target: &Path) -> io::Result<()> {
    let mut reader = std::fs::File::open(source)?;
    if let Some(parent) = target.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let mut writer = std::fs::File::create(target)?;
    io::copy(&mut reader, &mut writer)?;
    Ok(())
}

fn copy_tree(source: &Path, target: &Path, shown: &str, files: &mut Vec<String>) -> io::Result<()> {
    let mut entries: Vec<_> = std::fs::read_dir(source)?.flatten().collect();
    entries.sort_by_key(|entry| entry.file_name());
    for entry in entries {
        let name = entry.file_name();
        if skipped(&name.to_string_lossy(), shown.is_empty()) {
            continue;
        }
        let shown = if shown.is_empty() { name.to_string_lossy().into_owned() } else { format!("{shown}/{}", name.to_string_lossy()) };
        let path = entry.path();
        let kind = entry.file_type()?;
        if kind.is_dir() {
            copy_tree(&path, &target.join(&name), &shown, files)?;
        } else if kind.is_file() {
            copy_read_only(&path, &target.join(&name))?;
            files.push(shown);
        }
    }
    Ok(())
}

/// The updater for a build: the preview never looks for updates, whatever it is given.
pub fn updater(given: Box<dyn crate::wiring::stubs::UpdateCheck>, on: bool) -> Box<dyn crate::wiring::stubs::UpdateCheck> {
    if on {
        Box::new(crate::wiring::stubs::Quiet)
    } else {
        given
    }
}

#[cfg(test)]
#[path = "preview_tests.rs"]
mod tests;
