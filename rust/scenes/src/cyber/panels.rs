//! What the two holographic panels show, still and moving: cyber._chrome, _radar, _mesh, _wire and
//! _orbit. Lettering is left out (no font rasterizer here yet).

use std::f64::consts::{PI, TAU};

use super::canvas::{col, Canvas, Paint, Src, ATLAS};
use super::chrome::{chrome, ease_back};
use super::hud::{arc, dashed, sq_line};
use super::text::{Face, Type};
use super::{lay_dot, CYAN, MAGENTA};

const ICE: &str = "#e9fdff";
use crate::draw::{ease_in_out, ease_out, mix, win, Pt};
use crate::pyrand::PyRandom;

fn solid(color: [f32; 3], alpha: f64) -> Paint {
    Paint::Solid(color, alpha)
}

pub struct Radar {
    pub b: [f64; 4],
    pub rr: f64,
    pub c: Pt,
    pub sweep: Src,
    pub dots: [Src; 2],
    x0: f64,
    bar: (f64, f64),
    rows: [f64; 5],
    wave: [f64; 4],
    readings: Vec<Vec<f64>>,
}

const TARGETS: [(f64, f64, bool); 5] = [(0.68, -2.25, true), (0.4, 0.7, false), (0.8, 1.95, true), (0.55, -0.55, false), (0.3, 2.85, false)];
const RATE: f64 = TAU / 1.8;

impl Radar {
    pub fn new(b: [f64; 4], u: f64, sweep: Src, dots: [Src; 2]) -> Self {
        let rr = (b[3] - 48.0 * u) / 2.0;
        let c = [b[0] + 26.0 * u + rr, b[1] + 32.0 * u + rr];
        let x0 = c[0] + rr + 32.0 * u;
        let bar = (x0 + 40.0 * u, b[0] + b[2] - 58.0 * u);
        let rows = std::array::from_fn(|i| b[1] + 44.0 * u + i as f64 * 21.0 * u);
        let wave = [bar.0, rows[4] + 14.0 * u, b[0] + b[2] - 22.0 * u - bar.0, b[1] + b[3] - 12.0 * u - rows[4] - 14.0 * u];
        let mut rnd = PyRandom::new(5);
        let readings = (0..5).map(|_| (0..24).map(|_| rnd.uniform(0.3, 0.97)).collect()).collect();
        Self { b, rr, c, sweep, dots, x0, bar, rows, wave, readings }
    }

    pub fn sweep_side(b: [f64; 4], u: f64) -> usize {
        (((b[3] - 48.0 * u) / 2.0 * 4.0).round() as usize).max(16)
    }

    pub fn still(&self, c: &mut Canvas, u: f64, ty: &Type) {
        chrome(c, self.b, u, ty, "嘉宾 · TARGET SCAN", "SYS.07", false);
        let (cx, cy, rr) = (self.c[0], self.c[1], self.rr);
        c.circle(cx, cy, rr, &col(CYAN, 0.06));
        c.ring(cx, cy, rr, rr, 1.4 * u, &col(CYAN, 0.95));
        for k in [0.34, 0.67] {
            c.ring(cx, cy, rr * k, rr * k, 0.9 * u, &col(CYAN, 0.38));
        }
        sq_line(c, [cx - rr, cy], [cx + rr, cy], 0.8 * u, &col(CYAN, 0.28));
        sq_line(c, [cx, cy - rr], [cx, cy + rr], 0.8 * u, &col(CYAN, 0.28));
        for i in 0..72 {
            let a = f64::from(i) * TAU / 72.0;
            let major = i % 6 == 0;
            let (r0, r1) = (rr + 2.5 * u, rr + if major { 8.0 } else { 4.5 } * u);
            let paint = col(CYAN, if major { 0.9 } else { 0.45 });
            sq_line(c, [cx + a.cos() * r0, cy + a.sin() * r0], [cx + a.cos() * r1, cy + a.sin() * r1], if major { 1.3 } else { 0.8 } * u, &paint);
        }
        for (i, (label, &y)) in ["PWR", "SIG", "SYNC", "FLUX", "LINK"].iter().zip(&self.rows).enumerate() {
            ty.draw(c, Face::Small, [self.x0, y + 3.5 * u], label, if i == 4 { MAGENTA } else { CYAN }, 0.85);
            c.line([self.bar.0, y], [self.bar.1, y], 4.0 * u, &col(CYAN, 0.16), false);
        }
        let w = self.wave;
        let mid = w[1] + w[3] / 2.0;
        sq_line(c, [w[0], mid], [w[0] + w[2], mid], 0.8 * u, &col(CYAN, 0.22));
        for x in [w[0], w[0] + w[2]] {
            sq_line(c, [x, w[1]], [x, w[1] + w[3]], 0.8 * u, &col(CYAN, 0.22));
        }
    }

    pub fn moving(&self, c: &mut Canvas, age: f64, u: f64, ty: &Type) {
        let (cx, cy, rr) = (self.c[0], self.c[1], self.rr);
        let theta = -PI / 2.0 + age * RATE;
        let (s, co) = theta.sin_cos();
        c.picture(ATLAS, self.sweep, [-rr, -rr, 2.0 * rr, 2.0 * rr], [co, s, -s, co, cx, cy], 1.0, None);
        let turn = -(age * 0.7).to_degrees();
        for k in 0..3 {
            let from = ((turn + f64::from(k) * 120.0) * 16.0).round() / 16.0;
            c.stroke(&arc(cx, cy, rr * 0.86, rr * 0.86, from, 70.0), 1.6 * u, &col(CYAN, 0.55), false);
            let a = (-(turn + f64::from(k) * 120.0)).to_radians();
            c.line([cx + a.cos() * rr * 0.8, cy + a.sin() * rr * 0.8], [cx + a.cos() * rr * 0.92, cy + a.sin() * rr * 0.92], 2.4 * u, &col(MAGENTA, 0.9), false);
        }
        for (r, phi, locked) in TARGETS {
            let found = (age * RATE - (phi + PI / 2.0).rem_euclid(TAU)) / RATE;
            if found < 0.0 {
                continue;
            }
            let mut lit = (-(theta - phi).rem_euclid(TAU) / 1.3).exp();
            let (x, y) = (cx + phi.cos() * r * rr, cy + phi.sin() * r * rr);
            if locked {
                lit = lit.max(0.55);
            }
            lay_dot(c, self.dots[usize::from(locked)], [x, y], (6.0 + 7.0 * lit) * u, 0.4 + 0.6 * lit);
            c.opacity = 1.0;
            c.circle(x, y, 1.6 * u, &col("#ffffff", 0.4 + 0.6 * lit));
            if locked {
                let k = ease_out(win(found, 0.05, 0.4));
                let size = (6.0 + 14.0 * (1.0 - k)) * u;
                let arm = 3.5 * u;
                for (sx, sy) in [(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)] {
                    let (bx, by) = (x + sx * size, y + sy * size);
                    c.stroke(&[[bx, by - sy * arm], [bx, by], [bx - sx * arm, by]], 1.4 * u, &col(MAGENTA, 0.95 * win(found, 0.0, 0.1)), false);
                }
                if k > 0.6 {
                    ty.draw(c, Face::Small, [x + size + 3.0 * u, y - size + 2.0 * u], "LOCK", MAGENTA, (k - 0.6) / 0.4);
                }
            }
        }
        let grow = ease_out(win(age, 0.35, 1.0));
        for (i, (seq, &y)) in self.readings.iter().zip(&self.rows).enumerate() {
            let k = age / 0.62 + i as f64 * 0.37;
            let n = k as usize;
            let f = ease_in_out(k - n as f64);
            let v = (seq[n % 24] * (1.0 - f) + seq[(n + 1) % 24] * f) * grow;
            let tint = if i == 4 { MAGENTA } else { CYAN };
            let end = self.bar.0 + (self.bar.1 - self.bar.0) * v;
            dashed(c, [self.bar.0, y], [end, y], 4.0 * u, (1.15, 0.38), &solid(mix(tint, "#ffffff", 0.15), 0.95));
            sq_line(c, [end, y - 4.5 * u], [end, y + 4.5 * u], 1.3 * u, &col("#ffffff", 0.95));
            ty.draw(c, Face::Small, [self.bar.1 + 9.0 * u, y + 3.5 * u], &format!("{:4.1}", v * 100.0), ICE, 0.85);
        }
        let w = self.wave;
        let points: Vec<Pt> = (0..73)
            .map(|j| {
                let s = f64::from(j) / 72.0;
                let swing = 0.62 * (s * 21.0 - age * 9.0).sin() + 0.38 * (s * 47.0 + age * 13.0).sin();
                [w[0] + s * w[2], w[1] + w[3] / 2.0 + w[3] * 0.46 * (PI * s).sin() * swing * grow]
            })
            .collect();
        c.stroke(&points, 4.0 * u, &col(MAGENTA, 0.3), true);
        c.stroke(&points, 1.1 * u, &col("#ffd9f6", 0.95), true);
    }
}

/// A regular solid: corners on the unit sphere, edges (nearest pairs), triangles.
pub struct Solid {
    v: Vec<[f64; 3]>,
    edges: Vec<(usize, usize)>,
    faces: Vec<[usize; 3]>,
}

impl Solid {
    fn new(corners: &[[f64; 3]]) -> Self {
        let n = corners.len();
        let d = |i: usize, j: usize| (0..3).map(|k| (corners[i][k] - corners[j][k]).powi(2)).sum::<f64>().sqrt();
        let min = (0..n).flat_map(|i| (0..n).map(move |j| (i, j))).map(|(i, j)| d(i, j)).filter(|&x| x > 1e-6).fold(f64::MAX, f64::min);
        let near = |i: usize, j: usize| (d(i, j) - min).abs() < 1e-3;
        let edges: Vec<(usize, usize)> = (0..n).flat_map(|i| (i + 1..n).map(move |j| (i, j))).filter(|&(i, j)| near(i, j)).collect();
        let faces = edges.iter().flat_map(|&(i, j)| (j + 1..n).filter(move |&k| near(i, k) && near(j, k)).map(move |k| [i, j, k])).collect();
        let v = corners.iter().map(|c| c.map(|x| x / c.iter().map(|y| y * y).sum::<f64>().sqrt())).collect();
        Self { v, edges, faces }
    }

    pub fn icosahedron() -> Self {
        let phi = (1.0 + 5f64.sqrt()) / 2.0;
        let mut c = Vec::new();
        for (a, b) in [(-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0), (1.0, 1.0)] {
            c.push([0.0, a, b * phi]);
        }
        for (a, b) in [(-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0), (1.0, 1.0)] {
            c.push([a, b * phi, 0.0]);
        }
        for (a, b) in [(-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0), (1.0, 1.0)] {
            c.push([a * phi, 0.0, b]);
        }
        Self::new(&c)
    }

    pub fn octahedron() -> Self {
        Self::new(&[[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0], [0.0, 0.0, -1.0]])
    }
}

fn turn(yaw: f64, pitch: f64) -> [[f64; 3]; 3] {
    let (sy, cy) = yaw.sin_cos();
    let (sp, cp) = pitch.sin_cos();
    let spin = [[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]];
    let tilt = [[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]];
    std::array::from_fn(|i| std::array::from_fn(|j| (0..3).map(|k| tilt[i][k] * spin[k][j]).sum()))
}

/// A wireframe solid turned: faces toward us tinted as the light falls on them, edges brighter
/// the nearer they are, a glowing point at each corner.
#[allow(clippy::too_many_arguments)]
fn wire(c: &mut Canvas, shape: &Solid, center: Pt, r: f64, m: [[f64; 3]; 3], tint: &str, u: f64, alpha: f64) {
    let w: Vec<[f64; 3]> = shape.v.iter().map(|v| std::array::from_fn(|i| (0..3).map(|k| m[i][k] * v[k]).sum())).collect();
    let pts: Vec<Pt> = w.iter().map(|p| {
        let depth = 1.0 / (1.0 - p[2] * 0.22);
        [center[0] + p[0] * r * depth, center[1] - p[1] * r * depth]
    }).collect();
    let light = [-0.45, 0.6, 0.66];
    for f in &shape.faces {
        let (a, b, cc) = (w[f[0]], w[f[1]], w[f[2]]);
        let (e1, e2): ([f64; 3], [f64; 3]) = (std::array::from_fn(|k| b[k] - a[k]), std::array::from_fn(|k| cc[k] - a[k]));
        let mut n = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]];
        let sign = (0..3).map(|k| n[k] * (a[k] + b[k] + cc[k])).sum::<f64>().signum();
        let len = n.iter().map(|x| x * x).sum::<f64>().sqrt();
        n = n.map(|x| x * sign / len);
        if n[2] > 0.0 {
            let lit = (0..3).map(|k| n[k] * light[k]).sum::<f64>();
            c.poly(&[pts[f[0]], pts[f[1]], pts[f[2]]], &col(tint, alpha * (0.03 + 0.13 * lit.max(0.0))));
        }
    }
    let mut last = None;
    for (k, near) in [0.3, 0.62, 1.0].into_iter().enumerate() {
        let lines: Vec<(usize, usize)> = shape
            .edges
            .iter()
            .copied()
            .filter(|&(i, j)| {
                let z = (w[i][2] + w[j][2]) / 2.0;
                (if z < -0.3 { 0 } else if z < 0.3 { 1 } else { 2 }) == k
            })
            .collect();
        if lines.is_empty() {
            continue;
        }
        for &(i, j) in &lines {
            c.line(pts[i], pts[j], (3.0 + 2.0 * k as f64) * u, &col(tint, 0.2 * near * alpha), true);
        }
        let pen = (mix(tint, "#ffffff", 0.5), near * alpha, (0.7 + 0.45 * k as f64) * u);
        for &(i, j) in &lines {
            c.line(pts[i], pts[j], pen.2, &solid(pen.0, pen.1), true);
        }
        last = Some(pen);
    }
    for (p, v) in pts.iter().zip(&w) {
        let z = (v[2] + 1.0) / 2.0;
        let r = (1.2 + 0.8 * z) * u;
        c.circle(p[0], p[1], r, &col("#ffffff", alpha * (0.35 + 0.65 * z)));
        if let Some((color, a, width)) = last {
            c.ring(p[0], p[1], r, r, width, &solid(color, a));
        }
    }
}

pub struct Mesh {
    pub b: [f64; 4],
    pub center: Pt,
    pub emitter: Pt,
    pub cone_rect: [f64; 4],
    pub cone: Src,
    pub dots: [Src; 2],
    grid: [f64; 4],
    hexes: Vec<(Pt, f64)>,
    blinkers: Vec<(Pt, f64, f64)>,
    meter: [f64; 4],
    ico: Solid,
    oct: Solid,
}

fn hexagon(at: Pt, s: f64) -> Vec<Pt> {
    (0..6).map(|k| [at[0] + s * (f64::from(k) * TAU / 6.0).cos(), at[1] + s * (f64::from(k) * TAU / 6.0).sin()]).collect()
}

impl Mesh {
    pub fn cone_rect(b: [f64; 4], u: f64) -> ([f64; 4], Pt) {
        let r = 58.0 * u;
        let center = [b[0] + b[2] - 138.0 * u, b[1] + 100.0 * u];
        let emitter = [center[0], b[1] + b[3] - 13.0 * u];
        ([center[0] - 90.0 * u, center[1] - r * 0.9, 180.0 * u, emitter[1] + 10.0 * u - (center[1] - r * 0.9)], emitter)
    }

    pub fn new(b: [f64; 4], u: f64, cone: Src, dots: [Src; 2]) -> Self {
        let center = [b[0] + b[2] - 138.0 * u, b[1] + 100.0 * u];
        let (cone_rect, emitter) = Self::cone_rect(b, u);
        let size = 12.0 * u;
        let grid = [b[0] + 8.0 * u, b[1] + 30.0 * u, b[2] - 16.0 * u, b[3] - 38.0 * u];
        let mut hexes = Vec::new();
        let (mut i, mut x) = (0, grid[0]);
        while x < grid[0] + grid[2] + size {
            let mut y = grid[1] + if i % 2 == 1 { size * 3f64.sqrt() / 2.0 } else { 0.0 };
            while y < grid[1] + grid[3] + size {
                let d = (x - center[0]).hypot(y - center[1]);
                hexes.push(([x, y], 0.06 + 0.5 * (-(d / (150.0 * u)).powi(2)).exp()));
                y += size * 3f64.sqrt();
            }
            x += size * 1.5;
            i += 1;
        }
        let mut rnd = PyRandom::new(11);
        let blinkers = (0..9)
            .map(|_| {
                let at = hexes[rnd.below(hexes.len())].0;
                let rate = rnd.uniform(1.5, 3.5);
                (at, rate, rnd.uniform(0.0, TAU))
            })
            .collect();
        let meter = [b[0] + 22.0 * u, b[1] + b[3] - 52.0 * u, 132.0 * u, 40.0 * u];
        Self { b, center, emitter, cone_rect, cone, dots, grid, hexes, blinkers, meter, ico: Solid::icosahedron(), oct: Solid::octahedron() }
    }

    pub fn still(&self, c: &mut Canvas, u: f64, lit: bool, ty: &Type) {
        chrome(c, self.b, u, ty, "HOLO MESH · ICO-20", "LIVE", true);
        let saved = c.save();
        c.clip_to(self.grid);
        for &(at, alpha) in &self.hexes {
            let mut h = hexagon(at, 12.0 * u * 0.94);
            h.push(h[0]);
            c.stroke(&h, 0.8 * u, &col(CYAN, alpha), false);
        }
        c.restore(saved);
        if lit {
            c.lay(ATLAS, self.cone, self.cone_rect, 1.0);
        }
        for (k, alpha) in [(1.0, 0.95), (0.7, 0.6), (0.4, 0.4)] {
            c.ring(self.emitter[0], self.emitter[1], 46.0 * u * k, 7.0 * u * k, 1.1 * u, &col(CYAN, alpha));
        }
        let m = self.meter;
        ty.draw(c, Face::Small, [m[0], m[1] - 6.0 * u], "OUTPUT", CYAN, 0.6);
        sq_line(c, [m[0], m[1] + m[3] + 2.0 * u], [m[0] + m[2], m[1] + m[3] + 2.0 * u], 0.8 * u, &col(CYAN, 0.3));
    }

    fn orbit(c: &mut Canvas, o: [f64; 4], start: f64, u: f64) {
        let pts = arc(o[0] + o[2] / 2.0, o[1] + o[3] / 2.0, o[2] / 2.0, o[3] / 2.0, start, 180.0);
        let near = start == 180.0;
        c.stroke(&pts, 4.0 * u, &col(MAGENTA, if near { 0.25 } else { 0.12 }), false);
        c.stroke(&pts, u, &col("#ff9be9", if near { 0.9 } else { 0.4 }), false);
    }

    pub fn moving(&self, c: &mut Canvas, age: f64, u: f64, ty: &Type) {
        let grow = ease_out(win(age, 0.3, 0.9));
        for &(at, rate, phase) in &self.blinkers {
            let k = (age * rate + phase).sin().max(0.0).powi(4) * grow;
            if k > 0.02 {
                let h = hexagon(at, 12.0 * u * 0.94);
                c.poly(&h, &col(CYAN, 0.22 * k));
                let mut ring = h.clone();
                ring.push(h[0]);
                c.stroke(&ring, u, &col("#9ffcff", 0.8 * k), false);
            }
        }
        lay_dot(c, self.dots[0], self.emitter, 34.0 * u, 0.6 + 0.15 * (age * 11.0).sin());
        c.opacity = 1.0;
        let reach = 58.0 * u * ease_back(win(age, 0.3, 0.95), 1.2);
        let ctr = self.center;
        let o = [ctr[0] - reach * 1.55, ctr[1] + reach * 0.12 - reach * 0.3, reach * 3.1, reach * 0.6];
        let spin = age * 2.1;
        let dot = [o[0] + o[2] / 2.0 + o[2] / 2.0 * spin.cos(), o[1] + o[3] / 2.0 + o[3] / 2.0 * spin.sin()];
        if reach > 1.0 {
            Self::orbit(c, o, 0.0, u);
            if spin.sin() < 0.0 {
                lay_dot(c, self.dots[1], dot, 10.0 * u, 0.6);
                c.opacity = 1.0;
            }
            wire(c, &self.oct, ctr, reach * 0.48, turn(-age * 1.6, -0.35), MAGENTA, u, 0.95);
            wire(c, &self.ico, ctr, reach, turn(age * 0.85, 0.42 + 0.14 * (age * 0.7).sin()), CYAN, u, 1.0);
            Self::orbit(c, o, 180.0, u);
            if spin.sin() >= 0.0 {
                lay_dot(c, self.dots[1], dot, 13.0 * u, 0.95);
                c.opacity = 1.0;
            }
        }
        for i in 0..5u32 {
            let typed = ((age - 0.35 - f64::from(i) * 0.07) * 70.0) as i64;
            if typed <= 0 {
                continue;
            }
            let mut rnd = PyRandom::new(((age * 6.0 + f64::from(i) * 0.53) as u32) * 97 + i);
            let words: Vec<String> = (0..3).map(|_| format!("{:04X}", rnd.below(65536))).collect();
            let text: String = words.join(" ").chars().take(typed as usize).collect();
            let y = self.b[1] + 44.0 * u + f64::from(i) * 15.0 * u;
            ty.draw(c, Face::Small, [self.b[0] + 22.0 * u, y], &text, if i == 2 { MAGENTA } else { CYAN }, 0.8);
        }
        let m = self.meter;
        let step = m[2] / 16.0;
        for j in 0..16 {
            let jf = f64::from(j);
            let level = (0.2 + 0.8 * ((age * (2.7 + jf * 0.31) + jf * 1.7).sin() * (age * 1.3 + jf * 0.9).sin()).abs()) * grow;
            let x = m[0] + jf * step + step / 2.0;
            let bottom = m[1] + m[3];
            dashed(c, [x, bottom], [x, bottom - m[3] * level], step * 0.62, (0.45, 0.22), &solid(mix(CYAN, MAGENTA, level * level), 0.9));
        }
    }
}
