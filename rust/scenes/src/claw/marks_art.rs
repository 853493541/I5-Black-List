//! The 嘉宾 marks' pictures, per pixel, at `scale` pixels to the point (claw.py's _claw_marks, _disc,
//! _role, _glass, _note): made once for a mark's size, as claw.py keeps them.

use super::art::{CORE, FOG, LILAC, PURPLE};
use super::geom::{crescent, Affine};
use super::light::{bloom, blur, lerp3, load, mask, noise, picture, pyround, rgb, sample, smooth, Gray, Pic, Pt};

/// A polygon of an ellipse (rx, ry) round (0, 0).
fn oval(rx: f64, ry: f64) -> Vec<Pt> {
    (0..64).map(|i| f64::from(i) / 64.0 * std::f64::consts::TAU).map(|a| [rx * a.cos(), ry * a.sin()]).collect()
}

/// A rounded rect (x, y, w, h) with corner radius r as a polygon.
pub fn rounded(b: [f64; 4], r: f64) -> Vec<Pt> {
    let r = r.min(b[2] / 2.0).min(b[3] / 2.0);
    let corners = [(b[0] + b[2] - r, b[1] + r, -90.0), (b[0] + b[2] - r, b[1] + b[3] - r, 0.0), (b[0] + r, b[1] + b[3] - r, 90.0), (b[0] + r, b[1] + r, 180.0)];
    corners.iter().flat_map(|&(cx, cy, start)| (0..=12).map(move |i| (start + 7.5 * f64::from(i)).to_radians()).map(move |a| [cx + r * a.cos(), cy + r * a.sin()])).collect()
}

/// np.roll by (k, k) on both axes: out[y][x] = a[y - k][x - k], wrapping.
fn roll(a: &Gray, k: i64) -> Gray {
    let (w, h) = (a.w as i64, a.h as i64);
    Gray::from_fn(a.w, a.h, |x, y| a.at((x as i64 - k).rem_euclid(w) as usize, (y as i64 - k).rem_euclid(h) as usize))
}

/// Lit from the top left: brighter where the soft shape rises that way, deeper where it falls away.
fn relief(body: [f32; 3], height: &Gray, rolled: &Gray, i: usize) -> [f32; 3] {
    let slope = ((height.v[i] - rolled.v[i]) * 2.2).clamp(-1.0, 1.0);
    let (lit, shade) = (slope.max(0.0), (-slope).max(0.0) * 0.6);
    lerp3(lerp3(body, rgb(CORE), lit * 0.5), rgb("#4a2fa8"), shade)
}

/// _claw_marks: count claw marks lit per pixel, centred, at `angle` degrees.
pub fn claw_marks(length: f64, thick: f64, scale: f64, angle: f64, count: usize, spacing: Option<f64>) -> Pic {
    let spacing = spacing.unwrap_or(thick * 2.6);
    let side = length + thick * 5.0 + spacing * count as f64;
    let n = (side * scale).ceil().max(4.0) as usize;
    let mid = (count as f64 - 1.0) / 2.0;
    let shapes: Vec<Vec<Pt>> = (0..count)
        .map(|i| {
            let o = i as f64 - mid;
            let tf = Affine::default().translate(n as f64 / 2.0, n as f64 / 2.0).scale(scale, scale).rotate(angle).translate(0.0, o * spacing);
            crescent(length * (1.0 - 0.1 * o.abs()), thick).into_iter().map(|p| tf.map(p)).collect()
        })
        .collect();
    let core = mask(n, n, &shapes);
    bloom(&core, LILAC, &[(0.8 * scale, 1.0), (2.5 * scale, 0.8), (6.0 * scale, 0.5)], 0.8)
}

/// _disc: slate glass with fog in it, lit at the top, a lilac rim.
pub fn disc(side: f64, scale: f64) -> Pic {
    let n = (side * scale).ceil().max(4.0) as usize;
    let mist = noise(n, n, (n as f64 / 5.0).max(2.0), 3, 31);
    let nf = n as f32;
    let at = |i: usize| ((i % n) as f32, (i / n) as f32);
    let r = |i: usize| {
        let (x, y) = at(i);
        (x + 0.5 - nf / 2.0).hypot(y + 0.5 - nf / 2.0) / (nf / 2.0)
    };
    let color = |i: usize| {
        let (x, y) = at(i);
        let base = lerp3(rgb("#2f3a4f"), rgb("#121722"), (y + 0.5) / nf);
        let fog = rgb(FOG).map(|c| c * mist.v[i] * 0.22 * (1.0 - r(i) * 0.5));
        let rim = smooth(0.8, 0.9, r(i)) * smooth(1.0, 0.92, r(i));
        let shine = (-(((x / nf - 0.42) / 0.22).powi(2) + ((y / nf - 0.22) / 0.1).powi(2))).exp() * 0.25;
        lerp3(std::array::from_fn(|c| base[c] + fog[c]), rgb(LILAC), rim).map(|c| c + shine)
    };
    picture(n, n, color, |i| smooth(1.0, 0.94, r(i)))
}

fn percentile(mut v: Vec<f32>, q: f64) -> f32 {
    v.sort_by(f32::total_cmp);
    let at = q / 100.0 * (v.len() - 1) as f64;
    let (lo, f) = (at.floor() as usize, (at - at.floor()) as f32);
    v[lo] + (v[(lo + 1).min(v.len() - 1)] - v[lo]) * f
}

/// _role: the 指挥家's role icon for a badge `side` points wide: its purple glow, the icon pale
/// white-lilac and lit from the top left, and where the baton's tip is from the middle.
pub fn role(side: f64, scale: f64, icon: &std::path::Path) -> Result<(Pic, Pic, Pt), String> {
    let src = load(icon)?;
    let f = src.floats();
    let alpha = Gray { w: src.w, h: src.h, v: f.iter().map(|p| p[3]).collect() };
    let lum = Gray { w: src.w, h: src.h, v: f.iter().map(|p| (p[0] + p[1] + p[2]) / 3.0).collect() };
    let opaque: Vec<(f64, f64)> = (0..src.w * src.h).filter(|&i| alpha.v[i] >= 0.5).map(|i| ((i % src.w) as f64, (i / src.w) as f64)).collect();
    let span = |g: fn(&(f64, f64)) -> f64| opaque.iter().map(g).fold((f64::MAX, f64::MIN), |(a, b), v| (a.min(v), b.max(v)));
    let ((x0, x1), (y0, y1)) = (span(|p| p.0), span(|p| p.1));
    let (cx, cy) = ((x0 + x1 + 1.0) / 2.0, (y0 + y1 + 1.0) / 2.0);
    let reach = opaque.iter().map(|p| (p.0 + 0.5 - cx).hypot(p.1 + 0.5 - cy)).fold(0.0, f64::max);
    let k = side * 0.37 / reach;
    let n = (side * scale).ceil().max(4.0) as usize;
    let fine = (4.0 / (k * scale)).ceil().max(1.0) as usize;
    let m = n * fine;
    let per = k * scale * fine as f64;
    let grid = |i: usize| (i as f64 + 0.5 - m as f64 / 2.0) / per;
    let there = Gray::from_fn(m, m, |x, y| sample(&alpha, grid(x) + cx - 0.5, grid(y) + cy - 0.5) as f32);
    let lit_by = Gray::from_fn(m, m, |x, y| (sample(&lum, grid(x) + cx - 0.5, grid(y) + cy - 0.5) / f64::from(there.at(x, y)).max(1e-3)) as f32);
    let edge = (0.6 / per).min(0.2) as f32;
    let soft = blur(&there, 0.3 * per);
    let core = soft.map(|v| smooth(0.5 - edge, 0.5 + edge, v));
    let inner: Vec<f32> = (0..m * m).filter(|&i| core.v[i] > 0.5).map(|i| lit_by.v[i]).collect();
    let (lo, hi) = if inner.is_empty() { (0.0, 1.0) } else { (percentile(inner.clone(), 5.0), percentile(inner, 95.0)) };
    let step = pyround(0.6 * scale * fine as f64).max(1.0) as i64;
    let height = blur(&core, 0.7 * scale * fine as f64);
    let rolled = roll(&height, step);
    let body = |i: usize| {
        let g = 0.3 + 0.7 * smooth(lo, hi + 1e-3, lit_by.v[i]);
        let b = relief(lerp3(rgb("#a990f2"), rgb("#f6f2ff"), g), &height, &rolled, i);
        lerp3(b, rgb("#5b3fc0"), smooth(0.85, 0.55, soft.v[i]) * 0.55)
    };
    // Averaged down to the pixels it shows at.
    let mut a = Gray::new(n, n);
    let mut sum = vec![[0f32; 3]; n * n];
    for i in 0..m * m {
        let (x, y) = ((i % m) / fine, (i / m) / fine);
        let c = core.v[i];
        a.v[y * n + x] += c;
        let b = body(i);
        for ch in 0..3 {
            sum[y * n + x][ch] += b[ch] * c;
        }
    }
    let cells = (fine * fine) as f32;
    a = a.map(|v| v / cells);
    let role = picture(n, n, |i| sum[i].map(|s| s / cells / a.v[i].max(1e-4)), |i| a.v[i]);
    let (b1, b3) = (blur(&a, 1.2 * scale), blur(&a, 3.0 * scale));
    let halo = |i: usize| (b1.v[i] * 0.8 + b3.v[i] * 0.7).clamp(0.0, 1.0);
    let glow = picture(n, n, |i| lerp3(rgb(PURPLE), rgb(LILAC), smooth(0.0, 0.7, halo(i))), |i| halo(i) * 0.85);
    Ok((glow, role, [(31.5 - cx) * k, (28.5 - cy) * k]))
}

/// _glass: the card, slate glass darker toward its foot, fog drifting in it, a lilac edge.
pub fn glass(size: [f64; 2], card_top: f64, scale: f64) -> Pic {
    let (w, h) = ((size[0] * scale).ceil().max(4.0) as usize, (size[1] * scale).ceil().max(4.0) as usize);
    let body = [0.0, card_top, size[0], size[1] - card_top];
    let inside = mask(w, h, &[rounded(body, 8.0).into_iter().map(|p| [p[0] * scale, p[1] * scale]).collect()]);
    let mist = noise(w, h, (26.0 * scale).max(3.0), 3, 7);
    let k = pyround(1.2 * scale).max(1.0) as i64;
    let (ahead, behind) = (roll(&inside, k), roll(&inside, -k));
    let color = |i: usize| {
        let v = (((i / w) as f64 / scale - card_top) / body[3].max(1.0)).clamp(0.0, 1.0) as f32;
        let c = lerp3(rgb("#252c3d"), rgb("#141925"), v);
        let fog = smooth(0.45, 0.9, mist.v[i]) * 0.16;
        let c: [f32; 3] = std::array::from_fn(|ch| c[ch] + rgb(FOG)[ch] * fog);
        let edge = (inside.v[i] - ahead.v[i] * behind.v[i]).clamp(0.0, 1.0);
        lerp3(c, rgb("#9d86e8"), edge)
    };
    picture(w, h, color, |i| inside.v[i] * 0.94)
}

/// _beamed: two notes beamed together, ♫, `high` tall, centred on 0, as separate contours.
fn beamed(high: f64) -> Vec<Vec<Pt>> {
    let (rx, ry, stem, beam) = (0.19 * high, 0.135 * high, 0.075 * high, 0.17 * high);
    let heads = [[-0.3 * high, 0.36 * high], [0.3 * high, 0.26 * high]];
    let mut out: Vec<Vec<Pt>> = heads.iter().map(|h| oval(rx, ry).into_iter().map(|p| Affine::default().translate(h[0], h[1]).rotate(-22.0).map(p)).collect()).collect();
    let tops = heads.map(|h| [h[0] + rx * 0.86 - stem, h[1] - 0.66 * high]);
    for (h, t) in heads.iter().zip(tops) {
        let bottom = h[1] - ry * 0.2;
        out.push(vec![[t[0], t[1]], [t[0] + stem, t[1]], [t[0] + stem, bottom], [t[0], bottom]]);
    }
    out.push(vec![tops[0], [tops[1][0] + stem, tops[1][1]], [tops[1][0] + stem, tops[1][1] + beam], [tops[0][0], tops[0][1] + beam]]);
    out
}

/// _note: the card's ♫, pale lilac at its beam deepening to purple at its heads, lit, in a glow.
pub fn note(high: f64, scale: f64) -> Pic {
    let margin = high * 0.4;
    let n = ((high + margin * 2.0) * scale).ceil().max(4.0) as usize;
    let c = n as f64 / 2.0;
    let core = mask(n, n, &beamed(high).into_iter().map(|s| s.into_iter().map(|p| [p[0] * scale + c, p[1] * scale + c]).collect()).collect::<Vec<_>>());
    let height = blur(&core, 0.9 * scale);
    let rolled = roll(&height, pyround(0.8 * scale).max(1.0) as i64);
    let hot = blur(&core, 0.6 * scale);
    let (h1, h2) = (blur(&core, 1.2 * scale), blur(&core, 2.6 * scale));
    let px: Vec<([f32; 3], f32)> = (0..n * n)
        .map(|i| {
            let v = (((i / n) as f64 / scale - margin) / high).clamp(0.0, 1.0) as f32;
            let body = lerp3(lerp3(rgb("#ece4ff"), rgb("#b9a2ff"), smooth(0.0, 0.5, v)), rgb(PURPLE), smooth(0.45, 1.0, v));
            let body = lerp3(relief(body, &height, &rolled, i), rgb(CORE), smooth(0.8, 1.0, hot.v[i]) * 0.35);
            let halo = (h1.v[i] * 0.9 + h2.v[i] * 0.7).clamp(0.0, 1.0);
            let tint = lerp3(rgb(PURPLE), rgb(LILAC), smooth(0.0, 0.7, halo));
            let (k, glow) = (core.v[i], halo * 0.9 * (1.0 - core.v[i]));
            let alpha = k + glow;
            (std::array::from_fn(|ch| (body[ch] * k + tint[ch] * glow) / alpha.max(1e-4)), alpha)
        })
        .collect();
    picture(n, n, |i| px[i].0, |i| px[i].1)
}
