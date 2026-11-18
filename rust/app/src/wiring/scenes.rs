//! The 嘉宾 scenes over the game (LoveBorder through the stage crate): the scene made for the game's screen with
//! the button left bare, its frames drawn on the window's timer until it has run its length.

use super::stubs::{Rect, Stage};

fn xywh(rect: Rect) -> [i32; 4] {
    [rect.x, rect.y, rect.w, rect.h]
}

/// What LoveBorder.play is given: the game's screen, and the button with its marks to leave bare.
pub fn placement(stage: &Stage) -> stage::geom::Placement {
    stage::geom::Placement { area: xywh(stage.game), keep_clear: xywh(stage.button), badge: None, seats: Vec::new() }
}

/// The scene for this key on this stage; None for a key this build has no port of (it plays nothing).
pub fn make(key: &str, stage: &Stage) -> Option<Box<dyn stage::scene::Scene>> {
    stage::scene::make(key, &placement(stage).stage())
}

#[cfg(windows)]
pub use self::windows::StageScenes;

#[cfg(windows)]
mod windows {
    use super::super::stubs::{ScenePlayer, Stage, Target};
    use stage::paint::{Adapter, Gpu};
    use stage::scene::Scene;
    use std::time::Instant;

    struct Playing {
        scene: Box<dyn Scene>,
        window: stage::window::Overlay,
        since: Instant,
    }

    /// The GPU, opened at the first scene, and the scene that plays.
    #[derive(Default)]
    pub struct StageScenes {
        gpu: Option<Gpu>,
        playing: Option<Playing>,
        pub errors: Vec<String>,
    }

    impl StageScenes {
        fn start(&mut self, key: &str, stage: Stage) -> Result<(), String> {
            let Some(mut scene) = super::make(key, &stage) else { return Ok(()) };
            if self.gpu.is_none() {
                self.gpu = Some(Gpu::new(Adapter::Default).or_else(|_| Gpu::new(Adapter::Software))?);
            }
            let Some(gpu) = self.gpu.as_ref() else { return Ok(()) };
            let mut window = stage::window::Overlay::open(gpu, super::xywh(stage.game), None)?;
            if let Some(still) = scene.still() {
                window.set_still(gpu, &still);
            }
            window.present(gpu, &scene.frame(0.0))?;
            window.show()?;
            self.playing = Some(Playing { scene, window, since: Instant::now() });
            Ok(())
        }
    }

    impl ScenePlayer for StageScenes {
        fn play(&mut self, scene_key: &str, stage: Stage) {
            self.stop();
            if stage.target != Target::Screen {
                return;
            }
            if let Err(error) = self.start(scene_key, stage) {
                self.errors.push(format!("Scene {scene_key}: not played: {error}"));
            }
        }

        fn stop(&mut self) {
            if let Some(playing) = self.playing.take() {
                playing.window.hide();
            }
        }

        fn tick(&mut self) {
            let (Some(playing), Some(gpu)) = (self.playing.as_mut(), self.gpu.as_ref()) else { return };
            let t = playing.since.elapsed().as_secs_f64();
            if t >= playing.scene.duration() {
                return self.stop();
            }
            let frame = playing.scene.frame(t);
            if let Err(error) = playing.window.present(gpu, &frame) {
                self.errors.push(format!("Scene: frame not shown: {error}"));
                return self.stop();
            }
            stage::window::pump();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::super::stubs::Target;
    use super::*;

    fn stage() -> Stage {
        Stage { game: Rect { x: -1920, y: 0, w: 1920, h: 1080 }, button: Rect { x: -1371, y: 749, w: 556, h: 94 }, target: Target::Screen }
    }

    #[test]
    fn the_scene_leaves_the_button_bare_on_the_games_screen() {
        let place = placement(&stage());
        assert_eq!(place.area, [-1920, 0, 1920, 1080]);
        let inner = place.stage();
        assert_eq!((inner.width, inner.height), (1920.0, 1080.0));
        // 28 points either side of the button, 30 above it, down to the bottom of the game.
        assert_eq!(inner.gap, [549.0 - 28.0, 749.0 - 30.0, 556.0 + 56.0, 1080.0 - 749.0 + 30.0]);
    }

    #[test]
    fn a_ported_scene_is_made_and_an_unported_one_plays_nothing() {
        assert!(make("stars", &stage()).is_some_and(|scene| scene.duration() > 0.0));
        assert!(make("no-such-scene", &stage()).is_none());
    }
}
