//! 毛茸茸保护协会, ported from blacklist_detect/love_scenes/fluffy.py: the screen becomes a teal
//! notebook page doodled by hand, a name tab drops in, two pens draw the frame round the screen,
//! binder rings pop on, fluffy cats peek over the frame's line, puffy ❖ stars and doodles, paw prints.
//!
//! Every picture fluffy.py works out per pixel with numpy (the paper band, the fur, the stickers)
//! is worked out the same way here on the CPU, numpy's own random numbers included (`pcg`); each
//! frame lays them on the lobby on the graphics chip (`gpu`). The shapes Qt builds with its path
//! booleans, strokes and fonts come from Qt once, at unit size (`shapes.txt`, gen_shapes.py).

mod bake;
mod frame;
pub mod gpu;
mod lines;
mod paper;
mod pcg;
mod pixels;
mod sprite;

use bake::{fills, outline, parts, sticker, Ink, Look, Part, Pic, Shapes};
use lines::{fillet, even, Line};
use pixels::Canvas;
use crate::draw::{hex, Pt};
use crate::pyrand::PyRandom;
use sprite::Atlas;

pub use frame::Shot;

pub const DURATION: f64 = 5.0;
const INK: &str = "#2b6268";
const TEAL: &str = "#5fbdb8";
const MINT: &str = "#a8e6dc";
const PAPER: &str = "#fbfdfb";
const BAND: &str = "#a9d6d2";
const BEAD: &str = "#a6dcf6";
const PINK: &str = "#f6aabd";
const CHALK: &str = "#e2f7f2";
const PRINT: &str = "#ffd9e2";
const FACES: [&str; 3] = ["open", "blink", "flick"];
const DESIGN: [f64; 2] = [1635.0, 848.0];

/// light.rgb: a color as 0..1 floats.
fn rgb(color: &str) -> [f32; 3] {
    hex(color)
}

type Rect = [f64; 4];

fn contains(r: Rect, x: f64, y: f64) -> bool {
    r[0] <= x && x <= r[0] + r[2] && r[1] <= y && y <= r[1] + r[3]
}

/// A cat peeking over the frame: where, its head's width, which way it looks in, when it pops up,
/// which side its tail is on (0: none); and its pictures (atlas ids): faces, paws, tail, edge.
struct Cat {
    base: Pt,
    size: f64,
    turn: f64,
    when: f64,
    tail: f64,
    faces: [(usize, Rect); 3],
    paws: (usize, Rect),
    tail_pic: (usize, Rect),
    edge: (usize, Rect),
}

pub struct Fluffy {
    pub width: f64,
    pub height: f64,
    pub gap: Rect,
    u: f64,
    right: f64,
    pens: Vec<[Line; 2]>,
    rings: Vec<(f64, f64)>,
    tab: (usize, Rect, Pt),
    ring: (usize, Rect),
    paw: (usize, Rect),
    cats: Vec<Cat>,
    stars: Vec<(f64, f64, f64, usize, Rect, f64)>,
    doodles: Vec<(Line, f64, f64)>,
    trails: Vec<Vec<(Pt, f64)>>,
    sparkles: Vec<[f64; 4]>,
    band: Vec<([usize; 4], Canvas)>,
    pub atlas: Atlas,
}

impl Fluffy {
    /// love_scenes.sample_stage(width, height): the sample lobby's button gap at this size.
    pub fn sample(width: f64, height: f64) -> Self {
        let s = width / DESIGN[0];
        let keep = [549.0 * s, 749.0 * s, 556.0 * s, 94.0 * s];
        Self::new(width, height, [keep[0] - 28.0 * s, keep[1] - 30.0 * s, keep[2] + 56.0 * s, height - keep[1] + 30.0 * s])
    }

    pub fn new(width: f64, height: f64, gap: Rect) -> Self {
        let scale = 1.0;
        let u = (width / DESIGN[0]).min(height / DESIGN[1]);
        let shapes = Shapes::load();
        let mut rnd = PyRandom::new(41);
        let (edge, right, corner) = (16.0 * u, 32.0 * u, 26.0 * u);
        let routes: Vec<Vec<Pt>> = [(edge, gap[0] - 4.0 * u), (width - right, gap[0] + gap[2] + 4.0 * u)]
            .iter()
            .map(|&(x0, x1)| {
                let corners = [[width / 2.0, edge, 0.0], [x0, edge, corner], [x0, height - edge, corner], [x1, height - edge, 10.0 * u], [x1, height + 2.0 * u, 0.0]];
                even(&fillet(&corners), 2.5 * u, false)
            })
            .collect();
        let mut inside: Vec<Pt> = routes[0].iter().rev().copied().collect();
        inside.extend(&routes[1]);
        let pens = vec![frame::frame_lines(&routes[0], -1.0, &mut rnd, u, gap), frame::frame_lines(&routes[1], 1.0, &mut rnd, u, gap)];
        let rings = frame::ring_stops(&routes[1], width - right, edge + corner + 20.0 * u, height - edge - corner - 16.0 * u, 50.0 * u);
        let mut pics: Vec<Canvas> = Vec::new();
        let add = |pic: Pic, pics: &mut Vec<Canvas>| {
            pics.push(pic.canvas);
            (pics.len() - 1, pic.rect)
        };
        let cat_at = [([108.0 * u, height - edge], 112.0 * u, 0.0, 1.05, 1.0), ([edge, height * 0.43], 58.0 * u, 90.0, 1.25, 0.0), ([width - 106.0 * u, height - edge], 66.0 * u, 0.0, 1.6, 0.0), ([width - 154.0 * u, height - edge], 50.0 * u, 0.0, 1.72, -1.0)];
        let mut cats = Vec::new();
        for (index, &(base, size, turn, when, tail)) in cat_at.iter().enumerate() {
            let coat = index as u32;
            let faces = FACES.map(|face| add(cat_picture(&shapes, index, face, size, scale), &mut pics));
            let paws = add(fur_picture(&shapes, &format!("paws{index}"), size, scale, Look { soft: size * 0.05, seed: 31 + coat, shadow: size * 0.012, ..fur() }), &mut pics);
            let tail_pic = add(fur_picture(&shapes, &format!("tail{index}"), size, scale, Look { soft: size * 0.05, seed: 41 + coat, cut: Some(0.0), ..fur() }), &mut pics);
            let m = sprite::Affine::ID.translate(base[0], base[1]).rotate(turn);
            let line: pixels::Shape = paper::edge(size, 43 + coat, u).into_iter().map(|(s, p)| (s, p.into_iter().map(|q| m.map(q)).collect())).collect();
            let edge = add(paper::ink_sprite(&line, INK), &mut pics);
            cats.push(Cat { base, size, turn, when, tail, faces, paws, tail_pic, edge });
        }
        let star_at = [
            (70.0, 74.0, 24.0, MINT, 0.75), (160.0, 160.0, 14.0, BEAD, 1.05), (268.0, 46.0, 12.0, MINT, 0.9), (46.0, 300.0, 17.0, MINT, 1.2), (172.0, 392.0, 11.0, BEAD, 1.45),
        ];
        let mut stars: Vec<(f64, f64, f64, &str, f64)> = star_at.iter().map(|&(x, y, r, c, w)| (x * u, y * u, r * u, c, w)).collect();
        stars.extend([
            (150.0 * u, height - 330.0 * u, 13.0 * u, MINT, 1.6), (width - 405.0 * u, 46.0 * u, 15.0 * u, BEAD, 0.95), (width - 300.0 * u, 136.0 * u, 23.0 * u, MINT, 0.8),
            (width - 150.0 * u, 72.0 * u, 17.0 * u, MINT, 1.1), (width - 92.0 * u, 236.0 * u, 12.0 * u, BEAD, 1.35), (width - 74.0 * u, height * 0.53, 11.0 * u, MINT, 1.55),
            (width - 238.0 * u, height - 106.0 * u, 12.0 * u, MINT, 2.0), (width / 2.0 - 215.0 * u, 28.0 * u, 10.0 * u, MINT, 0.6), (width / 2.0 + 215.0 * u, 28.0 * u, 10.0 * u, MINT, 0.65),
        ]);
        let stars = stars.into_iter().map(|(x, y, r, tint, when)| {
            let (id, rect) = add(star_sticker(&shapes, r, tint, scale), &mut pics);
            (x, y, r, id, rect, when)
        }).collect();
        let ring = add(paper::binder(&shapes, 11.0 * u, scale), &mut pics);
        let paw = add(paper::paw_print(&shapes, 34.0 * u, scale), &mut pics);
        let tab_rect = [width / 2.0 - 165.0 * u, 4.0 * u, 330.0 * u, 44.0 * u];
        let (tab_id, tab_box) = add(tab_sticker(&shapes, u, scale), &mut pics);
        let tab = (tab_id, tab_box, [tab_rect[0] + tab_rect[2] / 2.0, tab_rect[1] + tab_rect[3] / 2.0]);
        let doodles = vec![
            (lines::doodle([186.0 * u, 172.0 * u], [520.0 * u, 120.0 * u], 4, 11.0 * u, &mut rnd, u), 1.0, 1.8),
            (lines::doodle([width - 470.0 * u, 222.0 * u], [width - 190.0 * u, 190.0 * u], 3, 11.0 * u, &mut rnd, u), 1.3, 2.05),
        ];
        let hop = |i: usize| if i % 2 == 1 { 9.0 } else { -9.0 };
        let trails: Vec<Vec<(Pt, f64)>> = [
            (0..8).map(|i| ([(200.0 + 44.0 * i as f64) * u, height - (52.0 + hop(i)) * u], 1.5 + 0.2 * i as f64)).collect::<Vec<_>>(),
            (0..7).map(|i| ([width - (478.0 - 44.0 * i as f64) * u, height - (54.0 + hop(i)) * u], 2.15 + 0.2 * i as f64)).collect(),
        ]
        .into_iter()
        .map(|trail| trail.into_iter().filter(|(at, _)| !(gap[0] - 24.0 * u < at[0] && at[0] < gap[0] + gap[2] + 24.0 * u)).collect())
        .collect();
        let names = [width * 0.13, height * 0.29, width * 0.81, height * 0.55];
        let title = [width * 0.38 - 20.0 * u, height * 0.07, width * 0.3 + 40.0 * u, height * 0.18];
        let keep = [names, title, [gap[0] - 30.0 * u, gap[1] - 30.0 * u, gap[2] + 60.0 * u, gap[3] + 30.0 * u]];
        let mut sparkles = Vec::new();
        while sparkles.len() < 22 {
            let (x, y) = (rnd.uniform(30.0 * u, width - 50.0 * u), rnd.uniform(30.0 * u, height - 30.0 * u));
            if !keep.iter().any(|&r| contains(r, x, y)) {
                sparkles.push([x, y, rnd.uniform(4.0, 8.0) * u, rnd.uniform(1.0, 4.0)]);
            }
        }
        let band = paper::band(width, height, &inside, u, scale);
        let atlas = Atlas::new(pics);
        Self { width, height, gap, u, right, pens, rings, tab, ring, paw, cats, stars, doodles, trails, sparkles, band, atlas }
    }
}

fn fur() -> Look {
    Look { soft: 0.0, gloss: 0.0, grain: 0.0, seed: 1, shadow: 0.0, fur: true, middle: None, blush: None, cut: None }
}

/// _fur for the paws and tails: parts, outline and toes from shapes.txt.
fn fur_picture(shapes: &Shapes, key: &str, s: f64, scale: f64, look: Look) -> Pic {
    let b = shapes.points(&format!("{key}.box"), s);
    let rect = [b[0][0], b[0][1], b[1][0] - b[0][0], b[1][1] - b[0][1]];
    sticker(rect, scale, &parts(shapes, key, s), &look, &[outline(shapes, &format!("{key}.out0"), s)], &fills(shapes, key, s))
}

/// _cat: a chubby cat's head peeking over a line, its face open, blinking or with an ear flicked.
fn cat_picture(shapes: &Shapes, index: usize, face: &str, s: f64, scale: f64) -> Pic {
    let key = format!("cat{index}.{face}");
    let b = shapes.points(&format!("{key}.box"), s);
    let rect = [b[0][0], b[0][1], b[1][0] - b[0][0], b[1][1] - b[0][1]];
    let outlines: Vec<Ink> = (0..).map(|n| format!("{key}.out{n}")).take_while(|k| shapes.has(k)).map(|k| outline(shapes, &k, s)).collect();
    let look = Look { soft: s * 0.13, seed: 21 + index as u32, middle: Some(b[2]), blush: Some(shapes.shape(&format!("{key}.blush"), s)), cut: Some(0.0), ..fur() };
    sticker(rect, scale, &parts(shapes, &key, s), &look, &outlines, &fills(shapes, &key, s))
}

/// _star_sticker: a puffy ❖ in tint, outlined in ink.
fn star_sticker(shapes: &Shapes, r: f64, tint: &str, scale: f64) -> Pic {
    let part = Part { shape: shapes.shape("star.part0", r), color: rgb(tint), lift: 0.0 };
    let ink = Ink { shape: shapes.shape("star.out0", r), width: (r * 0.085).max(0.7), color: rgb(INK) };
    let look = Look { soft: (r * 0.22).max(1.0), gloss: 0.55, grain: 0.03, seed: 5, shadow: (r * 0.08).max(0.6), fur: false, middle: None, blush: None, cut: None };
    sticker([-r * 1.25, -r * 1.25, r * 2.5, r * 2.5], scale, &[part], &look, &[ink], &[])
}

/// _tab: the white paper name tab in an inked edge, 毛茸茸保护协会 on it between two ❖.
fn tab_sticker(shapes: &Shapes, u: f64, scale: f64) -> Pic {
    let parts = [Part { shape: shapes.shape("tab.part0", u), color: rgb(PAPER), lift: 0.0 }, Part { shape: shapes.shape("tab.part1", u), color: rgb(MINT), lift: 0.8 }];
    let inks = [Ink { shape: shapes.shape("tab.out0", u), width: 1.8 * u, color: rgb(INK) }, Ink { shape: shapes.shape("tab.out1", u), width: 0.9 * u, color: rgb(INK) }];
    let words = Ink { shape: shapes.shape("tab.words", u), width: 1.0, color: rgb(INK) };
    let look = Look { soft: 3.0 * u, gloss: 0.12, grain: 0.04, seed: 9, shadow: 2.5 * u, fur: false, middle: None, blush: None, cut: None };
    sticker([-173.0 * u, -30.0 * u, 346.0 * u, 60.0 * u], scale, &parts, &look, &inks, &[words])
}
