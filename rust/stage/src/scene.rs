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
    /// Everything drawn t seconds in.
    fn frame(&mut self, t: f64) -> Frame;
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

/// The scene with this key made for a stage; None for a key whose port is not in this build yet.
pub fn make(key: &str, stage: &Stage) -> Option<Box<dyn Scene>> {
    let scene: Box<dyn Scene> = match key {
        "stars" => Box::new(Stars::make(stage)),
        // stub: scene-<key>. Each scene package adds its line here: "ice" => Box::new(Ice::make(stage)).
        _ => return None,
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
        assert!(make("ice", &stage).is_none());
    }
}
