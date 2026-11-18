//! The glass heart's picture, ported from ice.py's `_glass` (numpy) line for line: a height field
//! rising in a rounded bevel from the outline, shaded like clear ice-blue glass. Made once per size
//! on the CPU, as the Python scene caches it, and laid on each frame by the shader.

use super::heart_points;
use crate::draw::{hex, Pt};

fn smooth(e0: f64, e1: f64, x: f64) -> f64 {
    let k = ((x - e0) / (e1 - e0)).clamp(0.0, 1.0);
    k * k * (3.0 - 2.0 * k)
}

fn rgb(color: &str) -> [f64; 3] {
    hex(color).map(f64::from)
}

fn seg_dist(p: Pt, a: Pt, b: Pt, eps: f64) -> f64 {
    let (dx, dy) = (b[0] - a[0], b[1] - a[1]);
    let k = (((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy + eps)).clamp(0.0, 1.0);
    (p[0] - a[0] - k * dx).hypot(p[1] - a[1] - k * dy)
}

/// Coverage of the pixel centred at p by a closed outline: antialiased from the distance to its edge.
pub fn cover(p: Pt, ring: &[Pt]) -> f64 {
    let mut d = f64::MAX;
    let mut inside = false;
    for (i, &a) in ring.iter().enumerate() {
        let b = ring[(i + 1) % ring.len()];
        d = d.min(seg_dist(p, a, b, 1e-12));
        if (a[1] > p[1]) != (b[1] > p[1]) && p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0] {
            inside = !inside;
        }
    }
    if inside { (0.5 + d).min(1.0) } else { (0.5 - d).max(0.0) }
}

/// ice._blur: three box blurs along each axis (rows first), edges held.
fn blur(a: &mut [f64], side: usize, sigma: f64) {
    let r = ((sigma * 0.9).round_ties_even() as usize).max(1);
    let mut line = vec![0.0; side];
    for axis in 0..2 {
        for _ in 0..3 {
            for j in 0..side {
                let at = |i: usize| if axis == 0 { i * side + j } else { j * side + i };
                for (i, v) in line.iter_mut().enumerate() {
                    let sum: f64 = (i as isize - r as isize..=(i + r) as isize).map(|m| a[at(m.clamp(0, side as isize - 1) as usize)]).sum();
                    *v = sum / (2 * r + 1) as f64;
                }
                for (i, v) in line.iter().enumerate() {
                    a[at(i)] = *v;
                }
            }
        }
    }
}

/// np.gradient along one axis: central inside, one-sided at the ends.
fn grad(f: &[f64], side: usize, i: usize, j: usize, along_y: bool) -> f64 {
    let at = |k: usize| if along_y { f[k * side + j] } else { f[i * side + k] };
    let k = if along_y { i } else { j };
    if k == 0 {
        at(1) - at(0)
    } else if k == side - 1 {
        at(k) - at(k - 1)
    } else {
        (at(k + 1) - at(k - 1)) / 2.0
    }
}

/// The picture: side x side premultiplied RGBA bytes, the heart px wide; side = int(px * 1.04) + 4.
pub fn glass(px: usize) -> (usize, Vec<u8>) {
    let side = (px as f64 * 1.04) as usize + 4;
    let pxf = px as f64;
    let (cx, cy) = (side as f64 / 2.0, side as f64 / 2.0 - pxf * 0.145);
    let outline = heart_points(cx, cy, pxf, 120, 0.0);
    let ring = heart_points(cx, cy, pxf, 72, 0.0);
    let n = side * side;
    let mut mask = vec![0.0; n];
    let mut inside = vec![0.0; n];
    let mut dist = vec![0.0; n];
    let half = side.div_ceil(2);
    let mut halves = vec![f64::INFINITY; half * half];
    for (hi, d) in halves.iter_mut().enumerate() {
        let p = [(hi % half * 2) as f64 + 0.5, (hi / half * 2) as f64 + 0.5];
        for (k, &a) in ring.iter().enumerate() {
            *d = d.min(seg_dist(p, a, ring[(k + 1) % ring.len()], 1e-6));
        }
    }
    for i in 0..n {
        let (y, x) = (i / side, i % side);
        mask[i] = (cover([x as f64 + 0.5, y as f64 + 0.5], &outline) * 255.0).round() / 255.0;
        inside[i] = f64::from(u8::from(mask[i] > 0.5));
        dist[i] = halves[y / 2 * half + x / 2];
    }
    let bevel = pxf * 0.2;
    let mut height: Vec<f64> = (0..n).map(|i| (1.0 - (1.0 - (dist[i] / bevel).clamp(0.0, 1.0)).powi(2)).sqrt() * inside[i]).collect();
    blur(&mut height, side, pxf * 0.02);
    for (h, inn) in height.iter_mut().zip(&inside) {
        *h *= inn * bevel;
    }
    let (horizon, sky, ground) = (rgb("#4f8fe0"), rgb("#e8fbff"), rgb("#06123f"));
    let (light, deep) = (rgb("#8fd8ff"), rgb("#1747d8"));
    let lamps: [([f64; 3], [f64; 3], f64, bool); 2] = [([-0.55, -0.62, 0.56], rgb("#ffffff"), 0.85, true), ([0.62, 0.35, 0.7], rgb("#9ff4ff"), 0.5, false)];
    let (glow, cyan) = (rgb("#d9fbff"), rgb("#7fe6ff"));
    let mut out = vec![0u8; n * 4];
    for i in 0..n {
        let (yi, xi) = (i / side, i % side);
        let (gy, gx) = (grad(&height, side, yi, xi, true), grad(&height, side, yi, xi, false));
        let norm = (gx * gx + gy * gy + 1.0).sqrt();
        let (nx, ny, nz) = (-gx / norm, -gy / norm, 1.0 / norm);
        let (rx, ry, rz) = (2.0 * nz * nx, 2.0 * nz * ny, 2.0 * nz * nz - 1.0);
        let up = (-ry).clamp(-1.0, 1.0);
        let env: [f64; 3] = std::array::from_fn(|c| {
            if up > 0.0 { horizon[c] + (sky[c] - horizon[c]) * smooth(0.0, 0.7, up) } else { horizon[c] + (ground[c] - horizon[c]) * smooth(0.0, 0.6, -up) }
        });
        let fresnel = 0.06 + 0.94 * (1.0 - nz).powf(2.2);
        let x = (xi as f64 - cx) / pxf;
        let y = (yi as f64 - cy) / pxf - 0.14;
        let mut lights = [0.0; 3];
        for (l, color, strength, cleft) in &lamps {
            let length = (l[0] * l[0] + l[1] * l[1] + l[2] * l[2]).sqrt();
            let facing = (rx * l[0] + ry * l[1] + rz * l[2]) / length;
            let by = if *cleft { smooth(0.1, 0.22, x.hypot(y + 0.12)) } else { 1.0 };
            let k = smooth(0.9, 0.96, facing) * strength * by;
            for c in 0..3 {
                lights[c] += color[c] * k;
            }
        }
        let deepen = (0.45 + x * 0.5 + y * 0.9).clamp(0.0, 1.0);
        let gathered = (-(((x - 0.12) / 0.2).powi(2) + ((y - 0.16) / 0.13).powi(2))).exp();
        let core = (-((x / 0.3).powi(2) + ((y - 0.02) / 0.26).powi(2))).exp() * 0.25;
        let clear = (0.45 + 0.25 * gathered + 0.3 * core).clamp(0.0, 1.0);
        let turn = ny.atan2(nx);
        let slope = 1.0 - nz;
        let fringe = smooth(0.15, 0.45, slope) * (1.0 - smooth(0.5, 0.8, slope)) * 0.06;
        let env_max = env[0].max(env[1]).max(env[2]);
        let alpha = clear * (1.0 - fresnel) + fresnel * (env_max * 0.6 + 0.5).clamp(0.0, 1.0);
        let alpha = (alpha.max(lights[0].max(lights[1]).max(lights[2])) * mask[i]).clamp(0.0, 1.0);
        for c in 0..3 {
            let tint = light[c] + (deep[c] - light[c]) * deepen;
            let through = tint + glow[c] * 0.6 * gathered + cyan[c] * core;
            let rainbow = 0.5 + 0.5 * (turn * 2.0 + [0.0, 2.1, 4.2][c]).cos();
            let color = through * clear * (1.0 - fresnel) + env[c] * fresnel + rainbow * fringe + lights[c];
            out[i * 4 + c] = ((color * mask[i]).clamp(0.0, 1.0).min(alpha) * 255.0 + 0.5) as u8;
        }
        out[i * 4 + 3] = (alpha * 255.0 + 0.5) as u8;
    }
    (side, out)
}

#[cfg(test)]
mod tests {
    #[test]
    fn clear_in_the_middle_and_bare_outside() {
        let (side, px) = super::glass(64);
        assert_eq!(side, 70);
        let at = |x: usize, y: usize| &px[(y * side + x) * 4..(y * side + x) * 4 + 4];
        assert_eq!(at(1, 1), [0, 0, 0, 0]);
        let mid = at(35, 35);
        assert!(mid[3] > 100 && mid[2] >= mid[0], "{mid:?}");
    }
}
