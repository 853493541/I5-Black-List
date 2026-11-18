//! Every picture 竖琴清风 lays on, made once for a stage (lyre.py's jobs and _Pictures, all made ahead,
//! the gap round the button faded out of the band and the current as _cut_gap does), and where the
//! drifting things sit.

use super::img::Pic;
use super::wind::{self, Line, Placed};
use super::{birds, lyre_art, matched, sprites, smooth, Geo, CX, LYRE_AT, LYRE_SCALE, SHARP, STARTS, U};

/// A picture in the store and the box it is laid on (left, top, right, bottom), for those laid on a box.
#[derive(Clone, Copy)]
pub struct Laid {
    pub id: usize,
    pub rect: [f64; 4],
}

pub type Feather = (f64, f64, f64, f64, u32, bool, (f64, f64), (f64, f64));
pub type Leaf = (f64, f64, f64, f64, f64, bool, bool, (f64, f64), (f64, f64));
pub type Sprig = ((f64, f64), (f64, f64), (f64, f64), f64, f64);

pub const FEATHERS: [Feather; 7] = [
    (408.0, 58.0, -18.0, 62.0, 1, false, (9.0, 0.0), (1.0, -0.8)), (590.0, 38.0, 12.0, 50.0, 2, false, (8.0, 0.0), (1.0, -0.8)),
    (1190.0, 54.0, -30.0, 56.0, 3, false, (8.0, 0.0), (1.0, -0.8)), (1340.0, 100.0, 24.0, 46.0, 4, false, (9.0, -1.0), (1.0, -0.8)),
    (66.0, 320.0, 72.0, 66.0, 5, true, (0.0, -8.0), (-0.15, -1.0)), (106.0, 480.0, 108.0, 54.0, 6, true, (0.0, -7.0), (-0.15, -1.0)),
    (56.0, 620.0, 84.0, 60.0, 7, true, (0.0, -8.0), (-0.15, -1.0)),
];
const LEAVES: [Leaf; 6] = [
    (1584.0, 300.0, 29.0, 20.0, 0.4, false, true, (0.0, 8.0), (0.3, -1.0)), (1574.0, 470.0, 27.0, 130.0, 2.2, true, true, (0.0, 8.0), (0.3, -1.0)),
    (1590.0, 614.0, 28.0, 60.0, 4.0, false, true, (0.0, 7.0), (0.3, -1.0)), (1262.0, 796.0, 28.0, 200.0, 1.1, false, false, (-7.0, 0.0), (1.0, -0.35)),
    (1384.0, 774.0, 26.0, 300.0, 2.9, false, false, (-6.0, 0.0), (1.0, -0.35)), (420.0, 800.0, 27.0, 150.0, 5.2, false, false, (-7.0, 0.0), (-0.8, -0.6)),
];
const HERO: [(f64, f64, f64, f64, f64, bool, u64); 3] = [(1440.0, 80.0, 46.0, -24.0, 0.3, false, 1), (1598.0, 156.0, 38.0, 38.0, 1.9, true, 2), (1504.0, 162.0, 32.0, 76.0, 3.1, false, 3)];
pub const SEEDS: [(f64, f64, f64, f64, bool); 4] = [(470.0, 118.0, 18.0, -20.0, false), (1424.0, 206.0, 15.0, 25.0, false), (152.0, 644.0, 16.0, 10.0, true), (1560.0, 690.0, 14.0, -30.0, true)];
pub const RELEASED: [(f64, f64, f64, f64, u32); 2] = [(262.0, 66.0, -32.0, 38.0, 31), (346.0, 128.0, -12.0, 34.0, 32)];
pub const SPRIG: [Sprig; 3] = [((60.0, 838.0), (40.0, 780.0), (72.0, 735.0), 30.0, -8.0), ((96.0, 842.0), (110.0, 790.0), (138.0, 768.0), 25.0, 14.0),
    ((34.0, 840.0), (20.0, 805.0), (30.0, 772.0), 21.0, -24.0)];
pub const BUDS: [Sprig; 2] = [((76.0, 840.0), (92.0, 760.0), (110.0, 722.0), 15.0, 18.0), ((48.0, 842.0), (60.0, 800.0), (160.0, 815.0), 13.0, 50.0)];

pub struct Art {
    pub g: Geo,
    pub scale: f64,
    pub store: Vec<Pic>,
    pub lyre_at: [f64; 2],
    pub pt: f64,
    pub route: Vec<[f64; 2]>,
    pub run: Vec<f64>,
    pub nrm: Vec<[f64; 2]>,
    pub open_run: Vec<bool>,
    pub strands: Vec<Line>,
    pub band: Laid,
    /// The current's squares as Python cuts them: (left, top, right, bottom) and the route's points near each.
    pub tiles: Vec<([f64; 4], Vec<usize>)>,
    pub border: Laid,
    pub strand_pics: Vec<Laid>,
    pub curls: Vec<Laid>,
    pub stalks: Laid,
    pub glint: usize,
    pub lyre: usize,
    pub aura: usize,
    pub string: usize,
    pub cecilia: Vec<usize>,
    pub bud: Vec<usize>,
    pub hero: Vec<[usize; 2]>,
    pub hero_at: Vec<(f64, f64, f64, f64, f64)>,
    pub updraft: Vec<[usize; 2]>,
    pub updraft_at: Vec<(f64, f64, f64, f64, f64)>,
    pub released: Vec<usize>,
    pub released_leaf: [usize; 2],
    pub released_leaf_phase: f64,
    pub feather: Vec<usize>,
    pub leaf: Vec<[usize; 2]>,
    pub leaves: Vec<Leaf>,
    pub seed: usize,
    /// flyer, flyer_blink, wing, perch, perch_blink, lily, lily_blink.
    pub birds: [usize; 7],
}

/// Qt's BYTE_MUL: x * a / 255, rounded as Qt rounds it.
fn byte_mul(x: u8, a: u8) -> u8 {
    let t = u32::from(x) * u32::from(a);
    ((t + (t >> 8) + 0x80) >> 8) as u8
}

/// _cut_gap / _bare: the picture faded into the gap round the button.
fn bared(mut p: Placed, g: &Geo, scale: f64) -> Placed {
    let [gl, gt, gw, _] = g.gap;
    for y in 0..p.pic.h {
        let ys = p.top + y as f64 / scale;
        for x in 0..p.pic.w {
            let xs = p.left + x as f64 / scale;
            let dx = (gl - xs).max(xs - (gl + gw)).max(0.0);
            let dy = (gt - ys).max(0.0);
            let keep = smooth(0.0, 46.0 * g.u, dx.hypot(dy)) as f32;
            if keep < 1.0 {
                let level = (keep * 255.0 + 0.5) as u8;
                let px = &mut p.pic.px[y * p.pic.w + x];
                *px = px.map(|c| byte_mul(c, level));
            }
        }
    }
    p
}

impl Art {
    pub fn lyre_pt(&self, x: f64, y: f64, angle: f64, rise: f64) -> [f64; 2] {
        let r = angle.to_radians();
        let (x, y) = (x * self.pt, y * self.pt);
        [self.lyre_at[0] + x * r.cos() - y * r.sin(), self.lyre_at[1] + rise + x * r.sin() + y * r.cos()]
    }

    fn add(&mut self, p: Pic) -> usize {
        self.store.push(p);
        self.store.len() - 1
    }

    fn lay(&mut self, p: Placed) -> Laid {
        let rect = [p.left, p.top, p.right, p.bottom];
        Laid { id: self.add(p.pic), rect }
    }

    /// Every picture for a stage at scale pixels a point.
    pub fn new(g: Geo, scale: f64) -> Result<Self, String> {
        let u = g.u;
        let lyre_at = g.at(LYRE_AT.0, LYRE_AT.1, false);
        let pt = U * LYRE_SCALE * u;
        let route = wind::route(g.width, g.height, 14.0 * u, 44.0 * u);
        let run = wind::arclen(&route);
        let nrm = wind::normals(&route);
        let [gl, _, gw, _] = g.gap;
        let open_run = route.iter().map(|p| !(p[1] > g.height - 60.0 * u && p[0] > gl - 50.0 * u && p[0] < gl + gw + 50.0 * u)).collect();
        let mut art = Art {
            g, scale, store: Vec::new(), lyre_at, pt, route, run, nrm, open_run, strands: Vec::new(),
            band: Laid { id: 0, rect: [0.0; 4] }, tiles: Vec::new(), border: Laid { id: 0, rect: [0.0; 4] }, strand_pics: Vec::new(), curls: Vec::new(),
            stalks: Laid { id: 0, rect: [0.0; 4] }, glint: 0, lyre: 0, aura: 0, string: 0, cecilia: Vec::new(), bud: Vec::new(),
            hero: Vec::new(), hero_at: Vec::new(), updraft: Vec::new(), updraft_at: Vec::new(), released: Vec::new(),
            released_leaf: [0, 0], released_leaf_phase: matched(0.7, 1.6, 0.6), feather: Vec::new(), leaf: Vec::new(),
            leaves: LEAVES.iter().map(|l| (l.0, l.1, l.2, l.3, matched(l.4, 1.7, 0.7), l.5, l.6, l.7, l.8)).collect(), seed: 0, birds: [0; 7],
        };
        let still = super::angle(super::STILL);
        let xy = |x: f64, y: f64| g.at(x, y, false);
        let lp = |x: f64, y: f64| art.lyre_pt(x, y, still, 0.0);
        let ends = [
            [lp(STARTS[0].0, STARTS[0].1), lp(95.0, -150.0), xy(250.0, 30.0), xy(350.0, 15.0)],
            [lp(STARTS[1].0, STARTS[1].1), lp(115.0, -110.0), xy(262.0, 72.0), xy(310.0, 62.0)],
            [lp(STARTS[2].0, STARTS[2].1), lp(110.0, -80.0), xy(268.0, 122.0), xy(302.0, 110.0)],
        ];
        art.strands = wind::strand_lines(ends, u);
        let d = u * scale;
        let ss = 2.0 * d;
        let band = bared(wind::band(&g, lyre_at, scale), &g, scale);
        art.band = art.lay(band);
        let border = bared(wind::border(&g, &art.route, &art.run, &art.nrm, scale), &g, scale);
        art.tiles = border_tiles(&art, &border.pic);
        art.border = art.lay(border);
        for k in 0..3 {
            let p = wind::strokes_image(&art.strands[k..=k], scale, d);
            let laid = art.lay(p);
            art.strand_pics.push(laid);
        }
        art.glint = art.add(wind::glint(scale));
        for p in wind::curls(&g, scale) {
            let laid = art.lay(p);
            art.curls.push(laid);
        }
        let ppr = SHARP * pt * scale;
        art.lyre = art.add(lyre_art::lyre_image(super::LEAN, ppr, true));
        art.aura = art.add(lyre_art::aura(ppr));
        art.string = art.add(lyre_art::string_glow(ppr));
        for (k, s) in SPRIG.iter().enumerate() {
            let id = art.add(sprites::cecilia(s.3 * 0.72, s.4, 40 + k as u32, ss));
            art.cecilia.push(id);
        }
        for s in BUDS {
            let id = art.add(sprites::bud(s.3 * 1.7, s.4, ss));
            art.bud.push(id);
        }
        let pair = |art: &mut Art, p: [Pic; 2]| { let [a, b] = p; [art.add(a), art.add(b)] };
        for (x, y, r, a, ph, ember, seed) in HERO {
            let ids = pair(&mut art, sprites::maple_pair(r, a, ember, seed, ss));
            art.hero.push(ids);
            art.hero_at.push((x, y, r, a, matched(ph, 1.1, 0.82)));
        }
        for (x, y, r, a, ph) in [(1548.0, 766.0, 26.0, -40.0, 0.9), (1592.0, 698.0, 23.0, 30.0, 2.4)] {
            let ids = pair(&mut art, sprites::maple_pair(r, a, false, x as u64, ss));
            art.updraft.push(ids);
            art.updraft_at.push((x, y, r, a, matched(ph, 2.0, 0.6)));
        }
        for (_, _, a, length, seed) in RELEASED {
            let id = art.add(sprites::feather(length, a, seed, ss, 0.06));
            art.released.push(id);
        }
        art.released_leaf = pair(&mut art, sprites::maple_pair(22.0, 30.0, true, 33, ss));
        for f in FEATHERS {
            let id = art.add(sprites::feather(f.3, f.2, f.4, ss, 0.06));
            art.feather.push(id);
        }
        for (k, l) in LEAVES.iter().enumerate() {
            let ids = pair(&mut art, sprites::maple_pair(l.2, l.3, l.5, 10 + k as u64, ss));
            art.leaf.push(ids);
        }
        art.seed = art.add(sprites::seed(18.0, ss));
        let mut ids = [0; 7];
        for (k, (name, wide)) in [("flyer", 47.0), ("flyer_blink", 47.0), ("wing", 47.0), ("perch", 57.0), ("perch_blink", 57.0), ("lily", 70.0), ("lily_blink", 70.0)].iter().enumerate() {
            ids[k] = art.add(birds::bird(name, wide * ss)?);
        }
        art.birds = ids;
        let curves: Vec<[(f64, f64); 3]> = SPRIG.iter().chain(BUDS.iter()).map(|s| [s.0, s.1, s.2]).collect();
        let stalks = wind::stalks(&g, &curves);
        art.stalks = art.lay(stalks);
        let _ = CX;
        Ok(art)
    }
}

/// _border's squares: each strip cut in 128-pixel squares from its corner, the empty left out, and the points
/// of the current within 90 points of each (to show it as the current is drawn).
fn border_tiles(art: &Art, pic: &Pic) -> Vec<([f64; 4], Vec<usize>)> {
    let (g, scale, u) = (art.g, art.scale, art.g.u);
    let deep = (124.0 * u * scale).ceil() / scale;
    let room = (40.0 * u * scale).ceil() / scale;
    let cut = (room * scale).round_ties_even() as usize;
    let mut out = Vec::new();
    for (sx, sy, sw, sh) in [(0.0, 0.0, g.width, deep), (0.0, g.height - deep, g.width, deep), (0.0, deep, deep, g.height - 2.0 * deep), (g.width - deep, deep, deep, g.height - 2.0 * deep)] {
        let w = ((sw + 2.0 * room) * scale).ceil() as usize - 2 * cut;
        let h = ((sh + 2.0 * room) * scale).ceil() as usize - 2 * cut;
        let (ox, oy) = ((sx * scale).round() as usize, (sy * scale).round() as usize);
        for y in (0..h).step_by(128) {
            for x in (0..w).step_by(128) {
                let (tw, th) = (128.min(w - x), 128.min(h - y));
                let any = (0..th).any(|j| (0..tw).any(|i| pic.px.get((oy + y + j) * pic.w + ox + x + i).is_some_and(|p| p[3] > 0)));
                if !any {
                    continue;
                }
                let rect = [sx + x as f64 / scale, sy + y as f64 / scale, sx + (x + tw) as f64 / scale, sy + (y + th) as f64 / scale];
                let m = 90.0 * u;
                let mut near: Vec<usize> = (0..art.route.len())
                    .filter(|&i| { let [px, py] = art.route[i]; px > rect[0] - m && px < rect[2] + m && py > rect[1] - m && py < rect[3] + m })
                    .collect();
                if near.is_empty() {
                    near.push(0);
                }
                out.push((rect, near));
            }
        }
    }
    out
}
