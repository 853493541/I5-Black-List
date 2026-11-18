//! A frame as a list of shapes the shader fills pixel by pixel, in the order the Python painter
//! draws them: each a shape (rect, circle, polygon, crescent, stroke, picture) and a paint (solid,
//! linear or radial gradient, up to 4 stops, interpolated premultiplied as Qt does).

use bytemuck::{Pod, Zeroable};

use crate::draw::{hex, Pt};

pub const RECT: u32 = 0;
pub const CIRCLE: u32 = 1;
pub const POLY: u32 = 2;
pub const CRESCENT: u32 = 3;
pub const CRATER: u32 = 4;
pub const STROKE: u32 = 5;
pub const PICTURE: u32 = 6;

/// One shape as the shader reads it (std430: 176 bytes).
#[repr(C)]
#[derive(Clone, Copy, Debug, Default, Pod, Zeroable)]
pub struct Prim {
    /// shape, paint (0 solid, 1 linear, 2 radial), stop count, unused.
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

#[derive(Default)]
pub struct Frame {
    pub prims: Vec<Prim>,
    pub points: Vec<[f32; 2]>,
    /// painter.setOpacity: every alpha is multiplied by it.
    pub opacity: f64,
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

    fn push(&mut self, shape: u32, paint: &Paint, bbox: [f64; 4], s: [[f32; 4]; 3]) {
        let mut p = Prim { bbox: f4(bbox[0] - 1.0, bbox[1] - 1.0, bbox[2] + 1.0, bbox[3] + 1.0), s0: s[0], s1: s[1], s2: s[2], ..Prim::default() };
        let list = match paint {
            Paint::Solid(c, a) => {
                p.colors[0] = self.premul(*c, *a);
                p.kind = [shape, 0, 1, 0];
                self.prims.push(p);
                return;
            }
            Paint::Linear(a, b, list) => {
                p.grad = f4(a[0], a[1], b[0], b[1]);
                p.kind = [shape, 1, list.len() as u32, 0];
                list
            }
            Paint::Radial(c, r, list) => {
                p.grad = f4(c[0], c[1], *r, 0.0);
                p.kind = [shape, 2, list.len() as u32, 0];
                list
            }
        };
        for (i, &(at, c, a)) in list.iter().take(4).enumerate() {
            p.stops[i] = at as f32;
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
        // push widens every box by a pixel for the antialiased edge; a rect is filled exactly.
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
    pub fn stroke(&mut self, points: &[Pt], width: f64, color: &str, alpha: f64) {
        let (mut s0, bb) = self.add_points(points);
        s0[2] = (width / 2.0) as f32;
        let h = width / 2.0;
        self.push(STROKE, &solid(color, alpha), [bb[0] - h, bb[1] - h, bb[2] + h, bb[3] + h], [s0, [0.0; 4], [0.0; 4]]);
    }

    /// A disc with a disc bitten out of it.
    pub fn crescent(&mut self, disc: [f64; 3], bite: [f64; 3], paint: &Paint) {
        let [x, y, r] = disc;
        self.push(CRESCENT, paint, [x - r, y - r, x + r, y + r], [f4(x, y, r, 0.0), f4(bite[0], bite[1], bite[2], 0.0), [0.0; 4]]);
    }

    /// A circle clipped to a crescent.
    pub fn crater(&mut self, circle: [f64; 3], disc: [f64; 3], bite: [f64; 3], paint: &Paint) {
        let [x, y, r] = circle;
        let s = [f4(x, y, r, 0.0), f4(disc[0], disc[1], disc[2], 0.0), f4(bite[0], bite[1], bite[2], 0.0)];
        self.push(CRATER, paint, [x - r, y - r, x + r, y + r], s);
    }

    /// A whole-frame picture: layer 0 the lobby, 1 the Milky Way with its hole over `gap` (x, y, w, h).
    pub fn picture(&mut self, layer: u32, size: [f64; 2], gap: [f64; 4], alpha: f64) {
        let gap = f4(gap[0], gap[1], gap[2], gap[3]);
        self.push(PICTURE, &Paint::Solid([1.0; 3], alpha), [1.0, 1.0, size[0] - 1.0, size[1] - 1.0], [f4(f64::from(layer), 0.0, 0.0, 0.0), gap, [0.0; 4]]);
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
