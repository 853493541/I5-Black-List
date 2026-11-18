//! love_scenes/light.py: light worked out per pixel on the CPU (masks, blurs, value noise) and
//! turned into premultiplied pictures, made once and laid on every frame by the GPU.

use super::npr::Rng;
use crate::draw::hex;

/// A premultiplied RGBA picture, 8 bits a channel, as light.picture makes it.
#[derive(Clone)]
pub struct Pic {
    pub w: usize,
    pub h: usize,
    pub px: Vec<u8>,
}

/// A plane of floats, height by width.
#[derive(Clone)]
pub struct Plane {
    pub w: usize,
    pub h: usize,
    pub v: Vec<f32>,
}

impl Plane {
    pub fn new(w: usize, h: usize) -> Self {
        Self { w, h, v: vec![0.0; w * h] }
    }

    pub fn at(&self, x: usize, y: usize) -> f32 {
        self.v[y * self.w + x]
    }
}

pub fn rgb(color: &str) -> [f32; 3] {
    hex(color)
}

pub fn smooth(e0: f64, e1: f64, x: f64) -> f64 {
    let k = ((x - e0) / (e1 - e0)).clamp(0.0, 1.0);
    k * k * (3.0 - 2.0 * k)
}

/// Python's round: halves to even.
pub fn round_even(x: f64) -> f64 {
    let r = x.round();
    if (x - x.trunc()).abs() == 0.5 && r % 2.0 != 0.0 {
        r - x.signum()
    } else {
        r
    }
}

/// light.blur: three box blurs along each axis from running sums, edges held.
pub fn blur(a: &Plane, sigma: f64) -> Plane {
    let r = round_even(sigma * 0.9).max(1.0) as usize;
    let mut out = a.clone();
    let n = (2 * r + 1) as f32;
    for axis in 0..2 {
        let (len, lines) = if axis == 0 { (out.h, out.w) } else { (out.w, out.h) };
        let idx = |line: usize, i: usize| if axis == 0 { i * out.w + line } else { line * out.w + i };
        let mut sums = vec![0f32; len + 2 * r + 2];
        for _ in 0..3 {
            for line in 0..lines {
                let mut acc = 0f32;
                for (j, s) in sums.iter_mut().enumerate() {
                    let i = j.saturating_sub(r + 1).min(len - 1);
                    acc += out.v[idx(line, i)];
                    *s = acc;
                }
                for i in 0..len {
                    out.v[idx(line, i)] = (sums[i + 2 * r + 1] - sums[i]) / n;
                }
            }
        }
    }
    out
}

/// light.noise: smooth value noise, 0..1, octaves each half the size of the last.
pub fn noise(w: usize, h: usize, scale: f64, octaves: u32, seed: u32) -> Plane {
    let mut rng = Rng::new(seed);
    let mut out = Plane::new(w, h);
    let (mut total, mut amp) = (0.0f64, 1.0f64);
    for octave in 0..octaves {
        let cell = (scale / 2f64.powi(octave as i32)).max(2.0);
        let (gw, gh) = ((w as f64 / cell) as usize + 3, (h as f64 / cell) as usize + 3);
        let grid: Vec<f64> = (0..gw * gh).map(|_| f64::from(rng.random_f32())).collect();
        let at = |i: usize| {
            let f = i as f32 / cell as f32;
            let i0 = f as usize;
            let s = f64::from(f) - i0 as f64;
            (i0, s * s * (3.0 - 2.0 * s))
        };
        let xs: Vec<(usize, f64)> = (0..w).map(at).collect();
        for y in 0..h {
            let (y0, sy) = at(y);
            for (x, &(x0, sx)) in xs.iter().enumerate() {
                let row = |r: usize| grid[r * gw + x0] * (1.0 - sx) + grid[r * gw + x0 + 1] * sx;
                let v = (row(y0) * (1.0 - sy) + row(y0 + 1) * sy) * amp;
                let o = &mut out.v[y * w + x];
                *o = (f64::from(*o) + v) as f32;
            }
        }
        total += amp;
        amp *= 0.5;
    }
    for v in &mut out.v {
        *v /= total as f32;
    }
    out
}

fn seg_dist(p: [f64; 2], a: [f64; 2], b: [f64; 2]) -> f64 {
    let (abx, aby) = (b[0] - a[0], b[1] - a[1]);
    let k = (((p[0] - a[0]) * abx + (p[1] - a[1]) * aby) / (abx * abx + aby * aby).max(1e-12)).clamp(0.0, 1.0);
    (p[0] - a[0] - abx * k).hypot(p[1] - a[1] - aby * k)
}

/// light.mask: a polyline stroked round in a gray (0..1) over what is there, as 8-bit coverage.
pub fn stroke(m: &mut Plane, points: &[[f64; 2]], width: f64, gray: f64) {
    let half = width / 2.0;
    let mut cover = vec![0f64; m.w * m.h];
    for pair in points.windows(2) {
        let (a, b) = (pair[0], pair[1]);
        let x0 = (a[0].min(b[0]) - half - 1.0).floor().max(0.0) as usize;
        let x1 = ((a[0].max(b[0]) + half + 1.0).ceil().max(0.0) as usize).min(m.w);
        let y0 = (a[1].min(b[1]) - half - 1.0).floor().max(0.0) as usize;
        let y1 = ((a[1].max(b[1]) + half + 1.0).ceil().max(0.0) as usize).min(m.h);
        for y in y0..y1 {
            for x in x0..x1 {
                let d = seg_dist([x as f64 + 0.5, y as f64 + 0.5], a, b);
                let c = if half < 0.5 { (1.0 - d).clamp(0.0, 1.0) * half * 2.0 } else { (half + 0.5 - d).clamp(0.0, 1.0) };
                let slot = &mut cover[y * m.w + x];
                *slot = slot.max(c);
            }
        }
    }
    for (v, c) in m.v.iter_mut().zip(cover) {
        if c > 0.0 {
            let k = (c * gray * 255.0).round() / 255.0;
            *v = ((f64::from(*v) * (1.0 - c) + k) * 255.0).round() as f32 / 255.0;
        }
    }
}

/// light.picture: straight color (0..1) and alpha to premultiplied bytes.
pub fn picture(w: usize, h: usize, mut px: impl FnMut(usize, usize) -> ([f32; 3], f32)) -> Pic {
    let mut out = Vec::with_capacity(w * h * 4);
    for y in 0..h {
        for x in 0..w {
            let (c, a) = px(x, y);
            let a = a.clamp(0.0, 1.0);
            let byte = |v: f32| (v * 255.0 + 0.5) as u8;
            out.extend([byte(c[0].clamp(0.0, 1.0) * a), byte(c[1].clamp(0.0, 1.0) * a), byte(c[2].clamp(0.0, 1.0) * a), byte(a)]);
        }
    }
    Pic { w, h, px: out }
}

/// light.glow: light that may run over 1, as a picture as opaque as its brightest channel.
pub fn glow(w: usize, h: usize, mut light: impl FnMut(usize, usize) -> [f32; 3]) -> Pic {
    picture(w, h, |x, y| {
        let mut l = light(x, y).map(|v| v.max(0.0));
        let over = (l[0].max(l[1]).max(l[2]) - 1.0).max(0.0);
        l = l.map(|v| v + over * 0.6);
        let a = l[0].max(l[1]).max(l[2]).clamp(0.0, 1.0);
        (l.map(|v| v.clamp(0.0, 1.0) / a.max(1e-4)), a)
    })
}

/// light.bloom: the core burns white at its middle and the tint spreads round it.
pub fn bloom(core: &Plane, tint: &str, spread: &[(f64, f32)], white: f32) -> Pic {
    let color = rgb(tint);
    let mut halo = vec![0f32; core.v.len()];
    for &(sigma, strength) in spread {
        for (h, b) in halo.iter_mut().zip(blur(core, sigma).v) {
            *h += b * strength;
        }
    }
    glow(core.w, core.h, |x, y| {
        let i = y * core.w + x;
        let c = core.v[i].powf(1.5);
        std::array::from_fn(|k| halo[i] * color[k] + c * (color[k] * 0.5 + white * 0.7))
    })
}

#[cfg(test)]
mod tests {
    use super::{blur, noise, round_even, Plane};

    #[test]
    fn rounds_and_blurs_as_python() {
        assert_eq!((round_even(4.5), round_even(1.35), round_even(12.6), round_even(2.5)), (4.0, 1.0, 13.0, 2.0));
        let mut p = Plane::new(9, 1);
        p.v[4] = 1.0;
        let b = blur(&p, 1.0);
        let total: f32 = b.v.iter().sum();
        assert!((total - 1.0).abs() < 1e-5 && b.v[4] > b.v[3] && b.v[3] > b.v[1]);
    }

    /// light.noise(7, 3, 2.5, 2, 9) from numpy: its first row.
    #[test]
    fn noise_matches_numpy() {
        let n = noise(7, 3, 2.5, 2, 9);
        for (got, want) in n.v[..7].iter().zip(NOISE) {
            assert!((got - want).abs() < 1e-6, "{got} {want}");
        }
    }

    const NOISE: [f32; 7] = [0.530_426, 0.591_848_1, 0.710_704_3, 0.817_575_5, 0.919_970_2, 0.801_845_6, 0.504_195_7];
}
