//! summary_text: what the export says about this computer and the app's settings. Counts only, no names.

use std::path::{Path, PathBuf};

use chrono::NaiveDateTime;

/// The settings and counts the summary names, from the Store (`Settings::from_store`).
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Settings {
    pub safe_mode: bool,
    pub auto_capture: bool,
    pub stream_mode: String,
    pub hotkey: String,
    pub entries: usize,
    pub likes: usize,
    pub scans: usize,
}

impl Settings {
    pub fn from_store(store: &crate::store::Store) -> Settings {
        Settings {
            safe_mode: store.settings.safe_mode,
            auto_capture: store.settings.auto_capture,
            stream_mode: store.settings.stream_mode.clone(),
            hotkey: store.settings.hotkey.clone(),
            entries: store.entries.len(),
            likes: store.likes.len(),
            scans: store.scans.len(),
        }
    }
}

fn py_bool(value: bool) -> &'static str {
    if value {
        "True"
    } else {
        "False"
    }
}

/// "2026-11-18 09:05:07": the time in the summary's 导出于 line.
pub fn summary_stamp(now: NaiveDateTime) -> String {
    now.format("%Y-%m-%d %H:%M:%S").to_string()
}

/// "20261118-0905": the time in the export's file name (`export_logs`'s `stamp`).
pub fn export_stamp(now: NaiveDateTime) -> String {
    now.format("%Y%m%d-%H%M").to_string()
}

/// The summary, ending in a newline. `version` is the app's ("v1.0.1"), `machine` [`super::Machine::line`],
/// `screens` [`super::screens_line`], `device` what recognition runs on ("cpu").
pub fn summary_text(version: &str, now: NaiveDateTime, machine: &str, screens: &str, device: &str, s: &Settings) -> String {
    let lines = [
        format!("模仿者小工具 {version}"),
        format!("导出于 {}", summary_stamp(now)),
        String::new(),
        machine.to_string(),
        format!("Screens: {screens}"),
        format!("Recognition on {device}"),
        format!(
            "基础模式 {}, 自动检查 {}, 直播模式 {}, hotkey {}",
            py_bool(s.safe_mode),
            py_bool(s.auto_capture),
            py_bool(!s.stream_mode.is_empty()),
            s.hotkey
        ),
        format!("黑名单 {} people, 嘉宾 {} people, 记录 {} lobbies", s.entries, s.likes, s.scans),
    ];
    lines.join("\n") + "\n"
}

/// The Desktop when Windows does not say where it is (`win::machine::desktop` asks it): home\Desktop.
pub fn desktop_fallback(home: &Path) -> PathBuf {
    home.join("Desktop")
}
