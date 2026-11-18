//! The equations in chalk (equation.py's _formula, _lit, _Formula, _written and _brace): set once
//! as Qt sets them, their letters and glow kept in the atlas, written on left to right behind a
//! nib of light, crumbling to chalk dust at the end.

use std::f64::consts::PI;

use super::atlas::{Atlas, Tile};
use super::light::{halo, round_even};
use super::prim::{Frame, Place};
use super::text::{Fonts, Shape};
use super::{INK, SOFT};
use crate::draw::{clamp, ease_in_out, ease_out, win, Pt};
use crate::pyrand::PyRandom;

/// One piece of an equation: text (accent?), Han text (accent?), sup, sub, a line centred under
/// the piece before, a square root, a fraction.
pub enum Item {
    T(String, bool),
    Han(String, bool),
    Sup(String),
    Sub(String),
    Under(String),
    Root(String),
    Frac(String, String),
}

/// Letters as Cambria Math sets variables: in math italic, from Unicode's own alphabet.
pub fn it(text: &str) -> String {
    text.chars()
        .map(|ch| match ch {
            'h' => 'ℎ',
            'a'..='z' => char::from_u32(0x1D44E + ch as u32 - 'a' as u32).unwrap_or(ch),
            'θ' => '\u{1d703}',
            'π' => '\u{1d70b}',
            'φ' => '\u{1d711}',
            _ => ch,
        })
        .collect()
}

pub struct Formula {
    /// Ink and accent letters as coverage masks over their pixel-aligned rect.
    ink: Option<(Tile, [f64; 4])>,
    accent: Option<(Tile, [f64; 4])>,
    pub bbox: [f64; 4],
    glow: Tile,
    glow_box: [f64; 4],
    motes: Vec<[f64; 6]>,
    start: f64,
    end: f64,
    tint: &'static str,
    mark: &'static str,
    pub left: f64,
    pub leaves: f64,
}

/// A coverage mask of the shape over the whole pixels round it, into the atlas.
fn letters(atlas: &mut Atlas, shape: &Shape) -> Option<(Tile, [f64; 4])> {
    if shape.is_empty() {
        return None;
    }
    let r = shape.rect();
    let (x0, y0) = (r[0].floor() - 1.0, r[1].floor() - 1.0);
    let (w, h) = ((r[0] + r[2]).ceil() + 1.0 - x0, (r[1] + r[3]).ceil() + 1.0 - y0);
    let cover = shape.raster(x0, y0, w as usize, h as usize, 1.0);
    Some((atlas.add_mask(&cover, w as usize, h as usize), [x0, y0, w, h]))
}

/// Python's random.sample(range(n), k).
fn sample(rnd: &mut PyRandom, n: usize, k: usize) -> Vec<usize> {
    let mut setsize = 21usize;
    if k > 5 {
        setsize += 4usize.pow(((3 * k) as f64).log(4.0).ceil() as u32);
    }
    if n <= setsize {
        let mut pool: Vec<usize> = (0..n).collect();
        (0..k)
            .map(|i| {
                let j = rnd.below(n - i);
                let out = pool[j];
                pool[j] = pool[n - i - 1];
                out
            })
            .collect()
    } else {
        let mut picked = std::collections::HashSet::new();
        (0..k)
            .map(|_| {
                let mut j = rnd.below(n);
                while picked.contains(&j) {
                    j = rnd.below(n);
                }
                picked.insert(j);
                j
            })
            .collect()
    }
}

pub struct Style {
    pub start: f64,
    pub end: f64,
    pub tint: &'static str,
    pub mark: &'static str,
}

/// _lit: letters already set as shapes, lit in chalk, with the dust they crumble into.
pub fn lit(fonts_px: f64, ink: &Shape, accent: &Shape, style: Style, atlas: &mut Atlas, rnd: &mut PyRandom) -> Formula {
    let px = fonts_px;
    let mut both = ink.clone();
    both.add(accent);
    let bbox = both.rect();
    let gb = [bbox[0] - px * 0.7, bbox[1] - px * 0.7, bbox[2] + px * 1.4, bbox[3] + px * 1.4];
    let (w, h) = (round_even(gb[2] * SOFT).max(1.0) as usize, round_even(gb[3] * SOFT).max(1.0) as usize);
    let shape = both.raster(gb[0], gb[1], w, h, SOFT);
    let glow = atlas.add(&halo(&shape, w, h, px, style.tint));
    let hits: Vec<usize> = (0..w * h).filter(|&i| shape[i] > 0.5).collect();
    let motes = sample(rnd, hits.len(), hits.len().min(34))
        .into_iter()
        .map(|i| {
            let (x, y) = ((hits[i] % w) as f64, (hits[i] / w) as f64);
            let x0 = gb[0] + (x + 0.5) / SOFT;
            let y0 = gb[1] + (y + 0.5) / SOFT;
            let k = px / 26.0;
            [x0, y0, rnd.uniform(18.0, 46.0) * k, rnd.uniform(-12.0, 12.0) * k, rnd.uniform(0.7, 1.9) * k, rnd.uniform(0.0, 0.45)]
        })
        .collect();
    let (ink, accent) = (letters(atlas, ink), letters(atlas, accent));
    Formula { ink, accent, bbox, glow, glow_box: gb, motes, start: style.start, end: style.end, tint: style.tint, mark: style.mark, left: 0.0, leaves: 4.2 }
}

/// _formula: an equation set px high, its baseline starting at `at` (ending there, if `ends`).
pub fn formula(fonts: &Fonts, items: &[Item], px: f64, at: Pt, ends: bool, style: Style, atlas: &mut Atlas, rnd: &mut PyRandom) -> Formula {
    let (mut ink, mut accent) = (Shape::default(), Shape::default());
    let small = px * 0.62;
    let mut x = 0.0;
    let mut last = (0.0, 0.0, 0.0);
    let mut script: Option<(bool, f64)> = None;
    for item in items {
        let mut next_script = None;
        match item {
            Item::T(text, acc) | Item::Han(text, acc) => {
                let han = matches!(item, Item::Han(..));
                let out = if *acc { &mut accent } else { &mut ink };
                let advance = out.add_text(fonts, han, px, [x, 0.0], text);
                last = (x, x + advance, px * 0.66);
                x += advance;
            }
            Item::Sup(text) | Item::Sub(text) => {
                let sup = matches!(item, Item::Sup(_));
                let stacked = script.is_some_and(|(s, _)| s != sup);
                let left = if stacked { script.map_or(x, |s| s.1) } else { x };
                let advance = ink.add_text(fonts, false, small, [left + px * 0.03, if sup { -px * 0.42 } else { px * 0.24 }], text);
                x = f64::max(x, left + px * 0.03 + advance);
                next_script = Some((sup, left));
            }
            Item::Under(text) => {
                let advance = fonts.advance(false, small, text);
                let middle = (last.0 + last.1) / 2.0;
                ink.add_text(fonts, false, small, [middle - advance / 2.0, last.2], text);
                x = f64::max(x, middle + advance / 2.0);
            }
            Item::Root(text) => {
                let mut sign = Shape::default();
                let wide = sign.add_text(fonts, false, px, [x, 0.0], "√");
                let top = if sign.is_empty() { -px * 0.8 } else { sign.rect()[1] };
                ink.add(&sign);
                x += wide;
                let advance = fonts.advance(false, px, text);
                ink.add_rect(x - px * 0.04, top, advance + px * 0.1, px * 0.055);
                ink.add_text(fonts, false, px, [x + px * 0.03, 0.0], text);
                x += advance + px * 0.1;
            }
            Item::Frac(top, bottom) => {
                let fp = px * 0.74;
                let (a, b) = (fonts.advance(false, fp, top), fonts.advance(false, fp, bottom));
                let span = a.max(b) + px * 0.24;
                let axis = -px * 0.3;
                ink.add_rect(x + px * 0.04, axis - px * 0.03, span - px * 0.08, px * 0.055);
                ink.add_text(fonts, false, fp, [x + (span - a) / 2.0, axis - px * 0.16], top);
                ink.add_text(fonts, false, fp, [x + (span - b) / 2.0, axis + px * 0.16 + fonts.ascent(false, fp) * 0.78], bottom);
                x += span;
            }
        }
        script = next_script;
    }
    let at = if ends { [at[0] - x, at[1]] } else { at };
    ink.translate(at[0], at[1]);
    accent.translate(at[0], at[1]);
    let mut f = lit(px, &ink, &accent, style, atlas, rnd);
    f.left = at[0];
    f
}

/// _brace: a left curly brace in a chalk line, its point at x's left, from top to bottom.
pub fn brace(x: f64, top: f64, bottom: f64, px: f64) -> Shape {
    let wide = px * 0.34;
    let middle = (top + bottom) / 2.0;
    let bend = (wide * 0.9).min((bottom - top) / 6.0);
    let (stem, tip) = (x - wide * 0.5, x - wide);
    let mut points = vec![[x, top]];
    let quad = |c: Pt, b: Pt, points: &mut Vec<Pt>| {
        let a = *points.last().expect("starts with a point");
        points.extend((1..=16).map(|i| super::text::quad_at(a, c, b, f64::from(i) / 16.0)));
    };
    quad([stem, top], [stem, top + bend], &mut points);
    points.push([stem, middle - bend]);
    quad([stem, middle], [tip, middle], &mut points);
    quad([stem, middle], [stem, middle + bend], &mut points);
    points.push([stem, bottom - bend]);
    quad([stem, bottom], [x, bottom], &mut points);
    let mut shape = Shape::default();
    shape.add_stroke(points, px * 0.065 / 2.0);
    shape
}

/// A pixel clip as Qt keeps a QRectF clip: its edges rounded to whole pixels.
fn clip(x: f64, y: f64, w: f64, h: f64) -> [f64; 4] {
    [x.round(), y.round(), (x + w).round(), (y + h).round()]
}

impl Formula {
    fn letters(&self, f: &mut Frame, t: f64, base: f64, lift: f64, cut: [f64; 4]) {
        let g = self.glow_box;
        f.opacity = base * (0.85 + 0.15 * (t * 2.2 + self.start * 3.0).sin());
        f.image(self.glow, Place { rect: [g[0], g[1] - lift, g[2], g[3]], clip: cut, poly: None }, 1.0);
        f.opacity = base;
        for (part, color, alpha) in [(&self.ink, INK, 0.95), (&self.accent, self.mark, 0.98)] {
            if let Some((tile, r)) = part {
                f.mask(*tile, Place { rect: [r[0], r[1] - lift, r[2], r[3]], clip: cut, poly: None }, color, alpha);
            }
        }
    }

    pub fn paint(&self, f: &mut Frame, t: f64, u: f64, life: f64) {
        let write = win(t, self.start, self.end);
        if write <= 0.0 {
            return;
        }
        let gone = ease_in_out(win(t, self.leaves, self.leaves + 0.6));
        let (g, b) = (self.glow_box, self.bbox);
        if gone < 1.0 {
            let feather = 26.0 * u;
            let front = g[0] + (g[2] + feather) * ease_in_out(write);
            let base = life * (1.0 - gone);
            let lift = 6.0 * u * gone;
            // _written: all of it up to the front, the last of it fading in 4 slices.
            let done = front - feather;
            if done >= g[0] + g[2] {
                self.letters(f, t, base, lift, [-1e6, -1e6, 1e6, 1e6]);
            } else {
                if done > g[0] {
                    self.letters(f, t, base, lift, clip(g[0], g[1] - lift, done - g[0], g[3]));
                }
                for i in 0..4 {
                    let left = done + feather * f64::from(i) / 4.0;
                    let right = left + feather / 4.0;
                    if right <= g[0] || left >= g[0] + g[2] {
                        continue;
                    }
                    let l = left.max(g[0]);
                    self.letters(f, t, base * (1.0 - (f64::from(i) + 0.5) / 4.0), lift, clip(l, g[1] - lift, right - l, g[3]));
                }
            }
            let nib = b[0].max(front - feather * 0.6);
            if write < 1.0 && nib < b[0] + b[2] {
                let y = b[1] + b[3] * (0.5 + 0.3 * (t * 31.0 + self.start * 7.0).sin());
                f.opacity = life;
                f.soft_dot(nib, y, 15.0 * u, self.tint, 0.55);
                f.soft_dot(nib, y, 4.0 * u, "#ffffff", 0.9);
            }
        }
        if gone > 0.0 {
            f.opacity = life;
            for &[x, y, rise, sway, r, delay] in &self.motes {
                let k = clamp((gone - delay) / (1.0 - delay));
                if k <= 0.0 || k >= 1.0 {
                    continue;
                }
                let a = (PI * k).sin() * (1.0 - k * 0.4);
                let (px, py) = (x + sway * k, y - rise * ease_out(k));
                f.circle(px, py, r, &super::prim::solid(INK, 0.8 * a));
                if r > 1.3 * u {
                    f.soft_dot(px, py, r * 4.0, self.tint, 0.35 * a);
                }
            }
        }
    }
}
