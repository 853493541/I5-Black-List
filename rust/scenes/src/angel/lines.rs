//! The tracery's lines, where each is and when it draws: angel._cathedral, _frieze, _spandrel and
//! _rose_lines, point for point.

use std::f64::consts::PI;

use crate::draw::Pt;

/// How fast the tracery spreads from where it starts, and how fast each line draws, in design points a second.
pub const SPREAD: f64 = 560.0;
pub const DRAW: f64 = 620.0;

pub struct Line {
    pub points: Vec<Pt>,
    /// How thick, in units.
    pub width: f64,
    pub start: f64,
    pub span: f64,
    /// A row of beads this far apart (in units) instead of a solid line; 0 for a line.
    pub beads: f64,
    pub run: Vec<f64>,
}

pub type Rect = [f64; 4];

fn dist(a: Pt, b: Pt) -> f64 {
    (a[0] - b[0]).hypot(a[1] - b[1])
}

pub fn lengths(points: &[Pt]) -> Vec<f64> {
    let mut out = vec![0.0];
    for w in points.windows(2) {
        out.push(out[out.len() - 1] + dist(w[0], w[1]));
    }
    out
}

/// draw.point_at: the point at a distance along a polyline.
pub fn point_at(points: &[Pt], run: &[f64], distance: f64) -> Pt {
    let d = distance.clamp(0.0, run[run.len() - 1]);
    let (mut lo, mut hi) = (0, run.len() - 1);
    while hi - lo > 1 {
        let mid = (lo + hi) / 2;
        if run[mid] < d {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    let (a, b) = (points[lo], points[hi]);
    let seg = run[hi] - run[lo];
    let k = (d - run[lo]) / if seg == 0.0 { 1.0 } else { seg };
    [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k]
}

pub fn quad(a: Pt, c: Pt, b: Pt, s: f64) -> Pt {
    let m = 1.0 - s;
    [m * m * a[0] + 2.0 * m * s * c[0] + s * s * b[0], m * m * a[1] + 2.0 * m * s * c[1] + s * s * b[1]]
}

fn arc(cx: f64, cy: f64, r: f64, a0: f64, a1: f64, count: usize) -> Vec<Pt> {
    (0..=count).map(|i| {
        let a = a0 + (a1 - a0) * i as f64 / count as f64;
        [cx + r * a.cos(), cy + r * a.sin()]
    }).collect()
}

fn circle(cx: f64, cy: f64, r: f64, count: usize) -> Vec<Pt> {
    arc(cx, cy, r, -PI / 2.0, 1.5 * PI, count)
}

/// A foil (trefoil, quatrefoil...): lobes round arcs inside r, meeting in cusps; one lobe at turn.
fn foil(cx: f64, cy: f64, r: f64, lobes: usize, turn: f64) -> Vec<Pt> {
    let (d, n) = (r * 0.5, lobes * 24);
    let b = r - d;
    (0..=n).map(|i| {
        let a = turn + 2.0 * PI * i as f64 / n as f64;
        let mut best = 0.0f64;
        for k in 0..lobes {
            let off = a - (turn + 2.0 * PI * k as f64 / lobes as f64);
            let s = d * off.sin();
            if s.abs() <= b {
                best = best.max(d * off.cos() + (b * b - s * s).sqrt());
            }
        }
        [cx + best * a.cos(), cy + best * a.sin()]
    }).collect()
}

fn normal(a: Pt, c: Pt, b: Pt, s: f64) -> Pt {
    let dx = 2.0 * (1.0 - s) * (c[0] - a[0]) + 2.0 * s * (b[0] - c[0]);
    let dy = 2.0 * (1.0 - s) * (c[1] - a[1]) + 2.0 * s * (b[1] - c[1]);
    let n = dx.hypot(dy);
    let n = if n == 0.0 { 1.0 } else { n };
    [dy / n, -dx / n]
}

fn offset(points: &[Pt], d: f64) -> Vec<Pt> {
    (0..points.len()).map(|i| {
        let (a, b) = (points[i.saturating_sub(1)], points[(i + 1).min(points.len() - 1)]);
        let (dx, dy) = (b[0] - a[0], b[1] - a[1]);
        let n = dx.hypot(dy);
        let n = if n == 0.0 { 1.0 } else { n };
        [points[i][0] - dy / n * d, points[i][1] + dx / n * d]
    }).collect()
}

fn scroll(start: Pt, heading: f64, length: f64, turn: f64) -> Vec<Pt> {
    let mut out = vec![start];
    let (mut x, mut y) = (start[0], start[1]);
    for i in 1..=48 {
        let s = i as f64 / 48.0;
        let a = heading + turn * s.powf(2.6);
        let step = length / 48.0 * (1.0 - 0.45 * s);
        x += step * a.cos();
        y += step * a.sin();
        out.push([x, y]);
    }
    out
}

struct Adder<'a> {
    lines: &'a mut Vec<Line>,
    u: f64,
}

impl Adder<'_> {
    /// A line growing out from where it is nearest origin, both ways if that is in its middle.
    fn add(&mut self, points: Vec<Pt>, thick: f64, origin: Pt, t0: f64, closed: bool, after: f64, beads: f64) {
        let nearest = |p: &[Pt]| (0..p.len()).fold(0, |best, k| if dist(p[k], origin) < dist(p[best], origin) { k } else { best });
        let parts: Vec<Vec<Pt>> = if closed {
            let p = &points[..points.len() - 1];
            let i = nearest(p);
            let mut ring: Vec<Pt> = p[i..].iter().chain(&p[..i]).copied().collect();
            ring.push(p[i]);
            let half = ring.len() / 2;
            vec![ring[..=half].to_vec(), ring[half..].iter().rev().copied().collect()]
        } else {
            let i = nearest(&points);
            [points[..=i].iter().rev().copied().collect::<Vec<_>>(), points[i..].to_vec()].into_iter().filter(|p| p.len() > 1).collect()
        };
        let u = self.u;
        for part in parts {
            let run = lengths(&part);
            let start = t0 + after + dist(part[0], origin) / (SPREAD * u);
            let span = (run[run.len() - 1] / (DRAW * u)).max(0.12);
            self.lines.push(Line { points: part, width: thick, start, span, beads, run });
        }
    }

    fn line(&mut self, points: Vec<Pt>, thick: f64, origin: Pt, t0: f64, after: f64) {
        self.add(points, thick, origin, t0, false, after, 0.0);
    }

    fn ring(&mut self, points: Vec<Pt>, thick: f64, origin: Pt, t0: f64, after: f64) {
        self.add(points, thick, origin, t0, true, after, 0.0);
    }
}

/// The lines, the round window (middle and radius) and the six areas the gold is worked out over.
pub fn cathedral(width: f64, height: f64, u: f64) -> (Vec<Line>, (Pt, f64), Vec<Rect>) {
    let mut lines = Vec::new();
    let mut add = Adder { lines: &mut lines, u };
    let (mid, low) = (width / 2.0, height * 0.76);
    let (left, right) = ([0.0, 0.0], [width, 0.0]);
    let at = |x: f64, y: f64, side: i32| [if side > 0 { x * u } else { width - x * u }, y * u];
    for (side, origin) in [(1, left), (-1, right)] {
        for (inset, thick, beads) in [(10.0, 3.6, 0.0), (16.5, 3.2, 6.6), (22.0, 1.2, 0.0)] {
            let c = at(inset, inset, side);
            add.add(vec![[c[0], low], c, [mid, c[1]]], thick, origin, 0.12, false, 0.0, beads);
        }
        let boss = at(16.0, 16.0, side);
        add.ring(foil(boss[0], boss[1], 12.0 * u, 4, PI / 4.0), 2.4, origin, 0.12, 0.0);
        add.ring(circle(boss[0], boss[1], 3.4 * u, 12), 2.0, origin, 0.12, 0.1);
        let x = if side > 0 { 16.0 * u } else { width - 16.0 * u };
        add.ring(foil(x, low + 14.0 * u, 10.0 * u, 3, PI / 2.0), 1.8, [x, low], 0.12 + (low - 10.0 * u) / (SPREAD * u), 0.0);
        add.line(vec![[x, low + 24.0 * u], [x, low + 38.0 * u]], 2.4, [x, low], 0.12 + (low + 10.0 * u) / (SPREAD * u), 0.0);
    }
    let (center, radius) = ([width - 150.0 * u, 132.0 * u], 92.0 * u);
    let (a, c, b) = (at(470.0, 22.0, 1), at(120.0, 120.0, 1), at(22.0, 430.0, 1));
    let base = 58.0 * u;
    let end = center[0] - ((radius + 6.0 * u).powi(2) - (center[1] - base).powi(2)).max(0.0).sqrt();
    frieze(&mut add, width, base, (a[0], end), left, right);
    spandrel(&mut add, a, c, b, left);
    add.ring(circle(center[0], center[1], radius, 96), 3.0, center, 0.5, 0.0);
    let regions = vec![
        [0.0, 0.0, 530.0 * u, 210.0 * u],
        [0.0, 210.0 * u, 240.0 * u, 260.0 * u],
        [530.0 * u, 0.0, (width - 830.0 * u).max(1.0), 66.0 * u],
        [width - 300.0 * u, 0.0, 300.0 * u, 270.0 * u],
        [0.0, 470.0 * u, 50.0 * u, (low + 50.0 * u - 470.0 * u).max(1.0)],
        [width - 50.0 * u, 270.0 * u, 50.0 * u, (low + 50.0 * u - 270.0 * u).max(1.0)],
    ];
    (lines, (center, radius), regions)
}

fn frieze(add: &mut Adder, width: f64, base: f64, ends: (f64, f64), left: Pt, right: Pt) {
    let u = add.u;
    let mid = width / 2.0;
    let (spring, apex, span) = (base - 8.0 * u, base - 30.0 * u, 30.0 * u);
    let r = ((span / 2.0).powi(2) + (spring - apex).powi(2)) / span;
    let open = ((r - span / 2.0) / r).acos();
    for (side, origin, end) in [(1.0, left, ends.0), (-1.0, right, ends.1)] {
        add.line(vec![[end, base], [mid - side * 16.0 * u, base]], 1.8, origin, 0.12, 0.0);
        let mut k = 0.0;
        loop {
            let x0 = mid - side * (22.0 * u + k * span);
            let x1 = x0 - side * span;
            if if side > 0.0 { x1 < end + 4.0 * u } else { x1 > end - 4.0 * u } {
                break;
            }
            let (lo, hi) = (x0.min(x1), x0.max(x1));
            let mut arch = vec![[lo, base]];
            arch.extend(arc(lo + r, spring, r, PI, PI + open, 8));
            arch.extend(arc(hi - r, spring, r, -open, 0.0, 8));
            arch.push([hi, base]);
            add.line(arch, 1.5, origin, 0.12, 0.08);
            add.ring(circle((lo + hi) / 2.0, base - 19.0 * u, 2.4 * u, 10), 1.1, origin, 0.12, 0.18);
            add.ring(circle(if side > 0.0 { lo } else { hi }, base - 24.0 * u, 2.6 * u, 10), 1.1, origin, 0.12, 0.14);
            k += 1.0;
        }
    }
    let when = 0.12 + (mid - 10.0 * u) / (SPREAD * u) - 0.25;
    let y = base - 18.0 * u;
    add.ring(circle(mid, y, 15.0 * u, 40), 2.2, [mid, y - 15.0 * u], when, 0.0);
    add.ring(foil(mid, y, 12.0 * u, 4, PI / 4.0), 1.6, [mid, y - 12.0 * u], when + 0.1, 0.0);
    add.ring(circle(mid, y, 3.0 * u, 12), 1.4, [mid, y - 3.0 * u], when + 0.2, 0.0);
}

fn spandrel(add: &mut Adder, a: Pt, c: Pt, b: Pt, origin: Pt) {
    let (u, t0) = (add.u, 0.12);
    let arch: Vec<Pt> = (0..=60).map(|i| quad(a, c, b, f64::from(i) / 60.0)).collect();
    let molding = offset(&arch, 7.0 * u);
    add.line(arch, 3.0, origin, t0, 0.0);
    add.line(molding, 1.4, origin, t0, 0.05);
    let count = 11;
    for i in 0..count {
        let (s0, s1) = ((i as f64 + 0.5) / (count as f64 + 1.0), (i as f64 + 1.5) / (count as f64 + 1.0));
        let (p0, p1, n0, n1) = (quad(a, c, b, s0), quad(a, c, b, s1), normal(a, c, b, s0), normal(a, c, b, s1));
        let sm = (s0 + s1) / 2.0;
        let (m, nm) = (quad(a, c, b, sm), normal(a, c, b, sm));
        let tip0 = [p0[0] + n0[0] * 11.0 * u, p0[1] + n0[1] * 11.0 * u];
        let tip1 = [p1[0] + n1[0] * 11.0 * u, p1[1] + n1[1] * 11.0 * u];
        let dip = [m[0] + nm[0] * 2.0 * u, m[1] + nm[1] * 2.0 * u];
        let ctrl = [2.0 * dip[0] - (tip0[0] + tip1[0]) / 2.0, 2.0 * dip[1] - (tip0[1] + tip1[1]) / 2.0];
        add.line((0..=12).map(|k| quad(tip0, ctrl, tip1, f64::from(k) / 12.0)).collect(), 1.4, origin, t0, 0.12);
        if i > 0 {
            add.ring(circle(tip0[0] + n0[0] * 2.5 * u, tip0[1] + n0[1] * 2.5 * u, 2.2 * u, 10), 1.1, origin, t0, 0.2);
        }
    }
    let (ox, oy, r) = (98.0 * u, 98.0 * u, 62.0 * u);
    add.ring(circle(ox, oy, r, 72), 3.0, origin, t0, 0.0);
    add.ring(circle(ox, oy, r - 6.0 * u, 72), 1.3, origin, t0, 0.06);
    add.ring(foil(ox, oy, r - 11.0 * u, 4, 0.0), 2.2, origin, t0, 0.2);
    add.ring(foil(ox, oy, r - 30.0 * u, 4, PI / 4.0), 1.2, origin, t0, 0.35);
    add.ring(circle(ox, oy, 9.0 * u, 20), 2.0, origin, t0, 0.45);
    for k in 0..8 {
        let turn = f64::from(k) * PI / 4.0;
        let spoke = vec![[ox + 9.0 * u * turn.cos(), oy + 9.0 * u * turn.sin()], [ox + 19.0 * u * turn.cos(), oy + 19.0 * u * turn.sin()]];
        add.line(spoke, 1.1, origin, t0, 0.5);
    }
    for (x, y, rr, turn) in [(250.0, 48.0, 22.0, -PI / 2.0), (48.0, 250.0, 22.0, PI), (180.0, 130.0, 13.0, PI / 4.0)] {
        add.ring(circle(x * u, y * u, rr * u, 40), 2.2, origin, t0, 0.0);
        add.ring(foil(x * u, y * u, (rr - 5.0) * u, 3, turn), 1.4, origin, t0, 0.15);
    }
    let scrolls = [
        ([ox + r * (-0.15f64).cos(), oy + r * (-0.15f64).sin()], -0.05, 58.0, 5.0),
        ([ox + r * 1.72f64.cos(), oy + r * 1.72f64.sin()], 1.62, 58.0, -5.0),
        ([228.0 * u, 48.0 * u], PI + 0.1, 36.0, -4.6),
        ([48.0 * u, 228.0 * u], -PI / 2.0 - 0.1, 36.0, 4.6),
    ];
    for (start, heading, length, turn) in scrolls {
        let curl = scroll(start, heading, length * u, turn);
        let end = curl[curl.len() - 1];
        add.line(curl, 1.5, origin, t0, 0.15);
        add.ring(circle(end[0], end[1], 2.2 * u, 10), 1.6, origin, t0, 0.15 + length * u / (DRAW * u));
    }
}
