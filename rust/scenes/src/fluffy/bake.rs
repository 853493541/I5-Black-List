//! The scene's stickers worked out per pixel, as fluffy.py's _shade, _sticker and _fur do: each part
//! a mask tinted its color, swelling from its edges, lit from the top left with teal in its shade,
//! a paper grain or fine strands of fur, a soft shadow, then outlined by hand in ink.

use std::collections::HashMap;

use super::lines::inked;
use super::pixels::{blur, coverage, gradient, mask, noise, pyround, Canvas, Plane, Shape};
use super::{rgb, PINK, TEAL};
use crate::draw::Pt;
use crate::pyrand::PyRandom;

/// The shapes Qt builds (path booleans, strokes, the tab's words) at unit size: see shapes.txt.
pub struct Item {
    pub color: [f32; 3],
    pub a: f64,
    pub width: f64,
    pub polys: Shape,
}

pub struct Shapes(HashMap<String, Item>);

impl Shapes {
    pub fn load() -> Self {
        let mut items = HashMap::new();
        let mut current: Option<(String, Item)> = None;
        for line in include_str!("shapes.txt").lines() {
            let mut words = line.split_ascii_whitespace();
            match words.next() {
                Some("item") => {
                    let key = words.next().unwrap_or_default().to_string();
                    let color = crate::draw::hex(words.next().unwrap_or("#000000"));
                    let mut num = || words.next().and_then(|w| w.parse::<f64>().ok()).unwrap_or(0.0);
                    let (a, width) = (num(), num());
                    if let Some((k, v)) = current.replace((key, Item { color, a, width, polys: Vec::new() })) {
                        items.insert(k, v);
                    }
                }
                Some("poly") => {
                    let sign: f32 = words.next().and_then(|w| w.parse().ok()).unwrap_or(1.0);
                    let v: Vec<f64> = words.filter_map(|w| w.parse().ok()).collect();
                    if let Some((_, item)) = current.as_mut() {
                        item.polys.push((sign, v.chunks(2).map(|c| [c[0], c[1]]).collect()));
                    }
                }
                _ => {}
            }
        }
        if let Some((k, v)) = current {
            items.insert(k, v);
        }
        Self(items)
    }

    pub fn has(&self, key: &str) -> bool {
        self.0.contains_key(key)
    }

    pub fn item(&self, key: &str) -> &Item {
        &self.0[key]
    }

    /// An item's polygons times k.
    pub fn shape(&self, key: &str, k: f64) -> Shape {
        self.item(key).polys.iter().map(|(s, p)| (*s, p.iter().map(|q| [q[0] * k, q[1] * k]).collect())).collect()
    }

    /// An item's points times k (boxes and middles).
    pub fn points(&self, key: &str, k: f64) -> Vec<Pt> {
        self.shape(key, k).remove(0).1
    }
}

/// A sticker: its picture and the box (x, y, w, h, in points) it fills.
pub struct Pic {
    pub canvas: Canvas,
    pub rect: [f64; 4],
}

/// One part of a sticker: its shape (points), color and lift.
pub struct Part {
    pub shape: Shape,
    pub color: [f32; 3],
    pub lift: f64,
}

/// An outline gone over in ink, or a fill drawn on top (after): shape, width or alpha, color.
pub struct Ink {
    pub shape: Shape,
    pub width: f64,
    pub color: [f32; 3],
}

pub struct Look {
    pub soft: f64,
    pub gloss: f64,
    pub grain: f64,
    pub seed: u32,
    pub shadow: f64,
    /// Fur: strands from this middle, a blush there, shade deepening toward the line at cut.
    pub fur: bool,
    pub middle: Option<Pt>,
    pub blush: Option<Shape>,
    pub cut: Option<f64>,
}

const LIGHT_RAW: [f64; 3] = [-0.45, -0.6, 0.66];

fn unit(v: [f64; 3]) -> [f32; 3] {
    let n = (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]).sqrt();
    [(v[0] / n) as f32, (v[1] / n) as f32, (v[2] / n) as f32]
}

pub fn light() -> [f32; 3] {
    unit(LIGHT_RAW)
}

fn half() -> [f32; 3] {
    let l = light();
    unit([f64::from(l[0]), f64::from(l[1]), f64::from(l[2]) + 1.0])
}

/// Shapes in rect (points) as one sticker of `scale` pixels to the point.
pub fn sticker(rect: [f64; 4], scale: f64, parts: &[Part], look: &Look, outline: &[Ink], after: &[Ink]) -> Pic {
    let (w, h) = (((rect[2] * scale).ceil() as usize).max(1), ((rect[3] * scale).ceil() as usize).max(1));
    let (sx, sy) = (w as f64 / rect[2], h as f64 / rect[3]);
    let place = move |p: Pt| [(p[0] - rect[0]) * sx, (p[1] - rect[1]) * sy];
    let mut color = [Plane::new(w, h), Plane::new(w, h), Plane::new(w, h)];
    let mut alpha = Plane::new(w, h);
    let mut swell = Plane::new(w, h);
    let soft = look.soft * scale;
    for part in parts {
        let m = mask(w, h, &part.shape, &place);
        for (c, plane) in color.iter_mut().enumerate() {
            *plane = plane.zip(&m, |v, k| v + (part.color[c] - v) * k);
        }
        alpha = alpha.zip(&m, f32::max);
        if part.lift != 0.0 {
            let b = blur(&m, (soft * 0.45).max(1.0));
            let lift = part.lift as f32;
            swell = Plane { w, h, v: (0..w * h).map(|i| swell.v[i] + b.v[i] * m.v[i] * lift).collect() };
        }
    }
    let b = blur(&alpha, soft.max(1.0));
    swell = Plane { w, h, v: (0..w * h).map(|i| swell.v[i] + b.v[i] * alpha.v[i]).collect() };
    let (gy, gx) = gradient(&swell);
    let (l, hf, teal) = (light(), half(), rgb(TEAL));
    let k = (soft * 5.0) as f32;
    let grain = if look.fur { noise(w, h, 1.6 * scale, 2, look.seed) } else { noise(w, h, 3.0, 2, look.seed) };
    let strands = look.middle.map(|m| strands(w, h, rect, [sx, sy, scale], m, look.seed));
    let pink = rgb(PINK);
    let flush = look.blush.as_ref().map(|b| blur(&mask(w, h, b, &place), (soft * 0.6).max(1.0)).map(|v| v * 0.75));
    let mut lit = [Plane::new(w, h), Plane::new(w, h), Plane::new(w, h)];
    for i in 0..w * h {
        let (nx, ny) = (-gx.v[i] * k, -gy.v[i] * k);
        let nz = 1.0 / (1.0 + nx * nx + ny * ny).sqrt();
        let (nx, ny) = (nx * nz, ny * nz);
        let light = (nx * l[0] + ny * l[1] + nz * l[2]).clamp(0.0, 1.0);
        let facing = (nx * hf[0] + ny * hf[1] + nz * hf[2]).clamp(0.0, 1.0);
        let (sheen, shade, tone);
        if look.fur {
            sheen = facing.powi(8) * 0.1;
            let mut grain = grain.v[i] - 0.5;
            if let Some(st) = &strands {
                grain = st.v[i] + 0.4 * grain;
            }
            let mut s = (1.0 + 0.6 * (light - l[2])).clamp(0.0, 1.0);
            if let Some(cut) = look.cut {
                let deep = rect[3] * 0.22;
                let py = rect[1] + ((i / w) as f64 + 0.5) / sy;
                s *= 1.0 - 0.3 * ((py - cut + deep) / deep).clamp(0.0, 1.0).powf(1.5) as f32;
            }
            shade = s;
            tone = (1.0 + 0.16 * grain) * s;
        } else {
            sheen = facing.powi(26) * look.gloss as f32;
            shade = (1.0 + 0.55 * (light - l[2])).clamp(0.0, 1.0);
            tone = shade * (1.0 + look.grain as f32 * (grain.v[i] - 0.5) * 2.0);
        }
        let cool = if look.fur { 0.24 } else { 0.18 };
        for c in 0..3 {
            let mut v = color[c].v[i] * tone + (1.0 - shade) * cool * teal[c] + sheen;
            if let Some(f) = &flush {
                v += (pink[c] * shade - v) * f.v[i];
            }
            lit[c].v[i] = v;
        }
    }
    let shadow = look.shadow * scale;
    let mut canvas = if shadow > 0.0 {
        let drop = blur(&alpha.roll(pyround(shadow).max(1.0) as usize, 0), (shadow * 1.4).max(1.0)).map(|v| v * 0.32);
        let total = alpha.zip(&drop, |a, d| a + d * (1.0 - a));
        let under = rgb("#123a3e");
        let mixed: [Plane; 3] = std::array::from_fn(|c| Plane {
            w,
            h,
            v: (0..w * h).map(|i| (lit[c].v[i] * alpha.v[i] + under[c] * drop.v[i] * (1.0 - alpha.v[i])) / total.v[i].max(1e-4)).collect(),
        });
        Canvas::picture(&mixed, &total)
    } else {
        Canvas::picture(&lit, &alpha)
    };
    let mut rnd = PyRandom::new(look.seed);
    for ink in outline {
        let polys: Vec<Vec<Pt>> = ink.shape.iter().map(|(_, p)| p.clone()).collect();
        canvas.fill(&coverage(w, h, &inked(&polys, ink.width, &mut rnd), &place), ink.color, 1.0);
    }
    for fill in after {
        canvas.fill(&coverage(w, h, &fill.shape, &place), fill.color, fill.width);
    }
    Pic { canvas, rect }
}

/// Fur strands: noise drawn out along the lines from middle, fine round it and long along it,
/// showing more toward the edge.
fn strands(w: usize, h: usize, rect: [f64; 4], [sx, sy, scale]: [f64; 3], middle: Pt, seed: u32) -> Plane {
    let reach = rect[2].max(rect[3]) * 0.42;
    let count = pyround(2.0 * std::f64::consts::PI * reach * scale / 2.2).max(24.0) as usize;
    let at = |i: usize| {
        let x = (rect[0] + f64::from((i % w) as f32 + 0.5) / sx) as f32;
        let y = (rect[1] + f64::from((i / w) as f32 + 0.5) / sy) as f32;
        let (dx, dy) = (x - middle[0] as f32, y - middle[1] as f32);
        (dx, dy, dx.hypot(dy))
    };
    let half = (reach * 0.5) as f32;
    let top = (0..w * h).map(|i| at(i).2 / half).fold(0f32, f32::max);
    let rows = top as usize + 3;
    let grid = super::pcg::Rng::new(seed).grid(rows, count);
    let n = count as f32;
    let mut out = Plane::new(w, h);
    for (i, v) in out.v.iter_mut().enumerate() {
        let (dx, dy, rad) = at(i);
        let around = (dy.atan2(dx) / (2.0 * std::f32::consts::PI) + 0.5) * n;
        let out_k = rad / half;
        let i0 = around.floor();
        let f = around - i0;
        let i0 = (i0 as usize) % count;
        let i1 = (i0 + 1) % count;
        let j0 = out_k.floor();
        let g = out_k - j0;
        let g = g * g * (3.0 - 2.0 * g);
        let j0 = j0 as usize;
        let cell = |j: usize, c: usize| grid[j * count + c];
        let s = (cell(j0, i0) * (1.0 - f) + cell(j0, i1) * f) * (1.0 - g) + (cell(j0 + 1, i0) * (1.0 - f) + cell(j0 + 1, i1) * f) * g;
        *v = (s - 0.5) * (rad / reach as f32 - 0.2).clamp(0.0, 1.0);
    }
    out
}

/// An ink outline item from shapes.txt at size k.
pub fn outline(shapes: &Shapes, key: &str, k: f64) -> Ink {
    let item = shapes.item(key);
    Ink { shape: shapes.shape(key, k), width: item.width * k, color: item.color }
}

/// The cats' features and the tab's words: fills on top, alpha in `width`.
pub fn fills(shapes: &Shapes, prefix: &str, k: f64) -> Vec<Ink> {
    (0..)
        .map(|n| format!("{prefix}.feat{n}"))
        .take_while(|key| shapes.has(key))
        .map(|key| Ink { shape: shapes.shape(&key, k), width: shapes.item(&key).a, color: shapes.item(&key).color })
        .collect()
}

/// The parts of an item set: part0, part1, ... at size k.
pub fn parts(shapes: &Shapes, prefix: &str, k: f64) -> Vec<Part> {
    (0..)
        .map(|n| format!("{prefix}.part{n}"))
        .take_while(|key| shapes.has(key))
        .map(|key| Part { shape: shapes.shape(&key, k), color: shapes.item(&key).color, lift: shapes.item(&key).a })
        .collect()
}
