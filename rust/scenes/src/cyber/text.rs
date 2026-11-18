//! The HUD's lettering as Qt sets it: glyph outlines from the font file at FreeType's scaled points,
//! placed at Qt's advances plus its letter spacing, filled with exact pixel areas (equation::text's
//! Shape), each string at its own sub-pixel place.
//!
//! The Python scene asks for Consolas; Qt falls back for 嘉宾. On Windows: consola.ttf and Microsoft
//! YaHei; in this container Qt uses DejaVu Sans Mono and WenQuanYi Zen Hei, and so does this.

use ab_glyph::{Font, FontVec, GlyphId, Outline, OutlineCurve};

use super::canvas::{Canvas, TEXT};
use super::light::round_even;
use crate::draw::{hex, Pt};
use crate::equation::text::{quad_at, Shape};

const MONO: [(&str, u32); 2] = [("C:\\Windows\\Fonts\\consola.ttf", 0), ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 0)];
const HAN: [(&str, u32); 2] = [("C:\\Windows\\Fonts\\msyh.ttc", 0), ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0)];

fn load(list: &[(&str, u32)]) -> Option<FontVec> {
    list.iter().find_map(|&(path, index)| FontVec::try_from_vec_and_index(std::fs::read(path).ok()?, index).ok())
}

/// The three faces the scene uses: (pixel size, letter spacing in 1/64 px).
#[derive(Clone, Copy)]
pub enum Face {
    Title,
    Small,
    Rail,
}

pub struct Type {
    fonts: Option<(FontVec, FontVec)>,
    faces: [(f64, i64); 3],
}

impl Type {
    pub fn new(u: f64) -> Self {
        let spacing = (0.8 * u * 64.0).round() as i64;
        let px = |s: f64| round_even(s * u).max(4.0);
        let fonts = load(&MONO).zip(load(&HAN));
        Self { fonts, faces: [(px(10.5), spacing), (px(9.0), spacing), (px(8.0), 0)] }
    }

    fn pick(&self, ch: char) -> Option<(&FontVec, GlyphId)> {
        let (mono, han) = self.fonts.as_ref()?;
        let id = mono.glyph_id(ch);
        Some(if id.0 == 0 && !ch.is_ascii() { (han, han.glyph_id(ch)) } else { (mono, id) })
    }

    /// FreeType's 16.16 x_scale for a font px pixels high.
    fn scale(font: &FontVec, px: f64) -> i64 {
        let em = font.units_per_em().unwrap_or(1000.0) as i64;
        ((px as i64 * 64) * 65536 + em / 2) / em
    }

    fn step(font: &FontVec, scale: i64, id: GlyphId) -> i64 {
        ((font.h_advance_unscaled(id) as i64 * scale + 32) / 64) >> 10
    }

    /// QFontMetricsF::horizontalAdvance, letter spacing included.
    pub fn advance(&self, face: Face, text: &str) -> f64 {
        let (px, spacing) = self.faces[face as usize];
        let pen: i64 = text.chars().filter_map(|ch| self.pick(ch)).map(|(f, id)| Self::step(f, Self::scale(f, px), id) + spacing).sum();
        pen as f64 / 64.0
    }

    /// The outline of text set with its baseline starting at `at`.
    fn shape(&self, face: Face, at: Pt, text: &str) -> Shape {
        let (px, spacing) = self.faces[face as usize];
        let mut shape = Shape::default();
        let mut pen = 0i64;
        for ch in text.chars() {
            let Some((font, id)) = self.pick(ch) else { continue };
            let scale = Self::scale(font, px);
            let fix = |v: f32| (f64::from(v) * scale as f64 / 65536.0).round() / 64.0;
            let x = at[0] + pen as f64 / 64.0;
            let map = |p: ab_glyph::Point| [x + fix(p.x), at[1] - fix(p.y)];
            let quad = |lines: &mut Vec<(Pt, Pt)>, a: Pt, c: Pt, b: Pt| {
                let mut last = a;
                for i in 1..=16 {
                    let p = quad_at(a, c, b, f64::from(i) / 16.0);
                    lines.push((last, p));
                    last = p;
                }
            };
            for curve in font.outline(id).map(|o: Outline| o.curves).unwrap_or_default() {
                match curve {
                    OutlineCurve::Line(a, b) => shape.lines.push((map(a), map(b))),
                    OutlineCurve::Quad(a, c, b) => quad(&mut shape.lines, map(a), map(c), map(b)),
                    OutlineCurve::Cubic(a, c, d, b) => {
                        let (a, c, d, b) = (map(a), map(c), map(d), map(b));
                        let mid = [(a[0] + 3.0 * c[0] + 3.0 * d[0] + b[0]) / 8.0, (a[1] + 3.0 * c[1] + 3.0 * d[1] + b[1]) / 8.0];
                        quad(&mut shape.lines, a, [(a[0] + c[0] * 3.0) / 4.0, (a[1] + c[1] * 3.0) / 4.0], mid);
                        quad(&mut shape.lines, mid, [(b[0] + d[0] * 3.0) / 4.0, (b[1] + d[1] * 3.0) / 4.0], b);
                    }
                }
            }
            pen += Self::step(font, scale, id) + spacing;
        }
        shape
    }

    /// QPainter::drawText(at, text) in color at alpha; the coverage goes in the frame's text texture.
    pub fn draw(&self, c: &mut Canvas, face: Face, at: Pt, text: &str, color: &str, alpha: f64) {
        if self.fonts.is_none() || alpha <= 0.0 || text.trim().is_empty() {
            return;
        }
        let key = format!("{}|{}|{:.4}|{:.4}", face as usize, text, at[0], at[1]);
        let (src, dest) = match c.text_cache.get(&key) {
            Some(&hit) => hit,
            None => {
                let shape = self.shape(face, at, text);
                let (mut x0, mut y0, mut x1, mut y1) = (f64::MAX, f64::MAX, f64::MIN, f64::MIN);
                for &(a, b) in &shape.lines {
                    for p in [a, b] {
                        (x0, y0, x1, y1) = (x0.min(p[0]), y0.min(p[1]), x1.max(p[0]), y1.max(p[1]));
                    }
                }
                if x1 < x0 {
                    return;
                }
                let (x0, y0) = (x0.floor() - 1.0, y0.floor() - 1.0);
                let (w, h) = ((x1.ceil() + 1.0 - x0) as usize, (y1.ceil() + 1.0 - y0) as usize);
                let cover = shape.raster(x0, y0, w, h, 1.0);
                let src = c.text_atlas.add_mask(&cover, w, h);
                let hit = (src, [x0, y0, w as f64, h as f64]);
                c.text_cache.insert(key, hit);
                hit
            }
        };
        c.picture(TEXT, src, dest, [1.0, 0.0, 0.0, 1.0, 0.0, 0.0], alpha, Some(hex(color)));
    }
}
