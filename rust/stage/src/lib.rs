//! stage: where and how a 嘉宾 scene plays over the game (blacklist_detect/ui_love.py and
//! love_scenes.Stage), part of the Rust rewrite (docs/dev/research/rust-plan-2026-11-18.md).
//!
//! - `geom`: the Stage (size, the bare gap round the button, the 嘉宾 badge, the seats) and how
//!   LoveBorder.play makes it from the game's screen and the button.
//! - `pick`: which scene plays (love_scenes.choose, LoveBorder.pick / draw_again / heard).
//! - `clock`: the lifecycle: play, a 33 ms tick, the scene's clock, stop, waiting for a heavy scene's pictures.
//! - `scene`: the `Scene` trait every scene package implements, the adapter for stars.rs's shape, and
//!   `make`, the scenes this build has.
//! - `paint`: the scenes shader drawing onto any texture (offscreen, or a swap chain's).
//! - `window` (Windows): the topmost, click-through, see-through window the frames show in:
//!   DirectComposition first, a layered window fed by GPU readback as the fallback.
//!
//! A scene package implements `Scene` (and `MakeScene`) and adds one line to `scene::make`:
//!
//! ```ignore
//! impl Scene for Ice { fn duration(&self) -> f64 { 5.0 } fn frame(&mut self, t: f64) -> Frame { self.paint(t) } }
//! impl MakeScene for Ice { fn make(stage: &Stage) -> Self { Ice::new(stage.width, stage.height, stage.gap) } }
//! ```
#![cfg_attr(not(windows), forbid(unsafe_code))]
#![cfg_attr(windows, deny(unsafe_code))]

pub mod clock;
pub mod geom;
pub mod paint;
pub mod pick;
pub mod scene;
#[cfg(windows)]
pub mod window;
