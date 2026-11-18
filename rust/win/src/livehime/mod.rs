//! 哔哩哔哩直播姬 and 直播模式 (livehime.py): is 直播画面 in the stream? Read from 直播姬's own log, nothing else.
//!
//! 直播姬 (v8.2) writes `game_and_widnow_info : [...]` to its log (bililive_debug.log) when it starts, on a
//! scene switch and when a source is added: the current scene's window and game captures, bottom to top, each
//! with "process_info" ("title:class:exe") and "is_visible". The last one since 直播姬 last started is what its
//! stream shows. The log grows by megabytes and is never cut, so it is read from the end, then only what was
//! added since.
//!
//! The parts here are platform-free; [`windows`] finds the windows themselves (Windows only), [`layout`] is
//! where 直播姬 puts each capture on its canvas, [`follow`] where 直播画面 draws the game, and [`mask`] what 直播模式
//! hides from viewers.

pub mod follow;
pub mod layout;
mod log_lines;
pub mod mask;
#[cfg(windows)]
pub mod windows;

use std::fs::File;
use std::io::{Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};

use serde_json::Value;

/// 直播姬's program, for `process::running`.
pub const PROCESS: &str = "livehime.exe";
pub const SCENE: &[u8] = b"game_and_widnow_info :";
pub const START: &[u8] = b"--- Application Startup ---";
/// Read back a block at a time, this far at most, for the last scene line.
pub const BLOCK: u64 = 256 * 1024;
pub const REACH: u64 = 16 * 1024 * 1024;

/// What the header panel says beside 直播模式.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Status {
    /// The current scene shows 直播画面, nothing of the game's over it.
    Ok,
    /// The current scene has no capture of 直播画面.
    Missing,
    /// It is there, hidden (the eye in 直播姬's list).
    Hidden,
    /// The game's capture is over it, so the marks are under the game.
    Behind,
    /// 直播姬 is not running.
    Closed,
}

impl Status {
    /// The key the Python app uses ("ok", "missing", ...).
    pub fn key(self) -> &'static str {
        match self {
            Status::Ok => "ok",
            Status::Missing => "missing",
            Status::Hidden => "hidden",
            Status::Behind => "behind",
            Status::Closed => "closed",
        }
    }

    /// The words on the panel, as livehime.WORDS has them.
    pub fn words(self) -> &'static str {
        match self {
            Status::Ok => "✓ 已连上直播姬",
            Status::Missing => "直播姬场景里还没有「直播画面」",
            Status::Hidden => "「直播画面」被隐藏了，显示后切换一次直播姬场景",
            Status::Behind => "「直播画面」被游戏挡住了，置顶后切换一次直播姬场景",
            Status::Closed => "直播姬没有打开",
        }
    }

    /// The panel's tone: green for OK, a warning otherwise.
    pub fn is_ok(self) -> bool {
        self == Status::Ok
    }

    pub const ALL: [Status; 5] = [Status::Ok, Status::Missing, Status::Hidden, Status::Behind, Status::Closed];
}

/// %LOCALAPPDATA%\bililive\User Data\bililive_debug.log
pub fn log_path() -> PathBuf {
    PathBuf::from(std::env::var_os("LOCALAPPDATA").unwrap_or_default()).join("bililive").join("User Data").join("bililive_debug.log")
}

/// One window capture in the scene: the window it is set to, and whether it shows.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Capture {
    pub title: String,
    pub window_class: String,
    pub exe: String,
    pub visible: bool,
}

/// OBS keeps ":" and "#" inside a field as #3A and #22.
pub fn unescape(part: &str) -> String {
    part.replace("#3A", ":").replace("#22", "#")
}

/// "title:class:exe" split as Python's `[*map(_unescape, parts), "", ""][:3]`.
pub fn window_parts(text: &str) -> (String, String, String) {
    let mut parts = text.split(':').map(unescape).chain(std::iter::repeat(String::new()));
    let title = parts.next().unwrap_or_default();
    let class = parts.next().unwrap_or_default();
    (title, class, parts.next().unwrap_or_default())
}

/// Python's str() of a JSON value, for the few fields read as text.
pub(crate) fn py_str(value: Option<&Value>, missing: &str) -> String {
    match value {
        None => missing.to_string(),
        Some(Value::String(text)) => text.clone(),
        Some(Value::Null) => "None".to_string(),
        Some(Value::Bool(on)) => if *on { "True" } else { "False" }.to_string(),
        Some(other) => other.to_string(),
    }
}

/// The captures in one game_and_widnow_info line, bottom to top; None when it is not one.
pub fn parse_scene(line: &str) -> Option<Vec<Capture>> {
    let marker = std::str::from_utf8(SCENE).ok()?;
    let at = line.find(marker)?;
    let items: Value = serde_json::from_str(line[at + marker.len()..].trim()).ok()?;
    let items = items.as_array()?;
    let captures = items
        .iter()
        .filter_map(Value::as_object)
        .map(|item| {
            let (title, window_class, exe) = window_parts(&py_str(item.get("process_info"), ""));
            Capture { title, window_class, exe, visible: item.get("is_visible") != Some(&Value::Bool(false)) }
        })
        .collect();
    Some(captures)
}

/// The current scene as 直播姬 last logged it, kept up to date by reading only what was added to the log
/// since the last look. None: no log, or nothing logged since 直播姬 last started.
#[derive(Debug)]
pub struct SceneWatch {
    path: Option<PathBuf>,
    size: i64,
    scene: Option<Vec<Capture>>,
}

impl SceneWatch {
    /// A watch on `path`, or on [`log_path`] when None.
    pub fn new(path: Option<PathBuf>) -> SceneWatch {
        SceneWatch { path, size: -1, scene: None }
    }

    pub fn scene(&mut self) -> Option<Vec<Capture>> {
        let path = self.path.clone().unwrap_or_else(log_path);
        if self.look(&path).is_err() {
            self.size = -1;
            self.scene = None;
        }
        self.scene.clone()
    }

    fn look(&mut self, path: &Path) -> std::io::Result<()> {
        let size = std::fs::metadata(path)?.len() as i64;
        if size == self.size {
            return Ok(());
        }
        let mut log = File::open(path)?;
        if self.size < 0 || size < self.size {
            let (scene, end) = from_end(&mut log, size as u64)?;
            self.scene = scene;
            self.size = end as i64;
            return Ok(());
        }
        log.seek(SeekFrom::Start(self.size as u64))?;
        let mut data = Vec::new();
        log.by_ref().take((size - self.size) as u64).read_to_end(&mut data)?;
        // A line still being written waits for the next look.
        let whole = data.iter().rposition(|&b| b == b'\n').map_or(0, |at| at + 1);
        for line in data[..whole].split(|&b| b == b'\n') {
            if contains(line, START) {
                self.scene = None;
            } else if contains(line, SCENE) {
                self.scene = parse_scene(&String::from_utf8_lossy(line));
            }
        }
        self.size += whole as i64;
        Ok(())
    }
}

pub(crate) fn contains(haystack: &[u8], needle: &[u8]) -> bool {
    haystack.windows(needle.len()).any(|window| window == needle)
}

fn read_at(log: &mut File, start: u64, len: u64) -> std::io::Result<Vec<u8>> {
    log.seek(SeekFrom::Start(start))?;
    let mut data = Vec::new();
    log.by_ref().take(len).read_to_end(&mut data)?;
    Ok(data)
}

/// The last scene line, looking back from the end; and where the whole lines end.
fn from_end(log: &mut File, size: u64) -> std::io::Result<(Option<Vec<Capture>>, u64)> {
    let last = read_at(log, size.saturating_sub(BLOCK), u64::MAX)?;
    let cut = last.iter().rposition(|&b| b == b'\n').map_or(0, |at| at + 1) as u64;
    let end = size - last.len() as u64 + cut;
    let (mut pos, mut carry) = (end, Vec::new());
    while pos > 0 && end - pos < REACH {
        let start = pos.saturating_sub(BLOCK);
        let mut chunk = read_at(log, start, pos - start)?;
        chunk.extend_from_slice(&carry);
        let mut lines: Vec<&[u8]> = chunk.split(|&b| b == b'\n').collect();
        let first = lines.remove(0);
        carry = if start > 0 { first.to_vec() } else { Vec::new() };
        if start == 0 {
            lines.insert(0, first);
        }
        for line in lines.iter().rev() {
            if contains(line, START) {
                return Ok((None, end));
            }
            if contains(line, SCENE) {
                return Ok((parse_scene(&String::from_utf8_lossy(line)), end));
            }
        }
        pos = start;
    }
    Ok((None, end))
}

/// Ok, Missing, Hidden, Behind or Closed for the window titled `title`; None when not known yet. `covers` says
/// whether a capture is of the game's window; without it, the order is not judged.
pub fn status(title: &str, running: bool, scene: Option<&[Capture]>, covers: Option<&dyn Fn(&Capture) -> bool>) -> Option<Status> {
    if !running {
        return Some(Status::Closed);
    }
    let scene = scene?;
    let ours: Vec<usize> = (0..scene.len()).filter(|&i| scene[i].title == title).collect();
    if ours.is_empty() {
        return Some(Status::Missing);
    }
    let Some(&top) = ours.iter().filter(|&&i| scene[i].visible).max() else {
        return Some(Status::Hidden);
    };
    if let Some(covers) = covers {
        if scene[top + 1..].iter().any(|c| c.visible && c.title != title && covers(c)) {
            return Some(Status::Behind);
        }
    }
    Some(Status::Ok)
}

/// The capture the stream shows the game with: the top visible window capture under the one of 直播画面
/// (titled `title`), or the top visible one when the scene has no 直播画面.
pub fn game_capture<'a>(scene: Option<&'a [Capture]>, title: &str) -> Option<&'a Capture> {
    let scene = scene.filter(|scene| !scene.is_empty())?;
    let under = match scene.iter().position(|c| c.title == title) {
        Some(first) => &scene[..first],
        None => scene,
    };
    under.iter().rev().find(|c| c.visible && !c.title.is_empty() && c.title != title)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cap(title: &str, visible: bool) -> Capture {
        Capture { title: title.into(), window_class: String::new(), exe: String::new(), visible }
    }

    #[test]
    fn status_reads_the_scene_bottom_to_top() {
        let ours = "模仿者小工具·直播画面";
        assert_eq!(status(ours, false, None, None), Some(Status::Closed));
        assert_eq!(status(ours, true, None, None), None);
        assert_eq!(status(ours, true, Some(&[cap("心动小鹿的游戏", true)]), None), Some(Status::Missing));
        assert_eq!(status(ours, true, Some(&[cap(ours, false)]), None), Some(Status::Hidden));
        let scene = [cap(ours, true), cap("心动小鹿的游戏", true)];
        let covers = |c: &Capture| c.title == "心动小鹿的游戏";
        assert_eq!(status(ours, true, Some(&scene), Some(&covers)), Some(Status::Behind));
        assert_eq!(status(ours, true, Some(&scene), None), Some(Status::Ok));
        assert_eq!(game_capture(Some(&scene), ours), None);
        assert_eq!(game_capture(Some(&scene[1..]), ours).map(|c| c.title.as_str()), Some("心动小鹿的游戏"));
    }

    #[test]
    fn a_window_field_unescapes_colons_and_hashes() {
        assert_eq!(window_parts("a#3Ab:cls"), ("a:b".into(), "cls".into(), String::new()));
        assert_eq!(parse_scene("x game_and_widnow_info : nope"), None);
        assert_eq!(parse_scene("game_and_widnow_info : [1, {\"is_visible\": false}]"), Some(vec![cap("", false)]));
    }
}
