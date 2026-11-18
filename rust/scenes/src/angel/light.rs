//! The scene's other pictures, per pixel: the mote of light (angel._spark), the round window's shafts
//! (_shafts, _wave, _box) and the gold-leaf feather (_feather).

use std::f64::consts::PI;

use super::glass::HONEY;
use super::lines::Rect;
use super::pcg::Pcg64;
use super::px::{glow, picture, ramp, rgb, smooth, Pic};

pub fn spark() -> Pic {
    let n = 64;
    let (honey, white) = (rgb(HONEY), rgb("#fffaf0"));
    glow(n, n, |i| {
        let (x, y) = ((i % n) as f32 + 0.5 - 32.0, (i / n) as f32 + 0.5 - 32.0);
        let d = x.hypot(y) / 32.0;
        let (a, b, edge) = ((-(d / 0.42).powi(2)).exp() * 0.8, (-(d / 0.12).powi(2)).exp() * 1.3, 1.0 - smooth(0.85, 1.0, d));
        std::array::from_fn(|c| (honey[c] * a + white[c] * b) * edge)
    })
}

/// angel._wave: smooth value noise along one axis, 0..1, a new value every cell.
fn wave(x: &[f32], cell: f64, rnd: &mut Pcg64) -> Vec<f64> {
    let (lo, hi) = x.iter().fold((f32::MAX, f32::MIN), |(a, b), &v| (a.min(v), b.max(v)));
    let low = (f64::from(lo) / cell).floor() as i64 - 1;
    let count = ((f64::from(hi) / cell).ceil() as i64 - low + 3).max(0) as usize;
    let knots: Vec<f64> = (0..count).map(|_| rnd.random()).collect();
    x.iter()
        .map(|&v| {
            let f = v / cell as f32 - low as f32;
            let i = f.floor();
            let k = f - i;
            let k = f64::from(k * k * (3.0 - 2.0 * k));
            let i = i as usize;
            knots[i] * (1.0 - k) + knots[i + 1] * k
        })
        .collect()
}

/// angel._box: 1 inside rect, 0 feather beyond it, smoothly between.
fn inside(x: f32, y: f32, r: Rect, feather: f64) -> f32 {
    let (l, t, rr, b) = (r[0] as f32, r[1] as f32, (r[0] + r[2]) as f32, (r[1] + r[3]) as f32);
    let out = (l - x).max(x - rr).max((t - y).max(y - b));
    1.0 - smooth((-feather * 0.5) as f32, feather as f32, out)
}

/// The shafts, at a quarter size: where they may show, and two sets of streaks to breathe in turn.
pub fn shafts(width: f64, height: f64, gap: Rect, center: [f64; 2], radius: f64, u: f64) -> (Pic, [Pic; 2]) {
    let soft = 0.25f32;
    let (w, h) = ((width * 0.25).round_ties_even().max(1.0) as usize, (height * 0.25).round_ties_even().max(1.0) as usize);
    let at = |i: usize| (((i % w) as f32 + 0.5) / soft, ((i / w) as f32 + 0.5) / soft);
    let (angle, r): (Vec<f32>, Vec<f32>) = (0..w * h)
        .map(|i| {
            let (x, y) = at(i);
            let (dx, dy) = (x - center[0] as f32, y - center[1] as f32);
            (dy.atan2(dx), dx.hypot(dy))
        })
        .unzip();
    let base: Vec<f32> = (0..w * h)
        .map(|i| {
            let fan = smooth(1.45, 1.75, angle[i]) * (1.0 - smooth(2.55, 2.95, angle[i]));
            let fall = smooth((radius * 0.8) as f32, (radius * 1.4) as f32, r[i]) * (1.0 - smooth(0.0, (height * 0.95) as f32, r[i])).powf(1.3);
            fan * fall
        })
        .collect();
    let (warm, pale) = (rgb("#ffd486"), rgb("#fff3d6"));
    let layers = [3u64, 9].map(|seed| {
        let mut rnd = Pcg64::new(seed);
        let a = wave(&angle, 0.05, &mut rnd);
        let b = wave(&angle, 0.017, &mut rnd);
        glow(w, h, |i| {
            let streak = smooth(0.45, 0.85, (0.6 * a[i] + 0.4 * b[i]) as f32);
            let strength = base[i] * (0.08 + 0.92 * streak);
            std::array::from_fn(|c| (warm[c] + (pale[c] - warm[c]) * streak * 0.5) * strength * 0.85)
        })
    });
    let names = [width * 0.13, height * 0.29, width * 0.81, height * 0.55];
    let words = [width * 0.42, height * 0.07, width * 0.23, height * 0.14];
    let title = [width * 0.38, height * 0.07, width * 0.3, height * 0.24];
    let hole = [gap[0] - 20.0 * u, gap[1] - 20.0 * u, gap[2] + 40.0 * u, gap[3] + 40.0 * u];
    let keep = picture(w, h, |_| [1.0; 3], |i| {
        let (x, y) = at(i);
        (1.0 - 0.8 * inside(x, y, names, 50.0 * u)) * (1.0 - 0.5 * inside(x, y, title, 30.0 * u)) * (1.0 - inside(x, y, words, 24.0 * u)) * (1.0 - inside(x, y, hole, 50.0 * u))
    });
    (keep, layers)
}

/// angel._feather: a gold-leaf feather px pixels long, quill on the left; and where its quill is,
/// as a share of its height.
pub fn feather(px: usize) -> (Pic, f64) {
    let (broad, lead, bend) = (0.3f32, 0.42f32, 0.06f32);
    let pf = px as f32;
    let high = (px as f64 * f64::from(broad + bend) * 1.15) as usize + 4;
    let root = high as f32 / 2.0 - bend * pf / 2.0;
    let n = px * high;
    let cell = |i: usize| ((i % px) as f32 + 0.5, (i / px) as f32 + 0.5);
    let dv: Vec<f32> = (0..n).map(|i| { let (x, y) = cell(i); let s = x / pf; y - (root + bend * pf * s * s) }).collect();
    let along: Vec<f32> = (0..n).map(|i| cell(i).0 - dv[i].abs() * 1.15).collect();
    let mut rnd = Pcg64::new(px as u32);
    let shifted: Vec<f32> = (0..n).map(|i| along[i] + if dv[i] < 0.0 { 0.0 } else { pf * 3.0 }).collect();
    let parts = wave(&shifted, px as f64 / 9.0, &mut rnd);
    let stretched: Vec<f32> = along.iter().map(|a| a * 1.7).collect();
    let jag_wave = wave(&stretched, px as f64 / 30.0, &mut rnd);
    let tone_wave = wave(&along, px as f64 / 14.0, &mut rnd);
    let spacing = (pf / 55.0).max(2.0);
    let shine_c = rgb("#fff4cc");
    let mut colors = Vec::with_capacity(n);
    let mut alphas = Vec::with_capacity(n);
    for i in 0..n {
        let s = cell(i).0 / pf;
        let profile = smooth(0.0, 0.3, s).powf(0.55) * (1.0 - ((s - 0.36) / 0.64).clamp(0.0, 1.0).powf(2.4)).clamp(0.0, 1.0).sqrt();
        let half = 0.5 * broad * pf * profile * if dv[i] < 0.0 { 2.0 * lead } else { 2.0 * (1.0 - lead) };
        let r = dv[i].abs() / half.max(1e-3);
        let barbs = 0.5 + 0.5 * (along[i] / spacing * 2.0 * PI as f32).cos();
        let split = smooth(0.8, 0.9, parts[i] as f32) * smooth(0.3, 0.6, r) * smooth(0.15, 0.3, s);
        let jag = 0.06 * barbs + 0.08 * jag_wave[i] as f32;
        let inner = 1.0 - smooth(0.84 - jag, 1.0 - jag, r);
        let alpha = inner * (1.0 - 0.9 * split) * (0.82 + 0.18 * (1.0 - r * r)) * (0.5 + 0.5 * smooth(0.02, 0.25, s));
        let sheen = (-((r - 0.38) / 0.2).powi(2)).exp() * if dv[i] < 0.0 { 1.0 } else { 0.65 };
        let tone = 0.38 + 0.38 * sheen + 0.1 * barbs - 0.22 * smooth(0.6, 1.0, r) + 0.08 * tone_wave[i] as f32;
        let color = ramp(tone.clamp(0.0, 1.0));
        let shaft_w = pf * 0.016 * (1.0 - 0.75 * s) + 0.35;
        let shaft = (1.0 - smooth(shaft_w * 0.45, shaft_w, dv[i].abs())) * (1.0 - smooth(0.9, 0.99, s));
        colors.push(std::array::from_fn(|c| color[c] + (shine_c[c] - color[c]) * shaft * 0.8));
        alphas.push(alpha.max(shaft * 0.95));
    }
    (picture(px, high, |i| colors[i], |i| alphas[i]), f64::from(root) / high as f64)
}
