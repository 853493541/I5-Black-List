//! Where the marks go for a check (ui.py _show_result, _show_panel_at, _place_beside, _show_like_card), and
//! the one picture of all of them that the layered window shows.

use crate::canvas::Canvas;
use crate::cards::{hit_card, like_card, like_top, Person};
use crate::marks::{badge, panel, Mode, Style};
use crate::paint::{py_round, GLOW};

/// The 准备案件还原 cover reaches this far past the button on each side (_COVER_OUTSET).
pub const COVER_OUTSET: f32 = 3.0;
/// Between the cover and the mark beside it.
const GAP: i32 = 16;

// stub: pipeline — the parts of its CheckResult the marks need. Rects are (left, top, right, bottom) in
// virtual-desktop device pixels, as the app maps them from the screen copy.
#[derive(Clone, Debug, PartialEq)]
pub enum SeatKind {
    /// A 黑名单 player, with the entry's tags.
    Blacklist { tags: Vec<String> },
    /// A 嘉宾 player.
    Guest,
    None,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Seat {
    /// The name shown on a card: the entry's name for a 黑名单 player, the 昵称 or full name for a 嘉宾.
    pub name: String,
    pub rect: [i32; 4],
    pub kind: SeatKind,
}

#[derive(Clone, Debug, Default, PartialEq)]
pub struct CheckResult {
    pub seats: Vec<Seat>,
    /// 准备案件还原; None: no marks.
    pub button_box: Option<[i32; 4]>,
    /// The game's picture, from game_area.
    pub game_box: Option<[i32; 4]>,
}
// end stub

/// A box in logical pixels (x, y, width, height); right() and bottom() as QRect has them (the last pixel in).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Rect {
    pub x: i32,
    pub y: i32,
    pub w: i32,
    pub h: i32,
}

impl Rect {
    pub fn right(self) -> i32 {
        self.x + self.w - 1
    }
    pub fn bottom(self) -> i32 {
        self.y + self.h - 1
    }
}

/// What the cover shows besides a result: 检查中 while a check runs, or 我's 场景 (the rose ring and badge
/// with nobody listed).
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct Extras<'a> {
    pub checking: Option<&'a str>,
    pub mine: bool,
}

/// One mark drawn and where its window goes, in logical pixels.
pub struct Placed {
    pub what: &'static str,
    pub at: Rect,
    pub canvas: Canvas,
}

/// The marks for a check, bottom to top, as the app lays them out on a screen whose free area is `area`.
/// `ratio` is the monitor's scale (1.5 at 150 %); `button` is 准备案件还原 in device pixels.
pub fn plan(button: [i32; 4], result: &CheckResult, extras: Extras, area: Rect, style: &Style) -> Vec<Placed> {
    let Style { look, face, at, ratio } = *style;
    let (left, top) = (button[0] as f32 / ratio, button[1] as f32 / ratio);
    let (bw, bh) = ((button[2] - button[0]) as f32 / ratio, (button[3] - button[1]) as f32 / ratio);
    let cw = py_round(bw + COVER_OUTSET * 2.0).max(1);
    let ch = py_round(bh + COVER_OUTSET * 2.0).max(1);
    let cover = Rect { x: py_round(left - COVER_OUTSET), y: py_round(top - COVER_OUTSET), w: cw, h: ch };
    let hits: Vec<Person> = dedupe(result.seats.iter().filter_map(|s| match &s.kind {
        SeatKind::Blacklist { tags } => Some(Person { name: s.name.clone(), tags: tags.clone() }),
        _ => None,
    }));
    let likes: Vec<Person> =
        dedupe(result.seats.iter().filter(|s| s.kind == SeatKind::Guest).map(|s| Person { name: s.name.clone(), tags: vec![] }));
    let mode = match (extras.checking, hits.is_empty(), likes.is_empty() && !extras.mine) {
        (Some(_), _, _) => Mode::Checking,
        (None, false, _) => if likes.is_empty() { Mode::Hit } else { Mode::Both },
        (None, true, false) => Mode::Liked,
        (None, true, true) => Mode::Clear,
    };
    let window = |r: Rect| Rect { x: r.x - GLOW, y: r.y - GLOW, w: r.w + 2 * GLOW, h: r.h + 2 * GLOW };
    let mut out = vec![Placed { what: "cover", at: window(cover), canvas: panel(cw, ch, mode, extras.checking.unwrap_or(""), style) }];
    if mode == Mode::Checking {
        return out;
    }
    let mut side: Option<(Rect, i32)> = None;
    if !hits.is_empty() {
        if let Some(face) = face {
            let canvas = hit_card(face, &hits, ch, ratio);
            let at = beside(cover, logical(&canvas), 0, area);
            side = Some((at, 0));
            out.push(Placed { what: "hit_card", at, canvas });
        }
    } else {
        let canvas = badge(ch, mode == Mode::Liked, look, at.t, ratio);
        let at = beside(cover, logical(&canvas), GLOW, area);
        side = Some((at, GLOW));
        out.push(Placed { what: "badge", at, canvas });
    }
    if let (false, Some(face)) = (likes.is_empty(), face) {
        let canvas = like_card(face, look, &likes, ch, at.t, ratio);
        let (w, h) = logical(&canvas);
        let mut x = cover.x - GAP - w;
        let mut y = cover.y - like_top(look);
        if x < area.x + 8 {
            // No room on the left: on the right, under the 黑名单 card or after the badge.
            match side {
                Some((r, 0)) => (x, y) = (r.x, r.y + r.h + 8),
                Some((r, margin)) => x = r.x + r.w - margin + 10,
                None => {}
            }
        }
        y = y.min(area.bottom() - h - 8).max(area.y + 8);
        out.push(Placed { what: "like_card", at: Rect { x, y, w, h }, canvas });
    }
    out
}

fn dedupe(people: impl Iterator<Item = Person>) -> Vec<Person> {
    let mut out: Vec<Person> = Vec::new();
    for p in people {
        if !out.contains(&p) {
            out.push(p);
        }
    }
    out
}

fn logical(canvas: &Canvas) -> (i32, i32) {
    let r = canvas.ratio;
    (py_round(canvas.pixmap.width() as f32 / r), py_round(canvas.pixmap.height() as f32 / r))
}

/// Beside the cover, centered on it; a mark with a glow (margin) lines up by what it draws (_place_beside).
fn beside(cover: Rect, (w, h): (i32, i32), margin: i32, area: Rect) -> Rect {
    let mut x = cover.x + cover.w + GAP - margin;
    let mut y = cover.y + (cover.h - h).div_euclid(2);
    if x + w - margin > area.right() - 8 {
        x = cover.x - GAP - w + margin;
    }
    x = x.min(area.right() - w + margin - 8).max(area.x + 8 - margin);
    y = y.min(area.bottom() - h + margin - 8).max(area.y + 8 - margin);
    Rect { x, y, w, h }
}

/// All the marks in one picture: its top-left in logical pixels and the canvas (device pixels).
pub fn compose(marks: &[Placed], ratio: f32) -> Option<(Rect, Canvas)> {
    let x0 = marks.iter().map(|m| m.at.x).min()?;
    let y0 = marks.iter().map(|m| m.at.y).min()?;
    let x1 = marks.iter().map(|m| m.at.x + m.at.w).max()?;
    let y1 = marks.iter().map(|m| m.at.y + m.at.h).max()?;
    let bounds = Rect { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
    let mut frame = Canvas::new(bounds.w, bounds.h, ratio);
    for m in marks {
        let dx = ((m.at.x - x0) as f32 * ratio).round() as i32;
        let dy = ((m.at.y - y0) as f32 * ratio).round() as i32;
        frame.draw_pixmap(dx, dy, &m.canvas.pixmap);
    }
    Some((bounds, frame))
}
