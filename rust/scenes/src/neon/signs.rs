//! The billboards' pictures (neon._sign_art): made-up glyphs, or the screen's ring and bars, lit in
//! neon with their bloom, framed, and the panel's hologram light in scan lines.

use super::raster::{blur, glow, Img, Light, Pt, Shape};
use super::towers::{over, Tower};
use super::{rgb, Rect, CYAN, MAGENTA};
use crate::pyrand::PyRandom;

fn line(a: Pt, b: Pt, half: f64, square: bool) -> Vec<Shape> {
    vec![Shape::Line { a, b, half, reach: if square { half } else { 0.0 }, round: false }]
}

/// neon._glyph: three or four strokes on a three by three grid, each its own line.
fn glyph(cell: Rect, rnd: &mut PyRandom, half: f64, out: &mut Vec<Vec<Shape>>) {
    let (x0, x1, y0, y1) = (cell[0], cell[0] + cell[2], cell[1], cell[1] + cell[3]);
    let (xm, ym) = (cell[0] + cell[2] / 2.0, cell[1] + cell[3] / 2.0);
    let strokes = [
        (x0, y0, x1, y0), (x0, ym, x1, ym), (x0, y1, x1, y1), (x0, y0, x0, y1), (xm, y0, xm, y1), (x1, y0, x1, y1),
        (x0, y0, xm, ym), (x1, y0, x0, y1), (xm, ym, x1, y1), (x0, ym, xm, y1), (xm, y0, x1, ym),
    ];
    let k = rnd.choice(&[3, 3, 4]);
    // random.sample(strokes, k), by its pool method.
    let mut pool = strokes.to_vec();
    let n = pool.len();
    for i in 0..k {
        let j = rnd.below(n - i);
        let s = pool[j];
        pool[j] = pool[n - i - 1];
        out.push(line([s.0, s.1], [s.2, s.3], half, true));
    }
}

/// The area the sign's pictures cover, and its pictures (two to take turns; the ticker one long strip).
pub fn art(t: &Tower, panel: Rect, u: f64) -> (Rect, Vec<Img>) {
    let tint = if t.show == "screen" { CYAN } else if t.side < 0 { MAGENTA } else { CYAN };
    let edge = if tint == MAGENTA { CYAN } else { MAGENTA };
    let pad = 9.0 * u;
    let ticker = t.show == "ticker";
    let area = [panel[0] - pad, panel[1] - pad, panel[2] + 2.0 * pad + if ticker { panel[2] * 2.2 } else { 0.0 }, panel[3] + 2.0 * pad];
    let mut rnd = PyRandom::new(t.seed * 7);
    let (pcx, pcy) = (panel[0] + panel[2] / 2.0, panel[1] + panel[3] / 2.0);
    let half = 0.9 * u;
    let mut out = Vec::new();
    for variant in 0..if ticker { 1 } else { 2 } {
        let mut strokes: Vec<Vec<Shape>> = Vec::new();
        if t.show == "screen" {
            let r = panel[3] * 0.27;
            let at = [pcx, panel[1] + panel[3] * 0.38];
            strokes.push(vec![Shape::Ring { c: at, r, half }]);
            let d = r * if variant == 1 { 0.5 } else { 0.62 };
            let q = [[at[0], at[1] - d], [at[0] + d * 0.7, at[1]], [at[0], at[1] + d], [at[0] - d * 0.7, at[1]]];
            strokes.push((0..4).flat_map(|i| line(q[i], q[(i + 1) % 4], half, true)).collect());
            for row in 0..2 {
                let y = panel[1] + panel[3] * (0.78 + 0.12 * f64::from(row));
                let span = panel[2] * rnd.uniform(0.35, 0.75);
                strokes.push(line([pcx - span / 2.0, y], [pcx + span / 2.0, y], half, true));
            }
        } else {
            let side = panel[3] * 0.6;
            let count = if ticker { (area[2] / (side * 1.55)) as usize } else { (((panel[2] - side * 0.6) / (side * 1.4)) as usize).max(2) };
            let spacing = if ticker { area[2] } else { panel[2] } / count as f64;
            let start = if ticker { area[0] } else { panel[0] };
            for i in 0..count {
                let cell = [start + spacing * (i as f64 + 0.5) - side / 2.0, pcy - side / 2.0, side, side];
                if ticker && i % 4 == 3 {
                    let (cx, cy) = (cell[0] + side / 2.0, cell[1] + side / 2.0);
                    strokes.push(vec![Shape::Rect(cx - u - half, cy - u - half, 2.0 * u + 2.0 * half, 2.0 * u + 2.0 * half)]);
                    continue;
                }
                glyph(cell, &mut rnd, half, &mut strokes);
            }
        }
        let fh = 0.55 * u;
        let frame: Vec<Vec<Shape>> = if ticker {
            vec![line([area[0], panel[1]], [area[0] + area[2], panel[1]], fh, true), line([area[0], panel[1] + panel[3]], [area[0] + area[2], panel[1] + panel[3]], fh, true)]
        } else {
            let i = 0.6 * u;
            let (l, tp, r, b) = (panel[0] + i, panel[1] + i, panel[0] + panel[2] - i, panel[1] + panel[3] - i);
            vec![[[l, tp], [r, tp]], [[r, tp], [r, b]], [[r, b], [l, b]], [[l, b], [l, tp]]].into_iter().flat_map(|[a, b]| line(a, b, fh, true)).map(|s| vec![s]).collect()
        };
        let fill = if ticker { [area[0], panel[1], area[2], panel[3]] } else { panel };
        let g = over(area, &strokes);
        let f = over(area, &frame);
        let inside = over(area, &[vec![Shape::Rect(fill[0], fill[1], fill[2], fill[3])]]);
        let (g1, g3, g8, f1, f4) = (blur(&g, 1.0), blur(&g, 3.0), blur(&g, 8.0), blur(&f, 1.0), blur(&f, 4.0));
        let (tc, ec) = (rgb(tint), rgb(edge));
        let sy = area[3] as f32 / g.h as f32;
        let light: Light = (0..g.w * g.h)
            .map(|n| {
                let y = area[1] as f32 + ((n / g.w) as f32 + 0.5) * sy;
                let scan = if ((y - area[1] as f32) / (2.2 * u) as f32).rem_euclid(1.0) < 0.5 { 1.0 } else { 0.55 };
                let a = g1.v[n] * 1.4 + g3.v[n] * 1.3 + g8.v[n];
                let gp = g.v[n].powf(1.5);
                let b = f1.v[n] * 0.8 + f4.v[n] * 0.5;
                let fp = f.v[n].powf(1.5);
                std::array::from_fn(|q| tc[q] * a + gp * (tc[q] * 0.5 + 0.75) + b * ec[q] + fp * (ec[q] * 0.5 + 0.5) + inside.v[n] * scan * 0.16 * tc[q])
            })
            .collect();
        out.push(glow(g.w, g.h, &light));
    }
    (area, out)
}

