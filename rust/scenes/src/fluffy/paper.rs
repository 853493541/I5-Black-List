//! The scene's other pictures worked out per pixel: the paper band round the screen, the enamel
//! binder rings, the stamped paw prints, and each cat's own stretch of the frame's ink line.

use super::bake::{light, Pic, Shapes};
use super::lines::{along, even, inked, ribbon, stroke};
use super::pcg::Rng;
use super::pixels::{blur, coverage, mask, noise, pyround, Canvas, Plane, Shape};
use super::{rgb, BAND, INK, PRINT, TEAL};
use crate::draw::Pt;
use crate::pyrand::PyRandom;

/// _band: the pale teal paper outside the frame's line, as four strips along the edges, each with
/// its place (x, y, w, h in pixels): a fine grain, soft blotches, a little shade along its inner edge.
pub fn band(width: f64, height: f64, inside: &[Pt], u: f64, scale: f64) -> Vec<([usize; 4], Canvas)> {
    let (w, h) = ((width * scale).ceil() as usize, (height * scale).ceil() as usize);
    let hole: Shape = vec![(1.0, inside.to_vec())];
    let full = mask(w, h, &hole, &|p| [p[0] * scale, p[1] * scale]).map(|c| 1.0 - c);
    let reach = 64.0 * u;
    let rects = [
        [0.0, 0.0, width, reach],
        [0.0, height - reach, width, reach],
        [0.0, reach, reach, height - 2.0 * reach],
        [width - reach, reach, reach, height - 2.0 * reach],
    ];
    let mut out = Vec::new();
    for (index, r) in rects.iter().enumerate() {
        let (x0, y0) = (pyround(r[0] * scale) as usize, pyround(r[1] * scale) as usize);
        let (x1, y1) = (w.min(pyround((r[0] + r[2]) * scale) as usize), h.min(pyround((r[1] + r[3]) * scale) as usize));
        if x1 <= x0 || y1 <= y0 {
            continue;
        }
        let (pw, ph) = (x1 - x0, y1 - y0);
        let paper = Plane { w: pw, h: ph, v: (0..pw * ph).map(|i| full.v[(y0 + i / pw) * w + x0 + i % pw]).collect() };
        let shade = blur(&paper.map(|v| 1.0 - v), 3.0 * u * scale).zip(&paper, |b, p| b * p);
        let fibers = Plane { w: pw, h: ph, v: Rng::new(7 + index as u32).grid(ph, pw) };
        let grain = blur(&fibers, 0.8 * scale).map(|v| (v - 0.5) * 3.0);
        let step = 8;
        let (cw, ch) = (pw / step + 2, ph / step + 2);
        let coarse = noise(cw, ch, 46.0 * u * scale / step as f64, 2, 17 + index as u32);
        let band = rgb(BAND);
        let mut color = [Plane::new(pw, ph), Plane::new(pw, ph), Plane::new(pw, ph)];
        for i in 0..pw * ph {
            let blotch = coarse.v[(i / pw / step) * cw + (i % pw) / step] - 0.5;
            let tone = 1.0 + 0.07 * grain.v[i] + 0.06 * blotch - 0.22 * shade.v[i];
            for c in 0..3 {
                color[c].v[i] = band[c] * tone + 0.05 * (1.0 - shade.v[i]);
            }
        }
        out.push(([x0, y0, pw, ph], Canvas::picture(&color, &paper.map(|v| v * 0.94))));
    }
    out
}

/// _binder: a white enamel ring seen from the front, a torus lit from the top left, a soft shadow
/// on the paper and an inked rim.
pub fn binder(shapes: &Shapes, radius: f64, scale: f64) -> Pic {
    let side = ((radius * 2.0 + 8.0) * scale).ceil() as usize;
    let c = (side as f32 - 1.0) / 2.0;
    let (l, teal, enamel) = (light(), rgb(TEAL), rgb("#eef8f6"));
    let hf = {
        let v = [l[0], l[1], l[2] + 1.0];
        let n = (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]).sqrt();
        [v[0] / n, v[1] / n, v[2] / n]
    };
    let (sc, middle, tube) = (scale as f32, (radius * 0.72) as f32, (radius * 0.28) as f32);
    let mut inside = Plane::new(side, side);
    let mut body = [Plane::new(side, side), Plane::new(side, side), Plane::new(side, side)];
    for i in 0..side * side {
        let (dx, dy) = (((i % side) as f32 - c) / sc, ((i / side) as f32 - c) / sc);
        let rho = dx.hypot(dy) + 1e-6;
        let off = rho - middle;
        inside.v[i] = ((tube - off.abs()) * sc + 0.5).clamp(0.0, 1.0);
        let z = (tube * tube - off * off).max(0.0).sqrt() / tube;
        let radial = (off / tube).clamp(-1.0, 1.0);
        let (nx, ny, nz) = (radial * dx / rho, radial * dy / rho, z);
        let lit = (nx * l[0] + ny * l[1] + nz * l[2]).clamp(0.0, 1.0);
        let sheen = (nx * hf[0] + ny * hf[1] + nz * hf[2]).clamp(0.0, 1.0).powi(30) * 0.9;
        for k in 0..3 {
            body[k].v[i] = enamel[k] * (0.55 + 0.5 * lit) + (1.0 - lit) * 0.2 * teal[k] + sheen;
        }
    }
    let shifted = inside.roll(pyround(1.5 * scale) as usize, pyround(scale) as usize);
    let drop = blur(&shifted, 1.6 * scale).map(|v| v * 0.4);
    let total = inside.zip(&drop, |a, d| a + d * (1.0 - a));
    let under = rgb("#123a3e");
    let color: [Plane; 3] = std::array::from_fn(|k| Plane {
        w: side,
        h: side,
        v: (0..side * side).map(|i| (body[k].v[i] * inside.v[i] + under[k] * drop.v[i] * (1.0 - inside.v[i])) / total.v[i].max(1e-4)).collect(),
    });
    let mut canvas = Canvas::picture(&color, &total);
    let rim: Vec<Vec<Pt>> = shapes.shape("binder.out0", radius).into_iter().map(|(_, p)| p).collect();
    let ink = inked(&rim, (radius * 0.1).max(0.6), &mut PyRandom::new(3));
    let cf = f64::from(c);
    canvas.fill(&coverage(side, side, &ink, &|p| [p[0] * scale + cf, p[1] * scale + cf]), rgb(INK), 0.85);
    let size = side as f64 / scale;
    Pic { canvas, rect: [-size / 2.0, -size / 2.0, size, size] }
}

/// _paw_print: a paw print in pale pink, stamped, walking right, grainy where the stamp missed.
pub fn paw_print(shapes: &Shapes, s: f64, scale: f64) -> Pic {
    let shape = shapes.shape("paw.part0", s);
    let left = -s * 0.62;
    let w = (s * 1.24 * scale).ceil() as usize;
    let ink = mask(w, w, &shape, &|p| [(p[0] - left) * scale, (p[1] - left) * scale]);
    let speck = noise(w, w, 2.2 * scale, 2, 23);
    let edge = blur(&ink, (s * 0.05 * scale).max(1.0));
    let alpha = Plane {
        w,
        h: w,
        v: (0..w * w).map(|i| ink.v[i] * (0.78 + 0.22 * ((speck.v[i] - 0.25) * 4.0).clamp(0.0, 1.0)) * (edge.v[i] * 1.5).clamp(0.0, 1.0)).collect(),
    };
    let pink = rgb(PRINT);
    let color: [Plane; 3] = std::array::from_fn(|k| Plane { w, h: w, v: vec![pink[k]; w * w] });
    let size = w as f64 / scale;
    Pic { canvas: Canvas::picture(&color, &alpha), rect: [-size / 2.0, -size / 2.0, size, size] }
}

/// _edge: the frame's ink line again across a cat's width, drawn in front of the cat behind it.
pub fn edge(size: f64, seed: u32, u: f64) -> Shape {
    let mut rnd = PyRandom::new(seed);
    let points = even(&[[-0.66 * size, 0.0], [0.66 * size, 0.0]], 2.5 * u, false);
    let s = stroke(&points, &along(&points), 3.0 * u, &mut rnd, 0.4 * u, 8.0 * u, 8.0 * u);
    ribbon(&s.points, &s.widths)
}

/// A shape in screen points filled with ink on a picture of its own, at whole pixels.
pub fn ink_sprite(shape: &Shape, color: &str) -> Pic {
    let mut bb = [f64::MAX, f64::MAX, f64::MIN, f64::MIN];
    for (_, poly) in shape {
        for p in poly {
            bb = [bb[0].min(p[0]), bb[1].min(p[1]), bb[2].max(p[0]), bb[3].max(p[1])];
        }
    }
    let (x0, y0) = (bb[0].floor() - 1.0, bb[1].floor() - 1.0);
    let (w, h) = ((bb[2].ceil() + 1.0 - x0) as usize, (bb[3].ceil() + 1.0 - y0) as usize);
    let mut canvas = Canvas::new(w, h);
    canvas.fill(&coverage(w, h, shape, &|p| [p[0] - x0, p[1] - y0]), rgb(color), 1.0);
    Pic { canvas, rect: [x0, y0, w as f64, h as f64] }
}
