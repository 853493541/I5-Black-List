//! 冰蓝极光 Ice Aurora, ported from blacklist_detect/love_scenes/ice.py line for line: a sapphire
//! night wash, aurora curtains across the top (`aurora`), a heart of ice-blue glass (`heart`,
//! `glass`), frost growing from the bottom corners and prismatic diamond dust down the sides.
//!
//! A frame is three parts the renderer (`gpu`) draws in turn: the aurora at half size, the light
//! inside the heart at a quarter size, and the frame itself over the lobby, which lays both on.

pub mod aurora;
pub mod check;
pub mod glass;
pub mod gpu;
mod heart;
pub mod prim;
#[cfg(test)]
mod tests;

use std::f64::consts::PI;

use crate::draw::{ease_in, ease_out, hex, win, Pt};
use crate::pyrand::PyRandom;
use prim::{solid, stops, Frame, Paint};

pub const DURATION: f64 = 5.0;
const SAPPHIRE: &str = "#0b2a8a";
const WHITE: [f32; 3] = [1.0, 1.0, 1.0];
/// love_scenes.DESIGN: the size a scene's unit is measured against.
const DESIGN: [f64; 2] = [1635.0, 848.0];
const DUST: [&str; 5] = ["#9fe8ff", "#7ff2e6", "#a99bff", "#ffb4e6", "#6fb2ff"];

/// draw.heart_points with its start (in turns).
pub fn heart_points(cx: f64, cy: f64, size: f64, count: usize, start: f64) -> Vec<Pt> {
    (0..count)
        .map(|i| {
            let a = (start + i as f64 / count as f64) * 2.0 * PI;
            let x = 16.0 * a.sin().powi(3);
            let y = 13.0 * a.cos() - 5.0 * (2.0 * a).cos() - 2.0 * (3.0 * a).cos() - (4.0 * a).cos();
            [cx + x * size / 34.0, cy - (y - 2.5) * size / 34.0]
        })
        .collect()
}

/// draw.spectrum: a color along a looping list, each channel rounded to a byte.
pub fn spectrum(list: &[&str], k: f64) -> [f32; 3] {
    let k = k.rem_euclid(1.0);
    let n = list.len();
    let at = k * n as f64;
    let i = (at as usize) % n;
    let f = at - at.trunc();
    let (a, b) = (hex(list[i]), hex(list[(i + 1) % n]));
    std::array::from_fn(|c| ((f64::from(a[c]) * 255.0 + f64::from(b[c] - a[c]) * 255.0 * f).round_ties_even() / 255.0) as f32)
}

/// draw.mix of two colors, each channel rounded to a byte.
pub fn blend(a: [f32; 3], b: [f32; 3], k: f64) -> [f32; 3] {
    std::array::from_fn(|c| ((f64::from(a[c]) * 255.0 + (f64::from(b[c]) - f64::from(a[c])) * 255.0 * k).round_ties_even() / 255.0) as f32)
}

/// A frost segment: start, end, when it starts growing, depth.
struct Seg {
    a: Pt,
    b: Pt,
    born: f64,
    depth: u32,
}

struct Frost<'a> {
    rnd: &'a mut PyRandom,
    u: f64,
    segs: Vec<Seg>,
}

impl Frost<'_> {
    fn grow(&mut self, x: f64, y: f64, angle: f64, length: f64, depth: u32, born: f64) {
        if depth > 2 || length < 8.0 * self.u {
            return;
        }
        let (ex, ey) = (x + angle.cos() * length, y + angle.sin() * length);
        let speed = 360.0 * self.u;
        self.segs.push(Seg { a: [x, y], b: [ex, ey], born, depth });
        let end = born + length / speed;
        let steps = if depth == 0 { 3 } else { 2 };
        for s in 1..=steps {
            let k = f64::from(s) / f64::from(steps + 1) + self.rnd.uniform(-0.06, 0.06);
            let (bx, by) = (x + angle.cos() * length * k, y + angle.sin() * length * k);
            let at = born + length * k / speed;
            for turn in [60f64.to_radians(), (-60f64).to_radians()] {
                if self.rnd.random() < 0.8 {
                    let l = length * self.rnd.uniform(0.24, 0.34);
                    self.grow(bx, by, angle + turn, l, depth + 1, at);
                }
            }
        }
        if depth < 1 {
            let a = angle + self.rnd.uniform(-0.2, 0.2);
            self.grow(ex, ey, a, length * 0.45, depth + 1, end);
        }
    }
}

pub struct Ice {
    pub width: f64,
    pub height: f64,
    /// The bare area round the button, x, y, w, h.
    pub gap: [f64; 4],
    u: f64,
    frost: Vec<Seg>,
    /// born, x, y, fall, r, hue, phase.
    dust: Vec<[f64; 7]>,
    heart_at: Pt,
    /// Glints gathering on the heart: from, to, when.
    sparks: Vec<(Pt, Pt, f64)>,
    /// The glass picture's width in pixels (the heart's, at its largest).
    pub glass_px: usize,
}

/// What the renderer draws for one frame.
pub struct IceFrame {
    pub main: Frame,
    pub aurora: aurora::Aurora,
    /// The light inside the heart, at a quarter size: its shapes and its size in pixels.
    pub within: Option<(Frame, [u32; 2])>,
}

impl Ice {
    /// love_scenes.sample_stage(width, height): the sample lobby's button gap at this size.
    pub fn sample(width: f64, height: f64) -> Self {
        let s = width / DESIGN[0];
        let keep = [549.0 * s, 749.0 * s, 556.0 * s, 94.0 * s];
        let gap = [keep[0] - 28.0 * s, keep[1] - 30.0 * s, keep[2] + 56.0 * s, height - keep[1] + 30.0 * s];
        Self::new(width, height, gap)
    }

    pub fn new(width: f64, height: f64, gap: [f64; 4]) -> Self {
        let u = (width / DESIGN[0]).min(height / DESIGN[1]);
        let mut rnd = PyRandom::new(14);
        let heart_at = [width * 0.118, height * 0.175];
        let sparks = heart::sparks(heart_at, 150.0 * u, &mut PyRandom::new(15));
        let mut frost = Frost { rnd: &mut rnd, u, segs: Vec::new() };
        for (side, x) in [(1.0, 0.0), (-1.0, width)] {
            for (angle, length) in [(-74.0f64, 175.0), (-42.0, 135.0), (-10.0, 200.0)] {
                let a = if side > 0.0 { angle.to_radians() } else { PI - angle.to_radians() };
                let born = 0.35 + frost.rnd.uniform(0.0, 0.25);
                frost.grow(x, height + 2.0 * u, a, length * u, 0, born);
            }
        }
        let frost = frost.segs;
        // 6.28 as the Python scene has it, not TAU: the same numbers come out of the same seed.
        #[allow(clippy::approx_constant)]
        let dust = (0..46)
            .map(|_| {
                let born = rnd.uniform(0.3, 3.4);
                let x = if rnd.random() < 0.5 { rnd.uniform(0.0, 0.13) } else { rnd.uniform(0.87, 1.0) } * width;
                let y = rnd.uniform(-0.05, 0.75) * height;
                let (fall, r) = (rnd.uniform(18.0, 46.0) * u, rnd.uniform(1.6, 4.6) * u);
                [born, x, y, fall, r, rnd.random(), rnd.uniform(0.0, 6.28)]
            })
            .collect();
        let glass_px = ((150.0 * u * 1.14 / 8.0).ceil() * 8.0).max(16.0) as usize;
        Self { width, height, gap, u, frost, dust, heart_at, sparks, glass_px }
    }

    /// The night wash at full strength, drawn once into its own picture (the Python scene's Wash).
    pub fn wash(&self) -> Frame {
        let (width, height, u) = (self.width, self.height, self.u);
        let mut f = Frame::new();
        let top = 230.0 * u;
        let band = stops(&[(0.0, "#06164f", 0.62), (0.55, SAPPHIRE, 0.22), (1.0, SAPPHIRE, 0.0)]);
        f.rect(0.0, 0.0, width, top, &Paint::Linear([0.0, 0.0], [0.0, top], band));
        let edge = 150.0 * u;
        for (start, end, rect) in [
            ([0.0, 0.0], [edge, 0.0], [0.0, 0.0, edge, height]),
            ([width, 0.0], [width - edge, 0.0], [width - edge, 0.0, edge, height]),
            ([0.0, height], [0.0, height - edge], [0.0, height - edge, width, edge]),
        ] {
            let side = stops(&[(0.0, SAPPHIRE, 0.42), (1.0, SAPPHIRE, 0.0)]);
            f.rect(rect[0], rect[1], rect[2], rect[3], &Paint::Linear(start, end, side));
        }
        f
    }

    /// Everything drawn at t seconds over the lobby.
    pub fn paint(&self, t: f64) -> IceFrame {
        let (width, height) = (self.width, self.height);
        let mut f = Frame::new();
        f.backdrop(prim::LOBBY, [width, height], self.gap, 1.0);
        let life = win(t, 0.0, 0.35);
        let leave = ease_in(win(t, 4.1, 5.0));
        f.opacity = life;
        let wash = ease_out(win(t, 0.0, 0.8)) * (1.0 - leave);
        if wash > 0.005 {
            f.backdrop(prim::WASH, [width, height], self.gap, wash);
        }
        let aurora = aurora::Aurora::new(t, width, height, self.u, leave);
        if aurora.drawn() {
            f.image(prim::AURORA, [0.0, 0.0, width, aurora.band], [f64::from(aurora.size[0]), f64::from(aurora.size[1])], 1.0);
        }
        self.frost(&mut f, t, leave);
        self.dust(&mut f, t, 1.0 - leave);
        f.opacity = win(t, 0.0, 0.35);
        let within = self.heart(&mut f, t);
        IceFrame { main: f, aurora, within }
    }

    fn frost(&self, f: &mut Frame, t: f64, leave: f64) {
        let fade = 1.0 - leave;
        if fade <= 0.0 {
            return;
        }
        let u = self.u;
        let speed = 360.0 * u;
        let mut sides: [Vec<Pt>; 2] = [Vec::new(), Vec::new()];
        let mut tips = Vec::new();
        for s in &self.frost {
            let length = (s.b[0] - s.a[0]).hypot(s.b[1] - s.a[1]);
            let k = ((t - s.born) * speed / length.max(1e-3)).clamp(0.0, 1.0);
            if k <= 0.0 {
                continue;
            }
            let end = [s.a[0] + (s.b[0] - s.a[0]) * k, s.a[1] + (s.b[1] - s.a[1]) * k];
            sides[usize::from(s.a[0] > self.width / 2.0)].extend([s.a, end]);
            if k >= 1.0 && s.depth >= 1 {
                tips.push((s.b, s.depth));
            }
        }
        for (w, color, alpha) in [(5.0, "#5fb8ff", 0.25), (1.3, "#cdeeff", 0.85)] {
            for side in &sides {
                f.segments(side, w * u, &solid(color, alpha * fade));
            }
        }
        for (index, (p, depth)) in tips.into_iter().enumerate() {
            let r = (3.6 - 0.6 * f64::from(depth)) * u;
            let diamond = [[p[0], p[1] - r], [p[0] + r * 0.6, p[1]], [p[0], p[1] + r], [p[0] - r * 0.6, p[1]]];
            f.poly(&diamond, &solid("#ffffff", 0.8 * fade));
            if index % 5 != 0 {
                continue;
            }
            let twinkle = 0.5 + 0.5 * (t * 3.1 + index as f64).sin();
            let size = (7.0 + 4.0 * twinkle) * u;
            let pen = solid("#e9f8ff", 0.85 * fade * (0.5 + 0.5 * twinkle));
            for arm in 0..6 {
                let a = f64::from(arm * 60 + 15).to_radians();
                f.stroke(&[p, [p[0] + a.cos() * size, p[1] + a.sin() * size]], u, &pen);
                for side in [-1.0, 1.0] {
                    let b = a + side * 45f64.to_radians();
                    let mid = [p[0] + a.cos() * size * 0.6, p[1] + a.sin() * size * 0.6];
                    f.stroke(&[mid, [mid[0] + b.cos() * size * 0.3, mid[1] + b.sin() * size * 0.3]], u, &pen);
                }
            }
        }
    }

    fn dust(&self, f: &mut Frame, t: f64, a: f64) {
        let u = self.u;
        for &[born, x, y, fall, r, hue, phase] in &self.dust {
            let age = t - born;
            if age <= 0.0 || age > 3.2 {
                continue;
            }
            let fade = (age / 0.4).min(1.0) * ((3.2 - age) / 0.8).min(1.0) * a;
            let flash = (age * 4.2 + phase).sin().max(0.0).powi(3);
            let (px, py) = (x + 12.0 * u * (age * 1.2 + phase).sin(), y + fall * age);
            let color = spectrum(&DUST, hue + age * 0.3);
            f.soft_dot(px, py, r * 2.6, color, 0.55 * fade);
            f.star(px, py, r * (1.2 + 2.2 * flash), blend(color, WHITE, 0.6), fade * (0.4 + 0.6 * flash));
        }
    }
}

/// sin(pi k), for the heart's glints.
fn arc(k: f64) -> f64 {
    (PI * k).sin()
}
