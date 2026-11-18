//! What light.mask does with QPainter: paths filled or stroked, antialiased, white on black, into a
//! one-channel map. Coverage is exact across each row and sampled on 16 lines down each pixel; each fill
//! is laid over what is there (Qt's source-over in gray).

use super::img::Map;

pub type Pt = [f64; 2];
const SUB: usize = 16;

/// Closed polygons and their fill rule (Qt's default for a path is odd-even).
#[derive(Clone, Default)]
pub struct Shape {
    pub polys: Vec<Vec<Pt>>,
    pub winding: bool,
}

#[derive(Clone, Copy, PartialEq)]
pub enum Cap {
    Flat,
    Square,
    Round,
}

pub fn quad(p0: Pt, p1: Pt, p2: Pt, n: usize) -> Vec<Pt> {
    (0..=n)
        .map(|i| {
            let t = i as f64 / n as f64;
            let m = 1.0 - t;
            [m * m * p0[0] + 2.0 * m * t * p1[0] + t * t * p2[0], m * m * p0[1] + 2.0 * m * t * p1[1] + t * t * p2[1]]
        })
        .collect()
}

pub fn cubic(p0: Pt, p1: Pt, p2: Pt, p3: Pt, n: usize) -> Vec<Pt> {
    (0..=n).map(|i| bez(p0, p1, p2, p3, i as f64 / n as f64)).collect()
}

pub fn bez(p0: Pt, p1: Pt, p2: Pt, p3: Pt, t: f64) -> Pt {
    let m = 1.0 - t;
    let (a, b, c, d) = (m * m * m, 3.0 * m * m * t, 3.0 * m * t * t, t * t * t);
    [a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]]
}

pub fn ellipse(cx: f64, cy: f64, rx: f64, ry: f64, n: usize) -> Vec<Pt> {
    (0..n)
        .map(|i| {
            let a = std::f64::consts::TAU * i as f64 / n as f64;
            [cx + rx * a.cos(), cy + ry * a.sin()]
        })
        .collect()
}

pub fn rect(x0: f64, y0: f64, x1: f64, y1: f64) -> Vec<Pt> {
    vec![[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
}

/// QPainterPath.addRoundedRect: corners of radius r (absolute).
pub fn rounded_rect(x0: f64, y0: f64, x1: f64, y1: f64, r: f64) -> Vec<Pt> {
    let r = r.min((x1 - x0) / 2.0).min((y1 - y0) / 2.0);
    let mut out = Vec::new();
    for (cx, cy, a0) in [(x1 - r, y0 + r, -90.0f64), (x1 - r, y1 - r, 0.0), (x0 + r, y1 - r, 90.0), (x0 + r, y0 + r, 180.0)] {
        for k in 0..=8 {
            let a = (a0 + 90.0 * f64::from(k) / 8.0).to_radians();
            out.push([cx + r * a.cos(), cy + r * a.sin()]);
        }
    }
    out
}

fn area(poly: &[Pt]) -> f64 {
    let mut s = 0.0;
    for i in 0..poly.len() {
        let (a, b) = (poly[i], poly[(i + 1) % poly.len()]);
        s += a[0] * b[1] - b[0] * a[1];
    }
    s
}

fn positive(mut poly: Vec<Pt>) -> Vec<Pt> {
    if area(&poly) < 0.0 {
        poly.reverse();
    }
    poly
}

impl Shape {
    pub fn odd(polys: Vec<Vec<Pt>>) -> Self {
        Self { polys, winding: false }
    }

    pub fn winding(polys: Vec<Vec<Pt>>) -> Self {
        Self { polys, winding: true }
    }

    pub fn map(&self, f: impl Fn(Pt) -> Pt) -> Self {
        Self { polys: self.polys.iter().map(|p| p.iter().map(|&q| f(q)).collect()).collect(), winding: self.winding }
    }

    /// Moved by (dx, dy) and scaled by s about the origin after: Qt's translate then scale as a painter sees it.
    pub fn placed(&self, dx: f64, dy: f64, s: f64) -> Self {
        self.map(|[x, y]| [x * s + dx, y * s + dy])
    }

    pub fn add(&mut self, other: Shape) {
        self.polys.extend(other.polys);
    }
}

/// A pen's outline along each line: segments, round joins, and the caps; every piece wound the same
/// way, filled with the winding rule, so they make one union.
pub fn stroke(lines: &[Vec<Pt>], width: f64, cap: Cap) -> Shape {
    let hw = width / 2.0;
    let segs = if hw > 20.0 { 48 } else { 20 };
    let mut polys = Vec::new();
    for line in lines {
        let pts: Vec<Pt> = line.iter().copied().fold(Vec::new(), |mut v: Vec<Pt>, p| {
            if v.last().is_none_or(|q| (q[0] - p[0]).abs() + (q[1] - p[1]).abs() > 1e-9) {
                v.push(p);
            }
            v
        });
        if pts.len() < 2 {
            if cap == Cap::Round && !pts.is_empty() {
                polys.push(ellipse(pts[0][0], pts[0][1], hw, hw, segs));
            }
            continue;
        }
        let last = pts.len() - 2;
        for i in 0..=last {
            let (mut a, mut b) = (pts[i], pts[i + 1]);
            let (dx, dy) = (b[0] - a[0], b[1] - a[1]);
            let len = dx.hypot(dy);
            let (ux, uy) = (dx / len, dy / len);
            if cap == Cap::Square {
                if i == 0 {
                    a = [a[0] - ux * hw, a[1] - uy * hw];
                }
                if i == last {
                    b = [b[0] + ux * hw, b[1] + uy * hw];
                }
            }
            let (nx, ny) = (-uy * hw, ux * hw);
            polys.push(positive(vec![[a[0] + nx, a[1] + ny], [b[0] + nx, b[1] + ny], [b[0] - nx, b[1] - ny], [a[0] - nx, a[1] - ny]]));
            if i == 0 && cap == Cap::Round {
                polys.push(ellipse(pts[0][0], pts[0][1], hw, hw, segs));
            }
            if i > 0 {
                // Qt's round join: the pie between the two segments' edges on the outer side of the turn.
                let (p0, p1) = (pts[i - 1], pts[i]);
                let (ex, ey) = (p1[0] - p0[0], p1[1] - p0[1]);
                let el = ex.hypot(ey);
                let (a0, a1) = ((ex / el).atan2(-ey / el), ux.atan2(-uy));
                let turn = ex * uy - ey * ux;
                let (from, mut sweep) = if turn > 0.0 { (a0 + std::f64::consts::PI, a1 - a0) } else { (a0, a1 - a0) };
                sweep = (sweep + std::f64::consts::PI).rem_euclid(std::f64::consts::TAU) - std::f64::consts::PI;
                if sweep.abs() > 1e-6 {
                    let n = ((sweep.abs() / std::f64::consts::TAU * segs as f64).ceil() as usize).max(1);
                    let c = pts[i];
                    let mut pie = vec![c];
                    pie.extend((0..=n).map(|k| {
                        let a = from + sweep * k as f64 / n as f64;
                        [c[0] + hw * a.cos(), c[1] + hw * a.sin()]
                    }));
                    polys.push(positive(pie));
                }
            }
        }
        if cap == Cap::Round {
            let e = pts[pts.len() - 1];
            polys.push(ellipse(e[0], e[1], hw, hw, segs));
        }
    }
    Shape::winding(polys)
}

/// How much of each pixel the shape covers, 0..1, over the part of a w x h grid it can reach:
/// (left, top, that box's coverage).
pub fn coverage(shape: &Shape, w: usize, h: usize) -> (usize, usize, Map) {
    // Edges (x at top, top y, bottom y, dx per y, direction).
    let mut edges: Vec<(f64, f64, f64, f64, i32)> = Vec::new();
    let (mut x_min, mut x_max) = (f64::MAX, f64::MIN);
    for poly in &shape.polys {
        for i in 0..poly.len() {
            let (a, b) = (poly[i], poly[(i + 1) % poly.len()]);
            x_min = x_min.min(a[0]);
            x_max = x_max.max(a[0]);
            if a[1] == b[1] {
                continue;
            }
            let (top, bot, dir) = if a[1] < b[1] { (a, b, 1) } else { (b, a, -1) };
            edges.push((top[0], top[1], bot[1], (bot[0] - top[0]) / (bot[1] - top[1]), dir));
        }
    }
    let x_lo = x_min.max(0.0).floor() as usize;
    let x_hi = ((x_max.max(0.0).ceil() as usize) + 1).min(w);
    if edges.is_empty() || x_lo >= x_hi {
        return (0, 0, Map::new(0, 0, 0.0));
    }
    edges.sort_by(|a, b| a.1.total_cmp(&b.1));
    let y_lo = (edges[0].1.max(0.0).floor() as usize).min(h);
    let y_hi = (edges.iter().map(|e| e.2).fold(f64::MIN, f64::max).ceil().max(0.0) as usize).min(h);
    let bw = x_hi - x_lo;
    let mut out = Map::new(bw, y_hi.saturating_sub(y_lo), 0.0);
    let (mut next, mut active) = (0usize, Vec::<usize>::new());
    let mut cross: Vec<(f64, i32)> = Vec::new();
    let mut direct = vec![0f32; bw + 2];
    let mut diff = vec![0f32; bw + 2];
    let wt = 1.0 / SUB as f32;
    let (left, right) = (x_lo as f64, x_hi as f64);
    for y in y_lo..y_hi {
        direct.iter_mut().for_each(|v| *v = 0.0);
        diff.iter_mut().for_each(|v| *v = 0.0);
        let mut any = false;
        for s in 0..SUB {
            let sy = y as f64 + (s as f64 + 0.5) / SUB as f64;
            while next < edges.len() && edges[next].1 <= sy {
                active.push(next);
                next += 1;
            }
            active.retain(|&e| edges[e].2 > sy);
            cross.clear();
            for &e in &active {
                let (x0, y0, _, k, d) = edges[e];
                cross.push((x0 + (sy - y0) * k, d));
            }
            if cross.is_empty() {
                continue;
            }
            cross.sort_by(|a, b| a.0.total_cmp(&b.0));
            let mut wind = 0;
            for j in 0..cross.len() - 1 {
                wind += cross[j].1;
                let inside = if shape.winding { wind != 0 } else { wind % 2 != 0 };
                if !inside {
                    continue;
                }
                let (xa, xb) = (cross[j].0.clamp(left, right) - left, cross[j + 1].0.clamp(left, right) - left);
                if xb <= xa {
                    continue;
                }
                any = true;
                let (ia, ib) = (xa.floor() as usize, xb.floor() as usize);
                if ia == ib {
                    direct[ia] += (xb - xa) as f32 * wt;
                } else {
                    direct[ia] += (ia as f64 + 1.0 - xa) as f32 * wt;
                    diff[ia + 1] += wt;
                    diff[ib] -= wt;
                    direct[ib] += (xb - ib as f64) as f32 * wt;
                }
            }
        }
        if any {
            let mut run = 0f32;
            let row = (y - y_lo) * bw;
            for x in 0..bw {
                run += diff[x];
                out.v[row + x] = (run + direct[x]).clamp(0.0, 1.0);
            }
        }
    }
    (x_lo, y_lo, out)
}

/// A gray mask (light.mask): fills laid one over another in gray levels, kept to 8 bits as Qt keeps it.
pub struct Canvas {
    pub m: Map,
}

impl Canvas {
    pub fn new(w: usize, h: usize) -> Self {
        Self { m: Map::new(w, h, 0.0) }
    }

    pub fn fill(&mut self, shape: &Shape, gray: f32) {
        let (x0, y0, c) = coverage(shape, self.m.w, self.m.h);
        for y in 0..c.h {
            let row = (y0 + y) * self.m.w + x0;
            for x in 0..c.w {
                let a = c.v[y * c.w + x];
                if a > 0.0 {
                    let d = &mut self.m.v[row + x];
                    *d = gray * a + *d * (1.0 - a);
                }
            }
        }
    }

    pub fn stroke(&mut self, lines: &[Vec<Pt>], width: f64, cap: Cap, gray: f32) {
        self.fill(&stroke(lines, width, cap), gray);
    }

    pub fn done(self) -> Map {
        self.m.map(|v| (v * 255.0).round() / 255.0)
    }
}

/// One shape's mask.
pub fn filled(shape: &Shape, w: usize, h: usize) -> Map {
    let mut c = Canvas::new(w, h);
    c.fill(shape, 1.0);
    c.done()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn covers_a_square_and_a_disc() {
        let m = filled(&Shape::odd(vec![rect(2.5, 2.0, 6.5, 6.0)]), 10, 10);
        assert!((m.at(2, 3) - 0.5).abs() < 0.01 && (m.at(4, 3) - 1.0).abs() < 1e-6 && m.at(8, 3) == 0.0);
        let disc = filled(&Shape::odd(vec![ellipse(50.0, 50.0, 20.0, 20.0, 256)]), 100, 100);
        let sum: f32 = disc.v.iter().sum();
        assert!((f64::from(sum) - std::f64::consts::PI * 400.0).abs() < 3.0, "{sum}");
        let line = filled(&stroke(&[vec![[10.0, 10.0], [50.0, 10.0], [50.0, 50.0]]], 4.0, Cap::Round), 64, 64);
        assert!((line.at(50, 10) - 1.0).abs() < 1e-6 && (line.at(30, 12) - 0.0).abs() < 1e-6);
    }
}
