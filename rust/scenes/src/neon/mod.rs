//! 霓虹都市 (赛博朋克（二）), ported from blacklist_detect/love_scenes/neon.py: a rain-soaked skyline
//! at night under a lightning storm, a two-tube neon frame, flying cars, billboards.
//!
//! As in Python, everything soft is worked out per pixel once (`sky`, `towers`, `signs`, the bolts'
//! light in `fx`) and laid on each frame from one atlas; the rest (rain, trails, tubes, lightning) is
//! shaded per pixel in `neon.wgsl` every frame.

pub mod frame;
pub mod fx;
pub mod gpu;
pub mod np;
mod paint;
pub mod raster;
pub mod signs;
pub mod sky;
pub mod towers;

use frame::Atlas;
use raster::{noise, round_even, Img, Pt};
use towers::{Outline, Tower};

pub const DURATION: f64 = 5.0;
pub const CYAN: &str = "#21f6ff";
pub const MAGENTA: &str = "#ff2bd6";
pub const VIOLET: &str = "#7a2cff";
pub const NIGHT: &str = "#07021a";
pub const INDIGO: &str = "#12062e";
pub const SOFT: f64 = 0.25;
pub const GLOW_BAND: f64 = 140.0;
const DESIGN: [f64; 2] = [1635.0, 848.0];
const STRIKES: [(f64, i32); 4] = [(1.3, -1), (2.3, 1), (3.05, 0), (3.7, -1)];
const DISTANT: [(f64, f64); 2] = [(0.85, 0.8), (2.8, 0.18)];
const LANES: [&[(f64, f64)]; 2] = [
    &[(-0.06, 0.25), (0.1, 0.16), (0.24, 0.095), (0.37, 0.066), (0.5, 0.06), (0.63, 0.066), (0.76, 0.095), (0.9, 0.16), (1.06, 0.25)],
    &[(-0.06, 0.15), (0.14, 0.09), (0.36, 0.058), (0.5, 0.053), (0.64, 0.058), (0.86, 0.09), (1.06, 0.15)],
];

/// x, y, w, h.
pub type Rect = [f64; 4];

/// light.rgb: a color as float32 0..1.
pub fn rgb(color: &str) -> [f32; 3] {
    crate::draw::hex(color)
}

/// draw.mix: each channel rounded to a byte.
pub fn mix_hex(a: &str, b: &str, k: f64) -> [f32; 3] {
    crate::draw::mix(a, b, k)
}

/// A strike: when it lands, where from, where to, its tower (if any), seed, bolt pictures.
pub struct Strike {
    pub when: f64,
    pub start: Pt,
    pub end: Pt,
    pub hero: Option<usize>,
    pub seed: u32,
    pub bolts: [fx::Bolt; 2],
    pub bolt_ids: [usize; 2],
    pub cloud: (Rect, usize),
}

/// A tower with what was worked out for it: outline, pictures (area, body, lights), its sign's.
pub struct Built {
    pub tower: Tower,
    pub outline: Outline,
    pub area: Rect,
    pub body: usize,
    pub lit: usize,
    pub sign: Option<(Rect, Vec<usize>)>,
}

pub struct Neon {
    pub width: f64,
    pub height: f64,
    pub gap: Rect,
    pub u: f64,
    names: Rect,
    /// Every picture, in the order the atlas holds them.
    pub images: Vec<Img>,
    night: usize,
    flashes: [usize; 2],
    distant: Vec<(f64, Rect, usize)>,
    strikes: Vec<Strike>,
    towers: Vec<Built>,
    haze: Vec<(Rect, usize)>,
    beam: (Rect, usize),
    glows: [usize; 3],
    outer: Vec<Pt>,
    inner: Vec<Pt>,
    /// hot, cyan, violet.
    lights: [usize; 3],
    beacon: usize,
    rain: Vec<fx::Rain>,
    lanes: Vec<fx::Lane>,
}

/// neon._frame: the tube round the screen from the gap's left round to its right.
fn tube_line(width: f64, height: f64, gap: Rect, m: f64, c: f64, u: f64) -> Vec<Pt> {
    let bottom = height - m;
    let tab = 12.0 * u;
    vec![
        [gap[0] - 40.0 * u, bottom], [m + c, bottom], [m, bottom - c], [m, m + c], [m + c, m],
        [width * 0.34, m], [width * 0.34 + tab, m + tab], [width * 0.66 - tab, m + tab], [width * 0.66, m],
        [width - m - c, m], [width - m, m + c], [width - m, bottom - c], [width - m - c, bottom], [gap[0] + gap[2] + 40.0 * u, bottom],
    ]
}

impl Neon {
    /// love_scenes.sample_stage(width, height): the sample lobby's button gap at this size.
    pub fn sample(width: f64, height: f64) -> Self {
        let s = width / DESIGN[0];
        let keep = [549.0 * s, 749.0 * s, 556.0 * s, 94.0 * s];
        Self::new(width, height, [keep[0] - 28.0 * s, keep[1] - 30.0 * s, keep[2] + 56.0 * s, height - keep[1] + 30.0 * s])
    }

    pub fn new(width: f64, height: f64, gap: Rect) -> Self {
        let u = (width / DESIGN[0]).min(height / DESIGN[1]);
        let mut images = Vec::new();
        let mut add = |img: Img| {
            images.push(img);
            images.len() - 1
        };
        let outer = tube_line(width, height, gap, 15.0 * u, 34.0 * u, u);
        let inner = tube_line(width, height, gap, 25.0 * u, 40.0 * u, u);
        let [g0, g1, g2] = sky::frame_glow(width, height, &outer, &inner, u);
        let glows = [add(g0), add(g1), add(g2)];
        let sky_noise = noise(round_even(width * SOFT).max(1.0) as usize, round_even(height * SOFT).max(1.0) as usize, 170.0 * u * SOFT, 4, 21);
        let night = add(sky::night(width, height, u, &sky_noise));
        let flashes = [add(sky::flash(width, height, gap, u, -1)), add(sky::flash(width, height, gap, u, 1))];
        let mut towers = Vec::new();
        for tower in towers::skyline(width, height, gap, u) {
            let outline = towers::outline(&tower, height, u);
            let wins = towers::windows(&tower, &outline, u);
            let (area, body, lit) = towers::art(&tower, &outline, &wins, height, u);
            let sign = outline.panel.map(|p| {
                let (area, pics) = signs::art(&tower, p, u);
                (area, pics.into_iter().map(&mut add).collect())
            });
            towers.push(Built { area, body: add(body), lit: add(lit), sign, tower, outline });
        }
        let names = [width * 0.13, height * 0.29, width * 0.81, height * 0.55];
        let title = [width * 0.38, height * 0.07, width * 0.3, height * 0.18];
        let keep = [names, title, [gap[0] - 30.0 * u, gap[1] - 30.0 * u, gap[2] + 60.0 * u, gap[3] + 60.0 * u]];
        let mut strikes = Vec::new();
        for (i, &(when, side)) in STRIKES.iter().enumerate() {
            let seed = i as u32 + 1;
            let hero = towers.iter().position(|b| b.tower.side == side && side != 0 && (b.tower.show == "screen" || b.tower.show == "ticker"));
            let tip = hero.and_then(|h| towers[h].outline.tip);
            let (start, end, hero) = match tip {
                Some(end) => ([end[0] - f64::from(side) * width * 0.05, -height * 0.03], end, hero),
                None => ([width * 0.2, -height * 0.03], [width * 0.24, 15.0 * u], None),
            };
            let bolts = fx::bolt_shapes(start, end, seed, u, &keep);
            let bolt_ids = [add(bolts[0].light.clone()), add(bolts[1].light.clone())];
            let (rect, img) = sky::cloud_flash(width, height, u, &sky_noise, start[0] / width, title);
            strikes.push(Strike { when, start, end, hero, seed, bolts, bolt_ids, cloud: (rect, add(img)) });
        }
        let distant = DISTANT
            .iter()
            .map(|&(when, at)| {
                let (rect, img) = sky::cloud_flash(width, height, u, &sky_noise, at, title);
                (when, rect, add(img))
            })
            .collect();
        let lights = [add(sky::dot(rgb("#bff9ff"), 1.0, 64)), add(sky::dot(rgb(CYAN), 0.25, 64)), add(sky::dot(rgb(VIOLET), 0.0, 64))];
        let beacon = add(sky::dot(rgb("#ff2a3a"), 0.5, 32));
        let haze = [-1, 1]
            .iter()
            .map(|&side| {
                let (rect, img) = sky::haze(width, height, gap, u, side);
                (rect, add(img))
            })
            .collect();
        let (beam_rect, beam_img) = sky::beam(height, u);
        let beam = (beam_rect, add(beam_img));
        let rain = fx::rain_drops(width, height, u);
        let lanes = LANES.iter().map(|l| fx::lane(l, width, height)).collect();
        Self { width, height, gap, u, names, images, night, flashes, distant, strikes, towers, haze, beam, glows, outer, inner, lights, beacon, rain, lanes }
    }

    /// The atlas of every picture, `w` texels wide.
    pub fn atlas(&self, w: u32) -> Atlas {
        Atlas::pack(&self.images, w)
    }
}

#[cfg(test)]
mod tests {
    use super::Neon;

    #[test]
    fn lays_out_the_python_skyline() {
        let n = Neon::sample(1920.0, 1080.0);
        // Two strikes on the towers' spires (the screen's and the ticker's), one on the frame.
        assert_eq!(n.strikes.iter().filter(|s| s.hero.is_some()).count(), 3);
        assert!(n.towers.len() >= 16, "{}", n.towers.len());
        let atlas = n.atlas(4096);
        assert_eq!(atlas.at.len(), n.images.len());
    }
}
