//! Find the match-found header and place the twelve name strips from it: `find_anchor` and the boxes
//! of `blacklist_detect/layout.py`.

use std::sync::LazyLock;

use crate::header::{assemble_countdown, assemble_mode, center, norm, pick_tight, ready_search, x_overlap};
use crate::model::{OcrLine, Rect};
use crate::text::nfkc;

/// The reference shot is 3270×1695; the boxes are fractions of it (left, top, right, bottom).
pub const REF_W: f64 = 3270.0;
pub const REF_H: f64 = 1695.0;
pub const TITLE_BOX: Rect = [0.435, 0.074, 0.635, 0.187];
pub const MODE_BOX: Rect = [0.401, 0.199, 0.654, 0.247];
pub const COUNTDOWN_BOX: Rect = [0.466, 0.253, 0.604, 0.296];
/// 准备就绪's middle is this many reference px under the title's.
pub const REF_READY_DY: f64 = 1238.0;
/// How far the size measured to 准备就绪 may be from the countdown's.
pub const READY_GATE: f64 = 0.06;
/// The light 准备案件还原 control at the bottom of the reference shot.
pub const BUTTON_BOX: Rect = [0.458, 0.896, 0.614, 0.980];

const MEASURED_NAME_BOXES: [Rect; 12] = [
    [0.136, 0.487, 0.232, 0.527],
    [0.288, 0.489, 0.366, 0.526],
    [0.417, 0.483, 0.514, 0.528],
    [0.550, 0.486, 0.632, 0.528],
    [0.711, 0.486, 0.772, 0.530],
    [0.848, 0.487, 0.909, 0.528],
    [0.151, 0.777, 0.229, 0.817],
    [0.273, 0.774, 0.373, 0.819],
    [0.434, 0.774, 0.497, 0.818],
    [0.572, 0.773, 0.635, 0.815],
    [0.692, 0.777, 0.789, 0.816],
    [0.831, 0.776, 0.928, 0.816],
];

/// Python's `round(value, 4)`: the decimal nearest the exact binary value.
fn round4(value: f64) -> f64 {
    format!("{value:.4}").parse().unwrap_or(value)
}

/// Give every seat the same side margin, stopping before the next card.
fn widen_name_row(boxes: &[Rect]) -> Vec<Rect> {
    let (grow, gap) = (0.030, 0.012);
    let mid = |rect: &Rect| (rect[0] + rect[2]) / 2.0;
    let last = boxes.len() - 1;
    boxes
        .iter()
        .enumerate()
        .map(|(index, &[left, top, right, bottom])| {
            let middle = mid(&boxes[index]);
            let left_limit = if index == 0 { 0.0 } else { (mid(&boxes[index - 1]) + middle) / 2.0 };
            let right_limit = if index == last { 1.0 } else { (middle + mid(&boxes[index + 1])) / 2.0 };
            let left = (left - grow).max(left_limit + gap / 2.0);
            let right = (right + grow).min(right_limit - gap / 2.0);
            [round4(left), top, round4(right), bottom]
        })
        .collect()
}

/// The twelve name strips as fractions of the reference shot: top row left to right, then the bottom row.
pub static NAME_BOXES: LazyLock<Vec<Rect>> = LazyLock::new(|| {
    let mut boxes = widen_name_row(&MEASURED_NAME_BOXES[..6]);
    boxes.extend(widen_name_row(&MEASURED_NAME_BOXES[6..]));
    boxes
});

/// A box in whole pixels of the capture.
pub type PxBox = [i64; 4];

/// The lobby found (or why not), its countdown and ready count, its size against the reference, and where things are.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct Anchor {
    pub found: bool,
    pub reason: String,
    pub countdown_seconds: Option<i64>,
    pub ready_count: Option<i64>,
    pub scale: f64,
    pub name_boxes: Vec<PxBox>,
    pub button_box: Option<PxBox>,
    pub title_box: Option<Rect>,
    pub mode_box: Option<Rect>,
    pub countdown_box: Option<Rect>,
}

impl Anchor {
    fn missing(reason: &str, ready_count: Option<i64>) -> Self {
        Self { reason: reason.to_string(), ready_count, ..Self::default() }
    }
}

fn frac_to_px(rect: &Rect, width: f64, height: f64) -> Rect {
    [rect[0] * width, rect[1] * height, rect[2] * width, rect[3] * height]
}

fn ready_line(line: &OcrLine) -> Option<i64> {
    ready_search(&nfkc(&line.text))
}

/// The lobby's size from the title down to 准备就绪 when it is within READY_GATE of where the
/// countdown puts it (of two, the nearer); else the countdown's.
fn ready_scale(lines: &[OcrLine], title: &Rect, scale: f64) -> f64 {
    let (title_x, title_y) = center(title);
    let mut best: Option<(f64, f64)> = None;
    for line in lines.iter().filter(|line| ready_line(line).is_some()) {
        let (ready_x, ready_y) = center(&line.bbox);
        let sized = (ready_y - title_y) / REF_READY_DY;
        let off = (sized / scale - 1.0).abs();
        let near = (ready_x - title_x).abs() <= title[2] - title[0];
        if off <= READY_GATE && near && best.is_none_or(|(top, _)| off < top) {
            best = Some((off, sized));
        }
    }
    best.map_or(scale, |(_, sized)| sized)
}

/// Where 准备就绪 must be under the anchor's title.
pub fn ready_strip(anchor: &Anchor) -> Option<Rect> {
    let title = anchor.title_box.filter(|_| anchor.found)?;
    let [left, top, right, bottom] = title;
    let (middle, title_y) = center(&title);
    let reach = REF_READY_DY * anchor.scale;
    Some([
        middle - (right - left),
        title_y + (1.0 - READY_GATE) * reach - (bottom - top),
        middle + (right - left),
        title_y + (1.0 + READY_GATE) * reach + (bottom - top),
    ])
}

const NOT_FOUND: &str = "没找到「推演成功」大厅";
const NOT_WHOLE: &str = "没找到「推演成功」大厅，请用完整的大厅截图";

/// Require 推演成功, 模仿者狂欢（12人狂欢）, and 倒计时 <seconds> 秒, stacked in that order.
pub fn find_anchor(lines: &[OcrLine], image_width: i64, image_height: i64) -> Anchor {
    let titles: Vec<&OcrLine> = lines.iter().filter(|line| norm(&line.text).contains("推演成功")).collect();
    let title = pick_tight(&titles, "推演成功");
    let mode = assemble_mode(lines);
    let countdown = assemble_countdown(lines);
    let mut ready_count = None;
    let mut ready_y = 1e9;
    for line in lines {
        if let Some(count) = ready_line(line) {
            if line.bbox[1] < ready_y {
                ready_count = Some(count);
                ready_y = line.bbox[1];
            }
        }
    }
    let (Some(title), Some(mode), Some((countdown, seconds))) = (title, mode, countdown) else {
        return Anchor::missing(NOT_FOUND, ready_count);
    };
    let ref_title_c = center(&frac_to_px(&TITLE_BOX, REF_W, REF_H));
    let ref_dy = center(&frac_to_px(&COUNTDOWN_BOX, REF_W, REF_H)).1 - ref_title_c.1;
    let (title_c, mode_c, count_c) = (center(&title.bbox), center(&mode.bbox), center(&countdown.bbox));
    let stacked = title_c.1 < mode_c.1 && mode_c.1 < count_c.1;
    let overlapping = x_overlap(&title.bbox, &mode.bbox) > 0.0 && x_overlap(&mode.bbox, &countdown.bbox) > 0.0;
    let det_dy = count_c.1 - title_c.1;
    let scale = det_dy / ref_dy;
    if !stacked || !overlapping || det_dy < 8.0 || !(0.15..=6.0).contains(&scale) {
        return Anchor::missing(NOT_WHOLE, ready_count);
    }
    let scale = ready_scale(lines, &title.bbox, scale);
    let place = |frac: &Rect| map_box(frac, title_c, ref_title_c, scale, image_width, image_height);
    Anchor {
        found: true,
        reason: String::new(),
        countdown_seconds: Some(seconds),
        ready_count,
        scale,
        name_boxes: NAME_BOXES.iter().map(place).collect(),
        button_box: Some(place(&BUTTON_BOX)),
        title_box: Some(title.bbox),
        mode_box: Some(mode.bbox),
        countdown_box: Some(countdown.bbox),
    }
}

/// The whole 16:9 game screen in title-countdown gaps: its height, and from the title's middle up to its top.
pub const GAME_HEIGHT_GAPS: f64 = 8.3;
pub const GAME_TOP_GAPS: f64 = 1.12;
pub const GAME_ASPECT: f64 = 16.0 / 9.0;

/// Where the whole game screen is, from the lobby's title and countdown.
pub fn game_screen(anchor: &Anchor) -> Option<Rect> {
    if !anchor.found {
        return None;
    }
    let (title_x, title_y) = center(&anchor.title_box?);
    let gap = center(&anchor.countdown_box?).1 - title_y;
    if gap <= 0.0 {
        return None;
    }
    let height = GAME_HEIGHT_GAPS * gap;
    let width = height * GAME_ASPECT;
    let top = title_y - GAME_TOP_GAPS * gap;
    Some([title_x - width / 2.0, top, title_x + width / 2.0, top + height])
}

/// Place a reference box onto this capture, using the title as the anchor.
fn map_box(frac: &Rect, title_c: (f64, f64), ref_title_c: (f64, f64), scale: f64, width: i64, height: i64) -> PxBox {
    let r = frac_to_px(frac, REF_W, REF_H);
    let points = [(r[0], r[1]), (r[2], r[1]), (r[0], r[3]), (r[2], r[3])]
        .map(|(x, y)| (title_c.0 + (x - ref_title_c.0) * scale, title_c.1 + (y - ref_title_c.1) * scale));
    let edge = |pick: fn(&(f64, f64)) -> f64, low: bool| {
        let values = points.iter().map(pick);
        let value = if low { values.fold(f64::INFINITY, f64::min) } else { values.fold(f64::NEG_INFINITY, f64::max) };
        value.round_ties_even() as i64
    };
    let left = edge(|p| p.0, true).min(width - 1).max(0);
    let top = edge(|p| p.1, true).min(height - 1).max(0);
    let right = edge(|p| p.0, false).min(width).max(left + 1);
    let bottom = edge(|p| p.1, false).min(height).max(top + 1);
    [left, top, right, bottom]
}
