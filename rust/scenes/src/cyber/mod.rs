//! 赛博朋克（一） (blacklist_detect/love_scenes/cyber.py) on the graphics chip: the night, the neon
//! frame, the holographic panels, the scan beam, lightning and its sparks. Pictures the Python
//! scene works out once per pixel are worked out the same way here (`pics`, `light`, numpy's own
//! generator in `npr`) and packed in an atlas; every frame is a list of shapes for `gfx`.

mod bolt;
pub mod canvas;
mod frame;
mod holo;
mod hud;
mod panels;
pub mod gfx;
pub mod light;
pub mod npr;
mod pics;
mod sparks;
mod text;
mod chrome;
#[cfg(test)]
mod tests;

use canvas::{Canvas, Src, ATLAS, LOBBY, SCREEN, WASH};
use gfx::Atlas;
use pics::{dot, flash, frame_glow, night};

use crate::draw::{ease_in, ease_out, hex, win, Pt};
use bolt::{bolt_shapes, strike, strike_light, Shape, LEAD};
use sparks::{heats, shower, spark_shower, Heat, Shower};
use holo::{Holo, Kind};
use hud::{beam, beam_at, beam_picture, cone_picture, sweep_picture, Rail};
use panels::{Mesh, Radar};
use text::Type;

pub const DURATION: f64 = 5.0;
pub const DESIGN: (f64, f64) = (1635.0, 848.0);
pub const CYAN: &str = "#21f6ff";
pub const MAGENTA: &str = "#ff2bd6";
pub const VIOLET: &str = "#7a2cff";
pub const NIGHT: &str = "#07021a";
pub const INDIGO: &str = "#12062e";
/// Glow pictures are worked out at this share of the stage's size.
pub const SOFT: f64 = 0.25;

/// Glitches besides the strikes: (the panel, when, how long, how hard).
const GLITCHES: [(usize, f64, f64, f64); 3] = [(0, 2.55, 0.12, 0.55), (1, 3.5, 0.14, 0.65), (0, 4.0, 0.1, 0.5)];

/// Where each picture sits in the atlas.
pub struct Pics {
    pub night: Src,
    pub flash: [Src; 2],
    pub glow: [Src; 2],
    pub hot: Src,
    pub cyan: Src,
    pub violet: Src,
}

pub struct Cyber {
    pub width: f64,
    pub height: f64,
    pub gap: [f64; 4],
    pub u: f64,
    pub outer: Vec<Pt>,
    pub inner: Vec<Pt>,
    pub panels: [[f64; 4]; 2],
    pub pics: Pics,
    atlas: Atlas,
    /// (when it lands, where from, where to, the panel struck), its two shapes and its shower.
    strikes: Vec<(f64, Pt, Pt, usize, Vec<Shape>, Shower)>,
    heats: Vec<Heat>,
    holos: [Holo; 2],
    rails: [Rail; 2],
    beam: (Src, f64, f64),
    title: [f64; 4],
    ty: Type,
}

/// _lay: a round glow laid on at x, y, r its radius, at alpha (the painter's whole opacity).
pub fn lay_dot(c: &mut Canvas, src: Src, at: Pt, r: f64, alpha: f64) {
    if alpha <= 0.01 || r <= 0.3 {
        return;
    }
    c.opacity = alpha;
    c.lay(ATLAS, src, [at[0] - r, at[1] - r, 2.0 * r, 2.0 * r], 1.0);
}

impl Cyber {
    /// love_scenes.sample_stage(width, height): the sample lobby's button gap at this size.
    pub fn sample(width: f64, height: f64) -> Self {
        let s = width / DESIGN.0;
        let keep = [549.0 * s, 749.0 * s, 556.0 * s, 94.0 * s];
        Self::new(width, height, [keep[0] - 28.0 * s, keep[1] - 30.0 * s, keep[2] + 56.0 * s, height - keep[1] + 30.0 * s])
    }

    pub fn new(width: f64, height: f64, gap: [f64; 4]) -> Self {
        let u = (width / DESIGN.0).min(height / DESIGN.1);
        let outer = frame::frame(width, height, gap, 15.0 * u, 34.0 * u, u);
        let inner = frame::frame(width, height, gap, 25.0 * u, 40.0 * u, u);
        let top = 48.0 * u;
        let left = [50.0 * u, top, (500.0 * u).min(width * 0.38 - 66.0 * u), (184.0 * u).min(height * 0.29 - top - 12.0 * u)];
        let span = (452.0 * u).min(width * 0.32 - 80.0 * u);
        let right = [width - 50.0 * u - span, top, span, left[3]];
        let panels = [left, right];
        let mut atlas = Atlas::new(2048, 2048);
        let pics = Pics {
            night: atlas.add(&night(width, height, u, &panels)),
            flash: [atlas.add(&flash(width, height, gap, u, -1)), atlas.add(&flash(width, height, gap, u, 1))],
            glow: [atlas.add(&frame_glow(width, height, &outer, CYAN, u)), atlas.add(&frame_glow(width, height, &inner, MAGENTA, u))],
            hot: atlas.add(&dot(hex("#bff9ff"), 1.0, 64)),
            cyan: atlas.add(&dot(hex(CYAN), 0.25, 64)),
            violet: atlas.add(&dot(hex(VIOLET), 0.0, 64)),
        };
        let names = [width * 0.13, height * 0.29, width * 0.81, height * 0.55];
        let title = [width * 0.38, height * 0.07, width * 0.3, height * 0.18];
        let wide = [gap[0] - 30.0 * u, gap[1] - 30.0 * u, gap[2] + 60.0 * u, gap[3] + 60.0 * u];
        let (l, r) = (left, right);
        let defs = [
            (1.5, [width * 0.27, -height * 0.03], [l[0] + l[2], l[1] + l[3]], -2.2, 64, 1, 0),
            (2.1, [width * 0.74, -height * 0.03], [r[0], r[1] + r[3]], -0.9, 64, 2, 1),
            (2.75, [width, height * 0.62], [r[0] + r[2], r[1] + r[3]], -2.3, 74, 3, 1),
            (3.3, [0.0, height * 0.6], [l[0], l[1] + l[3]], -0.8, 64, 4, 0),
            (3.8, [width * 0.9, -height * 0.03], [r[0] + r[2], r[1]], 2.6, 50, 5, 1),
        ];
        let strikes = defs
            .iter()
            .map(|&(when, start, end, aim, count, seed, panel)| {
                let shapes = bolt_shapes(start, end, seed, u, &[names, title], &mut atlas);
                (when, start, end, panel, shapes, shower(end, aim, count, u, seed, width, height, &[names, title, wide]))
            })
            .collect();
        let heats = heats(u, &mut atlas);
        let dots = |atlas: &mut Atlas, white: f32| [atlas.add(&dot(hex(CYAN), white, 64)), atlas.add(&dot(hex(MAGENTA), white, 64))];
        let sweep = atlas.add(&sweep_picture(Radar::sweep_side(left, u)));
        let radar = Radar::new(left, u, sweep, dots(&mut atlas, 0.3));
        let (cone_rect, emitter) = Mesh::cone_rect(right, u);
        let cone = atlas.add(&cone_picture(cone_rect, emitter, u));
        let mesh = Mesh::new(right, u, cone, dots(&mut atlas, 0.6));
        let ty = Type::new(u);
        let holos = [Holo::new(left, u, Kind::Radar(radar), 0.45, 1, &mut atlas, &ty), Holo::new(right, u, Kind::Mesh(mesh), 0.7, 2, &mut atlas, &ty)];
        let rails = [Rail::new(88.0 * u, height * 0.34, height * 0.79, -1.0, u), Rail::new(width - 88.0 * u, height * 0.34, height * 0.79, 1.0, u)];
        let (pic, behind, ahead) = beam_picture(height * 0.285, u);
        let beam = (atlas.add(&pic), behind, ahead);
        Self { width, height, gap, u, outer, inner, panels, pics, atlas, strikes, heats, holos, rails, beam, title, ty }
    }

    pub fn atlas(&self) -> &Atlas {
        &self.atlas
    }

    /// The night's wash, drawn once into its own texture before the frames.
    pub fn wash(&self) -> Canvas {
        frame::wash(self)
    }

    /// The frame t seconds in, over the lobby.
    pub fn paint(&self, t: f64) -> Canvas {
        let (w, h) = (self.width, self.height);
        let mut c = Canvas::new();
        c.draw_into(SCREEN, true);
        c.lay(LOBBY, [0.0, 0.0, w, h], [0.0, 0.0, w, h], 1.0);
        let life = win(t, 0.0, 0.3);
        let leave = ease_in(win(t, 4.35, 5.0));
        c.opacity = life;
        let wash = ease_out(win(t, 0.0, 0.7)) * (1.0 - leave);
        if wash > 0.005 {
            c.lay(WASH, [0.0, 0.0, w, h], [0.0, 0.0, w, h], wash);
        }
        let bright = self.strikes.iter().map(|s| strike_light(t - s.0)).fold(0.0, f64::max);
        // A strike lights its own side of the screen most.
        for (side, &flash) in [-1.0, 1.0].iter().zip(&self.pics.flash) {
            let near = self
                .strikes
                .iter()
                .map(|s| strike_light(t - s.0) * if (s.2[0] < w / 2.0) == (*side < 0.0) { 1.0 } else { 0.3 })
                .fold(0.0, f64::max);
            if near * (1.0 - leave) > 0.01 {
                c.opacity = life * near * (1.0 - leave);
                c.lay(ATLAS, flash, [0.0, 0.0, w, h], 1.0);
            }
        }
        c.opacity = life;
        frame::neon_frame(&mut c, self, t, bright);
        for rail in &self.rails {
            rail.paint(&mut c, t, 1.0 - leave, &self.ty);
        }
        let at = beam_at(t, w, self.beam.1);
        for (index, holo) in self.holos.iter().enumerate() {
            let struck: Vec<f64> = self.strikes.iter().filter(|s| s.3 == index).map(|s| s.0).collect();
            let mut tear: f64 = struck.iter().map(|&when| (std::f64::consts::PI * win(t, when, when + 0.24)).sin()).fold(f64::MIN, f64::max);
            for (which, when, length, k) in GLITCHES {
                if which == index {
                    tear = tear.max(k * (std::f64::consts::PI * win(t, when, when + length)).sin());
                }
            }
            let surge = struck.iter().map(|&when| strike_light(t - when)).fold(f64::MIN, f64::max);
            holo.paint(&mut c, t, index, tear, surge, at.map(|a| a.0), &self.ty);
        }
        beam(&mut c, at, self.beam, h * 0.285, self.title, self.u);
        for (when, start, end, _panel, shapes, _shower) in &self.strikes {
            if (-LEAD..=0.55).contains(&(t - when)) {
                strike(&mut c, self, t - when, *start, *end, shapes);
            }
        }
        for (when, .., shower) in &self.strikes {
            spark_shower(&mut c, t - when, shower, &self.heats, self.u);
        }
        c
    }
}
