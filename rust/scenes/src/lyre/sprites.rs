//! The small things of 竖琴清风, shaded per pixel at ss pixels a design point: maple leaves, white
//! feathers, cecilias, buds and seeds (lyre.py's _maple, _feather, _cecilia, _bud, _seed).

use super::img::{self, lerp3, noise, over, picture, relief, rgb, scale3, smooth, Color, Map, Pic, Rgb};
use super::npr::Pcg64;
use super::raster::{cubic, ellipse, filled, quad, Canvas, Cap, Pt, Shape};
use super::wind::LIGHT;
use super::{CORE, DEEP_MAPLE, EMBER, FEATHER, FEATHER_SHADE, HEART, MINT, PINE, VERMILION};
use crate::pyrand::PyRandom;

const MAPLE_HALF: [Pt; 20] = [[0.0, -1.0], [0.1, -0.8], [0.23, -0.85], [0.215, -0.63], [0.31, -0.63], [0.21, -0.41], [0.4, -0.5], [0.5, -0.46],
    [0.6, -0.64], [0.665, -0.51], [0.93, -0.53], [0.78, -0.35], [0.88, -0.25], [0.64, -0.17], [0.38, -0.07], [0.57, 0.05], [0.7, 0.22],
    [0.46, 0.2], [0.22, 0.19], [0.07, 0.13]];
const MAPLE_VEINS: [Pt; 9] = [[0.0, -0.94], [0.86, -0.51], [-0.86, -0.51], [0.64, 0.2], [-0.64, 0.2], [0.21, -0.81], [-0.21, -0.81], [0.58, -0.6], [-0.58, -0.6]];

/// _local_light: the light as a picture turned by angle degrees and flipped sees it.
pub fn local_light(angle: f64, flip: f64) -> [f32; 3] {
    let a = (-angle).to_radians() as f32;
    let x = LIGHT[0] * a.cos() - LIGHT[1] * a.sin();
    let y = (LIGHT[0] * a.sin() + LIGHT[1] * a.cos()) * if flip >= 0.0 { 1.0 } else { -1.0 };
    let n = (x * x + y * y + LIGHT[2] * LIGHT[2]).sqrt();
    [x / n, y / n, LIGHT[2] / n]
}

fn even(v: f64) -> usize {
    (v as usize) / 2 * 2
}

fn grid(size: usize, f: impl Fn(f32, f32) -> f32) -> Map {
    Map::from_fn(size, size, f)
}

/// A shadow down and right on the screen, worked back into the turned frame, under shape.
fn shadow(shape: &Map, angle: f64, along: (f64, f64), flip: f64, sigma: f64, ss: f64) -> Map {
    let a = (-angle).to_radians();
    let dx = along.0 * a.cos() - along.1 * a.sin();
    let dy = (along.0 * a.sin() + along.1 * a.cos()) * if flip >= 0.0 { 1.0 } else { -1.0 };
    let s = shape.blur(sigma * ss).roll((dy * ss / 2.0) as i64, (dx * ss / 2.0) as i64);
    s.zip(shape, |v, m| v * (1.0 - m))
}

fn shadowed(color: &Color, shape: &Map, shade: &Map, strength: f32) -> Pic {
    let mut base = Color::new(color.w, color.h, rgb(PINE));
    let mut alpha = shade.map(|v| v * strength);
    over(&mut base, &mut alpha, |i| color.v[i], shape);
    picture(&base, &alpha)
}

pub fn maple_pair(r: f64, angle: f64, ember: bool, seed: u64, ss: f64) -> [Pic; 2] {
    [maple(r, angle, 1.0, ember, seed, ss), maple(r, angle, -1.0, ember, seed, ss)]
}

pub fn maple(r: f64, angle: f64, flip: f64, ember: bool, seed: u64, ss: f64) -> Pic {
    let size = even(2.7 * r * ss);
    let light = local_light(angle, flip);
    let off = 0.2 * r;
    let (c0, c1) = (size as f64 / 2.0, size as f64 / 2.0 + off * ss);
    let place = |p: Pt| [c0 + p[0] * ss, c1 + p[1] * ss];
    let mut outline: Vec<Pt> = MAPLE_HALF.iter().map(|p| [p[0] * r, p[1] * r]).collect();
    outline.extend(MAPLE_HALF[1..].iter().rev().map(|p| [-p[0] * r, p[1] * r]));
    let m = filled(&Shape::odd(vec![outline.into_iter().map(place).collect()]), size, size);
    let mut vc = Canvas::new(size, size);
    for (k, v) in MAPLE_VEINS.iter().enumerate() {
        let wide = (if k < 5 { 0.055 } else { 0.035 } * r).max(0.55);
        let from = if k < 5 { [0.0, 0.04 * r] } else if k < 7 { [0.0, -0.45 * r] } else { [0.3 * v[0].signum() * r, -0.2 * r] };
        vc.stroke(&[vec![place(from), place([v[0] * r, v[1] * r])]], wide * ss, Cap::Round, 1.0);
    }
    let stalk: Vec<Pt> = quad([0.0, 0.02 * r], [0.02 * r, 0.35 * r], [0.12 * r, 0.62 * r], 24).into_iter().map(place).collect();
    vc.stroke(&[stalk], (0.085 * r).max(1.0) * ss, Cap::Round, 1.0);
    let veins_all = vc.done();
    let petiole = veins_all.zip(&m, |v, m| v * (1.0 - m));
    let veins = veins_all.zip(&m, |v, m| v * m);
    let (rs, offs) = ((r * ss) as f32, (off * ss) as f32);
    let half = size as f32 / 2.0;
    let (bv05, bv25) = (veins.blur(0.5 * ss), veins.blur(2.5 * ss));
    let bm = m.blur(0.09 * r * ss);
    let h = Map::from_fn(size, size, |x, y| {
        let i = y as usize * size + x as usize;
        (bm.v[i] * m.v[i] - 0.22 * bv05.v[i] + 0.1 * bv25.v[i]) * 30.0 * ss as f32 / 2.0
    });
    let (d, sp) = relief(&h, 1.0, light);
    let sh = (ss as i64).max(1);
    let vl = veins.roll(-sh, -sh).blur(0.5 * ss).zip(&veins, |a, b| (a - b).clamp(0.0, 1.0));
    let edge_b = m.blur(0.8 * ss);
    let mut grain_rng = Pcg64::new(seed);
    let grain = Map { w: size, h: size, v: grain_rng.f32s(size * size) }.blur(1.2);
    let stops: [(f32, &str); 4] = [(0.0, DEEP_MAPLE), (0.2, "#a81c2a"), (0.5, "#d0262a"), (1.0, "#dc3a2c")];
    let (verm, emb, deep, hair, back, stem) = (rgb(VERMILION), rgb(EMBER), rgb(DEEP_MAPLE), rgb("#ff8a6a"), rgb("#b23a40"), rgb("#7a1822"));
    let color = Color::from_fn(size, size, |i| {
        let (x, y) = img::xy_of(size, i);
        let (cx, cy) = ((x - half) / rs, (y - half - offs) / rs);
        let k = cx.hypot(cy);
        let mut c = scale3(img::ramp(&stops, k), 0.74 + 0.4 * d.v[i]);
        c = lerp3(c, verm, ((d.v[i] - 0.5) * 2.2).clamp(0.0, 1.0) * 0.9);
        if ember {
            c = lerp3(c, emb, 0.7 * smooth(0.6, 1.0, k) * (-cy * 1.2 + 0.2).clamp(0.0, 1.0));
        }
        c = lerp3(c, deep, 0.65 * bv05.v[i]);
        c = lerp3(c, hair, 0.3 * vl.v[i] * m.v[i]);
        let edge = (1.0 - edge_b.v[i] * 1.7).clamp(0.0, 1.0) * m.v[i];
        c = img::add3(scale3(c, 1.0 - 0.4 * edge), [sp.v[i] * 0.2; 3]);
        if flip < 0.0 {
            c = img::add3(scale3(c, 0.84), scale3(back, 0.1));
        }
        c = scale3(c, 1.0 + 0.06 * (grain.v[i] - 0.5));
        if petiole.v[i] > m.v[i] {
            stem
        } else {
            c
        }
    });
    let shape = m.zip(&petiole, |a, b| (a + b).clamp(0.0, 1.0));
    let shade = shadow(&shape, angle, (2.2, 3.0), flip, 1.6, ss);
    shadowed(&color, &shape, &shade, 0.45)
}

pub fn feather(length: f64, angle: f64, seed: u32, ss: f64, bend: f64) -> Pic {
    let l = length;
    let size = even(1.3 * l * ss);
    let mut rnd = PyRandom::new(seed);
    let (wu, wl, u0) = (0.22 * l, 0.14 * l, 0.14);
    let sy = |kk: f64| bend * l * (kk - 0.4).powi(2) * 2.0;
    let prof = |kk: f64| {
        let v = ((kk - u0) / (1.0 - u0)).clamp(0.0, 1.0);
        v.powf(0.4) * (1.0 - v.powf(1.6)).clamp(0.0, 1.0).powf(0.8) / 0.56
    };
    let c = size as f64 / 2.0;
    let place = |p: Pt| [c + p[0] * ss, c + p[1] * ss];
    let ks: Vec<f64> = (0..110).map(|i| u0 + (1.0 - u0) * f64::from(i) / 109.0).collect();
    let mut outline: Vec<Pt> = ks.iter().map(|&k| [(k - 0.5) * l, sy(k) - wu * prof(k)]).collect();
    outline.extend(ks.iter().rev().map(|&k| [(k - 0.5) * l, sy(k) + wl * prof(k)]));
    let mut m = filled(&Shape::odd(vec![outline.into_iter().map(place).collect()]), size, size);
    let splits = [(-1.0, rnd.uniform(0.42, 0.5)), (-1.0, rnd.uniform(0.68, 0.76)), (1.0, rnd.uniform(0.52, 0.62))];
    for (side, us) in splits {
        let w = if side < 0.0 { wu } else { wl } * prof(us);
        let (x0, y0) = ((us - 0.5) * l, sy(us));
        let gap = (0.035 * l).max(1.1);
        let wedge = vec![[x0 - 0.62 * w, y0 + side * 0.3 * w], [x0 + 0.2 * w + gap, y0 + side * 1.15 * w], [x0 + 0.2 * w - gap, y0 + side * 1.15 * w]];
        let cut = filled(&Shape::odd(vec![wedge.into_iter().map(place).collect()]), size, size);
        m = m.zip(&cut, |a, b| a * (1.0 - b));
    }
    let mut sc = Canvas::new(size, size);
    for i in 0..34 {
        let (a, b) = (-0.1 + 1.06 * f64::from(i) / 34.0, -0.1 + 1.06 * f64::from(i + 1) / 34.0);
        let wide = (0.045 * l * (1.0 - 0.7 * a.max(0.0))).max(0.6);
        sc.stroke(&[vec![place([(a - 0.5) * l, sy(a)]), place([(b - 0.5) * l, sy(b)])]], wide * ss, Cap::Round, 1.0);
    }
    let shaft = sc.done();
    let mut dc = Canvas::new(size, size);
    let mut r2 = PyRandom::new(seed + 7);
    for i in 0..6 {
        let side = if i % 2 == 1 { -1.0 } else { 1.0 };
        let kk = u0 + r2.uniform(-0.03, 0.12);
        let (bx, by) = ((kk - 0.5) * l, sy(kk));
        let ln = l * r2.uniform(0.09, 0.16);
        let end = [bx + ln * 0.55 * r2.uniform(-0.4, 1.0), by + side * ln];
        let path: Vec<Pt> = quad([bx, by], [bx + ln * 0.2, by + side * ln * 0.7], end, 16).into_iter().map(place).collect();
        dc.stroke(&[path], (0.012 * l).max(0.35) * ss, Cap::Round, 1.0);
    }
    let down = dc.done().zip(&m, |d, m| d * (1.0 - m));
    let light = local_light(angle, 1.0);
    let mut lr = Pcg64::new(u64::from(seed));
    let raw: Vec<f32> = (0..4096).map(|_| lr.random() as f32).collect();
    let line: Vec<f64> = (0..4096).map(|i| 0.5 * f64::from(raw[i]) + if i > 0 { 0.5 * f64::from(raw[i - 1]) } else { 0.0 }).collect();
    let fluff = noise(size, size, 2.5 * ss, 2, u64::from(seed));
    let (shade_c, white, mint) = (rgb(FEATHER_SHADE), rgb(FEATHER), rgb(MINT));
    let stops: [(f32, &str); 3] = [(0.0, "#34525b"), (0.3, "#6f9092"), (1.0, "#aac4c2")];
    let (mut color, mut shape) = (Color::new(size, size, [0.0; 3]), Map::new(size, size, 0.0));
    for i in 0..size * size {
        let (x, y) = img::xy_of(size, i);
        let (lx, ly) = ((f64::from(x) - c) / ss, (f64::from(y) - c) / ss);
        let kk = (lx / l + 0.5).clamp(0.0, 1.0);
        let rel = ly - sy(kk);
        let width = if rel < 0.0 { wu } else { wl } * prof(kk).max(0.05);
        let dd = (rel.abs() / width).clamp(0.0, 1.0);
        let ny = if rel < 0.0 { -0.6 } else { 0.6 } * dd;
        let diffuse = (ny * f64::from(light[1]) + (1.0 - ny * ny).clamp(0.0, 1.0).sqrt() * f64::from(light[2])).clamp(0.0, 1.0);
        let q = (lx - rel.abs() * 1.5) * ss * 0.75;
        let barbs = line[((q as i64).rem_euclid(4096)) as usize];
        let k = (0.16 + 0.9 * diffuse + 0.3 * (barbs - 0.5) - 0.14 * dd.powi(4)).clamp(0.0, 1.0) as f32;
        let mut col = lerp3(shade_c, white, k);
        let groove = (-(rel / (0.03 * l).max(0.6)).powi(2)).exp() * f64::from(u8::from(kk > u0));
        col = scale3(col, 1.0 - 0.1 * groove as f32);
        col = lerp3(col, mint, 0.16 * smooth(0.75, 1.0, dd as f32));
        let fl = fluff.v[i];
        let mut a = m.v[i] * (1.0 - smooth(0.84, 1.0, dd as f32) * (0.45 + 0.55 * fl));
        let base = smooth(u0 as f32, (u0 + 0.14) as f32, kk as f32);
        a *= 0.35 + 0.65 * base.max(f32::from(u8::from(fl > 0.6 - 0.4 * base)));
        a = a.max(down.v[i] * 0.45);
        let mut sc: Rgb = img::ramp(&stops, ((kk - 0.02) / 0.7).clamp(0.0, 1.0) as f32);
        let lit = 0.35 * (-rel / (0.018 * l).max(0.4)).clamp(0.0, 1.0) as f32;
        sc = sc.map(|v| v + (1.0 - v) * lit);
        let s = shaft.v[i];
        let sh = (a + s).clamp(0.0, 1.0);
        shape.v[i] = sh;
        color.v[i] = [0, 1, 2].map(|j| (col[j] * a * (1.0 - s) + sc[j] * s) / sh.max(1e-4));
    }
    let shade = shadow(&shape, angle, (2.0, 3.0), 1.0, 1.8, ss);
    shadowed(&color, &shape, &shade, 0.42)
}

pub fn cecilia(length: f64, angle: f64, seed: u32, ss: f64) -> Pic {
    let l = length;
    let size = even(2.4 * l * ss);
    let light = local_light(angle, 1.0);
    let mut rnd = PyRandom::new(seed);
    let mut color = Color::new(size, size, [0.0; 3]);
    let mut alpha = Map::new(size, size, 0.0);
    let half = size as f32 / 2.0;
    let ssf = ss as f32;
    let (shade_c, white, pale) = (rgb(FEATHER_SHADE), rgb(FEATHER), rgb("#cdebd8"));
    for i in 0..5 {
        let a = (-90.0 + 72.0 * f64::from(i) + rnd.uniform(-6.0, 6.0)).to_radians();
        let ln = l * rnd.uniform(0.9, 1.05);
        let w = 0.5 * ln;
        let (d, n) = ([a.cos(), a.sin()], [-a.sin(), a.cos()]);
        let p = |s: f64, t: f64| [d[0] * s * ln + n[0] * t * w, d[1] * s * ln + n[1] * t * w];
        let mut path = cubic([0.0, 0.0], p(0.3, 1.0), p(0.78, 0.42), p(1.0, 0.0), 24);
        path.extend(cubic(p(1.0, 0.0), p(0.78, -0.42), p(0.3, -1.0), [0.0, 0.0], 24).into_iter().skip(1));
        let m = filled(&Shape::odd(vec![path]).placed(size as f64 / 2.0, size as f64 / 2.0, ss), size, size);
        let bm = m.blur(2.0 * ss);
        let (df, lnf) = ([d[0] as f32, d[1] as f32], ln as f32);
        let h = grid(size, |x, y| {
            let (cx, cy) = ((x - half) / ssf, (y - half) / ssf);
            let across = (-cx * df[1] + cy * df[0]) / lnf;
            let i = y as usize * size + x as usize;
            (bm.v[i] * m.v[i] - 0.15 * (-(across / 0.04).powi(2)).exp() * m.v[i]) * 12.5 * ssf
        });
        let (dif, _) = relief(&h, 1.0, light);
        let seam = m.blur(1.2 * ss);
        for (j, c) in color.v.iter_mut().enumerate() {
            *c = scale3(*c, 1.0 - 0.12 * seam.v[j] * (1.0 - m.v[j]));
        }
        let pc = |j: usize| {
            let (x, y) = img::xy_of(size, j);
            let along = (((x - half) / ssf) * df[0] + ((y - half) / ssf) * df[1]) / lnf;
            let k = (0.35 + 0.75 * dif.v[j]).clamp(0.0, 1.0);
            lerp3(lerp3(shade_c, white, k), pale, 0.5 * (1.0 - smooth(0.05, 0.4, along)))
        };
        over(&mut color, &mut alpha, pc, &m);
    }
    let (heart, dot_c, lf) = (rgb(HEART), rgb("#c7da78"), l as f32);
    for (j, c) in color.v.iter_mut().enumerate() {
        let (x, y) = img::xy_of(size, j);
        let (cx, cy) = ((x - half) / ssf, (y - half) / ssf);
        let r = cx.hypot(cy) / lf;
        *c = lerp3(*c, heart, 0.9 * (-(r / 0.17).powi(2)).exp());
        for i in 0..5 {
            let a = (-54.0 + 72.0 * i as f32).to_radians();
            let dot = (-((cx - 0.1 * lf * a.cos()).powi(2) + (cy - 0.1 * lf * a.sin()).powi(2)) / (0.035 * lf).powi(2)).exp();
            *c = lerp3(*c, dot_c, 0.8 * dot);
        }
    }
    picture(&color, &alpha)
}

pub fn bud(length: f64, angle: f64, ss: f64) -> Pic {
    let l = length;
    let size = even(1.6 * l * ss);
    let light = local_light(angle, 1.0);
    let mut body = cubic([0.0, -0.5 * l], [0.26 * l, -0.15 * l], [0.22 * l, 0.3 * l], [0.0, 0.38 * l], 24);
    body.extend(cubic([0.0, 0.38 * l], [-0.22 * l, 0.3 * l], [-0.26 * l, -0.15 * l], [0.0, -0.5 * l], 24).into_iter().skip(1));
    let mut calyx = Vec::new();
    for sx in [-1.0, 0.0, 1.0] {
        let mut leaf = quad([0.0, 0.45 * l], [sx * 0.2 * l - 0.1 * l, 0.3 * l], [sx * 0.14 * l, 0.05 * l], 16);
        leaf.extend(quad([sx * 0.14 * l, 0.05 * l], [sx * 0.2 * l + 0.1 * l, 0.3 * l], [0.0, 0.45 * l], 16).into_iter().skip(1));
        calyx.push(leaf);
    }
    let c = size as f64 / 2.0;
    let mb = filled(&Shape::odd(vec![body]).placed(c, c, ss), size, size);
    let mc = filled(&Shape::odd(calyx).placed(c, c, ss), size, size);
    let s = ss as f32;
    let (db, _) = relief(&mb.blur(2.5 * ss).zip(&mb, |a, b| a * b * 12.5 * s), 1.0, light);
    let (dc, _) = relief(&mc.blur(1.2 * ss).zip(&mc, |a, b| a * b * 10.0 * s), 1.0, light);
    let (shade_c, white, g0, g1) = (rgb(FEATHER_SHADE), rgb(FEATHER), rgb("#2e7a52"), rgb("#8fd8a8"));
    let out = mc.zip(&mb, |c, b| c + b * (1.0 - c));
    let color = Color::from_fn(size, size, |i| {
        let cb = lerp3(shade_c, white, (0.3 + 0.8 * db.v[i]).clamp(0.0, 1.0));
        let cc = lerp3(g0, g1, dc.v[i]);
        let (wc, wb) = (mc.v[i], mb.v[i] * (1.0 - mc.v[i]));
        [0, 1, 2].map(|k| (cc[k] * wc + cb[k] * wb) / out.v[i].max(1e-5))
    });
    picture(&color, &out)
}

pub fn seed(length: f64, ss: f64) -> Pic {
    let l = length;
    let size = even(1.4 * l * ss);
    let c = size as f64 / 2.0;
    let place = |p: Pt| [c + p[0] * ss, c + p[1] * ss];
    let mut cv = Canvas::new(size, size);
    let mut lines = vec![vec![place([0.0, 0.45 * l]), place([0.0, -0.05 * l])]];
    for i in 0..13 {
        let a = (-90.0 + (f64::from(i) - 6.0) * 13.0).to_radians();
        lines.push(vec![place([0.0, -0.05 * l]), place([0.5 * l * a.cos(), -0.05 * l + 0.5 * l * a.sin()])]);
    }
    for line in lines {
        cv.stroke(&[line], 0.7 * ss, Cap::Square, 1.0);
    }
    cv.fill(&Shape::odd(vec![ellipse(0.0, 0.47 * l, 0.05 * l, 0.08 * l, 32)]).placed(c, c, ss), 1.0);
    let m = cv.done().blur(0.5 * ss).map(|v| (v * 1.4).clamp(0.0, 1.0));
    picture(&Color::new(size, size, rgb(CORE)), &m)
}
