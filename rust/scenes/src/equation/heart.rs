//! The hero (equation.py's _Heart and _Readout): labelled axes, the heart's Fourier circles tracing
//! it in one lap, the traced line lit and a quiet fill grown from the middle out, one beat and a
//! ripple; beside it t = 0.00 … 6.28 ticking in chalk.

use std::f64::consts::{PI, TAU};

use super::atlas::{Atlas, Tile};
use super::light::{bloom, blur, glow, halo, rgb, round_even};
use super::prim::{Frame, Place};
use super::text::{Fonts, Shape};
use super::{CHALK, INK, PINK, ROSE, SOFT};
use crate::draw::{clamp, ease_in_out, ease_out, heart_points, win, Pt};

type C = (f64, f64);

/// The heart curve's Fourier series, largest circle first: (turns per lap, its arm).
fn terms() -> Vec<(i32, C)> {
    let n = 64;
    let z: Vec<C> = (0..n)
        .map(|i| {
            let s = TAU * f64::from(i) / f64::from(n);
            let y = 13.0 * s.cos() - 5.0 * (2.0 * s).cos() - 2.0 * (3.0 * s).cos() - (4.0 * s).cos();
            (16.0 * s.sin().powi(3), -y)
        })
        .collect();
    let mut out: Vec<(i32, C)> = (0..n)
        .map(|k| {
            let (mut re, mut im) = (0.0, 0.0);
            for (i, &(a, b)) in z.iter().enumerate() {
                let ang = -TAU * f64::from(k) * i as f64 / f64::from(n);
                re += a * ang.cos() - b * ang.sin();
                im += a * ang.sin() + b * ang.cos();
            }
            (if k < n / 2 { k } else { k - n }, (re / f64::from(n), im / f64::from(n)))
        })
        .filter(|(_, c)| c.0.hypot(c.1) > 1e-6)
        .collect();
    out.sort_by(|a, b| b.1 .0.hypot(b.1 .1).total_cmp(&a.1 .0.hypot(a.1 .1)));
    out
}

/// The circles' centres along the chain, and its tip last, for a lap s in radians.
fn chain(terms: &[(i32, C)], s: f64) -> Vec<C> {
    let mut out = vec![(0.0, 0.0)];
    for &(k, (a, b)) in terms {
        let (c, sn) = ((f64::from(k) * s).cos(), (f64::from(k) * s).sin());
        let last = out[out.len() - 1];
        out.push((last.0 + a * c - b * sn, last.1 + a * sn + b * c));
    }
    out
}

fn scaled(points: &[Pt], about: Pt, k: f64) -> Vec<Pt> {
    points.iter().map(|p| [about[0] + (p[0] - about[0]) * k, about[1] + (p[1] - about[1]) * k]).collect()
}

fn closed(points: &[Pt]) -> Vec<Pt> {
    let mut out = points.to_vec();
    out.push(points[0]);
    out
}

pub struct Heart {
    centre: Pt,
    u: f64,
    k: f64,
    pub origin: Pt,
    middle: Pt,
    terms: Vec<(i32, C)>,
    curve: Vec<C>,
    outline: Vec<Pt>,
    bbox: [f64; 4],
    fill: Tile,
    line: Tile,
    labels: Option<(Tile, [f64; 4])>,
}

impl Heart {
    pub fn new(centre: Pt, size: f64, u: f64, fonts: &Fonts, atlas: &mut Atlas) -> Self {
        let k = size / 34.0;
        let terms = terms();
        let curve = (0..241).map(|i| chain(&terms, TAU * f64::from(i) / 240.0)[terms.len()]).collect();
        let outline = heart_points(centre[0], centre[1], size, 120);
        let bbox = [centre[0] - 22.0 * k, centre[1] - 15.0 * k, 44.0 * k, 35.0 * k];
        let mut heart = Self {
            centre,
            u,
            k,
            origin: [centre[0], centre[1] + 2.5 * k],
            middle: [centre[0], centre[1] + 3.5 * k],
            terms,
            curve,
            outline,
            bbox,
            fill: Tile::default(),
            line: Tile::default(),
            labels: None,
        };
        heart.light(atlas);
        heart.labels = heart.labels(fonts, atlas);
        heart
    }

    pub fn lap(&self, t: f64) -> f64 {
        ease_in_out(win(t, 0.6, 2.45))
    }

    /// The fill and the traced line's bloom, worked out per pixel once.
    fn light(&mut self, atlas: &mut Atlas) {
        let (b, k, u) = (self.bbox, self.k, self.u);
        let (w, h) = (round_even(b[2]).max(8.0) as usize, round_even(b[3]).max(8.0) as usize);
        let mut shape = Shape::default();
        let ring = closed(&self.outline);
        for pair in ring.windows(2) {
            shape.add_stroke(vec![], 0.0);
            shape.lines.push((pair[0], pair[1]));
        }
        shape.strokes.clear();
        let within = shape.raster(b[0], b[1], w, h, 1.0);
        let soft = blur(&within, w, h, 5.0 * k);
        let wide = blur(&within, w, h, 4.0 * k);
        let (rose, pink, white) = (rgb(ROSE), rgb(PINK), rgb("#fff2f7"));
        let light: Vec<[f32; 3]> = (0..w * h)
            .map(|i| {
                let v = within[i];
                let rim = ((v - soft[i]) * 2.2).clamp(0.0, 1.0) * v;
                let hx = ((i % w) as f64 + b[0] - self.centre[0]) / k;
                let hy = ((i / w) as f64 + b[1] - self.centre[1]) / k;
                let sheen = (-((hx + 7.0).powi(2) + (hy + 2.0).powi(2)) / 40.0).exp() as f32 * v;
                std::array::from_fn(|c| {
                    rose[c] * (0.07 * v) + pink[c] * (0.05 * v + 0.3 * rim.powf(1.4)) + white[c] * (0.09 * sheen) + rose[c] * (wide[i] * (1.0 - v) * 0.22)
                })
            })
            .collect();
        self.fill = atlas.add(&glow(&light, w, h));
        let mut pen = Shape::default();
        pen.add_stroke(ring, 1.2 * u);
        let line = pen.raster(b[0], b[1], w, h, 1.0);
        self.line = atlas.add(&bloom(&line, w, h, PINK, &[(2.5 * u, 0.9), (7.0 * u, 0.6), (16.0 * u, 0.35)], 0.8));
    }

    /// The axes' names and the numbers at their ticks, set once.
    fn labels(&self, fonts: &Fonts, atlas: &mut Atlas) -> Option<(Tile, [f64; 4])> {
        let (k, u, o) = (self.k, self.u, self.origin);
        let mut all = Shape::default();
        let mut put = |text: &str, px: f64, x: f64, y: f64, align: f64| {
            let mut path = Shape::default();
            path.add_text(fonts, false, px, [0.0, 0.0], text);
            let r = path.rect();
            path.translate(x - r[2] * align - r[0], y - r[1] - r[3] / 2.0);
            all.add(&path);
        };
        for value in [-8.0, 8.0] {
            let text = format!("{value}").replace('-', "−");
            put(&text, 12.0 * u, o[0] + value * k, o[1] + 11.0 * u, 0.5);
            put(&text, 12.0 * u, o[0] - 7.0 * u, o[1] - value * k, 1.0);
        }
        put(&super::formula::it("x"), 17.0 * u, o[0] + 21.0 * k + 2.0 * u, o[1] - 11.0 * u, 0.5);
        put(&super::formula::it("y"), 17.0 * u, o[0] + 9.0 * u, o[1] - 16.0 * k + 2.0 * u, 0.0);
        let r = all.rect();
        let (x0, y0) = (r[0].floor() - 1.0, r[1].floor() - 1.0);
        let (w, h) = ((r[0] + r[2]).ceil() + 1.0 - x0, (r[1] + r[3]).ceil() + 1.0 - y0);
        let cover = all.raster(x0, y0, w as usize, h as usize, 1.0);
        Some((atlas.add_mask(&cover, w as usize, h as usize), [x0, y0, w, h]))
    }

    fn point(&self, z: C, k: f64) -> Pt {
        [self.origin[0] + z.0 * k, self.origin[1] + z.1 * k]
    }

    pub fn paint(&self, f: &mut Frame, t: f64, life: f64) {
        let fade = 1.0 - ease_in_out(win(t, 4.25, 4.85));
        if fade <= 0.0 {
            return;
        }
        let u = self.u;
        let lap = self.lap(t);
        self.axes(f, t, fade, life);
        let grow = ease_out(win(t, 2.45, 3.3));
        let lit = ease_out(win(t, 2.35, 2.6));
        let beat = 1.0 + 0.06 * (PI * win(t, 3.3, 3.62)).sin();
        let m = self.middle;
        let at = |p: Pt| [m[0] + (p[0] - m[0]) * beat, m[1] + (p[1] - m[1]) * beat];
        let b = self.bbox;
        let rect = {
            let (a, c) = (at([b[0], b[1]]), at([b[0] + b[2], b[1] + b[3]]));
            [a[0], a[1], c[0] - a[0], c[1] - a[1]]
        };
        f.opacity = life;
        if grow > 0.0 {
            let front: Vec<Pt> = scaled(&self.outline, m, 0.04 + 0.98 * grow).into_iter().map(at).collect();
            f.opacity = life * fade;
            f.image(self.fill, Place { rect, clip: [-1e6, -1e6, 1e6, 1e6], poly: (grow < 1.0).then_some(&front[..]) }, 1.0);
            f.opacity = life;
            if grow < 1.0 {
                for (w, color, alpha) in [(6.0, PINK, 0.2), (1.4, "#ffffff", 0.6)] {
                    f.stroke(&closed(&front), w * u * beat, color, alpha * fade * (1.0 - grow));
                }
            }
        }
        if lit > 0.0 {
            let flash = 1.0 + 0.5 * (PI * win(t, 2.4, 3.0)).sin();
            f.opacity = life * clamp(lit * fade * 0.75 * flash);
            f.image(self.line, Place::at(rect), 1.0);
            f.opacity = life;
        }
        if lap > 0.0 {
            let done = lap * (self.curve.len() - 1) as f64;
            let mut trail: Vec<Pt> = self.curve[..done as usize + 1].iter().map(|&z| at(self.point(z, self.k))).collect();
            if lap < 1.0 {
                trail.push(at(self.point(chain(&self.terms, lap * TAU)[self.terms.len()], self.k)));
            }
            if trail.len() > 1 {
                for (w, color, alpha) in [(14.0, ROSE, 0.1 * (1.0 - lit)), (7.0, PINK, 0.2 * (1.0 - lit)), (3.0, "#ffc4da", 0.7), (1.2, "#ffffff", 0.95)] {
                    if alpha > 0.005 {
                        f.stroke(&trail, w * u * beat, color, alpha * fade);
                    }
                }
            }
        }
        let ripple = win(t, 3.32, 4.1);
        if 0.0 < ripple && ripple < 1.0 {
            let ring = closed(&scaled(&self.outline, m, 1.0 + 0.36 * ease_out(ripple)));
            for (w, color, alpha) in [(6.0, PINK, 0.16), (1.3, "#ffe0ec", 0.6)] {
                f.stroke(&ring, w * u, color, alpha * (1.0 - ripple) * fade);
            }
        }
        self.epicycles(f, t, lap * TAU);
    }

    fn axes(&self, f: &mut Frame, t: f64, fade: f64, life: f64) {
        let a = ease_out(win(t, 0.3, 0.8)) * (1.0 - 0.45 * ease_in_out(win(t, 2.5, 3.1))) * fade;
        if a <= 0.0 {
            return;
        }
        let (u, k, o) = (self.u, self.k, self.origin);
        f.opacity = life;
        let draw = ease_out(win(t, 0.3, 0.9));
        let (reach, up, down) = (21.0 * k * draw, 16.0 * k * draw, 16.0 * k * draw);
        f.line([o[0] - reach, o[1]], [o[0] + reach, o[1]], u, CHALK, 0.5 * a);
        f.line([o[0], o[1] - up], [o[0], o[1] + down], u, CHALK, 0.5 * a);
        for i in (-5..6).filter(|&i| i != 0) {
            let tick = if i % 2 == 0 { 4.5 } else { 2.5 } * u;
            let d = f64::from(i) * 4.0 * k;
            if d.abs() < reach {
                f.line([o[0] + d, o[1] - tick], [o[0] + d, o[1] + tick], u, CHALK, 0.5 * a);
            }
            if -up < d && d < down {
                f.line([o[0] - tick, o[1] + d], [o[0] + tick, o[1] + d], u, CHALK, 0.5 * a);
            }
        }
        for (tip, back) in [([o[0] + reach, o[1]], [-7.0 * u, 0.0]), ([o[0], o[1] - up], [0.0, 7.0 * u])] {
            let side = [back[1] * 0.4, back[0] * 0.4];
            let arrow = [tip, [tip[0] + back[0] + side[0], tip[1] + back[1] + side[1]], [tip[0] + back[0] - side[0], tip[1] + back[1] - side[1]]];
            f.poly(&arrow, &super::prim::solid(CHALK, 0.65 * a));
        }
        let names = ease_out(win(t, 0.6, 1.1));
        if let (true, Some((tile, r))) = (names > 0.0, self.labels) {
            f.mask(tile, Place::at(r), INK, 0.6 * a * names);
        }
    }

    fn epicycles(&self, f: &mut Frame, t: f64, s: f64) {
        let a = ease_out(win(t, 0.3, 0.75)) * (1.0 - ease_in_out(win(t, 2.45, 2.95)));
        if a <= 0.0 {
            return;
        }
        let (u, k, o) = (self.u, self.k, self.origin);
        let grow = ease_out(win(t, 0.3, 0.75));
        let links: Vec<Pt> = chain(&self.terms, s).into_iter().map(|z| self.point(z, k * grow)).collect();
        let tip = links[links.len() - 1];
        for foot in [[tip[0], o[1]], [o[0], tip[1]]] {
            f.dashed(tip, foot, u, PINK, 0.42 * a);
        }
        for foot in [[tip[0], o[1]], [o[0], tip[1]]] {
            f.soft_dot(foot[0], foot[1], 9.0 * u, PINK, 0.55 * a);
            f.soft_dot(foot[0], foot[1], 2.4 * u, "#ffffff", 0.85 * a);
        }
        for (&(_, c), &centre) in self.terms.iter().zip(&links) {
            let r = c.0.hypot(c.1) * k * grow;
            if r < 1.5 * u {
                continue;
            }
            for (w, alpha) in [(4.5, 0.1), (1.1, 0.55)] {
                f.ring(centre, r, w * u, CHALK, alpha * a);
            }
        }
        for (w, color, alpha) in [(4.0, CHALK, 0.18), (1.4, INK, 0.9)] {
            f.stroke(&links, w * u, color, alpha * a);
        }
        for c in &links[..links.len() - 1] {
            f.circle(c[0], c[1], 2.1 * u, &super::prim::solid(INK, 0.9 * a));
        }
        f.soft_dot(tip[0], tip[1], 22.0 * u, PINK, 0.8 * a);
        f.soft_dot(tip[0], tip[1], 5.0 * u, "#ffffff", a);
    }
}

/// t = 0.00 … 6.28: each figure's glow and letters set once for each of the four cells it can sit in.
pub struct Readout {
    pub name: super::formula::Formula,
    cells: Vec<Vec<(char, Tile, [f64; 4], Tile, [f64; 4])>>,
}

impl Readout {
    pub fn new(at: Pt, px: f64, fonts: &Fonts, atlas: &mut Atlas, rnd: &mut crate::pyrand::PyRandom) -> Self {
        use super::formula::{formula, it, Item, Style};
        let step = "0123456789".chars().map(|c| fonts.advance(false, px, &c.to_string())).fold(0.0, f64::max);
        let dot = fonts.advance(false, px, ".");
        let left = at[0] - (step * 3.0 + dot);
        let prefix = fonts.advance(false, px, &it("t")) + fonts.advance(false, px, " = ");
        let items = [Item::T(it("t"), true), Item::T(" = ".into(), false)];
        let name = formula(fonts, &items, px, [left - prefix, at[1]], false, Style { start: 0.45, end: 0.72, tint: CHALK, mark: PINK }, atlas, rnd);
        let starts = [left, left + step, left + step + dot, left + 2.0 * step + dot];
        let cells = starts
            .iter()
            .enumerate()
            .map(|(cell, &x)| {
                let (wide, chars) = if cell == 1 { (dot, ".") } else { (step, "0123456789") };
                chars.chars().map(|ch| Self::figure(fonts, atlas, px, ch, x, wide, at[1])).collect()
            })
            .collect();
        Self { name, cells }
    }

    fn figure(fonts: &Fonts, atlas: &mut Atlas, px: f64, ch: char, x: f64, wide: f64, base: f64) -> (char, Tile, [f64; 4], Tile, [f64; 4]) {
        let mut path = Shape::default();
        path.add_text(fonts, false, px, [0.0, 0.0], &ch.to_string());
        let r = path.rect();
        let bx = [r[0] - px * 0.5, r[1] - px * 0.5, r[2] + px, r[3] + px];
        let (w, h) = (round_even(bx[2] * SOFT).max(1.0) as usize, round_even(bx[3] * SOFT).max(1.0) as usize);
        let lit = atlas.add(&halo(&path.raster(bx[0], bx[1], w, h, SOFT), w, h, px, PINK));
        let shift = (wide - r[2]) / 2.0 - r[0];
        path.translate(x + shift, base);
        let p = path.rect();
        let (x0, y0) = (p[0].floor() - 1.0, p[1].floor() - 1.0);
        let (mw, mh) = ((p[0] + p[2]).ceil() + 1.0 - x0, (p[1] + p[3]).ceil() + 1.0 - y0);
        let mask = atlas.add_mask(&path.raster(x0, y0, mw as usize, mh as usize, 1.0), mw as usize, mh as usize);
        (ch, lit, [bx[0] + x + shift, bx[1] + base, bx[2], bx[3]], mask, [x0, y0, mw, mh])
    }

    pub fn paint(&self, f: &mut Frame, t: f64, value: f64, life: f64) {
        let a = ease_out(win(t, 0.55, 0.8)) * (1.0 - ease_in_out(win(t, 2.45, 2.95)));
        if a <= 0.0 {
            return;
        }
        f.opacity = life * a;
        for (cell, ch) in format!("{value:.2}").chars().enumerate().take(4) {
            if let Some(&(_, lit, at, mask, r)) = self.cells[cell].iter().find(|c| c.0 == ch) {
                f.image(lit, Place::at(at), 1.0);
                f.mask(mask, Place::at(r), "#fff2f7", 0.97);
            }
        }
    }
}
