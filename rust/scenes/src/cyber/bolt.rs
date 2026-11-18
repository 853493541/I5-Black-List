//! Lightning: cyber._bolt_points, _bolt_shapes, _bolt_light, _strike_light and _strike.

use super::canvas::{col, Blend, Canvas, Paint, Src, ATLAS};
use super::gfx::Atlas;
use super::light::{blur, glow, rgb, round_even, smooth, stroke, Plane};
use super::{lay_dot, Cyber, CYAN, MAGENTA, VIOLET};
use crate::draw::{ease_out, hex, mix, partial, win, Pt};
use crate::pyrand::PyRandom;

/// The leader feels its way down this long before a strike lands.
pub const LEAD: f64 = 0.09;

/// One of a strike's two shapes: its main line, its branches, the box its light covers and that light.
pub struct Shape {
    pub main: Vec<Pt>,
    pub branches: Vec<Vec<Pt>>,
    pub boxed: [f64; 4],
    pub light: Src,
}

/// How bright a strike is age seconds after it: a flash, a dip, a second flash, then gone.
pub fn strike_light(age: f64) -> f64 {
    if !(0.0..=0.5).contains(&age) {
        return 0.0;
    }
    if age < 0.05 {
        1.0
    } else if age < 0.1 {
        0.3
    } else if age < 0.16 {
        0.9
    } else {
        (0.9 * (1.0 - (age - 0.16) / 0.34)).max(0.0).powf(1.6)
    }
}

/// A jagged line from start to end: midpoints pushed sideways, less at each finer step.
pub fn bolt_points(start: Pt, end: Pt, rnd: &mut PyRandom, rough: f64, levels: u32) -> Vec<Pt> {
    let mut points = vec![start, end];
    let mut spread = (end[0] - start[0]).hypot(end[1] - start[1]) * rough;
    for _ in 0..levels {
        let mut out = vec![points[0]];
        for pair in points.windows(2) {
            let (a, b) = (pair[0], pair[1]);
            let (dx, dy) = (b[0] - a[0], b[1] - a[1]);
            let length = match dx.hypot(dy) {
                l if l == 0.0 => 1.0,
                l => l,
            };
            let push = rnd.gauss(0.0, spread);
            out.push([(a[0] + b[0]) / 2.0 - dy / length * push, (a[1] + b[1]) / 2.0 + dx / length * push]);
            out.push(b);
        }
        points = out;
        spread *= 0.55;
    }
    points
}

fn contains(r: [f64; 4], p: Pt) -> bool {
    p[0] >= r[0] && p[0] <= r[0] + r[2] && p[1] >= r[1] && p[1] <= r[1] + r[3]
}

/// A strike's two shapes, the flash and the restrike down the same channel with new branches;
/// channel and branches keep out of the names and the title.
pub fn bolt_shapes(start: Pt, end: Pt, seed: u32, u: f64, keep: &[[f64; 4]], atlas: &mut Atlas) -> Vec<Shape> {
    let clear = |points: &[Pt]| !keep.iter().any(|&r| points.iter().any(|&q| contains(r, q)));
    let mut rnd = PyRandom::new(seed);
    let mut channel = bolt_points(start, end, &mut rnd, 0.09, 6);
    for _ in 0..60 {
        if clear(&channel) {
            break;
        }
        channel = bolt_points(start, end, &mut rnd, 0.09, 6);
    }
    let mut out = Vec::new();
    for k in 0..2 {
        let mut rnd = PyRandom::new(seed * 1000 + k);
        let n = channel.len();
        let mut main = vec![channel[0]];
        for q in &channel[1..n - 1] {
            let x = q[0] + rnd.gauss(0.0, 2.0 * u);
            main.push([x, q[1] + rnd.gauss(0.0, 2.0 * u)]);
        }
        main.push(channel[n - 1]);
        let mut branches: Vec<Vec<Pt>> = Vec::new();
        for _ in 0..16 {
            let lo = main.len() / 6;
            let a = main[lo + rnd.below(main.len() * 3 / 4 - lo)];
            let rest = main[main.len() - 1];
            let turn = rnd.choice(&[-1.0, 1.0]) * rnd.uniform(0.35, 0.85);
            let angle = (rest[1] - a[1]).atan2(rest[0] - a[0]) + turn;
            let reach = (rest[0] - a[0]).hypot(rest[1] - a[1]) * rnd.uniform(0.2, 0.45);
            let branch = bolt_points(a, [a[0] + angle.cos() * reach, a[1] + angle.sin() * reach], &mut rnd, 0.13, 4);
            if !clear(&branch) {
                continue;
            }
            let b = branch[branch.len() / 2];
            branches.push(branch);
            if rnd.random() < 0.6 {
                let bend = angle + rnd.choice(&[-1.0, 1.0]) * rnd.uniform(0.4, 0.9);
                let twig = bolt_points(b, [b[0] + bend.cos() * reach * 0.4, b[1] + bend.sin() * reach * 0.4], &mut rnd, 0.15, 3);
                if clear(&twig) {
                    branches.push(twig);
                }
            }
            if branches.len() >= 6 {
                break;
            }
        }
        let (boxed, light) = bolt_light(&main, &branches, u, atlas);
        out.push(Shape { main, branches, boxed, light });
    }
    out
}

/// The light round a bolt at a quarter of the size: white where it burns, a pale cyan bloom close
/// round it, cyan and violet spreading wide, faded out toward its box's edges.
fn bolt_light(main: &[Pt], branches: &[Vec<Pt>], u: f64, atlas: &mut Atlas) -> ([f64; 4], Src) {
    let k = 0.25;
    let pad = 110.0 * u;
    let all = main.iter().chain(branches.iter().flatten());
    let (mut x0, mut y0, mut x1, mut y1) = (f64::MAX, f64::MAX, f64::MIN, f64::MIN);
    for p in all {
        (x0, y0, x1, y1) = (x0.min(p[0]), y0.min(p[1]), x1.max(p[0]), y1.max(p[1]));
    }
    let boxed = [x0 - pad, y0 - pad, x1 - x0 + 2.0 * pad, y1 - y0 + 2.0 * pad];
    let (w, h) = (round_even(boxed[2] * k).max(1.0) as usize, round_even(boxed[3] * k).max(1.0) as usize);
    let at = |pts: &[Pt]| pts.iter().map(|p| [(p[0] - boxed[0]) * k, (p[1] - boxed[1]) * k]).collect::<Vec<Pt>>();
    let mut core = Plane::new(w, h);
    stroke(&mut core, &at(main), 5.0 * u * k, 1.0);
    for b in branches {
        stroke(&mut core, &at(b), 2.6 * u * k, 0.7);
    }
    let mid = mix(CYAN, VIOLET, 0.55);
    let tints = [(1.0, rgb("#9ff7ff"), 1.2), (3.0, rgb(CYAN), 1.9), (8.5, mid, 3.4), (21.0, rgb(VIOLET), 6.0)];
    let blurs: Vec<(Plane, [f32; 3], f32)> = tints.iter().map(|&(s, c, st)| (blur(&core, s), c, st)).collect();
    let pic = glow(w, h, |x, y| {
        let c = core.at(x, y).powf(1.5) * 1.1;
        let edge = x.min(w - 1 - x).min(y.min(h - 1 - y)) as f64;
        let fade = smooth(0.0, pad * k, edge) as f32;
        std::array::from_fn(|ch| {
            let mut v = c;
            for (b, tint, strength) in &blurs {
                v += b.at(x, y) * tint[ch] * strength;
            }
            v * fade
        })
    });
    (boxed, atlas.add(&pic))
}

fn line(c: &mut Canvas, points: &[Pt], width: f64, color: &str, alpha: f64) {
    c.stroke(points, width, &col(color, alpha), true);
}

/// A leader feeling its way down, then the strike: its light, its white core, glows where it lands
/// and the sky it comes from, and rings thrown off.
pub fn strike(c: &mut Canvas, s: &Cyber, age: f64, start: Pt, end: Pt, shapes: &[Shape]) {
    if !(-LEAD..=0.55).contains(&age) {
        return;
    }
    let u = s.u;
    let saved = c.save();
    let base = c.opacity;
    c.blend(Blend::Plus);
    if age < 0.0 {
        let reach = partial(&shapes[0].main, (age + LEAD) / LEAD);
        line(c, &reach, 1.5 * u, "#c9f9ff", 0.65);
        if let Some(&tip) = reach.last() {
            lay_dot(c, s.pics.cyan, tip, 34.0 * u, 0.6 * base);
        }
        c.restore(saved);
        return;
    }
    let light = strike_light(age);
    let shape = &shapes[if age < 0.1 { 0 } else { 1 }];
    if light > 0.0 {
        c.opacity = base * light;
        c.lay(ATLAS, shape.light, shape.boxed, 1.0);
        c.opacity = base;
        line(c, &shape.main, 2.2 * u, "#ffffff", light);
        for b in &shape.branches {
            line(c, b, 1.1 * u, "#e6fdff", 0.8 * light);
        }
        lay_dot(c, s.pics.violet, end, 120.0 * u, 0.4 * light * base);
        lay_dot(c, s.pics.cyan, end, 64.0 * u, 0.75 * light * base);
        lay_dot(c, s.pics.hot, end, 30.0 * u, light * base);
        lay_dot(c, s.pics.violet, start, 200.0 * u, 0.6 * light * base);
    }
    c.opacity = base;
    for (delay, tint) in [(0.0, CYAN), (0.07, MAGENTA)] {
        let k = win(age - delay, 0.0, 0.38);
        if 0.0 < k && k < 1.0 {
            let r = (10.0 + 46.0 * ease_out(k)) * u;
            c.ring(end[0], end[1], r, r, (3.2 - 2.0 * k) * u, &Paint::Solid(hex(tint), 0.85 * (1.0 - k).powi(2)));
        }
    }
    c.restore(saved);
}
