//! Molten sparks: cyber._cool, _heats, _shower (flown once with numpy's generator) and _spark_shower.

use super::canvas::{Blend, Canvas, Paint, Src};
use super::gfx::Atlas;
use super::npr::Rng;
use super::pics::dot;
use super::{lay_dot, MAGENTA};
use crate::draw::{hex, Pt};

const HEATS: usize = 8;
const STEP: f64 = 1.0 / 120.0;
const SHUTTER: f64 = 0.055;
const COOLING: [(f64, &str); 6] = [(0.0, MAGENTA), (0.25, "#ff3d6e"), (0.48, "#ff7f26"), (0.7, "#ffc247"), (0.88, "#fff0b0"), (1.0, "#ffffff")];

/// draw.mix of two byte colors, each channel rounded as QColor keeps it.
fn mixb(a: [f32; 3], b: [f32; 3], k: f64) -> [f32; 3] {
    let k = k.clamp(0.0, 1.0);
    std::array::from_fn(|i| ((f64::from(a[i]) * 255.0 + (f64::from(b[i]) - f64::from(a[i])) * 255.0 * k).round() / 255.0) as f32)
}

fn cool(heat: f64) -> [f32; 3] {
    for pair in COOLING.windows(2) {
        let ((lo, a), (hi, b)) = (pair[0], pair[1]);
        if heat <= hi {
            return mixb(hex(a), hex(b), (heat - lo) / (hi - lo));
        }
    }
    hex("#ffffff")
}

/// For each step of heat: its core (color, alpha, width), its glow's and the glow on its head.
pub struct Heat {
    core: ([f32; 3], f64, f64),
    halo: ([f32; 3], f64, f64),
    head: Src,
}

pub fn heats(u: f64, atlas: &mut Atlas) -> Vec<Heat> {
    (0..HEATS)
        .map(|b| {
            let heat = (b as f64 + 0.5) / HEATS as f64;
            let core = mixb(cool(heat), [1.0; 3], 0.3 * heat * heat);
            // QColor keeps alpha as a byte.
            let byte = |a: f64| (a.clamp(0.0, 1.0) * 255.0).round() / 255.0;
            Heat {
                core: (core, byte(0.12 + 0.88 * heat.powf(1.2)), (0.8 + 1.4 * heat) * u),
                halo: (cool(heat * 0.85), byte(0.08 + 0.3 * heat), (2.4 + 4.0 * heat) * u),
                head: atlas.add(&dot(cool(heat), ((heat - 0.3).max(0.0) * 1.5) as f32, 32)),
            }
        })
        .collect()
}

/// A shower flown once: track (steps by sparks), when each leaves, how long it lives, when it is
/// gone, its size.
pub struct Shower {
    track: Vec<Vec<[f32; 2]>>,
    delay: Vec<f64>,
    life: Vec<f64>,
    gone: Vec<f64>,
    size: Vec<f64>,
}

#[allow(clippy::too_many_arguments)]
pub fn shower(at: Pt, aim: f64, count: usize, u: f64, seed: u32, width: f64, height: f64, keep: &[[f64; 4]]) -> Shower {
    let mut rng = Rng::new(seed);
    let embers = count / 6;
    let n = count + embers;
    let mut draw = |k: usize, f: &mut dyn FnMut(&mut Rng) -> f64| (0..k).map(|_| f(&mut rng)).collect::<Vec<f64>>();
    let fast = draw(count, &mut |r| r.uniform(170.0, 480.0));
    let boost = draw(count, &mut |r| r.exponential(0.25));
    let slow_ = draw(embers, &mut |r| r.uniform(40.0, 150.0));
    let speed: Vec<f64> = fast.iter().zip(&boost).map(|(a, b)| a * (1.0 + b)).chain(slow_).collect();
    let angle = draw(n, &mut |r| aim + r.normal(0.0, 0.7));
    let jitter = draw(2 * n, &mut |r| r.normal(0.0, 3.0 * u));
    let life_a = draw(count, &mut |r| r.uniform(0.4, 1.0));
    let life_b = draw(embers, &mut |r| r.uniform(0.8, 1.15));
    let life: Vec<f64> = life_a.into_iter().chain(life_b).zip(&speed).map(|(l, s)| l * (1.15 - 0.3 * (s / 600.0).clamp(0.0, 1.0))).collect();
    let delay = draw(n, &mut |r| r.uniform(0.0, 0.05));
    let size_a = draw(count, &mut |r| r.uniform(0.8, 1.35));
    let size: Vec<f64> = size_a.into_iter().chain(draw(embers, &mut |r| r.uniform(0.5, 0.8))).collect();
    let bounce = draw(n, &mut |r| r.uniform(0.25, 0.55));
    let mut vel: Vec<[f64; 2]> = (0..n).map(|i| [angle[i].cos() * speed[i] * u, angle[i].sin() * speed[i] * u]).collect();
    let mut pos: Vec<[f64; 2]> = (0..n).map(|i| [at[0] + jitter[2 * i], at[1] + jitter[2 * i + 1]]).collect();
    let (floor, left, right, ceiling) = (height - 25.0 * u, 6.0 * u, width - 6.0 * u, 6.0 * u);
    let (gravity, drag) = (1500.0 * u * STEP, (-2.4 * STEP).exp());
    let steps = (life.iter().copied().fold(0.0, f64::max) / STEP) as usize + 3;
    let mut track = Vec::with_capacity(steps);
    for _ in 0..steps {
        track.push(pos.iter().map(|p| [p[0] as f32, p[1] as f32]).collect::<Vec<_>>());
        for i in 0..n {
            let (p, v) = (&mut pos[i], &mut vel[i]);
            v[1] += gravity;
            *v = [v[0] * drag, v[1] * drag];
            *p = [p[0] + v[0] * STEP, p[1] + v[1] * STEP];
            if p[1] > floor {
                p[1] = floor - (p[1] - floor) * bounce[i];
                v[1] *= -bounce[i];
                v[0] *= 0.82;
            }
            if p[1] < ceiling {
                p[1] = 2.0 * ceiling - p[1];
                v[1] *= -0.4;
            }
            for (edge, out) in [(left, p[0] < left), (right, p[0] > right)] {
                if out {
                    p[0] = 2.0 * edge - p[0];
                    v[0] *= -0.4;
                }
            }
        }
    }
    let mut gone = life.clone();
    for r in keep {
        let r32 = r.map(|v| v as f32);
        for (i, g) in gone.iter_mut().enumerate() {
            let first = track.iter().position(|row| {
                let [x, y] = row[i];
                x > r32[0] && x < (r[0] + r[2]) as f32 && y > r32[1] && y < (r[1] + r[3]) as f32
            });
            if let Some(k) = first {
                *g = g.min(k as f64 * STEP);
            }
        }
    }
    Shower { track, delay, life, gone, size }
}

fn along(track: &[Vec<[f32; 2]>], s: f64, i: usize) -> Pt {
    let k = (s / STEP).clamp(0.0, track.len() as f64 - 1.001);
    let k0 = k as usize;
    let f = k - k0 as f64;
    let (a, b) = (track[k0][i], track[k0 + 1][i]);
    [f64::from(a[0]) * (1.0 - f) + f64::from(b[0]) * f, f64::from(a[1]) * (1.0 - f) + f64::from(b[1]) * f]
}

/// Each spark a streak as far as it flew in SHUTTER: a hot core, a glow round its front half and a
/// glowing head, batched by heat.
pub fn spark_shower(c: &mut Canvas, age: f64, sh: &Shower, heats: &[Heat], u: f64) {
    let most = |v: &[f64]| v.iter().copied().fold(f64::MIN, f64::max);
    if age <= 0.0 || age > most(&sh.gone) + most(&sh.delay) {
        return;
    }
    let mut live = Vec::new();
    for i in 0..sh.delay.len() {
        let s = age - sh.delay[i];
        if s > 0.0 && s < sh.gone[i] {
            let heat = (1.0 - s / sh.life[i]).min((sh.gone[i] - s) / 0.12).clamp(0.0, 1.0);
            let step = ((heat * HEATS as f64) as usize).min(HEATS - 1);
            let head = along(&sh.track, s, i);
            let mid = along(&sh.track, (s - SHUTTER * 0.45).max(0.0), i);
            let tail = along(&sh.track, (s - SHUTTER).max(0.0), i);
            live.push((head, mid, tail, step, (1.6 + 3.4 * heat) * sh.size[i] * u));
        }
    }
    if live.is_empty() {
        return;
    }
    let saved = c.save();
    let base = c.opacity;
    c.blend(Blend::Plus);
    for (step, h) in heats.iter().enumerate() {
        let mine: Vec<_> = live.iter().filter(|l| l.3 == step).collect();
        for l in &mine {
            c.line(l.1, l.0, h.halo.2, &Paint::Solid(h.halo.0, h.halo.1), true);
        }
        for l in &mine {
            c.line(l.2, l.0, h.core.2, &Paint::Solid(h.core.0, h.core.1), true);
        }
    }
    for l in &live {
        lay_dot(c, heats[l.3].head, l.0, l.4, base);
    }
    c.restore(saved);
}
