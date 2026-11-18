//! The night's wash and the neon frame: cyber._frame, _tube, _neon, _power_down, _neon_frame.

use super::canvas::{col, Blend, Canvas, Paint, ATLAS, WASH};
use super::{lay_dot, Cyber, CYAN, MAGENTA};
use crate::draw::{ease_out, hex, mix, partial, win, Pt};

/// The tube round the screen, one line from the gap's left round to its right, corners cut.
pub fn frame(width: f64, height: f64, gap: [f64; 4], inset: f64, cut: f64, u: f64) -> Vec<Pt> {
    let (m, c) = (inset, cut);
    let bottom = height - m;
    let (left_end, right_end) = (gap[0] - 40.0 * u, gap[0] + gap[2] + 40.0 * u);
    let tab = 12.0 * u;
    vec![
        [left_end, bottom], [m + c, bottom], [m, bottom - c], [m, m + c], [m + c, m],
        [width * 0.34, m], [width * 0.34 + tab, m + tab], [width * 0.66 - tab, m + tab], [width * 0.66, m],
        [width - m - c, m], [width - m, m + c], [width - m, bottom - c], [width - m - c, bottom], [right_end, bottom],
    ]
}

/// A rounded rectangle's outline, x, y, w, h, its corners r round.
fn rounded(r: [f64; 4], radius: f64) -> Vec<Pt> {
    let [x, y, w, h] = r;
    let corners = [(x + w - radius, y + radius, -90.0), (x + w - radius, y + h - radius, 0.0), (x + radius, y + h - radius, 90.0), (x + radius, y + radius, 180.0)];
    let mut out = Vec::new();
    for (cx, cy, start) in corners {
        for i in 0..=16 {
            let a = (start + 90.0 * f64::from(i) / 16.0_f64).to_radians();
            out.push([cx + radius * a.cos(), cy + radius * a.sin()]);
        }
    }
    out
}

/// The Wash: the night laid on full size, scan lines drawn into it only, a feathered hole rubbed out
/// over the gap.
pub fn wash(s: &Cyber) -> Canvas {
    let mut c = Canvas::new();
    c.draw_into(WASH, true);
    c.lay(ATLAS, s.pics.night, [0.0, 0.0, s.width, s.height], 1.0);
    c.blend(Blend::Atop);
    let mut row = 0.0;
    while row < s.height {
        c.line([0.0, row], [s.width, row], 1.3 * s.u, &col("#000000", 0.3), false);
        row += 4.0 * s.u;
    }
    c.blend(Blend::Out);
    let g = s.gap;
    for step in 0..12 {
        let grow = 40.0 * (1.0 - f64::from(step) / 11.0);
        c.poly(&rounded([g[0] - grow, g[1] - grow, g[2] + 2.0 * grow, g[3] + 2.0 * grow], 14.0 + grow), &col("#000000", 62.0 / 255.0));
    }
    c
}

/// How lit a neon tube is: off, then stuttering on, then a faint hum with now and then a dip.
pub fn neon(t: f64, on: f64, seed: f64) -> f64 {
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
    let dip = 1.0 - 0.55 * (std::f64::consts::PI * win(t, 2.6 + seed * 0.37, 2.68 + seed * 0.37)).sin().max(0.0);
    hum * dip
}

/// 1 while on, stuttering to 0 at the end.
pub fn power_down(t: f64, seed: f64) -> f64 {
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

/// A lit tube along points: its colored glass, then its white-hot middle.
pub fn tube(c: &mut Canvas, points: &[Pt], tint: &str, level: f64, width: f64) {
    c.stroke(points, width, &Paint::Solid(hex(tint), 0.5 * level), true);
    c.stroke(points, width * 3.0 / 7.0, &Paint::Solid(mix(tint, "#ffffff", 0.75), 0.95 * level), true);
}

/// The spark runs round from the top left lighting the tubes; their light stutters on once it is
/// round and surges when lightning strikes.
pub fn neon_frame(c: &mut Canvas, s: &Cyber, t: f64, bright: f64) {
    let trace = ease_out(win(t, 0.3, 1.1));
    if trace <= 0.0 {
        return;
    }
    let base = c.opacity;
    let saved = c.save();
    let (w, h, u) = (s.width, s.height, s.u);
    let parts = [(&s.outer, CYAN, s.pics.glow[0], 1.12), (&s.inner, MAGENTA, s.pics.glow[1], 1.24)];
    for (index, (points, tint, light, on)) in parts.into_iter().enumerate() {
        let level = neon(t, on, index as f64) * power_down(t, index as f64);
        if level > 0.0 {
            c.opacity = base * level;
            c.lay(ATLAS, light, [0.0, 0.0, w, h], 1.0);
            if bright > 0.05 {
                c.blend(Blend::Plus);
                c.opacity = base * level * bright * 0.7;
                c.lay(ATLAS, light, [0.0, 0.0, w, h], 1.0);
                c.blend(Blend::Over);
            }
        }
        let lit = level.max(if t < on + 0.3 { 0.55 } else { 0.0 });
        if lit <= 0.0 {
            continue;
        }
        if trace >= 1.0 {
            c.opacity = base * lit;
            tube(c, points, tint, 1.0, 7.0 * u);
            continue;
        }
        let corner = (0..points.len()).min_by(|&a, &b| (points[a][0] + points[a][1]).total_cmp(&(points[b][0] + points[b][1]))).unwrap_or(0);
        let back: Vec<Pt> = points[..=corner].iter().rev().copied().collect();
        for half in [back, points[corner..].to_vec()] {
            let path = partial(&half, trace);
            c.opacity = base;
            tube(c, &path, tint, lit, 7.0 * u);
            if index == 0 {
                let Some(&head) = path.last() else { continue };
                let fade = 1.0 - win(trace, 0.7, 0.97);
                lay_dot(c, s.pics.cyan, head, 26.0 * u, 0.8 * fade * base);
                lay_dot(c, s.pics.hot, head, 10.0 * u, fade * base);
                c.opacity = base;
                c.star(head[0], head[1], 13.0 * u, "#ffffff", 0.85 * fade);
            }
        }
    }
    c.restore(saved);
}
