//! The drawing pieces of ui_overlay.py: rounded boxes, the two-color brush, glows, the heart, the flowers, the
//! knot, the glint and the result ring, shaded as QPainter shades them.

use tiny_skia::{Color, GradientStop, LinearGradient, Path, PathBuilder, Point, RadialGradient, Rect, Shader, SpreadMode, Transform};

use crate::canvas::Canvas;
use crate::look::{Flower, Look};

/// Room around a mark, inside its window, for its glow (_GLOW).
pub const GLOW: i32 = 9;
/// A result ring, from the outside in: a gold rim, then the color (_RIM, _BAND).
pub const RIM: f32 = 2.4;
pub const BAND: f32 = 4.0;
pub const GOLD: &str = "#e4c47e";
pub const RED: &str = "#a8262f";
pub const GREEN: &str = "#2f9e5e";
pub const ROSE: &str = "#c2306b";
pub const RED_GLOW: (u8, u8, u8, u8) = (220, 60, 70, 140);
pub const GREEN_GLOW: (u8, u8, u8, u8) = (52, 200, 110, 130);

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct RectF {
    pub x: f32,
    pub y: f32,
    pub w: f32,
    pub h: f32,
}

impl RectF {
    pub fn new(x: f32, y: f32, w: f32, h: f32) -> RectF {
        RectF { x, y, w, h }
    }
    /// QRectF.adjusted.
    pub fn adjusted(self, l: f32, t: f32, r: f32, b: f32) -> RectF {
        RectF::new(self.x + l, self.y + t, self.w - l + r, self.h - t + b)
    }
    pub fn right(self) -> f32 {
        self.x + self.w
    }
    pub fn bottom(self) -> f32 {
        self.y + self.h
    }
    pub fn center(self) -> (f32, f32) {
        (self.x + self.w / 2.0, self.y + self.h / 2.0)
    }
}

/// Python's round(): halves to even, so sizes match the app's to the pixel.
pub fn py_round(v: f32) -> i32 {
    let r = v.round();
    if (v - v.trunc()).abs() == 0.5 && (r as i64) % 2 != 0 {
        (r - v.signum()) as i32
    } else {
        r as i32
    }
}

/// "#rrggbb" at alpha 0..=1.
pub fn hex(color: &str, alpha: f32) -> Color {
    let v = u32::from_str_radix(color.trim_start_matches('#'), 16).unwrap_or(0);
    let a = (alpha.clamp(0.0, 1.0) * 255.0).round() as u8;
    Color::from_rgba8((v >> 16) as u8, (v >> 8) as u8, v as u8, a)
}

pub fn rgba(c: (u8, u8, u8, u8)) -> Color {
    Color::from_rgba8(c.0, c.1, c.2, c.3)
}

/// 准备案件还原 is a rounded rectangle, not a pill (_cover_radius).
pub fn cover_radius(height: i32) -> i32 {
    py_round(height as f32 * 0.14).max(4)
}

/// QPainter.drawRoundedRect's path: radii clamped to half the box.
pub fn rrect(r: RectF, radius: f32) -> Option<Path> {
    let rect = Rect::from_xywh(r.x, r.y, r.w, r.h)?;
    let rad = radius.min(r.w / 2.0).min(r.h / 2.0).max(0.0);
    if rad <= 0.0 {
        return Some(PathBuilder::from_rect(rect));
    }
    let k = rad * (1.0 - 0.552_284_8);
    let (x0, y0, x1, y1) = (r.x, r.y, r.right(), r.bottom());
    let mut pb = PathBuilder::new();
    pb.move_to(x0 + rad, y0);
    pb.line_to(x1 - rad, y0);
    pb.cubic_to(x1 - k, y0, x1, y0 + k, x1, y0 + rad);
    pb.line_to(x1, y1 - rad);
    pb.cubic_to(x1, y1 - k, x1 - k, y1, x1 - rad, y1);
    pb.line_to(x0 + rad, y1);
    pb.cubic_to(x0 + k, y1, x0, y1 - k, x0, y1 - rad);
    pb.line_to(x0, y0 + rad);
    pb.cubic_to(x0, y0 + k, x0 + k, y0, x0 + rad, y0);
    pb.close();
    pb.finish()
}

pub fn oval(r: RectF) -> Option<Path> {
    PathBuilder::from_oval(Rect::from_xywh(r.x, r.y, r.w, r.h)?)
}

pub fn circle(cx: f32, cy: f32, rx: f32, ry: f32) -> Option<Path> {
    oval(RectF::new(cx - rx, cy - ry, rx * 2.0, ry * 2.0))
}

/// A gradient from `a` to `b` through `stops` (at, color); one color when the points meet.
pub fn linear(a: (f32, f32), b: (f32, f32), stops: &[(f32, Color)]) -> Shader<'static> {
    let list = stops.iter().map(|&(at, c)| GradientStop::new(at, c)).collect();
    LinearGradient::new(Point::from_xy(a.0, a.1), Point::from_xy(b.0, b.1), list, SpreadMode::Pad, Transform::identity())
        .unwrap_or(Shader::SolidColor(stops[0].1))
}

pub fn radial(c: (f32, f32), radius: f32, stops: &[(f32, Color)]) -> Shader<'static> {
    let list = stops.iter().map(|&(at, c)| GradientStop::new(at, c)).collect();
    let p = Point::from_xy(c.0, c.1);
    RadialGradient::new(p, p, radius, list, SpreadMode::Pad, Transform::identity()).unwrap_or(Shader::SolidColor(stops[0].1))
}

/// One color, or two (left half, right half, blended in the middle), or three (ends and middle) (_across).
pub fn across(b: RectF, colors: &[Color]) -> Shader<'static> {
    let (l, r) = ((b.x, b.y), (b.right(), b.y));
    match colors {
        [one] => Shader::SolidColor(*one),
        [a, m, z] => linear(l, r, &[(0.0, *a), (0.5, *m), (1.0, *z)]),
        [a, z, ..] => linear(l, r, &[(0.0, *a), (0.42, *a), (0.58, *z), (1.0, *z)]),
        [] => Shader::SolidColor(Color::TRANSPARENT),
    }
}

/// A soft light around a box, fading out over GLOW; in two colors, split like the ring (_glow).
pub fn glow(canvas: &mut Canvas, b: RectF, radius: f32, colors: &[Color], round: bool) {
    for step in (1..GLOW).rev() {
        let fade = (1.0 - step as f32 / GLOW as f32).powf(1.6);
        let shades: Vec<Color> = colors
            .iter()
            .map(|c| {
                let mut s = *c;
                s.set_alpha((py_round(c.alpha() * 255.0 * fade) as f32 / 255.0).clamp(0.0, 1.0));
                s
            })
            .collect();
        let s = step as f32;
        let grown = b.adjusted(-s, -s, s, s);
        if round {
            if let Some(p) = oval(grown) {
                canvas.fill(&p, across(grown, &shades));
            }
        } else if let Some(p) = rrect(grown, radius + s) {
            canvas.stroke(&p, across(grown, &shades), 2.0);
        }
    }
}

/// The result ring: the color, a gold rim around it, a glow outside; two colors split it down the middle.
pub fn ring(canvas: &mut Canvas, cover: RectF, colors: &[Color], glows: &[Color]) {
    let radius = cover_radius(py_round(cover.h)) as f32;
    glow(canvas, cover, radius, glows, false);
    let half = RIM / 2.0;
    if let Some(p) = rrect(cover.adjusted(half, half, -half, -half), radius) {
        canvas.stroke(&p, Shader::SolidColor(hex(GOLD, 1.0)), RIM);
    }
    let inset = RIM + BAND / 2.0;
    if let Some(p) = rrect(cover.adjusted(inset, inset, -inset, -inset), (radius - inset).max(1.0)) {
        canvas.stroke(&p, across(cover, colors), BAND);
    }
}

/// A heart about `size` wide, centered on (cx, cy) (_heart_path).
pub fn heart_path(cx: f32, cy: f32, size: f32) -> Option<Path> {
    let u = size / 17.0;
    let (x0, y0) = (cx - 8.5 * u, cy - 7.5 * u);
    let p = |x: f32, y: f32| (x0 + x * u, y0 + y * u);
    let mut pb = PathBuilder::new();
    let s = p(8.5, 15.0);
    pb.move_to(s.0, s.1);
    for c in [
        [(2.0, 10.5), (0.0, 7.0), (0.0, 4.3)],
        [(0.0, 1.7), (2.0, 0.0), (4.3, 0.0)],
        [(6.1, 0.0), (7.6, 1.1), (8.5, 2.7)],
        [(9.4, 1.1), (10.9, 0.0), (12.7, 0.0)],
        [(15.0, 0.0), (17.0, 1.7), (17.0, 4.3)],
        [(17.0, 7.0), (15.0, 10.5), (8.5, 15.0)],
    ] {
        let (a, b, e) = (p(c[0].0, c[0].1), p(c[1].0, c[1].1), p(c[2].0, c[2].1));
        pb.cubic_to(a.0, a.1, b.0, b.1, e.0, e.1);
    }
    pb.close();
    pb.finish()
}

/// Five soft petals, deep at the heart and pale at the tips, in a faint glow of their own (_flower).
pub fn flower(canvas: &mut Canvas, x: f32, y: f32, r: f32, tone: Flower, turn: f32, halo: f32) {
    if r < 0.5 {
        return;
    }
    let (light, mid, deep) = tone;
    let saved = canvas.local;
    let base = saved.pre_translate(x, y).pre_rotate(turn);
    canvas.local = base;
    if halo > 0.0 {
        if let Some(p) = circle(0.0, 0.0, r * halo, r * halo) {
            canvas.fill(&p, radial((0.0, 0.0), r * halo, &[(0.0, hex(mid, 0.45)), (1.0, hex(mid, 0.0))]));
        }
    }
    for i in 0..5 {
        canvas.local = base.pre_rotate(i as f32 * 72.0);
        let petal = linear((0.0, 0.0), (0.0, -r * 1.05), &[(0.0, hex(deep, 1.0)), (0.55, hex(mid, 1.0)), (1.0, hex(light, 1.0))]);
        if let Some(p) = oval(RectF::new(-r * 0.36, -r * 1.05, r * 0.72, r * 0.82)) {
            canvas.fill(&p, petal);
            canvas.stroke(&p, Shader::SolidColor(hex("#ffffff", 0.55)), (r * 0.05).max(0.6));
        }
    }
    canvas.local = base;
    if let Some(p) = circle(0.0, 0.0, r * 0.2, r * 0.2) {
        canvas.fill(&p, Shader::SolidColor(hex("#fff6d8", 1.0)));
    }
    canvas.local = saved;
}

/// A knot of flowers, overlapping: two of the look's first flower and two of its second (_knot).
pub fn knot(canvas: &mut Canvas, x: f32, y: f32, size: f32, halo: f32, look: &Look) {
    for (dx, dy, scale, which, turn) in [(-0.55, 0.15, 0.62, 0, 12.0), (0.5, 0.05, 0.55, 1, 40.0), (0.0, -0.35, 0.75, 0, 64.0), (0.1, 0.55, 0.38, 1, 25.0)] {
        flower(canvas, x + dx * size, y + dy * size, scale * size, look.flowers[which], turn, halo);
    }
}

/// A four-point glint with a small halo (_sparkle).
pub fn sparkle(canvas: &mut Canvas, x: f32, y: f32, r: f32, alpha: f32) {
    if alpha <= 0.01 || r < 0.5 {
        return;
    }
    let a = |v: f32| py_round(v * alpha) as u8;
    if let Some(p) = circle(x, y, r * 1.6, r * 1.6) {
        let stops = [(0.0, Color::from_rgba8(255, 240, 250, a(140.0))), (1.0, Color::from_rgba8(255, 200, 230, 0))];
        canvas.fill(&p, radial((x, y), r * 1.6, &stops));
    }
    let mut pb = PathBuilder::new();
    pb.move_to(x, y - r);
    for (px, py) in [(0.16, -0.16), (1.0, 0.0), (0.16, 0.16), (0.0, 1.0), (-0.16, 0.16), (-1.0, 0.0), (-0.16, -0.16)] {
        pb.line_to(x + px * r, y + py * r);
    }
    pb.close();
    if let Some(p) = pb.finish() {
        canvas.fill(&p, Shader::SolidColor(hex("#ffffff", alpha)));
    }
}
