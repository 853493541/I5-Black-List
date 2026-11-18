//! 竖琴清风 (blacklist_detect/love_scenes/lyre.py) on the graphics chip.
//!
//! As in Python, the scene's pictures (the band, the lit current, the lyre, leaves, feathers, birds...) are
//! worked out per pixel once on the CPU (`img`, `raster`, `wind`, `sprites`, `lyre_art`, `birds`, with numpy's
//! own generator in `npr`), and each frame lays them on, turned, squashed and faded, with soft dots, in the
//! Python painter's order (`paint`); `gpu` shades every pixel of every frame in WGSL (`lyre.wgsl`).
//! The scene brings its own marks (lyre.py's ring, badge, card, lead): see README.md for how far they are.

pub mod art;
pub mod birds;
pub mod gpu;
pub mod hook;
pub mod img;
pub mod lyre_art;
pub mod marks;
pub use crate::np as npr;
pub mod paint;
pub mod raster;
pub mod sprites;
pub mod wind;

use std::f64::consts::PI;

pub const DURATION: f64 = 5.0;
pub const DESIGN: (f64, f64) = (1635.0, 848.0);
pub const PINE: &str = "#0e4436";
pub const JADE: &str = "#1f8a62";
pub const MEADOW: &str = "#3fae7a";
pub const ANEMO: &str = "#4fd1a0";
pub const MINT: &str = "#a8ecd0";
pub const CORE: &str = "#f4fffa";
pub const VERMILION: &str = "#e2452b";
pub const DEEP_MAPLE: &str = "#8a1420";
pub const EMBER: &str = "#ec7a35";
pub const FEATHER: &str = "#f7fbf8";
pub const FEATHER_SHADE: &str = "#c5d8d0";
pub const HEART: &str = "#e3f0b4";
pub const ANEMO_TEAL: &str = "#5fd3d0";
pub const STILL: f64 = 2.5;
pub const STRUMS: [(f64, f64); 3] = [(0.9, 0.06), (2.9, 0.07), (4.4, 0.07)];
pub const LYRE_AT: (f64, f64) = (140.0, 146.0);
pub const LEAN: f64 = 12.0;
pub const SHARP: f64 = 1.5;
pub const PERCH: (f64, f64) = (53.0, -129.0);
pub const FLY: (f64, f64) = (0.4, 1.5);
pub const FLAP: f64 = 0.24;
pub const WAY_IN: [(f64, f64); 4] = [(1705.0, 165.0), (1370.0, 205.0), (1405.0, 130.0), (1529.0, 121.0)];
pub const PACE: [(f64, f64); 4] = [(0.0, 1.25), (0.45, 0.85), (0.75, 0.95), (1.0, 0.3)];
pub const NEST: (f64, f64) = (88.0, 845.0);
pub const BREATH: f64 = 2.8;
pub const LYRE_SCALE: f64 = 1.14;
pub const U: f64 = 0.533;
pub const CX: f64 = 155.0;
pub const CY: f64 = 190.0;
pub const STRING_X: [f64; 7] = [121.5, 132.67, 143.84, 155.01, 166.18, 177.35, 188.52];
pub const STRING_Y: (f64, f64) = (58.0, 206.5);
pub const STARTS: [(f64, f64); 3] = [(11.2, -110.0), (22.3, -75.0), (0.0, -40.0)];
pub const STROKE: f64 = 80.0;
pub const REST: f64 = 22.0;
pub const REST_REACH: f64 = 0.85;
pub const LIFT: f64 = 6.5;

/// The look the overlay gives the seats for this scene (lyre.py's LOOK); the scene draws its own marks.
pub struct Look {
    pub glow: (u8, u8, u8),
    pub rim: &'static str,
    pub band: (&'static str, &'static str),
    pub card: (&'static str, &'static str),
    pub edge: &'static str,
    pub ink: &'static str,
    pub flowers: [(&'static str, &'static str, &'static str); 2],
    pub disc: (&'static str, &'static str),
    pub heart: (&'static str, &'static str),
    pub deep: &'static str,
    pub deep_glow: (u8, u8, u8),
}

pub const LOOK: Look = Look {
    glow: (56, 182, 106),
    rim: MINT,
    band: (ANEMO, MINT),
    card: ("#1d7a58", PINE),
    edge: MINT,
    ink: "#eefff7",
    flowers: [(FEATHER, MINT, JADE), ("#fde3dc", VERMILION, "#c8202a")],
    disc: (MEADOW, PINE),
    heart: (MINT, JADE),
    deep: JADE,
    deep_glow: (63, 174, 122),
};
pub const MARKS_ANIMATED: bool = true;
pub const CARD_TOP: f64 = 0.0;

/// Where the scene plays: its size, its unit (points a design point) and the bare gap round the button.
#[derive(Clone, Copy)]
pub struct Geo {
    pub width: f64,
    pub height: f64,
    pub u: f64,
    /// left, top, width, height.
    pub gap: [f64; 4],
}

impl Geo {
    pub fn new(width: f64, height: f64, gap: [f64; 4]) -> Self {
        Self { width, height, u: (width / DESIGN.0).min(height / DESIGN.1), gap }
    }

    /// love_scenes.sample_stage: the sample lobby's button and the gap round it.
    pub fn sample(width: f64, height: f64) -> Self {
        let s = width / DESIGN.0;
        let keep = [549.0 * s, 749.0 * s, 556.0 * s, 94.0 * s];
        let gap = [keep[0] - 28.0 * s, keep[1] - 30.0 * s, keep[2] + 56.0 * s, height - keep[1] + 30.0 * s];
        Self::new(width, height, gap)
    }

    /// A design point on this stage, kept to its corner, or (side) at its share of the edge's height.
    pub fn at(&self, x: f64, y: f64, side: bool) -> [f64; 2] {
        let sx = if x < DESIGN.0 / 2.0 { x * self.u } else { self.width - (DESIGN.0 - x) * self.u };
        if side {
            return [sx, y / DESIGN.1 * self.height];
        }
        [sx, if y < DESIGN.1 / 2.0 { y * self.u } else { self.height - (DESIGN.1 - y) * self.u }]
    }
}

pub fn clamp(x: f64) -> f64 {
    x.clamp(0.0, 1.0)
}

pub fn win(t: f64, a: f64, b: f64) -> f64 {
    clamp((t - a) / (b - a))
}

pub fn ease_out(k: f64) -> f64 {
    1.0 - (1.0 - clamp(k)).powi(3)
}

pub fn ease_in_out(k: f64) -> f64 {
    let k = clamp(k);
    if k < 0.5 { 4.0 * k.powi(3) } else { 1.0 - (-2.0 * k + 2.0).powi(3) / 2.0 }
}

pub fn smooth(e0: f64, e1: f64, x: f64) -> f64 {
    let k = clamp((x - e0) / (e1 - e0));
    k * k * (3.0 - 2.0 * k)
}

/// The lyre's lean t seconds in.
pub fn angle(t: f64) -> f64 {
    LEAN + 1.2 * ((t - 1.3) * 1.4).sin()
}

/// How bright each string is t seconds in.
pub fn strum(t: f64) -> [f64; 7] {
    let mut out = [0.0; 7];
    for (i, o) in out.iter_mut().enumerate() {
        let mut v = 0.0;
        for (when, step) in STRUMS {
            let x = t - when - i as f64 * step;
            if x > 0.0 {
                v += (1.0 - (-x / 0.025).exp()) * (-x * 3.2).exp();
            }
        }
        *o = v.min(1.0);
    }
    out
}

/// A tumbling leaf's squash across its turn.
pub fn flip(phase: f64, speed: f64, life: f64) -> f64 {
    let c = (phase + life * speed).cos();
    c.abs().sqrt().copysign(c)
}

/// The phase that makes `flip` at the still what the approved still has there.
pub fn matched(phase: f64, speed: f64, floor: f64) -> f64 {
    let theta = phase + (STILL - 1.3) * speed;
    let c = theta.cos();
    let target = floor.max(c.abs()).copysign(c);
    let mut new = (target * target).copysign(target).acos();
    if theta.sin() < 0.0 {
        new = -new;
    }
    new - (STILL - 1.3) * speed
}

pub fn breath(k: f64) -> f64 {
    let k = k.rem_euclid(1.0);
    if k < 0.4 { ease_in_out(k / 0.4) } else { 1.0 - ease_in_out((k - 0.4) / 0.6) }
}

pub fn dip(x: f64, rise: f64, fall: f64) -> f64 {
    if x <= 0.0 {
        0.0
    } else if x < rise {
        ease_in_out(x / rise)
    } else {
        1.0 - ease_in_out((x - rise) / fall)
    }
}

pub fn bob(t: f64) -> f64 {
    STRUMS.iter().map(|(when, _)| dip(t - when, 0.15, 0.6)).sum()
}

/// Sitting bird which's small life: blinking, its width and height as it breathes, its sway.
pub fn idle(t: f64, which: usize) -> (bool, f64, f64, f64) {
    let (blinks, start): (&[f64], f64) = match which {
        0 => (&[2.2, 3.75], 0.0),
        1 => (&[2.3, 3.9], 0.35),
        _ => (&[1.7, 3.35, 4.15], 0.7),
    };
    let blink = blinks.iter().any(|w| (0.0..0.13).contains(&(t - w)));
    let b = breath(t / BREATH + start);
    (blink, 1.0 + 0.012 * b, 1.0 + 0.022 * b, 0.9 * (2.0 * PI * (t / 5.3 + start)).sin())
}

pub fn bezier_at(points: &[[f64; 2]; 4], k: f64) -> [f64; 2] {
    raster::bez(points[0], points[1], points[2], points[3], k)
}

fn way(k: f64) -> f64 {
    let steps: Vec<f64> = (0..201).map(|i| f64::from(i) / 200.0).collect();
    let pts = WAY_IN.map(|(x, y)| [x, y]);
    let curve: Vec<[f64; 2]> = steps.iter().map(|&j| bezier_at(&pts, j)).collect();
    let run = wind::arclen(&curve);
    let (px, py): (Vec<f64>, Vec<f64>) = PACE.iter().copied().unzip();
    let pace: Vec<f64> = steps.iter().map(|&s| wind::interp(s, &px, &py)).collect();
    let mut gone = vec![0.0];
    for i in 1..steps.len() {
        let last = gone[i - 1];
        gone.push(last + (pace[i] + pace[i - 1]) / 2.0 * (steps[i] - steps[i - 1]));
    }
    let (total, length) = (gone[gone.len() - 1], run[run.len() - 1]);
    let table: Vec<f64> = gone.iter().map(|g| wind::interp(g / total * length, &run, &steps)).collect();
    wind::interp(k, &steps, &table)
}

/// The flyer t seconds in: how far along its way, its wings (flap and reach), and its squash as it lands.
pub fn flight(t: f64) -> (f64, f64, f64, f64) {
    let k = win(t, FLY.0, FLY.1);
    if k < 1.0 {
        let last = FLY.1 - FLAP;
        let beat = if t < last { ((t - last) / FLAP).rem_euclid(1.0) } else { (t - last) / FLAP };
        if beat < 0.35 {
            return (way(k), STROKE * (beat / 0.35).powi(2), 1.0, 0.0);
        }
        if t < last {
            return (way(k), STROKE * (1.0 - (beat - 0.35) / 0.65).powi(2), 1.0, 0.0);
        }
        let r = ease_out((beat - 0.35) / 0.65);
        return (way(k), STROKE + (REST - STROKE) * r, 1.0 - (1.0 - REST_REACH) * r, 0.0);
    }
    let squash = dip(t - FLY.1, 0.07, 0.28);
    let stretch = dip(t - STRUMS[1].0, 0.45, 0.8);
    (1.0, REST - 12.0 * squash - 16.0 * stretch, REST_REACH, squash)
}

#[cfg(test)]
mod tests;
