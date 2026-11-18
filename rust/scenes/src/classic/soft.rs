//! 经典's soft pictures, worked out on the CPU once as classic.py does with numpy (love_scenes/light.py):
//! the dimmed hall with its light from above, the frame's warm glow, and 心动嘉宾 in gold with its sheen.

use crate::draw::Pt;

/// A grid of floats, height rows of width.
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

    fn at(&self, x: usize, y: usize) -> f32 {
        self.v[y * self.w + x]
    }

    pub fn map(&self, f: impl Fn(f32) -> f32) -> Self {
        Self { w: self.w, h: self.h, v: self.v.iter().map(|&a| f(a)).collect() }
    }
}

/// light.rgb: a color as 0..1 floats.
pub fn rgb(color: &str) -> [f32; 3] {
    crate::draw::hex(color)
}

/// light.smooth.
pub fn smooth(e0: f32, e1: f32, x: f32) -> f32 {
    let k = ((x - e0) / (e1 - e0)).clamp(0.0, 1.0);
    k * k * (3.0 - 2.0 * k)
}

/// light.blur: about a Gaussian, three box blurs of radius round(sigma * 0.9) along each axis, the
/// edges held.
pub fn blur(a: &Grid, sigma: f64) -> Grid {
    let r = ((sigma * 0.9).round_ties_even() as usize).max(1);
    let mut out = a.clone();
    let mut line = Vec::new();
    for vertical in [true, false] {
        let (n, lines) = if vertical { (a.h, a.w) } else { (a.w, a.h) };
        let index = |l: usize, i: usize| if vertical { i * a.w + l } else { l * a.w + i };
        for _ in 0..3 {
            for l in 0..lines {
                line.clear();
                line.extend((0..n).map(|i| f64::from(out.v[index(l, i)])));
                let get = |j: isize| line[j.clamp(0, n as isize - 1) as usize];
                let mut sum: f64 = (-(r as isize)..=r as isize).map(get).sum();
                for i in 0..n {
                    out.v[index(l, i)] = (sum / (2 * r + 1) as f64) as f32;
                    sum += get(i as isize + r as isize + 1) - get(i as isize - r as isize);
                }
            }
        }
    }
    out
}

/// numpy.gradient: (along y, along x), central inside, one-sided at the edges.
fn gradient(a: &Grid) -> (Grid, Grid) {
    let d = |lo: f32, hi: f32, span: f32| (hi - lo) / span;
    let gy = Grid::from_fn(a.w, a.h, |x, y| match y {
        _ if a.h < 2 => 0.0,
        0 => d(a.at(x, 0), a.at(x, 1), 1.0),
        y if y == a.h - 1 => d(a.at(x, y - 1), a.at(x, y), 1.0),
        y => d(a.at(x, y - 1), a.at(x, y + 1), 2.0),
    });
    let gx = Grid::from_fn(a.w, a.h, |x, y| match x {
        _ if a.w < 2 => 0.0,
        0 => d(a.at(0, y), a.at(1, y), 1.0),
        x if x == a.w - 1 => d(a.at(x - 1, y), a.at(x, y), 1.0),
        x => d(a.at(x - 1, y), a.at(x + 1, y), 2.0),
    });
    (gy, gx)
}

/// light.picture: RGBA bytes, premultiplied, from straight color per pixel and alpha.
pub fn picture(w: usize, h: usize, color: impl Fn(usize) -> [f32; 3], alpha: &Grid) -> Vec<u8> {
    let mut out = Vec::with_capacity(w * h * 4);
    for i in 0..w * h {
        let a = alpha.v[i].clamp(0.0, 1.0);
        let c = color(i);
        for ch in c {
            out.push((ch.clamp(0.0, 1.0) * a * 255.0 + 0.5) as u8);
        }
        out.push((a * 255.0 + 0.5) as u8);
    }
    out
}

/// A pen of width `width` along polylines, square ends, painted white over `mask` with coverage from
/// the distance to its edge, the way QPainter paints light.mask's strokes (the glow blurs it after).
pub fn stroke_mask(mask: &mut Grid, subs: &[Vec<Pt>], width: f64) {
    let h = width / 2.0;
    let mut cover = Grid::new(mask.w, mask.h);
    for sub in subs {
        for (i, seg) in sub.windows(2).enumerate() {
            let (a, b) = (seg[0], seg[1]);
            let (dx, dy) = (b[0] - a[0], b[1] - a[1]);
            let len = dx.hypot(dy).max(1e-9);
            let (ux, uy) = (dx / len, dy / len);
            let lo = if i == 0 { -h } else { -1e9 };
            let hi = if i + 2 == sub.len() { len + h } else { 1e9 };
            let x0 = (a[0].min(b[0]) - h - 1.0).floor().max(0.0) as usize;
            let x1 = ((a[0].max(b[0]) + h + 1.0).ceil() as usize).min(mask.w);
            let y0 = (a[1].min(b[1]) - h - 1.0).floor().max(0.0) as usize;
            let y1 = ((a[1].max(b[1]) + h + 1.0).ceil() as usize).min(mask.h);
            for y in y0..y1 {
                for x in x0..x1 {
                    let (px, py) = (x as f64 + 0.5 - a[0], y as f64 + 0.5 - a[1]);
                    let along = px * ux + py * uy;
                    let across = (px * -uy + py * ux).abs();
                    // Inside joins the segments overlap round; an outer end is cut square.
                    let ex = (lo - along).max(along - hi);
                    let sd = if i > 0 && along < 0.0 || i + 2 < sub.len() && along > len {
                        px.hypot(py).min((px - dx).hypot(py - dy)) - h
                    } else {
                        let ey = across - h;
                        ex.max(0.0).hypot(ey.max(0.0)) + ex.max(ey).min(0.0)
                    };
                    let c = (0.5 - sd).clamp(0.0, 1.0) as f32;
                    let k = y * mask.w + x;
                    cover.v[k] = cover.v[k].max(c);
                }
            }
        }
    }
    for (m, c) in mask.v.iter_mut().zip(&cover.v) {
        *m = ((*m + (1.0 - *m) * c) * 255.0).round() / 255.0;
    }
}

/// The words of the title as the text engine sets them, white on black, at twice their size in points.
pub struct TitleMask {
    pub w: usize,
    pub h: usize,
    /// 0..1 per pixel, h rows of w.
    pub words: Vec<f32>,
    /// The font's height (QFontMetricsF.height) in the mask's pixels.
    pub text_height: f64,
}

/// classic._title_art: 心动嘉宾 in gold per pixel (light at the top of each stroke, deep at its foot, a
/// bevel along its edges, a fine dark edge and a soft glow), and the words in near white for the sheen.
pub fn title_art(m: &TitleMask, u: f64, gold: [[f32; 3]; 3]) -> (Vec<u8>, Vec<u8>) {
    let [deep, champagne, light] = gold;
    let ratio = 2.0;
    let (w, h) = (m.w, m.h);
    let words = Grid { w, h, v: m.words.clone() };
    let top_y = (h as f64 - m.text_height) / 2.0 / h as f64;
    let span = (m.text_height / h as f64).max(1e-3);
    let bevel = blur(&words, (1.2 * u * ratio).max(0.8));
    let (gy, gx) = gradient(&bevel);
    let edge_blur = blur(&words, (1.4 * u * ratio).max(0.8));
    let halo = blur(&words, 9.0 * u * ratio);
    let (dark, warm) = (rgb("#2a1d08"), rgb("#ffd98f"));
    let mut alpha = Grid::new(w, h);
    let mut color = vec![[0.0f32; 3]; w * h];
    for (i, out) in color.iter_mut().enumerate() {
        let row = if h > 1 { (i / w) as f64 / (h - 1) as f64 } else { 0.0 };
        let down = ((row - top_y) / span).clamp(0.0, 1.0) as f32;
        let lit = (0.5 - (gy.v[i] * 0.8 + gx.v[i] * 0.4) * 6.0).clamp(0.0, 1.0);
        let tone = (0.75 - down * 0.65 + (lit - 0.5) * 0.9).clamp(0.0, 1.0);
        let g: [f32; 3] = std::array::from_fn(|c| {
            if tone > 0.5 {
                champagne[c] * (1.0 - (tone - 0.5) * 2.0) + light[c] * ((tone - 0.5) * 2.0)
            } else {
                deep[c] * (1.0 - tone * 2.0) + champagne[c] * (tone * 2.0)
            }
        });
        let word = words.v[i];
        let edge = (edge_blur.v[i] * 1.8).clamp(0.0, 1.0) * (1.0 - word);
        let glow = halo.v[i] * 0.55;
        let total = word + edge * 0.75 + glow * 0.6;
        alpha.v[i] = total.clamp(0.0, 1.0);
        *out = std::array::from_fn(|c| (g[c] * word + dark[c] * edge * 0.75 + warm[c] * glow * 0.6) / total.max(1e-4));
    }
    let shine = rgb("#fffaf0");
    (picture(w, h, |i| color[i], &alpha), picture(w, h, |_| shine, &words))
}
