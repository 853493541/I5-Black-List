//! Where 直播画面 draws the game (ui_stream.StreamMirror._where_livehime_has_it, _fit and to_window).
//!
//! In the scene 直播姬 shows, its scene file says where it put the game's capture and 直播画面's on its canvas,
//! so the game is drawn in 直播画面 where, through 直播画面's own capture, it lands on the game's. Where that cannot
//! be known (no scene file, the game's window not open, a turned or stretched capture), the fit 直播姬 gives a new
//! capture stays: as big as fits, centered.

use super::layout::Placement;
use crate::frame::round_half_even;

/// A rect in desktop pixels: (left, top, right, bottom).
pub type Rect = (i64, i64, i64, i64);

/// A monitor as Qt has it: its top-left corner in desktop pixels, its size in logical units, and its scale.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Screen {
    pub x: i64,
    pub y: i64,
    pub width: i64,
    pub height: i64,
    pub ratio: f64,
}

/// A desktop pixel in window coordinates, with the scale of the monitor it is on (ui_overlay.native_to_logical):
/// Qt keeps each monitor's top-left corner at its pixel position and scales only the size.
pub fn native_to_logical(x: f64, y: f64, screens: &[Screen], primary_ratio: f64) -> (f64, f64, f64) {
    for s in screens {
        let ratio = if s.ratio == 0.0 { 1.0 } else { s.ratio };
        let (sx, sy) = (s.x as f64, s.y as f64);
        if sx <= x && x < sx + s.width as f64 * ratio && sy <= y && y < sy + s.height as f64 * ratio {
            return (sx + (x - sx) / ratio, sy + (y - sy) / ratio, ratio);
        }
    }
    let ratio = if primary_ratio == 0.0 { 1.0 } else { primary_ratio };
    (x / ratio, y / ratio, ratio)
}

/// Where 直播姬 has the game, for [`fit`]: the scale, where the game's corner is drawn in 直播画面 (logical units),
/// and the game window's corner on the screen (logical units).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Follow {
    pub scale: f64,
    pub start: (f64, f64),
    pub corner: (i64, i64),
}

/// 直播画面 itself: its rect in desktop pixels, and its size in Qt's logical units.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Mirror {
    pub mine: Rect,
    pub width: i64,
    pub height: i64,
}

/// Python's round(value, digits): correctly rounded, ties to even.
pub fn py_round(value: f64, digits: usize) -> f64 {
    format!("{value:.digits$}").parse().unwrap_or(value)
}

const FITTED: &str = "draws the game fitted and centered, as 直播姬 places a new capture";

/// Where 直播姬 has the game and 直播画面 (`title`), and what that is in words for the log; None and why where it
/// cannot be known. `scene` is the scene file's (current scene, placements), None when there is no file;
/// `frame_of` is the desktop rect a capture takes of its window (None when it is not open); `to_logical` is
/// [`native_to_logical`] over the screens.
pub fn where_livehime_has_it(
    scene: Option<(&str, &[Placement])>,
    title: &str,
    frame_of: &dyn Fn(&Placement) -> Option<Rect>,
    mirror: &Mirror,
    to_logical: &dyn Fn(f64, f64) -> (f64, f64, f64),
) -> (Option<Follow>, String) {
    let no = |why: String| (None, format!("{FITTED} ({why})"));
    let Some((current, placed)) = scene else { return no("no 直播姬 scene file".into()) };
    let items: Vec<&Placement> = placed.iter().filter(|item| item.scene == current).collect();
    let Some(ours) = items.iter().rev().find(|item| item.title == title && item.visible).copied() else {
        return no(format!("直播姬「{current}」 shows no 直播画面"));
    };
    let at = items.iter().position(|item| *item == ours).unwrap_or(0);
    let game = items[..at].iter().rev().find(|item| item.visible && !item.title.is_empty() && item.title != title).copied();
    let Some(game) = game else { return no(format!("no game capture under it in 直播姬「{current}」")) };
    if ours.rotation != 0.0 || game.rotation != 0.0 || ours.whole_screen {
        return no(format!("直播姬「{current}」 turns a capture, or takes 直播画面 by 窗口区域模式"));
    }
    let Some(frame) = frame_of(game) else { return no(format!("the game's 「{}」 is not open", game.title)) };
    let (fw, fh) = ((frame.2 - frame.0) as f64, (frame.3 - frame.1) as f64);
    let (mw, mh) = ((mirror.mine.2 - mirror.mine.0) as f64, (mirror.mine.3 - mirror.mine.1) as f64);
    let (gx, gy, gw, gh) = game.on_canvas(fw, fh);
    let (mx, my, cw, ch) = ours.on_canvas(mw, mh);
    let here = mw / mirror.width.max(1) as f64;
    let (left, top, ratio) = to_logical(frame.0 as f64, frame.1 as f64);
    // A screen point P lands on the canvas at gx + (P - corner) * ratio * gw / fw through the game's capture,
    // and at mx + (where it is drawn here) * here * cw / mw through 直播画面's.
    let sx = ratio * (gw / fw) * (mw / cw) / here;
    let sy = ratio * (gh / fh) * (mh / ch) / here;
    if !(0.2 < sx && sx < 5.0 && (sx - sy).abs() <= 0.03 * sx) {
        return no(format!("直播姬「{current}」 stretches a capture: ×{sx:.3} across, ×{sy:.3} down"));
    }
    let start = ((gx - mx) * (mw / cw) / here, (gy - my) * (mh / ch) / here);
    let (dw, dh) = (fw / ratio * sx, fh / ratio * sx);
    let seen_w = (start.0 + dw).min(mirror.width as f64) - start.0.max(0.0);
    let seen_h = (start.1 + dh).min(mirror.height as f64) - start.1.max(0.0);
    let seen = if seen_w > 0.0 && seen_h > 0.0 { seen_w * seen_h } else { 0.0 };
    if seen < 0.5 * dw * dh {
        return no(format!("in 直播姬「{current}」 the game is mostly outside 直播画面's capture"));
    }
    let follows = Follow {
        scale: py_round(sx, 4),
        start: (py_round(start.0, 1), py_round(start.1, 1)),
        corner: (round_half_even(left) as i64, round_half_even(top) as i64),
    };
    let note = format!(
        "follows 直播姬「{current}」: the game's 「{}」 drawn at ({:.0}, {:.0}) {:.0}x{:.0} px, where 直播姬 shows it",
        game.title,
        start.0 * here,
        start.1 * here,
        dw * here,
        dh * here
    );
    (Some(follows), note)
}

/// The scale and offset that put the mirrored `area` (x, y, w, h in logical units) in 直播画面 of `size`: where
/// 直播姬 has the game (`follows`), or else as big as fits, centered.
pub fn fit(area: (i64, i64, i64, i64), size: (i64, i64), follows: Option<&Follow>) -> (f64, (f64, f64)) {
    let (ax, ay, aw, ah) = area;
    if aw <= 0 || ah <= 0 {
        return (1.0, (0.0, 0.0));
    }
    if let Some(f) = follows {
        return (f.scale, (f.start.0 + (ax - f.corner.0) as f64 * f.scale, f.start.1 + (ay - f.corner.1) as f64 * f.scale));
    }
    let (w, h) = (size.0 as f64, size.1 as f64);
    let (kx, ky) = (w / aw as f64, h / ah as f64);
    let scale = if ky < kx { ky } else { kx };
    (scale, ((w - aw as f64 * scale) / 2.0, (h - ah as f64 * scale) / 2.0))
}

/// Where a point on the screen (logical units) is drawn in 直播画面.
pub fn to_window(point: (i64, i64), area: (i64, i64, i64, i64), size: (i64, i64), follows: Option<&Follow>) -> (f64, f64) {
    let (scale, offset) = fit(area, size, follows);
    (offset.0 + (point.0 - area.0) as f64 * scale, offset.1 + (point.1 - area.1) as f64 * scale)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_game_with_no_scene_file_is_fitted_and_centered() {
        let mirror = Mirror { mine: (0, 0, 1920, 1080), width: 1920, height: 1080 };
        let (follows, note) = where_livehime_has_it(None, "x", &|_| None, &mirror, &|x, y| (x, y, 1.0));
        assert!(follows.is_none() && note.ends_with("(no 直播姬 scene file)"));
        assert_eq!(fit((0, 0, 1280, 720), (1920, 1080), None), (1.5, (0.0, 0.0)));
        assert_eq!(fit((0, 0, 1000, 1080), (1920, 1080), None), (1.0, (460.0, 0.0)));
        assert_eq!(py_round(0.25, 1), 0.2);
    }
}
