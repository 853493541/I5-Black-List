//! cyber._Holo: a holographic panel drawn into a layer of its own and laid on as a whole: it opens
//! out of a bright line and flickers in, tears into color-split slices, surges when struck, flares
//! where the scan beam passes and folds back into a line at the end.

use std::f64::consts::PI;

use super::canvas::{col, Blend, Canvas, Src, ATLAS, LAYER, SCREEN, STROKE, RING};
use super::gfx::Atlas;
use super::light::{bloom, round_even, stroke, Plane};
use super::panels::{Mesh, Radar};
use super::CYAN;
use crate::draw::{ease_in, ease_in_out, ease_out, hex, win, Pt};
use crate::pyrand::PyRandom;

const FOLD: f64 = 4.1;

pub enum Kind {
    Radar(Radar),
    Mesh(Mesh),
}

pub struct Holo {
    pub b: [f64; 4],
    area: [f64; 4],
    kind: Kind,
    appear: f64,
    seed: u32,
    light: Src,
    u: f64,
}

/// What a canvas strokes, as an 8-bit gray mask (light.mask): gray as Qt turns a color to gray.
fn mask_of(c: &Canvas, w: usize, h: usize, origin: Pt, k: f64) -> Plane {
    let mut m = Plane::new(w, h);
    let at = |p: [f32; 2]| [(f64::from(p[0]) - origin[0]) * k, (f64::from(p[1]) - origin[1]) * k];
    for p in &c.prims {
        let a = f64::from(p.colors[0][3]);
        if a <= 0.0 || p.kind[1] != 0 {
            continue;
        }
        let rgb = [0, 1, 2].map(|i| (f64::from(p.colors[0][i]) / a * 255.0).round());
        let gray = ((rgb[0] * 11.0 + rgb[1] * 16.0 + rgb[2] * 5.0) / 32.0).floor() / 255.0;
        let pts: Vec<Pt> = match p.kind[0] {
            STROKE => {
                let (o, n) = (p.s0[0] as usize, p.s0[1] as usize);
                c.points[o..o + n].iter().map(|&q| at(q)).collect()
            }
            RING => (0..=64)
                .map(|i| {
                    let t = f64::from(i) / 64.0 * 2.0 * PI;
                    at([p.s0[0] + p.s0[2] * t.cos() as f32, p.s0[1] + p.s0[3] * t.sin() as f32])
                })
                .collect(),
            _ => continue,
        };
        let width = f64::from(if p.kind[0] == STROKE { p.s0[2] } else { p.s1[0] }) * 2.0 * k;
        stroke(&mut m, &pts, width, gray * a);
    }
    m
}

/// How lit a panel is: stuttering in as it opens, then a faint shimmer.
fn level(age: f64, t: f64, seed: f64) -> f64 {
    for (end, l) in [(0.12, 0.9), (0.17, 0.35), (0.25, 1.0), (0.3, 0.5), (0.42, 1.0), (0.46, 0.7)] {
        if age < end {
            return l;
        }
    }
    0.94 + 0.06 * (t * 31.0 + seed).sin() * (t * 5.3 + seed).sin()
}

impl Holo {
    pub fn new(b: [f64; 4], u: f64, kind: Kind, appear: f64, seed: u32, atlas: &mut Atlas) -> Self {
        let pad = 16.0 * u;
        let area = [b[0] - pad, b[1] - pad, b[2] + 2.0 * pad, b[3] + 2.0 * pad];
        let mut holo = Self { b, area, kind, appear, seed, light: [0.0; 4], u };
        let mut c = Canvas::new();
        holo.still(&mut c, false);
        let (w, h) = (round_even(area[2] * 0.5) as usize, round_even(area[3] * 0.5) as usize);
        let m = mask_of(&c, w, h, [area[0], area[1]], 0.5);
        holo.light = atlas.add(&bloom(&m, CYAN, &[(1.5, 0.55), (5.0, 0.45)], 0.0));
        holo
    }

    fn still(&self, c: &mut Canvas, lit: bool) {
        match &self.kind {
            Kind::Radar(r) => r.still(c, self.u),
            Kind::Mesh(m) => m.still(c, self.u, lit),
        }
    }

    #[allow(clippy::too_many_arguments)]
    pub fn paint(&self, c: &mut Canvas, t: f64, index: usize, tear: f64, surge: f64, beam: Option<f64>) {
        let age = t - self.appear;
        let end = FOLD + 0.12 * f64::from(self.seed);
        if age <= 0.0 || t > end + 0.62 {
            return;
        }
        let (u, a, b) = (self.u, self.area, self.b);
        let mid = [b[0] + b[2] / 2.0, b[1] + b[3] / 2.0];
        let spread = ease_out(win(age, 0.0, 0.14));
        let opened = ease_in_out(win(age, 0.1, 0.5));
        let fold = ease_in(win(t, end, end + 0.26));
        let shrink = ease_in(win(t, end + 0.26, end + 0.42));
        let lvl = level(age, t, f64::from(self.seed));
        let tear = tear.max(if age < 0.55 { 0.7 * (1.0 - opened) } else { 0.0 });
        let base = c.opacity;
        let saved = c.save();
        if opened > 0.0 && fold < 1.0 {
            let layer = LAYER[index];
            c.draw_into(layer, true);
            c.opacity = 1.0;
            c.lay(ATLAS, self.light, a, 1.0);
            self.still(c, true);
            match &self.kind {
                Kind::Radar(r) => r.moving(c, age, u),
                Kind::Mesh(m) => m.moving(c, age, u),
            }
            c.draw_into(SCREEN, false);
            c.restore(saved);
            let m = [1.0, 0.0, 0.0, 1.0 - fold, 0.0, mid[1] * fold];
            if opened < 1.0 {
                let half = opened * a[3] / 2.0;
                c.clip_to([a[0] - 60.0 * u, mid[1] - half, a[2] + 120.0 * u, 2.0 * half]);
            }
            let inner = c.save();
            let draw = |c: &mut Canvas, dx: f64, alpha: f64, tint: Option<[f32; 3]>| {
                c.picture(layer, a, [a[0] + dx, a[1], a[2], a[3]], m, alpha, tint);
            };
            if tear > 0.03 {
                let mut rnd = PyRandom::new(((t * 30.0) as u32) * 13 + self.seed);
                let split = (3.0 + 7.0 * tear) * u;
                let alpha = base * lvl;
                let mut y = a[1];
                while y < a[1] + a[3] {
                    let tall = rnd.uniform(5.0, 28.0) * u;
                    let shift = if rnd.random() < 0.55 { rnd.uniform(-24.0, 24.0) * u * tear } else { 0.0 };
                    c.restore(inner);
                    c.clip_to([a[0] - 60.0 * u, y, a[2] + 120.0 * u, tall + 0.5]);
                    c.blend(Blend::Plus);
                    c.opacity = alpha * 0.8 * tear;
                    draw(c, shift - split, 1.0, Some(hex("#ff2a55")));
                    draw(c, shift + split, 1.0, Some(hex("#2a7dff")));
                    c.blend(Blend::Over);
                    c.opacity = alpha * (1.0 - 0.25 * tear);
                    draw(c, shift, 1.0, None);
                    y += tall;
                }
                c.restore(inner);
            } else {
                c.opacity = base * lvl;
                draw(c, 0.0, 1.0, None);
            }
            c.blend(Blend::Plus);
            if surge > 0.02 {
                c.opacity = base * lvl * surge * 0.75;
                draw(c, 0.0, 1.0, None);
            }
            let roll = age.rem_euclid(2.3) / 1.1;
            if roll < 1.0 {
                let y = a[1] - 20.0 * u + roll * (a[3] + 40.0 * u);
                let keep = c.save();
                c.clip_to([a[0], y - 9.0 * u, a[2], 18.0 * u]);
                c.opacity = base * lvl * 0.35 * (PI * roll).sin();
                draw(c, 0.0, 1.0, None);
                c.restore(keep);
            }
            if let Some(x) = beam.filter(|&x| a[0] - 30.0 * u < x && x < a[0] + a[2] + 30.0 * u) {
                for (reach, alpha) in [(40.0, 0.1), (30.0, 0.12), (21.0, 0.15), (13.0, 0.2), (6.0, 0.25)] {
                    let keep = c.save();
                    c.clip_to([x - reach * u, a[1], 2.0 * reach * u, a[3]]);
                    c.opacity = base * alpha;
                    draw(c, 0.0, 1.0, None);
                    c.restore(keep);
                }
            }
            c.restore(saved);
        }
        let mut line = 0.0;
        if age < 0.6 {
            line = (1.0 - opened).powf(0.6) * spread;
        }
        if fold > 0.0 {
            line = f64::max(line, fold * fold * (1.0 - win(t, end + 0.42, end + 0.62)));
        }
        if line > 0.01 {
            let reach = b[2] / 2.0 * if age < 0.6 { spread } else { 1.0 - shrink * 0.98 };
            let half = if age < 0.6 { opened } else { 1.0 - fold } * a[3] / 2.0;
            c.blend(Blend::Plus);
            c.opacity = base;
            let ys = if half == 0.0 { vec![mid[1]] } else { vec![mid[1] - half, mid[1] + half] };
            for y in ys {
                for (w, color, alpha) in [(7.0, CYAN, 0.3), (2.6, "#9ffcff", 0.7), (1.1, "#ffffff", 1.0)] {
                    c.line([mid[0] - reach, y], [mid[0] + reach, y], w * u, &col(color, alpha * line), true);
                }
            }
            if shrink > 0.0 {
                c.star(mid[0], mid[1], (10.0 + 26.0 * shrink) * u, "#ffffff", line);
            }
        }
        c.restore(saved);
    }
}
