//! 星河许愿 Starry Wish, ported from blacklist_detect/love_scenes/stars.py line for line: a dusk
//! sky, a heart drawn in stars by two wishing stars, a crescent moon, shooting stars, gold dust.

use std::f64::consts::PI;

use crate::draw::{clamp, ease_in, ease_in_out, ease_out, heart_points, hex, mix, partial, win, Pt};
use crate::prim::{solid, stops, Frame, Paint};
use crate::pyrand::PyRandom;

pub const DURATION: f64 = 5.0;
const SILVER: &str = "#eef0ff";
const LILAC: &str = "#b9a3ff";
const GOLD: &str = "#f6d68a";
const WHITE: [f32; 3] = [1.0, 1.0, 1.0];
/// love_scenes.DESIGN: the size a scene's unit is measured against.
const DESIGN: [f64; 2] = [1635.0, 848.0];

type Rect = [f64; 4];

fn contains(r: Rect, x: f64, y: f64) -> bool {
    r[0] <= x && x <= r[0] + r[2] && r[1] <= y && y <= r[1] + r[3]
}

struct Sky {
    x: f64,
    y: f64,
    r: f64,
    born: f64,
    rate: f64,
    color: &'static str,
}

pub struct Stars {
    pub width: f64,
    pub height: f64,
    /// The bare area round the button, x, y, w, h.
    pub gap: Rect,
    u: f64,
    sky: Vec<Sky>,
    dust: Vec<[f64; 6]>,
    meteors: [(f64, Pt, Pt); 4],
}

impl Stars {
    /// love_scenes.sample_stage(width, height): the sample lobby's button gap at this size.
    pub fn sample(width: f64, height: f64) -> Self {
        let s = width / DESIGN[0];
        let keep = [549.0 * s, 749.0 * s, 556.0 * s, 94.0 * s];
        let gap = [keep[0] - 28.0 * s, keep[1] - 30.0 * s, keep[2] + 56.0 * s, height - keep[1] + 30.0 * s];
        Self::new(width, height, gap)
    }

    pub fn new(width: f64, height: f64, gap: Rect) -> Self {
        let u = (width / DESIGN[0]).min(height / DESIGN[1]);
        let mut rnd = PyRandom::new(31);
        let names = [width * 0.13, height * 0.29, width * 0.81, height * 0.55];
        let title = [width * 0.38, height * 0.07, width * 0.3, height * 0.18];
        let mut sky = Vec::new();
        while sky.len() < 150 {
            let (x, y) = (rnd.uniform(0.0, width), rnd.uniform(0.0, height));
            if contains(names, x, y) || contains(title, x, y) || contains(gap, x, y) {
                continue;
            }
            if y > height * 0.35 && width * 0.16 < x && x < width * 0.84 {
                continue;
            }
            let r = if rnd.random() < 0.45 { rnd.uniform(0.7, 2.1) } else { rnd.uniform(0.35, 0.8) };
            let (born, rate) = (rnd.uniform(0.2, 1.4), rnd.uniform(1.5, 4.0));
            let color = rnd.choice(&[SILVER, SILVER, LILAC, GOLD]);
            sky.push(Sky { x, y, r: r * u, born, rate, color });
        }
        let (w, h) = (width, height);
        let meteors = [
            (1.3, [w * 0.34, -h * 0.02], [w * 0.16, h * 0.24]),
            (2.3, [w * 0.97, h * 0.0], [w * 0.74, h * 0.27]),
            (2.85, [w * 0.2, -h * 0.03], [w * 0.04, h * 0.2]),
            (3.25, [w * 0.6, -h * 0.03], [w * 0.46, h * 0.06]),
        ];
        // 6.28 as the Python scene has it, not TAU: the same numbers come out of the same seed.
        #[allow(clippy::approx_constant)]
        let dust = (0..36)
            .map(|_| {
                let born = rnd.uniform(0.4, 3.4);
                let x = if rnd.random() < 0.5 { rnd.uniform(0.01, 0.13) } else { rnd.uniform(0.87, 0.99) } * w;
                [born, x, rnd.uniform(-0.05, 0.6) * h, rnd.uniform(16.0, 40.0) * u, rnd.uniform(1.2, 2.6) * u, rnd.uniform(0.0, 6.28)]
            })
            .collect();
        Self { width, height, gap, u, sky, dust, meteors }
    }

    /// The Milky Way, drawn once at full strength into its own picture (the Python scene's Wash).
    pub fn milky_way(&self) -> Frame {
        let (width, height, u) = (self.width, self.height, self.u);
        let title = [width * 0.38, height * 0.07, width * 0.3, height * 0.18];
        let mut f = Frame::new();
        let mut rnd = PyRandom::new(52);
        let along = |k: f64| [width * k, height * (0.2 - 0.2 * (PI * k).sin())];
        for _ in 0..46 {
            let c = along(rnd.random());
            let r = rnd.uniform(60.0, 130.0) * u;
            let centre = [c[0], c[1] + rnd.gauss(0.0, 18.0) * u];
            let color = rnd.choice(&["#9d8cff", "#7fa8ff", "#e6a2ff", "#b8b2ff"]);
            let a = rnd.uniform(0.04, 0.08);
            let paint = Paint::Radial(centre, r, vec![(0.0, hex(color), a), (1.0, hex("#9d8cff"), 0.0)]);
            f.circle(centre[0], centre[1], r, &paint);
        }
        for _ in 0..520 {
            let c = along(rnd.random());
            let (x, y) = (c[0] + rnd.gauss(0.0, 8.0) * u, c[1] + rnd.gauss(0.0, 26.0) * u);
            if y < 0.0 {
                continue;
            }
            let alpha = rnd.uniform(0.25, 0.8) * if contains(title, x, y) { 0.3 } else { 1.0 };
            let r = rnd.uniform(0.35, 1.0) * u;
            f.circle(x, y, r, &solid("#ffffff", alpha));
        }
        f
    }

    /// Everything drawn at t seconds, over the lobby (layer 0) and with the Milky Way (layer 1).
    pub fn paint(&self, t: f64) -> Frame {
        let (width, height, u) = (self.width, self.height, self.u);
        let mut f = Frame::new();
        f.picture(0, [width, height], self.gap, 1.0);
        let leave = ease_in(win(t, 4.1, 5.0));
        f.opacity = win(t, 0.0, 0.35);
        self.dusk(&mut f, t, leave);
        f.picture(1, [width, height], self.gap, ease_out(win(t, 0.3, 1.4)) * (1.0 - leave));
        self.sky(&mut f, t, leave);
        self.moon(&mut f, t, [width - 150.0 * u, 100.0 * u], leave);
        self.star_heart(&mut f, t, [width * 0.118, height * 0.2], 190.0 * u);
        for (when, a, b) in self.meteors {
            self.meteor(&mut f, t - when, a, b);
        }
        self.dust(&mut f, t, 1.0 - leave);
        f
    }

    fn dusk(&self, f: &mut Frame, t: f64, leave: f64) {
        let (width, height, u) = (self.width, self.height, self.u);
        let a = ease_out(win(t, 0.0, 0.9)) * (1.0 - leave);
        if a <= 0.0 {
            return;
        }
        let top = height * 0.34;
        let band = stops(&[(0.0, "#130b3c", 0.7 * a), (0.5, "#2b1a6b", 0.3 * a), (1.0, "#3a2479", 0.0)]);
        f.rect(0.0, 0.0, width, top, &Paint::Linear([0.0, 0.0], [0.0, top], band));
        for x in [0.0, width] {
            let side = stops(&[(0.0, "#2a1a66", 0.3 * a), (1.0, "#2a1a66", 0.0)]);
            f.rect(0.0, 0.0, width, height, &Paint::Radial([x, height * 0.55], height * 0.75, side));
            let glow = stops(&[(0.0, "#b44aa8", 0.34 * a), (0.5, "#7a2e8e", 0.14 * a), (1.0, "#7a2e8e", 0.0)]);
            f.rect(0.0, 0.0, width, height, &Paint::Radial([x, height], 420.0 * u, glow));
        }
        for (cx, cy, r, color, alpha) in [(0.2, 0.04, 330.0, "#a58bff", 0.2), (0.84, 0.1, 280.0, "#ff8fd0", 0.15), (0.06, 0.3, 200.0, "#7f6bff", 0.12)] {
            let breathe = 1.0 + 0.06 * (t * 0.9 + cx * 9.0).sin();
            let cloud = stops(&[(0.0, color, alpha * a), (1.0, color, 0.0)]);
            f.rect(0.0, 0.0, width, height * 0.6, &Paint::Radial([width * cx, height * cy], r * u * breathe, cloud));
        }
    }

    fn sky(&self, f: &mut Frame, t: f64, leave: f64) {
        let u = self.u;
        for s in &self.sky {
            let a = ease_out(win(t, s.born * 0.6, s.born * 0.6 + 0.5)) * (1.0 - leave);
            if a <= 0.0 {
                continue;
            }
            let twinkle = 0.55 + 0.45 * (t * s.rate + s.x * 0.01).sin();
            f.soft_dot(s.x, s.y, s.r * 3.2, s.color, 0.45 * a * twinkle);
            if s.r > 1.7 * u {
                f.star(s.x, s.y, s.r * (2.4 + 1.6 * twinkle), WHITE, a * twinkle, 0.1);
            } else {
                f.circle(s.x, s.y, s.r * 0.6, &solid("#ffffff", 0.9 * a * twinkle));
            }
        }
    }

    fn star_heart(&self, f: &mut Frame, t: f64, centre: Pt, size: f64) {
        let u = self.u;
        let fade = 1.0 - ease_in_out(win(t, 4.05, 4.7));
        if fade <= 0.0 {
            return;
        }
        let size = size * (1.0 + 0.05 * (PI * win(t, 2.2, 2.5)).sin().max(0.0));
        let ring = heart_points(centre[0], centre[1], size, 120);
        let left: Vec<Pt> = ring[..=60].iter().rev().copied().collect();
        let mut right: Vec<Pt> = ring[60..].to_vec();
        right.push(ring[0]);
        let draw = ease_in_out(win(t, 0.5, 1.5));
        let filled = ease_out(win(t, 1.45, 2.1)) * fade;
        if filled > 0.0 {
            let inside = stops(&[(0.0, GOLD, 0.42 * filled), (0.55, LILAC, 0.24 * filled), (1.0, LILAC, 0.08 * filled)]);
            f.poly(&ring, &Paint::Radial([centre[0], centre[1] + size * 0.12], size * 0.62, inside));
        }
        for side in [left, right] {
            let trail = partial(&side, draw);
            if trail.len() < 2 {
                continue;
            }
            for (w, color, alpha) in [(16.0, LILAC, 0.06), (8.0, LILAC, 0.14), (3.4, SILVER, 0.38), (1.3, "#ffffff", 0.95)] {
                f.stroke(&trail, w * u, color, alpha * fade);
            }
            if 0.0 < draw && draw < 1.0 {
                let head = trail[trail.len() - 1];
                f.soft_dot(head[0], head[1], 20.0 * u, "#ffffff", 0.75);
                f.star(head[0], head[1], 13.0 * u, WHITE, 1.0, 0.12);
            }
        }
        let meet = (PI * win(t, 1.45, 2.05)).sin();
        if meet > 0.0 {
            let top = ring[0];
            f.soft_dot(top[0], top[1], 34.0 * u * meet, GOLD, 0.7 * meet);
            f.star(top[0], top[1], 26.0 * u * meet, WHITE, meet, 0.12);
        }
        for (index, when) in [(104, 2.7), (22, 3.25)] {
            let glint = (PI * win(t, when, when + 0.5)).sin() * fade;
            if glint > 0.0 {
                f.star(ring[index][0], ring[index][1], 14.0 * u * glint, WHITE, glint, 0.12);
            }
        }
    }

    fn moon(&self, f: &mut Frame, t: f64, centre: Pt, leave: f64) {
        let u = self.u;
        let rise = ease_out(win(t, 0.25, 1.4));
        let a = rise * (1.0 - leave);
        if a <= 0.0 {
            return;
        }
        let c = [centre[0], centre[1] + 40.0 * u * (1.0 - rise)];
        let r = 52.0 * u;
        let halo = stops(&[(0.0, GOLD, 0.34 * a), (0.4, "#e9b8ff", 0.10 * a), (1.0, "#e9b8ff", 0.0)]);
        f.circle(c[0], c[1], 180.0 * u, &Paint::Radial(c, 180.0 * u, halo));
        let disc = [c[0], c[1], r];
        let bite = [c[0] + r * 0.45, c[1] - r * 0.22, r * 0.86];
        let body = stops(&[(0.0, "#fffaf0", a), (0.6, "#fbe3a8", a), (1.0, "#e9bd6e", a)]);
        f.crescent(disc, bite, &Paint::Radial([c[0] - r * 0.5, c[1] + r * 0.1], r * 1.2, body));
        for (cx, cy, cr) in [(-0.55, 0.15, 0.13), (-0.35, 0.55, 0.09), (-0.7, -0.25, 0.08)] {
            let at = [c[0] + cx * r, c[1] + cy * r];
            let crater = stops(&[(0.0, "#d9a95c", 0.35 * a), (1.0, "#d9a95c", 0.0)]);
            f.crater([at[0], at[1], cr * r], disc, bite, &Paint::Radial(at, cr * r, crater));
        }
        for k in 0..3 {
            let angle = t * 1.6 + f64::from(k) * 2.1;
            let (x, y) = (c[0] + angle.cos() * r * 1.9, c[1] + angle.sin() * r * 1.1);
            f.star(x, y, (4.0 + 2.0 * (t * 4.0 + f64::from(k)).sin()) * u, WHITE, 0.8 * a, 0.12);
        }
    }

    fn meteor(&self, f: &mut Frame, age: f64, start: Pt, end: Pt) {
        let u = self.u;
        let span = 0.7;
        if age < 0.0 || age > span + 0.35 {
            return;
        }
        let k = ease_out(clamp(age / span));
        let head = [start[0] + (end[0] - start[0]) * k, start[1] + (end[1] - start[1]) * k];
        let (dx, dy) = (end[0] - start[0], end[1] - start[1]);
        let length = dx.hypot(dy).max(1e-9);
        let (ux, uy) = (dx / length, dy / length);
        let fade = 1.0 - clamp((age - span) / 0.35);
        let tail = 320.0 * u * (age / 0.25).min(1.0) * fade;
        let tail_end = [head[0] - ux * tail, head[1] - uy * tail];
        let (nx, ny) = (-uy, ux);
        for (w, alpha) in [(7.0 * u, 0.25), (2.2 * u, 0.95)] {
            let shape = [[head[0] + nx * w, head[1] + ny * w], tail_end, [head[0] - nx * w, head[1] - ny * w]];
            let streak = stops(&[(0.0, "#ffffff", alpha * fade), (0.3, GOLD, 0.6 * alpha * fade), (1.0, LILAC, 0.0)]);
            f.poly(&shape, &Paint::Linear(head, tail_end, streak));
        }
        f.soft_dot(head[0], head[1], 26.0 * u, "#fff4dc", 0.8 * fade);
        f.star(head[0], head[1], 14.0 * u, WHITE, fade, 0.12);
    }

    fn dust(&self, f: &mut Frame, t: f64, a: f64) {
        let u = self.u;
        let shade = mix(GOLD, "#ffffff", 0.6);
        for &[born, x, y, fall, r, phase] in &self.dust {
            let age = t - born;
            if age <= 0.0 || age > 3.2 {
                continue;
            }
            let fade = (age / 0.4).min(1.0) * ((3.2 - age) / 0.8).min(1.0) * a;
            let twinkle = 0.5 + 0.5 * (age * 5.0 + phase).sin();
            let (px, py) = (x + 8.0 * u * (age * 1.4 + phase).sin(), y + fall * age);
            f.soft_dot(px, py, r * 3.0, GOLD, 0.6 * fade);
            f.star(px, py, r * (1.0 + 1.6 * twinkle), shade, fade * twinkle, 0.12);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::Stars;

    #[test]
    fn lays_out_the_same_every_time() {
        let a = Stars::sample(1920.0, 1080.0);
        let b = Stars::sample(1920.0, 1080.0);
        assert_eq!(a.sky.len(), 150);
        assert_eq!(a.paint(1.5).prims.len(), b.paint(1.5).prims.len());
        assert_eq!(a.sky[0].x.to_bits(), b.sky[0].x.to_bits());
        assert!(a.milky_way().prims.len() > 46, "{}", a.milky_way().prims.len());
    }

    #[test]
    fn nothing_but_the_lobby_at_the_start() {
        let s = Stars::sample(1920.0, 1080.0);
        let f = s.paint(0.0);
        assert!(f.prims.iter().skip(1).all(|p| p.colors.iter().all(|c| c[3] == 0.0)));
    }
}
