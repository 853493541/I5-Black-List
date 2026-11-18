//! 金色传说 (love_scenes/angel.py): a gilded cathedral frame draws itself round the lobby, a round
//! window of golden light where the 流浪汉's sack rises and becomes the 愚人's hat, candlelight, shafts
//! of light, falling gold-leaf feathers and rising motes. Its per-pixel pictures (the gold, the glass,
//! the light) are baked once on the CPU exactly as the numpy code makes them (`bake`), and each frame
//! lays them and the vector shapes on with the graphics chip (`paint`, in paint.rs).

mod atlas;
mod frame;
mod gild;
mod glass;
pub mod gpu;
mod light;
mod lines;
mod paint;
#[cfg(test)]
mod parity;
pub mod pcg;
pub mod px;

use atlas::{Atlas, Region};
use lines::{Line, Rect, DRAW};

use crate::draw::Pt;
use crate::pyrand::PyRandom;

pub use atlas::Atlas as Pictures;

pub const DURATION: f64 = 5.0;
const DESIGN: [f64; 2] = [1635.0, 848.0];
/// 6.28 as the Python scene has it, not TAU: the same numbers come out of the same seed.
#[allow(clippy::approx_constant)]
const TURN: f64 = 6.28;

pub struct Angel {
    pub width: f64,
    pub height: f64,
    pub gap: Rect,
    u: f64,
    lines: Vec<Line>,
    center: Pt,
    radius: f64,
    regions: Vec<Rect>,
    ends: f64,
    meet: f64,
    keystone: Pt,
    glints: Vec<(f64, usize, f64, bool)>,
    falling: Vec<[f64; 7]>,
    rising: Vec<[f64; 6]>,
    dust: Vec<[f64; 6]>,
}

/// Where each baked picture is in the atlas.
pub struct Art {
    areas: Vec<(Rect, Region, Region, f64)>,
    halo: Region,
    sack: [Region; 3],
    hat: [Region; 3],
    keep: Region,
    shafts: [Region; 2],
    feather: (Region, f64),
    spark: Region,
    rays: Region,
}

impl Angel {
    /// love_scenes.sample_stage(width, height): the sample lobby's button gap at this size.
    pub fn sample(width: f64, height: f64) -> Self {
        let s = width / DESIGN[0];
        let keep = [549.0 * s, 749.0 * s, 556.0 * s, 94.0 * s];
        Self::new(width, height, [keep[0] - 28.0 * s, keep[1] - 30.0 * s, keep[2] + 56.0 * s, height - keep[1] + 30.0 * s])
    }

    pub fn new(width: f64, height: f64, gap: Rect) -> Self {
        let u = (width / DESIGN[0]).min(height / DESIGN[1]);
        let (lines, (center, radius), regions) = lines::cathedral(width, height, u);
        let ends = lines.iter().map(|l| l.start + l.span).fold(f64::MIN, f64::max);
        let meet = 0.12 + (width / 2.0 - 10.0 * u) / (DRAW * u);
        let mut rnd = PyRandom::new(31);
        let mut tracks: Vec<usize> = (0..lines.len()).collect();
        tracks.sort_by(|&a, &b| lines[b].run[lines[b].run.len() - 1].total_cmp(&lines[a].run[lines[a].run.len() - 1]));
        tracks.truncate(10);
        let glints = (0..9)
            .map(|i| (2.0 + 0.27 * f64::from(i) + rnd.uniform(0.0, 0.15), tracks[i as usize % tracks.len()], rnd.uniform(0.9, 1.4), rnd.random() < 0.5))
            .collect();
        let falling = (0..10)
            .map(|i| {
                let born = rnd.uniform(0.6, 3.0);
                let x = if i % 2 == 1 { rnd.uniform(0.025, 0.1) } else { rnd.uniform(0.958, 0.985) } * width;
                [born, x, rnd.uniform(0.18, 0.55) * height, rnd.uniform(34.0, 52.0) * u, rnd.uniform(50.0, 66.0) * u, rnd.uniform(0.0, TURN), rnd.uniform(1.1, 1.9)]
            })
            .collect();
        let rising = (0..36)
            .map(|i| {
                let born = rnd.uniform(0.2, 4.0);
                let x = if i % 2 == 1 { rnd.uniform(0.0, 0.13) } else { rnd.uniform(0.9, 1.0) } * width;
                [born, x, height * rnd.uniform(0.86, 1.02), rnd.uniform(40.0, 90.0) * u, rnd.uniform(1.3, 2.8) * u, rnd.uniform(0.0, TURN)]
            })
            .collect();
        let dust = (0..20)
            .map(|_| [rnd.uniform(1.6, 3.4), rnd.uniform(0.35, 1.0), rnd.uniform(1.95, 2.9), rnd.uniform(0.35, 0.95), rnd.uniform(1.0, 2.2) * u, rnd.uniform(0.0, TURN)])
            .collect();
        let keystone = [width / 2.0, 40.0 * u];
        Self { width, height, gap, u, lines, center, radius, regions, ends, meet, keystone, glints, falling, rising, dust }
    }

    /// Every picture the scene lays on, worked out per pixel at one pixel to the point.
    pub fn bake(&self) -> (Atlas, Art) {
        let (u, scale) = (self.u, 1.0);
        let mut atlas = Atlas::new(2048);
        let areas = self
            .regions
            .iter()
            .map(|&rect| {
                let a = gild::area(rect, &self.lines, scale, u);
                (rect, atlas.put(&a.gold, Some(&a.gold_t)), atlas.put(&a.bloom, Some(&a.bloom_t)), a.scale)
            })
            .collect();
        let mut glass = |icon| {
            let g = glass::rose_glass(self.radius, scale, u, icon);
            [atlas.put(&g.back, None), atlas.put(&g.figure, None), atlas.put(&g.shine, None)]
        };
        let (sack, hat) = (glass(&glass::SACK_ICON), glass(&glass::HAT_ICON));
        let (keep, layers) = light::shafts(self.width, self.height, self.gap, self.center, self.radius, u);
        let px = ((66.0 * u * scale / 8.0).ceil() as usize * 8).max(16);
        let (feather, root) = light::feather(px);
        let art = Art {
            areas,
            halo: atlas.put(&glass::halo(self.radius, scale), None),
            sack,
            hat,
            keep: atlas.put(&keep, None),
            shafts: [atlas.put(&layers[0], None), atlas.put(&layers[1], None)],
            feather: (atlas.put(&feather, None), root),
            spark: atlas.put(&light::spark(), None),
            rays: atlas.put(&glass::rays(self.radius, scale), None),
        };
        (atlas, art)
    }
}

#[cfg(test)]
mod tests {
    use super::Angel;

    #[test]
    fn lays_out_the_same_every_time() {
        let (a, b) = (Angel::sample(1920.0, 1080.0), Angel::sample(1920.0, 1080.0));
        assert_eq!(a.lines.len(), b.lines.len());
        assert_eq!(a.dust[19][5].to_bits(), b.dust[19][5].to_bits());
        // What angel._cathedral gives at 1920x1080: 294 lines, drawn by 1.8114 s, 21349.55 points of them.
        assert_eq!(a.lines.len(), 294);
        assert!((a.ends - 1.811352350927835).abs() < 1e-9, "{}", a.ends);
        let total: f64 = a.lines.iter().map(|l| l.run[l.run.len() - 1]).sum();
        assert!((total - 21349.552967128315).abs() < 1e-6, "{total}");
    }
}
