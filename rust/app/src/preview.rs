//! The Rust preview (cargo feature `preview`, docs/dev/preview.md): a copy of the app the player tries beside v1.0.1.
//! It has a name, a data folder, a single-instance key and no 开机启动 of its own, never looks for updates and never
//! sweeps an install folder. On its first run it copies the lists, 设置, 嘉宾 and custom sounds from v1.0.1's data
//! folder, opening them read-only. Every choice here takes `on` so both builds are tested in one `cargo test`.

use std::io;
use std::path::{Path, PathBuf};

/// Built with `--features preview`.
pub const ON: bool = cfg!(feature = "preview");
/// The preview's name: window title, tray, log.
pub const NAME: &str = "模仿者小工具 Rust 预览";
/// Its data folder in %APPDATA%, beside v1.0.1's BlackListDetect.
pub const FOLDER: &str = "BlackListDetect-RustPreview";
/// What its single-instance key ends with, so it never answers for v1.0.1 or the other way round.
pub const KEY_SUFFIX: &str = "-RustPreview";
/// Written once the first-run copy has run; while it is there, nothing is copied again.
pub const COPIED_MARK: &str = "preview-copied.txt";
/// The files copied from the old folder: the lists, 设置, 嘉宾 and the history.
pub const COPIED_FILES: [&str; 4] = ["blacklist.json", "settings.json", "likes.json", "history.json"];
/// And this folder, the 场景 sounds the player added.
pub const COPIED_FOLDER: &str = "custom_sounds";

/// Called first in main: the data folder and the tray follow the preview's name.
pub fn install() {
    if ON {
        common::paths::use_folder_name(FOLDER);
        win::tray::model::set_tooltip(NAME);
    }
}

/// The version as the window title and 关于 show it ("模仿者小工具 Rust 预览 0.1.0").
pub fn shown_version(version: &str, on: bool) -> String {
    if on {
        format!("Rust 预览 {version}")
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
    /// The paths copied, relative to the data folder.
    pub files: Vec<String>,
    /// Why it copied nothing, when it did not run.
    pub skipped: Option<&'static str>,
}

impl Copied {
    pub fn line(&self, old: &Path) -> String {
        match self.skipped {
            Some(why) => format!("Preview: nothing copied from {} ({why}).", old.display()),
            None if self.files.is_empty() => format!("Preview: nothing to copy in {}.", old.display()),
            None => format!("Preview: copied from {} (read-only): {}.", old.display(), self.files.join(", ")),
        }
    }
}

/// The first-run copy: when `new` holds none of the player's files and no mark, the lists, 设置, 嘉宾 and custom
/// sounds in `old` are read (opened read-only) and written into `new`. The old files are never written, renamed or
/// held open past their read. The mark is written after, so a second run copies nothing.
pub fn copy_old_data(new: &Path, old: &Path) -> io::Result<Copied> {
    if new.join(COPIED_MARK).exists() {
        return Ok(Copied { skipped: Some("copied before"), ..Copied::default() });
    }
    if COPIED_FILES.iter().any(|name| new.join(name).exists()) || new.join(COPIED_FOLDER).exists() {
        return Ok(Copied { skipped: Some("the preview has data of its own"), ..Copied::default() });
    }
    if same_folder(new, old) {
        return Ok(Copied { skipped: Some("same folder"), ..Copied::default() });
    }
    let mut files = Vec::new();
    for name in COPIED_FILES {
        let source = old.join(name);
        if source.is_file() {
            copy_read_only(&source, &new.join(name))?;
            files.push(name.to_string());
        }
    }
    let sounds = old.join(COPIED_FOLDER);
    if sounds.is_dir() {
        copy_tree(&sounds, &new.join(COPIED_FOLDER), COPIED_FOLDER, &mut files)?;
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
        let shown = format!("{shown}/{}", name.to_string_lossy());
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
