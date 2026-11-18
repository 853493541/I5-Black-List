//! A holographic panel's edge (cyber._chrome) and ease_back from love_scenes/draw.py.

use super::canvas::{col, Canvas, Paint};
use super::hud::sq_line;
use super::text::{Face, Type};
use super::{CYAN, MAGENTA};
use crate::draw::{hex, Pt};

pub fn ease_back(k: f64, s: f64) -> f64 {
    let k = k.clamp(0.0, 1.0);
    1.0 + (s + 1.0) * (k - 1.0).powi(3) + s * (k - 1.0).powi(2)
}

/// A panel's edge: a faint pane with two corners cut, a fine outline, bright corner brackets, the
/// title bar's rules and ticks along its foot.
pub fn chrome(c: &mut Canvas, b: [f64; 4], u: f64, ty: &Type, title: &str, tag: &str, mirror: bool) {
    let k = 14.0 * u;
    let (l, t, r, bt) = (b[0], b[1], b[0] + b[2], b[1] + b[3]);
    let corners: Vec<Pt> = if mirror {
        vec![[l, t], [r - k, t], [r, t + k], [r, bt], [l + k, bt], [l, bt - k]]
    } else {
        vec![[l + k, t], [r, t], [r, bt - k], [r - k, bt], [l, bt], [l, t + k]]
    };
    let cy = hex(CYAN);
    c.poly(&corners, &Paint::Linear([l, t], [l, bt], vec![(0.0, cy, 0.07), (1.0, cy, 0.025)]));
    let mut ring = corners.clone();
    ring.push(corners[0]);
    c.stroke(&ring, 0.9 * u, &col(CYAN, 0.32), false);
    let n = corners.len();
    for i in 0..n {
        let corner = corners[i];
        let mut path = Vec::new();
        for (j, other) in [corners[(i + n - 1) % n], corners[(i + 1) % n]].into_iter().enumerate() {
            let d = (other[0] - corner[0]).hypot(other[1] - corner[1]);
            let d = if d == 0.0 { 1.0 } else { d };
            let reach = (26.0 * u).min(d * 0.45) / d;
            let end = [corner[0] + (other[0] - corner[0]) * reach, corner[1] + (other[1] - corner[1]) * reach];
            if j == 0 {
                path.extend([end, corner]);
            } else {
                path.push(end);
            }
        }
        c.stroke(&path, 2.0 * u, &col(CYAN, 0.95), false);
    }
    ty.draw(c, Face::Title, [l + 22.0 * u, t + 16.0 * u], title, "#e9fdff", 0.95);
    ty.draw(c, Face::Title, [r - 22.0 * u - ty.advance(Face::Title, tag), t + 16.0 * u], tag, MAGENTA, 0.95);
    let y = t + 23.0 * u;
    sq_line(c, [l + 14.0 * u, y], [r - 14.0 * u, y], 0.8 * u, &col(CYAN, 0.4));
    c.line([l + 14.0 * u, y], [l + 70.0 * u, y], 2.2 * u, &col(CYAN, 0.95), false);
    c.line([r - 40.0 * u, y], [r - 14.0 * u, y], 2.2 * u, &col(MAGENTA, 0.95), false);
    let start = if mirror { r - 150.0 * u } else { l + 40.0 * u };
    for i in 0..14 {
        let x = start + f64::from(i) * 8.0 * u;
        sq_line(c, [x, bt - 5.0 * u], [x, bt - if i % 4 == 0 { 9.0 } else { 7.0 } * u], u, &col(CYAN, 0.6));
    }
}

