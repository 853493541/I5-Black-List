//! 玫瑰花边, the app's first 嘉宾 border, ported from blacklist_detect/love_scenes/lace.py line for line
//! (it stays exactly as it is): sheer silk swags drop in across the top from knots of flowers, a thin
//! rose-gold frame with curls draws itself out from the middle of each edge and parts round the
//! button, roses bloom in the bottom corners, glints blink and drift down, the sides glow pink.
//!
//! The drawing engine here (prim, gpu, scene.wgsl) is crate::prim / crate::gpu grown for this scene and
//! 经典; `check` compares frames with Python's. 经典 uses them from here until the master unifies them.

pub mod check;
pub mod flowers;
pub mod gpu;
pub mod prim;

use std::f64::consts::PI;

use crate::draw::{ease_out, Pt};
use crate::lace::flowers::{knot, leaf, rose, sparkle};
use crate::lace::prim::{solid, Clip, Frame, Paint, Path, LAYER_A, LAYER_B, LOBBY};
use crate::pyrand::PyRandom;

pub const DURATION: f64 = 4.6;
/// By then the frame, the roses and the knots have settled; from there they are laid on from two
/// layers drawn once (Python's cached pictures) and only the silk and the glints are drawn again.
pub const SETTLED: f64 = 1.6;
/// love_scenes.DESIGN.
const DESIGN: [f64; 2] = [1635.0, 848.0];
/// sag, width, color, alpha.
const SILK: [(f64, f64, [u8; 3], f64); 5] = [
    (150.0, 30.0, [255, 214, 236], 0.20),
    (132.0, 16.0, [255, 236, 246], 0.30),
    (166.0, 11.0, [230, 220, 255], 0.24),
    (122.0, 2.4, [255, 255, 255], 0.80),
    (156.0, 1.8, [255, 250, 255], 0.65),
];
const ROSES: [(f64, f64, f64, f64); 4] = [(60.0, 60.0, 46.0, 10.0), (140.0, 34.0, 32.0, 40.0), (36.0, 150.0, 30.0, 70.0), (120.0, 120.0, 22.0, 20.0)];

type Rect = [f64; 4];

/// Overshoots a little and settles, like cloth dropping.
fn ease_back(k: f64) -> f64 {
    let k = k.clamp(0.0, 1.0);
    1.0 + 2.9 * (k - 1.0).powi(3) + 1.9 * (k - 1.0).powi(2)
}

/// In over the first half second, out over the last second.
fn life(t: f64) -> f64 {
    (t / 0.5).min(1.0) * ((DURATION - t) / 0.9).clamp(0.0, 1.0)
}

fn rgb(c: [u8; 3]) -> [f32; 3] {
    c.map(|v| f32::from(v) / 255.0)
}

pub struct Lace {
    pub width: f64,
    pub height: f64,
    /// The bare area round the button, x, y, w, h.
    pub gap: Rect,
    u: f64,
    /// x, y, speed, period, phase, r: random.Random(3), as every Python frame draws them.
    glints: Vec<[f64; 6]>,
}

impl Lace {
    /// love_scenes.sample_stage(width, height): the sample lobby's button gap at this size.
    pub fn sample(width: f64, height: f64) -> Self {
        let s = width / DESIGN[0];
        let keep = [549.0 * s, 749.0 * s, 556.0 * s, 94.0 * s];
        Self::new(width, height, [keep[0] - 28.0 * s, keep[1] - 30.0 * s, keep[2] + 56.0 * s, height - keep[1] + 30.0 * s])
    }

    pub fn new(width: f64, height: f64, gap: Rect) -> Self {
        let u = (width / DESIGN[0]).min(height / DESIGN[1]);
        let mut rnd = PyRandom::new(3);
        let glints = (0..26)
            .map(|_| {
                let x = rnd.uniform(0.02, 0.98) * width;
                let y = rnd.uniform(0.0, 0.42) * height;
                let speed = rnd.uniform(8.0, 26.0) * u;
                let period = rnd.uniform(0.9, 1.8);
                [x, y, speed, period, rnd.uniform(0.0, period), rnd.uniform(4.0, 11.0) * u]
            })
            .collect();
        Self { width, height, gap, u, glints }
    }

    /// The two still layers, drawn once onto transparency: what lies under the silk, and the knots.
    pub fn layers(&self) -> [Frame; 2] {
        let mut under = Frame::new();
        self.under(&mut under, SETTLED);
        let mut over = Frame::new();
        self.over(&mut over, SETTLED);
        [under, over]
    }

    /// Everything drawn at t seconds over the lobby, with the still layers from `layers`.
    pub fn paint(&self, t: f64) -> Frame {
        let mut f = Frame::new();
        f.layer(LOBBY, [self.width, self.height], 1.0);
        let life = life(t);
        if life <= 0.0 {
            return f;
        }
        f.opacity = life;
        if t >= SETTLED {
            f.layer(LAYER_A, [self.width, self.height], 1.0);
            self.swags(&mut f, t);
            f.layer(LAYER_B, [self.width, self.height], 1.0);
        } else {
            self.under(&mut f, t);
            self.swags(&mut f, t);
            self.over(&mut f, t);
        }
        self.glints(&mut f, t);
        f
    }

    /// The glowing sides, the frame parted round the button, the roses.
    fn under(&self, f: &mut Frame, t: f64) {
        self.glow_sides(f);
        let g = self.gap;
        f.clip = Clip::OutRounded([g[0], g[1], g[2], g[3], 14.0]);
        self.frame(f, t);
        f.clip = Clip::None;
        self.roses(f, t.min(SETTLED));
    }

    /// The knots of flowers the silk hangs from.
    fn over(&self, f: &mut Frame, t: f64) {
        let u = self.u;
        for i in 0..5 {
            let x = self.width * f64::from(i) / 4.0;
            knot(f, x, 6.0 * u + 20.0 * u, 38.0 * u * ease_back((t - 0.15 - 0.06 * f64::from(i)) / 0.7));
        }
    }

    fn glow_sides(&self, f: &mut Frame) {
        let (width, height) = (self.width, self.height);
        let reach = width * 0.14;
        let a = |v: u8| f64::from(v) / 255.0;
        for (x0, x1) in [(0.0, reach), (width, width - reach)] {
            let list = vec![(0.0, rgb([255, 170, 215]), a(102)), (0.5, rgb([205, 180, 255]), a(36)), (1.0, rgb([255, 170, 215]), 0.0)];
            f.rect(x0.min(x1), 0.0, reach, height, &Paint::Linear([x0, 0.0], [x1, 0.0], list));
        }
        let list = vec![(0.0, rgb([255, 200, 230]), a(71)), (1.0, rgb([255, 200, 230]), 0.0)];
        f.rect(0.0, 0.0, width, height * 0.18, &Paint::Linear([0.0, 0.0], [0.0, height * 0.18], list));
    }

    /// Sheer silk hanging between five points along the top, dropping in and swaying.
    fn swags(&self, f: &mut Frame, t: f64) {
        let u = self.u;
        let anchors: Vec<Pt> = (0..5).map(|k| [self.width * f64::from(k) / 4.0, 6.0 * u]).collect();
        for i in 0..4 {
            let (a, b) = (anchors[i], anchors[i + 1]);
            let fi = i as f64;
            let drop = ease_back((t - 0.08 * (fi - 1.5).abs()) / 1.1);
            for (layer, (sag, thick, color, alpha)) in SILK.iter().enumerate() {
                let depth = (sag + 5.0 * (t * 1.6 + fi * 0.9 + layer as f64).sin()) * u * drop;
                let mut path = Path::new(a);
                path.quad_to([(a[0] + b[0]) / 2.0, a[1] + 2.0 * depth], b);
                let pen = Paint::Solid(rgb(*color), (255.0 * alpha).round_ties_even() / 255.0);
                f.stroke_path(&path, thick * u, &pen, false, 0);
            }
        }
    }

    /// A thin rose-gold frame, drawn out from the middle of each edge, curls along top and bottom.
    fn frame(&self, f: &mut Frame, t: f64) {
        let (width, height, u) = (self.width, self.height, self.u);
        let grow = ease_out(t / 1.2);
        let inset = 16.0 * u;
        let (half_w, half_h) = ((width / 2.0 - inset) * grow, (height / 2.0 - inset) * grow);
        let line = |f: &mut Frame, a: Pt, b: Pt, w: f64, pen: &Paint| f.stroke_path(&Path::lines(&[a, b]), w, pen, true, 0);
        let pen = solid("#ffd9e6", 0.9);
        for y in [inset, height - inset] {
            line(f, [width / 2.0 - half_w, y], [width / 2.0 + half_w, y], 2.0 * u, &pen);
        }
        for x in [inset, width - inset] {
            line(f, [x, height / 2.0 - half_h], [x, height / 2.0 + half_h], 2.0 * u, &pen);
        }
        let pen = solid("#f7c4d6", 0.55);
        for y in [inset + 7.0 * u, height - inset - 7.0 * u] {
            line(f, [width / 2.0 - half_w, y], [width / 2.0 + half_w, y], u.max(1.0), &pen);
        }
        let pen = solid("#ffe3ec", 0.85);
        let step = 46.0 * u;
        for (y, flip) in [(inset + 22.0 * u, 1.0), (height - inset - 22.0 * u, -1.0)] {
            let mut reach = 0.0;
            while reach < half_w - step {
                for x in [width / 2.0 + reach, width / 2.0 - reach] {
                    let mut curl = Path::new([x - step / 2.0, y]);
                    curl.cubic_to([x - step / 4.0, y - 10.0 * u * flip], [x, y - 10.0 * u * flip], [x, y]);
                    curl.cubic_to([x, y + 6.0 * u * flip], [x + step / 6.0, y + 6.0 * u * flip], [x + step / 6.0, y + u * flip]);
                    curl.move_to([x, y]);
                    curl.cubic_to([x + step / 4.0, y + 9.0 * u * flip], [x + step / 2.0, y + 4.0 * u * flip], [x + step / 2.0, y]);
                    f.stroke_path(&curl, 1.6 * u, &pen, true, 0);
                }
                reach += step;
            }
        }
    }

    /// Pale roses, with leaves, blooming in the two bottom corners.
    fn roses(&self, f: &mut Frame, t: f64) {
        let (height, u) = (self.height, self.u);
        for (side, (cx, dirx)) in [(0.0, 1.0), (self.width, -1.0)].into_iter().enumerate() {
            let blooms: Vec<f64> = (0..ROSES.len()).map(|j| ease_back((t - 0.3 - 0.12 * j as f64 - 0.1 * side as f64) / 0.8)).collect();
            for (j, &(dx, dy, r, _)) in ROSES.iter().enumerate() {
                if blooms[j] > 0.0 {
                    leaf(f, cx + dirx * (dx + r * 0.8) * u, height - (dy - r * 0.2) * u, r * 1.3 * u * blooms[j], 30.0 * dirx + j as f64 * 25.0);
                }
            }
            for (j, &(dx, dy, r, turn)) in ROSES.iter().enumerate() {
                if blooms[j] > 0.0 {
                    rose(f, cx + dirx * dx * u, height - dy * u, r * u * blooms[j], turn + 6.0 * t);
                }
            }
        }
    }

    /// Glints drifting slowly down from the swags, each blinking on and off.
    fn glints(&self, f: &mut Frame, t: f64) {
        for &[x, y, speed, period, phase, r] in &self.glints {
            let blink = (((t + phase) % period) / period * PI).sin().max(0.0).powi(2);
            sparkle(f, x, y + speed * t, r, blink);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::Lace;

    #[test]
    fn lays_out_the_same_every_time() {
        let (a, b) = (Lace::sample(1920.0, 1080.0), Lace::sample(1920.0, 1080.0));
        assert_eq!(a.glints.len(), 26);
        assert_eq!(a.glints[0][0].to_bits(), b.glints[0][0].to_bits());
        assert_eq!(a.paint(1.0).prims.len(), b.paint(1.0).prims.len());
    }

    #[test]
    fn nothing_but_the_lobby_before_and_after() {
        let s = Lace::sample(1920.0, 1080.0);
        assert_eq!(s.paint(0.0).prims.len(), 1);
        assert_eq!(s.paint(super::DURATION).prims.len(), 1);
    }

    #[test]
    fn settled_frames_lay_on_the_layers() {
        let s = Lace::sample(1920.0, 1080.0);
        assert!(s.paint(1.0).prims.len() > 400);
        assert!(s.paint(2.0).prims.len() < s.paint(1.0).prims.len());
    }
}
