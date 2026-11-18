//! check_frames of pipeline.py: find the lobby on one of the frames (where it was last time first), read its twelve
//! names, and mark them against the 黑名单 and the 嘉宾.

use std::time::Instant;

use lobby::{
    contains_title, find_anchor, game_screen, match_label, normalize_text, ready_in, ready_strip, split_ellipsis,
    strip_noise, with_game_ellipsis, Anchor, Entry, NameLabel, OcrLine, PxBox, Rect,
};
use opencv::core::Mat;
use opencv::prelude::*;
use ort::environment::Environment;

use crate::engine::Engine;
use crate::image::{downscale, name_crop, pixels, scale_lines, slice, to_bgr};
use crate::models::ModelDirs;
use crate::pixel::{snap_button_box, Pixels};
use crate::spot::{at_spot, remember, LobbySpot};
use crate::Result;

/// A read below this is 未看清 and is not matched.
pub const NAME_CONFIDENCE_MIN: f64 = 0.55;
pub(crate) const NO_LOBBY: &str = "没有找到「推演成功」大厅";
const NO_FRAME: &str = "截屏失败，再试一次";
const TAGS: [&str; 5] = ["炸房", "贴脸", "挂机", "场外", "不尊重底牌"];

/// One seat as read: its box in the frame, the raw read, what the lobby shows, and whether it was too unclear.
#[derive(Debug, Clone, PartialEq)]
pub struct NameSlot {
    pub index: usize,
    pub bbox: PxBox,
    pub raw: String,
    pub visible: String,
    pub truncated: bool,
    pub confidence: f64,
    pub unclear: bool,
}

/// A 黑名单 player found: the seat, what was read, the entry (its index in the list) and the warning line.
#[derive(Debug, Clone, PartialEq)]
pub struct Hit {
    pub index: usize,
    pub read_text: String,
    pub entry: usize,
    pub entry_name: String,
    pub note: String,
    pub truncated: bool,
    pub line: String,
    pub tags: Vec<String>,
}

/// Seconds each step took; `spot` when the lobby was where it was last time.
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct Timings {
    pub find: f64,
    pub read: f64,
    pub spot: bool,
}

/// What a seat is marked as: a 黑名单 or a 嘉宾 entry (its index in that list), or nothing.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Mark {
    Blacklist(usize),
    Guest(usize),
    None,
}

/// One of the twelve seats with its mark, for the overlay.
#[derive(Debug, Clone, PartialEq)]
pub struct Seat {
    pub index: usize,
    pub bbox: PxBox,
    pub name: String,
    pub unclear: bool,
    pub mark: Mark,
}

#[derive(Debug, Clone, PartialEq, Default)]
pub struct CheckResult {
    pub header_found: bool,
    pub message: String,
    pub countdown_seconds: Option<i64>,
    pub ready_count: Option<i64>,
    pub names: Vec<NameSlot>,
    pub hits: Vec<Hit>,
    /// 嘉宾 in the lobby, in seat order, each once, as (seat, entry index); a warned seat is no 嘉宾's.
    pub likes: Vec<(usize, usize)>,
    /// Which frame the lobby was on (the first when none had it).
    pub frame: Option<usize>,
    pub button_box: Option<PxBox>,
    /// The whole game screen as the lobby places it, in the same pixels.
    pub game_box: Option<Rect>,
    pub timings: Timings,
}

impl CheckResult {
    fn missing(message: &str) -> Self {
        Self { message: message.to_string(), ..Self::default() }
    }

    /// The twelve seats with their marks: a warning wins over a 嘉宾.
    pub fn seats(&self) -> Vec<Seat> {
        self.names
            .iter()
            .map(|slot| {
                let warned = self.hits.iter().find(|hit| hit.index == slot.index).map(|hit| Mark::Blacklist(hit.entry));
                let liked = self.likes.iter().find(|like| like.0 == slot.index).map(|like| Mark::Guest(like.1));
                let mark = warned.or(liked).unwrap_or(Mark::None);
                Seat { index: slot.index, bbox: slot.bbox, name: slot.visible.clone(), unclear: slot.unclear, mark }
            })
            .collect()
    }
}

/// storage.describe_entry: tags (built-in first), then the written reason.
pub fn describe_entry(entry: &Entry) -> String {
    let mut tags: Vec<&str> = TAGS.iter().copied().filter(|tag| entry.tags.iter().any(|t| t == tag)).collect();
    for tag in &entry.tags {
        if !tags.contains(&tag.as_str()) {
            tags.push(tag);
        }
    }
    let (tags, reason) = (tags.join("、"), entry.reason.trim());
    match (tags.is_empty(), reason.is_empty()) {
        (false, false) => format!("{tags}。原因：{reason}"),
        (true, false) => format!("原因：{reason}"),
        _ => tags,
    }
}

/// The reader and where the last lobby was.
pub struct Checker {
    pub engine: Engine,
    pub spot: Option<LobbySpot>,
}

fn offset(lines: Vec<OcrLine>, x0: i64, y0: i64) -> impl Iterator<Item = OcrLine> {
    let (dx, dy) = (x0 as f64, y0 as f64);
    lines.into_iter().map(move |l| OcrLine::new(l.text, l.confidence, [l.bbox[0] + dx, l.bbox[1] + dy, l.bbox[2] + dx, l.bbox[3] + dy]))
}

fn size(rgb: &Mat) -> (i64, i64) {
    (i64::from(rgb.cols()), i64::from(rgb.rows()))
}

impl Checker {
    /// The models in `dirs` on ONNX Runtime (see `crate::runtime`), detection on `threads` threads.
    pub fn new(env: &Environment, dirs: &ModelDirs, threads: usize) -> Result<Self> {
        Ok(Self { engine: Engine::new(env, dirs, threads)?, spot: None })
    }

    /// check_frames with the 嘉宾 matched as the app does (_likes_in). `on_lobby` hears the button's box as soon as
    /// the lobby is found, before the names are read.
    pub fn check(&mut self, frames: &[Mat], blacklist: &[Entry], likes: &[Entry], on_lobby: Option<&mut dyn FnMut(PxBox)>) -> Result<CheckResult> {
        if frames.is_empty() {
            return Ok(CheckResult::missing(NO_FRAME));
        }
        let started = Instant::now();
        let mut chosen: Option<(usize, Anchor, bool)> = None;
        if let Some(spot) = self.spot.clone() {
            for (i, frame) in frames.iter().enumerate() {
                if (frame.rows(), frame.cols()) != spot.size {
                    continue;
                }
                let anchor = at_spot(&mut self.engine, frame, &spot)?;
                if anchor.found {
                    chosen = Some((i, anchor, true));
                    break;
                }
            }
        }
        let mut last_reason = NO_LOBBY.to_string();
        if chosen.is_none() {
            for (i, frame) in frames.iter().enumerate() {
                let (anchor, lines) = self.locate(frame)?;
                if anchor.found {
                    self.spot = remember(frame, &anchor, &lines)?;
                    chosen = Some((i, anchor, false));
                    break;
                }
                if !anchor.reason.is_empty() {
                    last_reason = anchor.reason.clone();
                }
            }
        }
        let Some((index, anchor, spotted)) = chosen else {
            let mut result = CheckResult::missing(&last_reason);
            result.frame = Some(0);
            result.timings.find = started.elapsed().as_secs_f64();
            return Ok(result);
        };
        let frame = &frames[index];
        let data = pixels(frame)?;
        let px = Pixels { data: &data, width: frame.cols() as usize, height: frame.rows() as usize };
        let button = snap_button_box(&px, anchor.button_box);
        let found = Instant::now();
        if let (Some(callback), Some(button)) = (on_lobby, button) {
            callback(button);
        }
        let mut result = self.read_names(frame, &anchor, blacklist, likes)?;
        result.frame = Some(index);
        result.button_box = button;
        result.game_box = game_screen(&anchor);
        result.timings = Timings { find: (found - started).as_secs_f64(), read: found.elapsed().as_secs_f64(), spot: spotted };
        Ok(result)
    }

    /// _locate: the title and the few lines under it first, every line on the screen when that does not find it.
    pub fn locate(&mut self, rgb: &Mat) -> Result<(Anchor, Vec<OcrLine>)> {
        let (small, factor) = downscale(rgb, 1280)?;
        let bgr = to_bgr(&small)?;
        let (width, height) = size(rgb);
        let lines = scale_lines(self.engine.read_lobby_lines(&bgr)?, factor);
        let anchor = find_anchor(&lines, width, height);
        if anchor.found {
            return self.with_ready(rgb, anchor, lines);
        }
        if factor > 1.0 && contains_title(&lines) {
            let sharp = self.under_title(rgb, lines)?;
            let anchor = find_anchor(&sharp, width, height);
            if anchor.found {
                return self.with_ready(rgb, anchor, sharp);
            }
        }
        let lines = scale_lines(self.engine.read_bgr(&bgr)?, factor);
        let anchor = find_anchor(&lines, width, height);
        self.with_ready(rgb, anchor, lines)
    }

    /// _with_ready: a lobby found without 准备就绪 among its lines, read again with it from the full copy.
    fn with_ready(&mut self, rgb: &Mat, anchor: Anchor, lines: Vec<OcrLine>) -> Result<(Anchor, Vec<OcrLine>)> {
        let Some(strip) = ready_strip(&anchor) else { return Ok((anchor, lines)) };
        if lines.iter().any(|line| ready_in(&line.text).is_some()) {
            return Ok((anchor, lines));
        }
        let (width, height) = size(rgb);
        let (x0, y0) = ((strip[0] as i64).max(0), (strip[1] as i64).max(0));
        let (x1, y1) = ((strip[2] as i64).min(width), (strip[3] as i64).min(height));
        if x1 - x0 < 8 || y1 - y0 < 8 {
            return Ok((anchor, lines));
        }
        let found = self.engine.read_bgr(&to_bgr(&slice(rgb, x0, y0, x1, y1)?)?)?;
        let ready: Vec<OcrLine> = offset(found, x0, y0).filter(|line| ready_in(&line.text).is_some()).collect();
        if ready.is_empty() {
            return Ok((anchor, lines));
        }
        let lines: Vec<OcrLine> = lines.into_iter().chain(ready).collect();
        let sized = find_anchor(&lines, width, height);
        Ok(if sized.found { (sized, lines) } else { (anchor, lines) })
    }

    /// _under_title: the lines around 推演成功, read from the full-size copy.
    fn under_title(&mut self, rgb: &Mat, lines: Vec<OcrLine>) -> Result<Vec<OcrLine>> {
        let Some(title) = lines.iter().find(|line| line.text.replace(' ', "").contains("推演成功")) else { return Ok(lines) };
        let [left, top, right, bottom] = title.bbox;
        let (title_w, title_h, middle) = (right - left, bottom - top, (left + right) / 2.0);
        let (width, height) = size(rgb);
        let x0 = ((middle - 1.4 * title_w) as i64).max(0);
        let x1 = ((middle + 1.4 * title_w) as i64).min(width);
        let y0 = ((top - 0.4 * title_h) as i64).max(0);
        let y1 = ((top + 7.6 * title_h) as i64).min(height);
        if x1 - x0 < 8 || y1 - y0 < 8 {
            return Ok(lines);
        }
        let found = self.engine.read_bgr(&to_bgr(&slice(rgb, x0, y0, x1, y1)?)?)?;
        Ok(offset(found, x0, y0).collect())
    }

    /// _read_names, then the 嘉宾 as the app finds them (ui._likes_in).
    fn read_names(&mut self, rgb: &Mat, anchor: &Anchor, blacklist: &[Entry], likes: &[Entry]) -> Result<CheckResult> {
        let crops = anchor.name_boxes.iter().map(|b| name_crop(rgb, b, anchor.scale)).collect::<Result<Vec<_>>>()?;
        let readings = self.engine.read_names(&crops)?;
        let mut result = CheckResult {
            header_found: true,
            countdown_seconds: anchor.countdown_seconds,
            ready_count: anchor.ready_count,
            button_box: anchor.button_box,
            ..CheckResult::default()
        };
        for (index, (raw, confidence)) in readings.into_iter().enumerate() {
            let (visible, truncated) = split_ellipsis(&raw);
            let mut visible = strip_noise(&visible);
            let unclear = confidence < NAME_CONFIDENCE_MIN || visible.is_empty();
            if !unclear {
                visible = with_game_ellipsis(&visible, truncated);
            }
            let slot = NameSlot {
                index,
                bbox: anchor.name_boxes[index],
                raw: raw.clone(),
                visible: if unclear { String::new() } else { visible.clone() },
                truncated: truncated && !unclear,
                confidence,
                unclear,
            };
            result.names.push(slot);
        }
        (result.hits, result.likes) = mark_names(&result.names, blacklist, likes);
        result.message = message(anchor, &result);
        Ok(result)
    }
}

/// The warnings of _read_names and the 嘉宾 of ui._likes_in for seats already read.
pub fn mark_names(names: &[NameSlot], blacklist: &[Entry], likes: &[Entry]) -> (Vec<Hit>, Vec<(usize, usize)>) {
    let mut hits = Vec::new();
    for slot in names {
        let label = NameLabel { raw: normalize_text(&slot.raw), visible: slot.visible.clone(), truncated: slot.truncated, unclear: slot.unclear };
        // shown: what was read, the ellipsis restored, even when too unclear to keep.
        let shown = if slot.visible.is_empty() { shown_read(&slot.raw) } else { slot.visible.clone() };
        for found in match_label(&label, blacklist) {
            let entry = &blacklist[found.index];
            let note = describe_entry(entry);
            hits.push(Hit {
                index: slot.index,
                read_text: shown.clone(),
                entry: found.index,
                entry_name: entry.name.clone(),
                line: lobby::format_hit(&shown, &entry.name, &note),
                note,
                truncated: slot.truncated,
                tags: entry.tags.clone(),
            });
        }
    }
    let likes = likes_in(names, &hits, likes);
    (hits, likes)
}

/// The visible part of a read, as _read_names keeps it for a seat too unclear to show.
fn shown_read(raw: &str) -> String {
    strip_noise(&split_ellipsis(raw).0)
}

/// ui._likes_in: 嘉宾 in the lobby, in seat order, each once; a 黑名单 player's seat is no 嘉宾's.
pub fn likes_in(names: &[NameSlot], hits: &[Hit], likes: &[Entry]) -> Vec<(usize, usize)> {
    let mut found: Vec<(usize, usize)> = Vec::new();
    for slot in names.iter().filter(|slot| hits.iter().all(|hit| hit.index != slot.index)) {
        let label = NameLabel { raw: slot.raw.clone(), visible: slot.visible.clone(), truncated: slot.truncated, unclear: slot.unclear };
        for matched in match_label(&label, likes) {
            if found.iter().all(|seen| seen.1 != matched.index) {
                found.push((slot.index, matched.index));
            }
        }
    }
    found
}

fn message(anchor: &Anchor, result: &CheckResult) -> String {
    let mut parts: Vec<String> = Vec::new();
    if let Some(seconds) = anchor.countdown_seconds {
        parts.push(format!("倒计时 {seconds} 秒"));
    }
    if let Some(ready) = anchor.ready_count {
        parts.push(format!("准备就绪 {ready}/12"));
    }
    parts.push(if result.hits.is_empty() { "未发现黑名单玩家".to_string() } else { format!("发现 {} 名黑名单玩家", result.hits.len()) });
    let unclear = result.names.iter().filter(|slot| slot.unclear).count();
    if unclear > 0 {
        parts.push(format!("{unclear} 人未识别"));
    }
    format!("检查完成：{}。", parts.join("，"))
}
