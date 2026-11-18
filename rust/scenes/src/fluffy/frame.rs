//! What 毛茸茸 draws at t seconds (fluffy.py's paint and _cat_pop), and the two full-frame layers it
//! works out on the CPU while they change: the page (the paper band revealed behind the pens, the
//! frame's lines) and the doodles.

use std::f64::consts::PI;

use super::lines::{along, glide, interp, linspace, normals, stroke, Line};
use super::pixels::{coverage, Canvas, Shape};
use super::sprite::{layer, place, sprite, Affine, Clip};
use super::{rgb, Fluffy, CHALK, INK, MINT};
use crate::draw::{ease_in, ease_out, win, Pt};
use crate::prim::Frame;
use crate::pyrand::PyRandom;

const PEN: (f64, f64) = (0.1, 1.4);
const LAG: f64 = 0.12;

fn ease_back(k: f64, s: f64) -> f64 {
    let k = k.clamp(0.0, 1.0) - 1.0;
    1.0 + (s + 1.0) * k.powi(3) + s * k * k
}

fn spring(seconds: f64, freq: f64, damp: f64) -> f64 {
    if seconds <= 0.0 {
        return 1.0;
    }
    (-damp * seconds).exp() * (2.0 * PI * freq * seconds).cos()
}

/// _frame_lines: one pen's half of the frame, the ink line and a lighter one inside it, lifted
/// twice, stopping short of the gap.
pub fn frame_lines(route: &[Pt], side: f64, rnd: &mut PyRandom, u: f64, gap: [f64; 4]) -> [Line; 2] {
    let at = along(route);
    let main = Line::new(vec![stroke(route, &at, 3.0 * u, rnd, 1.1 * u, 2.0 * u, 14.0 * u)], INK, 4.0 * u);
    let inner: Vec<Pt> = route.iter().zip(normals(route, false)).map(|(p, n)| [p[0] + n[0] * side * 6.5 * u, p[1] + n[1] * side * 6.5 * u]).collect();
    let last_y = route[route.len() - 1][1];
    let mid = gap[0] + gap[2] / 2.0;
    let stop = inner.iter().position(|p| p[1] > last_y - 30.0 * u && (p[0] - mid).abs() < gap[2] / 2.0 + 34.0 * u).unwrap_or(inner.len());
    let lifts = [rnd.uniform(0.25, 0.4) * stop as f64, rnd.uniform(0.62, 0.75) * stop as f64];
    let mut strokes = Vec::new();
    let mut begin = 0usize;
    for cut in [lifts[0], lifts[1], stop as f64] {
        let end = cut as usize;
        if end > begin + 6 {
            strokes.push(stroke(&inner[begin..end], &at[begin..end], 1.7 * u, rnd, 0.8 * u, 10.0, 24.0));
        }
        begin = end + (4.0 * u / 2.5) as usize + 1;
    }
    [main, Line::new(strokes, CHALK, 4.0 * u)]
}

/// _ring_stops: each binder ring's height, and when it pops on, just after the pen passes it.
pub fn ring_stops(route: &[Pt], x: f64, top: f64, bottom: f64, step: f64) -> Vec<(f64, f64)> {
    let at = along(route);
    let count = (((bottom - top) / step) as usize + 1).max(1);
    let ks = linspace(0.0, 1.0, 200);
    let glided: Vec<f64> = ks.iter().map(|&k| glide(k)).collect();
    (0..count)
        .map(|k| {
            let y = top + (bottom - top) * k as f64 / (count.max(2) - 1) as f64;
            let near = (0..route.len()).min_by(|&a, &b| {
                let d = |i: usize| (route[i][0] - x).hypot(route[i][1] - y);
                d(a).total_cmp(&d(b))
            });
            let share = at[near.unwrap_or(0)] / at[at.len() - 1];
            (y, PEN.0 + (PEN.1 - PEN.0) * interp(share, &glided, &ks) + 0.04)
        })
        .collect()
}

/// A frame: its shapes and pictures, and which page and doodles its two layers show.
pub struct Shot {
    pub frame: Frame,
    /// How far the pen and the lighter line have drawn (1, 1: the finished page).
    pub page: [f64; 2],
    pub doodles: [f64; 2],
}

impl Fluffy {
    /// Everything drawn at t seconds over the lobby.
    pub fn paint(&self, t: f64) -> Shot {
        let screen = [self.width, self.height];
        let u = self.u;
        let mut f = Frame::new();
        layer(&mut f, 0, screen, 1.0);
        let a = win(t, 0.0, 0.3) * (1.0 - ease_in(win(t, 4.3, 5.0)));
        let drawn = glide(win(t, PEN.0, PEN.1));
        let page = if drawn >= 1.0 && t >= PEN.1 + LAG { [1.0, 1.0] } else { [drawn, glide(win(t, PEN.0 + LAG, PEN.1 + LAG))] };
        let doodles = [0, 1].map(|i| {
            let (line, start, end) = &self.doodles[i];
            line.length * glide(win(t, *start, *end))
        });
        if a <= 0.0 {
            return Shot { frame: f, page, doodles };
        }
        f.opacity = a;
        layer(&mut f, 1, screen, a);
        if page[0] < 1.0 || page[1] < 1.0 {
            for lines in &self.pens {
                if let Some(h) = lines[0].head(lines[0].length * drawn) {
                    f.soft_dot(h[0], h[1], 16.0 * u, MINT, 0.7);
                    f.star(h[0], h[1], 9.0 * u, [1.0; 3], 1.0, 0.14);
                }
            }
        }
        for &(y, when) in &self.rings {
            let k = win(t, when, when + 0.35);
            if k > 0.0 {
                place(&mut f, &self.atlas, self.ring.0, self.ring.1, [self.width - self.right, y], 0.0, ease_back(k, 2.4), a, screen);
            }
        }
        layer(&mut f, 2, screen, a);
        for (index, &(x, y, r, id, rect, when)) in self.stars.iter().enumerate() {
            let k = win(t, when, when + 0.45);
            if k <= 0.0 {
                continue;
            }
            let i = index as f64;
            let twinkle = 1.0 + 0.09 * (2.7 * (t - when) + i * 1.7).sin();
            let gone = ease_in(win(t, 3.95 + 0.04 * i, 4.45 + 0.04 * i));
            let angle = 35.0 * (1.0 - ease_out(k)) + 6.0 * (t * 0.9 + i).sin() - 90.0 * gone;
            place(&mut f, &self.atlas, id, rect, [x, y], angle, ease_back(k, 2.2) * twinkle * (1.0 - gone), a, screen);
            let glint = (PI * win((t - when - 0.6 - i * 0.37).rem_euclid(2.3), 0.0, 0.5)).sin();
            if glint > 0.02 && t > when + 0.6 {
                let (gx, gy) = (x + r * 0.95, y - r * 0.95);
                f.soft_dot(gx, gy, r * 0.9, "#ffffff", 0.5 * glint);
                f.star(gx, gy, r * 0.75 * glint, [1.0; 3], glint, 0.13);
            }
        }
        for &[x, y, r, when] in &self.sparkles {
            let k = (PI * win(t, when, when + 0.6)).sin();
            if k > 0.02 {
                f.soft_dot(x, y, r * 2.2, MINT, 0.45 * k);
                f.star(x, y, r * (0.6 + 0.6 * k), [1.0; 3], k, 0.12);
            }
        }
        for trail in &self.trails {
            for &(at, when) in trail {
                let k = win(t, when, when + 0.12);
                let fade = 1.0 - ease_in(win(t, when + 1.7, when + 2.2));
                if k > 0.0 && fade > 0.0 {
                    place(&mut f, &self.atlas, self.paw.0, self.paw.1, at, 0.0, 1.3 - 0.3 * ease_out(k), a * ease_out(k) * fade * 0.92, screen);
                }
            }
        }
        for index in 0..self.cats.len() {
            if t > self.cats[index].when {
                let i = index as f64;
                let duck = 1.0 - ease_in(win(t, 4.05 + 0.06 * i, 4.55 + 0.06 * i));
                self.cat_pop(&mut f, t, index, duck, a);
            }
        }
        let drop = ease_back(win(t, 0.05, 0.6), 1.6) - ease_in(win(t, 4.2, 4.75)) * 1.2;
        if drop > 0.0 {
            let swing = if t > 0.5 { 4.0 * spring(t - 0.5, 1.4, 3.0) } else { 0.0 };
            let (id, rect, c) = self.tab;
            place(&mut f, &self.atlas, id, rect, [c[0], c[1] - 60.0 * u * (1.0 - drop)], swing, 1.0, a, screen);
        }
        Shot { frame: f, page, doodles }
    }

    /// _cat_pop: a cat peeking up over the frame, squashing as it lands, paws hopping onto the edge,
    /// breathing, blinking, swishing its tail; at the end it ducks back down.
    fn cat_pop(&self, f: &mut Frame, t: f64, index: usize, duck: f64, a: f64) {
        let screen = [self.width, self.height];
        let c = &self.cats[index];
        let (u, i, when, size) = (self.u, index as f64, c.when, c.size);
        let face = if t < when + 0.9 {
            0
        } else if (t - when - 0.9 - i * 0.53).rem_euclid(2.4) < 0.14 {
            1
        } else {
            let flick = (t - when - 1.4 - i * 0.71).rem_euclid(3.1);
            if flick < 0.09 || (0.17..0.26).contains(&flick) { 2 } else { 0 }
        };
        let (head, rect) = c.faces[face];
        let rise = ease_out(win(t, when, when + 0.42)) * duck;
        if rise <= 0.0 {
            return;
        }
        let base = Affine::ID.translate(c.base[0], c.base[1]).rotate(c.turn);
        let clip = Some(Clip(base, [-size * 1.5, -size * 2.0, size * 3.0, size * 2.0]));
        if c.tail != 0.0 {
            let (id, tb) = c.tail_pic;
            let up = ease_out(win(t, when + 0.2, when + 0.62)) * duck;
            let swish = 14.0 * (2.1 * (t - when) + i).sin() * win(t, when + 0.5, when + 1.2);
            let m = base.translate(c.tail * 0.66 * size, (1.0 - up) * tb[3]).rotate(c.tail * (swish - 6.0)).scale(c.tail, 1.0);
            sprite(f, &self.atlas, id, tb, m, a, clip, screen);
        }
        let land = if t > when + 0.42 { 0.09 * spring(t - when - 0.42, 2.0, 6.0) } else { 0.0 };
        let breath = 0.012 * (2.4 * t + i * 1.3).sin();
        let m = base.translate(0.0, (1.0 - rise) * -rect[1]).scale(1.0 + 0.6 * land, 1.0 - land + breath);
        sprite(f, &self.atlas, head, rect, m, a, clip, screen);
        sprite(f, &self.atlas, c.edge.0, c.edge.1, Affine::ID, a, None, screen);
        let (paws, pb) = c.paws;
        let hop = ease_back(win(t, when + 0.3, when + 0.48), 2.5) * (1.0 - win(t, 3.95 + 0.06 * i, 4.05 + 0.06 * i));
        if hop > 0.0 {
            sprite(f, &self.atlas, paws, pb, base.translate(0.0, (1.0 - hop) * pb[3]), a, clip, screen);
        }
        let burst = win(t, when + 0.25, when + 0.65);
        if 0.0 < burst && burst < 1.0 {
            let reach = -rect[1] * (0.95 + 0.25 * ease_out(burst));
            for angle in [-50.0f64, -15.0, 20.0] {
                let r = (angle - 90.0).to_radians();
                let (inner, outer) = (reach, reach + 12.0 * u * (1.0 - 0.5 * burst));
                let line = [base.map([r.cos() * inner, r.sin() * inner]), base.map([r.cos() * outer, r.sin() * outer])];
                f.stroke(&line, 2.2 * u, CHALK, 0.9 * (1.0 - burst));
            }
        }
    }

    fn fill(&self, canvas: &mut Canvas, shape: &Shape, color: &str, alpha: f64) {
        if !shape.is_empty() {
            canvas.fill(&coverage(canvas.w, canvas.h, shape, &|p| p), rgb(color), alpha);
        }
    }

    /// The page layer: the paper band, opening behind the two pens as they go round from the top
    /// middle, and the frame's lines as far as they have come.
    pub fn page(&self, [drawn, follow]: [f64; 2]) -> Canvas {
        let (w, h) = (self.width.ceil() as usize, self.height.ceil() as usize);
        let mut canvas = Canvas::new(w, h);
        if drawn > 0.0 {
            for (r, strip) in &self.band {
                for y in 0..r[3] {
                    canvas.px[(r[1] + y) * w + r[0]..][..r[2]].copy_from_slice(&strip.px[y * r[2]..(y + 1) * r[2]]);
                }
            }
        }
        if drawn > 0.0 && (drawn < 1.0 || follow < 1.0) {
            let middle = [self.width / 2.0, self.height / 2.0];
            let mut turn = [-90.0f64, -90.0];
            for (index, lines) in self.pens.iter().enumerate() {
                match lines[0].head(lines[0].length * drawn) {
                    None => turn[index] = if index == 0 { -270.0 } else { 90.0 },
                    Some(head) if (head[0] < middle[0]) == (index == 0) => {
                        let angle = (head[1] - middle[1]).atan2(head[0] - middle[0]).to_degrees();
                        turn[index] = if index == 0 && angle > 0.0 { angle - 360.0 } else { angle };
                    }
                    Some(_) => {}
                }
            }
            let reach = self.width.hypot(self.height);
            let mut slice = vec![middle];
            slice.extend(linspace(turn[0], turn[1], 48).iter().map(|k| [middle[0] + reach * k.to_radians().cos(), middle[1] + reach * k.to_radians().sin()]));
            let cover = coverage(w, h, &vec![(1.0, slice)], &|p| p);
            for (px, c) in canvas.px.iter_mut().zip(&cover.v) {
                let c = (c * 255.0).round() / 255.0;
                *px = px.map(|v| (f32::from(v) * c).round() as u8);
            }
        }
        for lines in &self.pens {
            self.fill(&mut canvas, &lines[0].shape(lines[0].length * drawn), lines[0].color, 1.0);
            self.fill(&mut canvas, &lines[1].shape(lines[1].length * follow), lines[1].color, 1.0);
        }
        canvas
    }

    /// The doodles layer: each loopy doodle drawn as far as its pen has come.
    pub fn doodles(&self, reach: [f64; 2]) -> Canvas {
        let mut canvas = Canvas::new(self.width.ceil() as usize, self.height.ceil() as usize);
        for ((line, _, _), r) in self.doodles.iter().zip(reach) {
            self.fill(&mut canvas, &line.shape(r), line.color, 0.92);
        }
        canvas
    }
}
