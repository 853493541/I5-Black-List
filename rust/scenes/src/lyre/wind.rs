//! The wind of 竖琴清风: the current's line round the screen, the band of green air, the lit current,
//! the curls in the right corners, the strands leaving the strings, the glint, and the cecilias' stalks
//! (lyre.py's _route, _band, _border, _curls, _strand_lines, _glint, _lit_strokes, _stalks).

use super::img::{self, light_of, over, picture, relief, rgb, scale3, smooth, Color, Map, Pic, Rgb};
use super::raster::{cubic, quad, stroke, Canvas, Cap, Pt, Shape};
use super::{Geo, ANEMO, CORE, JADE, MEADOW, MINT, PINE, STILL};
use std::f64::consts::PI;

/// A ribbon: points, widths, and the gray level its body is drawn in.
pub type Line = (Vec<Pt>, Vec<f64>, Vec<f64>);

pub const LIGHT: [f32; 3] = {
    // [-0.55, -0.68, 0.85] made unit length (1.2224...).
    let n = 1.222_497_3;
    [-0.55 / n, -0.68 / n, 0.85 / n]
};

/// A picture laid on the screen at (left, top), each pixel 1 / scale points.
#[derive(Clone, Default)]
pub struct Placed {
    pub left: f64,
    pub top: f64,
    pub right: f64,
    pub bottom: f64,
    pub pic: Pic,
}

pub fn arclen(points: &[Pt]) -> Vec<f64> {
    let mut out = vec![0.0];
    for w in points.windows(2) {
        let last = out[out.len() - 1];
        out.push(last + (w[1][0] - w[0][0]).hypot(w[1][1] - w[0][1]));
    }
    out
}

/// np.interp.
pub fn interp(x: f64, xs: &[f64], ys: &[f64]) -> f64 {
    if x <= xs[0] {
        return ys[0];
    }
    let i = xs.partition_point(|&v| v <= x);
    if i >= xs.len() {
        return ys[ys.len() - 1];
    }
    let (x0, x1) = (xs[i - 1], xs[i]);
    if x1 == x0 {
        return ys[i];
    }
    ys[i - 1] + (ys[i] - ys[i - 1]) * (x - x0) / (x1 - x0)
}

pub fn resample(points: &[Pt], step: f64) -> Vec<Pt> {
    let s = arclen(points);
    let total = s[s.len() - 1];
    let n = ((total / step) as usize).max(2);
    let (xs, ys): (Vec<f64>, Vec<f64>) = points.iter().map(|p| (p[0], p[1])).unzip();
    (0..n)
        .map(|i| {
            let at = total * i as f64 / (n - 1) as f64;
            [interp(at, &s, &xs), interp(at, &s, &ys)]
        })
        .collect()
}

pub fn tangents(points: &[Pt]) -> Vec<Pt> {
    let n = points.len();
    (0..n)
        .map(|i| {
            let (a, b, k) = if i == 0 { (1, 0, 1.0) } else if i == n - 1 { (n - 1, n - 2, 1.0) } else { (i + 1, i - 1, 0.5) };
            let d = [(points[a][0] - points[b][0]) * k, (points[a][1] - points[b][1]) * k];
            let len = d[0].hypot(d[1]).max(1e-6);
            [d[0] / len, d[1] / len]
        })
        .collect()
}

/// Unit normals to the right of travel.
pub fn normals(points: &[Pt]) -> Vec<Pt> {
    tangents(points).into_iter().map(|t| [-t[1], t[0]]).collect()
}

/// The current's line, clockwise from just right of the top-left corner, back round to it.
pub fn route(width: f64, height: f64, inset: f64, r: f64) -> Vec<Pt> {
    let (i, w, h) = (inset, width, height);
    let mut pts = Vec::new();
    let line = |pts: &mut Vec<Pt>, a: Pt, b: Pt| {
        for k in 0..200 {
            let k = f64::from(k) / 200.0;
            pts.push([a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k]);
        }
    };
    let arc = |pts: &mut Vec<Pt>, cx: f64, cy: f64, a0: f64| {
        for k in 0..30 {
            let a = (a0 + 90.0 * f64::from(k) / 30.0).to_radians();
            pts.push([cx + r * a.cos(), cy + r * a.sin()]);
        }
    };
    line(&mut pts, [i + r, i], [w - i - r, i]);
    arc(&mut pts, w - i - r, i + r, -90.0);
    line(&mut pts, [w - i, i + r], [w - i, h - i - r]);
    arc(&mut pts, w - i - r, h - i - r, 0.0);
    line(&mut pts, [w - i - r, h - i], [i + r, h - i]);
    arc(&mut pts, i + r, h - i - r, 90.0);
    line(&mut pts, [i, h - i - r], [i, i + r]);
    arc(&mut pts, i + r, i + r, 180.0);
    pts.push([i + r, i]);
    resample(&pts, 2.0)
}

pub fn bezier(p0: Pt, p1: Pt, p2: Pt, p3: Pt, n: usize) -> Vec<Pt> {
    cubic(p0, p1, p2, p3, n - 1)
}

/// A spiral carrying on from end along tangent, turning to side.
pub fn curl(end: Pt, tangent: Pt, r0: f64, turns: f64, side: f64, shrink: f64) -> Vec<Pt> {
    let perp = [-tangent[1] * side, tangent[0] * side];
    let c = [end[0] + perp[0] * r0, end[1] + perp[1] * r0];
    let a0 = (end[1] - c[1]).atan2(end[0] - c[0]);
    let inc = [-a0.sin(), a0.cos()];
    let sign = if inc[0] * tangent[0] + inc[1] * tangent[1] > 0.0 { 1.0 } else { -1.0 };
    let n = (120.0 * turns) as usize + 2;
    let last = 2.0 * PI * turns;
    (0..n)
        .map(|i| {
            let th = last * i as f64 / (n - 1) as f64;
            let r = r0 * (1.0 - shrink * th / last);
            [c[0] + r * (a0 + sign * th).cos(), c[1] + r * (a0 + sign * th).sin()]
        })
        .collect()
}

/// A line carrying on into a curl (the curl's first point left out).
pub fn with_curl(mut line: Vec<Pt>, r0: f64, turns: f64, side: f64, shrink: f64) -> Vec<Pt> {
    let t = tangents(&line);
    let c = curl(line[line.len() - 1], t[t.len() - 1], r0, turns, side, shrink);
    line.extend_from_slice(&c[1..]);
    line
}

pub fn ribbon(points: &[Pt], widths: &[f64]) -> Vec<Pt> {
    let n = normals(points);
    let mut edge: Vec<Pt> = points.iter().zip(&n).zip(widths).map(|((p, q), w)| [p[0] + q[0] * w / 2.0, p[1] + q[1] * w / 2.0]).collect();
    edge.extend(points.iter().zip(&n).zip(widths).rev().map(|((p, q), w)| [p[0] - q[0] * w / 2.0, p[1] - q[1] * w / 2.0]));
    edge
}

/// _lit_strokes: ribbons over the box (left, top, w, h pixels at scale), lit from the upper left.
pub fn lit_strokes(lines: &[Line], left: f64, top: f64, w: usize, h: usize, scale: f64, d: f64) -> (Color, Map) {
    let draw = |core: bool| {
        let mut c = Canvas::new(w, h);
        for (points, widths, level) in lines {
            let mut i = 0;
            while i + 1 < points.len() {
                let j = points.len().min(i + 18);
                let mut wide: Vec<f64> = widths[i..j].iter().map(|v| v * if core { 0.26 } else { 1.0 }).collect();
                if core {
                    for (k, v) in wide.iter_mut().enumerate() {
                        *v = if widths[i + k] > 1.2 * d / scale { v.max(0.9 * d / scale) } else { *v * 0.6 };
                    }
                }
                if wide.iter().copied().fold(f64::MIN, f64::max) >= 0.15 * d / scale {
                    let v = if core { 1.0 } else { level[i..j].iter().sum::<f64>() / (j - i) as f64 };
                    let poly = ribbon(&points[i..j], &wide);
                    c.fill(&Shape::odd(vec![poly]).map(|[x, y]| [(x - left) * scale, (y - top) * scale]), v as f32);
                }
                i += 16;
            }
        }
        c.done()
    };
    let (body, core) = (draw(false), draw(true));
    let solid = body.map(|v| (v * 3.0).clamp(0.0, 1.0));
    let shift = ((2.0 * d).round_ties_even() as i64).max(1);
    let shadow = solid.blur(2.2 * d).roll(shift, shift);
    let mut color = Color::new(w, h, [0.0; 3]);
    let mut alpha = Map::new(w, h, 0.0);
    over(&mut color, &mut alpha, |_| rgb(PINE), &shadow.map(|v| v * 0.55));
    let (b4, b12) = (body.blur(4.0 * d), body.blur(12.0 * d));
    let anemo = rgb(ANEMO);
    let (c, a) = light_of(w, h, |i| scale3(anemo, (b4.v[i] * 0.55 + b12.v[i] * 0.35) * 0.85));
    over(&mut color, &mut alpha, |i| c.v[i], &a);
    let (diffuse, _) = relief(&solid.blur(1.1 * d), (3.0 * d) as f32, LIGHT);
    let mint = rgb(MINT);
    let body_c = |i: usize| {
        let lit = (0.55 + 0.6 * diffuse.v[i]).clamp(0.0, 1.2);
        let b = body.v[i];
        scale3(mint, lit * (0.82 + 0.25 * b) * (1.0 - 0.35 * (1.0 - b)))
    };
    over(&mut color, &mut alpha, body_c, &solid.map(|v| v * 0.92));
    let glow = core.blur(0.6 * d);
    let core_c = rgb(CORE);
    let (c, a) = light_of(w, h, |i| scale3(core_c, glow.v[i] * 1.15));
    over(&mut color, &mut alpha, |i| c.v[i], &a);
    (color, alpha)
}

/// _strokes_image: the ribbons lit, on a box round them.
pub fn strokes_image(lines: &[Line], scale: f64, d: f64) -> Placed {
    let room = 34.0 * d / scale;
    let all = lines.iter().flat_map(|l| l.0.iter());
    let (mut x0, mut y0, mut x1, mut y1) = (f64::MAX, f64::MAX, f64::MIN, f64::MIN);
    for p in all {
        x0 = x0.min(p[0]);
        y0 = y0.min(p[1]);
        x1 = x1.max(p[0]);
        y1 = y1.max(p[1]);
    }
    let (left, top, rw, rh) = (x0 - room, y0 - room, x1 - x0 + 2.0 * room, y1 - y0 + 2.0 * room);
    let (w, h) = (((rw * scale).ceil() as usize).max(1), ((rh * scale).ceil() as usize).max(1));
    let (c, a) = lit_strokes(lines, left, top, w, h, scale, d);
    Placed { left, top, right: left + rw, bottom: top + rh, pic: picture(&c, &a) }
}

/// _band: the green air from every edge inward, a meadow glow behind the lyre (scale 1 pixel a point).
#[allow(clippy::needless_range_loop)]
pub fn band(g: &Geo, lyre: Pt, scale: f64) -> Placed {
    let (width, height, u) = (g.width, g.height, g.u);
    let (w, h) = ((width * scale).ceil() as usize, (height * scale).ceil() as usize);
    let d = u * scale;
    let (wf, hf, uf, sf) = (width as f32, height as f32, u as f32, scale as f32);
    let across_n = img::noise(w / 12 + 3, h, 4.0 * d, 3, 21);
    let across = Map::from_fn(w, h, |x, y| across_n.at(x as usize / 12, y as usize)).blur(2.0 * d);
    let down_n = img::noise(w, h / 12 + 3, 4.0 * d, 3, 22);
    let down = Map::from_fn(w, h, |x, y| down_n.at(x as usize, y as usize / 12)).blur(2.0 * d);
    let horizontal = Map::from_fn(w, h, |x, y| {
        let (xs, ys) = (x / sf, y / sf);
        f32::from(u8::from(ys.min(hf - ys) / 1.6 < xs.min(wf - xs)))
    })
    .blur(30.0 * d);
    let clouds = img::noise(w, h, 140.0 * d, 4, 23);
    let fine = super::npr::Pcg64::new(5).f32s(w * h);
    let stops: [(f32, &str); 5] = [(0.0, PINE), (0.16, "#14573f"), (0.38, JADE), (0.72, ANEMO), (1.0, ANEMO)];
    let (meadow, pale) = (rgb(MEADOW), rgb("#bff5dc"));
    let mut color = Color::new(w, h, [0.0; 3]);
    let mut alpha = Map::new(w, h, 0.0);
    for i in 0..w * h {
        let (x, y) = img::xy_of(w, i);
        let (xs, ys) = (x / sf, y / sf);
        let title = (-((xs - wf * 890.0 / 1635.0) / (230.0 * uf)).powi(4)).exp();
        let sides = [(xs, 190.0, 1.0), (wf - xs, 110.0, 1.0), (ys, 210.0 - 70.0 * title, 1.0 - 0.3 * title), (hf - ys, 120.0, 1.0)];
        let (mut keep, mut depth) = (1f32, 9f32);
        for (dist, reach, strength) in sides {
            let reach = reach * uf;
            let a = 1.0 - smooth(0.0, 1.0, (dist - 22.0 * uf) / (reach - 22.0 * uf));
            keep *= 1.0 - 0.84 * a.powf(1.25) * strength;
            depth = depth.min(dist / reach);
        }
        let streak = across.v[i] * horizontal.v[i] + down.v[i] * (1.0 - horizontal.v[i]);
        let mut a = (1.0 - keep) * (0.78 + 0.45 * (streak - 0.5) + 0.3 * (clouds.v[i] - 0.5));
        let mut tone = 1.0 + 0.22 * (streak - 0.5) + 0.06 * (fine[i] - 0.5);
        tone *= 1.08 - 0.16 * ((xs / wf) * 0.6 + (ys / hf) * 0.4).clamp(0.0, 1.0);
        let c = scale3(img::ramp(&stops, depth), tone);
        let gl = (1.0 - smooth(0.0, 270.0 * uf, (xs - lyre[0] as f32).hypot(ys - lyre[1] as f32))).powf(1.6);
        let c: Rgb = [0, 1, 2].map(|k| c[k] * (1.0 - 0.6 * gl) + meadow[k] * 0.6 * gl + pale[k] * 0.18 * gl.powi(3));
        a = a.max(0.8 * gl).clamp(0.0, 0.9);
        color.v[i] = c;
        alpha.v[i] = a;
    }
    Placed { left: 0.0, top: 0.0, right: w as f64 / scale, bottom: h as f64 / scale, pic: picture(&color, &alpha) }
}

/// _border: the current round the edge as at the still, worked out in four strips, put together.
pub fn border(g: &Geo, route: &[Pt], run: &[f64], nrm: &[Pt], scale: f64) -> Placed {
    let u = g.u;
    let d = u * scale;
    let phase = (STILL - 1.3) * 2.2;
    let line: Vec<Pt> =
        route.iter().zip(nrm).zip(run).map(|((p, n), s)| {
            let k = 2.0 * u * (2.0 * PI * s / (360.0 * u) - phase * 0.8 + 0.7).sin();
            [p[0] + n[0] * k, p[1] + n[1] * k]
        }).collect();
    let wide: Vec<f64> = run.iter().map(|s| (3.9 + (2.0 * PI * s / (420.0 * u) - phase).sin() + 0.3 * (2.0 * PI * s / (170.0 * u) + 1.3).sin()) * u).collect();
    let level: Vec<f64> = run.iter().map(|s| 0.72 + 0.28 * (0.5 + 0.5 * (2.0 * PI * s / (520.0 * u) - phase * 1.2).sin())).collect();
    let braid: Vec<Pt> = route.iter().zip(nrm).zip(run).map(|((p, n), s)| {
        let k = (7.0 + 3.5 * (2.0 * PI * s / (240.0 * u) - phase * 1.3).sin()) * u;
        [p[0] + n[0] * k, p[1] + n[1] * k]
    }).collect();
    let thin: Vec<f64> = run.iter().map(|s| 1.6 * u * (2.0 * PI * s / (760.0 * u) - phase * 0.5 + 1.0).sin().clamp(0.0, 1.0).powf(1.5)).collect();
    let mut lines: Vec<Line> = vec![(line.clone(), wide, level), (braid, thin, vec![0.6; route.len()])];
    let tang = tangents(route);
    let peels = [((428.0, 14.0, false), 22.0), ((1298.0, 14.0, false), 20.0), ((1621.0, 325.0, true), 17.0), ((1621.0, 565.0, true), 17.0),
                 ((1243.0, 834.0, false), 20.0), ((293.0, 834.0, false), 22.0), ((14.0, 489.0, true), 18.0), ((14.0, 189.0, true), 18.0)];
    for ((x, y, side), r) in peels {
        let p = g.at(x, y, side);
        let i = (0..route.len()).min_by(|&a, &b| {
            let da = (route[a][0] - p[0]).hypot(route[a][1] - p[1]);
            da.total_cmp(&(route[b][0] - p[0]).hypot(route[b][1] - p[1]))
        }).unwrap_or(0);
        let r = r * u;
        let (mut pts, mut ws) = (Vec::new(), Vec::new());
        for k in 0..160 {
            let psi = 2.0 * PI * f64::from(k) / 159.0;
            let n = r * (1.0 - psi.cos());
            let a = 0.62 * r * psi + r * psi.sin() + 0.35 * n;
            pts.push([line[i][0] + tang[i][0] * a + nrm[i][0] * n, line[i][1] + tang[i][1] * a + nrm[i][1] * n]);
            ws.push((0.6 + 2.4 * (psi / 2.0).sin().powf(0.8)) * u);
        }
        lines.push((pts, ws, vec![0.95; 160]));
    }
    let deep = (124.0 * u * scale).ceil() / scale;
    let room = (40.0 * u * scale).ceil() / scale;
    let (width, height) = (g.width, g.height);
    let (w, h) = ((width * scale).ceil() as usize, (height * scale).ceil() as usize);
    let mut px = vec![[0u8; 4]; w * h];
    for (sx, sy, sw, sh) in [(0.0, 0.0, width, deep), (0.0, height - deep, width, deep), (0.0, deep, deep, height - 2.0 * deep), (width - deep, deep, deep, height - 2.0 * deep)] {
        let (gl, gt) = (sx - room, sy - room);
        let (gw, gh) = (((sw + 2.0 * room) * scale).ceil() as usize, ((sh + 2.0 * room) * scale).ceil() as usize);
        let (c, a) = lit_strokes(&lines, gl, gt, gw, gh, scale, d);
        let pic = picture(&c, &a);
        let cut = (room * scale).round_ties_even() as usize;
        let (ox, oy) = ((sx * scale).round() as usize, (sy * scale).round() as usize);
        for y in cut..gh - cut {
            for x in cut..gw - cut {
                let (tx, ty) = (ox + x - cut, oy + y - cut);
                if tx < w && ty < h {
                    px[ty * w + tx] = pic.px[y * gw + x];
                }
            }
        }
    }
    Placed { left: 0.0, top: 0.0, right: w as f64 / scale, bottom: h as f64 / scale, pic: Pic { w, h, px } }
}

/// _curls: the curl leaving the top border, and the updraft's rising arcs in the bottom right.
pub fn curls(g: &Geo, scale: f64) -> [Placed; 2] {
    let (u, xy) = (g.u, |x: f64, y: f64| g.at(x, y, false));
    let d = u * scale;
    let lin = |n: usize| (0..n).map(move |i| i as f64 / (n - 1) as f64);
    let lead = bezier(xy(1390.0, 14.0), xy(1450.0, 16.0), xy(1500.0, 22.0), xy(1540.0, 34.0), 60);
    let a = with_curl(lead, 52.0 * u, 1.05, 1.0, 0.62);
    let wa = lin(a.len()).map(|k| (3.4 * (1.0 - k).powf(0.7) + 0.4) * u).collect();
    let lead = bezier(xy(1450.0, 14.0), xy(1500.0, 20.0), xy(1560.0, 30.0), xy(1592.0, 52.0), 60);
    let b = with_curl(lead, 34.0 * u, 0.8, 1.0, 0.5);
    let wb = lin(b.len()).map(|k| (1.8 * (1.0 - k) + 0.3) * u).collect();
    let top = vec![(a.clone(), wa, vec![0.9; a.len()]), (b.clone(), wb, vec![0.7; b.len()])];
    let mut low = Vec::new();
    for (p0, p1, p2, p3, r0, wmax) in [((1452.0, 846.0), (1515.0, 836.0), (1560.0, 790.0), (1574.0, 728.0), 22.0, 4.2),
                                       ((1530.0, 848.0), (1585.0, 838.0), (1612.0, 800.0), (1612.0, 752.0), 15.0, 3.0)] {
        let arc = bezier(xy(p0.0, p0.1), xy(p1.0, p1.1), xy(p2.0, p2.1), xy(p3.0, p3.1), 70);
        let line = with_curl(arc, r0 * u, 0.85, -1.0, 0.5);
        let ws = lin(line.len()).map(|k| (wmax * (PI * (k * 1.3).clamp(0.0, 1.0) * 0.5 + 0.2).sin() * (1.0 - k).powf(0.4) + 0.3) * u).collect();
        let n = line.len();
        low.push((line, ws, vec![0.85; n]));
    }
    [strokes_image(&top, scale, d), strokes_image(&low, scale, d)]
}

/// _strand_lines: the three strands leaving the strings (starts and bends given on the stage).
pub fn strand_lines(ends: [[Pt; 4]; 3], u: f64) -> Vec<Line> {
    let spec = [(1.2, 4.8, None), (1.1, 4.0, Some((17.0, 0.95, -1.0))), (0.9, 3.2, Some((13.0, 0.9, -1.0)))];
    let life = STILL - 1.3;
    let mut out = Vec::new();
    for (k, ([p0, p1, p2, p3], (w0, w1, end))) in ends.into_iter().zip(spec).enumerate() {
        let mut line = bezier(p0, p1, p2, p3, 140);
        if let Some((r0, turns, side)) = end {
            line = with_curl(line, r0 * u, turns, side, 0.55);
        }
        let n = line.len();
        let wide = (0..n)
            .map(|i| {
                let kk = i as f64 / (n - 1) as f64;
                let base = if end.is_none() { w0 + (w1 - w0) * kk.powf(0.8) } else { (w0 + (w1 - w0) * (PI * (kk * 1.25).clamp(0.0, 1.0) / 2.0).sin()) * (1.0 - kk).powf(0.35) + 0.25 };
                base * (0.85 + 0.15 * (2.0 * PI * kk * 3.0 - life * 3.0 + k as f64).sin()) * u
            })
            .collect();
        out.push((line, wide, vec![0.95 - 0.08 * k as f64; n]));
    }
    out
}

/// _glint: a soft streak of light, 40 by 9 points, made at scale.
pub fn glint(scale: f64) -> Pic {
    let (w, h) = ((40.0 * scale).ceil() as usize, (9.0 * scale).ceil() as usize);
    let (mint, core) = (rgb(MINT), rgb(CORE));
    let (c, a) = light_of(w, h, |i| {
        let (xs, ys) = img::xy_of(w, i);
        let (x, y) = ((xs / w as f32 - 0.5) * 2.0, (ys / h as f32 - 0.5) * 2.0);
        let k = (-(x * x) * 3.0 - (y * y) * 5.0).exp();
        img::add3(scale3(mint, k * 0.9), scale3(core, k.powi(4) * 0.8))
    });
    picture(&c, &a)
}

/// _stalks: the cecilias' stalks and two blade leaves, painted once at full strength into a picture.
pub fn stalks(g: &Geo, curves: &[[(f64, f64); 3]]) -> Placed {
    let u = g.u;
    let xy = |p: (f64, f64)| g.at(p.0, p.1, false);
    let (left, top) = (0.0, g.height - 200.0 * u);
    let (w, h) = ((220.0 * u).ceil() as usize, (200.0 * u).ceil() as usize);
    let mut color = Color::new(w, h, [0.0; 3]);
    let mut alpha = Map::new(w, h, 0.0);
    let local = |p: Pt, dx: f64, dy: f64| [p[0] + dx - left, p[1] + dy - top];
    let mut lay = |shape: Shape, hex: &str| {
        let mut c = Canvas::new(w, h);
        c.fill(&shape, 1.0);
        let col = rgb(hex);
        over(&mut color, &mut alpha, |_| col, &c.done());
    };
    for [b0, b1, b2] in curves {
        let path = quad(xy(*b0), xy(*b1), xy(*b2), 24);
        for (hex, wide, dx, dy) in [(PINE, 3.4, 1.0, 1.0), ("#4f9f6e", 2.4, 0.0, 0.0), ("#9be0b4", 0.8, -0.6, -0.4)] {
            let moved: Vec<Pt> = path.iter().map(|&p| local(p, dx * u, dy * u)).collect();
            lay(stroke(&[moved], wide * u, Cap::Round), hex);
        }
    }
    for (x0, y0, cx, cy, x1, y1) in [(50.0, 846.0, 70.0, 800.0, 112.0, 790.0), (40.0, 846.0, 18.0, 812.0, 8.0, 770.0)] {
        let mut blade = quad(xy((x0, y0)), xy((cx + 6.0, cy)), xy((x1, y1)), 24);
        blade.extend(quad(xy((x1, y1)), xy((cx - 6.0, cy + 10.0)), xy((x0 + 6.0, y0)), 24).into_iter().skip(1));
        lay(Shape::odd(vec![blade.into_iter().map(|p| local(p, 0.0, 0.0)).collect()]), "#3c8f5e");
    }
    Placed { left, top, right: left + w as f64, bottom: top + h as f64, pic: picture(&color, &alpha) }
}
