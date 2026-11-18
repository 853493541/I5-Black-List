//! The cyber scene's pictures worked out per pixel, as cyber.py makes them once: the night, a
//! strike's flash, the tubes' glow and the round glows.

use super::light::{bloom, glow, noise, picture, rgb, smooth, stroke, Pic, Plane};
use super::{CYAN, INDIGO, MAGENTA, NIGHT, SOFT, VIOLET};
use crate::draw::Pt;

/// cyber._field at one pixel of the quarter-size picture: x, y in points, how clear of the names,
/// how near the edge.
fn field(xs: usize, ys: usize, width: f64, height: f64, u: f64) -> (f64, f64, f64, f64) {
    let (x, y) = ((xs as f64 + 0.5) / SOFT, (ys as f64 + 0.5) / SOFT);
    let r = 120.0 * u;
    let dx = (width * 0.13 + r - x).max(x - width * 0.94 + r).max(0.0);
    let dy = (height * 0.29 + r - y).max(y - height * 0.84 + r).max(0.0);
    let clear = smooth(0.0, 150.0 * u, dx.hypot(dy) - r);
    let rim = 1.0 - smooth(0.0, 300.0 * u, x.min(width - x).min(y.min(height - y)));
    (x, y, clear, rim)
}

pub fn soft_size(width: f64, height: f64) -> (usize, usize) {
    (((width * SOFT).round() as usize).max(1), ((height * SOFT).round() as usize).max(1))
}

fn mix3(a: [f32; 3], b: [f32; 3], g: f64) -> [f64; 3] {
    std::array::from_fn(|k| f64::from(a[k]) * (1.0 - g) + f64::from(b[k]) * g)
}

/// cyber._night: indigo night at the edges, darkest behind the panels, pooling violet and plum.
pub fn night(width: f64, height: f64, u: f64, panels: &[[f64; 4]; 2]) -> Pic {
    let (w, h) = soft_size(width, height);
    let smog = noise(w, h, 110.0 * u * SOFT, 3, 9);
    let pools = [(0.0, 0.0, 600.0, "#1d0a4a"), (width, 0.0, 620.0, "#0d0f4d"), (0.0, height, 640.0, "#33082f"), (width, height, 620.0, "#0b1245")];
    let spills = [(0.0, height * 0.55, 320.0, MAGENTA, 0.08), (width * 0.5, 0.0, 420.0, VIOLET, 0.1), (0.0, height, 420.0, MAGENTA, 0.14), (width, height, 400.0, CYAN, 0.1)];
    picture(w, h, |xs, ys| {
        let (x, y, clear, rim) = field(xs, ys, width, height, u);
        let s = f64::from(smog.at(xs, ys));
        let mut dark = clear * (0.42 + 0.5 * rim) * (0.85 + 0.3 * s);
        let above = 1.0 - smooth(height * 0.29 - 26.0 * u, height * 0.29, y);
        for b in panels {
            let dx = (b[0] - x).max(x - b[0] - b[2]).max(0.0);
            let dy = (b[1] - y).max(y - b[1] - b[3]).max(0.0);
            dark = dark.max(0.88 * (1.0 - smooth(0.0, 60.0 * u, dx.hypot(dy))) * above);
        }
        let mut tone = mix3(rgb(INDIGO), rgb(NIGHT), rim);
        for (cx, cy, reach, tint) in pools {
            let reach = reach * u;
            let g = (-((x - cx).powi(2) + (y - cy).powi(2)) / (reach * reach) * 2.0).exp() * (0.6 + 0.5 * s) * 0.9;
            let t = rgb(tint);
            tone = std::array::from_fn(|k| tone[k] * (1.0 - g) + f64::from(t[k]) * g);
        }
        let mut light = tone.map(|v| v * dark);
        let mut amount = dark;
        for (cx, cy, reach, tint, strength) in spills {
            let reach = reach * u;
            let g = (-((x - cx).powi(2) + (y - cy).powi(2)) / (reach * reach) * 2.2).exp() * strength * clear * s * 2.0;
            let t = rgb(tint);
            light = std::array::from_fn(|k| light[k] + g * f64::from(t[k]));
            amount += g;
        }
        (light.map(|v| (v / amount.max(1e-4)) as f32), amount.clamp(0.0, 0.92) as f32)
    })
}

/// cyber._flash: one side's edges lit by a strike, blue-white at the edge through cyan to violet.
pub fn flash(width: f64, height: f64, gap: [f64; 4], u: f64, side: i32) -> Pic {
    let (w, h) = soft_size(width, height);
    let (ice, cyan, violet) = (rgb("#e9fdff"), rgb(CYAN), rgb(VIOLET));
    picture(w, h, |xs, ys| {
        let (x, y, clear, rim) = field(xs, ys, width, height, u);
        let half = if side < 0 { 1.0 - smooth(width * 0.2, width * 0.75, x) } else { smooth(width * 0.25, width * 0.8, x) };
        let away = (gap[0] - x).max(x - gap[0] - gap[2]).max(0.0).hypot((gap[1] - y).max(0.0));
        let light = rim.powf(1.6) * clear * half * smooth(0.0, 60.0 * u, away);
        let c: [f64; 3] = std::array::from_fn(|k| {
            f64::from(ice[k]) * light * light + f64::from(cyan[k]) * light * (1.0 - light) * 1.6 + f64::from(violet[k]) * (1.0 - light) * 0.3
        });
        let top = c[0].max(c[1]).max(c[2]).max(1e-4);
        (c.map(|v| (v / top) as f32), (light * 0.36) as f32)
    })
}

/// cyber._frame_glow: the light one tube throws, at a quarter of the size.
pub fn frame_glow(width: f64, height: f64, points: &[Pt], tint: &str, u: f64) -> Pic {
    let (w, h) = soft_size(width, height);
    let mut m = Plane::new(w, h);
    let scaled: Vec<Pt> = points.iter().map(|p| [p[0] * SOFT, p[1] * SOFT]).collect();
    stroke(&mut m, &scaled, 5.0 * u * SOFT, 1.0);
    bloom(&m, tint, &[(1.5, 1.1), (5.0, 0.9), (14.0, 0.7)], 0.4)
}

/// cyber._dot: a round glow, a hot middle going white by white, the tint fading round it.
pub fn dot(color: [f32; 3], white: f32, side: usize) -> Pic {
    let half = (side as f32 - 1.0) / 2.0;
    glow(side, side, |xs, ys| {
        let r = (xs as f32 - half).hypot(ys as f32 - half) / (side as f32 / 2.0);
        let halo = (-(r * 2.4).powi(2)).exp() * 0.75 + (-r * 5.5).exp() * 0.5;
        let core = (-(r * 9.0).powi(2)).exp();
        let fade = ((1.0 - r) * 4.0).clamp(0.0, 1.0);
        std::array::from_fn(|k| (halo * color[k] + core * (color[k] * 0.5 + white)) * fade)
    })
}
