//! names.py: what the app is called, and what its files are called.
//!
//! The app was 黑名单检测 until v0.4.2. A folder unzipped before then keeps its old file names when it
//! updates itself, so everything that looks for the launcher or the app's process takes either name, new first.

use std::path::{Path, PathBuf};

pub const APP_NAME: &str = "模仿者小工具";
/// The launcher a friend double-clicks, beside runtime\ and blacklist_detect\.
pub const LAUNCHERS: [&str; 2] = ["模仿者小工具.exe", "黑名单检测.exe"];
/// The app's own process in runtime\: pythonw.exe with the app's name and icon.
pub const PROCESSES: [&str; 2] = ["模仿者小工具.exe", "I5黑名单.exe"];

/// The launcher in this folder, under whichever name it has.
pub fn launcher_in(root: &Path) -> Option<PathBuf> {
    LAUNCHERS.iter().map(|name| root.join(name)).find(|path| path.is_file())
}
