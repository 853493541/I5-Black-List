//! Lines as a hand draws them, as fluffy.py has them: rounded routes, points evened out along a
//! line, a hand's tremor, pen strokes that swell and taper, and outlines gone over in ink.

use std::f64::consts::PI;

use super::pixels::Shape;
use crate::draw::Pt;
use crate::pyrand::PyRandom;

/// _fillet: a line through corners (x, y, r), each corner rounded off r along its sides.
pub fn fillet(corners: &[[f64; 3]]) -> Vec<Pt> {
    let pt = |i: usize| [corners[i][0], corners[i][1]];
    let mut out = vec![pt(0)];
    for i in 1..corners.len() - 1 {
        let (a, b, c) = (pt(i - 1), pt(i), pt(i + 1));
        let (ab, cb) = (dist(a, b), dist(c, b));
        let r = corners[i][2].min(ab / 2.0).min(cb / 2.0);
        let p0 = [b[0] + (a[0] - b[0]) / ab.max(1e-9) * r, b[1] + (a[1] - b[1]) / ab.max(1e-9) * r];
        let p1 = [b[0] + (c[0] - b[0]) / cb.max(1e-9) * r, b[1] + (c[1] - b[1]) / cb.max(1e-9) * r];
        for j in 0..14 {
            let k = f64::from(j) / 13.0;
            out.push(std::array::from_fn(|d| (1.0 - k) * (1.0 - k) * p0[d] + 2.0 * (1.0 - k) * k * b[d] + k * k * p1[d]));
        }
    }
    out.push(pt(corners.len() - 1));
    out
}

pub fn dist(a: Pt, b: Pt) -> f64 {
    (b[0] - a[0]).hypot(b[1] - a[1])
}

/// np.linspace(a, b, n).
pub fn linspace(a: f64, b: f64, n: usize) -> Vec<f64> {
    let step = (b - a) / (n.max(2) - 1) as f64;
    (0..n).map(|i| if i + 1 == n { b } else { a + step * i as f64 }).collect()
}

/// np.interp(x, xs, ys) for increasing xs.
pub fn interp(x: f64, xs: &[f64], ys: &[f64]) -> f64 {
    let n = xs.len();
    if x <= xs[0] {
        return ys[0];
    }
    if x >= xs[n - 1] {
        return ys[n - 1];
    }
    let j = xs.partition_point(|&v| v <= x) - 1;
    let k = (x - xs[j]) / (xs[j + 1] - xs[j]);
    ys[j] + (ys[j + 1] - ys[j]) * k
}

/// _even: points along a line every step apart.
pub fn even(points: &[Pt], step: f64, closed: bool) -> Vec<Pt> {
    let mut pts = points.to_vec();
    if closed {
        pts.push(points[0]);
    }
    let mut kept = vec![pts[0]];
    let mut s = vec![0.0];
    for w in pts.windows(2) {
        let d = dist(w[0], w[1]);
        if d > 1e-9 {
            kept.push(w[1]);
            s.push(s[s.len() - 1] + d);
        }
    }
    let total = s[s.len() - 1];
    let at = linspace(0.0, total, 3.max((total / step) as usize + 1));
    let xs: Vec<f64> = kept.iter().map(|p| p[0]).collect();
    let ys: Vec<f64> = kept.iter().map(|p| p[1]).collect();
    let mut out: Vec<Pt> = at.iter().map(|&a| [interp(a, &s, &xs), interp(a, &s, &ys)]).collect();
    if closed {
        out.pop();
    }
    out
}

/// _along: how far along the line each point is.
pub fn along(points: &[Pt]) -> Vec<f64> {
    let mut out = vec![0.0];
    for w in points.windows(2) {
        out.push(out[out.len() - 1] + dist(w[0], w[1]));
    }
    out
}

/// _normals: each point's sideways unit, right of the way the line goes on a screen.
pub fn normals(points: &[Pt], closed: bool) -> Vec<Pt> {
    let n = points.len();
    (0..n)
        .map(|i| {
            let (a, b, half) = if closed {
                (points[(i + n - 1) % n], points[(i + 1) % n], 1.0)
            } else if i == 0 {
                (points[0], points[1], 1.0)
            } else if i == n - 1 {
                (points[n - 2], points[n - 1], 1.0)
            } else {
                (points[i - 1], points[i + 1], 0.5)
            };
            let d = [(b[0] - a[0]) * half, (b[1] - a[1]) * half];
            let len = d[0].hypot(d[1]).max(1e-9);
            [-d[1] / len, d[0] / len]
        })
        .collect()
}

/// _tremor: a hand's slow tremor along a line, s along it; round a closed line (period its length)
/// it comes back to where it began.
pub fn tremor(s: &[f64], rnd: &mut PyRandom, amp: f64, wave: f64, period: f64) -> Vec<f64> {
    let mut out = vec![0.0; s.len()];
    for (k, weight) in [(1.0, 0.6), (2.3, 0.28), (5.2, 0.12)] {
        let phase = rnd.uniform(0.0, 2.0 * PI);
        let per = if period != 0.0 { (period / (wave / k)).round_ties_even().max(1.0) / period } else { 1.0 / (wave / k) };
        for (o, &v) in out.iter_mut().zip(s) {
            *o += weight * (2.0 * PI * v * per + phase).sin();
        }
    }
    out.iter().map(|v| v * amp).collect()
}

/// _ribbon: a pen line of varying width through points, as its outline.
pub fn ribbon(points: &[Pt], widths: &[f64]) -> Shape {
    let side = normals(points, false);
    let mut poly: Vec<Pt> = points.iter().zip(&side).zip(widths).map(|((p, n), w)| [p[0] + n[0] * w / 2.0, p[1] + n[1] * w / 2.0]).collect();
    poly.extend(points.iter().zip(&side).zip(widths).rev().map(|((p, n), w)| [p[0] - n[0] * w / 2.0, p[1] - n[1] * w / 2.0]));
    vec![(1.0, poly)]
}

/// _loop: a closed pen line of varying width round points.
fn closed_loop(points: &[Pt], widths: &[f64]) -> Shape {
    let side = normals(points, true);
    let outer = points.iter().zip(&side).zip(widths).map(|((p, n), w)| [p[0] + n[0] * w / 2.0, p[1] + n[1] * w / 2.0]).collect();
    let inner = points.iter().zip(&side).zip(widths).rev().map(|((p, n), w)| [p[0] - n[0] * w / 2.0, p[1] - n[1] * w / 2.0]).collect();
    vec![(1.0, outer), (1.0, inner)]
}

/// _inked: each outline polygon gone over in ink by hand, wobbling and pressing harder here and there.
pub fn inked(polys: &[Vec<Pt>], width: f64, rnd: &mut PyRandom) -> Shape {
    let mut out = Shape::new();
    for poly in polys {
        if poly.len() < 3 {
            continue;
        }
        let points = even(poly, (width * 0.6).max(0.25), true);
        let s = along(&points);
        let period = s[s.len() - 1] + dist(points[0], points[points.len() - 1]);
        let side = normals(&points, true);
        let shake = tremor(&s, rnd, width * 0.3, width * 9.0, period);
        let moved: Vec<Pt> = points.iter().zip(&side).zip(&shake).map(|((p, n), d)| [p[0] + n[0] * d, p[1] + n[1] * d]).collect();
        let press = tremor(&s, rnd, 0.3, width * 14.0, period);
        let widths: Vec<f64> = press.iter().map(|v| width * (1.0 + v)).collect();
        out.extend(closed_loop(&moved, &widths));
    }
    out
}

/// One pen stroke: points, widths, and how far along the whole each point is.
#[derive(Clone)]
pub struct Stroke {
    pub points: Vec<Pt>,
    pub widths: Vec<f64>,
    pub at: Vec<f64>,
}

/// _stroke: wobbled sideways, its width swelling and thinning, tapering where the pen lands and lifts.
pub fn stroke(points: &[Pt], at: &[f64], width: f64, rnd: &mut PyRandom, wobble: f64, start: f64, end: f64) -> Stroke {
    let s: Vec<f64> = at.iter().map(|a| a - at[0]).collect();
    let side = normals(points, false);
    let shake = tremor(&s, rnd, wobble, 160.0, 0.0);
    let moved = points.iter().zip(&side).zip(&shake).map(|((p, n), d)| [p[0] + n[0] * d, p[1] + n[1] * d]).collect();
    let last = s[s.len() - 1];
    let press = tremor(&s, rnd, 0.32, 120.0, 0.0);
    let widths = s
        .iter()
        .zip(&press)
        .map(|(&v, &p)| {
            let taper = (v / start).clamp(0.0, 1.0).powf(0.6) * ((last - v) / end).clamp(0.0, 1.0).powf(0.6);
            width * (0.86 + p) * taper.max(0.08)
        })
        .collect();
    Stroke { points: moved, widths, at: at.to_vec() }
}

/// _Line: a hand-drawn line of one or more strokes, drawn as far along as wanted.
pub struct Line {
    pub strokes: Vec<Stroke>,
    pub color: &'static str,
    pub tip: f64,
    pub length: f64,
}

impl Line {
    pub fn new(strokes: Vec<Stroke>, color: &'static str, tip: f64) -> Self {
        let length = strokes.iter().map(|s| s.at[s.at.len() - 1]).fold(f64::MIN, f64::max);
        Self { strokes, color, tip, length }
    }

    /// The outline drawn up to `reach`, the pen's round tip as it goes.
    pub fn shape(&self, reach: f64) -> Shape {
        let mut out = Shape::new();
        for s in &self.strokes {
            if reach >= s.at[s.at.len() - 1] {
                out.extend(ribbon(&s.points, &s.widths));
                continue;
            }
            let n = s.at.partition_point(|&a| a < reach);
            if n >= 3 {
                let widths: Vec<f64> = (0..n).map(|i| s.widths[i] * ((reach - s.at[i]) / self.tip).clamp(0.45, 1.0)).collect();
                out.extend(ribbon(&s.points[..n], &widths));
            }
        }
        out
    }

    /// Where the pen is, while it draws.
    pub fn head(&self, reach: f64) -> Option<Pt> {
        let s = self.strokes.iter().find(|s| s.at[0] <= reach && reach < s.at[s.at.len() - 1])?;
        Some(s.points[(s.at.len() - 1).min(s.at.partition_point(|&a| a < reach))])
    }
}

/// _glide: a hand drawing a long line, setting off and slowing at the end gently.
pub fn glide(k: f64) -> f64 {
    let k = k.clamp(0.0, 1.0);
    k * k * (3.0 - 2.0 * k)
}

/// _doodle: a loopy doodle from a to b, as a pen trails between two stars.
pub fn doodle(a: Pt, b: Pt, loops: u32, size: f64, rnd: &mut PyRandom, u: f64) -> Line {
    let end = 2.0 * PI * f64::from(loops) + PI * 0.5;
    let theta = linspace(0.0, end, 160 * loops as usize);
    let last = theta[theta.len() - 1];
    let span = dist(a, b);
    let turn = (b[1] - a[1]).atan2(b[0] - a[0]);
    let (c, s) = (turn.cos(), turn.sin());
    let points: Vec<Pt> = theta
        .iter()
        .map(|&th| {
            let fwd = th / last * span - size * 2.4 * th.sin();
            let across = size * 1.3 * (th.cos() - 1.0) - size * 0.8 * (th / last * PI).sin();
            [a[0] + fwd * c - across * s, a[1] + fwd * s + across * c]
        })
        .collect();
    let points = even(&points, 1.6 * u, false);
    Line::new(vec![stroke(&points, &along(&points), 2.3 * u, rnd, 0.5 * u, 8.0 * u, 18.0 * u)], super::CHALK, 3.0 * u)
}
