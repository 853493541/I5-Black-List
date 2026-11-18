//! A frame of 演说家遇袭 as the shader reads it: shapes and pictures in the Python painter's order,
//! each with the painter's transform and opacity at the time, grouped into draws by the picture
//! (texture) they read.

use bytemuck::{Pod, Zeroable};

use super::geom::Affine;
use super::light::Pt;
use crate::prim::{stops, Paint};

pub const RECT: u32 = 0;
pub const ELLIPSE: u32 = 1;
pub const PATH: u32 = 2;
pub const RRECT: u32 = 3;
pub const RRECT_PEN: u32 = 4;
pub const IMAGE: u32 = 5;
/// Between contours in a PATH's points.
pub const BREAK: f32 = 1e30;

/// One shape (std430, 192 bytes): kind (shape, paint 0 solid / 1 linear / 2 radial, stop count,
/// flags); its quad on screen; the device-to-local transform (a, b, c, d) and (e, f, pixels per
/// unit, -); the shape in local units; its gradient; stops; more shape (radius, pen, or a clip).
#[repr(C)]
#[derive(Clone, Copy, Debug, Default, Pod, Zeroable)]
pub struct Prim {
    pub kind: [u32; 4],
    pub bbox: [f32; 4],
    pub inv0: [f32; 4],
    pub inv1: [f32; 4],
    pub shape: [f32; 4],
    pub grad: [f32; 4],
    pub stops: [f32; 4],
    pub more: [f32; 4],
    pub colors: [[f32; 4]; 4],
}

/// A run of prims drawn together, reading one texture (and a mask texture, for the veil).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Draw {
    pub start: u32,
    pub end: u32,
    pub texture: Option<usize>,
    pub mask: Option<usize>,
}

pub struct Frame {
    pub prims: Vec<Prim>,
    pub points: Vec<[f32; 2]>,
    pub draws: Vec<Draw>,
    pub tf: Affine,
    pub opacity: f64,
    stack: Vec<(Affine, f64)>,
}

fn f4(a: f64, b: f64, c: f64, d: f64) -> [f32; 4] {
    [a as f32, b as f32, c as f32, d as f32]
}

impl Default for Frame {
    fn default() -> Self {
        Self { prims: Vec::new(), points: Vec::new(), draws: Vec::new(), tf: Affine::default(), opacity: 1.0, stack: Vec::new() }
    }
}

impl Frame {
    pub fn save(&mut self) {
        self.stack.push((self.tf, self.opacity));
    }

    pub fn restore(&mut self) {
        if let Some((tf, opacity)) = self.stack.pop() {
            (self.tf, self.opacity) = (tf, opacity);
        }
    }

    fn premul(&self, c: [f32; 3], alpha: f64) -> [f32; 4] {
        let a = (alpha.clamp(0.0, 1.0) * self.opacity) as f32;
        [c[0] * a, c[1] * a, c[2] * a, a]
    }

    fn push(&mut self, mut p: Prim, paint: &Paint, bbox: [f64; 4], texture: Option<usize>, mask: Option<usize>) {
        let inv = self.tf.inverse();
        p.bbox = f4(bbox[0] - 1.0, bbox[1] - 1.0, bbox[2] + 1.0, bbox[3] + 1.0);
        p.inv0 = f4(inv[0], inv[1], inv[2], inv[3]);
        p.inv1 = f4(inv[4], inv[5], self.tf.px(), 0.0);
        let list = match paint {
            Paint::Solid(c, a) => {
                p.colors[0] = self.premul(*c, *a);
                p.kind[1..3].copy_from_slice(&[0, 1]);
                None
            }
            Paint::Linear(a, b, list) => {
                p.grad = f4(a[0], a[1], b[0], b[1]);
                p.kind[1..3].copy_from_slice(&[1, list.len() as u32]);
                Some(list)
            }
            Paint::Radial(c, r, list) => {
                p.grad = f4(c[0], c[1], *r, 0.0);
                p.kind[1..3].copy_from_slice(&[2, list.len() as u32]);
                Some(list)
            }
        };
        for (i, &(at, c, a)) in list.into_iter().flatten().take(4).enumerate() {
            p.stops[i] = at as f32;
            p.colors[i] = self.premul(c, a);
        }
        let index = self.prims.len() as u32;
        self.prims.push(p);
        match self.draws.last_mut() {
            Some(d) if d.texture.is_none() && texture.is_none() => d.end = index + 1,
            _ => self.draws.push(Draw { start: index, end: index + 1, texture, mask }),
        }
    }

    fn shaped(kind: u32, shape: [f32; 4], more: [f32; 4]) -> Prim {
        Prim { kind: [kind, 0, 0, 0], shape, more, ..Prim::default() }
    }

    pub fn rect(&mut self, r: [f64; 4], paint: &Paint) {
        let b = self.tf.bounds(r);
        self.push(Self::shaped(RECT, f4(r[0], r[1], r[2], r[3]), [0.0; 4]), paint, b, None, None);
    }

    pub fn ellipse(&mut self, x: f64, y: f64, r: f64, paint: &Paint) {
        let b = self.tf.bounds([x - r, y - r, 2.0 * r, 2.0 * r]);
        self.push(Self::shaped(ELLIPSE, f4(x, y, r, 0.0), [0.0; 4]), paint, b, None, None);
    }

    pub fn rrect(&mut self, r: [f64; 4], radius: f64, paint: &Paint) {
        let b = self.tf.bounds(r);
        self.push(Self::shaped(RRECT, f4(r[0], r[1], r[2], r[3]), f4(radius, 0.0, 0.0, 0.0)), paint, b, None, None);
    }

    /// A rounded rect's outline, the pen `width` across, centred on the edge.
    pub fn rrect_pen(&mut self, r: [f64; 4], radius: f64, width: f64, paint: &Paint) {
        let h = width / 2.0;
        let b = self.tf.bounds([r[0] - h, r[1] - h, r[2] + width, r[3] + width]);
        self.push(Self::shaped(RRECT_PEN, f4(r[0], r[1], r[2], r[3]), f4(radius, width, 0.0, 0.0)), paint, b, None, None);
    }

    /// Filled contours (local units), winding: each contour its own even-odd ring.
    pub fn path(&mut self, contours: &[Vec<Pt>], paint: &Paint) {
        let offset = self.points.len();
        let mut b = [f64::MAX, f64::MAX, f64::MIN, f64::MIN];
        for contour in contours {
            for &p in contour {
                let d = self.tf.map(p);
                b = [b[0].min(d[0]), b[1].min(d[1]), b[2].max(d[0]), b[3].max(d[1])];
                self.points.push([d[0] as f32, d[1] as f32]);
            }
            self.points.push([BREAK, BREAK]);
        }
        let count = self.points.len() - offset;
        if count == 0 {
            return;
        }
        // The shape's points are on screen already: its local is the screen.
        let tf = std::mem::take(&mut self.tf);
        self.push(Self::shaped(PATH, f4(offset as f64, count as f64, 0.0, 0.0), [0.0; 4]), paint, b, None, None);
        self.tf = tf;
    }

    /// draw.soft_dot: a round glow, bright core, soft edge.
    pub fn soft_dot(&mut self, x: f64, y: f64, r: f64, color: &str, alpha: f64) {
        if alpha <= 0.01 || r <= 0.2 {
            return;
        }
        self.ellipse(x, y, r, &Paint::Radial([x, y], r, stops(&[(0.0, color, alpha), (0.35, color, alpha * 0.35), (1.0, color, 0.0)])));
    }

    /// drawImage(box, picture) with smooth scaling, clipped to `clip` (local units) if given; `mask`
    /// multiplies each of its texels by another picture's alpha first (DestinationIn).
    pub fn image(&mut self, texture: usize, size: (usize, usize), r: [f64; 4], clip: Option<[f64; 4]>, mask: Option<usize>) {
        if self.opacity <= 0.0 {
            return;
        }
        let mut shown = r;
        if let Some(c) = clip {
            let (x0, y0) = (r[0].max(c[0]), r[1].max(c[1]));
            let (x1, y1) = ((r[0] + r[2]).min(c[0] + c[2]), (r[1] + r[3]).min(c[1] + c[3]));
            if x1 <= x0 || y1 <= y0 {
                return;
            }
            shown = [x0, y0, x1 - x0, y1 - y0];
        }
        let b = self.tf.bounds(shown);
        let mut p = Self::shaped(IMAGE, f4(r[0], r[1], r[2], r[3]), f4(shown[0], shown[1], shown[2], shown[3]));
        p.kind[3] = u32::from(mask.is_some());
        p.stops = f4(size.0 as f64, size.1 as f64, 0.0, 0.0);
        self.push(p, &Paint::Solid([1.0; 3], 1.0), b, Some(texture), mask);
    }
}
