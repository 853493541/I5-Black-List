//! neon.py's paint(): one frame of 霓虹都市 as shapes and pictures, in the Python painter's order.

use std::f64::consts::PI;

use crate::draw::{clamp, ease_in, ease_in_out, ease_out, mix, partial, win};
use crate::pyrand::PyRandom;

use super::frame::{rgba, Frame};
use super::raster::{round_even, Pt};
use super::sky::{far_light, strike_light};
use super::{fx, Built, Neon, Rect, CYAN, GLOW_BAND, MAGENTA};

/// neon._neon: off, then stuttering on as neon does, then a faint hum.
fn neon(t: f64, on: f64, seed: f64) -> f64 {
    let age = t - on;
    if age < 0.0 {
        return 0.0;
    }
    for (end, level) in [(0.05, 1.0), (0.1, 0.15), (0.16, 0.85), (0.2, 0.05), (0.26, 0.7), (0.3, 0.3)] {
        if age < end {
            return level;
        }
    }
    let hum = 0.93 + 0.07 * (t * 23.0 + seed).sin() * (t * 7.3 + seed * 2.0).sin();
    let dip = 1.0 - 0.55 * (PI * win(t, 2.6 + seed * 0.37, 2.68 + seed * 0.37)).sin().max(0.0);
    hum * dip
}

/// neon._power_down: 1 while on, stuttering to 0 at the end.
fn power_down(t: f64, seed: f64) -> f64 {
    let age = t - (4.3 + 0.08 * seed);
    if age < 0.0 {
        return 1.0;
    }
    for (end, level) in [(0.06, 0.2), (0.12, 0.9), (0.18, 0.1), (0.26, 0.6), (0.4, 0.25)] {
        if age < end {
            return level;
        }
    }
    (0.25 * (1.0 - (age - 0.4) / 0.25)).max(0.0)
}

fn shade(c: [f32; 3], alpha: f64) -> [f32; 4] {
    [c[0], c[1], c[2], clamp(alpha) as f32]
}

impl Neon {
    /// neon._lay_round: a screen-sized soft picture laid on only round `inner`, in four pieces cut on its own pixels.
    fn lay_round(&self, f: &mut Frame, id: usize, inner: Rect, at: &[[u32; 4]]) {
        let (w, h) = (f64::from(at[id][2]), f64::from(at[id][3]));
        let (width, height) = (self.width, self.height);
        let left = round_even(inner[0] * w / width);
        let right = round_even((inner[0] + inner[2]) * w / width);
        let top = round_even(inner[1] * h / height);
        let bottom = round_even((inner[1] + inner[3]) * h / height);
        for (x, y, x2, y2) in [(0.0, 0.0, w, top), (0.0, bottom, w, h), (0.0, top, left, bottom), (right, top, w, bottom)] {
            if x2 > x && y2 > y {
                let dest = [x * width / w, y * height / h, (x2 - x) * width / w, (y2 - y) * height / h];
                f.image(id, dest, Some([x, y, x2 - x, y2 - y]), [0.0, 0.0], 0.0, true, 1.0);
            }
        }
    }

    /// Everything drawn at t seconds over the lobby; `at` is where the atlas holds each picture.
    pub fn paint<'a>(&self, t: f64, at: &'a [[u32; 4]]) -> Frame<'a> {
        let (width, height, u) = (self.width, self.height, self.u);
        let mut f = Frame::new(at);
        f.lobby(width, height);
        let life = win(t, 0.0, 0.3);
        let leave = ease_in(win(t, 4.35, 5.0));
        f.opacity = life;
        let wash = ease_out(win(t, 0.0, 0.7)) * (1.0 - leave);
        if wash > 0.005 {
            f.wash(self.night, width, height, clamp(wash));
        }
        let bright = self.strikes.iter().map(|s| strike_light(t - s.when)).fold(0.0, f64::max);
        f.plus = true;
        for s in &self.strikes {
            let light = strike_light(t - s.when) * (1.0 - leave);
            if light > 0.01 {
                f.opacity = life * light;
                f.lay(s.cloud.1, s.cloud.0, true, 1.0);
            }
        }
        for &(when, rect, id) in &self.distant {
            let light = far_light(t - when) * (1.0 - leave);
            if light > 0.01 {
                f.opacity = life * light;
                f.lay(id, rect, true, 1.0);
            }
        }
        f.plus = false;
        for (side, &flash) in [-1.0, 1.0].iter().zip(&self.flashes) {
            let near = self.strikes.iter().map(|s| strike_light(t - s.when) * if (s.end[0] < width / 2.0) == (*side < 0.0) { 1.0 } else { 0.3 }).fold(0.0, f64::max);
            if near * (1.0 - leave) > 0.01 {
                f.opacity = life * near * (1.0 - leave);
                self.lay_round(&mut f, flash, self.names, at);
            }
        }
        f.opacity = life * (1.0 - leave);
        let struck = |i: usize| self.strikes.iter().filter(|s| s.hero == Some(i)).map(|s| strike_light(t - s.when)).fold(0.0, f64::max);
        for near in [false, true] {
            if near {
                let keep = f.opacity;
                self.beams(&mut f, t, life * (1.0 - leave));
                f.opacity = keep;
            }
            for (i, b) in self.towers.iter().enumerate() {
                if b.tower.near == near && t > b.tower.rise {
                    self.tower(&mut f, t, b, struck(i));
                }
            }
            for &(rect, id) in &self.haze {
                f.opacity = life * (1.0 - leave) * if near { 0.6 } else { 0.55 } * ease_out(win(t, 0.3, 1.2));
                let drift = (t * 0.7 + if near { 0.0 } else { 2.0 }).sin() * 8.0 * u;
                f.lay(id, [rect[0] + drift, rect[1], rect[2], rect[3]], true, 1.0);
            }
        }
        f.opacity = life;
        fx::rain(&mut f, t, &self.rain, width, height, self.gap, self.names, u, (1.0 - leave) * ease_out(win(t, 0.15, 0.9)), bright);
        fx::trails(&mut f, t, &self.lanes, self.lights, height, u, 1.0 - leave);
        self.neon_frame(&mut f, t, bright, at);
        for s in &self.strikes {
            let age = t - s.when;
            if (-fx::LEAD..=0.55).contains(&age) {
                fx::strike(&mut f, age, s.start, s.end, &s.bolts, s.bolt_ids, self.lights, u);
            }
            if s.hero.is_some() {
                fx::spire(&mut f, age, s.end, self.lights, u, s.seed);
            }
        }
        f
    }

    /// neon._beams: two searchlights behind the near towers, sweeping slowly, out of step.
    fn beams(&self, f: &mut Frame, t: f64, a: f64) {
        let level = ease_out(win(t, 0.9, 1.8)) * a;
        if level <= 0.01 {
            return;
        }
        let (width, height, u) = (self.width, self.height, self.u);
        let (rect, id) = self.beam;
        let d = height * 0.71;
        let edge = 3.0 * u + d * 0.055 * 1.3;
        f.plus = true;
        f.opacity = level;
        for (side, x0, phase) in [(-1.0, width * 0.04, 0.0), (1.0, width * 0.965, 2.4)] {
            let room = if side < 0.0 { width * 0.13 - 8.0 * u - x0 - edge } else { x0 - width * 0.94 - 8.0 * u - edge };
            let lean = room.atan2(d).to_degrees();
            let angle = lean - 26.0 * (0.5 - 0.5 * (t * 0.85 + phase).sin());
            let turn = if side < 0.0 { angle } else { -angle };
            f.image(id, [x0 + rect[0], height + rect[1], rect[2], rect[3]], None, [x0, height], turn.to_radians(), true, 1.0);
        }
        f.plus = false;
    }

    /// neon._tower: rising into place, windows lighting floor by floor, its sign, its spire's red light.
    fn tower(&self, f: &mut Frame, t: f64, b: &Built, struck: f64) {
        let (tw, u) = (&b.tower, self.u);
        let k = ease_out(win(t, tw.rise, tw.rise + if tw.near { 0.9 } else { 1.1 }));
        if k <= 0.0 {
            return;
        }
        let r = b.area;
        let drop = (1.0 - k) * (self.height - r[1] + 6.0 * u);
        let base = f.opacity;
        let wipe = ease_in_out(win(t, tw.lit, tw.lit + 0.6));
        let dest = [r[0], r[1] + drop, r[2], r[3]];
        f.lay(b.body, dest, false, 1.0);
        if wipe >= 1.0 {
            f.lay(b.lit, dest, false, 1.0);
        } else if wipe > 0.0 {
            let line = r[1] + r[3] - r[3] * wipe;
            let keep = f.clip;
            f.clip = [r[0], line + drop, r[0] + r[2], r[1] + r[3] + 2.0 + drop];
            f.lay(b.lit, dest, false, 1.0);
            f.clip = keep;
        }
        if let (Some(sign), Some(panel)) = (&b.sign, b.outline.panel) {
            self.sign(f, t, b, sign, panel, drop, struck);
            f.opacity = base;
        }
        if let Some(tip) = b.outline.tip {
            let blink = (PI * clamp(((t + f64::from(tw.seed) * 0.17) % 1.15) / 0.22)).sin();
            if blink > 0.0 {
                f.dot(self.beacon, tip[0], tip[1] + drop + u, 9.0 * u, base * blink * k);
            }
        }
    }

    /// neon._sign: flickering on, two pictures taking turns, torn into slices when struck; the
    /// screen's ring turning and scan line, the ticker scrolling.
    #[allow(clippy::too_many_arguments)]
    fn sign(&self, f: &mut Frame, t: f64, b: &Built, sign: &(Rect, Vec<usize>), panel: Rect, drop: f64, struck: f64) {
        let (tw, u) = (&b.tower, self.u);
        let (area, images) = sign;
        let on = tw.lit + 0.3 + if tw.show == "sign" { 0.2 } else { 0.0 };
        let mut level = neon(t, on, f64::from(tw.seed)) * power_down(t, f64::from(tw.seed % 5));
        if level <= 0.0 {
            return;
        }
        let base = f.opacity;
        let age = t - on;
        let turn = (age / 1.3) as usize % images.len();
        if images.len() > 1 && age % 1.3 < 0.07 && age > 1.0 {
            level *= 0.3;
        }
        level *= 1.0 + 0.8 * struck;
        let area = [area[0], area[1] + drop, area[2], area[3]];
        let panel = [panel[0], panel[1] + drop, panel[2], panel[3]];
        let keep = f.clip;
        f.plus = true;
        if tw.show == "ticker" {
            f.clip = [panel[0], area[1], panel[0] + panel[2], area[1] + area[3]];
            let span = area[2] - panel[2] - 18.0 * u;
            let shift = (age * 26.0 * u) % span;
            f.opacity = base * level.min(1.0);
            f.lay(images[0], [area[0] - shift, area[1], area[2], area[3]], true, 1.0);
        } else {
            if struck > 0.2 {
                let mut rnd = PyRandom::new(((t * 30.0) as u32) * 13 + tw.seed);
                for i in 0..5 {
                    let top = area[1] + area[3] * f64::from(i) / 5.0;
                    f.clip = [area[0] - 20.0 * u, top, area[0] + area[2] + 20.0 * u, top + area[3] / 5.0 + 1.0];
                    let shift = rnd.uniform(-9.0, 9.0) * u;
                    for (dx, alpha) in [(shift - 4.0 * u, 0.45), (shift + 4.0 * u, 0.45), (shift, 1.0)] {
                        f.opacity = base * level.min(1.0) * alpha;
                        f.lay(images[turn], [area[0] + dx, area[1], area[2], area[3]], true, 1.0);
                    }
                }
                f.clip = keep;
            } else {
                f.opacity = base * level.min(1.0);
                f.lay(images[turn], area, true, 1.0);
            }
            if tw.show == "screen" {
                let r = panel[3] * 0.27 + 3.2 * u;
                let at: Pt = [panel[0] + panel[2] / 2.0, panel[1] + panel[3] * 0.38];
                f.opacity = base * level.min(1.0);
                let start = round_even(-age * 140.0 * 16.0).rem_euclid(360.0 * 16.0) / 16.0;
                for (w, color, alpha) in [(4.5, CYAN, 0.35), (1.4, "#e9fdff", 0.95)] {
                    f.ring(at, r, w * u, Some((start.to_radians(), 80f64.to_radians())), rgba(color, alpha));
                }
                let scan = (age % 1.7) / 1.7;
                let y = panel[1] + panel[3] * scan;
                f.line([panel[0] + 1.5 * u, y], [panel[0] + panel[2] - 1.5 * u, y], 1.2 * u, true, rgba(CYAN, 0.55 * (1.0 - scan)));
            }
        }
        f.clip = keep;
        f.plus = false;
    }

    /// neon._tube: a lit neon tube, its colored glass and its white-hot middle.
    fn tube(f: &mut Frame, points: &[Pt], tint: &str, level: f64, width: f64) {
        f.stroke(points, width, rgba(tint, 0.5 * level));
        f.stroke(points, width * 3.0 / 7.0, shade(mix(tint, "#ffffff", 0.75), 0.95 * level));
    }

    /// neon._neon_frame: a spark runs round and lights the tubes; their light stutters on and surges with lightning.
    fn neon_frame(&self, f: &mut Frame, t: f64, bright: f64, at: &[[u32; 4]]) {
        let trace = ease_out(win(t, 0.3, 1.1));
        if trace <= 0.0 {
            return;
        }
        let u = self.u;
        let base = f.opacity;
        let parts: [(&[Pt], &str, f64); 2] = [(&self.outer, CYAN, 1.12), (&self.inner, MAGENTA, 1.24)];
        let levels: Vec<f64> = parts.iter().enumerate().map(|(i, p)| neon(t, p.2, i as f64) * power_down(t, i as f64)).collect();
        let band = GLOW_BAND * u;
        let inside = [band, band, self.width - 2.0 * band, self.height - 2.0 * band];
        let alike = levels[0].min(levels[1]) > 0.0 && (levels[0] - levels[1]).abs() < 0.08;
        let lays: Vec<(usize, f64)> = if alike { vec![(self.glows[2], (levels[0] + levels[1]) / 2.0)] } else { vec![(self.glows[0], levels[0]), (self.glows[1], levels[1])] };
        for (id, level) in lays {
            if level > 0.0 {
                f.opacity = base * level;
                self.lay_round(f, id, inside, at);
                if bright > 0.05 {
                    f.plus = true;
                    f.opacity = base * level * bright * 0.7;
                    self.lay_round(f, id, inside, at);
                    f.plus = false;
                }
            }
        }
        for (index, (&(points, tint, on), &level)) in parts.iter().zip(&levels).enumerate() {
            let lit = level.max(if t < on + 0.3 { 0.55 } else { 0.0 });
            if lit <= 0.0 {
                continue;
            }
            if trace >= 1.0 {
                f.opacity = base * lit;
                Self::tube(f, points, tint, 1.0, 7.0 * u);
                continue;
            }
            let corner = (0..points.len()).min_by(|&a, &b| (points[a][0] + points[a][1]).total_cmp(&(points[b][0] + points[b][1]))).unwrap_or(0);
            let back: Vec<Pt> = points[..=corner].iter().rev().copied().collect();
            for half in [back, points[corner..].to_vec()] {
                let path = partial(&half, trace);
                f.opacity = base;
                Self::tube(f, &path, tint, lit, 7.0 * u);
                if let (0, Some(&head)) = (index, path.last()) {
                    let fade = 1.0 - win(trace, 0.7, 0.97);
                    f.dot(self.lights[1], head[0], head[1], 26.0 * u, 0.8 * fade * base);
                    f.dot(self.lights[0], head[0], head[1], 10.0 * u, fade * base);
                    f.star(head[0], head[1], 13.0 * u, "#ffffff", 0.85 * fade);
                }
            }
        }
        f.opacity = base;
    }
}
