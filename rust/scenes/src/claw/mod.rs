//! 演说家遇袭 (love_scenes/claw.py), drawn with wgpu: the 指挥家's fog rolls in, the names are lost in
//! it as ???, notes drift; at three seconds three slashes rip across the middle with a flash, a jolt
//! and pink smoke, the notice comes up top right; then it all clears.
//!
//! As claw.py: the pictures (fog, slashes and their frayed steps, cloud, notice) are made once on the
//! CPU, per pixel, with numpy's generator and the same seeds (`art`, `light`, `rng`); each frame is a
//! list of shapes and pictures (`frame`) shaded per pixel on the chip (`gpu`, `claw.wgsl`). The marks
//! it brings instead of a LOOK from ui_overlay (ring, badge, card, lead) are in `marks`.

pub mod art;
pub mod frame;
pub mod geom;
pub mod glyphs;
pub mod hook;
pub mod gpu;
pub mod light;
pub mod marks;
pub mod marks_art;
pub use crate::np as rng;
mod strike;
#[cfg(test)]
mod parity;

use art::{Notice, Slash, LENGTH, SOFT, THICK};
use frame::Frame;
use light::{Pic, Pt};
use crate::draw::{ease_in, ease_in_out, ease_out, win};
use crate::pyrand::PyRandom;

pub const DURATION: f64 = 6.6;
const FOG_IN: (f64, f64) = (0.35, 1.4);
const FOG_OUT: (f64, f64) = (4.75, 5.9);
pub const PINK: &str = "#ff9ad5";
/// The strike lands at 3 s; the three slashes' offsets across it and their delays.
const STRIKE: f64 = 3.0;
const SLASHES: [(f64, f64); 3] = [(-1.0, 0.0), (0.0, 0.035), (1.0, 0.07)];
const LANDED: f64 = STRIKE + 0.07 + 0.075;

/// A note in the fog: where it starts, which glyph, its size, phase, side and when it comes.
struct Note {
    at: Pt,
    shape: usize,
    size: f64,
    phase: f64,
    side: f64,
    born: f64,
}

/// Texture numbers of the scene's pictures once uploaded.
#[derive(Clone, Copy, Default)]
pub struct Textures {
    fog: [usize; 2],
    keep: usize,
    cloud: usize,
    veil: usize,
    slashes: [usize; 3],
    frayed: [[usize; 6]; 3],
    notice: [usize; 4],
}

pub struct Claw {
    width: f64,
    height: f64,
    u: f64,
    centre: Pt,
    seats: Vec<[f64; 4]>,
    unknown: Vec<(Vec<Vec<Pt>>, f64)>,
    notes: Vec<Note>,
    note_shapes: Vec<Vec<Vec<Pt>>>,
    puff: Vec<[f64; 4]>,
    fog: [Pic; 2],
    keep: Pic,
    cloud: Pic,
    slashes: Vec<Slash>,
    notice: Notice,
    tex: Textures,
}

/// A glyph's contours at 100 pixels, scaled by s and moved by (dx, dy).
fn glyph(shape: &[&[[f32; 2]]], s: f64, dx: f64) -> Vec<Vec<Pt>> {
    shape.iter().map(|c| c.iter().map(|p| [f64::from(p[0]) * s + dx, f64::from(p[1]) * s]).collect()).collect()
}

/// Contours moved so their bounding box is centred on 0, and its width.
fn centred(mut contours: Vec<Vec<Pt>>) -> (Vec<Vec<Pt>>, f64) {
    let mut b = [f64::MAX, f64::MAX, f64::MIN, f64::MIN];
    for p in contours.iter().flatten() {
        b = [b[0].min(p[0]), b[1].min(p[1]), b[2].max(p[0]), b[3].max(p[1])];
    }
    let (cx, cy) = ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0);
    for p in contours.iter_mut().flatten() {
        *p = [p[0] - cx, p[1] - cy];
    }
    (contours, b[2] - b[0])
}

impl Claw {
    /// The scene on a stage width x height: gap (x, y, w, h) the bare area round the button, seats the
    /// twelve name boxes (x, y, w, h), assets the folder with orator_paper.png and orator_words.png.
    pub fn new(width: f64, height: f64, gap: [f64; 4], seats: &[[f64; 4]], assets: &std::path::Path) -> Result<Self, String> {
        let u = (width / 1635.0).min(height / 848.0);
        let mut rnd = PyRandom::new(19);
        let centre = art::landing(width, height, u, &SLASHES.map(|s| s.0));
        let px = light::pyround(34.0 * u).max(6.0) / 100.0;
        let note_shapes: Vec<Vec<Vec<Pt>>> = glyphs::NOTES.iter().map(|g| centred(glyph(g, px, 0.0)).0).collect();
        let notes = (0..10)
            .map(|i| {
                let side = if i % 2 == 0 { -1.0 } else { 1.0 };
                let x = width * (0.5 + side * rnd.uniform(0.3, 0.46));
                let y = height * rnd.uniform(if side < 0.0 { 0.12 } else { 0.3 }, 0.72);
                let shape = rnd.choice(&[0usize, 1, 2, 3]);
                let (size, phase) = (rnd.uniform(0.7, 1.5), rnd.uniform(0.0, std::f64::consts::TAU));
                Note { at: [x, y], shape, size, phase, side, born: 0.55 + f64::from(i) * 0.15 }
            })
            .collect();
        let puff = (0..16).map(|_| [rnd.uniform(0.0, std::f64::consts::TAU), rnd.uniform(40.0, 150.0) * u, rnd.uniform(26.0, 60.0) * u, rnd.uniform(0.0, 0.12)]).collect();
        let unknown = seats
            .iter()
            .map(|s| {
                let k = light::pyround(s[3] * 0.9).max(6.0) / 100.0;
                let step = f64::from(glyphs::QUESTION_ADVANCE) * k + s[3] * 0.08;
                centred((0..3).flat_map(|i| glyph(glyphs::QUESTION, k, f64::from(i) * step)).collect())
            })
            .collect();
        let sprite = art::slash_sprite(LENGTH * u, THICK * u, u);
        let frayed: Vec<Pic> = (0..art::FRAYS).map(|i| art::frayed(&sprite, (i + 1) as f32 / art::FRAYS as f32, i as u32)).collect();
        let slashes = SLASHES.iter().map(|&(o, _)| art::cleared(&sprite, &frayed, art::place(centre, o, u), gap, u)).collect();
        Ok(Self {
            width,
            height,
            u,
            centre,
            seats: seats.to_vec(),
            unknown,
            notes,
            note_shapes,
            puff,
            fog: [art::fog_layer(width, height, u, 11, 1.0), art::fog_layer(width, height, u, 23, 0.85)],
            keep: art::keep(width, height, gap, u),
            cloud: art::cloud(u),
            slashes,
            notice: art::notice_art(u, assets)?,
            tex: Textures::default(),
        })
    }

    /// The sample lobby's stage at width x height (love_scenes.sample_stage): its gap.
    pub fn sample_gap(width: f64, height: f64) -> [f64; 4] {
        let s = width / 1635.0;
        let keep = [549.0 * s, 749.0 * s, 556.0 * s, 94.0 * s];
        [keep[0] - 28.0 * s, keep[1] - 30.0 * s, keep[2] + 56.0 * s, height - keep[1] + 30.0 * s]
    }

    /// Uploads every picture once.
    pub fn upload(&mut self, gpu: &mut gpu::Renderer) {
        let mut add = |p: &Pic| gpu.add(p.w, p.h, &p.bytes());
        let t = Textures {
            fog: [add(&self.fog[0]), add(&self.fog[1])],
            keep: add(&self.keep),
            cloud: add(&self.cloud),
            veil: 0,
            slashes: std::array::from_fn(|i| add(&self.slashes[i].sprite)),
            frayed: std::array::from_fn(|i| std::array::from_fn(|k| add(&self.slashes[i].frayed[k]))),
            notice: [add(&self.notice.paper), add(&self.notice.words), add(&self.notice.soft), add(&self.notice.band)],
        };
        self.tex = Textures { veil: gpu.add_target(self.keep.w, self.keep.h), ..t };
    }

    /// The veil's own frame and its texture, when it shows.
    pub fn veil_target(&self) -> usize {
        self.tex.veil
    }

    /// Draws the scene t seconds in onto `p` (after whatever is under it); returns the veil's frame,
    /// to be drawn first into `veil_target()`, when there is one.
    pub fn paint(&self, t: f64, p: &mut Frame) -> Option<Frame> {
        let life = win(t, 0.0, 0.25) * (1.0 - ease_in(win(t, DURATION - 0.4, DURATION)));
        if life <= 0.0 {
            return None;
        }
        let u = self.u;
        p.save();
        p.opacity = life;
        let j = strike::jolt(t - LANDED, u);
        p.tf = p.tf.translate(j[0], j[1]);
        let veil = self.veil(p, t);
        self.lost_names(p, t);
        self.notes_paint(p, t);
        strike::strike(self, p, t - STRIKE);
        strike::impact(p, t - LANDED, self.centre, u);
        strike::puff(p, t - LANDED, self.centre, &self.puff, u);
        p.restore();
        p.save();
        p.opacity = life;
        strike::notice(self, p, t - STRIKE, [self.width - 26.0 * u, self.height * 0.165]);
        p.restore();
        veil
    }

    fn veil(&self, p: &mut Frame, t: f64) -> Option<Frame> {
        let (u, width, height) = (self.u, self.width, self.height);
        let thick = fog_level(t);
        let flash = strike::flash_level(t - LANDED);
        if thick <= 0.005 && flash <= 0.005 {
            return None;
        }
        let come = ease_out(win(t, FOG_IN.0, FOG_IN.1));
        let mut q = Frame::default();
        q.tf = q.tf.scale(SOFT, SOFT);
        if thick > 0.0 {
            for (index, layer) in self.fog.iter().enumerate() {
                let (i, way) = (index as f64, if index == 0 { 1.0 } else { -1.0 });
                let push = 1.0 + 0.35 * (1.0 - come);
                let (w, h) = (width * 1.16 * push, height * 1.16 * push);
                let x = (width - w) / 2.0 + way * (30.0 * u * (t * 0.7 + i).sin() + 22.0 * u * t);
                let y = (height - h) / 2.0 + 12.0 * u * (t * 0.9 + i * 2.0).sin();
                q.opacity = thick * (0.85 + 0.15 * (t * 1.3 + i).sin());
                q.image(self.tex.fog[index], (layer.w, layer.h), [x, y, w, h], None, None);
            }
            q.opacity = 1.0;
        }
        if flash > 0.0 {
            let stops = crate::prim::stops(&[(0.0, "#f3eeff", 0.55 * flash), (0.5, art::LILAC, 0.32 * flash), (1.0, art::PURPLE, 0.12 * flash)]);
            q.rect([0.0, 0.0, width, height], &crate::prim::Paint::Radial([width * 0.5, height * 0.45], width * 0.75, stops));
        }
        p.image(self.tex.veil, (self.keep.w, self.keep.h), [0.0, 0.0, width, height], None, Some(self.tex.keep));
        Some(q)
    }

    fn lost_names(&self, p: &mut Frame, t: f64) {
        let a = fog_level(t);
        if a <= 0.0 {
            return;
        }
        let u = self.u;
        for (index, (seat, (path, width))) in self.seats.iter().zip(&self.unknown).enumerate() {
            let i = index as f64;
            let c = [seat[0] + seat[2] / 2.0, seat[1] + seat[3] / 2.0];
            let (w, h) = ((seat[2] * 1.6).max(150.0 * u), seat[3] * 2.3);
            let drift = 4.0 * u * (t * 1.3 + i).sin();
            p.save();
            p.opacity *= a;
            p.image(self.tex.cloud, (self.cloud.w, self.cloud.h), [c[0] - w / 2.0 + drift, c[1] - h / 2.0, w, h], None, None);
            let glitch = (t * 17.0 + i * 3.1).sin() > 0.94;
            p.tf = p.tf.translate(c[0] + if glitch { 3.0 * u } else { 0.0 }, c[1]);
            p.soft_dot(0.0, 0.0, width.max(30.0 * u) * 0.75, "#dfe6ff", 0.25);
            p.path(path, &crate::prim::solid("#f4f6ff", if glitch { 0.55 } else { 0.95 }));
            p.restore();
        }
    }

    fn notes_paint(&self, p: &mut Frame, t: f64) {
        let u = self.u;
        for n in &self.notes {
            let a = ease_out(win(t, n.born, n.born + 0.5)) * (1.0 - ease_in(win(t, FOG_OUT.0, FOG_OUT.1 - 0.3)));
            if a <= 0.0 {
                continue;
            }
            let age = t - n.born;
            let x = n.at[0] + n.side * 26.0 * u * (age * 1.4 + n.phase).sin() - n.side * 18.0 * u * age;
            let y = n.at[1] - 30.0 * u * age + 10.0 * u * (age * 2.1 + n.phase).cos();
            p.save();
            p.tf = p.tf.translate(x, y).rotate(18.0 * (age * 1.7 + n.phase).sin()).scale(n.size, n.size);
            p.soft_dot(0.0, 0.0, 30.0 * u, "#e9f1ff", 0.22 * a);
            p.path(&self.note_shapes[n.shape], &crate::prim::solid("#f6f9ff", 0.85 * a));
            p.restore();
        }
    }
}

/// How thick the fog is: rolling in, then clearing.
fn fog_level(t: f64) -> f64 {
    ease_out(win(t, FOG_IN.0, FOG_IN.1)) * (1.0 - ease_in_out(win(t, FOG_OUT.0, FOG_OUT.1)))
}

/// The sample stage's twelve name boxes at 1920x1080 (love_scenes.sample_stage(1920, 1080).names()).
pub fn seats_1920() -> [[f64; 4]; 12] {
    [
        [203.52, 525.96, 275.52, 43.2],
        [502.08, 528.12, 247.104, 39.96],
        [772.224, 521.64, 230.4, 48.6],
        [1025.856, 524.88, 241.92, 45.36],
        [1307.52, 524.88, 232.32, 47.52],
        [1570.56, 525.96, 232.32, 44.28],
        [232.32, 839.16, 248.64, 43.2],
        [504.0, 835.92, 241.344, 48.6],
        [775.68, 835.92, 236.16, 47.52],
        [1040.64, 834.84, 236.16, 45.36],
        [1301.76, 839.16, 241.92, 42.12],
        [1566.72, 838.08, 272.64, 43.2],
    ]
}
