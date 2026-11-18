//! The molten sparks a strike throws (neon._shower, _spark_shower): flown once with numpy's
//! generator under gravity and drag, bouncing off the bottom tube and the sides; each frame a streak
//! per spark, its glow and its glowing head, colored by how hot it still is.

use crate::draw::mix;

use super::frame::Frame;
use super::np::Rng;
use super::raster::{Img, Pt};
use super::{Rect, MAGENTA};

const STEP: f64 = 1.0 / 120.0;
const SHUTTER: f64 = 0.055;
pub const HEATS: usize = 8;
const COOLING: [(f64, &str); 6] = [(0.0, MAGENTA), (0.25, "#ff3d6e"), (0.48, "#ff7f26"), (0.7, "#ffc247"), (0.88, "#fff0b0"), (1.0, "#ffffff")];

/// neon._cool: a spark's color at a heat, rounded to bytes.
pub fn cool(heat: f64) -> [f32; 3] {
    for w in COOLING.windows(2) {
        let ((lo, a), (hi, b)) = (w[0], w[1]);
        if heat <= hi {
            return mix(a, b, (heat - lo) / (hi - lo));
        }
    }
    [1.0; 3]
}

/// One step of heat: the core's color and width, the glow's, and its head's round glow picture.
pub struct Heat {
    pub core: ([f32; 4], f64),
    pub halo: ([f32; 4], f64),
    pub dot: usize,
}

/// neon._heats: cooler sparks dimmer and thinner. `add` stores a picture and gives its id.
pub fn heats(u: f64, add: &mut dyn FnMut(Img) -> usize) -> Vec<Heat> {
    (0..HEATS)
        .map(|b| {
            let heat = (b as f64 + 0.5) / HEATS as f64;
            let hex = |c: [f32; 3]| format!("#{:02x}{:02x}{:02x}", (c[0] * 255.0).round() as u8, (c[1] * 255.0).round() as u8, (c[2] * 255.0).round() as u8);
            let c = mix(&hex(cool(heat)), "#ffffff", 0.3 * heat * heat);
            let h = cool(heat * 0.85);
            let alpha = |a: f64| (a.clamp(0.0, 1.0) * 255.0).round() as f32 / 255.0;
            Heat {
                core: ([c[0], c[1], c[2], alpha(0.12 + 0.88 * heat.powf(1.2))], (0.8 + 1.4 * heat) * u),
                halo: ([h[0], h[1], h[2], alpha(0.08 + 0.3 * heat)], (2.4 + 4.0 * heat) * u),
                dot: add(super::sky::dot(cool(heat), ((heat - 0.3).max(0.0) * 1.5) as f32, 32)),
            }
        })
        .collect()
}

/// A strike's sparks: tracks (step by spark, float32 as numpy keeps them), when each leaves, how
/// long it lives, when it is gone, its size.
pub struct Shower {
    track: Vec<Vec<[f32; 2]>>,
    delay: Vec<f64>,
    life: Vec<f64>,
    gone: Vec<f64>,
    size: Vec<f64>,
}

/// neon._shower: sparks thrown from `at`, most toward `aim`, gone once they reach what `keep` holds.
#[allow(clippy::too_many_arguments)]
pub fn shower(at: Pt, aim: f64, count: usize, u: f64, seed: u32, width: f64, height: f64, keep: &[Rect]) -> Shower {
    let mut rng = Rng::new(seed);
    let embers = count / 6;
    let n = count + embers;
    let fast = rng.uniform(150.0, 460.0, count);
    let boost: Vec<f64> = (0..count).map(|_| 1.0 + 0.25 * rng.exponential()).collect();
    let mut speed: Vec<f64> = fast.iter().zip(&boost).map(|(a, b)| a * b).collect();
    speed.extend(rng.uniform(40.0, 150.0, embers));
    let angle: Vec<f64> = (0..n).map(|_| aim + 0.75 * rng.normal()).collect();
    let mut vel: Vec<[f64; 2]> = (0..n).map(|i| [angle[i].cos() * speed[i] * u, angle[i].sin() * speed[i] * u]).collect();
    let mut pos: Vec<[f64; 2]> = (0..n).map(|_| [at[0] + 2.0 * u * rng.normal(), at[1] + 2.0 * u * rng.normal()]).collect();
    let mut life = rng.uniform(0.45, 1.1, count);
    life.extend(rng.uniform(0.8, 1.2, embers));
    for (l, s) in life.iter_mut().zip(&speed) {
        *l *= 1.15 - 0.3 * (s / 600.0).clamp(0.0, 1.0);
    }
    let delay = rng.uniform(0.0, 0.05, n);
    let mut size = rng.uniform(0.8, 1.35, count);
    size.extend(rng.uniform(0.5, 0.8, embers));
    let bounce = rng.uniform(0.25, 0.55, n);
    let (floor, left, right) = (height - 25.0 * u, 6.0 * u, width - 6.0 * u);
    let (gravity, slow) = (1500.0 * u * STEP, (-2.4 * STEP).exp());
    let steps = (life.iter().copied().fold(0.0, f64::max) / STEP) as usize + 3;
    let mut track = Vec::with_capacity(steps);
    for _ in 0..steps {
        track.push(pos.iter().map(|p| [p[0] as f32, p[1] as f32]).collect::<Vec<_>>());
        for i in 0..n {
            vel[i][1] += gravity;
            vel[i] = [vel[i][0] * slow, vel[i][1] * slow];
            pos[i] = [pos[i][0] + vel[i][0] * STEP, pos[i][1] + vel[i][1] * STEP];
            if pos[i][1] > floor {
                pos[i][1] = floor - (pos[i][1] - floor) * bounce[i];
                vel[i][1] *= -bounce[i];
                vel[i][0] *= 0.82;
            }
            let (out_left, out_right) = (pos[i][0] < left, pos[i][0] > right);
            for (edge, outside) in [(left, out_left), (right, out_right)] {
                if outside {
                    pos[i][0] = 2.0 * edge - pos[i][0];
                    vel[i][0] *= -0.4;
                }
            }
        }
    }
    let mut gone = life.clone();
    for r in keep {
        for (i, g) in gone.iter_mut().enumerate() {
            let inside = |p: [f32; 2]| {
                let (x, y) = (f64::from(p[0]), f64::from(p[1]));
                x > r[0] && x < r[0] + r[2] && y > r[1] && y < r[1] + r[3]
            };
            if let Some(k) = track.iter().position(|row| inside(row[i])) {
                *g = g.min(k as f64 * STEP);
            }
        }
    }
    Shower { track, delay, life, gone, size }
}

impl Shower {
    /// neon._along: where spark i is s seconds into its flight.
    fn along(&self, s: f64, i: usize) -> Pt {
        let k = (s / STEP).clamp(0.0, self.track.len() as f64 - 1.001);
        let k0 = k as usize;
        let f = k - k0 as f64;
        let (a, b) = (self.track[k0][i], self.track[k0 + 1][i]);
        [f64::from(a[0]) * (1.0 - f) + f64::from(b[0]) * f, f64::from(a[1]) * (1.0 - f) + f64::from(b[1]) * f]
    }

    /// neon._spark_shower: each spark a streak as far as it flew in SHUTTER, a glow round its
    /// front half and a glowing head, added.
    pub fn paint(&self, f: &mut Frame, age: f64, heats: &[Heat], u: f64) {
        let last = self.gone.iter().copied().fold(f64::MIN, f64::max) + self.delay.iter().copied().fold(f64::MIN, f64::max);
        if age <= 0.0 || age > last {
            return;
        }
        let base = f.opacity;
        let mut sparks = Vec::new();
        for i in 0..self.delay.len() {
            let s = age - self.delay[i];
            if !(s > 0.0 && s < self.gone[i]) {
                continue;
            }
            let heat = (1.0 - s / self.life[i]).min((self.gone[i] - s) / 0.12).clamp(0.0, 1.0);
            let step = ((heat * HEATS as f64) as usize).min(HEATS - 1);
            let head = self.along(s, i);
            let mid = self.along((s - SHUTTER * 0.45).max(0.0), i);
            let tail = self.along((s - SHUTTER).max(0.0), i);
            sparks.push((head, mid, tail, step, (1.6 + 3.4 * heat) * self.size[i] * u));
        }
        f.plus = true;
        for (step, h) in heats.iter().enumerate() {
            for &(head, mid, _, _, _) in sparks.iter().filter(|s| s.3 == step) {
                f.stroke(&[mid, head], h.halo.1, h.halo.0);
            }
            for &(head, _, tail, _, _) in sparks.iter().filter(|s| s.3 == step) {
                f.stroke(&[tail, head], h.core.1, h.core.0);
            }
        }
        for &(head, _, _, step, r) in &sparks {
            f.dot(heats[step].dot, head[0], head[1], r, base);
        }
        f.plus = false;
    }
}
