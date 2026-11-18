//! 数学公式, ported from blacklist_detect/love_scenes/equation.py: the blueprint night with the
//! heart's equations writing themselves in chalk, its Fourier circles tracing it, a cardioid in gold,
//! a golden spiral, drifting symbols, and the chalk crumbling to dust at the end.
//!
//! Its still light (the equations' glow, the heart's fill and bloom, the symbols) is worked out per
//! pixel once on the CPU as the Python scene does with numpy, kept in one atlas, and laid on by the
//! chip every frame with what moves. Letters come from the font files named in `text`.

pub mod atlas;
pub mod formula;
pub mod gpu;
pub mod heart;
pub mod light;
pub mod prim;
pub mod text;

use std::f64::consts::PI;

use atlas::{Atlas, Tile};
use formula::{brace, formula, it, lit, Formula, Item, Style};
use heart::{Heart, Readout};
use light::{blur, glow, rgb, round_even};
use prim::{stops, Frame, Paint, Place, HOLE};
use text::{Fonts, Shape};

use crate::draw::{clamp, ease_in, ease_in_out, ease_out, win, Pt};
use crate::pyrand::PyRandom;

pub const DURATION: f64 = 5.0;
const CHALK: &str = "#7fd8ff";
const INK: &str = "#eaf6ff";
const PINK: &str = "#ff9fc4";
const ROSE: &str = "#e0507f";
const NAVY: &str = "#0f2440";
const DEEP: &str = "#06142a";
const GOLD: &str = "#f3cf7a";
/// The equations' glow is worked out at this share of the stage's size and laid on scaled up.
const SOFT: f64 = 0.5;
const SYMBOLS: [char; 9] = ['π', 'Σ', '∞', '√', 'θ', '∫', 'φ', '∂', 'Δ'];
const DESIGN: [f64; 2] = [1635.0, 848.0];

type Rect = [f64; 4];

pub struct Equation {
    pub width: f64,
    pub height: f64,
    pub gap: Rect,
    u: f64,
    pub atlas: Atlas,
    formulas: Vec<Formula>,
    readout: Readout,
    heart: Heart,
    polar: (Pt, f64),
    spiral: Vec<(Rect, Pt, f64)>,
    numbers: Vec<(Tile, Rect)>,
    glyphs: Vec<Tile>,
    drift: Vec<(usize, f64, f64, f64, f64, f64, f64)>,
    boxes: Vec<Rect>,
}

impl Equation {
    /// love_scenes.sample_stage(width, height): the sample lobby's button gap at this size.
    pub fn sample(width: f64, height: f64, fonts: &Fonts) -> Self {
        let s = width / DESIGN[0];
        let keep = [549.0 * s, 749.0 * s, 556.0 * s, 94.0 * s];
        let gap = [keep[0] - 28.0 * s, keep[1] - 30.0 * s, keep[2] + 56.0 * s, height - keep[1] + 30.0 * s];
        Self::new(width, height, gap, fonts)
    }

    pub fn new(width: f64, height: f64, gap: Rect, fonts: &Fonts) -> Self {
        let u = (width / DESIGN[0]).min(height / DESIGN[1]);
        let mut rnd = PyRandom::new(23);
        let mut atlas = Atlas::new(2048);
        let st = |start, end, tint| Style { start, end, tint, mark: PINK };
        let px = 23.0 * u;
        let t_ = || it("t");
        let lower = [
            Item::T(it("y") + "(", false), Item::T(t_(), true), Item::T(") = 13 cos ".into(), false), Item::T(t_(), true),
            Item::T(" − 5 cos 2".into(), false), Item::T(t_(), true), Item::T(" − 2 cos 3".into(), false), Item::T(t_(), true),
            Item::T(" − cos 4".into(), false), Item::T(t_(), true),
        ];
        let lower = formula(fonts, &lower, px, [width - 22.0 * u, 66.0 * u], true, st(0.8, 1.65, CHALK), &mut atlas, &mut rnd);
        let upper = [Item::T(it("x") + "(", false), Item::T(t_(), true), Item::T(") = 16 sin".into(), false), Item::Sup("3".into()), Item::T(t_(), true)];
        let upper = formula(fonts, &upper, px, [lower.left, 35.0 * u], false, st(0.45, 0.95, CHALK), &mut atlas, &mut rnd);
        let line = brace(lower.left - px * 0.22, 35.0 * u - px * 0.86, 66.0 * u + px * 0.3, px);
        let brace = lit(px, &line, &Shape::default(), st(0.3, 0.5, CHALK), &mut atlas, &mut rnd);
        let heart_at = [width * 0.873, height * 0.177];
        let size = 152.0 * u;
        let k = size / 34.0;
        let origin = [heart_at[0], heart_at[1] + 2.5 * k];
        let mut readout = Readout::new([origin[0] - 21.0 * k - 16.0 * u, origin[1] + 8.0 * u], px * 1.05, fonts, &mut atlas, &mut rnd);
        let mut more = vec![
            (vec![Item::T(it("e"), false), Item::Sup(it("iπ")), Item::T(" + 1 = 0".into(), false)], 30.0 * u, [24.0 * u, height * 0.44], st(1.1, 1.75, CHALK)),
            (
                vec![
                    Item::T("∫".into(), false), Item::Sup("∞".into()), Item::Sub("−∞".into()), Item::T(format!(" {}", it("e")), false),
                    Item::Sup(format!("−{}²", it("x"))), Item::T(format!(" d{} = ", it("x")), false), Item::Root(it("π")),
                ],
                26.0 * u, [22.0 * u, height * 0.62], st(1.85, 2.6, CHALK),
            ),
            (vec![Item::T(it("r") + " = 1 − sin " + &it("θ"), false)], 27.0 * u, [width * 0.19, height * 0.085], st(1.0, 1.6, GOLD)),
            (vec![Item::T(it("φ") + " = ", false), Item::Frac("1 + √5".into(), "2".into())], 28.0 * u, [width * 0.718, height * 0.91], st(2.05, 2.7, GOLD)),
            (
                vec![
                    Item::T("lim".into(), false), Item::Under(it("t") + "→∞"), Item::T(" ".into(), false), Item::Han("心动".into(), true),
                    Item::T(format!("({}) = ", it("t")), false), Item::T("∞".into(), true),
                ],
                31.0 * u, [30.0 * u, height * 0.915], st(2.85, 3.6, PINK),
            ),
        ]
        .into_iter()
        .map(|(items, px, at, style)| formula(fonts, &items, px, at, false, style, &mut atlas, &mut rnd))
        .collect::<Vec<_>>();
        let mut formulas = vec![brace, upper, lower];
        formulas.append(&mut more);
        for (index, f) in formulas.iter_mut().enumerate() {
            f.leaves = 4.1 + 0.05 * (index + usize::from(index >= 3)) as f64;
        }
        readout.name.leaves = 2.45;
        let polar = ([width * 0.1, height * 0.12], 46.0 * u);
        let (gw, gh) = (136.0 * u * (1.0 + 5f64.sqrt()) / 2.0, 136.0 * u);
        let golden = [width - 14.0 * u - gw, height - 10.0 * u - gh, gw, gh];
        let spiral = spiral(golden);
        let numbers = numbers(&spiral, fonts, &mut atlas);
        let glyphs = glyphs(u, fonts, &mut atlas);
        let grow = |r: Rect, d: f64| [r[0] - d, r[1] - d, r[2] + 2.0 * d, r[3] + 2.0 * d];
        let mut boxes: Vec<Rect> = formulas.iter().take(3).chain([&readout.name]).chain(formulas.iter().skip(3)).map(|f| grow(f.bbox, 14.0 * u)).collect();
        boxes.push([origin[0] - 130.0 * u, 0.0, 260.0 * u, origin[1] + 100.0 * u]);
        boxes.push([polar.0[0] - 104.0 * u, 0.0, 208.0 * u, polar.0[1] + 104.0 * u]);
        boxes.push([golden[0] - 10.0 * u, golden[1] - 10.0 * u, golden[2] + 10.0 * u, golden[3] + 10.0 * u]);
        let drift = (0..22)
            .map(|i| {
                let x = if i % 3 == 0 { rnd.uniform(0.012, 0.1) } else { rnd.uniform(0.952, 0.988) } * width;
                let glyph = rnd.below(SYMBOLS.len());
                (glyph, x, rnd.uniform(0.25, 1.05) * height, rnd.uniform(18.0, 34.0) * u, rnd.uniform(0.6, 1.1), rnd.uniform(0.0, 6.28), rnd.uniform(0.0, 1.2))
            })
            .collect();
        let heart = Heart::new(heart_at, size, u, fonts, &mut atlas);
        Self { width, height, gap, u, atlas, formulas, readout, heart, polar, spiral, numbers, glyphs, drift, boxes }
    }

    /// The paper (equation.py's _paper), drawn once at full strength: navy at the edges, graph paper
    /// rubbed out over the names, a chalk-blue light behind the heart and the polar plot.
    pub fn paper(&self) -> Frame {
        let (width, height, u) = (self.width, self.height, self.u);
        let mut f = Frame::new();
        let top = height * 0.34;
        f.rect(0.0, 0.0, width, top, &Paint::Linear([0.0, 0.0], [0.0, top], stops(&[(0.0, DEEP, 0.84), (0.5, NAVY, 0.42), (1.0, NAVY, 0.0)])));
        let side = 215.0 * u;
        let edge = stops(&[(0.0, DEEP, 0.78), (0.45, NAVY, 0.4), (1.0, NAVY, 0.0)]);
        f.rect(0.0, 0.0, side, height, &Paint::Linear([0.0, 0.0], [side, 0.0], edge.clone()));
        f.rect(width - side, 0.0, side, height, &Paint::Linear([width, 0.0], [width - side, 0.0], edge.clone()));
        f.rect(0.0, height - side * 0.8, width, side * 0.8, &Paint::Linear([0.0, height], [0.0, height - side * 0.8], edge));
        let step = 22.0 * u;
        f.flags = HOLE;
        for i in 0..(width.max(height) / step) as usize + 2 {
            let strong = i % 5 == 0;
            let (alpha, pen) = if strong { (0.2, 1.1 * u) } else { (0.085, 0.8 * u) };
            let at = i as f64 * step;
            f.line([at, 0.0], [at, height], pen, CHALK, alpha);
            f.line([0.0, at], [width, at], pen, CHALK, alpha);
        }
        f.flags = 0;
        for (x, y, r) in [(0.873, 0.17, 300.0), (0.1, 0.14, 240.0)] {
            f.soft_dot(width * x, height * y, r * u, "#2d6fa8", 0.32);
        }
        f
    }

    /// Everything drawn at t seconds, over the lobby (layer 0) and with the paper (layer 1).
    pub fn paint(&self, t: f64) -> Frame {
        let (width, height, u) = (self.width, self.height, self.u);
        let mut f = Frame::new();
        f.picture(0, [width, height], self.gap, 1.0);
        let life = win(t, 0.0, 0.3);
        let leave = ease_in(win(t, 4.3, 5.0));
        f.opacity = life;
        f.picture(1, [width, height], self.gap, ease_out(win(t, 0.0, 0.8)) * (1.0 - leave));
        self.drift(&mut f, t, (1.0 - leave) * ease_out(win(t, 0.2, 1.0)));
        f.opacity = life;
        self.spiral_paint(&mut f, t, 1.0 - leave);
        self.polar_paint(&mut f, t, 1.0 - leave);
        self.heart.paint(&mut f, t, life);
        self.readout.paint(&mut f, t, 2.0 * PI * self.heart.lap(t), life);
        for (i, formula) in self.formulas.iter().enumerate() {
            if i == 3 {
                self.readout.name.paint(&mut f, t, u, life);
            }
            formula.paint(&mut f, t, u, life);
        }
        f
    }

    fn polar_paint(&self, f: &mut Frame, t: f64, fade: f64) {
        let a = ease_out(win(t, 0.45, 1.0)) * fade;
        if a <= 0.0 {
            return;
        }
        let (u, (o, s)) = (self.u, self.polar);
        for i in 1..5 {
            f.ring(o, s * 0.5 * f64::from(i), 0.9 * u, CHALK, if i % 2 == 0 { 0.3 } else { 0.16 } * a);
        }
        for i in 0..12 {
            let angle = f64::from(i) * PI / 6.0;
            f.line(o, [o[0] + angle.cos() * s * 2.15, o[1] - angle.sin() * s * 2.15], 0.9 * u, CHALK, if i % 3 == 0 { 0.3 } else { 0.14 } * a);
        }
        let at = |theta: f64| {
            let r = (1.0 - theta.sin()) * s;
            [o[0] + r * theta.cos(), o[1] - r * theta.sin()]
        };
        let plot = ease_in_out(win(t, 0.95, 2.6));
        if plot <= 0.0 {
            return;
        }
        let start = -PI / 2.0;
        let count = round_even(200.0 * plot).max(2.0) as usize;
        let curve: Vec<Pt> = (0..count).map(|i| at(start + 2.0 * PI * plot * i as f64 / (count - 1) as f64)).collect();
        for (w, color, alpha) in [(7.0, GOLD, 0.16), (2.6, GOLD, 0.6), (1.1, "#fff6dc", 0.95)] {
            f.stroke(&curve, w * u, color, alpha * a);
        }
        let theta = start + 2.0 * PI * plot + if plot >= 1.0 { (t - 2.6).max(0.0) * 1.6 } else { 0.0 };
        let point = at(theta);
        f.dashed(o, point, 1.1 * u, "#fff6dc", 0.6 * a);
        let sweep = round_even(theta.to_degrees().rem_euclid(360.0) * 16.0) / 16.0;
        let steps = (sweep / 3.0).ceil().max(1.0) as usize;
        let arc: Vec<Pt> = (0..=steps).map(|i| (sweep * i as f64 / steps as f64).to_radians()).map(|a| [o[0] + 0.3 * s * a.cos(), o[1] - 0.3 * s * a.sin()]).collect();
        if sweep > 0.0 {
            f.stroke(&arc, 1.1 * u, GOLD, 0.55 * a);
        }
        f.soft_dot(point[0], point[1], 16.0 * u, GOLD, 0.8 * a);
        f.soft_dot(point[0], point[1], 3.6 * u, "#ffffff", a);
    }

    fn spiral_paint(&self, f: &mut Frame, t: f64, fade: f64) {
        let grow = ease_in_out(win(t, 0.9, 3.0));
        if grow <= 0.0 || fade <= 0.0 {
            return;
        }
        let u = self.u;
        let n = self.spiral.len();
        let reached = grow * n as f64;
        let mut arc = Vec::new();
        for index in (0..n).rev() {
            let (sq, pivot, angle) = self.spiral[index];
            let k = clamp(reached - (n - 1 - index) as f64);
            if k <= 0.0 {
                break;
            }
            let corners = [[sq[0], sq[1]], [sq[0] + sq[2], sq[1]], [sq[0] + sq[2], sq[1] + sq[3]], [sq[0], sq[1] + sq[3]], [sq[0], sq[1]]];
            f.stroke(&corners, u, CHALK, 0.42 * fade * (k * 3.0).min(1.0));
            if index < self.numbers.len() && k >= 1.0 {
                let (tile, r) = self.numbers[index];
                f.mask(tile, Place::at(r), INK, 0.38 * fade);
            }
            let r = sq[2];
            for j in 0..=24 {
                let theta = angle - PI / 2.0 * (1.0 - f64::from(j) / 24.0 * k);
                arc.push([pivot[0] + r * theta.cos(), pivot[1] + r * theta.sin()]);
            }
        }
        if arc.len() < 2 {
            return;
        }
        for (w, color, alpha) in [(8.0, GOLD, 0.14), (3.0, GOLD, 0.55), (1.2, "#fff6dc", 0.95)] {
            f.stroke(&arc, w * u, color, alpha * fade);
        }
        if grow < 1.0 {
            let tip = arc[arc.len() - 1];
            f.soft_dot(tip[0], tip[1], 14.0 * u, GOLD, 0.8 * fade);
        }
    }

    /// Symbols drifting up the sides and twinkling, dimmed where an equation is. Their opacity
    /// replaces the painter's, as setOpacity does in the Python scene.
    fn drift(&self, f: &mut Frame, t: f64, a: f64) {
        if a <= 0.0 {
            return;
        }
        let side = 44.0 * self.u;
        for &(glyph, x, y0, speed, scale, phase, born) in &self.drift {
            let y = y0 - speed * t;
            let on = ease_out(win(t, born, born + 0.6));
            let twinkle = 0.55 + 0.45 * (t * 2.3 + phase).sin();
            let near = self.boxes.iter().map(|b| ((x - b[0] - b[2] / 2.0).abs() - b[2] / 2.0).max((y - b[1] - b[3] / 2.0).abs() - b[3] / 2.0)).fold(f64::MAX, f64::min);
            let alpha = 0.5 * a * on * twinkle * clamp(near / (24.0 * self.u));
            if alpha <= 0.01 {
                continue;
            }
            f.opacity = alpha;
            let r = side * scale;
            f.image(self.glyphs[glyph], Place::at([x - r / 2.0, y - r / 2.0, r, r]), 1.0);
        }
    }
}

/// The Fibonacci tiling of a golden rectangle, largest square first: (square, the corner its
/// quarter of the spiral turns about, the angle the quarter starts at going inward).
fn spiral(rect: Rect) -> Vec<(Rect, Pt, f64)> {
    let [mut x, mut y, mut w, mut h] = rect;
    (0..9)
        .map(|i| {
            let side = w.min(h);
            let cut = i % 4;
            let (sq, pivot) = match cut {
                0 => {
                    let sq = [x + w - side, y, side, side];
                    w -= side;
                    (sq, [sq[0], sq[1] + side])
                }
                1 => {
                    let sq = [x, y, side, side];
                    y += side;
                    h -= side;
                    (sq, [sq[0] + side, sq[1] + side])
                }
                2 => {
                    let sq = [x, y, side, side];
                    x += side;
                    w -= side;
                    (sq, [sq[0] + side, sq[1]])
                }
                _ => {
                    let sq = [x, y + h - side, side, side];
                    h -= side;
                    (sq, [sq[0], sq[1]])
                }
            };
            (sq, pivot, -f64::from(cut) * PI / 2.0)
        })
        .collect()
}

/// A text's coverage centred in a square, as drawText(rect, AlignCenter) sets it.
fn centred(fonts: &Fonts, px: f64, text: &str, sq: Rect) -> Shape {
    let (adv, asc) = (fonts.advance(false, px, text), fonts.ascent(false, px));
    let height = asc + fonts.descent(false, px);
    let mut shape = Shape::default();
    shape.add_text(fonts, false, px, [sq[0] + (sq[2] - adv) / 2.0, sq[1] + (sq[3] - height) / 2.0 + asc], text);
    shape
}

/// The Fibonacci numbers in the three largest squares, set once.
fn numbers(tiles: &[(Rect, Pt, f64)], fonts: &Fonts, atlas: &mut Atlas) -> Vec<(Tile, Rect)> {
    ["21", "13", "8"]
        .iter()
        .zip(tiles)
        .map(|(text, &(sq, _, _))| {
            let x0 = sq[0].floor();
            let y0 = sq[1].floor();
            let (w, h) = ((sq[0] + sq[2]).ceil() - x0, (sq[1] + sq[3]).ceil() - y0);
            let cover = centred(fonts, sq[2] * 0.2, text, sq).raster(x0, y0, w as usize, h as usize, 1.0);
            (atlas.add_mask(&cover, w as usize, h as usize), [x0, y0, w, h])
        })
        .collect()
}

/// Each drifting symbol lit once in chalk, a soft glow round a fine core.
fn glyphs(u: f64, fonts: &Fonts, atlas: &mut Atlas) -> Vec<Tile> {
    let side = round_even(44.0 * u).max(8.0);
    let n = side as usize;
    let chalk = rgb(CHALK);
    SYMBOLS
        .iter()
        .map(|g| {
            let shape = centred(fonts, 30.0 * u, &g.to_string(), [0.0, 0.0, side, side]).raster(0.0, 0.0, n, n, 1.0);
            let soft = blur(&shape, n, n, 2.5);
            let light: Vec<[f32; 3]> = shape.iter().zip(&soft).map(|(&s, &b)| chalk.map(|c| (b * 0.8 + s.powf(1.2) * 0.9) * c)).collect();
            atlas.add(&glow(&light, n, n))
        })
        .collect()
}

#[cfg(test)]
mod tests;
