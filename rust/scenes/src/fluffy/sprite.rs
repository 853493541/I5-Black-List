//! Pictures laid on the frame as QPainter lays them: an affine transform (translate, rotate, scale
//! as the painter's are combined), bilinear sampling where the picture is turned or sized (Qt's
//! SmoothPixmapTransform), whole pixels where it is only moved, and clip rects. All the scene's
//! pictures share one atlas, uploaded once.

use super::pixels::Canvas;
use crate::prim::{Frame, Prim};

pub const LAYER: u32 = 6;
pub const SPRITE: u32 = 7;

/// x' = a x + b y + c, y' = d x + e y + f.
#[derive(Clone, Copy, Debug)]
pub struct Affine(pub [f64; 6]);

impl Affine {
    pub const ID: Self = Self([1.0, 0.0, 0.0, 0.0, 1.0, 0.0]);

    /// self then op, as painter.translate / rotate / scale stack: op is applied to points first.
    pub fn then(self, op: Self) -> Self {
        let [a, b, c, d, e, f] = self.0;
        let [p, q, r, s, t, u] = op.0;
        Self([a * p + b * s, a * q + b * t, a * r + b * u + c, d * p + e * s, d * q + e * t, d * r + e * u + f])
    }

    pub fn translate(self, x: f64, y: f64) -> Self {
        self.then(Self([1.0, 0.0, x, 0.0, 1.0, y]))
    }

    /// QTransform.rotate: degrees, clockwise on a screen; 0 leaves it as it is.
    pub fn rotate(self, degrees: f64) -> Self {
        if degrees == 0.0 {
            return self;
        }
        let (s, c) = degrees.to_radians().sin_cos();
        self.then(Self([c, -s, 0.0, s, c, 0.0]))
    }

    pub fn scale(self, sx: f64, sy: f64) -> Self {
        self.then(Self([sx, 0.0, 0.0, 0.0, sy, 0.0]))
    }

    pub fn map(self, p: [f64; 2]) -> [f64; 2] {
        let [a, b, c, d, e, f] = self.0;
        [a * p[0] + b * p[1] + c, d * p[0] + e * p[1] + f]
    }

    pub fn inverse(self) -> Self {
        let [a, b, c, d, e, f] = self.0;
        let det = a * e - b * d;
        let (ia, ib, id, ie) = (e / det, -b / det, -d / det, a / det);
        Self([ia, ib, -(ia * c + ib * f), id, ie, -(id * c + ie * f)])
    }

    fn turned(self) -> bool {
        self.0[1] != 0.0 || self.0[3] != 0.0
    }

    fn moved_only(self) -> bool {
        !self.turned() && self.0[0] == 1.0 && self.0[4] == 1.0
    }
}

/// Every picture side by side in rows, premultiplied bytes.
pub struct Atlas {
    pub canvas: Canvas,
    pub places: Vec<[usize; 4]>,
    pics: Vec<Canvas>,
}

impl Atlas {
    pub fn new(pics: Vec<Canvas>) -> Self {
        let width = 2048;
        let (mut x, mut y, mut row) = (0, 0, 0);
        let mut places = Vec::new();
        for p in &pics {
            if x + p.w + 1 > width {
                (x, y, row) = (0, y + row + 1, 0);
            }
            places.push([x, y, p.w, p.h]);
            x += p.w + 1;
            row = row.max(p.h);
        }
        let mut canvas = Canvas::new(width, y + row + 1);
        for (p, at) in pics.iter().zip(&places) {
            for r in 0..p.h {
                canvas.px[(at[1] + r) * width + at[0]..][..p.w].copy_from_slice(&p.px[r * p.w..(r + 1) * p.w]);
            }
        }
        Self { canvas, places, pics }
    }

    pub fn size(&self, id: usize) -> [usize; 2] {
        [self.pics[id].w, self.pics[id].h]
    }
}

/// A clip rect (x, y, w, h) in the space of the painter transform it was set under.
#[derive(Clone, Copy)]
pub struct Clip(pub Affine, pub [f64; 4]);

fn f4(v: [f64; 4]) -> [f32; 4] {
    v.map(|x| x as f32)
}

/// A full-frame layer: 0 the lobby, 1 the page (paper band and frame lines), 2 the doodles.
pub fn layer(f: &mut Frame, index: u32, size: [f64; 2], alpha: f64) {
    let mut p = Prim { kind: [LAYER, 0, 0, 0], bbox: [0.0, 0.0, size[0] as f32, size[1] as f32], ..Prim::default() };
    p.s0[0] = index as f32;
    p.colors[0] = [0.0, 0.0, 0.0, alpha.clamp(0.0, 1.0) as f32];
    f.prims.push(p);
}

/// The atlas and the screen pictures are laid on.
pub struct Sheet<'a> {
    pub atlas: &'a Atlas,
    pub screen: [f64; 2],
}

/// A picture of the atlas and the box (x, y, w, h, in points) it fills.
pub type Pic = (usize, [f64; 4]);

impl Sheet<'_> {
    /// drawImage(rect, picture) under painter transform m: the picture filling its box.
    pub fn sprite(&self, f: &mut Frame, (id, rect): Pic, m: Affine, opacity: f64, clip: Option<Clip>) {
        let (atlas, screen) = (self.atlas, self.screen);
        if opacity <= 0.0 {
            return;
        }
        let [w, h] = atlas.size(id).map(|v| v as f64);
        let place = atlas.places[id];
        let mut t = m.translate(rect[0], rect[1]).scale(rect[2] / w, rect[3] / h);
        let nearest = t.moved_only() && (rect[2] - w).abs() < 1e-9 && (rect[3] - h).abs() < 1e-9;
        if nearest {
            // Qt lays an only-moved picture at whole pixels, its place rounded.
            t = Affine([1.0, 0.0, (t.0[2] + 0.5).floor(), 0.0, 1.0, (t.0[5] + 0.5).floor()]);
        }
        let corners = [[0.0, 0.0], [w, 0.0], [0.0, h], [w, h]].map(|c| t.map(c));
        let mut bb = [f64::MAX, f64::MAX, f64::MIN, f64::MIN];
        for c in corners {
            bb = [bb[0].min(c[0]), bb[1].min(c[1]), bb[2].max(c[0]), bb[3].max(c[1])];
        }
        bb = if nearest { bb } else { [bb[0].floor() - 1.0, bb[1].floor() - 1.0, bb[2].ceil() + 1.0, bb[3].ceil() + 1.0] };
        let mut flags = u32::from(nearest);
        let mut p = Prim::default();
        if let Some(Clip(cm, r)) = clip {
            if cm.turned() {
                flags |= 2;
                let inv = cm.inverse().0;
                p.grad = f4([inv[0], inv[1], inv[2], 0.0]);
                p.stops = f4([inv[3], inv[4], inv[5], 0.0]);
                p.colors[0] = f4([r[0], r[1], r[0] + r[2], r[1] + r[3]]);
            } else {
                // A rect clip under a plain transform is cut at whole pixels.
                let (a, b) = (cm.map([r[0], r[1]]), cm.map([r[0] + r[2], r[1] + r[3]]));
                let round = |v: f64| (v + 0.5).floor();
                bb = [bb[0].max(round(a[0].min(b[0]))), bb[1].max(round(a[1].min(b[1]))), bb[2].min(round(a[0].max(b[0]))), bb[3].min(round(a[1].max(b[1])))];
            }
        }
        bb = [bb[0].max(0.0), bb[1].max(0.0), bb[2].min(screen[0]), bb[3].min(screen[1])];
        if bb[2] <= bb[0] || bb[3] <= bb[1] {
            return;
        }
        let inv = t.inverse().0;
        let det = (t.0[0] * t.0[4] - t.0[1] * t.0[3]).abs().sqrt();
        p.kind = [SPRITE, flags, 0, 0];
        p.bbox = f4(bb);
        p.s0 = f4([inv[0], inv[1], inv[2], place[0] as f64]);
        p.s1 = f4([inv[3], inv[4], inv[5], place[1] as f64]);
        p.s2 = f4([w, h, opacity.clamp(0.0, 1.0), det]);
        f.prims.push(p);
    }

    /// _place: a picture whose box is `rect` (points round its pivot) put at `at`, turned and sized.
    pub fn place(&self, f: &mut Frame, (id, rect): Pic, at: [f64; 2], angle: f64, size: f64, opacity: f64) {
        if size <= 0.01 {
            return;
        }
        let mut m = Affine::ID.translate(at[0], at[1]).rotate(angle);
        if (size - 1.0).abs() > 1e-3 {
            m = m.scale(size, size);
        }
        self.sprite(f, (id, [-rect[2] / 2.0, -rect[3] / 2.0, rect[2], rect[3]]), m, opacity, None);
    }
}
