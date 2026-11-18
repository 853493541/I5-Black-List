//! What light.py and neon.py work out per pixel with numpy, on the CPU, once, as the Python scene
//! caches it: value noise, box blurs, smoothstep, and masks of shapes drawn in white (QPainter's
//! antialiased coverage: exact area for rects, edge distance for the rest, supersampled where two
//! shapes share a pixel). Pictures come out as premultiplied bytes, as picture() and glow() make them.

use super::np::Rng;

pub type Pt = [f64; 2];

/// A float32 picture, row by row, one value per pixel.
#[derive(Clone)]
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

    pub fn at(&self, x: usize, y: usize) -> f32 {
        self.v[y * self.w + x]
    }

    pub fn map(&self, f: impl Fn(f32) -> f32) -> Self {
        Self { w: self.w, h: self.h, v: self.v.iter().map(|&a| f(a)).collect() }
    }

    pub fn zip(&self, o: &Grid, f: impl Fn(f32, f32) -> f32) -> Self {
        Self { w: self.w, h: self.h, v: self.v.iter().zip(&o.v).map(|(&a, &b)| f(a, b)).collect() }
    }
}

/// Light, three channels that may run over 1.
pub type Light = Vec<[f32; 3]>;

/// A picture as premultiplied RGBA bytes.
#[derive(Clone)]
pub struct Img {
    pub w: usize,
    pub h: usize,
    pub px: Vec<[u8; 4]>,
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

pub fn smooth(e0: f32, e1: f32, x: f32) -> f32 {
    let k = ((x - e0) / (e1 - e0)).clamp(0.0, 1.0);
    k * k * (3.0 - 2.0 * k)
}

/// light.blur: three box blurs along each axis, edges held.
pub fn blur(a: &Grid, sigma: f64) -> Grid {
    let r = round_even(sigma * 0.9).max(1.0) as isize;
    let mut out = a.clone();
    let n = (2 * r + 1) as f32;
    for axis in 0..2 {
        let (len, lines) = if axis == 0 { (out.h, out.w) } else { (out.w, out.h) };
        let idx = |line: usize, i: usize| if axis == 0 { i * out.w + line } else { line * out.w + i };
        let mut buf = vec![0f32; len];
        let mut sums = vec![0f32; len + 2 * r as usize + 2];
        for _ in 0..3 {
            for line in 0..lines {
                for (i, b) in buf.iter_mut().enumerate() {
                    *b = out.v[idx(line, i)];
                }
                // cumsum over the edge-padded line: r + 1 before, r after.
                let mut acc = 0f32;
                for (j, s) in sums.iter_mut().enumerate().take(len + 2 * r as usize + 1) {
                    let src = (j as isize - r - 1).clamp(0, len as isize - 1) as usize;
                    acc += buf[src];
                    *s = acc;
                }
                for i in 0..len {
                    out.v[idx(line, i)] = (sums[i + 2 * r as usize + 1] - sums[i]) / n;
                }
            }
        }
    }
    out
}

/// light.noise: smooth value noise in 0..1, octaves each half the size of the last.
pub fn noise(w: usize, h: usize, scale: f64, octaves: u32, seed: u32) -> Grid {
    let mut rnd = Rng::new(seed);
    let mut out = Grid::new(w, h);
    let (mut total, mut amp) = (0f64, 1f32);
    for octave in 0..octaves {
        let cell = (scale / f64::from(1u32 << octave)).max(2.0);
        let (gw, gh) = ((w as f64 / cell) as usize + 3, (h as f64 / cell) as usize + 3);
        let grid: Vec<f32> = (0..gw * gh).map(|_| rnd.random_f32()).collect();
        let c = cell as f32;
        let ease = |s: f32| s * s * (3.0 - 2.0 * s);
        let fx: Vec<(usize, f32)> = (0..w).map(|x| {
            let f = x as f32 / c;
            (f as usize, ease(f - (f as usize) as f32))
        }).collect();
        for y in 0..h {
            let f = y as f32 / c;
            let (y0, sy) = (f as usize, ease(f - (f as usize) as f32));
            for (x, &(x0, sx)) in fx.iter().enumerate() {
                let across = |row: usize| grid[row * gw + x0] * (1.0 - sx) + grid[row * gw + x0 + 1] * sx;
                out.v[y * w + x] += (across(y0) * (1.0 - sy) + across(y0 + 1) * sy) * amp;
            }
        }
        total += f64::from(amp);
        amp *= 0.5;
    }
    let total = total as f32;
    out.map(|v| v / total)
}

/// neon._soft: each pixel shared with its four neighbours, wrapping round as np.roll does.
pub fn soft(a: &Grid) -> Grid {
    let (w, h) = (a.w, a.h);
    Grid::from_fn(w, h, |x, y| {
        let n = a.at(x, (y + h - 1) % h) + a.at(x, (y + 1) % h) + a.at((x + w - 1) % w, y) + a.at((x + 1) % w, y);
        (a.at(x, y) * 2.0 + n) / 6.0
    })
}

/// neon._grown: k times bigger, edges held, cut to w by h.
pub fn grown(a: &Grid, k: usize, w: usize, h: usize) -> Grid {
    Grid::from_fn(w, h, |x, y| a.at((x / k).min(a.w - 1), (y / k).min(a.h - 1)))
}

/// light.picture: straight color and alpha, 0..1, as premultiplied bytes.
pub fn picture(w: usize, h: usize, color: &Light, alpha: &[f32]) -> Img {
    let byte = |v: f32| (v * 255.0 + 0.5) as u8;
    let px = color
        .iter()
        .zip(alpha)
        .map(|(c, &a)| {
            let a = a.clamp(0.0, 1.0);
            [byte(c[0].clamp(0.0, 1.0) * a), byte(c[1].clamp(0.0, 1.0) * a), byte(c[2].clamp(0.0, 1.0) * a), byte(a)]
        })
        .collect();
    Img { w, h, px }
}

/// light.glow: light as a picture that adds it over what is under, over-bright bleeding white.
pub fn glow(w: usize, h: usize, light: &Light) -> Img {
    let mut color = Vec::with_capacity(light.len());
    let mut alpha = Vec::with_capacity(light.len());
    for l in light {
        let l = l.map(|v| v.max(0.0));
        let over = (l[0].max(l[1]).max(l[2]) - 1.0).max(0.0) * 0.6;
        let l = l.map(|v| v + over);
        let a = l[0].max(l[1]).max(l[2]).clamp(0.0, 1.0);
        color.push(l.map(|v| v.clamp(0.0, 1.0) / a.max(1e-4)));
        alpha.push(a);
    }
    picture(w, h, &color, &alpha)
}

/// A shape a mask is drawn with, in the mask's pixels.
#[derive(Clone, Debug)]
pub enum Shape {
    Rect(f64, f64, f64, f64),
    Poly(Vec<Pt>),
    /// A line, half its pen wide, and how far its ends reach past the points (0 flat, half square);
    /// `round` for round caps.
    Line { a: Pt, b: Pt, half: f64, reach: f64, round: bool },
    /// An ellipse's outline, half its pen wide.
    Ring { c: Pt, r: f64, half: f64 },
}

fn seg_dist(p: Pt, a: Pt, b: Pt) -> f64 {
    let (abx, aby) = (b[0] - a[0], b[1] - a[1]);
    let k = (((p[0] - a[0]) * abx + (p[1] - a[1]) * aby) / (abx * abx + aby * aby).max(1e-12)).clamp(0.0, 1.0);
    (p[0] - a[0] - abx * k).hypot(p[1] - a[1] - aby * k)
}

impl Shape {
    /// Signed distance from p to the edge, negative inside.
    fn sdf(&self, p: Pt) -> f64 {
        match self {
            Shape::Rect(x, y, w, h) => {
                let (cx, cy) = (x + w / 2.0, y + h / 2.0);
                let (qx, qy) = ((p[0] - cx).abs() - w / 2.0, (p[1] - cy).abs() - h / 2.0);
                qx.max(0.0).hypot(qy.max(0.0)) + qx.max(qy).min(0.0)
            }
            Shape::Poly(pts) => {
                let (mut d, mut inside) = (f64::MAX, false);
                for i in 0..pts.len() {
                    let (a, b) = (pts[i], pts[(i + 1) % pts.len()]);
                    d = d.min(seg_dist(p, a, b));
                    if (a[1] > p[1]) != (b[1] > p[1]) && p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0] {
                        inside = !inside;
                    }
                }
                if inside { -d } else { d }
            }
            Shape::Line { a, b, half, reach, round } => {
                if *round {
                    return seg_dist(p, *a, *b) - half;
                }
                let len = (b[0] - a[0]).hypot(b[1] - a[1]).max(1e-12);
                let (ux, uy) = ((b[0] - a[0]) / len, (b[1] - a[1]) / len);
                let (dx, dy) = (p[0] - (a[0] + b[0]) / 2.0, p[1] - (a[1] + b[1]) / 2.0);
                let (qx, qy) = ((dx * ux + dy * uy).abs() - len / 2.0 - reach, (-dx * uy + dy * ux).abs() - half);
                qx.max(0.0).hypot(qy.max(0.0)) + qx.max(qy).min(0.0)
            }
            Shape::Ring { c, r, half } => ((p[0] - c[0]).hypot(p[1] - c[1]) - r).abs() - half,
        }
    }

    fn bounds(&self) -> [f64; 4] {
        match self {
            Shape::Rect(x, y, w, h) => [*x, *y, x + w, y + h],
            Shape::Poly(pts) => pts.iter().fold([f64::MAX, f64::MAX, f64::MIN, f64::MIN], |b, p| [b[0].min(p[0]), b[1].min(p[1]), b[2].max(p[0]), b[3].max(p[1])]),
            Shape::Line { a, b, half, reach, .. } => {
                let e = half + reach;
                [a[0].min(b[0]) - e, a[1].min(b[1]) - e, a[0].max(b[0]) + e, a[1].max(b[1]) + e]
            }
            Shape::Ring { c, r, half } => [c[0] - r - half, c[1] - r - half, c[0] + r + half, c[1] + r + half],
        }
    }

    /// How much of the pixel at (x, y) the shape covers.
    fn cover(&self, x: usize, y: usize) -> f64 {
        let (px, py) = (x as f64, y as f64);
        if let Shape::Rect(rx, ry, w, h) = self {
            let ox = ((rx + w).min(px + 1.0) - rx.max(px)).max(0.0);
            let oy = ((ry + h).min(py + 1.0) - ry.max(py)).max(0.0);
            return ox * oy;
        }
        let d = self.sdf([px + 0.5, py + 0.5]);
        if let Shape::Line { half, .. } | Shape::Ring { half, .. } = self {
            if *half < 0.5 {
                return (1.0 - (d + half)).clamp(0.0, 1.0) * half * 2.0;
            }
        }
        (0.5 - d).clamp(0.0, 1.0)
    }
}

/// A mask, 0..1 per pixel, that shapes are painted on in white.
pub struct Mask(pub Grid);

impl Mask {
    pub fn new(w: usize, h: usize) -> Self {
        Self(Grid::new(w, h))
    }

    /// Paints the union of `shapes` (one path) in white at `alpha`, over what is there.
    pub fn fill(&mut self, shapes: &[Shape], alpha: f32) {
        let g = &mut self.0;
        let mut bb = [f64::MAX, f64::MAX, f64::MIN, f64::MIN];
        for s in shapes {
            let b = s.bounds();
            bb = [bb[0].min(b[0]), bb[1].min(b[1]), bb[2].max(b[2]), bb[3].max(b[3])];
        }
        let x0 = (bb[0] - 1.0).floor().max(0.0) as usize;
        let y0 = (bb[1] - 1.0).floor().max(0.0) as usize;
        let x1 = ((bb[2] + 2.0).ceil().max(0.0) as usize).min(g.w);
        let y1 = ((bb[3] + 2.0).ceil().max(0.0) as usize).min(g.h);
        for y in y0..y1 {
            for x in x0..x1 {
                let (mut full, mut partial, mut part) = (false, 0, 0.0);
                for s in shapes {
                    let c = s.cover(x, y);
                    if c >= 1.0 {
                        full = true;
                        break;
                    }
                    if c > 0.0 {
                        partial += 1;
                        part = c;
                    }
                }
                let c = if full {
                    1.0
                } else if partial > 1 {
                    let mut hits = 0;
                    for sy in 0..8 {
                        for sx in 0..8 {
                            let p = [x as f64 + (f64::from(sx) + 0.5) / 8.0, y as f64 + (f64::from(sy) + 0.5) / 8.0];
                            hits += usize::from(shapes.iter().any(|s| s.sdf(p) < 0.0));
                        }
                    }
                    hits as f64 / 64.0
                } else {
                    part
                };
                let c = c as f32 * alpha;
                let v = &mut g.v[y * g.w + x];
                *v += c * (1.0 - *v);
            }
        }
    }

    /// The mask as numpy has it after mask(): quantized to bytes.
    pub fn done(self) -> Grid {
        self.0.map(|v| (v * 255.0 + 0.5).floor() / 255.0)
    }
}
