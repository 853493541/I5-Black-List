//! The shapes of a 冰蓝极光 frame, as the shader reads them: copied from crate::prim and widened for
//! this scene (up to 8 gradient stops, a clip to the heart, additive blending, segment lists, and
//! pictures sampled smoothly from the aurora, the glass and the light inside the heart).

use bytemuck::{Pod, Zeroable};

use crate::draw::{hex, Pt};

pub const RECT: u32 = 0;
pub const CIRCLE: u32 = 1;
pub const POLY: u32 = 2;
pub const STROKE: u32 = 5;
pub const PICTURE: u32 = 6;
/// Separate line segments (point pairs) stroked as one path: where they cross, light is not doubled.
pub const SEGS: u32 = 7;

/// Picture layers.
pub const LOBBY: u32 = 0;
pub const WASH: u32 = 1;
pub const AURORA: u32 = 2;
pub const GLASS: u32 = 3;
pub const WITHIN: u32 = 4;

/// kind.w flags: clipped to the heart outline, added (Qt's CompositionMode_Plus) instead of laid over.
pub const CLIPPED: u32 = 1;
pub const ADD: u32 = 2;

/// One shape (std430: 272 bytes).
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
    pub stops: [[f32; 4]; 2],
    /// The clip outline: offset and count in the points.
    pub clip: [f32; 4],
    /// Premultiplied colors at the stops.
    pub colors: [[f32; 4]; 8],
}

/// Gradient stops: (at, color, alpha).
pub type Stops = Vec<(f64, [f32; 3], f64)>;

pub enum Paint {
    Solid([f32; 3], f64),
    Linear(Pt, Pt, Stops),
    Radial(Pt, f64, Stops),
}

pub fn solid(color: &str, alpha: f64) -> Paint {
    Paint::Solid(hex(color), alpha)
}

pub fn stops(list: &[(f64, &str, f64)]) -> Stops {
    list.iter().map(|&(at, c, a)| (at, hex(c), a)).collect()
}

fn f4(a: f64, b: f64, c: f64, d: f64) -> [f32; 4] {
    [a as f32, b as f32, c as f32, d as f32]
}

#[derive(Default)]
pub struct Frame {
    pub prims: Vec<Prim>,
    pub points: Vec<[f32; 2]>,
    /// painter.setOpacity.
    pub opacity: f64,
    /// Flags for the shapes pushed now (CLIPPED, ADD).
    pub flags: u32,
    clip: [f32; 4],
}

impl Frame {
    pub fn new() -> Self {
        Self { opacity: 1.0, ..Self::default() }
    }

    /// Clips what is pushed from now on to this outline (the heart), until `unclip`.
    pub fn clip_to(&mut self, outline: &[Pt]) {
        let (s, _) = self.add_points(outline);
        self.clip = s;
        self.flags |= CLIPPED;
    }

    pub fn unclip(&mut self) {
        self.flags &= !CLIPPED;
    }

    fn premul(&self, c: [f32; 3], alpha: f64) -> [f32; 4] {
        let a = (alpha.clamp(0.0, 1.0) * self.opacity) as f32;
        [c[0] * a, c[1] * a, c[2] * a, a]
    }

    fn push(&mut self, shape: u32, paint: &Paint, bbox: [f64; 4], s: [[f32; 4]; 3]) {
        let bbox = f4(bbox[0] - 1.0, bbox[1] - 1.0, bbox[2] + 1.0, bbox[3] + 1.0);
        let mut p = Prim { bbox, s0: s[0], s1: s[1], s2: s[2], clip: self.clip, ..Prim::default() };
        let (kind, list) = match paint {
            Paint::Solid(c, a) => {
                p.colors[0] = self.premul(*c, *a);
                p.kind = [shape, 0, 1, self.flags];
                self.prims.push(p);
                return;
            }
            Paint::Linear(a, b, list) => {
                p.grad = f4(a[0], a[1], b[0], b[1]);
                (1, list)
            }
            Paint::Radial(c, r, list) => {
                p.grad = f4(c[0], c[1], *r, 0.0);
                (2, list)
            }
        };
        let n = list.len().min(8);
        p.kind = [shape, kind, n as u32, self.flags];
        for (i, &(at, c, a)) in list.iter().take(n).enumerate() {
            p.stops[i / 4][i % 4] = at as f32;
            p.colors[i] = self.premul(c, a);
        }
        self.prims.push(p);
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
        self.push(RECT, paint, [x + 1.0, y + 1.0, x + w - 1.0, y + h - 1.0], [[0.0; 4]; 3]);
    }

    pub fn circle(&mut self, x: f64, y: f64, r: f64, paint: &Paint) {
        self.push(CIRCLE, paint, [x - r, y - r, x + r, y + r], [f4(x, y, r, 0.0), [0.0; 4], [0.0; 4]]);
    }

    pub fn poly(&mut self, points: &[Pt], paint: &Paint) {
        let (s0, bb) = self.add_points(points);
        self.push(POLY, paint, bb, [s0, [0.0; 4], [0.0; 4]]);
    }

    /// A stroked polyline with round caps and joins, `width` across.
    pub fn stroke(&mut self, points: &[Pt], width: f64, paint: &Paint) {
        self.lines(STROKE, points, width, paint);
    }

    /// Point pairs, each a line with round caps, stroked as one path.
    pub fn segments(&mut self, pairs: &[Pt], width: f64, paint: &Paint) {
        self.lines(SEGS, pairs, width, paint);
    }

    fn lines(&mut self, shape: u32, points: &[Pt], width: f64, paint: &Paint) {
        if points.len() < 2 {
            return;
        }
        let (mut s0, bb) = self.add_points(points);
        s0[2] = (width / 2.0) as f32;
        let h = width / 2.0;
        self.push(shape, paint, [bb[0] - h, bb[1] - h, bb[2] + h, bb[3] + h], [s0, [0.0; 4], [0.0; 4]]);
    }

    /// The lobby (whole frame) or the wash with its hole over `gap` (x, y, w, h).
    pub fn backdrop(&mut self, layer: u32, size: [f64; 2], gap: [f64; 4], alpha: f64) {
        let gap = f4(gap[0], gap[1], gap[2], gap[3]);
        let s = [f4(f64::from(layer), 0.0, 0.0, 0.0), gap, [0.0; 4]];
        self.push(PICTURE, &Paint::Solid([1.0; 3], alpha), [1.0, 1.0, size[0] - 1.0, size[1] - 1.0], s);
    }

    /// A picture of `pixels` (w, h) laid smoothly into `rect` (x, y, w, h) at `alpha`.
    pub fn image(&mut self, layer: u32, rect: [f64; 4], pixels: [f64; 2], alpha: f64) {
        let s = [f4(f64::from(layer), 0.0, 0.0, 0.0), f4(rect[0], rect[1], rect[2], rect[3]), f4(pixels[0], pixels[1], 0.0, 0.0)];
        let bbox = [rect[0] + 1.0, rect[1] + 1.0, rect[0] + rect[2] - 1.0, rect[1] + rect[3] - 1.0];
        self.push(PICTURE, &Paint::Solid([1.0; 3], alpha), bbox, s);
    }

    /// draw.soft_dot.
    pub fn soft_dot(&mut self, x: f64, y: f64, r: f64, color: [f32; 3], alpha: f64) {
        if alpha <= 0.01 || r <= 0.2 {
            return;
        }
        let list = vec![(0.0, color, alpha), (0.35, color, alpha * 0.35), (1.0, color, 0.0)];
        self.circle(x, y, r, &Paint::Radial([x, y], r, list));
    }

    /// draw.star: a four-point star, arms 0.12 of its radius.
    pub fn star(&mut self, x: f64, y: f64, r: f64, color: [f32; 3], alpha: f64) {
        if alpha <= 0.01 || r < 0.4 {
            return;
        }
        let k = 0.12;
        let arms = [[0.0, -r], [r * k, -r * k], [r, 0.0], [r * k, r * k], [0.0, r], [-r * k, r * k], [-r, 0.0], [-r * k, -r * k]];
        let points: Vec<Pt> = arms.iter().map(|d| [x + d[0], y + d[1]]).collect();
        self.poly(&points, &Paint::Solid(color, alpha));
    }
}
