//! A frame as a list of shapes the shader fills pixel by pixel, in the order the Python painter
//! draws them (copied from the spike's prim.rs, the master unifies them later): each a shape (rect,
//! circle, polygon, stroke, ring, picture from the atlas) and a paint (solid, linear or radial
//! gradient, up to 4 stops, interpolated premultiplied as Qt does).

use bytemuck::{Pod, Zeroable};

use crate::draw::{hex, Pt};

use super::atlas::Tile;

pub const RECT: u32 = 0;
pub const CIRCLE: u32 = 1;
pub const POLY: u32 = 2;
pub const CRESCENT: u32 = 3;
pub const CRATER: u32 = 4;
pub const STROKE: u32 = 5;
pub const PICTURE: u32 = 6;
pub const IMAGE: u32 = 7;
pub const RING: u32 = 8;

/// Flags in kind.w: an atlas picture used as a coverage mask for the paint, the paper's oval
/// hole rubbed out of the shape, the shape clipped to the polygon at grad.xy (offset, count).
pub const MASK: u32 = 1;
pub const HOLE: u32 = 2;
pub const CLIP: u32 = 4;

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
    /// Flags (HOLE) given to every shape pushed while set.
    pub flags: u32,
}

/// Where a picture goes: its rect, the pixel clip (x0, y0, x1, y1) and a polygon to clip it to.
pub struct Place<'a> {
    pub rect: [f64; 4],
    pub clip: [f64; 4],
    pub poly: Option<&'a [Pt]>,
}

impl Place<'_> {
    pub fn at(rect: [f64; 4]) -> Self {
        Place { rect, clip: [-1e6, -1e6, 1e6, 1e6], poly: None }
    }
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
        let flags = self.flags;
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

    /// A whole-frame picture: layer 0 the lobby, 1 the paper with its hole over `gap` (x, y, w, h).
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


    /// A straight line, `width` across (QPainter.drawLine).
    pub fn line(&mut self, a: Pt, b: Pt, width: f64, color: &str, alpha: f64) {
        self.stroke(&[a, b], width, color, alpha);
    }

    /// A Qt.DashLine: dashes 4 pen widths long and gaps 2, each dash capped half a width.
    pub fn dashed(&mut self, a: Pt, b: Pt, width: f64, color: &str, alpha: f64) {
        let len = (b[0] - a[0]).hypot(b[1] - a[1]);
        if len <= 0.0 {
            return;
        }
        let dir = [(b[0] - a[0]) / len, (b[1] - a[1]) / len];
        let at = |d: f64| [a[0] + dir[0] * d, a[1] + dir[1] * d];
        let mut d = 0.0;
        while d < len {
            self.line(at(d), at((d + 4.0 * width).min(len)), width, color, alpha);
            d += 6.0 * width;
        }
    }

    /// A circle's outline, `width` across.
    pub fn ring(&mut self, c: Pt, r: f64, width: f64, color: &str, alpha: f64) {
        let o = r + width;
        self.push(RING, &solid(color, alpha), [c[0] - o, c[1] - o, c[0] + o, c[1] + o], [f4(c[0], c[1], r, width / 2.0), [0.0; 4], [0.0; 4]]);
    }

    /// An atlas picture laid on (drawImage, smoothed), at `alpha`.
    pub fn image(&mut self, tile: Tile, at: Place, alpha: f64) {
        self.tile(tile, at, &Paint::Solid([1.0; 3], alpha), 0);
    }

    /// An atlas coverage mask filled with `color`: letters set once, laid on every frame.
    pub fn mask(&mut self, tile: Tile, at: Place, color: &str, alpha: f64) {
        self.tile(tile, at, &solid(color, alpha), MASK);
    }

    fn tile(&mut self, tile: Tile, at: Place, paint: &Paint, mode: u32) {
        let r = at.rect;
        let c = at.clip;
        let bbox = [r[0].max(c[0]) + 1.0, r[1].max(c[1]) + 1.0, (r[0] + r[2]).min(c[2]) - 1.0, (r[1] + r[3]).min(c[3]) - 1.0];
        if bbox[2] <= bbox[0] - 2.0 || bbox[3] <= bbox[1] - 2.0 {
            return;
        }
        let mut grad = [0.0; 4];
        let mut flags = mode;
        if let Some(poly) = at.poly {
            let (s, _) = self.add_points(poly);
            grad = [s[0], s[1], 0.0, 0.0];
            flags |= CLIP;
        }
        let s = [f4(r[0], r[1], r[2], r[3]), f4(tile.x, tile.y, tile.w, tile.h), f4(c[0], c[1], c[2], c[3])];
        self.push(IMAGE, paint, bbox, s);
        let last = self.prims.last_mut().expect("just pushed");
        last.kind[3] |= flags;
        last.grad = grad;
    }
}
