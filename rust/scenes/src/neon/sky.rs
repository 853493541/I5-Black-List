//! The pictures neon.py works out once per pixel for its sky and light: the night at the edges, the
//! storm clouds lit by lightning, a strike's side flash, the frame's glow, the street haze, a
//! searchlight's beam, and the round glows (`_dot`).

use super::raster::{blur, glow, noise, picture, round_even, smooth, Grid, Img, Light, Mask, Pt, Shape};
use super::{rgb, Rect, CYAN, GLOW_BAND, INDIGO, MAGENTA, NIGHT, SOFT, VIOLET};

fn add(a: [f32; 3], b: [f32; 3]) -> [f32; 3] {
    [a[0] + b[0], a[1] + b[1], a[2] + b[2]]
}

fn mul(a: [f32; 3], k: f32) -> [f32; 3] {
    [a[0] * k, a[1] * k, a[2] * k]
}

/// neon._field: x, y, how clear of the names and how near the edge, at a quarter of the size.
pub struct Field {
    pub w: usize,
    pub h: usize,
    pub x: Grid,
    pub y: Grid,
    pub clear: Grid,
    pub rim: Grid,
}

pub fn field(width: f64, height: f64, u: f64) -> Field {
    let (w, h) = (round_even(width * SOFT).max(1.0) as usize, round_even(height * SOFT).max(1.0) as usize);
    let (wf, hf, s) = (width as f32, height as f32, SOFT as f32);
    let x = Grid::from_fn(w, h, |i, _| (i as f32 + 0.5) / s);
    let y = Grid::from_fn(w, h, |_, j| (j as f32 + 0.5) / s);
    let r = (120.0 * u) as f32;
    let (n0, n1, t0, t1) = ((width * 0.13) as f32, (width * 0.94) as f32, (height * 0.29) as f32, (height * 0.84) as f32);
    let clear = x.zip(&y, |x, y| {
        let dx = (n0 + r - x).max(x - n1 + r).max(0.0);
        let dy = (t0 + r - y).max(y - t1 + r).max(0.0);
        smooth(0.0, (150.0 * u) as f32, dx.hypot(dy) - r)
    });
    let rim = x.zip(&y, |x, y| 1.0 - smooth(0.0, (300.0 * u) as f32, x.min(wf - x).min(y.min(hf - y))));
    Field { w, h, x, y, clear, rim }
}

/// neon._night: the night at the edges, smog, storm clouds, the city's glow in each bottom corner.
pub fn night(width: f64, height: f64, u: f64, sky: &Grid) -> Img {
    let f = field(width, height, u);
    let smog = noise(f.w, f.h, 110.0 * u * SOFT, 3, 9);
    let (wf, hf) = (width as f32, height as f32);
    let mut light: Light = Vec::with_capacity(f.w * f.h);
    let mut alpha = Vec::with_capacity(f.w * f.h);
    for i in 0..f.w * f.h {
        let (x, y, clear, rim, sm) = (f.x.v[i], f.y.v[i], f.clear.v[i], f.rim.v[i], smog.v[i]);
        let dark = clear * (0.45 + 0.5 * rim) * (0.85 + 0.3 * sm);
        let mut tone = add(mul(rgb(NIGHT), rim), mul(rgb(INDIGO), 1.0 - rim));
        for (cx, cy, reach, tint) in [(0.0, 0.0, 600.0 * u, "#1a0a4d"), (wf, 0.0, 620.0 * u, "#1c0840")] {
            let reach = reach as f32;
            let g = (-((x - cx).powi(2) + (y - cy).powi(2)) / (reach * reach) * 2.0).exp() * (0.6 + 0.5 * sm) * 0.9;
            tone = add(mul(tone, 1.0 - g), mul(rgb(tint), g));
        }
        let cloud = smooth(0.42, 0.78, sky.at(i % f.w, i / f.w)) * (1.0 - smooth(hf * 0.05, hf * 0.3, y));
        tone = add(mul(tone, 1.0 - cloud * 0.55), mul(rgb("#2e2163"), cloud * 0.55));
        let mut l = mul(tone, dark);
        let mut amount = dark;
        for (cx, tint, deep, strength) in [(0.0, MAGENTA, "#4a0c5c", 0.62f32), (wf, CYAN, "#0b3478", 0.68)] {
            let g = (-(((x - cx) / (wf * 0.24)).powi(2) + ((y - hf) / (hf * 0.8)).powi(2))).exp() * clear * (0.5 + 0.7 * sm);
            l = add(l, mul(add(mul(rgb(deep), 0.9), mul(rgb(tint), 0.3)), g * strength * 2.0));
            amount += g * strength;
        }
        light.push(mul(l, 1.0 / amount.max(1e-4)));
        alpha.push(amount.clamp(0.0, 0.94));
    }
    picture(f.w, f.h, &light, &alpha)
}

/// neon._cloud_flash: the clouds lit from inside near `at` (a share of the width); hardly any over the title.
pub fn cloud_flash(width: f64, height: f64, u: f64, sky: &Grid, at: f64, title: Rect) -> (Rect, Img) {
    let rect = [0.0, 0.0, width, height * 0.42];
    let (h, w) = (round_even(rect[3] * SOFT).max(1.0) as usize, round_even(width * SOFT).max(1.0) as usize);
    let (hf, wf) = (height as f32, width as f32);
    let mut lit = Grid::new(w, h);
    for j in 0..h {
        for i in 0..w {
            let x = rect[0] as f32 + (i as f32 + 0.5) * rect[2] as f32 / w as f32;
            let y = rect[1] as f32 + (j as f32 + 0.5) * rect[3] as f32 / h as f32;
            let thick = smooth(0.38, 0.85, sky.at(i, j));
            let near = (-((x - at as f32 * wf) / (wf * 0.2)).powi(2)).exp() * (1.0 - smooth(hf * 0.02, hf * 0.38, y));
            let (l, t, r, b) = (title[0] as f32, title[1] as f32, (title[0] + title[2]) as f32, (title[1] + title[3]) as f32);
            let away = (l - x).max(x - r).max(0.0).hypot((t - y).max(y - b).max(0.0));
            lit.v[j * w + i] = thick * near * (0.1 + 0.9 * smooth(0.0, (60.0 * u) as f32, away));
        }
    }
    let soft = blur(&lit, 6.0);
    let light: Light = (0..w * h)
        .map(|i| {
            let v = lit.v[i];
            add(add(mul(rgb("#ffffff"), v.powf(2.5) * 0.8), mul(rgb("#a99bff"), v * 0.55)), mul(rgb(VIOLET), soft.v[i] * 0.45))
        })
        .collect();
    (rect, glow(w, h, &light))
}

/// neon._far_light: lightning far off in the clouds, two dim flickers.
pub fn far_light(age: f64) -> f64 {
    if !(0.0..=0.42).contains(&age) {
        return 0.0;
    }
    for (end, level) in [(0.05, 0.55), (0.1, 0.12), (0.15, 0.4)] {
        if age < end {
            return level;
        }
    }
    0.4 * (1.0 - (age - 0.15) / 0.27).powi(2)
}

/// neon._strike_light: a flash, a dip, a second flash, then gone.
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

/// neon._flash: one side's edges lit by a strike, none over the names or the gap.
pub fn flash(width: f64, height: f64, gap: Rect, u: f64, side: i32) -> Img {
    let f = field(width, height, u);
    let wf = width as f32;
    let mut color: Light = Vec::with_capacity(f.w * f.h);
    let mut alpha = Vec::with_capacity(f.w * f.h);
    for i in 0..f.w * f.h {
        let (x, y) = (f.x.v[i], f.y.v[i]);
        let half = if side < 0 { 1.0 - smooth(wf * 0.2, wf * 0.75, x) } else { smooth(wf * 0.25, wf * 0.8, x) };
        let away = (gap[0] as f32 - x).max(x - (gap[0] + gap[2]) as f32).max(0.0).hypot((gap[1] as f32 - y).max(0.0));
        let l = f.rim.v[i].powf(1.6) * f.clear.v[i] * half * smooth(0.0, (60.0 * u) as f32, away);
        let c = add(add(mul(rgb("#e9fdff"), l * l), mul(rgb(CYAN), l * (1.0 - l) * 1.6)), mul(rgb(VIOLET), (1.0 - l) * 0.3));
        let top = c[0].max(c[1]).max(c[2]).max(1e-4);
        color.push(mul(c, 1.0 / top));
        alpha.push(l * 0.4);
    }
    picture(f.w, f.h, &color, &alpha)
}

/// A polyline stroked with round caps and joins, as mask shapes.
pub fn polyline(points: &[Pt], width: f64) -> Vec<Shape> {
    points.windows(2).map(|p| Shape::Line { a: p[0], b: p[1], half: width / 2.0, reach: 0.0, round: true }).collect()
}

/// neon._frame_glow: the light the two tubes throw, at a quarter of the size: cyan's, magenta's, both.
pub fn frame_glow(width: f64, height: f64, outer: &[Pt], inner: &[Pt], u: f64) -> [Img; 3] {
    let f = field(width, height, u);
    let (wf, hf) = (width as f32, height as f32);
    let fade = f.x.zip(&f.y, |x, y| 1.0 - smooth((GLOW_BAND * 0.6 * u) as f32, (GLOW_BAND * u) as f32, x.min(wf - x).min(y.min(hf - y))));
    let mut lights: Vec<Light> = Vec::new();
    for (points, tint) in [(outer, CYAN), (inner, MAGENTA)] {
        let scaled: Vec<Pt> = points.iter().map(|p| [p[0] * SOFT, p[1] * SOFT]).collect();
        let mut m = Mask::new(f.w, f.h);
        m.fill(&polyline(&scaled, 5.0 * u * SOFT), 1.0);
        let core = m.done();
        let (b1, b5, b14) = (blur(&core, 1.5), blur(&core, 5.0), blur(&core, 14.0));
        let t = rgb(tint);
        lights.push(
            (0..f.w * f.h)
                .map(|i| {
                    let halo = b1.v[i] * 1.1 + b5.v[i] * 0.9 + b14.v[i] * 0.7;
                    mul(add(mul(t, halo), mul(add(mul(t, 0.5), [0.28; 3]), core.v[i].powf(1.5))), fade.v[i])
                })
                .collect(),
        );
    }
    let both: Light = lights[0].iter().zip(&lights[1]).map(|(a, b)| add(*a, *b)).collect();
    [glow(f.w, f.h, &lights[0]), glow(f.w, f.h, &lights[1]), glow(f.w, f.h, &both)]
}

/// The pixel grid of a picture of rect, w by h, in points (neon._grid).
fn grid(rect: Rect, w: usize, h: usize) -> (Grid, Grid) {
    let x = Grid::from_fn(w, h, |i, _| rect[0] as f32 + (i as f32 + 0.5) * rect[2] as f32 / w as f32);
    let y = Grid::from_fn(w, h, |_, j| rect[1] as f32 + (j as f32 + 0.5) * rect[3] as f32 / h as f32);
    (x, y)
}

/// neon._haze: the street's glow in the mist round the towers' feet on one side, at half size.
pub fn haze(width: f64, height: f64, gap: Rect, u: f64, side: i32) -> (Rect, Img) {
    let reach = 190.0 * u;
    let rect = if side < 0 { [-20.0 * u, height - reach, gap[0] + 20.0 * u, reach] } else { [gap[0] + gap[2], height - reach, width - gap[0] - gap[2] + 20.0 * u, reach] };
    let (w, h) = (round_even(rect[2] * 0.5).max(1.0) as usize, round_even(rect[3] * 0.5).max(1.0) as usize);
    let (x, y) = grid(rect, w, h);
    let mist = noise(w, h, 40.0 * u * 0.5, 3, (30 + side) as u32);
    let edge = (if side < 0 { gap[0] } else { gap[0] + gap[2] }) as f32;
    let hf = height as f32;
    let tint = add(mul(rgb(if side < 0 { MAGENTA } else { CYAN }), 0.42), mul(rgb(VIOLET), 0.22));
    let light: Light = (0..w * h)
        .map(|i| {
            let (x, y) = (x.v[i], y.v[i]);
            let mut thick = (-(hf - y) / (55.0 * u) as f32).exp() * (0.45 + 0.9 * mist.v[i]);
            thick *= smooth((10.0 * u) as f32, (150.0 * u) as f32, (x - edge).abs());
            thick *= 1.0 - smooth(rect[3] as f32 * 0.7, rect[3] as f32, hf - y);
            mul(tint, thick)
        })
        .collect();
    (rect, glow(w, h, &light))
}

/// neon._beam: a searchlight's shaft up from its lamp at (0, 0), at half size.
pub fn beam(height: f64, u: f64) -> (Rect, Img) {
    let reach = height * 1.08;
    let rect = [-80.0 * u, -reach, 160.0 * u, reach];
    let (w, h) = (round_even(rect[2] * 0.5).max(1.0) as usize, round_even(rect[3] * 0.5).max(1.0) as usize);
    let (x, y) = grid(rect, w, h);
    let smog = noise(w, h, 60.0 * u * 0.5, 3, 44);
    let r = reach as f32;
    let tint = add(mul(rgb("#e4dcff"), 0.45), mul(rgb(VIOLET), 0.22));
    let light: Light = (0..w * h)
        .map(|i| {
            let d = -y.v[i];
            let spread = (3.0 * u) as f32 + d * 0.055;
            let mut shaft = (-2.2 * (x.v[i] / spread).powi(2)).exp() * (1.0 - smooth(r * 0.72, r, d)) * (0.55 + 0.45 * (-d / (r * 0.4)).exp());
            shaft *= 0.65 + 0.6 * smog.v[i];
            mul(tint, shaft)
        })
        .collect();
    (rect, glow(w, h, &light))
}

/// neon._dot: a round glow, a hot middle going white by `white`, the tint round it fading out.
pub fn dot(tint: [f32; 3], white: f32, side: usize) -> Img {
    let c = (side as f32 - 1.0) / 2.0;
    let light: Light = (0..side * side)
        .map(|i| {
            let r = ((i % side) as f32 - c).hypot((i / side) as f32 - c) / (side as f32 / 2.0);
            let halo = (-(r * 2.4).powi(2)).exp() * 0.75 + (-r * 5.5).exp() * 0.5;
            let core = (-(r * 9.0).powi(2)).exp();
            let fade = ((1.0 - r) * 4.0).clamp(0.0, 1.0);
            mul(add(mul(tint, halo), mul(add(mul(tint, 0.5), [white; 3]), core)), fade)
        })
        .collect();
    glow(side, side, &light)
}
