//! 赛博朋克（一） (blacklist_detect/love_scenes/cyber.py) on the graphics chip: the night, the neon
//! frame, the holographic panels, the scan beam, lightning and its sparks. Pictures the Python
//! scene works out once per pixel are worked out the same way here (`pics`, `light`, numpy's own
//! generator in `npr`) and packed in an atlas; every frame is a list of shapes for `gfx`.

pub mod canvas;
mod frame;
pub mod gfx;
pub mod light;
pub mod npr;
mod pics;

use canvas::{Canvas, Src, ATLAS, LOBBY, SCREEN, WASH};
use gfx::Atlas;
use pics::{dot, flash, frame_glow, night};

use crate::draw::{ease_in, ease_out, win, Pt};

pub const DURATION: f64 = 5.0;
pub const DESIGN: (f64, f64) = (1635.0, 848.0);
pub const CYAN: &str = "#21f6ff";
pub const MAGENTA: &str = "#ff2bd6";
pub const VIOLET: &str = "#7a2cff";
pub const NIGHT: &str = "#07021a";
pub const INDIGO: &str = "#12062e";
/// Glow pictures are worked out at this share of the stage's size.
pub const SOFT: f64 = 0.25;

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
            hot: atlas.add(&dot("#bff9ff", 1.0, 64)),
            cyan: atlas.add(&dot(CYAN, 0.25, 64)),
            violet: atlas.add(&dot(VIOLET, 0.0, 64)),
        };
        Self { width, height, gap, u, outer, inner, panels, pics, atlas }
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
        let bright = 0.0;
        frame::neon_frame(&mut c, self, t, bright);
        c
    }
}
