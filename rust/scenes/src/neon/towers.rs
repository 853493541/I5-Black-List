//! The skyline as neon.py builds it: each side's towers kept out of the gap and off the names, their
//! outlines, windows, and their pictures worked out per pixel (steel and glass, neon rim, grain, lit
//! windows with their bloom), and the billboards' glyph pictures.

use super::raster::{blur, glow, grown, noise, picture, smooth, soft, Grid, Img, Light, Mask, Pt, Shape};
use super::{mix_hex, rgb, Rect, CYAN, MAGENTA};
use crate::pyrand::PyRandom;

type Row = (f64, f64, f64, bool, &'static str, f64, &'static str, f64);

const LEFT: [Row; 11] = [
    (-4.0, 96.0, 0.37, false, "flat", 0.0, "", 0.25),
    (86.0, 168.0, 0.29, false, "flat", 34.0, "", 0.32),
    (158.0, 210.0, 0.52, false, "slant", 0.0, "", 0.4),
    (236.0, 352.0, 0.862, false, "flat", 0.0, "", 0.5),
    (344.0, 470.0, 0.888, false, "flat", 0.0, "", 0.56),
    (-4.0, 36.0, 0.52, true, "flat", 0.0, "", 0.36),
    (22.0, 128.0, 0.25, true, "step", 74.0, "screen", 0.42),
    (120.0, 206.0, 0.46, true, "slant", 0.0, "", 0.5),
    (222.0, 322.0, 0.868, true, "sign", 0.0, "sign", 0.6),
    (318.0, 404.0, 0.905, true, "tank", 0.0, "", 0.66),
    (402.0, 502.0, 0.935, true, "flat", 0.0, "", 0.72),
];
const RIGHT: [Row; 9] = [
    (-4.0, 44.0, 0.33, false, "flat", 0.0, "", 0.28),
    (40.0, 96.0, 0.4, false, "flat", 28.0, "", 0.34),
    (96.0, 214.0, 0.862, false, "flat", 0.0, "", 0.48),
    (206.0, 330.0, 0.884, false, "flat", 0.0, "", 0.55),
    (-4.0, 26.0, 0.5, true, "flat", 0.0, "", 0.38),
    (12.0, 94.0, 0.27, true, "step", 64.0, "ticker", 0.44),
    (100.0, 246.0, 0.866, true, "sign", 0.0, "sign", 0.58),
    (242.0, 346.0, 0.912, true, "tank", 0.0, "", 0.64),
    (344.0, 486.0, 0.94, true, "flat", 0.0, "", 0.7),
];

pub struct Tower {
    pub left: f64,
    pub right: f64,
    pub top: f64,
    pub near: bool,
    pub crown: &'static str,
    pub spire: f64,
    pub show: &'static str,
    pub side: i32,
    pub rise: f64,
    pub lit: f64,
    pub seed: u32,
}

pub struct Outline {
    pub path: Vec<Shape>,
    pub tip: Option<Pt>,
    pub panel: Option<Rect>,
    pub blocks: Vec<Rect>,
    pub trim: Vec<[f64; 4]>,
}

/// neon._skyline: both sides' towers, far ones first.
pub fn skyline(width: f64, height: f64, gap: Rect, u: f64) -> Vec<Tower> {
    let (names_left, names_right) = (width * 0.13, width * 0.94);
    let under = height * 0.84 + 14.0 * u;
    let mut out = Vec::new();
    for (side, rows) in [(-1, &LEFT[..]), (1, &RIGHT[..])] {
        for (i, &(near_edge, far_edge, top, near, crown, spire, show, rise)) in rows.iter().enumerate() {
            let mut top = top * height;
            let (mut left, mut right, over);
            if side < 0 {
                (left, right) = (near_edge * u, (far_edge * u).min(gap[0] - 16.0 * u));
                over = right > names_left;
            } else {
                (left, right) = ((width - far_edge * u).max(gap[0] + gap[2] + 16.0 * u), width - near_edge * u);
                over = left < names_right;
            }
            if over && top < under {
                if spire != 0.0 || show == "screen" || show == "ticker" {
                    if side < 0 {
                        right = right.min(names_left - 3.0 * u);
                    } else {
                        left = left.max(names_right + 3.0 * u);
                    }
                } else {
                    top = under;
                }
            }
            if right - left < 14.0 * u {
                continue;
            }
            let seed = 40 + i as u32 + if side > 0 { 20 } else { 0 };
            out.push(Tower { left, right, top, near, crown, spire: spire * u, show, side, rise, lit: rise + 0.62 + 0.07 * (i % 3) as f64, seed });
        }
    }
    out
}

fn rect(x: f64, y: f64, w: f64, h: f64) -> Shape {
    Shape::Rect(x, y, w, h)
}

/// neon._tower_shape: the body to the bottom of the screen, its crown, its spire and its panel.
pub fn outline(t: &Tower, height: f64, u: f64) -> Outline {
    let mut rnd = PyRandom::new(t.seed);
    let (left, right, top) = (t.left, t.right, t.top);
    let w = right - left;
    let (mut path, mut blocks, mut trim) = (Vec::new(), Vec::new(), Vec::new());
    let (mut tip, mut panel) = (None, None);
    let mut spire_at = left + w * 0.68;
    let mut roof = top;
    match t.crown {
        "step" => {
            roof = top + 36.0 * u;
            for (share, y, tall) in [(0.25, top, 18.0 * u), (0.12, top + 16.0 * u, 22.0 * u)] {
                let b = [left + w * share, y, w * (1.0 - 2.0 * share), tall + 2.0 * u];
                path.push(rect(b[0], b[1], b[2], b[3]));
                blocks.push(b);
                trim.push([b[0] + 1.5 * u, b[1] + 0.8 * u, b[0] + b[2] - 1.5 * u, b[1] + 0.8 * u]);
            }
            trim.push([left + 1.5 * u, roof + 0.8 * u, right - 1.5 * u, roof + 0.8 * u]);
            spire_at = left + w / 2.0;
        }
        "slant" => {
            let fall = (28.0 * u).min(w * 0.35);
            let high_left = t.side > 0;
            let (a, b) = if high_left { (0.0, fall) } else { (fall, 0.0) };
            path.push(Shape::Poly(vec![[left, top + a], [right, top + b], [right, height + 2.0 * u], [left, height + 2.0 * u]]));
            roof = top + fall;
        }
        "tank" => {
            roof = top + 15.0 * u;
            let side = (17.0 * u).min(w * 0.3);
            let at = left + w * rnd.uniform(0.18, 0.5);
            path.push(rect(at, top + 3.5 * u, side, 8.0 * u));
            path.push(Shape::Poly(vec![[at - 0.6 * u, top + 3.8 * u], [at + side / 2.0, top], [at + side + 0.6 * u, top + 3.8 * u]]));
            for leg in [at + 1.5 * u, at + side - 3.0 * u] {
                path.push(rect(leg, top + 11.0 * u, 1.5 * u, roof - top - 10.0 * u));
            }
        }
        "sign" => {
            roof = top + 34.0 * u;
            let p = [left + w * 0.05, top, w * 0.9, 25.0 * u];
            path.push(rect(p[0], p[1], p[2], p[3]));
            for share in [0.22, 0.74] {
                path.push(rect(p[0] + p[2] * share, p[1] + p[3] - 1.0, 2.2 * u, roof - p[1] - p[3] + 2.0));
            }
            panel = Some(p);
        }
        _ => {
            for _ in 0..rnd.choice(&[1, 2]) {
                let box_w = w * rnd.uniform(0.14, 0.3);
                let box_h = rnd.uniform(3.5, 7.0) * u;
                path.push(rect(left + rnd.uniform(0.05, 0.9) * (w - box_w), top - box_h, box_w, box_h + 1.0));
            }
        }
    }
    let body = [left, roof, w, height + 2.0 * u - roof];
    path.push(rect(body[0], body[1], body[2], body[3]));
    blocks.push(body);
    if t.spire != 0.0 {
        let base = if t.crown == "step" { top } else { roof };
        let tp = [spire_at, base - t.spire];
        path.push(Shape::Poly(vec![[spire_at - 2.2 * u, base + 1.0], [spire_at - 0.55 * u, tp[1]], [spire_at + 0.55 * u, tp[1]], [spire_at + 2.2 * u, base + 1.0]]));
        path.push(rect(spire_at - 4.5 * u, base - t.spire * 0.45, 9.0 * u, 1.4 * u));
        tip = Some(tp);
    }
    if t.show == "screen" {
        panel = Some([left + w * 0.13, roof + 18.0 * u, w * 0.74, 52.0 * u]);
    } else if t.show == "ticker" {
        panel = Some([left + 4.0 * u, roof + 26.0 * u, w - 8.0 * u, 15.0 * u]);
    }
    Outline { path, tip, panel, blocks, trim }
}

fn intersects(a: Rect, b: Rect) -> bool {
    a[0] < b[0] + b[2] && b[0] < a[0] + a[2] && a[1] < b[1] + b[3] && b[1] < a[1] + a[3]
}

/// neon._windows: (where, color, how bright; 0 dark).
pub fn windows(t: &Tower, o: &Outline, u: f64) -> Vec<(Rect, &'static str, f64)> {
    let mut rnd = PyRandom::new(t.seed * 31);
    let ((px, py), (ww, wh)) = if t.near { ((6.0 * u, 8.6 * u), (3.0 * u, 4.0 * u)) } else { ((5.0 * u, 7.0 * u), (2.2 * u, 3.0 * u)) };
    let share = rnd.uniform(0.13, 0.22) * if t.near { 1.0 } else { 0.7 };
    let colors = ["#ffb767", "#ffc98a", "#ffc98a", "#ffd9a6", "#ffe8c8", "#dfefff", "#bcd8ff", "#7ff3ff", "#ff8fe6"];
    let clear = o.panel.map(|p| [p[0] - 3.0 * u, p[1] - 3.0 * u, p[2] + 6.0 * u, p[3] + 6.0 * u]);
    let mut out = Vec::new();
    for b in &o.blocks {
        let cols = ((b[2] - 5.0 * u) / px) as i64;
        if cols < 1 {
            continue;
        }
        let x0 = b[0] + (b[2] - cols as f64 * px) / 2.0 + (px - ww) / 2.0;
        let busy: Vec<f64> = (0..cols).map(|_| rnd.choice(&[0.2, 0.6, 1.0, 1.0, 1.6])).collect();
        let mut y = b[1] + 6.0 * u;
        while y + wh < b[1] + b[3] {
            let floor = if rnd.random() < 0.9 { rnd.choice(&[0.15, 0.4, 0.8, 1.0, 1.3, 4.0]) } else { 5.0 };
            for (c, &busy) in busy.iter().enumerate() {
                let cell = [x0 + c as f64 * px, y, ww, wh];
                if clear.is_some_and(|k| intersects(k, cell)) {
                    continue;
                }
                let lit = rnd.random() < share * busy * floor;
                let tone = rnd.choice(&colors);
                out.push((cell, tone, if lit { rnd.uniform(0.3, 1.0).powf(0.8) } else { 0.0 }));
            }
            y += py;
        }
    }
    out
}

/// A shape in points moved into a picture of `area` whose pixels are (sx, sy) points across.
fn placed(s: &Shape, area: Rect, sx: f64, sy: f64) -> Shape {
    let p = |q: Pt| [(q[0] - area[0]) * sx, (q[1] - area[1]) * sy];
    match s {
        Shape::Rect(x, y, w, h) => Shape::Rect((x - area[0]) * sx, (y - area[1]) * sy, w * sx, h * sy),
        Shape::Poly(pts) => Shape::Poly(pts.iter().map(|&q| p(q)).collect()),
        Shape::Line { a, b, half, reach, round } => Shape::Line { a: p(*a), b: p(*b), half: half * sx, reach: reach * sx, round: *round },
        Shape::Ring { c, r, half } => Shape::Ring { c: p(*c), r: r * sx, half: half * sx },
    }
}

/// neon._over: what the groups of shapes (each one path) paint in white over area, one pixel a point.
pub fn over(area: Rect, groups: &[Vec<Shape>]) -> Grid {
    let (w, h) = (area[2].ceil().max(1.0) as usize, area[3].ceil().max(1.0) as usize);
    let (sx, sy) = (w as f64 / area[2], h as f64 / area[3]);
    let mut m = Mask::new(w, h);
    for g in groups {
        let shapes: Vec<Shape> = g.iter().map(|s| placed(s, area, sx, sy)).collect();
        m.fill(&shapes, 1.0);
    }
    m.done()
}

pub fn bounds(shapes: &[Shape]) -> Rect {
    let mut b = [f64::MAX, f64::MAX, f64::MIN, f64::MIN];
    for s in shapes {
        if let Shape::Rect(x, y, w, h) = s {
            b = [b[0].min(*x), b[1].min(*y), b[2].max(x + w), b[3].max(y + h)];
        } else if let Shape::Poly(pts) = s {
            for p in pts {
                b = [b[0].min(p[0]), b[1].min(p[1]), b[2].max(p[0]), b[3].max(p[1])];
            }
        }
    }
    [b[0], b[1], b[2] - b[0], b[3] - b[1]]
}

fn axpy(c: &mut [f32; 3], t: [f32; 3], k: f32) {
    for i in 0..3 {
        c[i] += t[i] * k;
    }
}

/// neon._tower_art: where the tower goes, its body, and its lights with their bloom.
pub fn art(t: &Tower, o: &Outline, wins: &[(Rect, &str, f64)], height: f64, u: f64) -> (Rect, Img, Img) {
    let b = bounds(&o.path);
    let area = [b[0] - 5.0 * u, b[1] - 5.0 * u, b[2] + 10.0 * u, height - (b[1] - 5.0 * u)];
    let m = over(area, &[o.path.clone()]);
    let (w, h) = (m.w, m.h);
    let (sx, sy) = (area[2] as f32 / w as f32, area[3] as f32 / h as f32);
    let px = |i: usize| area[0] as f32 + (i as f32 + 0.5) * sx;
    let py = |j: usize| area[1] as f32 + (j as f32 + 0.5) * sy;
    let hf = height as f32;
    let (tint, rim_tint) = if t.side < 0 { (rgb(MAGENTA), rgb(CYAN)) } else { (rgb(CYAN), rgb(MAGENTA)) };
    let small = noise(w / 4 + 1, h / 4 + 1, (7.0 * u / 4.0).max(2.0), 2, t.seed);
    let grain = grown(&small, 4, w, h);
    let k = if t.side < 0 { 1 } else { w - 1 };
    let rim = soft(&Grid::from_fn(w, h, |x, y| (m.at(x, y) - m.at((x + k) % w, y)).clamp(0.0, 1.0)));
    let roof = soft(&Grid::from_fn(w, h, |x, y| (m.at(x, y) - m.at(x, (y + h - 1) % h)).clamp(0.0, 1.0)));
    let dark_shapes: Vec<Vec<Shape>> = wins.iter().filter(|w| w.2 <= 0.0).map(|(c, ..)| vec![rect(c[0], c[1], c[2], c[3])]).collect();
    let dark = over(area, &dark_shapes);
    let mut color: Light = Vec::with_capacity(w * h);
    let mut alpha = Vec::with_capacity(w * h);
    for j in 0..h {
        for i in 0..w {
            let n = j * w + i;
            let (x, y, mv) = (px(i), py(j), m.v[n]);
            let v = ((y - t.top as f32) / (hf - t.top as f32).max(1.0)).clamp(0.0, 1.0);
            let mut c = [0.0f32; 3];
            axpy(&mut c, rgb("#130c2c"), 1.0 - v);
            axpy(&mut c, rgb("#040210"), v);
            let mullion = 1.0 - 0.3 * smooth(0.8, 0.97, ((x - t.left as f32) / (6.0 * u) as f32).rem_euclid(1.0));
            c = c.map(|a| a * ((0.75 + 0.5 * grain.v[n]) * mullion));
            axpy(&mut c, tint, (-(hf - y) / (70.0 * u) as f32).exp() * 0.32);
            axpy(&mut c, rim_tint, rim.v[n] * mv * (0.2 + (1.0 - v).powi(3)));
            axpy(&mut c, rgb("#a294ff"), roof.v[n] * mv * 0.45);
            axpy(&mut c, rgb("#2c3070"), dark.v[n] * 0.16 * (1.0 - v * 0.7));
            let mut a = mv;
            if !t.near {
                let far = if t.side < 0 { rgb("#2a0f3c") } else { rgb("#0e1f48") };
                let haze: [f32; 3] = std::array::from_fn(|q| rgb("#1e1240")[q] * (1.0 - v) + far[q] * v);
                c = std::array::from_fn(|q| c[q] * 0.35 + haze[q] * 0.65);
                a = mv * 0.95;
            }
            color.push(c);
            alpha.push(a);
        }
    }
    let body = picture(w, h, &color, &alpha);
    // The lit windows and crown trim on black, as bytes, then their bloom at half size.
    let mut lit = vec![[0f32; 3]; w * h];
    let (fx, fy) = (w as f64 / area[2], h as f64 / area[3]);
    let paint = |shape: Shape, tone: [f32; 3], lit: &mut Vec<[f32; 3]>| {
        let shape = placed(&shape, area, fx, fy);
        let b = shape.bounds();
        let (x0, y0) = ((b[0] - 1.0).max(0.0) as usize, (b[1] - 1.0).max(0.0) as usize);
        let (x1, y1) = (((b[2] + 2.0).max(0.0) as usize).min(w), ((b[3] + 2.0).max(0.0) as usize).min(h));
        if x1 <= x0 || y1 <= y0 {
            return;
        }
        let mut one = Mask::new(x1 - x0, y1 - y0);
        one.fill(&[placed(&shape, [x0 as f64, y0 as f64, 1.0, 1.0], 1.0, 1.0)], 1.0);
        for (n, &c) in one.0.v.iter().enumerate() {
            if c > 0.0 {
                let p = &mut lit[(y0 + n / (x1 - x0)) * w + x0 + n % (x1 - x0)];
                *p = std::array::from_fn(|q| ((p[q] * (1.0 - c) + tone[q] * c) * 255.0 + 0.5).floor() / 255.0);
            }
        }
    };
    for (cell, tone, level) in wins {
        if *level > 0.0 {
            paint(rect(cell[0], cell[1], cell[2], cell[3]), mix_hex("#000000", tone, *level), &mut lit);
        }
    }
    for l in &o.trim {
        let tone = rgb(if t.side < 0 { CYAN } else { MAGENTA });
        paint(Shape::Line { a: [l[0], l[1]], b: [l[2], l[3]], half: 0.6 * u, reach: 0.0, round: false }, tone, &mut lit);
    }
    let (hw, hh) = (w / 2, h / 2);
    let halves: Vec<Grid> = (0..3).map(|q| Grid::from_fn(hw, hh, |x, y| (lit[2 * y * w + 2 * x][q] + lit[(2 * y + 1) * w + 2 * x + 1][q]) / 2.0)).collect();
    let halo: Vec<Grid> = halves.iter().map(|g| soft(&grown(&blur(g, 0.65).zip(&blur(g, 2.25), |a, b| a * 0.75 + b * 0.4), 2, w, h))).collect();
    let dim = if t.near { 1.0 } else { 0.45 };
    let light: Light = (0..w * h).map(|n| std::array::from_fn(|q| (lit[n][q] + halo[q].v[n] * 1.15) * dim)).collect();
    (area, body, glow(w, h, &light))
}
