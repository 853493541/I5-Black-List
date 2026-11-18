//! The trait every 嘉宾 scene implements, and the scenes this build has.

use scenes::prim::Frame;
use scenes::stars::Stars;

use crate::clock::duration;
use crate::geom::Stage;

/// A 嘉宾 scene: made once for a stage, then asked for its shapes at t seconds into its play.
///
/// Frames are `scenes::prim::Frame`s: shapes the GPU shades pixel by pixel, in the Python painter's
/// order. A whole-frame picture on layer 0 is the lobby (shown only in previews; over the game it is
/// left out, the game itself shows through), layer 1 is the scene's still picture from `still`, drawn
/// once per stage (the Python scenes' cached Wash).
///
/// Randomness is the Python scene's own: each scene seeds `scenes::pyrand::PyRandom` with the seeds its
/// Python module uses, so stars and dust sit where they do in Python; no seed is passed in.
pub trait Scene {
    /// Its length in seconds (the module's DURATION).
    fn duration(&self) -> f64;
    /// The still picture shown through layer-1 pictures, drawn once; None for a scene without one.
    fn still(&self) -> Option<Frame> {
        None
    }
    /// Everything drawn t seconds in. For a scene with its own renderer, one picture of the still (layer 1).
    fn frame(&mut self, t: f64) -> Frame;
    /// A scene drawn by its own renderer (`scene_own`): its frame at t as premultiplied RGBA bytes of the
    /// stage's size, to be made the still picture (`Painter::set_still_pixels`) before `frame(t)` is drawn
    /// (see `shoot`). None for a scene drawn as shapes (stars).
    fn pixels(&mut self, _t: f64) -> Option<Vec<u8>> {
        None
    }
    /// A scene made on the stage's device (`make_on`): draws its frame at t straight into `still` (the
    /// window's still texture, `Overlay::still_texture`) by a copy on the chip; false when it cannot
    /// (shapes, or a device of its own), and `shoot` is used instead.
    fn draw_into(&mut self, _t: f64, _still: &wgpu::Texture) -> bool {
        false
    }
}

/// What the window shows at t when the still texture can be written on the chip: the frame, the scene's
/// own picture (if any) copied into `still` first, read back only for a scene on a device of its own.
pub fn shoot_into(scene: &mut dyn Scene, t: f64, still: &wgpu::Texture) -> (Frame, Option<Vec<u8>>) {
    if scene.draw_into(t, still) {
        return (scene.frame(t), None);
    }
    shoot(scene, t)
}

/// `make` on the stage's device, so `shoot_into` copies frames on the chip; the app's path.
pub fn make_on(key: &str, stage: &Stage, gpu: &crate::paint::Gpu) -> Option<Box<dyn Scene + Send>> {
    let scene: Box<dyn Scene + Send> = match key {
        "stars" => Box::new(Stars::make(stage)),
        _ => Box::new(crate::scene_own::make_own_on(key, stage, gpu).ok()?),
    };
    Some(scene)
}

/// What the window shows at t: the frame, and the still picture's bytes to set first, when there are any.
pub fn shoot(scene: &mut dyn Scene, t: f64) -> (Frame, Option<Vec<u8>>) {
    let pixels = scene.pixels(t);
    (scene.frame(t), pixels)
}

/// A scene that can be made for a stage; `make` below lists them by key.
pub trait MakeScene: Scene + Sized {
    fn make(stage: &Stage) -> Self;
}

/// stars.rs's shape (new(width, height, gap), paint(t), milky_way()) is the shape every scene package
/// builds today; this is its adapter, and the pattern for the rest.
impl Scene for Stars {
    fn duration(&self) -> f64 {
        scenes::stars::DURATION
    }
    fn still(&self) -> Option<Frame> {
        Some(self.milky_way())
    }
    fn frame(&mut self, t: f64) -> Frame {
        self.paint(t)
    }
}

impl MakeScene for Stars {
    fn make(stage: &Stage) -> Self {
        Stars::new(stage.width, stage.height, stage.gap)
    }
}

/// Every scene key (love_scenes.SCENES).
pub const KEYS: [&str; 11] = ["classic", "lace", "stars", "ice", "cyber", "neon", "angel", "equation", "fluffy", "claw", "lyre"];

/// The scene with this key made for a stage, its pictures baked (heavy for claw and lyre: call it off the
/// screen's thread for those, clock::WARMED); None for an unknown key, or when it cannot be made here (no
/// graphics chip, a missing font or picture).
pub fn make(key: &str, stage: &Stage) -> Option<Box<dyn Scene + Send>> {
    let scene: Box<dyn Scene + Send> = match key {
        "stars" => Box::new(Stars::make(stage)),
        _ => Box::new(crate::scene_own::make_own(key, stage).ok()?),
    };
    debug_assert_eq!(scene.duration(), duration(key));
    Some(scene)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::geom::sample_stage;

    #[test]
    fn stars_through_the_trait_draws_what_stars_draws() {
        let stage = sample_stage(1920.0, 1080.0);
        let mut scene = make("stars", &stage).expect("stars is ported");
        let direct = Stars::sample(1920.0, 1080.0).paint(1.5);
        let via = scene.frame(1.5);
        assert_eq!(via.prims.len(), direct.prims.len());
        assert!(via
            .prims
            .iter()
            .zip(&direct.prims)
            .all(|(a, b)| bytemuck::bytes_of(a) == bytemuck::bytes_of(b)));
        assert!(scene.still().is_some());
        assert!(scene.pixels(1.5).is_none());
        assert!(make("nothing", &stage).is_none());
    }
}
