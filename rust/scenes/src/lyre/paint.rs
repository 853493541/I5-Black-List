//! One frame of 竖琴清风 as a list of things to lay on, in lyre.py's paint order: pictures (each with
//! the transform the Python painter has for it, its opacity and the clip it is drawn through) and soft
//! dots. Clips (the current and the strands drawing themselves in) are worked out on the CPU per frame.

use super::art::{Art, Laid, FEATHERS, RELEASED, SEEDS, SPRIG, BUDS};
use super::img::Map;
use super::raster::{coverage, stroke, Cap, Shape};
use super::{angle, birds, bob, dip, ease_out, flight, idle, smooth, strum, win, bezier_at, CORE, CX, CY, FLAP, FLY, LIFT, MINT, NEST, PERCH,
    STARTS, STILL, STRING_X, STRING_Y, STROKE, STRUMS, WAY_IN, SHARP};
use std::f64::consts::PI;

/// x' = a x + c y + e, y' = b x + d y + f.
pub type Aff = [f64; 6];
const ID: Aff = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0];

fn mul(a: Aff, b: Aff) -> Aff {
    [a[0] * b[0] + a[2] * b[1], a[1] * b[0] + a[3] * b[1], a[0] * b[2] + a[2] * b[3], a[1] * b[2] + a[3] * b[3],
     a[0] * b[4] + a[2] * b[5] + a[4], a[1] * b[4] + a[3] * b[5] + a[5]]
}
fn tr(x: f64, y: f64) -> Aff {
    [1.0, 0.0, 0.0, 1.0, x, y]
}
fn rot(deg: f64) -> Aff {
    let r = deg.to_radians();
    [r.cos(), r.sin(), -r.sin(), r.cos(), 0.0, 0.0]
}
fn sc(x: f64, y: f64) -> Aff {
    [x, 0.0, 0.0, y, 0.0, 0.0]
}

#[derive(Clone)]
pub enum Item {
    Pic { id: usize, m: Aff, alpha: f64, clip: u32 },
    Dot { x: f64, y: f64, r: f64, color: &'static str, alpha: f64 },
}

#[derive(Default)]
pub struct Frame {
    pub items: Vec<Item>,
    /// Screen-size clips, one for each channel 1..=4 an item may name.
    pub clips: [Option<Map>; 4],
}

struct P<'a> {
    art: &'a Art,
    f: Frame,
}

impl P<'_> {
    fn pic(&mut self, id: usize, m: Aff, alpha: f64, clip: u32) {
        if alpha > 0.0 {
            self.f.items.push(Item::Pic { id, m, alpha, clip });
        }
    }
    fn laid(&mut self, l: Laid, base: Aff, alpha: f64, clip: u32) {
        let p = &self.art.store[l.id];
        let [x0, y0, x1, y1] = l.rect;
        self.pic(l.id, mul(base, mul(tr(x0, y0), sc((x1 - x0) / p.w as f64, (y1 - y0) / p.h as f64))), alpha, clip);
    }
    fn dot(&mut self, x: f64, y: f64, r: f64, color: &'static str, alpha: f64) {
        if alpha > 0.01 && r > 0.2 {
            self.f.items.push(Item::Dot { x, y, r, color, alpha: alpha.min(1.0) });
        }
    }
    /// _place: centred on (x, y), turned and squashed, px pixels a point.
    #[allow(clippy::too_many_arguments)]
    fn place(&mut self, id: usize, x: f64, y: f64, a: f64, sx: f64, sy: f64, alpha: f64, px: f64) {
        if alpha <= 0.01 {
            return;
        }
        let p = &self.art.store[id];
        let m = mul(mul(mul(tr(x, y), rot(a)), sc(sx / px, sy / px)), tr(-(p.w as f64) / 2.0, -(p.h as f64) / 2.0));
        self.pic(id, m, alpha, 0);
    }
    #[allow(clippy::too_many_arguments)]
    fn tumble(&mut self, pair: [usize; 2], x: f64, y: f64, a: f64, flip: f64, alpha: f64, px: f64) {
        if flip.abs() >= 0.04 {
            self.place(if flip > 0.0 { pair[0] } else { pair[1] }, x, y, a, 1.0, flip, alpha, px);
        }
    }
    /// _sat: the middle of its bottom on the base transform's (0, 0).
    fn sat(&mut self, id: usize, base: Aff, alpha: f64) {
        if alpha <= 0.01 {
            return;
        }
        let p = &self.art.store[id];
        self.pic(id, mul(base, tr(-(p.w as f64) / 2.0, -(p.h as f64))), alpha, 0);
    }
    #[allow(clippy::too_many_arguments)]
    fn sat_at(&mut self, id: usize, x: f64, y: f64, a: f64, sx: f64, sy: f64, alpha: f64, px: f64) {
        self.sat(id, mul(mul(tr(x, y), rot(a)), sc(sx / px, sy / px)), alpha);
    }
    #[allow(clippy::too_many_arguments)]
    fn flyer(&mut self, blink: bool, x: f64, y: f64, a: f64, sx: f64, sy: f64, alpha: f64, px: f64, flap: f64, reach: f64, lead: f64) {
        if alpha <= 0.01 {
            return;
        }
        let ids = self.art.birds;
        let (body, wing) = (ids[usize::from(blink)], ids[2]);
        let (bw, bh) = (self.art.store[body].w as f64, self.art.store[body].h as f64);
        let (kx, ky) = (bw / birds::FRONT_SIZE.0, bh / birds::FRONT_SIZE.1);
        let ((rx, ry), (tx, ty)) = (birds::WING_ROOT, birds::WING_TIP);
        let along = ((tx - rx) * kx).atan2((ry - ty) * ky).to_degrees();
        let length = 1.0 - 0.25 * (PI / 2.0 * (flap / STROKE).min(1.0)).sin();
        let (ww, wh) = (self.art.store[wing].w as f64, self.art.store[wing].h as f64);
        for ((ax, ay), mirror) in [(birds::FRONT_RIGHT, 1.0), (birds::FRONT_LEFT, -1.0)] {
            let mut m = mul(mul(tr(x, y), rot(a)), sc(sx / px, sy / px));
            m = mul(m, tr(ax * kx - bw / 2.0, ay * ky - bh));
            m = mul(m, sc(mirror, 1.0));
            m = mul(m, rot(flap * (1.0 - 0.15 * (lead * mirror).max(0.0)) + along));
            m = mul(m, sc(reach, length * reach));
            m = mul(m, rot(-along));
            m = mul(m, tr(ww / 2.0 - rx * kx, wh - ry * ky));
            self.sat(wing, m, alpha);
        }
        self.sat_at(body, x, y, a, sx, sy, alpha, px);
    }
}

/// The area within wide / 2 of a line (_along_path), as a screen clip.
fn along(points: &[[f64; 2]], wide: f64, cap: Cap, dy: f64, w: usize, h: usize) -> Map {
    let step = (points.len() / 400).max(1);
    let mut line: Vec<[f64; 2]> = points.iter().step_by(step).map(|p| [p[0], p[1] + dy]).collect();
    let last = points[points.len() - 1];
    line.push([last[0], last[1] + dy]);
    let (x0, y0, c) = coverage(&stroke(&[line], wide, cap), w, h);
    let mut out = Map::new(w, h, 0.0);
    for y in 0..c.h {
        out.v[(y0 + y) * w + x0..(y0 + y) * w + x0 + c.w].copy_from_slice(&c.v[y * c.w..(y + 1) * c.w]);
    }
    let _ = Shape::default;
    out
}

/// The current part drawn, square by square as lyre.py shows it: a square whose nearby points are all drawn
/// shows whole, one whose first is not yet drawn shows nothing, the rest through the drawn stretches.
fn tile_clip(art: &Art, n: usize, w: usize, h: usize) -> Map {
    let mut out = Map::new(w, h, 0.0);
    for (rect, near) in &art.tiles {
        if near[0] > n {
            continue;
        }
        let (x0, y0) = (rect[0].round() as usize, rect[1].round() as usize);
        let (x1, y1) = ((rect[2].round() as usize).min(w), (rect[3].round() as usize).min(h));
        let mut fill = |m: &dyn Fn(usize, usize) -> f32| {
            for y in y0..y1 {
                for x in x0..x1 {
                    let v = m(x, y);
                    let o = &mut out.v[y * w + x];
                    *o = o.max(v);
                }
            }
        };
        if near[near.len() - 1] <= n {
            fill(&|_, _| 1.0);
            continue;
        }
        let drawn: Vec<usize> = near.iter().copied().filter(|&i| i <= n).collect();
        let mut runs: Vec<Vec<usize>> = Vec::new();
        for i in drawn {
            match runs.last_mut() {
                Some(r) if r[r.len() - 1] + 1 == i => r.push(i),
                _ => runs.push(vec![i]),
            }
        }
        for r in runs.into_iter().filter(|r| r.len() > 1) {
            let pts: Vec<[f64; 2]> = r.iter().map(|&i| art.route[i]).collect();
            let c = along(&pts, 160.0 * art.g.u, Cap::Flat, 0.0, w, h);
            fill(&|x, y| c.v[y * w + x]);
        }
    }
    out
}

pub fn paint(art: &Art, t: f64) -> Frame {
    let mut p = P { art, f: Frame::default() };
    let g = art.g;
    let u = g.u;
    let (w, h) = (g.width.ceil() as usize, g.height.ceil() as usize);
    let xy = |x: f64, y: f64| g.at(x, y, false);
    let px = 2.0 * art.scale;
    let leave = smooth(0.0, 1.0, win(t, 4.4, 5.0));
    let fade = 1.0 - leave;
    let life = t - 1.3;
    let lift = 160.0 * u * leave;
    p.laid(art.band, ID, ease_out(win(t, 0.0, 0.5)) * fade, 0);
    let reveal = smooth(0.0, 1.0, win(t, 0.2, 1.0));
    let a_border = (fade * 1.4).min(1.0);
    if reveal >= 1.0 {
        p.laid(art.border, ID, a_border, 0);
    } else if reveal > 0.0 {
        let n = art.run.partition_point(|&s| s < reveal * art.run[art.run.len() - 1]);
        p.f.clips[0] = Some(tile_clip(art, n, w, h));
        p.laid(art.border, ID, a_border, 1);
        let [hx, hy] = art.route[n.min(art.route.len() - 1)];
        p.dot(hx, hy, 18.0 * u, MINT, 0.7 * (PI * reveal).sin() + 0.2);
        p.dot(hx, hy, 7.0 * u, CORE, 0.8);
    }
    if reveal > 0.0 && t >= 0.9 {
        let on = win(t, 0.9, 1.4) * fade;
        let total = art.run[art.run.len() - 1];
        let gw = art.store[art.glint].w as f64 / 40.0;
        for j in 0..7 {
            let age = (t - 0.9 - f64::from(j) * 0.45).rem_euclid(3.15);
            if age > 1.3 {
                continue;
            }
            let at = (f64::from(j) * 0.37 * total + 300.0 * u * (t - 0.9)).rem_euclid(total);
            let i = art.run.partition_point(|&s| s < at).min(art.route.len() - 1);
            if !art.open_run[i] {
                continue;
            }
            let [x, y] = art.route[i];
            let n = art.nrm[i];
            p.place(art.glint, x, y, (-n[0]).atan2(n[1]).to_degrees(), u, u, on * (PI * age / 1.3).sin() * 0.85, gw);
        }
    }
    let hero = ease_out(win(t, 0.3, 1.1)) * fade;
    if hero > 0.0 {
        for c in art.curls.clone() {
            p.laid(c, ID, hero, 0);
        }
        let nod = (life * 1.6).sin() * 3.0;
        p.laid(art.stalks, ID, hero, 0);
        let puff = dip(t - STRUMS[0].0, 0.3, 1.2);
        let (blink, sx, sy, sway) = idle(t, 2);
        let [nx, ny] = xy(NEST.0, NEST.1);
        p.sat_at(art.birds[5 + usize::from(blink)], nx, ny, sway, sx * (1.0 + 0.03 * puff), sy * (1.0 + 0.025 * puff), hero, px);
        for (k, s) in SPRIG.iter().enumerate() {
            let [x, y] = xy(s.2 .0, s.2 .1);
            p.place(art.cecilia[k], x, y, s.4 + nod * if k % 2 == 1 { 1.0 } else { -1.0 }, 1.0, 0.82, hero, px);
        }
        for (k, s) in BUDS.iter().enumerate() {
            let [x, y] = xy(s.2 .0, s.2 .1);
            p.place(art.bud[k], x, y, s.4 + nod, 1.0, 1.0, hero, px);
        }
    }
    let lyre_a = ease_out(win(t, 0.3, 0.9)) * fade;
    let rise = 12.0 * u * (1.0 - ease_out(win(t, 0.3, 0.9)));
    let ang = angle(t);
    let st = strum(t);
    if lyre_a > 0.0 {
        let ppr = SHARP * art.pt * art.scale;
        let base = mul(mul(tr(art.lyre_at[0], art.lyre_at[1] + rise), rot(ang)), sc(art.pt, art.pt));
        let glow_k = st.iter().sum::<f64>() / 7.0;
        let side = art.store[art.lyre].w as f64 / ppr;
        let square = mul(base, mul(tr(-side / 2.0, -side / 2.0), sc(1.0 / ppr, 1.0 / ppr)));
        if glow_k > 0.01 {
            p.pic(art.aura, square, lyre_a * (glow_k * 1.5).min(1.0), 0);
        }
        p.pic(art.lyre, square, lyre_a, 0);
        let ring = &art.store[art.string];
        let (rw, rh) = (ring.w as f64 / ppr, ring.h as f64 / ppr);
        let _ = rh;
        for (i, sx) in STRING_X.iter().enumerate() {
            if st[i] > 0.02 {
                let shiver = 0.6 * st[i] * (st[i] * 40.0 + i as f64).sin();
                let m = mul(base, mul(tr(sx - CX - rw / 2.0 + shiver, STRING_Y.0 - CY - 4.0), sc(1.0 / ppr, 1.0 / ppr)));
                p.pic(art.string, m, lyre_a * st[i] * 0.85, 0);
            }
        }
    }
    let reveal = win(t, 0.2, 1.0);
    if reveal > 0.0 {
        for k in 0..3 {
            let share = (ease_out(reveal) * (2.2 - 0.3 * k as f64)).min(1.0);
            let line = &art.strands[k].0;
            if share >= 1.0 {
                p.laid(art.strand_pics[k], tr(0.0, rise), fade, 0);
            } else if share > 0.0 {
                let cut = ((line.len() as f64 * share) as usize).max(2);
                p.f.clips[k + 1] = Some(along(&line[..cut], 64.0 * u, Cap::Round, rise, w, h));
                p.laid(art.strand_pics[k], tr(0.0, rise), fade, k as u32 + 2);
            }
        }
        let gw = art.store[art.glint].w as f64 / 40.0;
        for (when, _) in STRUMS {
            for (k, (line, _, _)) in art.strands.iter().enumerate() {
                let q = (t - when - 0.2 - 0.06 * k as f64) / 0.9;
                if !(q > 0.0 && q < 1.0) {
                    continue;
                }
                let i = (line.len() - 2).min((q * (line.len() - 1) as f64) as usize);
                let (dx, dy) = (line[i + 1][0] - line[i][0], line[i + 1][1] - line[i][1]);
                p.place(art.glint, line[i][0], line[i][1] + rise, dy.atan2(dx).to_degrees(), 0.8 * u, 0.8 * u, (PI * q).sin() * fade, gw);
            }
        }
        let glow_k = st.iter().sum::<f64>() / 7.0;
        for ((x, y), r) in STARTS.iter().zip([16.0, 13.0, 11.0]) {
            let [sx, sy] = art.lyre_pt(*x, *y, ang, rise);
            p.dot(sx, sy, r * 2.0 * u, "#9ff5e0", (0.8 * reveal + 0.3 * glow_k).min(1.0) * fade);
            p.dot(sx, sy, r * 0.9 * u, CORE, (0.45 * reveal + 0.3 * glow_k) * fade);
        }
    }
    if lyre_a > 0.0 {
        let b = bob(t);
        let (blink, sx, sy, sway) = idle(t, 0);
        let [x, y] = art.lyre_pt(PERCH.0, PERCH.1, ang, rise);
        p.sat_at(art.birds[3 + usize::from(blink)], x, y, 0.35 * ang + 0.6 * sway, sx * (1.0 + 0.05 * b), sy * (1.0 - 0.08 * b), lyre_a, px);
    }
    let parts = ease_out(win(t, 0.9, 1.4)) * fade;
    if parts > 0.0 {
        let carry = ease_out(win(t, 0.9, 1.6));
        for (k, (x, y, a, _, _)) in RELEASED.iter().enumerate() {
            let kf = k as f64;
            let [sx, sy] = art.lyre_pt(STARTS[k].0, STARTS[k].1, ang, rise);
            let [mut tx, mut ty] = xy(*x, *y);
            tx += 5.0 * u * (life + kf).sin() + 8.0 * u * (t - STILL) + lift;
            ty -= 3.0 * u * (life * 1.2 + kf).sin() + 2.0 * u * (t - STILL) + lift * 0.8;
            let sway = 8.0 * (life * 1.5 + kf * 2.0).sin();
            p.place(art.released[k], sx + (tx - sx) * carry, sy + (ty - sy) * carry, a + sway, 1.0, 0.92 + 0.08 * (life * 1.2 + kf).cos(), parts, px);
        }
        let [mut tx, mut ty] = xy(326.0, 50.0);
        tx += 4.0 * u * life.sin() + 8.0 * u * (t - STILL) + lift;
        ty -= lift * 0.8;
        let [sx, sy] = art.lyre_pt(STARTS[0].0, STARTS[0].1, ang, rise);
        p.tumble(art.released_leaf, sx + (tx - sx) * carry, sy + (ty - sy) * carry, 30.0 + life * 50.0, super::flip(art.released_leaf_phase, 1.6, life), parts, px);
    }
    if hero > 0.0 {
        for (k, &(x, y, r, a, phase)) in art.hero_at.iter().enumerate() {
            let [mut cx, mut cy] = xy(x, y);
            let kf = k as f64;
            let swirl = (t - STILL) * 0.9 + kf * 2.1;
            cx += 6.0 * u * (swirl.sin() - (kf * 2.1).sin()) + lift;
            cy += 4.0 * u * (swirl.cos() - (kf * 2.1).cos()) - lift * 0.6;
            let spin = life * 40.0 * if r > 25.0 { 0.3 } else { 0.6 };
            p.tumble(art.hero[k], cx, cy, a + spin, super::flip(phase, 1.1, life), hero, px);
        }
    }
    if parts > 0.0 {
        let drift = t - STILL;
        for (k, f) in FEATHERS.iter().enumerate() {
            let kf = k as f64;
            let [mut fx, mut fy] = g.at(f.0, f.1, f.5);
            let sway = 7.0 * (life * 1.3 + kf * 1.7).sin();
            fx += 6.0 * u * (life * 0.9 + kf).sin() + f.6 .0 * u * drift + f.7 .0 * lift;
            fy += f.6 .1 * u * drift + f.7 .1 * lift;
            p.place(art.feather[k], fx, fy, f.2 + sway, 1.0, 0.9 + 0.1 * (life * 1.1 + kf * 2.3).cos(), parts * 0.97, px);
        }
        for (k, l) in art.leaves.iter().enumerate() {
            let [mut lx, mut ly] = g.at(l.0, l.1, l.6);
            lx += l.7 .0 * u * drift + l.8 .0 * lift;
            ly += l.7 .1 * u * drift + l.8 .1 * lift;
            let spin = life * 60.0 * if k % 2 == 1 { 1.0 } else { -1.0 };
            p.tumble(art.leaf[k], lx, ly, l.3 + spin, super::flip(l.4, 1.7, life), parts, px);
        }
        for (x, y, size, a, side) in SEEDS {
            let [mut sx, mut sy] = g.at(x, y, side);
            sx += 4.0 * u * (life + x).sin() + 0.5 * lift;
            sy += -6.0 * u * drift - lift;
            p.place(art.seed, sx, sy, a + 6.0 * (life * 1.3 + y).sin(), size / 18.0, size / 18.0, parts * 0.4, px);
        }
    }
    if hero > 0.0 {
        for (k, &(x, y, _, a, phase)) in art.updraft_at.iter().enumerate() {
            let [lx, ly] = xy(x, y);
            let kf = k as f64;
            let rise_k = (t - STILL) * 6.0 * u;
            p.tumble(art.updraft[k], lx + 3.0 * u * (life * 1.4 + kf).sin() + 0.3 * lift, ly - rise_k - lift, a + life * 90.0, super::flip(phase, 2.0, life), hero, px);
        }
    }
    if t > FLY.0 {
        let (wy, flap, reach, squash) = flight(t);
        let way_pts = WAY_IN.map(|(x, y)| xy(x, y));
        let [fx, fy] = bezier_at(&way_pts, wy);
        let seen = ease_out(win(t, FLY.0, FLY.0 + 0.15)) * fade;
        if wy < 1.0 {
            let k = win(t, FLY.0, FLY.1);
            let [nx, _] = bezier_at(&way_pts, (wy + 0.02).min(1.0));
            let toward = ((nx - fx) / (2.0 * u)).clamp(-1.0, 1.0);
            let pull = flap.min(STROKE) / STROKE * (1.0 - smooth(0.85, 1.0, k));
            let size = 0.88 + 0.12 * smooth(0.8, 1.0, k);
            let mut lean = toward * (13.0 - 19.0 * smooth(0.76, 0.92, k)) * (1.0 - smooth(0.92, 1.0, k));
            lean += 1.5 * (PI * (t - FLY.0) / FLAP).sin() * (1.0 - smooth(0.8, 1.0, k));
            p.flyer(false, fx, fy - LIFT * u * pull, lean, size * (1.0 - 0.03 * pull), size * (1.0 + 0.05 * pull), seen, px, flap, reach, toward);
        } else {
            let (blink, sx, sy, sway) = idle(t, 1);
            p.flyer(blink, fx, fy, sway, sx * (1.0 + 0.08 * squash), sy * (1.0 - 0.12 * squash), seen, px, flap, reach, 0.0);
        }
    }
    p.f
}
