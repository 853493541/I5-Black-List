//! The cover on 准备案件还原 (ui_overlay.LobbyPanel) and the badge beside it (ClearMark), each drawn into a
//! canvas the size of its Qt window: the mark and GLOW around it for the glow.

use tiny_skia::{Color, Shader};

use crate::canvas::Canvas;
use crate::look::Look;
use crate::paint::{
    across, circle, cover_radius, glow, heart_path, hex, knot, linear, oval, py_round, radial, rgba, ring, rrect, sparkle, RectF,
    GLOW, GOLD, GREEN, GREEN_GLOW, RED, RED_GLOW,
};
use crate::text::Face;

/// What the cover shows (LobbyPanel.mode).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Mode {
    /// A block of antique gold hides the button while a check runs, with 检查中 on it.
    Checking,
    /// 黑名单 players: a crimson ring.
    Hit,
    /// Nobody listed: an emerald ring.
    Clear,
    /// 嘉宾 players (or 我's 场景) and no 黑名单: the look's rose ring with flowers.
    Liked,
    /// 嘉宾 and 黑名单 players: rose on the left, where their card is, crimson on the right.
    Both,
}

/// Mark state that moves: the glint's phase on the gold block (0..1, a 1.6 s loop), and the seconds since a
/// scene-drawn mark showed (MARKS_ANIMATED).
#[derive(Clone, Copy, Debug, Default)]
pub struct Moment {
    pub phase: f32,
    pub t: f32,
}

/// How every mark of one showing is drawn: the scene's look, the face for words, the moment, the screen's scale.
#[derive(Clone, Copy)]
pub struct Style<'a> {
    pub look: &'a Look,
    pub face: Option<&'a Face>,
    pub at: Moment,
    pub ratio: f32,
}

/// The cover window: `width` by `height` is the cover (the button and its outset), GLOW added round it.
pub fn panel(width: i32, height: i32, mode: Mode, text: &str, style: &Style) -> Canvas {
    let Style { look, face, at, ratio } = *style;
    let (w, h) = (width.max(1) + 2 * GLOW, height.max(1) + 2 * GLOW);
    let mut canvas = Canvas::new(w, h, ratio);
    let cover = RectF::new(GLOW as f32, GLOW as f32, width.max(1) as f32, height.max(1) as f32);
    let radius = cover_radius(height.max(1)) as f32;
    // The window's shape (_mask_pill): the cover while checking, the cover and its glow for a result.
    let shape = match mode {
        Mode::Checking => rrect(cover, radius),
        Mode::Liked => rrect(RectF::new(0.0, 0.0, w as f32, h as f32), 0.0),
        _ => rrect(RectF::new(0.0, 0.0, w as f32, h as f32), radius + GLOW as f32),
    };
    if let Some(shape) = shape {
        canvas.clip_to(&shape);
    }
    match mode {
        Mode::Checking => brass(&mut canvas, cover, radius, text, face, at.phase),
        Mode::Liked => liked(&mut canvas, cover, radius, look, at.t),
        Mode::Hit => ring(&mut canvas, cover, &[hex(RED, 1.0)], &[rgba(RED_GLOW)]),
        Mode::Clear => ring(&mut canvas, cover, &[hex(GREEN, 1.0)], &[rgba(GREEN_GLOW)]),
        Mode::Both => {
            let deep = rgba((look.deep_glow.0, look.deep_glow.1, look.deep_glow.2, 140));
            ring(&mut canvas, cover, &[hex(look.deep, 1.0), hex(RED, 1.0)], &[deep, rgba(RED_GLOW)]);
        }
    }
    canvas
}

fn liked(canvas: &mut Canvas, cover: RectF, radius: f32, look: &Look, t: f32) {
    if look.hook().is_some_and(|hook| hook.ring(canvas, cover, t)) {
        return;
    }
    glow(canvas, cover, radius, &[rgba((look.glow.0, look.glow.1, look.glow.2, 120))], false);
    let (ends, middle) = (hex(look.band.0, 1.0), hex(look.band.1, 1.0));
    let pens: [(f32, Shader<'static>, f32); 3] = [
        (1.1, Shader::SolidColor(hex(look.rim, 1.0)), 2.2),
        (4.7, across(cover, &[ends, middle, ends]), 5.0),
        (7.7, Shader::SolidColor(hex("#ffffff", 0.6)), 1.0),
    ];
    for (inset, shader, width) in pens {
        if let Some(p) = rrect(cover.adjusted(inset, inset, -inset, -inset), (radius - inset).max(1.0)) {
            canvas.stroke(&p, shader, width);
        }
    }
    let size = (cover.h * 0.17).clamp(8.0, 13.0);
    knot(canvas, cover.x + size * 0.7, cover.y + size * 0.7, size, 1.2, look);
    knot(canvas, cover.right() - size * 0.7, cover.bottom() - size * 0.7, size, 1.2, look);
}

/// Opaque antique gold: the button must not show through while it is being checked (_paint_brass).
fn brass(canvas: &mut Canvas, cover: RectF, radius: f32, text: &str, face: Option<&Face>, phase: f32) {
    let fill = linear(
        (cover.x, cover.y),
        (cover.x, cover.bottom()),
        &[(0.0, hex("#e4c47e", 1.0)), (0.5, hex("#c9a254", 1.0)), (1.0, hex("#a07c36", 1.0))],
    );
    if let Some(p) = rrect(cover.adjusted(0.5, 0.5, -0.5, -0.5), radius) {
        canvas.fill(&p, fill);
        canvas.stroke(&p, Shader::SolidColor(Color::from_rgba8(0, 0, 0, 150)), 1.0);
    }
    if let Some(p) = rrect(cover.adjusted(3.5, 3.5, -3.5, -3.5), (radius - 3.0).max(1.0)) {
        canvas.stroke(&p, Shader::SolidColor(Color::from_rgba8(255, 240, 200, 150)), 1.0);
    }
    let travel = phase / 0.65;
    if travel <= 1.0 {
        let x = cover.x - cover.h + travel * (cover.w + cover.h * 2.0);
        let clear = Color::from_rgba8(255, 255, 255, 0);
        let band = linear((x - 30.0, cover.y), (x + 30.0, cover.bottom()), &[(0.0, clear), (0.5, Color::from_rgba8(255, 250, 230, 120)), (1.0, clear)]);
        if let (Some(p), Some(shape)) = (rrect(cover, radius), rrect(cover, radius)) {
            let saved = canvas.clip.take();
            canvas.clip_to(&shape);
            canvas.fill(&p, band);
            canvas.clip = saved;
        }
    }
    // The words, dead center on the cover (_paint_words).
    if let (Some(face), false) = (face, text.is_empty()) {
        let px = py_round(cover.h * 0.36).clamp(12, 30) as f32;
        let (x0, y0, x1, y1) = face.ink(text, px);
        let (cx, cy) = cover.center();
        face.draw(canvas, text, cx - (x0 + x1) / 2.0, cy - (y0 + y1) / 2.0, px, hex("#2b1d08", 1.0));
    }
}

/// The badge's window for a cover `cover_height` high: its side and GLOW round it (ClearMark.set_size).
pub fn badge_side(cover_height: i32) -> i32 {
    py_round(cover_height as f32 * 0.7).max(16) + 2 * GLOW
}

/// The check beside a clear button, or with 嘉宾 players the heart badge in the look (ClearMark).
pub fn badge(cover_height: i32, heart: bool, look: &Look, t: f32, ratio: f32) -> Canvas {
    let full = badge_side(cover_height);
    let mut canvas = Canvas::new(full, full, ratio);
    let b = RectF::new(GLOW as f32, GLOW as f32, (full - 2 * GLOW) as f32, (full - 2 * GLOW) as f32);
    let side = b.w;
    if heart {
        heart_badge(&mut canvas, b, look, t);
        return canvas;
    }
    glow(&mut canvas, b, side / 2.0, &[rgba(GREEN_GLOW)], true);
    if let Some(p) = oval(b.adjusted(1.0, 1.0, -1.0, -1.0)) {
        canvas.fill(&p, Shader::SolidColor(hex(GREEN, 1.0)));
        canvas.stroke(&p, Shader::SolidColor(hex(GOLD, 1.0)), (side * 0.06).max(1.5));
    }
    let mut pb = tiny_skia::PathBuilder::new();
    pb.move_to(b.x + side * 0.28, b.y + side * 0.52);
    pb.line_to(b.x + side * 0.44, b.y + side * 0.67);
    pb.line_to(b.x + side * 0.73, b.y + side * 0.36);
    if let Some(p) = pb.finish() {
        canvas.stroke_round(&p, hex("#ffffff", 1.0), (side * 0.08).max(2.0));
    }
    canvas
}

/// A disc in a fine rim, a heart on it, a glint at its shoulder (_paint_heart), or the scene's own badge.
fn heart_badge(canvas: &mut Canvas, b: RectF, look: &Look, t: f32) {
    if look.hook().is_some_and(|hook| hook.badge(canvas, b, t)) {
        return;
    }
    let side = b.w;
    let (cx, cy) = b.center();
    glow(canvas, b, side / 2.0, &[rgba((look.glow.0, look.glow.1, look.glow.2, 120))], true);
    if let Some(p) = oval(b.adjusted(1.0, 1.0, -1.0, -1.0)) {
        canvas.fill(&p, radial((cx, cy), side / 2.0, &[(0.0, hex(look.disc.0, 1.0)), (1.0, hex(look.disc.1, 1.0))]));
        canvas.stroke(&p, Shader::SolidColor(hex(look.rim, 1.0)), (side * 0.04).max(1.5));
    }
    let inner = (side * 0.08).max(3.0);
    if let Some(p) = oval(b.adjusted(inner, inner, -inner, -inner)) {
        canvas.stroke(&p, Shader::SolidColor(hex("#ffffff", 0.7)), 1.0);
    }
    let shade = linear((cx, cy - side * 0.25), (cx, cy + side * 0.25), &[(0.0, hex(look.heart.0, 1.0)), (1.0, hex(look.heart.1, 1.0))]);
    if let Some(p) = heart_path(cx, cy + side * 0.03, side * 0.48) {
        canvas.fill(&p, shade);
    }
    if let Some(p) = circle(cx - side * 0.11, cy - side * 0.07, side * 0.05, side * 0.035) {
        canvas.fill(&p, Shader::SolidColor(hex("#ffffff", 0.7)));
    }
    sparkle(canvas, b.right() - side * 0.08, b.y + side * 0.1, (side * 0.09).max(3.0), 1.0);
}
