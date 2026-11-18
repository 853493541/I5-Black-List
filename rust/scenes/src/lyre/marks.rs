//! 竖琴清风's own marks (lyre.py's ring, badge, card, lead): the pictures, made once for each size and
//! sharpness, and the ring's shimmer as soft dots. Rects are (left, top, width, height) in points.

use super::img::{self, light_of, noise, over, picture, relief, rgb, scale3, smooth, Color, Map, Pic};
use super::lyre_art::lyre_image;
use super::raster::{filled, Canvas, Cap, Pt, Shape};
use super::sprites::{feather, maple};
use super::wind::{arclen, resample, ribbon};
use super::{ANEMO, CORE, JADE, MEADOW, MINT, PINE};

fn cells(v: f64) -> usize {
    v.ceil() as usize
}

/// src laid over dst through `inv` (dst pixel centre to src pixel coordinates), bilinear, as Qt's smooth drawImage.
fn draw(dst: &mut Pic, src: &Pic, inv: impl Fn(f64, f64) -> (f64, f64)) {
    let tap = |x: i64, y: i64| -> [f32; 4] {
        if x < 0 || y < 0 || x >= src.w as i64 || y >= src.h as i64 {
            return [0.0; 4];
        }
        src.px[y as usize * src.w + x as usize].map(f32::from)
    };
    for y in 0..dst.h {
        for x in 0..dst.w {
            let (u, v) = inv(x as f64 + 0.5, y as f64 + 0.5);
            let (u, v) = (u - 0.5, v - 0.5);
            let (x0, y0) = (u.floor() as i64, v.floor() as i64);
            let (fx, fy) = ((u - u.floor()) as f32, (v - v.floor()) as f32);
            let mix = |a: [f32; 4], b: [f32; 4], k: f32| [0, 1, 2, 3].map(|c| a[c] + (b[c] - a[c]) * k);
            let s = mix(mix(tap(x0, y0), tap(x0 + 1, y0), fx), mix(tap(x0, y0 + 1), tap(x0 + 1, y0 + 1), fx), fy);
            if s[3] <= 0.0 {
                continue;
            }
            let d = &mut dst.px[y * dst.w + x];
            let k = 1.0 - s[3] / 255.0;
            *d = [0, 1, 2, 3].map(|c| (s[c] + f32::from(d[c]) * k + 0.5).min(255.0) as u8);
        }
    }
}

/// Qt's addRoundedRect, from the right end of the top-right corner, counter-clockwise on the screen.
fn qt_rounded(x: f64, y: f64, w: f64, h: f64, r: f64) -> Vec<Pt> {
    let mut pts = Vec::new();
    for (cx, cy, a0) in [(x + w - r, y + r, 0.0f64), (x + r, y + r, 90.0), (x + r, y + h - r, 180.0), (x + w - r, y + h - r, 270.0)] {
        for k in 0..=16 {
            let a = (a0 + 90.0 * f64::from(k) / 16.0).to_radians();
            pts.push([cx + r * a.cos(), cy - r * a.sin()]);
        }
    }
    pts.push(pts[0]);
    pts
}

/// The ring's run as Qt's toFillPolygon gives it: from the top of the left side, clockwise on the screen.
fn ring_outline(x: f64, y: f64, w: f64, h: f64, r: f64) -> Vec<Pt> {
    let mut pts = Vec::new();
    for (cx, cy, a0) in [(x + r, y + r, 180.0f64), (x + w - r, y + r, 270.0), (x + w - r, y + h - r, 0.0), (x + r, y + h - r, 90.0)] {
        for k in 0..=16 {
            let a = (a0 + 90.0 * f64::from(k) / 16.0).to_radians();
            pts.push([cx + r * a.cos(), cy + r * a.sin()]);
        }
    }
    pts.push(pts[0]);
    pts
}

/// _ring_art: the wind ribbon round the button; also where it runs (points and their arc length).
pub fn ring_art(cover: [f64; 4], scale: f64) -> ([f64; 4], Pic, Vec<Pt>, Vec<f64>) {
    let area = [cover[0] - 9.0, cover[1] - 9.0, cover[2] + 18.0, cover[3] + 18.0];
    let r = cover[3] * 0.32;
    let pts = resample(&ring_outline(cover[0], cover[1], cover[2], cover[3], r), 1.0);
    let s = arclen(&pts);
    let total = s[s.len() - 1];
    let wide: Vec<f64> = s.iter().map(|v| 2.8 + 0.8 * (2.0 * std::f64::consts::PI * v / (total / 3.0)).sin()).collect();
    let (w, h) = (cells(area[2] * scale), cells(area[3] * scale));
    let local: Vec<Pt> = pts.iter().map(|p| [(p[0] - area[0]) * scale, (p[1] - area[1]) * scale]).collect();
    let draw_w = |widths: &[f64]| {
        let mut c = Canvas::new(w, h);
        let mut i = 0;
        while i + 1 < local.len() {
            let j = local.len().min(i + 12);
            let ws: Vec<f64> = widths[i..j].iter().map(|v| v * scale).collect();
            c.fill(&Shape::odd(vec![ribbon(&local[i..j], &ws)]), 1.0);
            i += 10;
        }
        c.done()
    };
    let body = draw_w(&wide);
    let core = draw_w(&wide.iter().map(|v| (v * 0.32).max(0.7)).collect::<Vec<_>>());
    let mut color = Color::new(w, h, [0.0; 3]);
    let mut alpha = Map::new(w, h, 0.0);
    let (b1, b2) = (body.blur(2.2 * scale), body.blur(4.5 * scale));
    let anemo = rgb(ANEMO);
    let (c, a) = light_of(w, h, |i| scale3(anemo, b1.v[i] * 0.9 + b2.v[i] * 0.5));
    over(&mut color, &mut alpha, |i| c.v[i], &a);
    let mint = rgb(MINT);
    over(&mut color, &mut alpha, |_| mint, &body.map(|v| (v * 1.2).clamp(0.0, 1.0) * 0.92));
    let glow = core.blur(0.5 * scale);
    let white = rgb(CORE);
    let (c, a) = light_of(w, h, |i| scale3(white, glow.v[i] * 1.2));
    over(&mut color, &mut alpha, |i| c.v[i], &a);
    (area, picture(&color, &alpha), pts, s)
}

/// ring's shimmer t seconds in: (x, y, radius, color, alpha) soft dots, and the ribbon's opacity.
/// A soft dot: x, y, radius, color, alpha.
pub type Dot = (f64, f64, f64, &'static str, f64);

pub fn ring_shimmer(pts: &[Pt], s: &[f64], t: f64) -> (f64, Vec<Dot>) {
    let total = s[s.len() - 1];
    let head = ((t - 0.2) * 0.45).rem_euclid(1.0) * total;
    let mut dots = Vec::new();
    for k in 0..8 {
        let i = s.partition_point(|&v| v < (head - f64::from(k) * 5.0).rem_euclid(total)) % pts.len();
        let [x, y] = pts[i];
        if k == 0 {
            dots.push((x, y, 12.0, MINT, 0.55));
        }
        dots.push((x, y, 3.2 - 0.25 * f64::from(k), CORE, 0.9 * (1.0 - f64::from(k) / 8.0)));
    }
    (0.85 + 0.15 * (t * 2.0).sin(), dots)
}

/// _card_art: deep-jade glass with a mint edge and a faint white line inside it.
pub fn card_art(rect: [f64; 4], scale: f64) -> Pic {
    let body = [rect[0] + 0.65, rect[1] + super::CARD_TOP + 0.65, rect[2] - 1.3, rect[3] - super::CARD_TOP - 1.3];
    let radius = 12.0f64.min(body[3] / 3.0);
    let (w, h) = (cells(rect[2] * scale), cells(rect[3] * scale));
    let to_px = |p: Pt| [(p[0] - rect[0]) * scale, (p[1] - rect[1]) * scale];
    let outline: Vec<Pt> = qt_rounded(body[0], body[1], body[2], body[3], radius).into_iter().map(to_px).collect();
    let m = filled(&Shape::odd(vec![outline.clone()]), w, h);
    let grain = noise(w, h, 10.0 * scale, 2, 3);
    let (top, deep, mint) = (rgb("#1d7a58"), rgb(PINE), rgb(MINT));
    let color = Color::from_fn(w, h, |i| {
        let (x, y) = img::xy_of(w, i);
        let (xr, yr) = (x / w as f32, y / h as f32);
        let k = (0.55 * xr + 0.45 * yr).clamp(0.0, 1.0);
        let sheen = (-((yr - 0.12) / 0.16).powi(2)).exp() * (1.0 - xr * 0.6);
        scale3(img::lerp3(img::lerp3(top, deep, k), mint, 0.22 * sheen), 1.0 + 0.05 * (grain.v[i] - 0.5))
    });
    let (mut color, mut alpha) = (color, m.map(|v| v * 0.78));
    let mut pen = |line: Vec<Pt>, width: f64, c: [f32; 3], a: f32| {
        let mut cv = Canvas::new(w, h);
        cv.stroke(&[line], width * scale, Cap::Flat, 1.0);
        over(&mut color, &mut alpha, |_| c, &cv.done().map(|v| v * a));
    };
    pen(outline, 1.3, mint, 1.0);
    let inner = qt_rounded(body[0] + 2.2, body[1] + 2.2, body[2] - 4.4, body[3] - 4.4, radius - 2.0).into_iter().map(to_px).collect();
    pen(inner, 0.8, [1.0; 3], 70.0 / 255.0);
    picture(&color, &alpha)
}

/// _badge_art: a small Der Frühling on a jade disc lit from the upper left.
pub fn badge_art(box_w: f64, box_h: f64, scale: f64) -> Pic {
    let (w, h) = (cells(box_w * scale), cells(box_h * scale));
    let radius = box_w.min(box_h) * 0.375;
    let (rf, sf) = (radius as f32, scale as f32);
    let at = |i: usize| {
        let (x, y) = img::xy_of(w, i);
        ((x + 0.5) / sf - box_w as f32 / 2.0, (y + 0.5) / sf - box_h as f32 / 2.0)
    };
    let height = Map::from_fn(w, h, |x, y| {
        let (cx, cy) = ((x + 0.5) / sf - box_w as f32 / 2.0, (y + 0.5) / sf - box_h as f32 / 2.0);
        (1.0 - (cx.hypot(cy) / rf).powi(2)).clamp(0.0, 1.0).sqrt() * rf * 0.8 * sf
    });
    let (d, sp) = relief(&height, 1.0, super::wind::LIGHT);
    let stops: [(f32, &str); 4] = [(0.0, PINE), (0.45, JADE), (0.85, MEADOW), (1.1, "#7fd6a8")];
    let (mint, pine) = (rgb(MINT), rgb(PINE));
    let mut alpha = Map::new(w, h, 0.0);
    let color = Color::from_fn(w, h, |i| {
        let (cx, cy) = at(i);
        let r = cx.hypot(cy);
        let disc = ((rf + 0.5 - r) * sf).clamp(0.0, 1.0);
        if disc <= 0.0 {
            return pine;
        }
        let k = (0.15 + 0.95 * d.v[i]).clamp(0.0, 1.1);
        let c = img::add3(img::ramp(&stops, k), [sp.v[i] * 0.25; 3]);
        img::lerp3(c, mint, 0.55 * smooth(rf - 2.5, rf, r) * (-(cx + cy) / rf).clamp(0.0, 1.0))
    });
    for (i, a) in alpha.v.iter_mut().enumerate() {
        let (cx, cy) = at(i);
        let disc = ((rf + 0.5 - cx.hypot(cy)) * sf).clamp(0.0, 1.0);
        let shadow = (rf + 3.0 - (cx - 2.0).hypot(cy - 2.5)).clamp(0.0, 4.0) / 4.0 * 0.45 * (1.0 - disc);
        *a = (disc + shadow).clamp(0.0, 1.0);
    }
    let mut image = picture(&color, &alpha);
    let per = radius * 1.58 / 357.0;
    let lyre = lyre_image(0.0, 2.0 * per * scale, false);
    let big = lyre.w as f64 / (2.0 * scale);
    let (across, down) = ink_middle(&lyre);
    let (left, top) = (box_w / 2.0 - across * big, box_h / 2.0 - down * big);
    let k = lyre.w as f64 / (big * scale);
    draw(&mut image, &lyre, |x, y| ((x - left * scale) * k, (y - top * scale) * k));
    image
}

/// _ink_middle: the middle of the crossbar and horns across, of all of it down, as fractions.
fn ink_middle(p: &Pic) -> (f64, f64) {
    let shows = |x: usize, y: usize| p.px[y * p.w + x][3] > 40;
    let rows: Vec<usize> = (0..p.h).filter(|&y| (0..p.w).any(|x| shows(x, y))).collect();
    let (Some(&y0), Some(&y1)) = (rows.first(), rows.last()) else { return (0.5, 0.5) };
    let band = y0..y0 + (y1 - y0 + 1) / 4;
    let cols: Vec<usize> = (0..p.w).filter(|&x| band.clone().any(|y| shows(x, y))).collect();
    let (x0, x1) = (cols[0], cols[cols.len() - 1]);
    ((x0 + x1 + 1) as f64 / 2.0 / p.w as f64, (y0 + y1 + 1) as f64 / 2.0 / p.h as f64)
}

/// lead: a white feather before the first name, a small red maple leaf before the second, and so on, at
/// three pixels a point.
pub fn lead(size: f64, index: usize) -> Pic {
    let ratio = 3.0;
    let n = (size * ratio).ceil() as usize;
    let mut image = Pic { w: n, h: n, px: vec![[0; 4]; n * n] };
    let unit = size / 18.0;
    let ss = 2.0 * ratio * unit;
    let (pic, angle) = if index.is_multiple_of(2) { (feather(21.0, -50.0, 99, ss, 0.04), -50.0f64) } else { (maple(9.0, 18.0, 1.0, false, 98, ss), 18.0) };
    let px = ss / unit;
    let (c, s) = (angle.to_radians().cos(), angle.to_radians().sin());
    draw(&mut image, &pic, |x, y| {
        let (dx, dy) = (x / ratio - size / 2.0, y / ratio - size / 2.0);
        ((c * dx + s * dy) * px + pic.w as f64 / 2.0, (-s * dx + c * dy) * px + pic.h as f64 / 2.0)
    });
    image
}
