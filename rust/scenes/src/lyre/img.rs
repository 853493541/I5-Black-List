//! Pictures worked out per pixel on the CPU, as lyre.py and light.py do it with numpy: one-channel maps,
//! straight color, blur, value noise, relief lighting, colour ramps, "over", and the 8-bit premultiplied
//! picture that is laid on the screen.

use super::npr::Pcg64;

pub type Rgb = [f32; 3];

/// One value a pixel, row by row.
#[derive(Clone)]
pub struct Map {
    pub w: usize,
    pub h: usize,
    pub v: Vec<f32>,
}

/// Straight color a pixel.
#[derive(Clone)]
pub struct Color {
    pub w: usize,
    pub h: usize,
    pub v: Vec<Rgb>,
}

/// A picture as the screen takes it: premultiplied RGBA bytes.
#[derive(Clone, Default)]
pub struct Pic {
    pub w: usize,
    pub h: usize,
    pub px: Vec<[u8; 4]>,
}

pub fn rgb(hex: &str) -> Rgb {
    let n = u32::from_str_radix(hex.trim_start_matches('#'), 16).unwrap_or(0);
    [((n >> 16) & 255) as f32 / 255.0, ((n >> 8) & 255) as f32 / 255.0, (n & 255) as f32 / 255.0]
}

pub fn smooth(e0: f32, e1: f32, x: f32) -> f32 {
    let k = ((x - e0) / (e1 - e0)).clamp(0.0, 1.0);
    k * k * (3.0 - 2.0 * k)
}

pub fn lerp3(a: Rgb, b: Rgb, k: f32) -> Rgb {
    [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k]
}

pub fn scale3(a: Rgb, k: f32) -> Rgb {
    [a[0] * k, a[1] * k, a[2] * k]
}

pub fn add3(a: Rgb, b: Rgb) -> Rgb {
    [a[0] + b[0], a[1] + b[1], a[2] + b[2]]
}

/// np.interp along stops (position, color), held flat past the ends.
pub fn ramp(stops: &[(f32, &str)], k: f32) -> Rgb {
    let first = stops[0];
    if k <= first.0 {
        return rgb(first.1);
    }
    for pair in stops.windows(2) {
        let ((a, ca), (b, cb)) = (pair[0], pair[1]);
        if k <= b {
            return lerp3(rgb(ca), rgb(cb), (k - a) / (b - a));
        }
    }
    rgb(stops[stops.len() - 1].1)
}

impl Map {
    pub fn new(w: usize, h: usize, fill: f32) -> Self {
        Self { w, h, v: vec![fill; w * h] }
    }

    pub fn from_fn(w: usize, h: usize, f: impl Fn(f32, f32) -> f32) -> Self {
        let mut v = Vec::with_capacity(w * h);
        for y in 0..h {
            for x in 0..w {
                v.push(f(x as f32, y as f32));
            }
        }
        Self { w, h, v }
    }

    pub fn at(&self, x: usize, y: usize) -> f32 {
        self.v[y * self.w + x]
    }

    pub fn map(&self, f: impl Fn(f32) -> f32) -> Self {
        Self { w: self.w, h: self.h, v: self.v.iter().map(|&a| f(a)).collect() }
    }

    pub fn zip(&self, other: &Map, f: impl Fn(f32, f32) -> f32) -> Self {
        Self { w: self.w, h: self.h, v: self.v.iter().zip(&other.v).map(|(&a, &b)| f(a, b)).collect() }
    }

    pub fn max(&self) -> f32 {
        self.v.iter().copied().fold(f32::MIN, f32::max)
    }

    /// np.roll(np.roll(a, dy, axis=0), dx, axis=1).
    pub fn roll(&self, dy: i64, dx: i64) -> Self {
        let (w, h) = (self.w as i64, self.h as i64);
        let mut v = vec![0.0; self.v.len()];
        for y in 0..h {
            let sy = (y - dy).rem_euclid(h);
            for x in 0..w {
                v[(y * w + x) as usize] = self.v[(sy * w + (x - dx).rem_euclid(w)) as usize];
            }
        }
        Self { w: self.w, h: self.h, v }
    }

    /// light.blur: three box blurs along each axis, edges held.
    pub fn blur(&self, sigma: f64) -> Self {
        let r = ((sigma * 0.9).round() as usize).max(1);
        let mut out = self.v.clone();
        let mut line = Vec::new();
        let mut sums = Vec::new();
        for axis in 0..2 {
            let (n, count, stride, step) = if axis == 0 { (self.h, self.w, 1, self.w) } else { (self.w, self.h, self.w, 1) };
            for _ in 0..3 {
                for c in 0..count {
                    line.clear();
                    line.extend((0..n).map(|i| out[c * stride + i * step]));
                    sums.clear();
                    let mut acc = 0f64;
                    // pad r + 1 before and r after with the edge values, running sums.
                    for i in 0..(n + 2 * r + 1) {
                        let j = (i as i64 - r as i64 - 1).clamp(0, n as i64 - 1) as usize;
                        acc += f64::from(line[j]);
                        sums.push(acc);
                    }
                    for i in 0..n {
                        out[c * stride + i * step] = ((sums[i + 2 * r + 1] - sums[i]) / (2 * r + 1) as f64) as f32;
                    }
                }
            }
        }
        Self { w: self.w, h: self.h, v: out }
    }

    /// np.gradient: (along y, along x).
    pub fn gradient(&self) -> (Map, Map) {
        let (w, h) = (self.w, self.h);
        let mut gy = Map::new(w, h, 0.0);
        let mut gx = Map::new(w, h, 0.0);
        let d = |a: f32, b: f32, two: bool| if two { (a - b) / 2.0 } else { a - b };
        for y in 0..h {
            for x in 0..w {
                let i = y * w + x;
                gy.v[i] = if h < 2 {
                    0.0
                } else if y == 0 {
                    self.v[i + w] - self.v[i]
                } else if y == h - 1 {
                    self.v[i] - self.v[i - w]
                } else {
                    d(self.v[i + w], self.v[i - w], true)
                };
                gx.v[i] = if w < 2 {
                    0.0
                } else if x == 0 {
                    self.v[i + 1] - self.v[i]
                } else if x == w - 1 {
                    self.v[i] - self.v[i - 1]
                } else {
                    d(self.v[i + 1], self.v[i - 1], true)
                };
            }
        }
        (gy, gx)
    }
}

/// lyre._relief: diffuse and specular light on a height field.
pub fn relief(height: &Map, gain: f32, light: [f32; 3]) -> (Map, Map) {
    let (gy, gx) = height.gradient();
    let half = {
        let h = [light[0], light[1], light[2] + 1.0];
        let n = (h[0] * h[0] + h[1] * h[1] + h[2] * h[2]).sqrt();
        [h[0] / n, h[1] / n, h[2] / n]
    };
    let mut diffuse = Map::new(height.w, height.h, 0.0);
    let mut spec = Map::new(height.w, height.h, 0.0);
    for i in 0..height.v.len() {
        let (nx, ny) = (-gx.v[i] * gain, -gy.v[i] * gain);
        let n = (nx * nx + ny * ny + 1.0).sqrt();
        let (nx, ny, nz) = (nx / n, ny / n, 1.0 / n);
        diffuse.v[i] = (nx * light[0] + ny * light[1] + nz * light[2]).clamp(0.0, 1.0);
        spec.v[i] = (nx * half[0] + ny * half[1] + nz * half[2]).clamp(0.0, 1.0).powi(28);
    }
    (diffuse, spec)
}

/// light.noise: smooth value noise, 0..1, octaves each half the size of the last, numpy's numbers.
pub fn noise(width: usize, height: usize, scale: f64, octaves: u32, seed: u64) -> Map {
    let mut rnd = Pcg64::new(seed);
    let mut out = vec![0f32; width * height];
    let (mut total, mut amp) = (0f64, 1f64);
    for octave in 0..octaves {
        let cell = (scale / f64::from(1u32 << octave)).max(2.0);
        let gw = (width as f64 / cell) as usize + 3;
        let gh = (height as f64 / cell) as usize + 3;
        let grid = rnd.f32s(gw * gh);
        let cellf = cell as f32;
        let split = |i: usize| {
            let f = i as f32 / cellf;
            let i0 = f as usize;
            let s = f - i0 as f32;
            (i0, s * s * (3.0 - 2.0 * s))
        };
        let xs: Vec<(usize, f32)> = (0..width).map(split).collect();
        let ys: Vec<(usize, f32)> = (0..height).map(split).collect();
        let mut across = vec![0f32; gh * width];
        for gy in 0..gh {
            for (x, &(x0, sx)) in xs.iter().enumerate() {
                across[gy * width + x] = grid[gy * gw + x0] * (1.0 - sx) + grid[gy * gw + x0 + 1] * sx;
            }
        }
        let a = amp as f32;
        for (y, &(y0, sy)) in ys.iter().enumerate() {
            for x in 0..width {
                out[y * width + x] += (across[y0 * width + x] * (1.0 - sy) + across[(y0 + 1) * width + x] * sy) * a;
            }
        }
        total += amp;
        amp *= 0.5;
    }
    let t = total as f32;
    Map { w: width, h: height, v: out.into_iter().map(|v| v / t).collect() }
}

impl Color {
    pub fn new(w: usize, h: usize, fill: Rgb) -> Self {
        Self { w, h, v: vec![fill; w * h] }
    }

    pub fn from_fn(w: usize, h: usize, f: impl Fn(usize) -> Rgb) -> Self {
        Self { w, h, v: (0..w * h).map(f).collect() }
    }
}

/// lyre._over: c at a laid over color at alpha, straight color, in place.
pub fn over(color: &mut Color, alpha: &mut Map, c: impl Fn(usize) -> Rgb, a: &Map) {
    for i in 0..alpha.v.len() {
        let ai = a.v[i].clamp(0.0, 1.0);
        if ai <= 0.0 {
            continue;
        }
        let below = alpha.v[i];
        let out = ai + below * (1.0 - ai);
        let ci = c(i);
        let k = below * (1.0 - ai);
        let o = color.v[i];
        let m = out.max(1e-5);
        color.v[i] = [(ci[0] * ai + o[0] * k) / m, (ci[1] * ai + o[1] * k) / m, (ci[2] * ai + o[2] * k) / m];
        alpha.v[i] = out;
    }
}

/// lyre._light: light (may run over 1) as straight color and alpha, as light.glow makes it.
pub fn light_of(w: usize, h: usize, f: impl Fn(usize) -> Rgb) -> (Color, Map) {
    let mut color = Color::new(w, h, [0.0; 3]);
    let mut alpha = Map::new(w, h, 0.0);
    for i in 0..w * h {
        let l = f(i).map(|v| v.max(0.0));
        let over = (l[0].max(l[1]).max(l[2]) - 1.0).max(0.0) * 0.6;
        let l = l.map(|v| v + over);
        let a = l[0].max(l[1]).max(l[2]).clamp(0.0, 1.0);
        let m = a.max(1e-4);
        color.v[i] = l.map(|v| v.clamp(0.0, 1.0) / m);
        alpha.v[i] = a;
    }
    (color, alpha)
}

/// light.picture: straight color and alpha as 8-bit premultiplied RGBA.
pub fn picture(color: &Color, alpha: &Map) -> Pic {
    let px = color
        .v
        .iter()
        .zip(&alpha.v)
        .map(|(c, &a)| {
            let a = a.clamp(0.0, 1.0);
            let q = |v: f32| ((v.clamp(0.0, 1.0) * a) * 255.0 + 0.5) as u8;
            [q(c[0]), q(c[1]), q(c[2]), (a * 255.0 + 0.5) as u8]
        })
        .collect();
    Pic { w: color.w, h: color.h, px }
}

/// A grid's pixel coordinates (x, y) for index i.
pub fn xy_of(w: usize, i: usize) -> (f32, f32) {
    ((i % w) as f32, (i / w) as f32)
}
