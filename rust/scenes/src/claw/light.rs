//! love_scenes/light.py: light worked out per pixel on the CPU (masks, blurs, noise, bloom) and kept
//! as premultiplied 8-bit pictures, quantized where the Python scene turns arrays into QImages.

use super::rng::Pcg64;
use crate::draw::hex;

pub type Pt = [f64; 2];

/// A 0..1 value per pixel, `h` rows of `w`.
#[derive(Clone)]
pub struct Gray {
    pub w: usize,
    pub h: usize,
    pub v: Vec<f32>,
}

/// A picture: premultiplied RGBA bytes, as a QImage in Format_RGBA8888_Premultiplied.
#[derive(Clone)]
pub struct Pic {
    pub w: usize,
    pub h: usize,
    pub px: Vec<[u8; 4]>,
}

impl Gray {
    pub fn new(w: usize, h: usize) -> Self {
        Self { w, h, v: vec![0.0; w * h] }
    }

    pub fn from_fn(w: usize, h: usize, f: impl Fn(usize, usize) -> f32) -> Self {
        Self { w, h, v: (0..w * h).map(|i| f(i % w, i / w)).collect() }
    }

    pub fn map(&self, f: impl Fn(f32) -> f32) -> Self {
        Self { w: self.w, h: self.h, v: self.v.iter().map(|&x| f(x)).collect() }
    }

    pub fn at(&self, x: usize, y: usize) -> f32 {
        self.v[y * self.w + x]
    }
}

impl Pic {
    /// Premultiplied floats 0..1 per pixel.
    pub fn floats(&self) -> Vec<[f32; 4]> {
        self.px.iter().map(|p| p.map(|c| f32::from(c) / 255.0)).collect()
    }

    pub fn bytes(&self) -> Vec<u8> {
        self.px.iter().flatten().copied().collect()
    }
}

/// Python's round(): halves to even.
pub fn pyround(x: f64) -> f64 {
    let r = x.round();
    if (x - x.trunc()).abs() == 0.5 && r % 2.0 != 0.0 {
        r - x.signum()
    } else {
        r
    }
}

pub fn rgb(color: &str) -> [f32; 3] {
    hex(color)
}

pub fn smooth(e0: f32, e1: f32, x: f32) -> f32 {
    let k = ((x - e0) / (e1 - e0)).clamp(0.0, 1.0);
    k * k * (3.0 - 2.0 * k)
}

pub fn lerp3(a: [f32; 3], b: [f32; 3], k: f32) -> [f32; 3] {
    std::array::from_fn(|i| a[i] * (1.0 - k) + b[i] * k)
}

/// About a Gaussian blur: three box blurs along each axis, edges padded with the edge value.
pub fn blur(a: &Gray, sigma: f64) -> Gray {
    let r = pyround(sigma * 0.9).max(1.0) as i64;
    let mut out = a.clone();
    let n = (2 * r + 1) as f64;
    for axis in 0..2 {
        let (len, lines) = if axis == 0 { (a.h, a.w) } else { (a.w, a.h) };
        let idx = |line: usize, i: usize| if axis == 0 { i * a.w + line } else { line * a.w + i };
        let mut row = vec![0f64; len];
        for line in 0..lines {
            for _ in 0..3 {
                let get = |i: i64| f64::from(out.v[idx(line, i.clamp(0, len as i64 - 1) as usize)]);
                let mut sum: f64 = (-r..=r).map(get).sum();
                for (i, slot) in row.iter_mut().enumerate() {
                    *slot = sum / n;
                    sum += get(i as i64 + r + 1) - get(i as i64 - r);
                }
                for (i, &v) in row.iter().enumerate() {
                    out.v[idx(line, i)] = v as f32;
                }
            }
        }
    }
    out
}

/// Smooth value noise, 0..1, from numpy's default_rng(seed), as light.noise.
pub fn noise(w: usize, h: usize, scale: f64, octaves: u32, seed: u32) -> Gray {
    let mut rng = Pcg64::new(seed);
    let mut out = vec![0f32; w * h];
    let (mut total, mut amp) = (0f64, 1f64);
    for octave in 0..octaves {
        let cell = (scale / f64::from(1u32 << octave)).max(2.0);
        let (gw, gh) = ((w as f64 / cell) as usize + 3, (h as f64 / cell) as usize + 3);
        let grid: Vec<f32> = (0..gw * gh).map(|_| rng.f32()).collect();
        let axis = |n: usize| -> Vec<(usize, f64)> {
            (0..n)
                .map(|i| {
                    let f = f64::from(i as f32 / cell as f32);
                    let i0 = f as usize;
                    let s = f - i0 as f64;
                    (i0, s * s * (3.0 - 2.0 * s))
                })
                .collect()
        };
        let (xs, ys) = (axis(w), axis(h));
        let g = |x: usize, y: usize| f64::from(grid[y * gw + x]);
        for (y, &(y0, sy)) in ys.iter().enumerate() {
            for (x, &(x0, sx)) in xs.iter().enumerate() {
                let top = g(x0, y0) * (1.0 - sx) + g(x0 + 1, y0) * sx;
                let bottom = g(x0, y0 + 1) * (1.0 - sx) + g(x0 + 1, y0 + 1) * sx;
                out[y * w + x] += ((top * (1.0 - sy) + bottom * sy) * amp) as f32;
            }
        }
        total += amp;
        amp *= 0.5;
    }
    Gray { w, h, v: out.into_iter().map(|v| (f64::from(v) / total) as f32).collect() }
}

fn seg_dist(p: Pt, a: Pt, b: Pt) -> f64 {
    let (abx, aby) = (b[0] - a[0], b[1] - a[1]);
    let k = (((p[0] - a[0]) * abx + (p[1] - a[1]) * aby) / (abx * abx + aby * aby).max(1e-12)).clamp(0.0, 1.0);
    (p[0] - a[0] - abx * k).hypot(p[1] - a[1] - aby * k)
}

/// How much of the pixel centred at p one closed contour covers: from the exact distance to its edge.
pub fn cover(p: Pt, poly: &[Pt]) -> f64 {
    let mut d = f64::MAX;
    let mut inside = false;
    for i in 0..poly.len() {
        let (a, b) = (poly[i], poly[(i + 1) % poly.len()]);
        d = d.min(seg_dist(p, a, b));
        if (a[1] > p[1]) != (b[1] > p[1]) && p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0] {
            inside = !inside;
        }
    }
    if inside {
        (0.5 + d).min(1.0)
    } else {
        (0.5 - d).max(0.0)
    }
}

/// light.mask: contours (in pixels) painted white on black, antialiased, each laid over the last;
/// kept as bytes, as the Grayscale8 picture keeps them.
pub fn mask(w: usize, h: usize, shapes: &[Vec<Pt>]) -> Gray {
    let mut out = Gray::new(w, h);
    for poly in shapes {
        let (mut x0, mut y0, mut x1, mut y1) = (f64::MAX, f64::MAX, f64::MIN, f64::MIN);
        for p in poly {
            (x0, y0, x1, y1) = (x0.min(p[0]), y0.min(p[1]), x1.max(p[0]), y1.max(p[1]));
        }
        let span = |lo: f64, hi: f64, n: usize| ((lo - 1.0).floor().max(0.0) as usize, ((hi + 1.0).ceil().max(0.0) as usize).min(n));
        let ((xa, xb), (ya, yb)) = (span(x0, x1, w), span(y0, y1, h));
        for y in ya..yb {
            for x in xa..xb {
                let c = cover([x as f64 + 0.5, y as f64 + 0.5], poly) as f32;
                let v = &mut out.v[y * w + x];
                *v = c + *v * (1.0 - c);
            }
        }
    }
    out.map(|v| (v * 255.0).round() / 255.0)
}

/// light.picture: straight color and alpha (0..1) to premultiplied bytes.
pub fn picture(w: usize, h: usize, color: impl Fn(usize) -> [f32; 3], alpha: impl Fn(usize) -> f32) -> Pic {
    let px = (0..w * h)
        .map(|i| {
            let a = alpha(i).clamp(0.0, 1.0);
            let c = color(i);
            let q = |v: f32| (v * 255.0 + 0.5) as u8;
            [q(c[0].clamp(0.0, 1.0) * a), q(c[1].clamp(0.0, 1.0) * a), q(c[2].clamp(0.0, 1.0) * a), q(a)]
        })
        .collect();
    Pic { w, h, px }
}

/// A premultiplied pixel's straight color.
pub fn straight(p: [f32; 4]) -> [f32; 3] {
    let a = p[3].max(1e-4);
    [p[0] / a, p[1] / a, p[2] / a]
}

/// light.bloom (with light.glow): core burns white at its middle, the tint spreads round it.
pub fn bloom(core: &Gray, tint: &str, spread: &[(f64, f32)], white: f32) -> Pic {
    let color = rgb(tint);
    let mut halo = vec![0f32; core.v.len()];
    for &(sigma, strength) in spread {
        for (h, b) in halo.iter_mut().zip(blur(core, sigma).v) {
            *h += b * strength;
        }
    }
    let light: Vec<[f32; 3]> = halo
        .iter()
        .zip(&core.v)
        .map(|(&h, &c)| {
            let hot = c.powf(1.5);
            let l: [f32; 3] = std::array::from_fn(|i| (h * color[i] + hot * (color[i] * 0.5 + white * 0.7)).max(0.0));
            let over = (l[0].max(l[1]).max(l[2]) - 1.0).max(0.0);
            l.map(|v| v + over * 0.6)
        })
        .collect();
    let alpha = |i: usize| light[i][0].max(light[i][1]).max(light[i][2]).clamp(0.0, 1.0);
    picture(core.w, core.h, |i| light[i].map(|v| v.clamp(0.0, 1.0) / alpha(i).max(1e-4)), alpha)
}

/// a at (x, y) in its pixels from the middle of its first, bilinear, nothing beyond its edges.
pub fn sample(a: &Gray, x: f64, y: f64) -> f64 {
    let get = |xi: i64, yi: i64| if xi < 0 || yi < 0 || xi >= a.w as i64 || yi >= a.h as i64 { 0.0 } else { f64::from(a.at(xi as usize, yi as usize)) };
    let (x, y) = ((x + 1.0).clamp(0.0, a.w as f64), (y + 1.0).clamp(0.0, a.h as f64));
    let (x0, y0) = (x.floor(), y.floor());
    let (fx, fy) = (x - x0, y - y0);
    let (xi, yi) = (x0 as i64 - 1, y0 as i64 - 1);
    let top = get(xi, yi) * (1.0 - fx) + get(xi + 1, yi) * fx;
    let bottom = get(xi, yi + 1) * (1.0 - fx) + get(xi + 1, yi + 1) * fx;
    top * (1.0 - fy) + bottom * fy
}

/// A PNG as a premultiplied picture.
pub fn load(path: &std::path::Path) -> Result<Pic, String> {
    let img = image::open(path).map_err(|e| format!("{}: {e}", path.display()))?.to_rgba8();
    let px = img.pixels().map(|p| {
        let a = u32::from(p[3]);
        let m = |c: u8| ((u32::from(c) * a + 127) / 255) as u8;
        [m(p[0]), m(p[1]), m(p[2]), p[3]]
    });
    Ok(Pic { w: img.width() as usize, h: img.height() as usize, px: px.collect() })
}

/// QImage.scaled(..., SmoothTransformation) when shrinking: each pixel the area-weighted average of
/// what it covers.
pub fn shrink(src: &Pic, w: usize, h: usize) -> Pic {
    let f = src.floats();
    let (kx, ky) = (src.w as f64 / w as f64, src.h as f64 / h as f64);
    let spans = |n: usize, k: f64, max: usize| -> Vec<Vec<(usize, f64)>> {
        (0..n)
            .map(|i| {
                let (a, b) = (i as f64 * k, (i as f64 + 1.0) * k);
                (a.floor() as usize..(b.ceil() as usize).min(max)).map(|j| (j, (b.min(j as f64 + 1.0) - a.max(j as f64)) / k)).collect()
            })
            .collect()
    };
    let (sx, sy) = (spans(w, kx, src.w), spans(h, ky, src.h));
    let mut px = Vec::with_capacity(w * h);
    for row in &sy {
        for col in &sx {
            let mut acc = [0f64; 4];
            for &(y, wy) in row {
                for &(x, wx) in col {
                    let p = f[y * src.w + x];
                    for c in 0..4 {
                        acc[c] += f64::from(p[c]) * wx * wy;
                    }
                }
            }
            px.push(acc.map(|v| (v * 255.0).round().clamp(0.0, 255.0) as u8));
        }
    }
    Pic { w, h, px }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pyround_halves_to_even() {
        assert_eq!([pyround(2.5), pyround(3.5), pyround(-2.5), pyround(2.4)], [2.0, 4.0, -2.0, 2.0]);
    }

    #[test]
    fn noise_matches_numpy() {
        // light.noise(8, 4, 3.0, 2, 7)[1, 2] and [3, 7], from the Python module.
        let n = noise(8, 4, 3.0, 2, 7);
        assert!((n.at(2, 1) - 0.621_321_4).abs() < 1e-5, "{}", n.at(2, 1));
        assert!((n.at(7, 3) - 0.295_748_56).abs() < 1e-5, "{}", n.at(7, 3));
    }

    #[test]
    fn mask_covers_a_square_with_soft_edges() {
        let m = mask(6, 6, &[vec![[1.0, 1.0], [4.5, 1.0], [4.5, 5.0], [1.0, 5.0]]]);
        assert_eq!(m.at(2, 2), 1.0);
        assert!((m.at(4, 2) - 0.5).abs() < 0.01 && m.at(5, 2) == 0.0);
    }
}
