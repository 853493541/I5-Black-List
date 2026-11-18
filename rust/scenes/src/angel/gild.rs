//! The gold tracery's pictures, per area (angel._gilt and _gild), and when each of their pixels is
//! drawn: the Python scene copies the finished picture in along each line as its pen passes
//! (_Gilding._lay); here every pixel keeps the time the pen first comes within the copying stroke of
//! it, and the shader shows the picture where that time has passed.

use super::lines::{point_at, Line, Rect, DRAW};
use super::px::{blur, glow, metal, picture, pyround, rgb, shift, Grid, Pic};

pub struct Area {
    pub rect: Rect,
    pub gold: Pic,
    pub bloom: Pic,
    /// When each pixel of gold and of bloom is reached; f32::MAX for never.
    pub gold_t: Vec<f32>,
    pub bloom_t: Vec<f32>,
    /// Picture pixels to the point, for gold; bloom is at half.
    pub scale: f64,
}

/// Seconds per picture pixel as a pen runs: the shader fades the pen's edge over one.
pub fn pen_speed(u: f64, at: f64) -> f64 {
    DRAW * u * at
}

fn size(rect: Rect, at: f64) -> (usize, usize) {
    ((rect[2] * at).ceil().max(1.0) as usize, (rect[3] * at).ceil().max(1.0) as usize)
}

fn seg_dist(p: [f64; 2], a: [f64; 2], b: [f64; 2]) -> f64 {
    let (dx, dy) = (b[0] - a[0], b[1] - a[1]);
    let len2 = dx * dx + dy * dy;
    let k = if len2 > 0.0 { (((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2).clamp(0.0, 1.0) } else { 0.0 };
    (p[0] - a[0] - dx * k).hypot(p[1] - a[1] - dy * k)
}

/// Pixels of a w x h picture within `pad` of the points' box, as (x0, y0, x1, y1).
fn span(points: &[[f64; 2]], pad: f64, w: usize, h: usize) -> Option<(usize, usize, usize, usize)> {
    let (mut x0, mut y0, mut x1, mut y1) = (f64::MAX, f64::MAX, f64::MIN, f64::MIN);
    for p in points {
        (x0, y0, x1, y1) = (x0.min(p[0]), y0.min(p[1]), x1.max(p[0]), y1.max(p[1]));
    }
    let lo = |v: f64| (v - pad).floor().max(0.0) as usize;
    let (ax, ay) = (lo(x0), lo(y0));
    let (bx, by) = (((x1 + pad).ceil() as i64).min(w as i64 - 1), ((y1 + pad).ceil() as i64).min(h as i64 - 1));
    (bx >= ax as i64 && by >= ay as i64).then_some((ax, ay, bx as usize, by as usize))
}

/// What the lines paint in white on black over rect, at `at` pixels to the point (light.mask).
fn mask(rect: Rect, lines: &[&Line], at: f64, u: f64) -> Grid {
    let (w, h) = size(rect, at);
    let mut acc = Grid::new(w, h);
    let to = |p: [f64; 2]| [(p[0] - rect[0]) * at, (p[1] - rect[1]) * at];
    let lay = |acc: &mut Grid, pts: &[[f64; 2]], half: f64, cover: &dyn Fn(f64) -> f64| {
        if let Some((x0, y0, x1, y1)) = span(pts, half + 1.0, w, h) {
            for y in y0..=y1 {
                for x in x0..=x1 {
                    let p = [x as f64 + 0.5, y as f64 + 0.5];
                    let d = if pts.len() == 1 { seg_dist(p, pts[0], pts[0]) } else { pts.windows(2).map(|s| seg_dist(p, s[0], s[1])).fold(f64::MAX, f64::min) };
                    let c = cover(d) as f32;
                    let v = &mut acc.v[y * w + x];
                    *v += c * (1.0 - *v);
                }
            }
        }
    };
    for line in lines {
        let half = line.width * u * at / 2.0;
        let cover = move |d: f64| if half < 0.5 { (1.0 - d).clamp(0.0, 1.0) * half * 2.0 } else { (half + 0.5 - d).clamp(0.0, 1.0) };
        let disc = move |d: f64| if half < 0.7 { (1.0 - d).clamp(0.0, 1.0) * (3.0 * half * half).min(1.0) } else { (half + 0.5 - d).clamp(0.0, 1.0) };
        if line.beads > 0.0 {
            let total = line.run[line.run.len() - 1];
            for k in 0..=(total / (line.beads * u)) as usize {
                let p = to(point_at(&line.points, &line.run, k as f64 * line.beads * u));
                lay(&mut acc, &[p], half, &disc);
            }
        } else {
            let pts: Vec<[f64; 2]> = line.points.iter().map(|&p| to(p)).collect();
            lay(&mut acc, &pts, half, &cover);
        }
    }
    acc.map(|v| (v * 255.0).round() / 255.0)
}

/// angel._gild: lines as raised gold wire with a soft shadow under them; px is pixels to the unit.
fn gild(cover: &Grid, px: f64) -> Pic {
    let height = blur(cover, (0.8 * px).max(0.6));
    let color = metal(&height, (2.6 * px) as f32, 1.0);
    let soft = blur(cover, (1.1 * px).max(0.6));
    let under = shift(&soft, pyround(1.2 * px).max(1), pyround(0.5 * px)).zip(cover, |s, c| s * 0.55 * (1.0 - c));
    let dark = rgb("#1e1004");
    let total = |i: usize| cover.v[i] + under.v[i];
    picture(cover.w, cover.h, |i| std::array::from_fn(|k| (color[i][k] * cover.v[i] + dark[k] * under.v[i]) / total(i).max(1e-4)), total)
}

/// When the pen first comes within `half` units of each pixel (angel._Gilding: the copying stroke).
fn times(rect: Rect, lines: &[&Line], at: f64, u: f64, half: f64) -> Vec<f32> {
    let (w, h) = size(rect, at);
    let mut out = vec![f32::MAX; w * h];
    let r = half * u * at;
    for line in lines {
        let total = line.run[line.run.len() - 1].max(1e-9);
        for (i, s) in line.points.windows(2).enumerate() {
            let a = [(s[0][0] - rect[0]) * at, (s[0][1] - rect[1]) * at];
            let b = [(s[1][0] - rect[0]) * at, (s[1][1] - rect[1]) * at];
            let Some((x0, y0, x1, y1)) = span(&[a, b], r + 1.0, w, h) else { continue };
            let len = (b[0] - a[0]).hypot(b[1] - a[1]);
            let dir = if len > 0.0 { [(b[0] - a[0]) / len, (b[1] - a[1]) / len] } else { [1.0, 0.0] };
            for y in y0..=y1 {
                for x in x0..=x1 {
                    let (px, py) = (x as f64 + 0.5 - a[0], y as f64 + 0.5 - a[1]);
                    let q = px * dir[0] + py * dir[1];
                    let off = px * dir[1] - py * dir[0];
                    if off.abs() > r {
                        continue;
                    }
                    let reach = (r * r - off * off).sqrt();
                    let first = (q - reach).max(0.0);
                    if first > len.min(q + reach) {
                        continue;
                    }
                    let when = (line.start + line.span * (line.run[i] + first / at) / total) as f32;
                    let slot = &mut out[y * w + x];
                    *slot = slot.min(when);
                }
            }
        }
    }
    out
}

fn intersects(a: Rect, b: Rect) -> bool {
    a[0] < b[0] + b[2] && b[0] < a[0] + a[2] && a[1] < b[1] + b[3] && b[1] < a[1] + a[3]
}

/// One area's pictures and their times: the lines near it, the gold at `scale`, its warm light at half.
pub fn area(rect: Rect, lines: &[Line], scale: f64, u: f64) -> Area {
    let room = [rect[0] - 30.0 * u, rect[1] - 30.0 * u, rect[2] + 60.0 * u, rect[3] + 60.0 * u];
    let near: Vec<&Line> = lines
        .iter()
        .filter(|line| {
            let (mut x0, mut y0, mut x1, mut y1) = (f64::MAX, f64::MAX, f64::MIN, f64::MIN);
            for p in &line.points {
                (x0, y0, x1, y1) = (x0.min(p[0]), y0.min(p[1]), x1.max(p[0]), y1.max(p[1]));
            }
            intersects([x0 - 1.0, y0 - 1.0, x1 - x0 + 2.0, y1 - y0 + 2.0], room)
        })
        .collect();
    let gold = gild(&mask(rect, &near, scale, u), u * scale);
    let half = scale * 0.5;
    let small = mask(rect, &near, half, u);
    let px = u * half;
    let (b1, b2, b3) = (blur(&small, 2.5 * px), blur(&small, 8.0 * px), blur(&small, 20.0 * px));
    let honey = rgb("#ffd98a");
    let bloom = glow(small.w, small.h, |i| honey.map(|c| (b1.v[i] * 0.9 + b2.v[i] * 0.55 + b3.v[i] * 0.3) * c * 0.85));
    let gold_t = times(rect, &near, scale, u, 3.5);
    let bloom_t = times(rect, &near, half, u, 20.0);
    Area { rect, gold, bloom, gold_t, bloom_t, scale }
}
