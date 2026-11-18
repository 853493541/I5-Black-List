//! The glass heart, ported from ice.py's `_sparks`, `_heart` and `_aurora_within`: glints gather
//! and it forms; a prism of light sweeps it, it beats once, and at the end it melts into light.

use std::f64::consts::PI;

use super::prim::{self, solid, stops, Frame, Paint};
use super::{arc, heart_points, spectrum, Ice, WHITE};
use crate::draw::{ease_in, ease_in_out, ease_out, win, Pt};
use crate::pyrand::PyRandom;

/// The aurora inside the heart: its cyans and violets.
const WITHIN: [&str; 6] = ["#46c6ff", "#7ff2e6", "#9a7bff", "#4fa6ff", "#c08bff", "#46c6ff"];

/// Glints that gather on the heart's edge as it forms: (from, to, starts).
pub fn sparks(centre: Pt, size: f64, rnd: &mut PyRandom) -> Vec<(Pt, Pt, f64)> {
    heart_points(centre[0], centre[1], size, 12, 0.5 / 12.0)
        .into_iter()
        .enumerate()
        .map(|(i, p)| {
            let angle = (p[1] - centre[1]).atan2(p[0] - centre[0]) + rnd.uniform(-0.4, 0.4);
            let far = size * rnd.uniform(0.9, 1.5);
            let start = [p[0] + angle.cos() * far, p[1] + angle.sin() * far];
            (start, p, 0.55 + 0.04 * i as f64 + rnd.uniform(0.0, 0.12))
        })
        .collect()
}

impl Ice {
    /// Draws the heart into f; returns the light inside it, to be drawn at a quarter size first.
    pub(super) fn heart(&self, f: &mut Frame, t: f64) -> Option<(Frame, [u32; 2])> {
        let u = self.u;
        let form = ease_out(win(t, 0.8, 1.55));
        let melt = ease_in(win(t, 4.05, 4.75));
        let float_y = 3.0 * u * (t * 1.7).sin();
        for &(start, end, when) in &self.sparks {
            let k = ease_in_out(win(t, when, when + 0.6));
            if 0.0 < k && k < 1.0 {
                let x = start[0] + (end[0] - start[0]) * k;
                let y = start[1] + (end[1] - start[1]) * k + float_y * k;
                f.star(x, y, 9.0 * u * (0.5 + 0.5 * arc(k)), WHITE, 0.9);
            }
        }
        if form <= 0.0 || melt >= 1.0 {
            return None;
        }
        let beat = 1.0 + 0.06 * arc(win(t, 2.25, 2.45)).max(0.0) + 0.04 * arc(win(t, 2.5, 2.68)).max(0.0);
        let a = form * (1.0 - melt);
        let c = [self.heart_at[0], self.heart_at[1] + float_y];
        let size = 150.0 * u * (0.82 + 0.18 * form) * beat * (1.0 + 0.12 * melt);
        let glow_at = [c[0], c[1] + 6.0 * u];
        let glow = stops(&[(0.0, "#7fd0ff", 0.42 * a), (0.45, "#2f7bff", 0.18 * a), (1.0, "#2f7bff", 0.0)]);
        f.circle(glow_at[0], glow_at[1], 150.0 * u * beat, &Paint::Radial(glow_at, 150.0 * u * beat, glow));
        let px = self.glass_px as f64;
        let scale = size / px;
        let side = ((px * 1.04) as usize + 4) as f64;
        let rect = [c[0] - side / 2.0 * scale, c[1] - (side / 2.0 - px * 0.145) * scale, side * scale, side * scale];
        f.image(prim::GLASS, rect, [side, side], a);
        let shape = heart_points(c[0], c[1], size, 120, 0.0);
        f.clip_to(&shape);
        let (within, box_, pixels) = within(t, c, size);
        f.flags |= prim::ADD;
        f.image(prim::WITHIN, box_, [f64::from(pixels[0]), f64::from(pixels[1])], a);
        f.flags &= !prim::ADD;
        // The prism: a band of spectrum and white crossing from the top left.
        for (sweep, strength) in [(win(t, 1.75, 2.55), 0.8), (win(t, 3.1, 3.7), 0.45)] {
            if !(0.0 < sweep && sweep < 1.0) {
                continue;
            }
            let at = [c[0] - size * 0.75 + size * 1.5 * sweep, c[1] - size * 0.6 + size * 1.2 * sweep];
            let (sin, cos) = (-45f64).to_radians().sin_cos();
            let map = |x: f64, y: f64| [at[0] + cos * x - sin * y, at[1] + sin * x + cos * y];
            let w = size * 0.16;
            let corners = [map(-w, -size), map(w, -size), map(w, size), map(-w, size)];
            let s = strength * a;
            let band = stops(&[(0.0, "#7ff2e6", 0.0), (0.3, "#7ff2e6", 0.45 * s), (0.5, "#ffffff", 0.8 * s), (0.7, "#ff9ad5", 0.4 * s), (1.0, "#9a7bff", 0.0)]);
            f.poly(&corners, &Paint::Linear(map(-w, 0.0), map(w, 0.0), band));
        }
        f.unclip();
        // The edge: icy starlight, a haze round a fine bright line.
        let mut closed = shape.clone();
        closed.push(shape[0]);
        for (w, color, alpha) in [(10.0, "#7fd0ff", 0.10), (4.0, "#bff3ff", 0.30), (1.3, "#ffffff", 0.85)] {
            f.stroke(&closed, w * u, &solid(color, alpha * a));
        }
        let sweep = win(t, 1.75, 2.55);
        if 0.0 < sweep && sweep < 1.0 {
            f.star(c[0] - size * 0.3 + size * 0.6 * sweep, c[1] - size * 0.2 + size * 0.4 * sweep, 22.0 * u * arc(sweep), WHITE, 0.95 * a);
        }
        if melt <= 0.0 && t > 2.3 {
            let twinkle = arc(win(t, 3.4, 3.8)).max(0.0);
            f.star(c[0] + size * 0.23, c[1] - size * 0.2, 16.0 * u * twinkle, WHITE, twinkle);
        }
        // Melting: the light it held goes up as glints.
        if melt > 0.0 {
            for (i, p) in heart_points(c[0], c[1], size, 8, 0.5 / 8.0).into_iter().enumerate() {
                let rise = 60.0 * u * melt * (0.6 + 0.08 * i as f64);
                f.star(p[0], p[1] - rise, 8.0 * u * (PI * melt).sin(), WHITE, 0.9 * (1.0 - melt));
            }
        }
        Some((within, pixels))
    }
}

/// Aurora light drifting inside the heart: two wide bands, cyan through violet, drawn at a quarter
/// size (in that picture's pixels) to be laid on scaled up. Returns the shapes, the box they are
/// laid into and the picture's size.
fn within(t: f64, c: Pt, size: f64) -> (Frame, [f64; 4], [u32; 2]) {
    let shrink = 4.0;
    let box_ = [c[0] - size * 0.55, c[1] - size * 0.45, size * 1.1, size * 0.95];
    let pixels = [(box_[2] / shrink).round_ties_even().max(1.0) as u32, (box_[3] / shrink).round_ties_even().max(1.0) as u32];
    let mut f = Frame::new();
    f.flags = prim::ADD;
    let small = |x: f64, y: f64| [(x - box_[0]) / shrink, (y - box_[1]) / shrink];
    for (i, (off, amp, speed, phase, bright)) in [(-0.04, 0.08, 0.9, 0.0, 1.0), (0.22, 0.06, -0.7, 2.4, 0.75)].into_iter().enumerate() {
        let path: Vec<Pt> = (0..25)
            .map(|s| {
                let k = f64::from(s) / 24.0;
                let y = c[1] + size * (off + amp * (k * 4.2 + t * speed + phase).sin() + 0.025 * (k * 9.0 + t * 1.3 + phase).sin());
                small(box_[0] + box_[2] * k, y)
            })
            .collect();
        let across: Vec<_> = (0..7).map(|s| (f64::from(s) / 6.0, spectrum(&WITHIN, f64::from(s) / 6.0 * 0.8 + t * 0.12 + i as f64 * 0.3), 1.0)).collect();
        for (width, alpha) in [(0.34, 0.12), (0.2, 0.16), (0.09, 0.22)] {
            f.opacity = alpha * bright;
            let paint = Paint::Linear(small(box_[0], 0.0), small(box_[0] + box_[2], 0.0), across.clone());
            f.stroke(&path, size * width / shrink, &paint);
        }
    }
    (f, box_, pixels)
}
