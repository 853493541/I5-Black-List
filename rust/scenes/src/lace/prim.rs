//! A frame as a list of shapes the shader fills pixel by pixel, in the order the Python painter draws
//! them. Copied from crate::prim and grown for 玫瑰花边 and 经典 (the master unifies them later): strokes
//! of several subpaths painted with any paint (a gold pen is a gradient), square caps, a clip that
//! keeps a shape off the button's gap, reflected gradients, and pictures from the scene's own layers.

use bytemuck::{Pod, Zeroable};

use crate::draw::{hex, Pt};

pub const RECT: u32 = 0;
pub const CIRCLE: u32 = 1;
pub const POLY: u32 = 2;
pub const STROKE: u32 = 5;
pub const PICTURE: u32 = 6;
/// flags: the shape is clipped off a rounded rect (s2, radius s1.w), or kept inside a rect (s2).
pub const CLIP_OUT_ROUNDED: u32 = 1;
pub const CLIP_IN_RECT: u32 = 2;
/// flags: a linear gradient reflects past its ends (QGradient.ReflectSpread).
pub const REFLECT: u32 = 4;
/// Where a picture comes from: the lobby, the scene's layers drawn on the chip, its CPU-made atlas.
pub const LOBBY: u32 = 0;
pub const LAYER_A: u32 = 1;
pub const LAYER_B: u32 = 2;
pub const ATLAS: u32 = 3;
/// A point that starts a new subpath in a stroke's point list.
pub const BREAK: [f32; 2] = [-1e30, -1e30];

/// One shape as the shader reads it (std430: 176 bytes).
#[repr(C)]
#[derive(Clone, Copy, Debug, Default, Pod, Zeroable)]
pub struct Prim {
    /// shape, paint (0 solid, 1 linear, 2 radial), stop count, flags.
    pub kind: [u32; 4],
    pub bbox: [f32; 4],
    pub s0: [f32; 4],
    pub s1: [f32; 4],
    pub s2: [f32; 4],
    pub grad: [f32; 4],
    pub stops: [f32; 4],
    /// Premultiplied colors at the stops.
    pub colors: [[f32; 4]; 4],
}

/// How a shape is filled: a color with its alpha, or gradient stops (at, color, alpha).
#[derive(Clone)]
pub enum Paint {
    Solid([f32; 3], f64),
    Linear(Pt, Pt, Vec<(f64, [f32; 3], f64)>),
    Radial(Pt, f64, Vec<(f64, [f32; 3], f64)>),
}

pub fn solid(color: &str, alpha: f64) -> Paint {
    Paint::Solid(hex(color), alpha)
}

/// Gradient stops from (at, "#color", alpha).
pub fn stops(list: &[(f64, &str, f64)]) -> Vec<(f64, [f32; 3], f64)> {
    list.iter().map(|&(at, c, a)| (at, hex(c), a)).collect()
}

/// How a shape is clipped.
#[derive(Clone, Copy, Default)]
pub enum Clip {
    #[default]
    None,
    /// Everywhere but this rounded rect (x, y, w, h, radius).
    OutRounded([f64; 5]),
    /// Only inside this rect (x, y, w, h), whole pixels.
    InRect([f64; 4]),
}

#[derive(Default)]
pub struct Frame {
    pub prims: Vec<Prim>,
    pub points: Vec<[f32; 2]>,
    /// painter.setOpacity: every alpha is multiplied by it.
    pub opacity: f64,
    pub clip: Clip,
}

fn f4(a: f64, b: f64, c: f64, d: f64) -> [f32; 4] {
    [a as f32, b as f32, c as f32, d as f32]
}

impl Frame {
    pub fn new() -> Self {
        Self { opacity: 1.0, ..Self::default() }
    }

    fn premul(&self, c: [f32; 3], alpha: f64) -> [f32; 4] {
        let a = (alpha.clamp(0.0, 1.0) * self.opacity) as f32;
        [c[0] * a, c[1] * a, c[2] * a, a]
    }

    fn push(&mut self, shape: u32, paint: &Paint, bbox: [f64; 4], s: [[f32; 4]; 3], flags: u32) {
        let mut p = Prim { bbox: f4(bbox[0] - 1.0, bbox[1] - 1.0, bbox[2] + 1.0, bbox[3] + 1.0), s0: s[0], s1: s[1], s2: s[2], ..Prim::default() };
        let mut flags = flags;
        match self.clip {
            Clip::None => {}
            Clip::OutRounded(r) => {
                flags |= CLIP_OUT_ROUNDED;
                p.s2 = f4(r[0], r[1], r[2], r[3]);
                p.s1[3] = r[4] as f32;
            }
            Clip::InRect(r) => {
                flags |= CLIP_IN_RECT;
                p.s2 = f4(r[0], r[1], r[2], r[3]);
            }
        }
        let list = match paint {
            Paint::Solid(c, a) => {
                p.colors[0] = self.premul(*c, *a);
                p.kind = [shape, 0, 1, flags];
                self.prims.push(p);
                return;
            }
            Paint::Linear(a, b, list) => {
                p.grad = f4(a[0], a[1], b[0], b[1]);
                p.kind = [shape, 1, list.len() as u32, flags];
                list
            }
            Paint::Radial(c, r, list) => {
                p.grad = f4(c[0], c[1], *r, 0.0);
                p.kind = [shape, 2, list.len() as u32, flags];
                list
            }
        };
        for (i, &(at, c, a)) in list.iter().take(4).enumerate() {
            p.stops[i] = at as f32;
            p.colors[i] = self.premul(c, a);
        }
        self.prims.push(p);
    }

    fn add_points(&mut self, subs: &[Vec<Pt>]) -> ([f32; 4], [f64; 4]) {
        let offset = self.points.len();
        let mut bb = [f64::MAX, f64::MAX, f64::MIN, f64::MIN];
        for (i, sub) in subs.iter().enumerate() {
            if i > 0 {
                self.points.push(BREAK);
            }
            for p in sub {
                self.points.push([p[0] as f32, p[1] as f32]);
                bb = [bb[0].min(p[0]), bb[1].min(p[1]), bb[2].max(p[0]), bb[3].max(p[1])];
            }
        }
        (f4(offset as f64, (self.points.len() - offset) as f64, 0.0, 0.0), bb)
    }

    pub fn rect(&mut self, x: f64, y: f64, w: f64, h: f64, paint: &Paint) {
        // push widens every box by a pixel for the antialiased edge; a rect is filled exactly.
        self.push(RECT, paint, [x + 1.0, y + 1.0, x + w - 1.0, y + h - 1.0], [[0.0; 4]; 3], 0);
    }

    pub fn circle(&mut self, x: f64, y: f64, r: f64, paint: &Paint) {
        self.push(CIRCLE, paint, [x - r, y - r, x + r, y + r], [f4(x, y, r, 0.0), [0.0; 4], [0.0; 4]], 0);
    }

    /// A filled polygon, odd-even, as a QPainterPath fills.
    pub fn poly(&mut self, points: &[Pt], paint: &Paint) {
        let (s0, bb) = self.add_points(&[points.to_vec()]);
        self.push(POLY, paint, bb, [s0, [0.0; 4], [0.0; 4]], 0);
    }

    /// A pen along a path, `width` across, round joins; `square` caps reach half the width past each
    /// open end, squared off (Qt's default pen), else round caps.
    pub fn stroke_path(&mut self, path: &Path, width: f64, paint: &Paint, square: bool, flags: u32) {
        let h = width / 2.0;
        let subs: Vec<Vec<Pt>> = path
            .subs
            .iter()
            .zip(&path.closed)
            .filter(|(s, _)| s.len() > 1)
            .map(|(s, &closed)| match (closed, square) {
                // A closed one runs on over its first segment, so its start is a join like the rest.
                (true, _) => s.iter().chain(s.get(1)).copied().collect(),
                (false, true) => extend(s, h),
                (false, false) => s.clone(),
            })
            .collect();
        if subs.is_empty() {
            return;
        }
        let (mut s0, bb) = self.add_points(&subs);
        s0[2] = h as f32;
        s0[3] = if square { 1.0 } else { 0.0 };
        self.push(STROKE, paint, [bb[0] - h, bb[1] - h, bb[2] + h, bb[3] + h], [s0, [0.0; 4], [0.0; 4]], flags);
    }

    /// A round-capped pen of one color along one polyline.
    pub fn stroke(&mut self, points: &[Pt], width: f64, color: &str, alpha: f64) {
        self.stroke_path(&Path::lines(points), width, &solid(color, alpha), false, 0);
    }

    /// A whole-frame picture: the lobby or one of the scene's layers, at `alpha`.
    pub fn layer(&mut self, source: u32, size: [f64; 2], alpha: f64) {
        self.push(PICTURE, &Paint::Solid([1.0; 3], alpha), [1.0, 1.0, size[0] - 1.0, size[1] - 1.0], [f4(f64::from(source), 0.0, 0.0, 0.0), [0.0; 4], [0.0; 4]], 0);
    }

    /// Part `src` (x, y, w, h in atlas pixels) of the atlas laid on `dest`, smoothed (bilinear), at `alpha`.
    pub fn image(&mut self, dest: [f64; 4], src: [f64; 4], alpha: f64) {
        let p = Paint::Solid([1.0; 3], alpha);
        let s = [f4(f64::from(ATLAS), 0.0, 0.0, 0.0), f4(dest[0], dest[1], dest[2], dest[3]), [0.0; 4]];
        self.push(PICTURE, &p, [dest[0], dest[1], dest[0] + dest[2], dest[1] + dest[3]], s, 0);
        if let Some(last) = self.prims.last_mut() {
            last.grad = f4(src[0], src[1], src[2], src[3]);
        }
    }

    /// draw.soft_dot: a round glow, bright core, soft edge.
    pub fn soft_dot(&mut self, x: f64, y: f64, r: f64, color: &str, alpha: f64) {
        if alpha <= 0.01 || r <= 0.2 {
            return;
        }
        self.circle(x, y, r, &Paint::Radial([x, y], r, stops(&[(0.0, color, alpha), (0.35, color, alpha * 0.35), (1.0, color, 0.0)])));
    }

    /// draw.star: a four-point star, its arms `thin` of its radius.
    pub fn star(&mut self, x: f64, y: f64, r: f64, color: [f32; 3], alpha: f64, thin: f64) {
        if alpha <= 0.01 || r < 0.4 {
            return;
        }
        let k = thin;
        let arms = [[0.0, -r], [r * k, -r * k], [r, 0.0], [r * k, r * k], [0.0, r], [-r * k, r * k], [-r, 0.0], [-r * k, -r * k]];
        let points: Vec<Pt> = arms.iter().map(|d| [x + d[0], y + d[1]]).collect();
        self.poly(&points, &Paint::Solid(color, alpha));
    }
}

/// An open polyline with its ends pushed out by `h` along the line (a square cap's reach).
fn extend(s: &[Pt], h: f64) -> Vec<Pt> {
    let mut out = s.to_vec();
    let n = out.len();
    let push = |a: Pt, b: Pt| {
        let (dx, dy) = (a[0] - b[0], a[1] - b[1]);
        let len = dx.hypot(dy);
        if len < 1e-9 {
            a
        } else {
            [a[0] + dx / len * h, a[1] + dy / len * h]
        }
    };
    out[0] = push(s[0], s[1]);
    out[n - 1] = push(s[n - 1], s[n - 2]);
    out
}

/// A QPainter transform made of translations and rotations, in degrees as painter.rotate takes them.
#[derive(Clone, Copy)]
pub struct Xf {
    m: [f64; 6],
}

impl Xf {
    pub fn at(x: f64, y: f64) -> Self {
        Self { m: [1.0, 0.0, 0.0, 1.0, x, y] }
    }

    pub fn rotate(self, degrees: f64) -> Self {
        let (s, c) = degrees.to_radians().sin_cos();
        let [a, b, cc, d, e, f] = self.m;
        Self { m: [a * c + cc * s, b * c + d * s, -a * s + cc * c, -b * s + d * c, e, f] }
    }

    pub fn translate(self, x: f64, y: f64) -> Self {
        let [a, b, c, d, e, f] = self.m;
        Self { m: [a, b, c, d, e + a * x + c * y, f + b * x + d * y] }
    }

    pub fn map(&self, p: Pt) -> Pt {
        let [a, b, c, d, e, f] = self.m;
        [a * p[0] + c * p[1] + e, b * p[0] + d * p[1] + f]
    }
}

/// A QPainterPath flattened to polylines, curves cut fine enough to stay within 0.02 px.
#[derive(Default, Clone)]
pub struct Path {
    pub subs: Vec<Vec<Pt>>,
    /// Whether each subpath was closed (closeSubpath, or an ellipse).
    pub closed: Vec<bool>,
}

fn pieces(dd: f64) -> usize {
    ((dd / (8.0 * 0.02)).sqrt().ceil() as usize).clamp(1, 160)
}

impl Path {
    pub fn new(at: Pt) -> Self {
        Self { subs: vec![vec![at]], closed: vec![false] }
    }

    /// An open polyline.
    pub fn lines(points: &[Pt]) -> Self {
        Self { subs: vec![points.to_vec()], closed: vec![false] }
    }

    fn last(&self) -> Pt {
        *self.subs.last().and_then(|s| s.last()).unwrap_or(&[0.0, 0.0])
    }

    pub fn move_to(&mut self, p: Pt) {
        self.subs.push(vec![p]);
        self.closed.push(false);
    }

    pub fn line_to(&mut self, p: Pt) {
        if let Some(s) = self.subs.last_mut() {
            s.push(p);
        }
    }

    pub fn quad_to(&mut self, c: Pt, b: Pt) {
        let a = self.last();
        let n = pieces(2.0 * (a[0] - 2.0 * c[0] + b[0]).hypot(a[1] - 2.0 * c[1] + b[1]));
        for i in 1..=n {
            let s = i as f64 / n as f64;
            let m = 1.0 - s;
            self.line_to([m * m * a[0] + 2.0 * m * s * c[0] + s * s * b[0], m * m * a[1] + 2.0 * m * s * c[1] + s * s * b[1]]);
        }
    }

    pub fn cubic_to(&mut self, c1: Pt, c2: Pt, b: Pt) {
        let a = self.last();
        let d1 = (a[0] - 2.0 * c1[0] + c2[0]).hypot(a[1] - 2.0 * c1[1] + c2[1]);
        let d2 = (c1[0] - 2.0 * c2[0] + b[0]).hypot(c1[1] - 2.0 * c2[1] + b[1]);
        let n = pieces(6.0 * d1.max(d2));
        for i in 1..=n {
            let s = i as f64 / n as f64;
            let m = 1.0 - s;
            let (w0, w1, w2, w3) = (m * m * m, 3.0 * m * m * s, 3.0 * m * s * s, s * s * s);
            self.line_to([w0 * a[0] + w1 * c1[0] + w2 * c2[0] + w3 * b[0], w0 * a[1] + w1 * c1[1] + w2 * c2[1] + w3 * b[1]]);
        }
    }

    /// Closes the last subpath back to its start.
    pub fn close(&mut self) {
        if let Some(s) = self.subs.last_mut() {
            if s.len() > 1 && s[0] != s[s.len() - 1] {
                s.push(s[0]);
            }
        }
        if let Some(c) = self.closed.last_mut() {
            *c = true;
        }
    }

    /// The path through a transform.
    pub fn mapped(&self, xf: &Xf) -> Path {
        Path { subs: self.subs.iter().map(|s| s.iter().map(|&p| xf.map(p)).collect()).collect(), closed: self.closed.clone() }
    }
}
