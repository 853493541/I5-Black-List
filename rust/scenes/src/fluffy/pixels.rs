//! Pictures worked out per pixel, as love_scenes/light.py does with numpy: planes of floats,
//! light.blur's three box blurs, light.noise, np.gradient, shapes filled with exact area coverage
//! (as QPainter's antialiasing does), and RGBA pictures, premultiplied bytes as QImage keeps them.

use super::pcg::Rng;
use crate::draw::Pt;

/// A plane of floats, row by row.
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

    pub fn map(&self, f: impl Fn(f32) -> f32) -> Self {
        Self { w: self.w, h: self.h, v: self.v.iter().map(|&x| f(x)).collect() }
    }

    pub fn zip(&self, other: &Self, f: impl Fn(f32, f32) -> f32) -> Self {
        Self { w: self.w, h: self.h, v: self.v.iter().zip(&other.v).map(|(&a, &b)| f(a, b)).collect() }
    }

    /// np.roll down by `rows` (and right by `cols`), wrapping round.
    pub fn roll(&self, rows: usize, cols: usize) -> Self {
        let mut out = Self::new(self.w, self.h);
        for y in 0..self.h {
            for x in 0..self.w {
                out.v[((y + rows) % self.h) * self.w + (x + cols) % self.w] = self.v[y * self.w + x];
            }
        }
        out
    }
}

/// Python's round(): halves to even.
pub fn pyround(x: f64) -> f64 {
    x.round_ties_even()
}

/// light.blur: about a Gaussian, three box blurs along each axis (down first), edges repeated.
pub fn blur(a: &Plane, sigma: f64) -> Plane {
    let r = pyround(sigma * 0.9).max(1.0) as usize;
    let mut out = a.clone();
    let (w, h) = (a.w, a.h);
    let mut line = Vec::new();
    for axis in 0..2 {
        let (n, lines) = if axis == 0 { (h, w) } else { (w, h) };
        let at = |l: usize, i: usize| if axis == 0 { i * w + l } else { l * w + i };
        for _ in 0..3 {
            for l in 0..lines {
                line.clear();
                line.extend((0..n).map(|i| out.v[at(l, i)]));
                // cumsum over the padded line: r + 1 copies of the first, r of the last.
                let padded = |j: usize| line[j.saturating_sub(r + 1).min(n - 1)];
                let mut sums = Vec::with_capacity(n + 2 * r + 1);
                let mut acc = 0f32;
                for j in 0..n + 2 * r + 1 {
                    acc += padded(j);
                    sums.push(acc);
                }
                for i in 0..n {
                    out.v[at(l, i)] = (sums[i + 2 * r + 1] - sums[i]) / (2 * r + 1) as f32;
                }
            }
        }
    }
    out
}

/// light.noise: smooth value noise, 0..1, octaves of it each half the size of the last.
pub fn noise(width: usize, height: usize, scale: f64, octaves: u32, seed: u32) -> Plane {
    let mut rng = Rng::new(seed);
    let mut out = Plane::new(width, height);
    let (mut total, mut amp) = (0.0f64, 1.0f64);
    for octave in 0..octaves {
        let cell = (scale / f64::from(1u32 << octave)).max(2.0);
        let (gw, gh) = ((width as f64 / cell) as usize + 3, (height as f64 / cell) as usize + 3);
        let grid = rng.grid(gh, gw);
        let split = |i: usize| {
            let f = f64::from(i as f32 / cell as f32);
            let i0 = f as usize;
            let s = f - i0 as f64;
            (i0, s * s * (3.0 - 2.0 * s))
        };
        let xs: Vec<(usize, f64)> = (0..width).map(split).collect();
        for y in 0..height {
            let (y0, sy) = split(y);
            for (x, &(x0, sx)) in xs.iter().enumerate() {
                let g = |r: usize, c: usize| f64::from(grid[r * gw + c]);
                let top = g(y0, x0) * (1.0 - sx) + g(y0, x0 + 1) * sx;
                let bottom = g(y0 + 1, x0) * (1.0 - sx) + g(y0 + 1, x0 + 1) * sx;
                let v = &mut out.v[y * width + x];
                *v = (f64::from(*v) + (top * (1.0 - sy) + bottom * sy) * amp) as f32;
            }
        }
        total += amp;
        amp *= 0.5;
    }
    out.map(|v| (f64::from(v) / total) as f32)
}

/// np.gradient of a plane: (down, across), central inside, one-sided at the edges.
pub fn gradient(a: &Plane) -> (Plane, Plane) {
    let (w, h) = (a.w, a.h);
    let d = |v: &[f32], i: usize, n: usize, step: usize| -> f32 {
        if n < 2 {
            0.0
        } else if i == 0 {
            v[step] - v[0]
        } else if i == n - 1 {
            v[i * step] - v[(i - 1) * step]
        } else {
            (v[(i + 1) * step] - v[(i - 1) * step]) / 2.0
        }
    };
    let mut gy = Plane::new(w, h);
    let mut gx = Plane::new(w, h);
    for y in 0..h {
        for x in 0..w {
            gy.v[y * w + x] = d(&a.v[x..], y, h, w);
            gx.v[y * w + x] = d(&a.v[y * w..], x, w, 1);
        }
    }
    (gy, gx)
}

/// A filled shape: polygons, each with the sign its winding counts with.
pub type Shape = Vec<(f32, Vec<Pt>)>;

/// How much of each pixel `shape` covers, mapped by `to` into pixels: exact area coverage, the
/// windings summed (so overlapping parts of one sign fill once).
pub fn coverage(w: usize, h: usize, shape: &Shape, to: &dyn Fn(Pt) -> Pt) -> Plane {
    let stride = w + 2;
    let mut acc = vec![0f32; stride * h];
    for (sign, poly) in shape {
        let n = poly.len();
        for i in 0..n {
            let (a, b) = (to(poly[i]), to(poly[(i + 1) % n]));
            line(&mut acc, stride, w, h, a, b, *sign);
        }
    }
    let mut out = Plane::new(w, h);
    for y in 0..h {
        let mut sum = 0f32;
        for x in 0..w {
            sum += acc[y * stride + x];
            out.v[y * w + x] = sum.abs().min(1.0);
        }
    }
    out
}

fn line(acc: &mut [f32], stride: usize, w: usize, h: usize, p0: Pt, p1: Pt, sign: f32) {
    if (p0[1] - p1[1]).abs() < 1e-9 {
        return;
    }
    let (dir, p0, p1) = if p0[1] < p1[1] { (sign, p0, p1) } else { (-sign, p1, p0) };
    let dxdy = (p1[0] - p0[0]) / (p1[1] - p0[1]);
    let top = p0[1].max(0.0);
    let mut x = p0[0] + (top - p0[1]) * dxdy;
    let wf = w as f64;
    for y in (top as usize)..h.min(p1[1].ceil().max(0.0) as usize) {
        let dy = ((y + 1) as f64).min(p1[1]) - (y as f64).max(p0[1]);
        let xnext = x + dxdy * dy;
        let d = (dy as f32) * dir;
        let (x0, x1) = if x < xnext { (x, xnext) } else { (xnext, x) };
        let (x0, x1) = (x0.clamp(0.0, wf), x1.clamp(0.0, wf));
        let row = &mut acc[y * stride..(y + 1) * stride];
        let x0f = x0.floor();
        let x0i = x0f as usize;
        let x1i = x1.ceil() as usize;
        if x1i <= x0i + 1 {
            let xm = (0.5 * (x0 + x1) - x0f) as f32;
            row[x0i] += d - d * xm;
            row[x0i + 1] += d * xm;
        } else {
            let s = (1.0 / (x1 - x0)) as f32;
            let fx0 = (x0 - x0f) as f32;
            let a0 = 0.5 * s * (1.0 - fx0) * (1.0 - fx0);
            let fx1 = (x1 - x1.ceil() + 1.0) as f32;
            let am = 0.5 * s * fx1 * fx1;
            row[x0i] += d * a0;
            if x1i == x0i + 2 {
                row[x0i + 1] += d * (1.0 - a0 - am);
            } else {
                let a1 = s * (1.5 - fx0);
                row[x0i + 1] += d * (a1 - a0);
                for v in &mut row[x0i + 2..x1i - 1] {
                    *v += d * s;
                }
                let a2 = a1 + (x1i - x0i - 3) as f32 * s;
                row[x1i - 1] += d * (1.0 - a2 - am);
            }
            row[x1i] += d * am;
        }
        x = xnext;
    }
}

/// light.mask: a shape's coverage as a Grayscale8 QImage keeps it.
pub fn mask(w: usize, h: usize, shape: &Shape, to: &dyn Fn(Pt) -> Pt) -> Plane {
    coverage(w, h, shape, to).map(|c| (c * 255.0).round() / 255.0)
}

/// An RGBA picture, premultiplied bytes.
#[derive(Clone)]
pub struct Canvas {
    pub w: usize,
    pub h: usize,
    pub px: Vec<[u8; 4]>,
}

impl Canvas {
    pub fn new(w: usize, h: usize) -> Self {
        Self { w, h, px: vec![[0; 4]; w * h] }
    }

    /// light.picture: from straight color (three planes) and alpha, 0..1.
    pub fn picture(color: &[Plane; 3], alpha: &Plane) -> Self {
        let mut out = Self::new(alpha.w, alpha.h);
        for (i, px) in out.px.iter_mut().enumerate() {
            let a = alpha.v[i].clamp(0.0, 1.0);
            let byte = |v: f32| (v * 255.0 + 0.5) as u8;
            *px = [byte(color[0].v[i].clamp(0.0, 1.0) * a), byte(color[1].v[i].clamp(0.0, 1.0) * a), byte(color[2].v[i].clamp(0.0, 1.0) * a), byte(a)];
        }
        out
    }

    /// Fills where `cover` is with a color of alpha, over what is there (QPainter's source over).
    pub fn fill(&mut self, cover: &Plane, color: [f32; 3], alpha: f64) {
        let a = (alpha.clamp(0.0, 1.0) * 255.0).round() as f32;
        let src: [f32; 4] = [(color[0] * 255.0).round() * a / 255.0, (color[1] * 255.0).round() * a / 255.0, (color[2] * 255.0).round() * a / 255.0, a];
        self.fill_with(cover, |_| src);
    }

    /// Fills where `cover` is with premultiplied 0..255 colors per pixel index.
    pub fn fill_with(&mut self, cover: &Plane, src: impl Fn(usize) -> [f32; 4]) {
        for (i, px) in self.px.iter_mut().enumerate() {
            let c = (cover.v[i] * 255.0).round() / 255.0;
            if c <= 0.0 {
                continue;
            }
            let s = src(i);
            let keep = 1.0 - s[3] * c / 255.0;
            for k in 0..4 {
                px[k] = (s[k] * c + f32::from(px[k]) * keep).round().clamp(0.0, 255.0) as u8;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_square_covers_its_area() {
        let square: Shape = vec![(1.0, vec![[1.5, 1.0], [3.5, 1.0], [3.5, 3.0], [1.5, 3.0]])];
        let c = coverage(5, 4, &square, &|p| p);
        assert!((c.v[5 + 1] - 0.5).abs() < 1e-6 && (c.v[5 + 2] - 1.0).abs() < 1e-6 && (c.v[5 + 3] - 0.5).abs() < 1e-6);
        let reversed: Shape = vec![(-1.0, square[0].1.iter().rev().copied().collect())];
        assert_eq!(coverage(5, 4, &reversed, &|p| p).v, c.v);
    }

    #[test]
    fn blur_keeps_a_flat_plane_and_noise_is_numpys() {
        let flat = Plane { w: 7, h: 5, v: vec![0.25; 35] };
        assert!(blur(&flat, 2.0).v.iter().all(|v| (v - 0.25).abs() < 1e-6));
        // light.noise(4, 3, 3.0, 2, 5)[1]
        let n = noise(4, 3, 3.0, 2, 5);
        let want = [0.521_187_84_f32, 0.552_589_5, 0.600_504_6, 0.585_129_3];
        assert!(n.v[4..8].iter().zip(want).all(|(a, b)| (a - b).abs() < 1e-6), "{:?}", &n.v[4..8]);
    }
}
