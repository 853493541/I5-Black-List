//! Laying a baked picture on a frame: one image shape (kind 7 in angel.wgsl) through an affine map.

use super::atlas::Region;
use crate::prim::{Frame, Prim};

pub const NEAREST: u32 = 1;
pub const PLUS: u32 = 2;
pub const TIMED: u32 = 4;
pub const SECOND: u32 = 8;
pub const MASK: u32 = 16;
pub const BAND: u32 = 32;
pub const CLIP: u32 = 64;

/// A picture laid on: screen = m * picture pixel + t, at an opacity (clamped as Qt's setOpacity).
pub struct Lay {
    pub region: Region,
    pub m: [f64; 4],
    pub t: [f64; 2],
    pub opacity: f64,
    pub flags: u32,
}

impl Lay {
    /// The picture stretched over rect (x, y, w, h).
    pub fn rect(region: Region, r: [f64; 4], opacity: f64, flags: u32) -> Self {
        Self { region, m: [r[2] / f64::from(region[2]), 0.0, 0.0, r[3] / f64::from(region[3])], t: [r[0], r[1]], opacity, flags }
    }

    /// _lay: a square picture centred on (x, y), r its half width.
    pub fn dot(region: Region, x: f64, y: f64, r: f64, opacity: f64, flags: u32) -> Self {
        Self::rect(region, [x - r, y - r, 2.0 * r, 2.0 * r], opacity, flags)
    }

    /// Adds it to the frame; `extra` fills the shape's other fields (second picture, mask, times...).
    pub fn put(&self, f: &mut Frame, size: [f64; 2], extra: impl FnOnce(&mut Prim)) {
        let [a, b, c, d] = self.m;
        let det = a * d - b * c;
        if det.abs() < 1e-12 || self.opacity <= 0.0 {
            return;
        }
        let inv = [d / det, -b / det, -c / det, a / det];
        let off = [-(inv[0] * self.t[0] + inv[1] * self.t[1]), -(inv[2] * self.t[0] + inv[3] * self.t[1])];
        let (w, h) = (f64::from(self.region[2]), f64::from(self.region[3]));
        let (mut x0, mut y0, mut x1, mut y1) = (f64::MAX, f64::MAX, f64::MIN, f64::MIN);
        for (u, v) in [(0.0, 0.0), (w, 0.0), (0.0, h), (w, h)] {
            let (x, y) = (a * u + b * v + self.t[0], c * u + d * v + self.t[1]);
            (x0, y0, x1, y1) = (x0.min(x), y0.min(y), x1.max(x), y1.max(y));
        }
        let (x0, y0, x1, y1) = ((x0 - 1.0).max(0.0), (y0 - 1.0).max(0.0), (x1 + 1.0).min(size[0]), (y1 + 1.0).min(size[1]));
        if x1 <= x0 || y1 <= y0 {
            return;
        }
        let r = self.region;
        let mut p = Prim {
            kind: [7, 0, 0, self.flags],
            bbox: [x0 as f32, y0 as f32, x1 as f32, y1 as f32],
            s0: inv.map(|v| v as f32),
            grad: [off[0] as f32, off[1] as f32, r[2], r[3]],
            s1: [r[0], r[1], 1.0, self.opacity.clamp(0.0, 1.0) as f32],
            ..Prim::default()
        };
        extra(&mut p);
        f.prims.push(p);
    }
}
