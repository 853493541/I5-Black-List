//! The log file beside the settings: a port of blacklist_detect/logs.py.
//!
//! Each line is one event: `2026-10-13 17:43:23.317 INFO    ui     Check 12 …`. Lines after the first of
//! one event are indented by four spaces. Player names are never written whole (masked). app.log rolls
//! over at 1 MB and five files are kept; crash.log is cut to its last part past half a MB.

pub mod export;
pub mod watch;

use std::io::Write as _;
use std::path::{Path, PathBuf};

pub const MAX_BYTES: u64 = 1_000_000;
pub const BACKUPS: u32 = 4;
pub const CRASH_MAX: u64 = 512_000;
pub const CRASH_KEEP: usize = 256_000;
const RUNNING: &str = "running";
/// What Python's text mode writes for "\n": the app's log on Windows has CRLF lines.
pub const NEWLINE: &str = if cfg!(windows) { "\r\n" } else { "\n" };

/// A player's name for the log: the first character, then a * for each one after it.
pub fn masked(name: &str) -> String {
    let mut chars = name.chars();
    chars.next().map(|first| format!("{first}{}", "*".repeat(chars.count()))).unwrap_or_default()
}

/// The thread's short name in a line, from the name each thread gives itself.
pub fn where_of(thread: &str) -> String {
    match thread {
        "MainThread" => "ui".into(),
        "check" => "check".into(),
        "update-check" | "update-download" => "update".into(),
        "watchdog" => "watch".into(),
        "" => "?".into(),
        other => other.chars().take(6).collect(),
    }
}

/// One event as logs._Format writes it: `%(asctime)s.%(msecs)03d %(levelname)-7s %(where)-6s %(message)s`,
/// with every line after the first indented. `time` is local time, `message` holds any traceback.
pub fn format_line(time: chrono::NaiveDateTime, level: &str, thread: &str, message: &str) -> String {
    let millis = time.and_utc().timestamp_subsec_millis();
    let line = format!("{}.{millis:03} {level:<7} {:<6} {message}", time.format("%Y-%m-%d %H:%M:%S"), where_of(thread));
    line.replace('\n', "\n    ")
}

/// logs/ in the data folder.
pub fn log_dir(root: &Path) -> PathBuf {
    root.join("logs")
}

/// app.log with RotatingFileHandler's rollover: before a line that would take the file to max_bytes,
/// app.log.3 → .4 … app.log → app.log.1; an empty file never rolls over.
pub struct RotatingLog {
    pub path: PathBuf,
    pub max_bytes: u64,
    pub backups: u32,
}

impl RotatingLog {
    pub fn new(path: PathBuf) -> Self {
        Self { path, max_bytes: MAX_BYTES, backups: BACKUPS }
    }

    /// Append one formatted event (without its newline).
    pub fn write(&self, line: &str) -> std::io::Result<()> {
        let text = format!("{line}\n").replace('\n', NEWLINE);
        let pos = std::fs::metadata(&self.path).map(|meta| meta.len()).unwrap_or(0);
        // Python compares the bytes so far with the line's length in characters, newline as one.
        let length = line.chars().count() as u64 + 1;
        if self.max_bytes > 0 && pos > 0 && pos + length >= self.max_bytes && self.path.is_file() {
            self.roll()?;
        }
        std::fs::OpenOptions::new().create(true).append(true).open(&self.path)?.write_all(text.as_bytes())
    }

    fn numbered(&self, at: u32) -> PathBuf {
        let mut name = self.path.clone().into_os_string();
        name.push(format!(".{at}"));
        name.into()
    }

    fn roll(&self) -> std::io::Result<()> {
        if self.backups == 0 {
            return Ok(());
        }
        for at in (1..self.backups).rev() {
            let (from, to) = (self.numbered(at), self.numbered(at + 1));
            if from.exists() {
                if to.exists() {
                    std::fs::remove_file(&to)?;
                }
                std::fs::rename(&from, &to)?;
            }
        }
        let first = self.numbered(1);
        if first.exists() {
            std::fs::remove_file(&first)?;
        }
        std::fs::rename(&self.path, &first)
    }
}

/// Keep only the end of a file that only grows, from a whole line on (crash.log past CRASH_MAX).
pub fn trim(path: &Path, limit: u64, keep: usize) {
    let Ok(meta) = std::fs::metadata(path) else { return };
    if !meta.is_file() || meta.len() <= limit {
        return;
    }
    let Ok(data) = std::fs::read(path) else { return };
    let tail = &data[data.len().saturating_sub(keep)..];
    let tail = tail.iter().position(|byte| *byte == b'\n').map_or(tail, |at| &tail[at + 1..]);
    let _ = std::fs::write(path, [b"(older lines removed)\n".as_slice(), tail].concat());
}

/// Note that the app is open. Returns whether the last run never said it was closing.
pub fn mark_running(root: &Path) -> bool {
    let marker = log_dir(root).join(RUNNING);
    let unclean = marker.exists();
    let _ = std::fs::create_dir_all(log_dir(root));
    let _ = std::fs::write(&marker, "");
    unclean
}

pub fn mark_closed(root: &Path) {
    let _ = std::fs::remove_file(log_dir(root).join(RUNNING));
}
