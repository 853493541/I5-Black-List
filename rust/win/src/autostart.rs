//! 开机自动启动 (autostart.py): the current user's Run key points at the launcher with --background.
//! Only HKEY_CURRENT_USER is touched; nothing needs administrator rights.

use std::path::Path;

pub const RUN_KEY: &str = r"Software\Microsoft\Windows\CurrentVersion\Run";
pub const VALUE_NAME: &str = "BlackListDetect";
pub const BACKGROUND: &str = "--background";
/// The launcher's names, newest first (names.LAUNCHERS), and the one in a folder.
pub use common::names::{launcher_in, LAUNCHERS};

/// The Run entry's text for a launcher.
pub fn command(launcher: &Path) -> String {
    format!("\"{}\" {BACKGROUND}", launcher.display())
}

/// Where the entry lives. The app uses `RunEntry::app()`; tests use a key of their own, so a test run
/// never adds or removes the player's own entry.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RunEntry {
    pub key: String,
    pub value: String,
}

impl RunEntry {
    pub fn app() -> RunEntry {
        RunEntry { key: RUN_KEY.to_string(), value: VALUE_NAME.to_string() }
    }
}

#[cfg(windows)]
impl RunEntry {
    /// The entry's text, empty when there is none.
    pub fn read(&self) -> String {
        windows_registry::CURRENT_USER.open(&self.key).and_then(|key| key.get_string(&self.value)).unwrap_or_default()
    }

    pub fn is_enabled(&self) -> bool {
        !self.read().is_empty()
    }

    /// Add the entry (with `command`) or remove it. False when it could not be changed.
    pub fn set(&self, command: Option<&str>) -> bool {
        let Ok(key) = windows_registry::CURRENT_USER.create(&self.key) else { return false };
        match command {
            Some("") => false,
            Some(text) => key.set_string(&self.value, text).is_ok(),
            None => key.remove_value(&self.value).is_ok() || key.get_string(&self.value).is_err(),
        }
    }

    /// After the app moved, point an existing entry at this launcher.
    pub fn refresh(&self, launcher: Option<&Path>) {
        let current = self.read();
        if let Some(exe) = launcher {
            let wanted = command(exe);
            if !current.is_empty() && current != wanted {
                self.set(Some(&wanted));
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn command_quotes_the_launcher_and_starts_in_the_tray() {
        assert_eq!(command(Path::new(r"C:\Games\模仿者小工具.exe")), "\"C:\\Games\\模仿者小工具.exe\" --background");
    }

    #[test]
    fn launcher_is_found_under_either_name() {
        let dir = std::env::temp_dir().join(format!("win-autostart-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        assert_eq!(launcher_in(&dir), None);
        std::fs::write(dir.join("黑名单检测.exe"), b"").unwrap();
        assert_eq!(launcher_in(&dir), Some(dir.join("黑名单检测.exe")));
        std::fs::write(dir.join("模仿者小工具.exe"), b"").unwrap();
        assert_eq!(launcher_in(&dir), Some(dir.join("模仿者小工具.exe")));
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[cfg(windows)]
    #[test]
    fn turning_it_on_and_off_and_following_a_move() {
        let entry = RunEntry { key: format!(r"Software\BlackListDetectTest\Run-{}", std::process::id()), value: VALUE_NAME.into() };
        assert!(!entry.is_enabled());
        assert!(entry.set(Some(&command(Path::new(r"C:\old\模仿者小工具.exe")))));
        assert!(entry.is_enabled());
        entry.refresh(Some(Path::new(r"C:\new\模仿者小工具.exe")));
        assert_eq!(entry.read(), command(Path::new(r"C:\new\模仿者小工具.exe")));
        assert!(!entry.set(Some("")));
        assert!(entry.set(None) && !entry.is_enabled() && entry.set(None));
        entry.refresh(Some(Path::new(r"C:\x.exe")));
        assert!(!entry.is_enabled(), "refresh never turns it on");
        let _ = windows_registry::CURRENT_USER.remove_tree(r"Software\BlackListDetectTest");
    }
}
