//! The side rails, the scan beam and the per-pixel pictures of the panels: cyber._Rail,
//! _beam_picture, _beam_at, _beam, _sweep_picture and _cone_picture.

use std::f64::consts::{PI, TAU};

use super::canvas::{col, Blend, Canvas, Paint, Src, ATLAS};
use super::light::{glow, noise, rgb, round_even, smooth, Pic};
use super::text::{Face, Type};
use super::{CYAN, MAGENTA, VIOLET};
use crate::draw::{ease_in_out, ease_out, hex, win, Pt};

/// The scan beam's sweeps: (from, to, which way).
const SWEEPS: [(f64, f64, f64); 2] = [(1.2, 2.05, 1.0), (3.0, 3.8, -1.0)];

/// A line with Qt's default square ends: flat ends pushed out half its width.
pub fn sq_line(c: &mut Canvas, a: Pt, b: Pt, width: f64, paint: &Paint) {
    let (dx, dy) = (b[0] - a[0], b[1] - a[1]);
    let l = dx.hypot(dy).max(1e-9);
    let (ex, ey) = (dx / l * width / 2.0, dy / l * width / 2.0);
    c.line([a[0] - ex, a[1] - ey], [b[0] + ex, b[1] + ey], width, paint, false);
}

/// A dashed line, dash and gap in pen widths, its ends flat.
pub fn dashed(c: &mut Canvas, a: Pt, b: Pt, width: f64, dash: (f64, f64), paint: &Paint) {
    let (dx, dy) = (b[0] - a[0], b[1] - a[1]);
    let l = dx.hypot(dy);
    if l <= 0.0 {
        return;
    }
    let (on, period) = (dash.0 * width, (dash.0 + dash.1) * width);
    let mut s = 0.0;
    while s < l {
        let e = (s + on).min(l);
        c.line([a[0] + dx * s / l, a[1] + dy * s / l], [a[0] + dx * e / l, a[1] + dy * e / l], width, paint, false);
        s += period;
    }
}

pub struct Rail {
    x: f64,
    top: f64,
    bottom: f64,
    side: f64,
    u: f64,
    step: f64,
    area: [f64; 4],
    tape: [f64; 4],
}

impl Rail {
    pub fn new(x: f64, top: f64, bottom: f64, side: f64, u: f64) -> Self {
        let step = 9.0 * u;
        let area = [if side < 0.0 { x - 46.0 * u } else { x - 10.0 * u }, top - 3.0 * step, 56.0 * u, bottom - top + 6.0 * step];
        let tape = [area[0], top - 30.0 * step, area[2], bottom - top + 60.0 * step];
        Self { x, top, bottom, side, u, step, area, tape }
    }

    /// A tick scale sliding to a reading, fading toward its ends in steps; a spine and a caret.
    pub fn paint(&self, c: &mut Canvas, t: f64, stay: f64, ty: &Type) {
        let on = ease_out(win(t, 1.0, 1.5)) * stay;
        if on <= 0.01 {
            return;
        }
        let (u, a, step) = (self.u, self.area, self.step);
        let k = t / 1.3 + (self.side + 1.0) * 0.4;
        let n = k as i64;
        let f = ease_in_out(k - n as f64);
        let pick = |i: i64| ((i * 7 + self.side as i64 * 3).rem_euclid(11) - 5) as f64 * 2.3 * step;
        let shift = pick(n) * (1.0 - f) + pick(n + 1) * f;
        let fade = 4.0 * step;
        let saved = c.save();
        let base = c.opacity * on * 0.75;
        let mut zones: Vec<(f64, f64, f64)> = (0..4).map(|i| (a[1] + fade * f64::from(i) / 4.0, fade / 4.0, (f64::from(i) + 0.5) / 4.0)).collect();
        zones.push((a[1] + fade, a[3] - 2.0 * fade, 1.0));
        zones.extend((0..4).map(|i| (a[1] + a[3] - fade * f64::from(i + 1) / 4.0, fade / 4.0, (f64::from(i) + 0.5) / 4.0)));
        let count = (self.tape[3] / step) as usize;
        for (y0, tall, alpha) in zones {
            c.restore(saved);
            c.opacity = base * alpha;
            c.clip_to([a[0], y0, a[2], tall]);
            for i in 0..=count {
                let y = self.tape[1] + i as f64 * step + shift;
                if y < y0 - 2.0 || y > y0 + tall + 2.0 {
                    continue;
                }
                let major = i % 5 == 0;
                let paint = col(CYAN, if major { 0.85 } else { 0.4 });
                let reach = if major { 10.0 } else { 5.0 } * u;
                sq_line(c, [self.x, y], [self.x + self.side * reach, y], if major { 1.2 } else { 0.8 } * u, &paint);
                if major {
                    let x = self.x + self.side * 13.0 * u - if self.side < 0.0 { 26.0 * u } else { 0.0 };
                    ty.draw(c, Face::Rail, [x, y + 3.0 * u], &format!("{:03}", (count - i) * 5), CYAN, 0.7);
                }
            }
        }
        c.restore(saved);
        c.opacity *= on;
        let cyan = hex(CYAN);
        let g = Paint::Linear([self.x, self.top], [self.x, self.bottom], vec![(0.0, cyan, 0.0), (0.2, cyan, 0.7), (0.8, cyan, 0.7), (1.0, cyan, 0.0)]);
        sq_line(c, [self.x, self.top], [self.x, self.bottom], 1.2 * u, &g);
        let mid = (self.top + self.bottom) / 2.0;
        let tip = self.x - self.side * 3.0 * u;
        let back = tip - self.side * 9.0 * u;
        c.poly(&[[tip, mid], [back, mid - 5.0 * u], [back, mid + 5.0 * u]], &col(MAGENTA, 0.95));
        c.restore(saved);
    }
}

/// The scan beam moving right down the top band, and how far it reaches behind and ahead.
pub fn beam_picture(band: f64, u: f64) -> (Pic, f64, f64) {
    let (behind, ahead) = (190.0 * u, 50.0 * u);
    let (w, h) = (round_even(behind + ahead).max(2.0) as usize, round_even(band).max(2.0) as usize);
    let streaks = noise(w, 1, 3.0 * u, 2, 4);
    let (white, cyan, violet) = (rgb("#ffffff"), rgb(CYAN), rgb(VIOLET));
    let pic = glow(w, h, |xs, ys| {
        let dx = (xs as f64 + 0.5) * ((behind + ahead) / w as f64) - behind;
        let y = (ys as f64 + 0.5) * (band / h as f64);
        let fall = smooth(0.0, 10.0 * u, y) * (1.0 - smooth(band * 0.45, band, y));
        let core = (-(dx / (1.4 * u)).powi(2)).exp();
        let near = (-dx.abs() / (8.0 * u)).exp();
        let wide = (-(dx / (30.0 * u)).powi(2)).exp() * (1.0 - smooth(ahead * 0.5, ahead, dx));
        let st = 0.55 + 0.45 * f64::from(streaks.at(xs, 0));
        let trail = if dx < 0.0 { (dx.min(0.0) / (60.0 * u)).exp() * smooth(-behind, -behind * 0.7, dx) * st * 0.2 } else { 0.0 };
        std::array::from_fn(|k| {
            ((core * f64::from(white[k]) * 0.95 + near * f64::from(cyan[k]) * 0.6 + wide * f64::from(violet[k]) * 0.35 + trail * f64::from(cyan[k])) * fall) as f32
        })
    });
    (pic, behind, ahead)
}

/// Where the scan beam is at t and which way it goes, or None between its sweeps.
pub fn beam_at(t: f64, width: f64, reach: f64) -> Option<(f64, f64)> {
    SWEEPS.iter().find(|s| s.0 <= t && t <= s.1).map(|&(start, end, way)| {
        let k = ease_in_out(win(t, start, end));
        (-reach + (width + 2.0 * reach) * if way > 0.0 { k } else { 1.0 - k }, way)
    })
}

/// The beam down the top band, dimmed where it crosses the title.
#[allow(clippy::too_many_arguments)]
pub fn beam(c: &mut Canvas, at: Option<(f64, f64)>, pic: (Src, f64, f64), band: f64, title: [f64; 4], u: f64) {
    let Some((x, way)) = at else { return };
    let (src, behind, ahead) = pic;
    let k = src[3] / band;
    let (lo, hi) = if way > 0.0 { (x - behind, x + ahead) } else { (x - ahead, x + behind) };
    let (stops, alphas): (Vec<f64>, Vec<f64>) = if lo < title[0] + title[2] && hi > title[0] {
        let (f, tt, tb) = (14.0 * u, title[1], title[1] + title[3]);
        (vec![0.0, tt - f, tt - f / 2.0, tt, tb, tb + f / 2.0, tb + f, band], vec![1.0, 0.65, 0.35, 0.12, 0.35, 0.65, 1.0])
    } else {
        (vec![0.0, band], vec![1.0])
    };
    let saved = c.save();
    c.blend(Blend::Plus);
    let base = c.opacity;
    for (i, alpha) in alphas.iter().enumerate() {
        let (y0, y1) = (stops[i].max(0.0), stops[i + 1].min(band));
        if y1 <= y0 {
            continue;
        }
        c.opacity = base * alpha;
        let part = [src[0], src[1] + y0 * k, src[2], (y1 - y0) * k];
        c.picture(ATLAS, part, [-behind, y0, behind + ahead, y1 - y0], [way, 0.0, 0.0, 1.0, x, 0.0], 1.0, None);
    }
    c.restore(saved);
}

/// The radar's sweep pointing right: a bright leading edge and a phosphor trail behind it.
pub fn sweep_picture(side: usize) -> Pic {
    let r0 = side as f64 / 2.0;
    let (cyan, ice) = (rgb(CYAN), rgb("#d8fdff"));
    glow(side, side, |xs, ys| {
        let (dx, dy) = (xs as f64 + 0.5 - r0, ys as f64 + 0.5 - r0);
        let r = dx.hypot(dy) / r0;
        let behind = (-dy.atan2(dx)).rem_euclid(TAU);
        let inside = 1.0 - smooth(0.96, 1.0, r);
        let trail = ((-behind / 0.9).exp() * 0.8 + (-behind / 0.12).exp() * 0.5) * (0.25 + 0.75 * r);
        let edge = if dx > 0.0 { (-(dy / (side as f64 * 0.008)).powi(2)).exp() * (0.3 + 0.7 * r) } else { 0.0 };
        std::array::from_fn(|k| ((trail * f64::from(cyan[k]) + edge * f64::from(ice[k]) * 1.2) * inside) as f32)
    })
}

/// The projector's cone of light rising from the emitter and widening, faint lines in it.
pub fn cone_picture(rect: [f64; 4], emitter: Pt, u: f64) -> Pic {
    let (w, h) = (round_even(rect[2]).max(2.0) as usize, round_even(rect[3]).max(2.0) as usize);
    let cyan = rgb(CYAN);
    glow(w, h, |xs, ys| {
        let x = rect[0] + xs as f64 + 0.5 - emitter[0];
        let y = rect[1] + ys as f64 + 0.5;
        let rise = ((emitter[1] - y) / (emitter[1] - rect[1]).max(1.0)).clamp(0.0, 1.0);
        let spread = 40.0 * u + 46.0 * u * rise;
        let b = (-(x / spread).powi(2) * 2.2).exp() * (1.0 - rise).powf(1.3) * smooth(-0.02, 0.06, rise);
        let streaks = 0.75 + 0.25 * (x / spread * 9.0).cos();
        cyan.map(|v| (b * streaks * 0.42 * f64::from(v)) as f32)
    })
}

/// Points round part of an ellipse, Qt's way: degrees counterclockwise from three o'clock.
pub fn arc(cx: f64, cy: f64, rx: f64, ry: f64, from: f64, span: f64) -> Vec<Pt> {
    let n = ((span.abs() / 4.0).ceil() as usize).max(2);
    (0..=n)
        .map(|i| {
            let a = (from + span * i as f64 / n as f64) * PI / 180.0;
            [cx + rx * a.cos(), cy - ry * a.sin()]
        })
        .collect()
}
