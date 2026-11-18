//! What moves over the skyline each frame (neon.py): the rain, the flying cars' trails, the neon
//! frame's spark and tubes, the lightning (leader, bolt, its light, rings) and the struck spire's arcs.

use crate::draw::{clamp, ease_out, mix, partial, win};
use crate::pyrand::PyRandom;

use super::frame::{rgba, Frame};
use super::raster::{blur, glow, round_even, smooth, Img, Light, Mask, Pt};
use super::sky::polyline;
use super::{rgb, Rect, CYAN, MAGENTA, VIOLET};

pub const SLANT: f64 = 0.16;
pub const LEAD: f64 = 0.09;

fn shade(c: [f32; 3], alpha: f64) -> [f32; 4] {
    [c[0], c[1], c[2], clamp(alpha) as f32]
}

/// One layer of rain: where each drop crosses the top, its phase, speed and length; pen, alpha, bright front.
pub struct Rain {
    pub x0: Vec<f64>,
    pub phase: Vec<f64>,
    pub speed: Vec<f64>,
    pub length: Vec<f64>,
    pub pen: f64,
    pub alpha: f64,
    pub front: bool,
}

/// neon._rain_drops, from numpy's generator seeded 31.
pub fn rain_drops(width: f64, height: f64, u: f64) -> Vec<Rain> {
    let mut rng = super::np::Rng::new(31);
    let layers = [(160.0, (850.0, 1100.0), (9.0, 16.0), 0.8, 0.26, false), (60.0, (1500.0, 1900.0), (22.0, 38.0), 1.2, 0.3, true)];
    layers
        .iter()
        .map(|&(count, speed, length, pen, alpha, front)| {
            let n = round_even(count * width / 1635.0) as usize;
            let x0 = rng.uniform(-SLANT * height, width, n);
            let phase = rng.uniform(0.0, 1.0, n);
            let speed = rng.uniform(speed.0, speed.1, n).iter().map(|v| v * u).collect();
            let length = rng.uniform(length.0, length.1, n).iter().map(|v| v * u).collect();
            Rain { x0, phase, speed, length, pen: pen * u, alpha, front }
        })
        .collect()
}

/// neon._rain: streaks tinted by the neon, faint over the names, none in the gap, added.
#[allow(clippy::too_many_arguments)]
pub fn rain(f: &mut Frame, t: f64, layers: &[Rain], width: f64, height: f64, gap: Rect, names: Rect, u: f64, a: f64, flash: f64) {
    if a <= 0.0 {
        return;
    }
    f.plus = true;
    let tints = [("#ffb3ee", "#ffe0f8"), ("#c2b8ff", "#ece8ff"), ("#a8fbff", "#e2feff")];
    let span = height + 80.0 * u;
    for l in layers {
        for i in 0..l.x0.len() {
            let head = (l.phase[i] * span + l.speed[i] * t).rem_euclid(span) - 20.0 * u;
            let (tail, middle) = (head - l.length[i], head - l.length[i] * 0.45);
            let (xh, xm, xt) = (l.x0[i] + SLANT * head, l.x0[i] + SLANT * middle, l.x0[i] + SLANT * tail);
            if xh > gap[0] - 8.0 * u && xt < gap[0] + gap[2] + 8.0 * u && head > gap[1] - 10.0 * u {
                continue;
            }
            let dim = xh > names[0] && xh < names[0] + names[2] && head > names[1] && tail < names[1] + names[3];
            let zone = usize::from(xh >= width / 3.0) + usize::from(xh >= width * 2.0 / 3.0);
            let (tint, hot) = tints[zone];
            let strength = l.alpha * a * if dim { 0.28 } else { 1.0 } * (1.0 + 1.6 * flash);
            f.stroke(&[[xt, tail], [xh, head]], l.pen, shade(mix(tint, "#ffffff", flash * 0.6), strength * 0.6));
            if l.front {
                f.stroke(&[[xm, middle], [xh, head]], l.pen, shade(mix(hot, "#ffffff", flash * 0.6), strength));
            }
        }
    }
    f.plus = false;
}

/// draw.catmull: a smooth curve through points.
pub fn catmull(points: &[Pt], per: usize) -> Vec<Pt> {
    let mut pts = vec![points[0]];
    pts.extend_from_slice(points);
    pts.push(points[points.len() - 1]);
    let mut out = Vec::new();
    for i in 1..pts.len() - 2 {
        let (p0, p1, p2, p3) = (pts[i - 1], pts[i], pts[i + 1], pts[i + 2]);
        for s in 0..per {
            let t = s as f64 / per as f64;
            let (t2, t3) = (t * t, t * t * t);
            let c = |k: usize| 0.5 * ((2.0 * p1[k]) + (-p0[k] + p2[k]) * t + (2.0 * p0[k] - 5.0 * p1[k] + 4.0 * p2[k] - p3[k]) * t2 + (-p0[k] + 3.0 * p1[k] - 3.0 * p2[k] + p3[k]) * t3);
            out.push([c(0), c(1)]);
        }
    }
    out.push(points[points.len() - 1]);
    out
}

pub struct Lane {
    pub points: Vec<Pt>,
    pub cumulative: Vec<f64>,
}

pub fn lane(points: &[(f64, f64)], width: f64, height: f64) -> Lane {
    let pts: Vec<Pt> = points.iter().map(|&(x, y)| [x * width, y * height]).collect();
    let points = catmull(&pts, 16);
    let mut cumulative = vec![0.0];
    for w in points.windows(2) {
        cumulative.push(cumulative[cumulative.len() - 1] + (w[1][0] - w[0][0]).hypot(w[1][1] - w[0][1]));
    }
    Lane { points, cumulative }
}

/// draw.point_at: the point at a distance along the lane, and the direction there.
fn point_at(l: &Lane, distance: f64) -> (Pt, f64) {
    let c = &l.cumulative;
    let distance = distance.clamp(0.0, c[c.len() - 1]);
    let (mut lo, mut hi) = (0, c.len() - 1);
    while hi - lo > 1 {
        let mid = (lo + hi) / 2;
        if c[mid] < distance {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    let (a, b) = (l.points[lo], l.points[hi]);
    let seg = if c[hi] - c[lo] == 0.0 { 1.0 } else { c[hi] - c[lo] };
    let k = (distance - c[lo]) / seg;
    ([a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k], (b[1] - a[1]).atan2(b[0] - a[0]))
}

const CARS: [(usize, i32, f64, f64); 6] = [(0, 1, 0.5, 1.5), (1, -1, 1.0, 1.9), (0, -1, 1.8, 1.4), (1, 1, 2.45, 1.8), (0, 1, 3.1, 1.45), (1, -1, 3.55, 1.7)];

/// neon._trails: flying cars, a hot head and a long light trail, added. `lights`: hot, cyan, violet.
pub fn trails(f: &mut Frame, t: f64, lanes: &[Lane], lights: [usize; 3], height: f64, u: f64, a: f64) {
    if a <= 0.0 {
        return;
    }
    f.plus = true;
    let base = f.opacity;
    let pieces = 12;
    for &(lane, way, start, cross) in &CARS {
        let k = (t - start) / cross;
        if !(0.0 < k && k < 1.5) {
            continue;
        }
        let l = &lanes[lane];
        let total = l.cumulative[l.cumulative.len() - 1];
        let trail = total * 0.42;
        let (mut head, mut tail) = (k * (total + trail) * 0.75, 0.0);
        tail += head - trail;
        if way < 0 {
            (head, tail) = (total - head, total - tail);
        }
        let (tint, hot) = if way > 0 { (CYAN, "#e9fdff") } else { (MAGENTA, "#ffe3f8") };
        let fade = a * (1.0 - win(k, 1.15, 1.5));
        let track: Vec<(Pt, f64, f64, bool)> = (0..=pieces)
            .map(|i| {
                let s = tail + (head - tail) * f64::from(i) / f64::from(pieces);
                let (at, angle) = point_at(l, s);
                (at, angle, 0.45 + 0.55 * clamp((at[1] - height * 0.05) / (height * 0.15)), (0.0..=total).contains(&s))
            })
            .collect();
        for i in 1..=pieces as usize {
            let ((a0, _, _, in0), (a1, angle, near, in1)) = (track[i - 1], track[i]);
            if !(in0 && in1) {
                continue;
            }
            let k = i as f64 / f64::from(pieces);
            let strength = k.powf(1.6) * fade;
            f.stroke(&[a0, a1], 8.0 * u * near, rgba(tint, 0.2 * strength));
            for side in [-1.0, 1.0] {
                let (dx, dy) = (-angle.sin() * side * 1.6 * u * near, angle.cos() * side * 1.6 * u * near);
                f.stroke(&[[a0[0] + dx, a0[1] + dy], [a1[0] + dx, a1[1] + dy]], 1.3 * u * near, shade(mix(tint, hot, k), strength * 0.9));
            }
        }
        let (front, _, near, inside) = track[pieces as usize];
        if inside {
            f.dot(lights[if way > 0 { 1 } else { 2 }], front[0], front[1], 22.0 * u * near, 0.8 * fade * base);
            f.dot(lights[0], front[0], front[1], 8.0 * u * near, fade * base);
            f.star(front[0], front[1], 11.0 * u * near, "#ffffff", 0.7 * fade);
        }
    }
    f.plus = false;
}

/// neon._bolt_points: a jagged line, midpoints pushed sideways, less at each finer step.
pub fn bolt_points(start: Pt, end: Pt, rnd: &mut PyRandom, rough: f64, levels: u32) -> Vec<Pt> {
    let mut points = vec![start, end];
    let mut spread = (end[0] - start[0]).hypot(end[1] - start[1]) * rough;
    for _ in 0..levels {
        let mut out = vec![points[0]];
        for w in points.windows(2) {
            let (a, b) = (w[0], w[1]);
            let (dx, dy) = (b[0] - a[0], b[1] - a[1]);
            let length = if dx.hypot(dy) == 0.0 { 1.0 } else { dx.hypot(dy) };
            let push = rnd.gauss(0.0, spread);
            out.push([(a[0] + b[0]) / 2.0 - dy / length * push, (a[1] + b[1]) / 2.0 + dx / length * push]);
            out.push(b);
        }
        points = out;
        spread *= 0.55;
    }
    points
}

fn contains(r: Rect, p: Pt) -> bool {
    r[0] <= p[0] && p[0] <= r[0] + r[2] && r[1] <= p[1] && p[1] <= r[1] + r[3]
}

/// One look of a strike: main line, branches, the box its light covers, that light.
pub struct Bolt {
    pub main: Vec<Pt>,
    pub branches: Vec<Vec<Pt>>,
    pub box_: Rect,
    pub light: Img,
}

/// neon._bolt_shapes: the flash and the restrike down the same channel, kept off the names and title.
pub fn bolt_shapes(start: Pt, end: Pt, seed: u32, u: f64, keep: &[Rect]) -> [Bolt; 2] {
    let clear = |pts: &[Pt]| !pts.iter().any(|&q| keep.iter().any(|&r| contains(r, q)));
    let mut rnd = PyRandom::new(seed);
    let mut channel = bolt_points(start, end, &mut rnd, 0.09, 6);
    for _ in 0..60 {
        if clear(&channel) {
            break;
        }
        channel = bolt_points(start, end, &mut rnd, 0.09, 6);
    }
    std::array::from_fn(|k| {
        let mut rnd = PyRandom::new(seed * 1000 + k as u32);
        let n = channel.len();
        let mut main = vec![channel[0]];
        for q in &channel[1..n - 1] {
            let x = q[0] + rnd.gauss(0.0, 2.0 * u);
            main.push([x, q[1] + rnd.gauss(0.0, 2.0 * u)]);
        }
        main.push(channel[n - 1]);
        let mut branches = Vec::new();
        for _ in 0..16 {
            let lo = main.len() / 6;
            let (a, rest) = (main[lo + rnd.below(main.len() * 3 / 4 - lo)], main[main.len() - 1]);
            let turn = rnd.choice(&[-1.0, 1.0]);
            let angle = (rest[1] - a[1]).atan2(rest[0] - a[0]) + turn * rnd.uniform(0.35, 0.85);
            let reach = (rest[0] - a[0]).hypot(rest[1] - a[1]) * rnd.uniform(0.2, 0.45);
            let branch = bolt_points(a, [a[0] + angle.cos() * reach, a[1] + angle.sin() * reach], &mut rnd, 0.13, 4);
            if !clear(&branch) {
                continue;
            }
            let b = branch[branch.len() / 2];
            branches.push(branch);
            if rnd.random() < 0.6 {
                let turn = rnd.choice(&[-1.0, 1.0]);
                let bend = angle + turn * rnd.uniform(0.4, 0.9);
                let twig = bolt_points(b, [b[0] + bend.cos() * reach * 0.4, b[1] + bend.sin() * reach * 0.4], &mut rnd, 0.15, 3);
                if clear(&twig) {
                    branches.push(twig);
                }
            }
            if branches.len() >= 6 {
                break;
            }
        }
        let (box_, light) = bolt_light(&main, &branches, u);
        Bolt { main, branches, box_, light }
    })
}

/// neon._bolt_light: white where it burns, pale cyan close round it, cyan and violet spreading wide.
fn bolt_light(main: &[Pt], branches: &[Vec<Pt>], u: f64) -> (Rect, Img) {
    let (k, pad) = (0.25, 110.0 * u);
    let all = main.iter().chain(branches.iter().flatten());
    let b = all.fold([f64::MAX, f64::MAX, f64::MIN, f64::MIN], |b, p| [b[0].min(p[0]), b[1].min(p[1]), b[2].max(p[0]), b[3].max(p[1])]);
    let box_ = [b[0] - pad, b[1] - pad, b[2] - b[0] + 2.0 * pad, b[3] - b[1] + 2.0 * pad];
    let (w, h) = (round_even(box_[2] * k) as usize, round_even(box_[3] * k) as usize);
    let at = |pts: &[Pt]| -> Vec<Pt> { pts.iter().map(|p| [(p[0] - box_[0]) * k, (p[1] - box_[1]) * k]).collect() };
    let mut m = Mask::new(w, h);
    m.fill(&polyline(&at(main), 5.0 * u * k), 1.0);
    for br in branches {
        m.fill(&polyline(&at(br), 2.6 * u * k), (f64::from((0.7f64 * 255.0).round() as u8) / 255.0) as f32);
    }
    let core = m.done();
    let mid = mix(CYAN, VIOLET, 0.55);
    let blurs: Vec<(super::raster::Grid, [f32; 3], f32)> =
        [(1.0, rgb("#9ff7ff"), 1.2), (3.0, rgb(CYAN), 1.9), (8.5, mid, 3.4), (21.0, rgb(VIOLET), 6.0)].iter().map(|&(s, c, k)| (blur(&core, s), c, k)).collect();
    let light: Light = (0..w * h)
        .map(|n| {
            let (x, y) = ((n % w) as f32, (n / w) as f32);
            let edge = x.min(w as f32 - 1.0 - x).min(y.min(h as f32 - 1.0 - y));
            let fade = smooth(0.0, (pad * k) as f32, edge);
            let mut l = [core.v[n].powf(1.5) * 1.1; 3];
            for (g, c, s) in &blurs {
                for q in 0..3 {
                    l[q] += g.v[n] * c[q] * s;
                }
            }
            l.map(|v| v * fade)
        })
        .collect();
    (box_, glow(w, h, &light))
}

/// neon._strike: the leader feeling its way down, then the strike's light, core, flash and rings.
#[allow(clippy::too_many_arguments)]
pub fn strike(f: &mut Frame, age: f64, start: Pt, end: Pt, bolts: &[Bolt; 2], light_ids: [usize; 2], lights: [usize; 3], u: f64) {
    if !(-LEAD..=0.55).contains(&age) {
        return;
    }
    f.plus = true;
    let base = f.opacity;
    if age < 0.0 {
        let reach = partial(&bolts[0].main, (age + LEAD) / LEAD);
        f.stroke(&reach, 1.5 * u, rgba("#c9f9ff", 0.65));
        if let Some(tip) = reach.last() {
            f.dot(lights[1], tip[0], tip[1], 34.0 * u, 0.6 * base);
        }
        f.plus = false;
        return;
    }
    let light = super::sky::strike_light(age);
    let which = if age < 0.1 { 0 } else { 1 };
    let b = &bolts[which];
    if light > 0.0 {
        f.opacity = base * light;
        f.lay(light_ids[which], b.box_, true, 1.0);
        f.opacity = base;
        f.stroke(&b.main, 2.2 * u, rgba("#ffffff", light));
        for br in &b.branches {
            f.stroke(br, 1.1 * u, rgba("#e6fdff", 0.8 * light));
        }
        f.dot(lights[2], end[0], end[1], 210.0 * u, 0.55 * light * base);
        f.dot(lights[1], end[0], end[1], 120.0 * u, 0.8 * light * base);
        f.dot(lights[0], end[0], end[1], 42.0 * u, light * base);
        f.dot(lights[2], start[0], start[1], 200.0 * u, 0.6 * light * base);
    }
    for (delay, tint) in [(0.0, CYAN), (0.07, MAGENTA)] {
        let k = win(age - delay, 0.0, 0.38);
        if 0.0 < k && k < 1.0 {
            let r = (14.0 + 80.0 * ease_out(k)) * u;
            f.ring(end, r, (3.2 - 2.0 * k) * u, None, rgba(tint, 0.85 * (1.0 - k).powi(2)));
        }
    }
    f.plus = false;
}

/// neon._spire: a struck spire's tip glowing hot and cooling, little arcs crawling down it.
pub fn spire(f: &mut Frame, age: f64, tip: Pt, lights: [usize; 3], u: f64, seed: u32) {
    if !(0.0..=0.9).contains(&age) {
        return;
    }
    f.plus = true;
    let base = f.opacity;
    let cool = (1.0 - age / 0.9).powi(2);
    f.dot(lights[2], tip[0], tip[1] + 6.0 * u, 30.0 * u, 0.6 * cool * base);
    f.dot(lights[0], tip[0], tip[1], 9.0 * u, cool * base);
    for i in 0..3u32 {
        let start = 0.08 + 0.17 * f64::from(i);
        let k = win(age, start, start + 0.16);
        if 0.0 < k && k < 1.0 {
            let mut rnd = PyRandom::new(seed * 100 + i + (age * 30.0) as u32);
            let a = [tip[0] + rnd.uniform(-2.0, 2.0) * u, tip[1] + rnd.uniform(4.0, 18.0) * u];
            let turn = rnd.choice(&[-1.0, 1.0]);
            let b = [a[0] + turn * rnd.uniform(8.0, 16.0) * u, a[1] + rnd.uniform(10.0, 26.0) * u];
            let path = bolt_points(a, b, &mut rnd, 0.25, 4);
            for (w, color, alpha) in [(6.0, CYAN, 0.3), (2.4, "#9ffcff", 0.75), (1.0, "#ffffff", 1.0)] {
                f.stroke(&path, w * u * 0.6, rgba(color, alpha * (1.0 - k)));
            }
        }
    }
    f.plus = false;
}
