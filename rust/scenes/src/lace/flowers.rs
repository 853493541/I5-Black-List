//! What 玫瑰花边 draws its flowers with: lace.py's pale rose and leaf, and ui_overlay's flower, knot of
//! flowers and sparkle, line for line.

use crate::draw::{hex, Pt};
use crate::lace::prim::{solid, stops, Frame, Paint, Path, Xf};

/// ui_overlay._FLOWER_TONES: (tip, middle, heart).
pub const PINK: [&str; 3] = ["#fff0f6", "#ff9cc4", "#ff6fa6"];
pub const BLUE: [&str; 3] = ["#f2f9ff", "#a8d6ff", "#6fb4ff"];

/// A filled path, then its outline with a pen, as QPainter.drawPath does with a brush and a pen.
fn fill_and_stroke(f: &mut Frame, path: &Path, fill: &Paint, pen: &Paint, width: f64) {
    for sub in &path.subs {
        f.poly(sub, fill);
    }
    f.stroke_path(path, width, pen, true, 0);
}

fn grad(xf: &Xf, a: Pt, b: Pt, list: &[(f64, &str, f64)]) -> Paint {
    Paint::Linear(xf.map(a), xf.map(b), stops(list))
}

/// An ellipse as Qt draws it, closed, centred on c with radii rx, ry.
fn ellipse(c: Pt, rx: f64, ry: f64) -> Path {
    let n = 96;
    let mut path = Path::new([c[0] + rx, c[1]]);
    for i in 1..n {
        let a = -(i as f64) / n as f64 * std::f64::consts::TAU;
        path.line_to([c[0] + rx * a.cos(), c[1] + ry * a.sin()]);
    }
    path.close();
    path
}

/// lace._rose: a pale rose seen from above, rings of rounded petals, deeper toward a closed bud.
pub fn rose(f: &mut Frame, x: f64, y: f64, r: f64, turn: f64) {
    if r < 0.5 {
        return;
    }
    let base = Xf::at(x, y).rotate(turn);
    let glow = stops(&[(0.0, "#ffb6cf", 0.35), (1.0, "#ffb6cf", 0.0)]);
    f.circle(x, y, r * 1.9, &Paint::Radial([x, y], r * 1.9, glow));
    let rings = [
        (5, 1.0, 0.62, "#ffe4ee", "#f7a9c4", 0.0),
        (5, 0.74, 0.5, "#ffd0e0", "#ee8fb2", 36.0),
        (4, 0.5, 0.42, "#ffbcd3", "#e07aa0", 15.0),
        (3, 0.3, 0.36, "#f9a5c3", "#cf6690", 60.0),
    ];
    let pen = solid("#fff6f9", 0.75);
    for (count, reach, width, tip, deep, offset) in rings {
        for i in 0..count {
            let xf = base.rotate(offset + f64::from(i) * 360.0 / f64::from(count));
            let shade = grad(&xf, [0.0, 0.0], [0.0, -r * reach], &[(0.0, deep, 1.0), (1.0, tip, 1.0)]);
            let mut petal = Path::new([0.0, 0.0]);
            petal.cubic_to([-r * width, -r * reach * 0.35], [-r * width * 0.9, -r * reach], [0.0, -r * reach]);
            petal.cubic_to([r * width * 0.9, -r * reach], [r * width, -r * reach * 0.35], [0.0, 0.0]);
            fill_and_stroke(f, &petal.mapped(&xf), &shade, &pen, (r * 0.035).max(0.7));
        }
    }
    f.circle(x, y, r * 0.1, &solid("#c85d86", 1.0));
}

/// lace._leaf.
pub fn leaf(f: &mut Frame, x: f64, y: f64, length: f64, angle: f64) {
    let xf = Xf::at(x, y).rotate(angle);
    let mut leaf = Path::new([0.0, 0.0]);
    leaf.quad_to([length * 0.5, -length * 0.32], [length, 0.0]);
    leaf.quad_to([length * 0.5, length * 0.32], [0.0, 0.0]);
    fill_and_stroke(f, &leaf.mapped(&xf), &solid("#f6d6c4", 0.6), &solid("#fff1e0", 0.7), 1.0);
}

/// ui_overlay._flower: five soft petals, deep at the heart and pale at the tips, in a glow of their own.
pub fn flower(f: &mut Frame, x: f64, y: f64, r: f64, tone: [&str; 3], turn: f64, halo: f64) {
    if r < 0.5 {
        return;
    }
    let [light, mid, deep] = tone;
    let base = Xf::at(x, y).rotate(turn);
    if halo > 0.0 {
        let glow = stops(&[(0.0, mid, 0.45), (1.0, mid, 0.0)]);
        f.circle(x, y, r * halo, &Paint::Radial([x, y], r * halo, glow));
    }
    let pen = solid("#ffffff", 0.55);
    for i in 0..5 {
        let xf = base.rotate(f64::from(i) * 72.0);
        let petal = grad(&xf, [0.0, 0.0], [0.0, -r * 1.05], &[(0.0, deep, 1.0), (0.55, mid, 1.0), (1.0, light, 1.0)]);
        let shape = ellipse([0.0, -r * 1.05 + r * 0.41], r * 0.36, r * 0.41);
        fill_and_stroke(f, &shape.mapped(&xf), &petal, &pen, (r * 0.05).max(0.6));
    }
    f.circle(x, y, r * 0.2, &solid("#fff6d8", 1.0));
}

/// ui_overlay._knot: a knot of flowers, two pink and two blue, overlapping.
pub fn knot(f: &mut Frame, x: f64, y: f64, size: f64) {
    for (dx, dy, scale, which, turn) in [(-0.55, 0.15, 0.62, PINK, 12.0), (0.5, 0.05, 0.55, BLUE, 40.0), (0.0, -0.35, 0.75, PINK, 64.0), (0.1, 0.55, 0.38, BLUE, 25.0)] {
        flower(f, x + dx * size, y + dy * size, scale * size, which, turn, 2.2);
    }
}

/// ui_overlay._sparkle: a four-point glint with a small halo.
pub fn sparkle(f: &mut Frame, x: f64, y: f64, r: f64, alpha: f64) {
    if alpha <= 0.01 || r < 0.5 {
        return;
    }
    // QColor(255, 240, 250, round(140 * alpha)): the alpha is a whole byte.
    let a = (140.0 * alpha).round_ties_even() / 255.0;
    let halo = vec![(0.0, [1.0, 240.0 / 255.0, 250.0 / 255.0], a), (1.0, hex("#ffc8e6"), 0.0)];
    f.circle(x, y, r * 1.6, &Paint::Radial([x, y], r * 1.6, halo));
    f.star(x, y, r, [1.0; 3], alpha, 0.16);
}
