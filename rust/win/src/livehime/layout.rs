//! Where 直播姬 puts each window capture on its canvas, and what its log says of the canvas (livehime_layout.py).
//!
//! 直播姬 is built on OBS. Its scene collection (%LOCALAPPDATA%\bililive\User Data\<account>\Scene
//! Collection\*.json) keeps every scene's sources with OBS's pos, scale, crop and bounds, and for a 窗口捕获 the
//! window it is set to and whether it takes only the client area. Its log says the canvas size, whether 横竖双屏
//! is on, when the two-canvas mode (预览 and 直播 apart) turns on or off, when 同步至直播 is pressed, and when a
//! source is added to or removed from a scene.

#![forbid(unsafe_code)]

use std::collections::HashMap;
use std::fs::File;
use std::io::{Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};

use serde_json::{Map, Value};

use super::{py_str, window_parts};

/// OBS's alignment bits (align, bounds_align); neither left nor right is the middle, and so on.
pub const LEFT: i64 = 1;
pub const RIGHT: i64 = 2;
pub const TOP: i64 = 4;
pub const BOTTOM: i64 = 8;
/// OBS's bounds types.
pub const NO_BOUNDS: i64 = 0;
pub const STRETCH: i64 = 1;
pub const INNER: i64 = 2;
pub const OUTER: i64 = 3;
pub const TO_WIDTH: i64 = 4;
pub const TO_HEIGHT: i64 = 5;
pub const MAX_ONLY: i64 = 6;
/// How far back the log is read for the canvas and the two-canvas mode.
pub const REACH: u64 = 8 * 1024 * 1024;

/// One 窗口捕获 in one scene: the window it is set to, how it captures, and where it sits.
#[derive(Clone, Debug, PartialEq)]
pub struct Placement {
    pub scene: String,
    pub name: String,
    pub title: String,
    pub window_class: String,
    pub exe: String,
    pub client_area: bool,
    /// 窗口区域模式: the screen where the window is, not the window.
    pub whole_screen: bool,
    pub visible: bool,
    pub pos: (f64, f64),
    pub scale: (f64, f64),
    /// left, top, right, bottom
    pub crop: (i64, i64, i64, i64),
    pub bounds_type: i64,
    pub bounds: (f64, f64),
    pub bounds_align: i64,
    pub align: i64,
    pub rotation: f64,
}

impl Placement {
    /// (x, y, w, h) on the canvas of a captured frame `width` by `height` pixels, as OBS draws it.
    pub fn on_canvas(&self, width: f64, height: f64) -> (f64, f64, f64, f64) {
        let (left, top, right, bottom) = self.crop;
        let w = (width - left as f64 - right as f64).max(1.0);
        let h = (height - top as f64 - bottom as f64).max(1.0);
        if self.bounds_type == NO_BOUNDS {
            let (sw, sh) = (w * self.scale.0, h * self.scale.1);
            return (anchor(self.pos.0, sw, self.align), anchor(self.pos.1, sh, self.align >> 2), sw, sh);
        }
        let (bx, by) = self.bounds;
        let (kx, ky) = match self.bounds_type {
            STRETCH => (bx / w, by / h),
            INNER => ((bx / w).min(by / h), (bx / w).min(by / h)),
            OUTER => ((bx / w).max(by / h), (bx / w).max(by / h)),
            TO_WIDTH => (bx / w, bx / w),
            TO_HEIGHT => (by / h, by / h),
            MAX_ONLY => {
                let k = py_min(1.0, py_min(bx / w, by / h));
                (k, k)
            }
            _ => (1.0, 1.0),
        };
        let (sw, sh) = (w * kx, h * ky);
        let (box_x, box_y) = (anchor(self.pos.0, bx, self.align), anchor(self.pos.1, by, self.align >> 2));
        (box_x + inside(bx - sw, self.bounds_align), box_y + inside(by - sh, self.bounds_align >> 2), sw, sh)
    }
}

/// Python's min(a, b): the first unless the second is smaller.
fn py_min(a: f64, b: f64) -> f64 {
    if b < a {
        b
    } else {
        a
    }
}

/// Where a span starts, given the point it is aligned by (bits: LEFT and RIGHT, shifted for TOP and BOTTOM).
fn anchor(at: f64, size: f64, bits: i64) -> f64 {
    if bits & LEFT != 0 {
        at
    } else if bits & RIGHT != 0 {
        at - size
    } else {
        at - size / 2.0
    }
}

fn inside(room: f64, bits: i64) -> f64 {
    if bits & LEFT != 0 {
        0.0
    } else if bits & RIGHT != 0 {
        room
    } else {
        room / 2.0
    }
}

/// The scene collection 直播姬 last wrote: the newest one of any account, under `root` (or
/// %LOCALAPPDATA%\bililive\User Data).
pub fn collection_path(root: Option<&Path>) -> Option<PathBuf> {
    let base = match root {
        Some(root) => root.to_path_buf(),
        None => PathBuf::from(std::env::var_os("LOCALAPPDATA").unwrap_or_default()).join("bililive").join("User Data"),
    };
    let mut found: Vec<(std::time::SystemTime, PathBuf)> = Vec::new();
    for account in std::fs::read_dir(base).ok()?.flatten() {
        let Ok(files) = std::fs::read_dir(account.path().join("Scene Collection")) else { continue };
        for file in files.flatten() {
            let path = file.path();
            let json = path.extension().is_some_and(|ext| ext == "json");
            if let (true, Ok(meta)) = (json, file.metadata()) {
                if meta.is_file() {
                    found.push((meta.modified().unwrap_or(std::time::UNIX_EPOCH), path));
                }
            }
        }
    }
    found.into_iter().max_by_key(|(when, _)| *when).map(|(_, path)| path)
}

fn number(value: Option<&Value>, default: f64) -> f64 {
    match value {
        None => default,
        Some(Value::Bool(on)) => f64::from(u8::from(*on)),
        Some(value) => value.as_f64().unwrap_or(default),
    }
}

/// Python's `int(x or 0)` on a JSON value (floats are cut toward zero).
fn integer(value: Option<&Value>, default: i64) -> i64 {
    match value {
        None => default,
        Some(Value::Bool(on)) => i64::from(*on),
        Some(value) => value.as_i64().or_else(|| value.as_f64().map(|v| v.trunc() as i64)).unwrap_or(0),
    }
}

fn pair(item: &Map<String, Value>, key: &str, default: f64) -> (f64, f64) {
    let empty = Map::new();
    let pair = item.get(key).and_then(Value::as_object).unwrap_or(&empty);
    (number(pair.get("x"), default), number(pair.get("y"), default))
}

/// A dictionary key as Python sees `source.get("uuid")`: None for missing or null.
fn key(value: Option<&Value>) -> Option<String> {
    match value {
        None | Some(Value::Null) => None,
        Some(other) => Some(other.to_string()),
    }
}

/// The scene 直播姬 shows, and every 窗口捕获 in every scene, each scene's bottom to top.
pub fn placements(text: &str) -> Result<(String, Vec<Placement>), serde_json::Error> {
    let data: Value = serde_json::from_str(text)?;
    let empty = Map::new();
    let sources: Vec<&Map<String, Value>> =
        data.get("sources").and_then(Value::as_array).into_iter().flatten().filter_map(Value::as_object).collect();
    let by_uuid: HashMap<Option<String>, &Map<String, Value>> = sources.iter().map(|s| (key(s.get("uuid")), *s)).collect();
    let by_name: HashMap<Option<String>, &Map<String, Value>> = sources.iter().map(|s| (key(s.get("name")), *s)).collect();
    let mut out = Vec::new();
    for scene in &sources {
        if scene.get("id").and_then(Value::as_str) != Some("scene") {
            continue;
        }
        let settings = scene.get("settings").and_then(Value::as_object).unwrap_or(&empty);
        for item in settings.get("items").and_then(Value::as_array).into_iter().flatten().filter_map(Value::as_object) {
            let found = by_uuid.get(&key(item.get("source_uuid"))).filter(|s| !s.is_empty());
            let source = found.or_else(|| by_name.get(&key(item.get("name"))).filter(|s| !s.is_empty())).copied().unwrap_or(&empty);
            if source.get("id").and_then(Value::as_str) != Some("window_capture") {
                continue;
            }
            let settings = source.get("settings").and_then(Value::as_object).unwrap_or(&empty);
            let (title, window_class, exe) = window_parts(&py_str(settings.get("window"), ""));
            let crop = |side: &str| integer(item.get(&format!("crop_{side}")), 0);
            out.push(Placement {
                scene: py_str(scene.get("name"), ""),
                name: py_str(item.get("name"), ""),
                title,
                window_class,
                exe,
                client_area: settings.get("client_area") != Some(&Value::Bool(false)),
                whole_screen: settings.get("capture_from_whole_screen") == Some(&Value::Bool(true)),
                visible: item.get("visible") != Some(&Value::Bool(false)),
                pos: pair(item, "pos", 0.0),
                scale: pair(item, "scale", 1.0),
                crop: (crop("left"), crop("top"), crop("right"), crop("bottom")),
                bounds_type: integer(item.get("bounds_type"), 0),
                bounds: pair(item, "bounds", 0.0),
                bounds_align: integer(item.get("bounds_align"), 0),
                align: integer(item.get("align"), LEFT | TOP),
                rotation: number(item.get("rot").filter(|v| !v.is_null()), 0.0),
            });
        }
    }
    Ok((py_str(data.get("current_scene"), ""), out))
}

/// What 直播姬's log says of its canvas and its two-canvas mode; None where it says nothing.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Studio {
    pub canvas: Option<(i64, i64)>,
    pub double_screen: Option<bool>,
    pub two_canvas: Option<bool>,
    /// When 同步至直播 was last pressed, and a source last added to or removed from a scene, as "MMDD HHMMSS";
    /// "" when not seen.
    pub synced: String,
    pub edited: String,
}

impl Studio {
    /// In the two-canvas mode, a source changed since 同步至直播: viewers do not see it yet.
    pub fn unsynced(&self) -> bool {
        self.two_canvas == Some(true) && !self.edited.is_empty() && self.edited > self.synced
    }
}

pub use super::log_lines::{read_log, splitlines, stamp};

/// The canvas and the two-canvas mode, from the end of 直播姬's log, back to its last start.
pub fn studio(path: &Path, reach: u64) -> Studio {
    StudioWatch::new(Some(path.to_path_buf()), reach).studio()
}

/// [`studio`], kept up to date by reading only what 直播姬 added to its log since the last look.
#[derive(Debug)]
pub struct StudioWatch {
    pub path: Option<PathBuf>,
    pub reach: u64,
    size: i64,
    found: Studio,
}

impl StudioWatch {
    pub fn new(path: Option<PathBuf>, reach: u64) -> StudioWatch {
        StudioWatch { path, reach, size: -1, found: Studio::default() }
    }

    pub fn studio(&mut self) -> Studio {
        let path = self.path.clone().unwrap_or_else(super::log_path);
        if self.look(&path).is_err() {
            self.size = -1;
            self.found = Studio::default();
        }
        self.found.clone()
    }

    fn look(&mut self, path: &Path) -> std::io::Result<()> {
        let size = std::fs::metadata(path)?.len() as i64;
        if size == self.size {
            return Ok(());
        }
        let mut log = File::open(path)?;
        let start = if self.size < 0 || size < self.size {
            self.found = Studio::default();
            (size - self.reach as i64).max(0)
        } else {
            self.size
        };
        log.seek(SeekFrom::Start(start as u64))?;
        let mut data = Vec::new();
        log.by_ref().take((size - start) as u64).read_to_end(&mut data)?;
        // A line still being written waits for the next look.
        let whole = data.iter().rposition(|&b| b == b'\n').map_or(0, |at| at + 1);
        self.found = read_log(std::mem::take(&mut self.found), &String::from_utf8_lossy(&data[..whole]));
        self.size = start + whole as i64;
        Ok(())
    }
}
