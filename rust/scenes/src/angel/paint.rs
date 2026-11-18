//! Each frame of 金色传说, in the Python painter's order (angel.make's paint and the functions it
//! calls): the warm wash, candlelight, shafts, dust, the round window, the gold, its pens, the
//! keystone's flare, glints, feathers and motes.

use std::f64::consts::PI;

use super::atlas::Region;
use super::frame::{Lay, BAND, CLIP, MASK, NEAREST, PLUS, SECOND, TIMED, WINDOW};
use super::gild::pen_speed;
use super::lines::point_at;
use super::{Angel, Art};
use crate::draw::{clamp, ease_in, ease_in_out, ease_out, hex, win};
use crate::prim::{stops, Frame, Paint};

const EMBER: &str = "#ffb24a";
const RISE: (f64, f64) = (1.35, 2.55);
const REVEAL: f64 = 3.6;
const SWEEPS: [(f64, f64, f64); 2] = [(2.7, 0.8, 0.45), (REVEAL + 0.3, 0.6, 1.4)];

fn flicker(t: f64, seed: i32) -> f64 {
    let k = f64::from(seed) * 1.7;
    clamp(0.62 + 0.16 * (t * 7.1 + k).sin() + 0.1 * (t * 12.7 + 2.0 * k).sin() + 0.07 * (t * 23.3 + k).sin() + 0.05 * (t * 3.1 + 3.0 * k).sin())
}

/// The window's light about the reveal: how far it has dimmed, the flash, the burst, how far it has risen after.
fn reveal(t: f64) -> (f64, f64, f64, f64) {
    let hush = if t < REVEAL { ease_in_out(win(t, REVEAL - 0.45, REVEAL)) } else { 0.0 };
    let come = ease_out(win(t, REVEAL - 0.03, REVEAL + 0.03));
    let flash = come * (1.0 - ease_out(win(t, REVEAL + 0.03, REVEAL + 0.4)));
    let burst = come * (1.0 - ease_out(win(t, REVEAL + 0.03, REVEAL + 1.1)));
    (hush, flash, burst, ease_out(win(t, REVEAL, REVEAL + 0.35)))
}

impl Angel {
    fn size(&self) -> [f64; 2] {
        [self.width, self.height]
    }

    #[allow(clippy::too_many_arguments)] // angel._lay with the frame, the pictures and how it is laid
    /// _lay: a mote of light; returns the opacity it left the painter at, if it drew.
    fn spark(&self, f: &mut Frame, art: &Art, x: f64, y: f64, r: f64, alpha: f64, flags: u32) -> Option<f64> {
        if alpha <= 0.01 || r <= 0.2 {
            return None;
        }
        Lay::dot(art.spark, x, y, r, alpha, flags).put(f, self.size(), |_| {});
        Some(clamp(alpha))
    }

    #[allow(clippy::too_many_arguments)] // angel._brighter with the frame, the picture and how it is laid
    /// _brighter: a picture of light laid on at a, which may run up to 2.
    fn brighter(&self, f: &mut Frame, region: Region, rect: [f64; 4], base: f64, a: f64, flags: u32, extra: impl Fn(&mut crate::prim::Prim)) {
        Lay::rect(region, rect, base * clamp(a), flags).put(f, self.size(), &extra);
        if a > 1.01 {
            Lay::rect(region, rect, base * clamp(a - 1.0), flags | PLUS).put(f, self.size(), &extra);
        }
    }

    /// The warm wash at the screen's edges (_warmth), drawn once into the still layer.
    pub fn warmth(&self) -> Frame {
        let (w, h, u) = (self.width, self.height, self.u);
        let mut f = Frame::new();
        let top = h * 0.32;
        f.rect(0.0, 0.0, w, top, &Paint::Linear([0.0, 0.0], [0.0, top], stops(&[(0.0, "#ffdf9e", 0.22), (0.4, "#ffcf7a", 0.07), (1.0, "#ffcf7a", 0.0)])));
        let side = 190.0 * u;
        for (start, end, x) in [([0.0, 0.0], [side, 0.0], 0.0), ([w, 0.0], [w - side, 0.0], w - side)] {
            f.rect(x, 0.0, side, h, &Paint::Linear(start, end, stops(&[(0.0, "#ffd88f", 0.2), (0.5, "#ffc870", 0.06), (1.0, "#ffc870", 0.0)])));
        }
        for (cx, cy, r, alpha) in [(0.12, 0.1, 480.0, 0.24), (0.91, 0.15, 420.0, 0.22)] {
            let light = stops(&[(0.0, "#ffe2a6", alpha), (0.5, "#ffcf7a", alpha * 0.35), (1.0, "#ffcf7a", 0.0)]);
            f.rect(0.0, 0.0, w, h, &Paint::Radial([w * cx, h * cy], r * u, light));
        }
        f
    }

    /// Everything drawn at t seconds over the lobby (layer 0) and the warm wash (layer 1).
    pub fn paint(&self, t: f64, art: &Art) -> Frame {
        let (w, h, u) = (self.width, self.height, self.u);
        let mut f = Frame::new();
        f.picture(0, [w, h], self.gap, 1.0);
        let life = win(t, 0.0, 0.3);
        let leave = ease_in(win(t, 4.3, 5.0));
        f.opacity = life;
        let wash = ease_out(win(t, 0.0, 0.9)) * (1.0 - leave) * (0.86 + 0.14 * flicker(t, 0));
        if wash > 0.005 {
            f.picture(1, [w, h], self.gap, wash);
        }
        let candle = (1.0 - leave) * ease_out(win(t, 0.0, 1.2));
        if candle > 0.01 {
            for (seed, x) in [(1, 0.0), (2, w)] {
                let k = flicker(t, seed);
                let r = (400.0 + 30.0 * k) * u;
                let pool = stops(&[(0.0, "#ffc76a", 0.42 * candle * (0.7 + 0.3 * k)), (0.35, EMBER, 0.16 * candle * (0.6 + 0.4 * k)), (1.0, EMBER, 0.0)]);
                f.circle(x, h, r, &Paint::Radial([x, h], r, pool));
            }
        }
        let lit = ease_out(win(t, 1.15, 2.05));
        let (hush, _flash, burst, after) = reveal(t);
        let a = (1.0 - leave) * ease_out(win(t, 1.6, 2.7)) * (1.0 - 0.35 * hush + 0.7 * after + 1.6 * burst);
        if a > 0.01 {
            let o = |i: f64| clamp(a.min(1.0) * (0.55 + 0.45 * (t * (0.9 + 0.35 * i) + i * 2.4).sin()));
            let (s1, keep) = (art.shafts[1], art.keep);
            let (o0, o1) = (o(0.0) as f32, o(1.0) as f32);
            self.brighter(&mut f, art.shafts[0], [0.0, 0.0, w, h], life, a, SECOND | MASK, |p| {
                p.s1[2] = o0;
                p.s2 = [s1[0], s1[1], o1, 0.0];
                p.stops = [keep[0], keep[1], 0.0, 0.0];
            });
        }
        let a = (1.0 - leave) * lit * (1.0 + 0.6 * after);
        if a > 0.01 {
            for &[along, across, turn, depth, r, phase] in &self.dust {
                let angle = turn + 0.04 * (t * 0.5 + phase).sin();
                let far = self.radius * 1.3 + (depth * 380.0 * u + 18.0 * u * t) % (380.0 * u);
                let x = self.center[0] + far * angle.cos() + 8.0 * u * (t * 0.8 + phase).sin();
                let y = self.center[1] + far * angle.sin() * across + 10.0 * u * t * 0.3;
                let shine = 0.5 + 0.5 * (t * along * 2.1 + phase).sin();
                self.spark(&mut f, art, x, y, r * (3.0 + 2.0 * shine), life * a * (0.25 + 0.55 * shine), NEAREST);
            }
        }
        self.rose(&mut f, t, art, lit, 1.0 - ease_in(win(t, 4.55, 4.97)), life);
        self.tracery(&mut f, t, art, 1.0 - leave, life);
        self.pens(&mut f, t, art, 1.0 - leave, life);
        let k = ease_out(win(t, self.meet - 0.05, self.meet + 0.1)) * (1.0 - ease_in_out(win(t, self.meet + 0.1, self.meet + 0.9)));
        if k > 0.01 {
            let [x, y] = self.keystone;
            self.spark(&mut f, art, x, y, 70.0 * u, life * k * 0.8, NEAREST | PLUS);
            f.star(x, y, 30.0 * u * k, hex("#fffbea"), k, 0.07);
            f.star(x, y, 14.0 * u * k, hex("#fffbea"), k * 0.8, 0.2);
        }
        for &(when, line, span, back) in &self.glints {
            let k = win(t, when, when + span);
            if !(0.0 < k && k < 1.0) {
                continue;
            }
            let l = &self.lines[line];
            let total = l.run[l.run.len() - 1];
            let at = ease_in_out(k) * total;
            let head = point_at(&l.points, &l.run, if back { total - at } else { at });
            let shine = (PI * k).sin() * (1.0 - leave);
            self.spark(&mut f, art, head[0], head[1], 16.0 * u, life * shine * 0.8, NEAREST | PLUS);
            f.star(head[0], head[1], (6.0 + 7.0 * shine) * u, hex("#fffbea"), shine, 0.09);
        }
        self.feathers(&mut f, t, art, 1.0 - leave, life);
        let a = 1.0 - leave;
        for &[born, x, y, rise, r, phase] in &self.rising {
            let age = t - born;
            if a <= 0.01 || age <= 0.0 || age > 2.8 {
                continue;
            }
            let fade = (age / 0.4).min(1.0) * ((2.8 - age) / 1.0).min(1.0) * a;
            let twinkle = 0.55 + 0.45 * (age * 6.5 + phase).sin();
            self.spark(&mut f, art, x + 10.0 * u * (age * 1.7 + phase).sin(), y - rise * age, r * 3.2, life * fade * twinkle, NEAREST);
        }
        f
    }

    fn rose(&self, f: &mut Frame, t: f64, art: &Art, lit: f64, a: f64, base: f64) {
        let (u, c, radius) = (self.u, self.center, self.radius);
        if lit <= 0.0 || a <= 0.01 {
            return;
        }
        let hat = t >= REVEAL;
        let [back, figure, shine] = if hat { art.hat } else { art.sack };
        let rect = [c[0] - radius, c[1] - radius, 2.0 * radius, 2.0 * radius];
        let (hush, flash, burst, after) = reveal(t);
        let swell = ease_out(win(t, 2.0, 2.5)) * (1.0 - ease_in_out(win(t, 2.5, 3.2)));
        let halo = [c[0] - 3.0 * radius, c[1] - 3.0 * radius, 6.0 * radius, 6.0 * radius];
        let glow = a * lit * ((0.8 + 0.12 * flicker(t, 4) + 0.25 * swell) * (1.0 - 0.35 * hush) + 0.5 * after + 1.2 * burst);
        self.brighter(f, art.halo, halo, base, glow, 0, |_| {});
        let mut cur = base * a;
        if lit >= 1.0 {
            Lay::rect(back, rect, cur, 0).put(f, self.size(), |_| {});
        } else {
            let reach = (radius * lit) as f32;
            Lay::rect(back, rect, cur, CLIP).put(f, self.size(), |p| p.colors[1] = [c[0] as f32, c[1] as f32, reach, 0.0]);
        }
        let come = if hat { 1.0 } else { ease_in_out(win(t, RISE.0, RISE.1)) };
        if come > 0.01 {
            let dy = if hat { 0.0 } else { 12.0 * u * (1.0 - ease_out(win(t, RISE.0, RISE.1))) };
            let rise = [rect[0], rect[1] + dy, rect[2], rect[3]];
            Lay::rect(figure, rise, base * a * come, 0).put(f, self.size(), |_| {});
            let candle = ((0.12 + 0.1 * after) * flicker(t, 5) + 0.04 * swell) * (1.0 - 0.5 * hush) + 0.08 * after + 0.5 * flash;
            cur = base * a * come * clamp(candle);
            let (lower, under) = ((dy * f64::from(back[3]) / rect[3]) as f32, clamp(base * a * come) as f32);
            Lay::rect(back, rect, cur, PLUS | WINDOW).put(f, self.size(), |p| {
                p.s2 = [figure[0], figure[1], 1.0, 0.0];
                p.colors[2] = [lower, under, 0.0, 0.0];
            });
            let top = base * a * come;
            for (when, span, strength) in SWEEPS {
                let k = win(t, when, when + span);
                if !(0.0 < k && k < 1.0) || top <= 0.01 {
                    continue;
                }
                let n = f64::from(shine[2]);
                let at = ((0.12 + 0.76 * ease_in_out(k)) * n) as f32;
                cur = clamp(top * strength * (PI * k).sin());
                Lay::rect(shine, rise, cur, PLUS | BAND).put(f, self.size(), |p| p.colors[0] = [at, n as f32, 0.0, 0.0]);
            }
        }
        if swell > 0.01 {
            cur = self.spark(f, art, c[0], c[1], radius * 0.9, base * a * swell * 0.25, PLUS).unwrap_or(cur);
        }
        if burst > 0.01 {
            cur = self.spark(f, art, c[0], c[1], radius * (1.2 + 0.4 * flash), base * a * flash, PLUS).unwrap_or(cur);
            let reach = radius * 4.0 * (0.75 + 0.35 * ease_out(win(t, REVEAL, REVEAL + 0.8)));
            self.brighter(f, art.rays, [c[0] - reach, c[1] - reach, 2.0 * reach, 2.0 * reach], cur, a * burst * 1.6, 0, |_| {});
        }
    }

    fn tracery(&self, f: &mut Frame, t: f64, art: &Art, a: f64, base: f64) {
        if a <= 0.01 {
            return;
        }
        let done = t >= self.ends;
        let glow = base * a * (0.8 + 0.2 * flicker(t, 0));
        for &(rect, gold, bloom, scale) in &art.areas {
            for (region, opacity, at) in [(bloom, glow, scale * 0.5), (gold, base * a, scale)] {
                let speed = pen_speed(self.u, at) as f32;
                Lay::rect(region, rect, opacity, if done { 0 } else { TIMED }).put(f, self.size(), |p| p.stops = [0.0, 0.0, t as f32, speed]);
            }
        }
    }

    fn pens(&self, f: &mut Frame, t: f64, art: &Art, a: f64, base: f64) {
        let u = self.u;
        let heads: Vec<(usize, f64)> = (0..self.lines.len())
            .filter_map(|i| {
                let l = &self.lines[i];
                let drawn = (t - l.start) / l.span;
                (0.0 < drawn && drawn < 1.0).then(|| (i, drawn * l.run[l.run.len() - 1]))
            })
            .collect();
        if heads.is_empty() || a <= 0.01 {
            return;
        }
        for &(i, at) in &heads {
            let l = &self.lines[i];
            let big = 0.6 + 0.2 * l.width;
            for (back, size, alpha) in [(44.0, 9.0, 0.18), (26.0, 11.0, 0.3), (12.0, 13.0, 0.45), (0.0, 15.0, 0.85)] {
                if at - back * u > 0.0 || back == 0.0 {
                    let p = point_at(&l.points, &l.run, at - back * u);
                    self.spark(f, art, p[0], p[1], size * big * u, base * a * alpha, NEAREST | PLUS);
                }
            }
        }
        for &(i, at) in &heads {
            let l = &self.lines[i];
            if l.width >= 2.2 {
                let p = point_at(&l.points, &l.run, at);
                f.star(p[0], p[1], 9.0 * u, [1.0; 3], 0.9 * a, 0.1);
            }
        }
    }

    fn feathers(&self, f: &mut Frame, t: f64, art: &Art, a: f64, base: f64) {
        if a <= 0.01 {
            return;
        }
        let (region, root) = art.feather;
        let (iw, ih) = (f64::from(region[2]), f64::from(region[3]));
        for (index, &[born, x, y, fall, length, phase, rate]) in self.falling.iter().enumerate() {
            let age = t - born;
            if age <= 0.0 {
                continue;
            }
            let fade = (age / 0.6).min(1.0) * a;
            let swing = (age * 1.6 + phase).sin();
            let (cx, cy) = (x + 16.0 * (length / 40.0) * swing, y + fall * age - 5.0 * (length / 40.0) * swing.abs());
            let heading = if index % 4 < 2 { 180.0 } else { 0.0 };
            let angle = heading + 26.0 * (age * 1.6 + phase).cos() * if heading != 0.0 { 1.0 } else { -1.0 } + 12.0;
            let turn = (age * rate + phase).cos();
            let across = (0.3 + 0.7 * turn.abs()).copysign(turn);
            let back = angle.to_radians();
            let scale = length / iw;
            let (cs, sn) = (back.cos(), back.sin());
            let m = [cs * scale, -sn * scale * across, sn * scale, cs * scale * across];
            let lift = -root * ih;
            let origin = [cx - cs * length / 2.0 + m[1] * lift, cy - sn * length / 2.0 + m[3] * lift];
            Lay { region, m, t: origin, opacity: base * fade * (0.7 + 0.3 * turn.abs()), flags: 0 }.put(f, self.size(), |_| {});
            let flash = clamp((turn.abs() - 0.86) / 0.14);
            if flash > 0.01 {
                Lay { region, m, t: origin, opacity: base * fade * flash * 0.55, flags: PLUS }.put(f, self.size(), |_| {});
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::super::Angel;

    #[test]
    fn nothing_but_the_lobby_at_the_start_and_more_once_lit() {
        let s = Angel::sample(1920.0, 1080.0);
        let (_, art) = s.bake();
        assert_eq!(s.paint(0.0, &art).prims.iter().skip(1).filter(|p| p.kind[0] == 7 && p.s1[3] > 0.0).count(), 0);
        assert!(s.paint(3.0, &art).prims.len() > 40);
    }
}
