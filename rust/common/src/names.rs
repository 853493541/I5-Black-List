//! names.py: what the app's files and processes are called.

use std::path::{Path, PathBuf};

/// names.LAUNCHERS: the launcher's names, newest first.
pub const LAUNCHERS: [&str; 2] = ["模仿者小工具.exe", "黑名单检测.exe"];
/// names.PROCESSES: the app's own process in runtime\: pythonw.exe with the app's name and icon.
pub const PROCESSES: [&str; 2] = ["模仿者小工具.exe", "I5黑名单.exe"];

/// The launcher in this folder, under whichever name it has.
pub fn launcher_in(root: &Path) -> Option<PathBuf> {
    LAUNCHERS.iter().map(|name| root.join(name)).find(|path| path.is_file())
}
