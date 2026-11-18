//! The equations' letters as Qt sets them: glyph outlines from the font file, placed at Qt's own
//! advances (FreeType's 16.16 linear advance cut to 1/64 px), each outline point on the 1/64 grid as
//! QPainterPath::addText leaves it, then filled into coverage masks with exact pixel areas.
//!
//! The Python scene asks for Cambria Math (Han text: KaiTi). On Windows those are
//! C:\Windows\Fonts\cambria.ttc (face 1, Cambria Math) and simkai.ttf; Qt in this container falls
//! back to FreeSerif and WenQuanYi Zen Hei, so those are what the frames here are compared with.

use ab_glyph::{Font, FontVec, GlyphId, Outline, OutlineCurve};

use crate::draw::Pt;

/// Where the fonts are looked for, the first found used: (file, face index).
const MATH: [(&str, u32); 3] = [
    ("C:\\Windows\\Fonts\\cambria.ttc", 1),
    ("/usr/share/fonts/truetype/freefont/FreeSerif.ttf", 0),
    ("/usr/share/fonts/opentype/freefont/FreeSerif.otf", 0),
];
const HAN: [(&str, u32); 3] = [
    ("C:\\Windows\\Fonts\\simkai.ttf", 0),
    ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0),
    ("C:\\Windows\\Fonts\\msyh.ttc", 0),
];

pub struct Fonts {
    math: FontVec,
    han: FontVec,
}

fn load(list: &[(&str, u32)]) -> Result<FontVec, String> {
    for &(path, index) in list {
        if let Ok(data) = std::fs::read(path) {
            return FontVec::try_from_vec_and_index(data, index).map_err(|e| format!("{path}: {e}"));
        }
    }
    Err(format!("no font found among {list:?}"))
}

impl Fonts {
    pub fn load() -> Result<Self, String> {
        Ok(Self { math: load(&MATH)?, han: load(&HAN)? })
    }

    fn pick(&self, han: bool) -> &FontVec {
        if han {
            &self.han
        } else {
            &self.math
        }
    }

    /// FreeType's x_scale for a font set px pixels high (16.16).
    fn scale(&self, han: bool, px: f64) -> i64 {
        let em = self.pick(han).units_per_em().unwrap_or(1000.0) as i64;
        let px = px.round().max(1.0) as i64;
        ((px * 64) * 65536 + em / 2) / em
    }

    /// QFontMetricsF::horizontalAdvance.
    pub fn advance(&self, han: bool, px: f64, text: &str) -> f64 {
        let font = self.pick(han);
        let scale = self.scale(han, px);
        text.chars().map(|ch| f64::from(((font.h_advance_unscaled(font.glyph_id(ch)) as i64 * scale + 32) / 64) as i32 >> 10) / 64.0).sum()
    }

    /// QFontMetricsF::descent.
    pub fn descent(&self, han: bool, px: f64) -> f64 {
        let font = self.pick(han);
        (-f64::from(font.descent_unscaled()) * self.scale(han, px) as f64 / 65536.0).round() / 64.0
    }

    /// QFontMetricsF::ascent.
    pub fn ascent(&self, han: bool, px: f64) -> f64 {
        let font = self.pick(han);
        (f64::from(font.ascent_unscaled()) * self.scale(han, px) as f64 / 65536.0).round() / 64.0
    }
}

/// A filled outline: lines in device pixels, plus round-capped strokes (centre line, half width).
#[derive(Clone, Default)]
pub struct Shape {
    pub lines: Vec<(Pt, Pt)>,
    pub strokes: Vec<(Vec<Pt>, f64)>,
    /// Exact bounds of the curves, as QPainterPath::boundingRect has them: x0, y0, x1, y1.
    bounds: Option<[f64; 4]>,
}

fn grow(b: &mut Option<[f64; 4]>, p: Pt) {
    let r = b.get_or_insert([p[0], p[1], p[0], p[1]]);
    *r = [r[0].min(p[0]), r[1].min(p[1]), r[2].max(p[0]), r[3].max(p[1])];
}

/// The point at s on a quadratic curve.
pub fn quad_at(a: Pt, c: Pt, b: Pt, s: f64) -> Pt {
    let m = 1.0 - s;
    [m * m * a[0] + 2.0 * m * s * c[0] + s * s * b[0], m * m * a[1] + 2.0 * m * s * c[1] + s * s * b[1]]
}

impl Shape {
    pub fn is_empty(&self) -> bool {
        self.bounds.is_none()
    }

    /// x, y, w, h of what is in it (0s when empty).
    pub fn rect(&self) -> [f64; 4] {
        self.bounds.map_or([0.0; 4], |b| [b[0], b[1], b[2] - b[0], b[3] - b[1]])
    }

    fn line(&mut self, a: Pt, b: Pt) {
        grow(&mut self.bounds, a);
        grow(&mut self.bounds, b);
        self.lines.push((a, b));
    }

    fn quad(&mut self, a: Pt, c: Pt, b: Pt) {
        grow(&mut self.bounds, a);
        grow(&mut self.bounds, b);
        for axis in 0..2 {
            let d = a[axis] - 2.0 * c[axis] + b[axis];
            if d.abs() > 1e-12 {
                let s = (a[axis] - c[axis]) / d;
                if s > 0.0 && s < 1.0 {
                    grow(&mut self.bounds, quad_at(a, c, b, s));
                }
            }
        }
        let n = 8;
        let mut last = a;
        for i in 1..=n {
            let p = quad_at(a, c, b, f64::from(i) / f64::from(n));
            self.lines.push((last, p));
            last = p;
        }
    }

    pub fn add_rect(&mut self, x: f64, y: f64, w: f64, h: f64) {
        let (a, b, c, d) = ([x, y], [x + w, y], [x + w, y + h], [x, y + h]);
        self.line(a, b);
        self.line(b, c);
        self.line(c, d);
        self.line(d, a);
    }

    /// A round-capped, round-joined line half wide either side of its centre line.
    pub fn add_stroke(&mut self, points: Vec<Pt>, half: f64) {
        for p in &points {
            grow(&mut self.bounds, [p[0] - half, p[1] - half]);
            grow(&mut self.bounds, [p[0] + half, p[1] + half]);
        }
        self.strokes.push((points, half));
    }

    pub fn add(&mut self, other: &Shape) {
        for &(a, b) in &other.lines {
            self.lines.push((a, b));
        }
        self.strokes.extend(other.strokes.iter().cloned());
        if let Some(b) = other.bounds {
            grow(&mut self.bounds, [b[0], b[1]]);
            grow(&mut self.bounds, [b[2], b[3]]);
        }
    }

    pub fn translate(&mut self, dx: f64, dy: f64) {
        let m = |p: &mut Pt| *p = [p[0] + dx, p[1] + dy];
        self.lines.iter_mut().for_each(|(a, b)| {
            m(a);
            m(b);
        });
        self.strokes.iter_mut().for_each(|(pts, _)| pts.iter_mut().for_each(m));
        if let Some(b) = self.bounds.as_mut() {
            *b = [b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy];
        }
    }

    /// QPainterPath::addText(at, font, text): returns the advance.
    pub fn add_text(&mut self, fonts: &Fonts, han: bool, px: f64, at: Pt, text: &str) -> f64 {
        let font = fonts.pick(han);
        let scale = fonts.scale(han, px);
        // Outline points on the 1/64 grid, as FreeType scales them.
        let fix = |v: f32| ((f64::from(v) * scale as f64 / 65536.0).round()) / 64.0;
        let mut pen = 0i64;
        for ch in text.chars() {
            let id: GlyphId = font.glyph_id(ch);
            let x = at[0] + pen as f64 / 64.0;
            let map = |p: ab_glyph::Point| [x + fix(p.x), at[1] - fix(p.y)];
            if let Some(Outline { curves, .. }) = font.outline(id) {
                for curve in curves {
                    match curve {
                        OutlineCurve::Line(a, b) => self.line(map(a), map(b)),
                        OutlineCurve::Quad(a, c, b) => self.quad(map(a), map(c), map(b)),
                        OutlineCurve::Cubic(a, c, d, b) => {
                            // Rare in these fonts: two quads through the cubic's midpoint.
                            let (a, c, d, b) = (map(a), map(c), map(d), map(b));
                            let mid = [(a[0] + 3.0 * c[0] + 3.0 * d[0] + b[0]) / 8.0, (a[1] + 3.0 * c[1] + 3.0 * d[1] + b[1]) / 8.0];
                            self.quad(a, [(a[0] + c[0] * 3.0) / 4.0, (a[1] + c[1] * 3.0) / 4.0], mid);
                            self.quad(mid, [(b[0] + d[0] * 3.0) / 4.0, (b[1] + d[1] * 3.0) / 4.0], b);
                        }
                    }
                }
            }
            pen += ((font.h_advance_unscaled(id) as i64 * scale + 32) / 64) >> 10;
        }
        pen as f64 / 64.0
    }

    /// Coverage 0..1 of each pixel of a w x h image whose pixel (0, 0) starts at (x0, y0), the
    /// shape scaled by `scale` about that corner, rounded to bytes as a Grayscale8 mask is.
    pub fn raster(&self, x0: f64, y0: f64, w: usize, h: usize, scale: f64) -> Vec<f32> {
        let stride = w + 1;
        let mut acc = vec![0f32; stride * h];
        let to = |p: Pt| [(p[0] - x0) * scale, (p[1] - y0) * scale];
        for &(a, b) in &self.lines {
            area_line(&mut acc, w, h, to(a), to(b));
        }
        let mut out = vec![0f32; w * h];
        for (row, line) in out.chunks_mut(w.max(1)).enumerate() {
            let mut sum = 0f32;
            for (x, v) in line.iter_mut().enumerate() {
                sum += acc[row * stride + x];
                *v = sum.abs().min(1.0);
            }
        }
        for (points, half) in &self.strokes {
            let pts: Vec<Pt> = points.iter().map(|&p| to(p)).collect();
            let half = half * scale;
            for (i, v) in out.iter_mut().enumerate() {
                let p = [(i % w) as f64 + 0.5, (i / w) as f64 + 0.5];
                let d = pts.windows(2).map(|s| seg_dist(p, s[0], s[1])).fold(f64::MAX, f64::min);
                *v = v.max((half + 0.5 - d).clamp(0.0, 1.0) as f32);
            }
        }
        out.iter_mut().for_each(|v| *v = (*v * 255.0).round() / 255.0);
        out
    }
}

pub fn seg_dist(p: Pt, a: Pt, b: Pt) -> f64 {
    let ab = [b[0] - a[0], b[1] - a[1]];
    let k = (((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / (ab[0] * ab[0] + ab[1] * ab[1]).max(1e-12)).clamp(0.0, 1.0);
    (p[0] - a[0] - ab[0] * k).hypot(p[1] - a[1] - ab[1] * k)
}

/// One edge into a signed-area accumulation buffer (font-rs's method): each pixel's share of the
/// area left of the edge, summed along each row afterwards.
fn area_line(acc: &mut [f32], w: usize, h: usize, p0: Pt, p1: Pt) {
    if (p0[1] - p1[1]).abs() < 1e-12 {
        return;
    }
    let (dir, a, b) = if p0[1] < p1[1] { (1.0, p0, p1) } else { (-1.0, p1, p0) };
    let dxdy = (b[0] - a[0]) / (b[1] - a[1]);
    let mut x = a[0];
    let y0 = a[1].max(0.0);
    if a[1] < 0.0 {
        x -= a[1] * dxdy;
    }
    let y_end = b[1].min(h as f64);
    let mut y = y0;
    while y < y_end {
        let row = y.floor() as usize;
        let next = (row as f64 + 1.0).min(y_end);
        let dy = next - y;
        let xn = x + dxdy * dy;
        let base = row * (w + 1);
        let (x0, x1) = if x < xn { (x, xn) } else { (xn, x) };
        let d = (dy * dir) as f32;
        let x0i = x0.max(0.0).floor();
        let x1c = x1.ceil();
        if x1 <= 0.0 {
            acc[base] += d;
        } else if x0 >= w as f64 {
        } else if x1c - x0i <= 1.0 {
            let xmf = 0.5 * (x0 + x1) - x0i;
            let i = (x0i as usize).min(w - 1);
            acc[base + i] += d - d * xmf as f32;
            acc[base + i + 1] += d * xmf as f32;
        } else {
            let s = 1.0 / (x1 - x0);
            let x0f = x0 - x0.floor();
            let a0 = 0.5 * s * (1.0 - x0f) * (1.0 - x0f);
            let x1f = x1 - x1c + 1.0;
            let am = 0.5 * s * x1f * x1f;
            let first = x0.floor();
            let (i0, i1) = (first as i64, x1c as i64);
            let put = |acc: &mut [f32], i: i64, v: f64| {
                let i = i.clamp(0, w as i64) as usize;
                acc[base + i] += (v * f64::from(d)) as f32;
            };
            put(acc, i0, a0);
            if i1 - i0 == 2 {
                put(acc, i0 + 1, 1.0 - a0 - am);
            } else {
                let a1 = s * (1.5 - x0f);
                put(acc, i0 + 1, a1 - a0);
                for xi in i0 + 2..i1 - 1 {
                    put(acc, xi, s);
                }
                let a2 = a1 + (i1 - i0 - 3) as f64 * s;
                put(acc, i1 - 1, 1.0 - a2 - am);
            }
            put(acc, i1, am);
        }
        x = xn;
        y = next;
    }
}
