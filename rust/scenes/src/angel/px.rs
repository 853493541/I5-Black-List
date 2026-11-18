//! Per-pixel work as light.py and angel.py do it with numpy: grids of floats, blurs, slopes, and
//! pictures (premultiplied RGBA bytes) made from color and alpha.

pub struct Grid {
    pub w: usize,
    pub h: usize,
    pub v: Vec<f32>,
}

impl Grid {
    pub fn new(w: usize, h: usize) -> Self {
        Self { w, h, v: vec![0.0; w * h] }
    }

    pub fn from_fn(w: usize, h: usize, f: impl Fn(usize, usize) -> f32) -> Self {
        Self { w, h, v: (0..w * h).map(|i| f(i % w, i / w)).collect() }
    }

    pub fn map(&self, f: impl Fn(f32) -> f32) -> Self {
        Self { w: self.w, h: self.h, v: self.v.iter().map(|&x| f(x)).collect() }
    }

    pub fn zip(&self, o: &Grid, f: impl Fn(f32, f32) -> f32) -> Self {
        Self { w: self.w, h: self.h, v: self.v.iter().zip(&o.v).map(|(&a, &b)| f(a, b)).collect() }
    }

    pub fn at(&self, x: usize, y: usize) -> f32 {
        self.v[y * self.w + x]
    }
}

pub fn smooth(e0: f32, e1: f32, x: f32) -> f32 {
    let k = ((x - e0) / (e1 - e0)).clamp(0.0, 1.0);
    k * k * (3.0 - 2.0 * k)
}

/// light.rgb: "#rrggbb" as 0..1 floats.
pub fn rgb(color: &str) -> [f32; 3] {
    crate::draw::hex(color)
}

/// Python's round(): halves to even.
pub fn pyround(x: f64) -> i64 {
    x.round_ties_even() as i64
}

/// light.blur: three box blurs along each axis (down first), edges held, from running sums.
pub fn blur(a: &Grid, sigma: f64) -> Grid {
    let r = pyround(sigma * 0.9).max(1) as usize;
    let mut out = a.v.clone();
    let k = (2 * r + 1) as f32;
    for axis in 0..2 {
        let (n, lines, stride, step) = if axis == 0 { (a.h, a.w, 1, a.w) } else { (a.w, a.h, a.w, 1) };
        let mut sums = vec![0f32; n + 2 * r + 2];
        for _ in 0..3 {
            for line in 0..lines {
                let base = line * stride;
                let get = |i: isize, out: &[f32]| out[base + (i.clamp(0, n as isize - 1) as usize) * step];
                let mut total = 0f32;
                sums[0] = 0.0;
                for (j, s) in sums.iter_mut().enumerate().skip(1).take(n + 2 * r + 1) {
                    total += get(j as isize - 1 - (r as isize + 1), &out);
                    *s = total;
                }
                for i in 0..n {
                    out[base + i * step] = (sums[i + 2 * r + 2] - sums[i + 1]) / k;
                }
            }
        }
    }
    Grid { w: a.w, h: a.h, v: out }
}

/// np.gradient: (down, across), central inside and one-sided at the edges.
pub fn gradient(a: &Grid) -> (Grid, Grid) {
    let d = |i: usize, n: usize, f: &dyn Fn(usize) -> f32| -> f32 {
        if n < 2 {
            0.0
        } else if i == 0 {
            f(1) - f(0)
        } else if i == n - 1 {
            f(n - 1) - f(n - 2)
        } else {
            (f(i + 1) - f(i - 1)) / 2.0
        }
    };
    let gy = Grid::from_fn(a.w, a.h, |x, y| d(y, a.h, &|k| a.at(x, k)));
    let gx = Grid::from_fn(a.w, a.h, |x, y| d(x, a.w, &|k| a.at(k, y)));
    (gy, gx)
}

/// angel._shift: moved dy down and dx across, zeros brought in.
pub fn shift(a: &Grid, dy: i64, dx: i64) -> Grid {
    Grid::from_fn(a.w, a.h, |x, y| {
        let (sx, sy) = (x as i64 - dx, y as i64 - dy);
        if sx < 0 || sy < 0 || sx >= a.w as i64 || sy >= a.h as i64 {
            0.0
        } else {
            a.at(sx as usize, sy as usize)
        }
    })
}

/// A picture: premultiplied RGBA bytes.
#[derive(Clone, Default)]
pub struct Pic {
    pub w: usize,
    pub h: usize,
    pub px: Vec<u8>,
}

/// light.picture: straight color and alpha, both 0..1, to premultiplied bytes.
pub fn picture(w: usize, h: usize, color: impl Fn(usize) -> [f32; 3], alpha: impl Fn(usize) -> f32) -> Pic {
    let mut px = Vec::with_capacity(w * h * 4);
    for i in 0..w * h {
        let a = alpha(i).clamp(0.0, 1.0);
        let c = color(i);
        for v in c {
            px.push((v.clamp(0.0, 1.0) * a * 255.0 + 0.5) as u8);
        }
        px.push((a * 255.0 + 0.5) as u8);
    }
    Pic { w, h, px }
}

/// light.glow: light (may run over 1) as a picture that adds it over what is under.
pub fn glow(w: usize, h: usize, light: impl Fn(usize) -> [f32; 3]) -> Pic {
    let lit = |i: usize| {
        let l = light(i).map(|v| v.max(0.0));
        let over = (l[0].max(l[1]).max(l[2]) - 1.0).max(0.0);
        l.map(|v| v + over * 0.6)
    };
    picture(
        w,
        h,
        |i| {
            let l = lit(i);
            let a = l[0].max(l[1]).max(l[2]).clamp(0.0, 1.0).max(1e-4);
            l.map(|v| v.clamp(0.0, 1.0) / a)
        },
        |i| {
            let l = lit(i);
            l[0].max(l[1]).max(l[2])
        },
    )
}

/// Gold from its shade to its shine: tone 0..1 picks a color along it (angel.RAMP).
pub fn ramp(tone: f32) -> [f32; 3] {
    const RAMP: [(f32, &str); 7] =
        [(0.0, "#2e1a04"), (0.2, "#6b4410"), (0.42, "#a8721e"), (0.6, "#d6a240"), (0.76, "#f2cf76"), (0.9, "#fff0b8"), (1.0, "#fffbec")];
    let t = tone.clamp(0.0, 1.0);
    for w in RAMP.windows(2) {
        if t <= w[1].0 {
            let k = (t - w[0].0) / (w[1].0 - w[0].0);
            let (a, b) = (rgb(w[0].1), rgb(w[1].1));
            return std::array::from_fn(|i| a[i] + (b[i] - a[i]) * k);
        }
    }
    rgb(RAMP[6].1)
}

/// angel._metal: gold over a height field, lit from the upper left.
pub fn metal(height: &Grid, relief: f32, polish: f32) -> Vec<[f32; 3]> {
    let (gy, gx) = gradient(height);
    (0..height.v.len())
        .map(|i| {
            let (nx, ny) = (-gx.v[i] * relief, -gy.v[i] * relief);
            let norm = (nx * nx + ny * ny + 1.0).sqrt();
            let (nx, ny, nz) = (nx / norm, ny / norm, 1.0 / norm);
            let (lx, ly, lz) = (-0.45, -0.62, 0.64);
            let diffuse = (nx * lx + ny * ly + nz * lz).clamp(0.0, 1.0);
            let (rx, ry, rz) = (2.0 * nz * nx, 2.0 * nz * ny, 2.0 * nz * nz - 1.0);
            let sky = smooth(-0.55, 0.65, -(ry * 0.85 + rx * 0.4));
            let spec = (rx * lx + ry * ly + rz * lz).clamp(0.0, 1.0).powf(8.0 + 18.0 * polish);
            let tone = (0.12 + 0.4 * sky * (0.45 + 0.55 * polish) + 0.42 * diffuse + 0.3 * spec * polish) * (0.8 + 0.2 * polish);
            ramp(tone).map(|c| c + spec * 0.3 * polish)
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::{blur, Grid};

    #[test]
    fn blur_keeps_a_flat_field_and_spreads_a_dot() {
        let flat = blur(&Grid::from_fn(9, 7, |_, _| 0.5), 2.0);
        assert!(flat.v.iter().all(|v| (v - 0.5).abs() < 1e-6));
        let mut dot = Grid::new(21, 21);
        dot.v[10 * 21 + 10] = 1.0;
        let b = blur(&dot, 2.0);
        assert!((b.v.iter().sum::<f32>() - 1.0).abs() < 1e-4 && b.at(10, 10) > b.at(12, 10));
    }
}
