//! A neon frame as a list of shapes and pictures the shader fills pixel by pixel, in the Python
//! painter's order, each drawn over (source-over) or added (CompositionMode_Plus), inside a clip.

use bytemuck::{Pod, Zeroable};

use super::raster::{Img, Pt};

pub const RECT: u32 = 0;
pub const CIRCLE: u32 = 1;
pub const POLY: u32 = 2;
pub const STROKE: u32 = 3;
pub const LINE: u32 = 4;
pub const RING: u32 = 5;
pub const IMAGE: u32 = 6;
pub const LOBBY: u32 = 7;

/// One shape as the shader reads it (std430: 112 bytes).
#[repr(C)]
#[derive(Clone, Copy, Debug, Default, Pod, Zeroable)]
pub struct Prim {
    /// shape, flags (1 smooth sampling), unused, unused.
    pub kind: [u32; 4],
    pub bbox: [f32; 4],
    pub s0: [f32; 4],
    pub s1: [f32; 4],
    pub s2: [f32; 4],
    pub clip: [f32; 4],
    /// Premultiplied color; for a picture, its opacity in alpha.
    pub color: [f32; 4],
}

/// Where each picture sits in the atlas: x, y, w, h in texels.
pub struct Atlas {
    pub w: u32,
    pub h: u32,
    pub bytes: Vec<u8>,
    pub at: Vec<[u32; 4]>,
}

impl Atlas {
    /// Shelf-packs the pictures into one texture `w` texels wide, a texel of room round each.
    pub fn pack(images: &[Img], w: u32) -> Self {
        let mut order: Vec<usize> = (0..images.len()).collect();
        order.sort_by_key(|&i| std::cmp::Reverse(images[i].h));
        let mut at = vec![[0u32; 4]; images.len()];
        let (mut x, mut y, mut shelf) = (0u32, 0u32, 0u32);
        for &i in &order {
            let (iw, ih) = (images[i].w as u32, images[i].h as u32);
            if x + iw + 2 > w {
                x = 0;
                y += shelf;
                shelf = 0;
            }
            at[i] = [x + 1, y + 1, iw, ih];
            x += iw + 2;
            shelf = shelf.max(ih + 2);
        }
        let h = (y + shelf).max(1);
        let mut bytes = vec![0u8; (w * h * 4) as usize];
        for (img, a) in images.iter().zip(&at) {
            for row in 0..img.h {
                let start = (((a[1] as usize + row) * w as usize) + a[0] as usize) * 4;
                let src = bytemuck::cast_slice(&img.px[row * img.w..(row + 1) * img.w]);
                bytes[start..start + img.w * 4].copy_from_slice(src);
            }
        }
        Self { w, h, bytes, at }
    }
}

pub struct Frame<'a> {
    pub prims: Vec<Prim>,
    pub points: Vec<[f32; 2]>,
    /// Runs of prims: (first, end, added).
    pub runs: Vec<(u32, u32, bool)>,
    /// painter.setOpacity: every alpha is multiplied by it.
    pub opacity: f64,
    pub plus: bool,
    pub clip: [f64; 4],
    atlas: &'a [[u32; 4]],
}

fn f4(a: f64, b: f64, c: f64, d: f64) -> [f32; 4] {
    [a as f32, b as f32, c as f32, d as f32]
}

/// "#rrggbb" and an alpha as a straight color.
pub fn rgba(color: &str, alpha: f64) -> [f32; 4] {
    let c = crate::draw::hex(color);
    [c[0], c[1], c[2], alpha.clamp(0.0, 1.0) as f32]
}

impl<'a> Frame<'a> {
    pub fn new(atlas: &'a [[u32; 4]]) -> Self {
        Self { prims: Vec::new(), points: Vec::new(), runs: Vec::new(), opacity: 1.0, plus: false, clip: [-1e9, -1e9, 1e9, 1e9], atlas }
    }

    fn push(&mut self, kind: u32, flags: u32, bbox: [f64; 4], s: [[f32; 4]; 3], color: [f32; 4]) {
        let a = (f64::from(color[3]) * self.opacity.clamp(0.0, 1.0)) as f32;
        if a <= 0.0 {
            return;
        }
        let c = &self.clip;
        let bbox = [bbox[0].max(c[0]) - 1.0, bbox[1].max(c[1]) - 1.0, bbox[2].min(c[2]) + 1.0, bbox[3].min(c[3]) + 1.0];
        if bbox[0] >= bbox[2] || bbox[1] >= bbox[3] {
            return;
        }
        let index = self.prims.len() as u32;
        match self.runs.last_mut() {
            Some(run) if run.2 == self.plus && run.1 == index => run.1 += 1,
            _ => self.runs.push((index, index + 1, self.plus)),
        }
        let color = if kind == IMAGE { [0.0, 0.0, 0.0, a] } else { [color[0] * a, color[1] * a, color[2] * a, a] };
        self.prims.push(Prim { kind: [kind, flags, 0, 0], bbox: f4(bbox[0], bbox[1], bbox[2], bbox[3]), s0: s[0], s1: s[1], s2: s[2], clip: f4(c[0], c[1], c[2], c[3]), color });
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

    /// The lobby under everything.
    pub fn lobby(&mut self, w: f64, h: f64) {
        self.push(LOBBY, 0, [1.0, 1.0, w - 1.0, h - 1.0], [[0.0; 4]; 3], [1.0; 4]);
    }

    pub fn circle(&mut self, x: f64, y: f64, r: f64, color: [f32; 4]) {
        self.push(CIRCLE, 0, [x - r, y - r, x + r, y + r], [f4(x, y, r, 0.0), [0.0; 4], [0.0; 4]], color);
    }

    pub fn poly(&mut self, points: &[Pt], color: [f32; 4]) {
        let (s0, bb) = self.add_points(points);
        self.push(POLY, 0, bb, [s0, [0.0; 4], [0.0; 4]], color);
    }

    /// A polyline stroked with round caps and joins, `width` across.
    pub fn stroke(&mut self, points: &[Pt], width: f64, color: [f32; 4]) {
        if points.len() < 2 {
            return;
        }
        let (mut s0, bb) = self.add_points(points);
        s0[2] = (width / 2.0) as f32;
        let h = width / 2.0;
        self.push(STROKE, 0, [bb[0] - h, bb[1] - h, bb[2] + h, bb[3] + h], [s0, [0.0; 4], [0.0; 4]], color);
    }

    /// A straight line with flat (`square` false) or square caps.
    pub fn line(&mut self, a: Pt, b: Pt, width: f64, square: bool, color: [f32; 4]) {
        let h = width / 2.0;
        let bb = [a[0].min(b[0]) - h, a[1].min(b[1]) - h, a[0].max(b[0]) + h, a[1].max(b[1]) + h];
        self.push(LINE, 0, bb, [f4(a[0], a[1], b[0], b[1]), f4(h, if square { h } else { 0.0 }, 0.0, 0.0), [0.0; 4]], color);
    }

    /// A circle's outline, or the arc of it from `start` for `span` (radians, counterclockwise on screen).
    pub fn ring(&mut self, c: Pt, r: f64, width: f64, arc: Option<(f64, f64)>, color: [f32; 4]) {
        let e = r + width / 2.0;
        let (start, span) = arc.unwrap_or((0.0, 10.0));
        self.push(RING, 0, [c[0] - e, c[1] - e, c[0] + e, c[1] + e], [f4(c[0], c[1], r, width / 2.0), f4(start, span, 0.0, 0.0), [0.0; 4]], color);
    }

    /// Picture `id` laid on the rect (x, y, w, h), turned by `angle` radians round `pivot`; its part
    /// `src` (x, y, w, h in its texels) if given.
    #[allow(clippy::too_many_arguments)]
    pub fn image(&mut self, id: usize, rect: [f64; 4], src: Option<[f64; 4]>, pivot: Pt, angle: f64, smooth: bool, alpha: f64) {
        let a = self.atlas[id];
        let src = src.unwrap_or([0.0, 0.0, f64::from(a[2]), f64::from(a[3])]);
        let (c, s) = (angle.cos(), angle.sin());
        let turn = |x: f64, y: f64| [pivot[0] + (x - pivot[0]) * c - (y - pivot[1]) * s, pivot[1] + (x - pivot[0]) * s + (y - pivot[1]) * c];
        let o = turn(rect[0], rect[1]);
        let ax = [rect[2] * c, rect[2] * s];
        let ay = [-rect[3] * s, rect[3] * c];
        let corners = [o, [o[0] + ax[0], o[1] + ax[1]], [o[0] + ay[0], o[1] + ay[1]], [o[0] + ax[0] + ay[0], o[1] + ax[1] + ay[1]]];
        let bb = corners.iter().fold([f64::MAX, f64::MAX, f64::MIN, f64::MIN], |b, p| [b[0].min(p[0]), b[1].min(p[1]), b[2].max(p[0]), b[3].max(p[1])]);
        let s = [f4(o[0], o[1], ax[0], ax[1]), f4(ay[0], ay[1], src[2], src[3]), f4(f64::from(a[0]) + src[0], f64::from(a[1]) + src[1], 0.0, 0.0)];
        self.push(IMAGE, u32::from(smooth), bb, s, [1.0, 1.0, 1.0, alpha as f32]);
    }

    /// A screen-sized wash (draw.Wash): picture `id` over the whole frame, rubbed out over the gap.
    pub fn wash(&mut self, id: usize, w: f64, h: f64, alpha: f64) {
        let n = self.prims.len();
        self.lay(id, [0.0, 0.0, w, h], true, alpha);
        if let Some(p) = self.prims.get_mut(n) {
            p.kind[1] |= 2;
        }
    }

    /// An upright picture over rect.
    pub fn lay(&mut self, id: usize, rect: [f64; 4], smooth: bool, alpha: f64) {
        self.image(id, rect, None, [0.0, 0.0], 0.0, smooth, alpha);
    }

    /// neon._lay: a round glow picture at x, y, r its radius.
    pub fn dot(&mut self, id: usize, x: f64, y: f64, r: f64, alpha: f64) {
        if alpha <= 0.01 || r <= 0.3 {
            return;
        }
        let keep = self.opacity;
        self.opacity = 1.0;
        self.lay(id, [x - r, y - r, 2.0 * r, 2.0 * r], true, alpha);
        self.opacity = keep;
    }

    /// draw.star: a four-point star, its arms thin.
    pub fn star(&mut self, x: f64, y: f64, r: f64, color: &str, alpha: f64) {
        if alpha <= 0.01 || r < 0.4 {
            return;
        }
        let k = 0.12;
        let arms = [[0.0, -r], [r * k, -r * k], [r, 0.0], [r * k, r * k], [0.0, r], [-r * k, r * k], [-r, 0.0], [-r * k, -r * k]];
        let points: Vec<Pt> = arms.iter().map(|d| [x + d[0], y + d[1]]).collect();
        self.poly(&points, rgba(color, alpha));
    }
}
