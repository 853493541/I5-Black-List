//! What a cyber frame is: shapes in the Python painter's order, each with its clip, its blend and
//! the layer it is drawn into, built on the CPU for gfx to shade.

use bytemuck::{Pod, Zeroable};

use crate::draw::{hex, Pt};

pub const RECT: u32 = 0;
pub const CIRCLE: u32 = 1;
pub const POLY: u32 = 2;
pub const STROKE: u32 = 3;
pub const PICTURE: u32 = 4;
pub const RING: u32 = 5;

/// The lobby, the atlas of pictures, the night's wash, the two panels' layers.
pub const LOBBY: u32 = 0;
pub const ATLAS: u32 = 1;
pub const WASH: u32 = 2;
pub const LAYER: [u32; 2] = [3, 4];
/// Render targets: the screen, then the textures above that can be drawn into.
pub const SCREEN: u32 = 0;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Blend {
    Over,
    Plus,
    Atop,
    Out,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default, Pod, Zeroable)]
pub struct Prim {
    /// shape, paint (0 solid, 1 linear, 2 radial, 3 tinted picture), stops, texture
    pub kind: [u32; 4],
    pub bbox: [f32; 4],
    pub s0: [f32; 4],
    pub s1: [f32; 4],
    pub grad: [f32; 4],
    pub stops: [f32; 4],
    pub colors: [[f32; 4]; 4],
    pub clip: [f32; 4],
    pub xf: [f32; 4],
    pub xf2: [f32; 4],
}

pub struct Run {
    pub target: u32,
    pub clear: bool,
    pub blend: Blend,
    pub start: u32,
    pub end: u32,
}

/// Where a picture sits in a texture, in texels: x, y, w, h.
pub type Src = [f64; 4];

pub struct Canvas {
    pub prims: Vec<Prim>,
    pub points: Vec<[f32; 2]>,
    pub runs: Vec<Run>,
    pub opacity: f64,
    pub clip: [f64; 4],
    blend: Blend,
    target: u32,
    clear: bool,
}

const NO_CLIP: [f64; 4] = [-1e6, -1e6, 1e6, 1e6];

fn f4(a: f64, b: f64, c: f64, d: f64) -> [f32; 4] {
    [a as f32, b as f32, c as f32, d as f32]
}

/// A paint: one color, or a linear gradient of up to four stops (from, to, (at, color, alpha)).
pub enum Paint {
    Solid([f32; 3], f64),
    Linear(Pt, Pt, Vec<(f64, [f32; 3], f64)>),
}

pub fn col(color: &str, alpha: f64) -> Paint {
    Paint::Solid(hex(color), alpha)
}

impl Default for Canvas {
    fn default() -> Self {
        Self::new()
    }
}

impl Canvas {
    pub fn new() -> Self {
        Self { prims: Vec::new(), points: Vec::new(), runs: Vec::new(), opacity: 1.0, clip: NO_CLIP, blend: Blend::Over, target: SCREEN, clear: true }
    }

    /// Draw from here into target, cleared first if clear.
    pub fn draw_into(&mut self, target: u32, clear: bool) {
        self.target = target;
        self.clear = clear;
        self.blend = Blend::Over;
        self.clip = NO_CLIP;
    }

    pub fn blend(&mut self, blend: Blend) {
        self.blend = blend;
    }

    pub fn clip_to(&mut self, r: [f64; 4]) {
        let c = self.clip;
        self.clip = [c[0].max(r[0]), c[1].max(r[1]), c[2].min(r[0] + r[2]), c[3].min(r[1] + r[3])];
    }

    pub fn unclip(&mut self) {
        self.clip = NO_CLIP;
    }

    /// The state to come back to, as QPainter.save keeps it.
    pub fn save(&self) -> (f64, [f64; 4], Blend) {
        (self.opacity, self.clip, self.blend)
    }

    pub fn restore(&mut self, s: (f64, [f64; 4], Blend)) {
        (self.opacity, self.clip, self.blend) = s;
    }

    fn premul(&self, c: [f32; 3], alpha: f64) -> [f32; 4] {
        let a = (alpha.clamp(0.0, 1.0) * self.opacity) as f32;
        [c[0] * a, c[1] * a, c[2] * a, a]
    }

    fn push(&mut self, mut p: Prim, bbox: [f64; 4]) {
        let c = self.clip;
        let b = [bbox[0].max(c[0]) - 1.0, bbox[1].max(c[1]) - 1.0, bbox[2].min(c[2]) + 1.0, bbox[3].min(c[3]) + 1.0];
        if b[2] <= b[0] || b[3] <= b[1] {
            return;
        }
        p.bbox = f4(b[0], b[1], b[2], b[3]);
        p.clip = f4(c[0], c[1], c[2], c[3]);
        let n = self.prims.len() as u32;
        let same = self.runs.last().is_some_and(|r| r.target == self.target && r.blend == self.blend && r.end == n) && !self.clear;
        if same {
            if let Some(r) = self.runs.last_mut() {
                r.end += 1;
            }
        } else {
            self.runs.push(Run { target: self.target, clear: self.clear, blend: self.blend, start: n, end: n + 1 });
            self.clear = false;
        }
        self.prims.push(p);
    }

    fn shape(&mut self, shape: u32, paint: &Paint, bbox: [f64; 4], s0: [f32; 4], s1: [f32; 4]) {
        let mut p = Prim { s0, s1, ..Prim::default() };
        match paint {
            Paint::Solid(c, a) => {
                if *a * self.opacity <= 0.0 {
                    return;
                }
                p.colors[0] = self.premul(*c, *a);
                p.kind = [shape, 0, 1, 0];
            }
            Paint::Linear(a, b, list) => {
                p.grad = f4(a[0], a[1], b[0], b[1]);
                p.kind = [shape, 1, list.len().min(4) as u32, 0];
                for (i, &(at, c, al)) in list.iter().take(4).enumerate() {
                    p.stops[i] = at as f32;
                    p.colors[i] = self.premul(c, al);
                }
            }
        }
        self.push(p, bbox);
    }

    fn add_points(&mut self, points: &[Pt]) -> ([f32; 4], [f64; 4]) {
        let offset = self.points.len();
        let mut bb = [f64::MAX, f64::MAX, f64::MIN, f64::MIN];
        for p in points {
            self.points.push([p[0] as f32, p[1] as f32]);
            bb = [bb[0].min(p[0]), bb[1].min(p[1]), bb[2].max(p[0]), bb[3].max(p[1])];
        }
        (f4(offset as f64, points.len() as f64, 0.0, 0.0), bb)
    }

    pub fn rect(&mut self, x: f64, y: f64, w: f64, h: f64, paint: &Paint) {
        self.shape(RECT, paint, [x + 1.0, y + 1.0, x + w - 1.0, y + h - 1.0], f4(x, y, x + w, y + h), [0.0; 4]);
    }

    pub fn circle(&mut self, x: f64, y: f64, r: f64, paint: &Paint) {
        self.ellipse(x, y, r, r, paint);
    }

    pub fn ellipse(&mut self, x: f64, y: f64, rx: f64, ry: f64, paint: &Paint) {
        self.shape(CIRCLE, paint, [x - rx, y - ry, x + rx, y + ry], f4(x, y, rx, ry), [0.0; 4]);
    }

    /// An ellipse's outline, width wide.
    pub fn ring(&mut self, x: f64, y: f64, rx: f64, ry: f64, width: f64, paint: &Paint) {
        let h = width / 2.0;
        self.shape(RING, paint, [x - rx - h, y - ry - h, x + rx + h, y + ry + h], f4(x, y, rx, ry), f4(h, 0.0, 0.0, 0.0));
    }

    pub fn poly(&mut self, points: &[Pt], paint: &Paint) {
        if points.len() < 3 {
            return;
        }
        let (s0, bb) = self.add_points(points);
        self.shape(POLY, paint, bb, s0, [0.0; 4]);
    }

    /// A polyline stroked width wide, its ends round, or flat if not round.
    pub fn stroke(&mut self, points: &[Pt], width: f64, paint: &Paint, round: bool) {
        if points.len() < 2 || width <= 0.0 {
            return;
        }
        let (mut s0, bb) = self.add_points(points);
        s0[2] = (width / 2.0) as f32;
        s0[3] = if round { 0.0 } else { 1.0 };
        let h = width / 2.0 + 1.0;
        self.shape(STROKE, paint, [bb[0] - h, bb[1] - h, bb[2] + h, bb[3] + h], s0, [0.0; 4]);
    }

    pub fn line(&mut self, a: Pt, b: Pt, width: f64, paint: &Paint, round: bool) {
        self.stroke(&[a, b], width, paint, round);
    }

    /// A picture (src in texture tex) laid on dest (x, y, w, h), then turned by m (a, b, c, d, e, f:
    /// x' = a x + c y + e, y' = b x + d y + f, as QTransform). tint: laid on as that color only.
    pub fn picture(&mut self, tex: u32, src: Src, dest: [f64; 4], m: [f64; 6], alpha: f64, tint: Option<[f32; 3]>) {
        if alpha * self.opacity <= 0.002 || dest[2] <= 0.0 || dest[3] <= 0.0 {
            return;
        }
        let [a, b, c, d, e, f] = m;
        let det = a * d - b * c;
        if det.abs() < 1e-9 {
            return;
        }
        // The inverse: from the screen back to the picture's own space.
        let (ia, ib, ic, id) = (d / det, -b / det, -c / det, a / det);
        let (ie, i_f) = (-(ia * e + ic * f), -(ib * e + id * f));
        let corners = [[dest[0], dest[1]], [dest[0] + dest[2], dest[1]], [dest[0], dest[1] + dest[3]], [dest[0] + dest[2], dest[1] + dest[3]]];
        let mut bb = [f64::MAX, f64::MAX, f64::MIN, f64::MIN];
        for [x, y] in corners {
            let (px, py) = (a * x + c * y + e, b * x + d * y + f);
            bb = [bb[0].min(px), bb[1].min(py), bb[2].max(px), bb[3].max(py)];
        }
        let o = (alpha.clamp(0.0, 1.0) * self.opacity) as f32;
        let mut p = Prim { kind: [PICTURE, 0, 0, tex], ..Prim::default() };
        p.s0 = f4(dest[0], dest[1], dest[0] + dest[2], dest[1] + dest[3]);
        p.s1 = f4(src[0], src[1], src[2], src[3]);
        p.xf = f4(ia, ib, ic, id);
        p.xf2 = f4(ie, i_f, det.abs().sqrt(), 0.0);
        p.colors[0] = [o, o, o, o];
        if let Some(t) = tint {
            p.kind[1] = 3;
            p.colors[0] = [t[0] * o, t[1] * o, t[2] * o, o];
        }
        self.push(p, bb);
    }

    /// A picture laid on dest as it is.
    pub fn lay(&mut self, tex: u32, src: Src, dest: [f64; 4], alpha: f64) {
        self.picture(tex, src, dest, [1.0, 0.0, 0.0, 1.0, 0.0, 0.0], alpha, None);
    }

    /// draw.star: a four-point star, its arms thin.
    pub fn star(&mut self, x: f64, y: f64, r: f64, color: &str, alpha: f64) {
        if alpha <= 0.01 || r < 0.4 {
            return;
        }
        let k = 0.12;
        let arms = [[0.0, -r], [r * k, -r * k], [r, 0.0], [r * k, r * k], [0.0, r], [-r * k, r * k], [-r, 0.0], [-r * k, -r * k]];
        let points: Vec<Pt> = arms.iter().map(|d| [x + d[0], y + d[1]]).collect();
        self.poly(&points, &col(color, alpha));
    }
}
