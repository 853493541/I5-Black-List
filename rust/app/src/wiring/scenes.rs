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
pub fn make(key: &str, stage: &Stage) -> Option<Box<dyn stage::scene::Scene + Send>> {
    stage::scene::make(key, &placement(stage).stage())
}

#[cfg(windows)]
pub use self::windows::StageScenes;

#[cfg(windows)]
mod windows {
    use super::super::stubs::{ScenePlayer, Stage, Target};
    use stage::paint::{Adapter, Gpu};
    use stage::scene::{shoot_into, Scene};
    use stage::window::{Overlay, Path};
    use std::sync::mpsc::{channel, Receiver};
    use std::time::Instant;

    type Made = Option<Box<dyn Scene + Send>>;

    /// Frames timed for the log at each scene's start.
    const TIMED: usize = 5;
    /// How long a scene has to show its pixels before Composition is judged (seconds after the first frame).
    const LOOK_FROM: f64 = 0.3;
    const LOOK_UNTIL: f64 = 2.5;

    struct Playing {
        key: String,
        scene: Box<dyn Scene + Send>,
        window: Overlay,
        since: Instant,
        times: Vec<f64>,
        /// The desktop under the window before the first frame (Composition only, until it is judged).
        before: Option<Vec<u8>>,
    }

    /// The GPU, opened at the first scene, and the scene that plays. Every step is said in `notes` for the log; a
    /// failure falls back (another adapter, the layered window, WARP) and says why, never silently.
    #[derive(Default)]
    pub struct StageScenes {
        gpu: Option<Gpu>,
        playing: Option<Playing>,
        /// A scene whose pictures take long to make (clock::WARMED), made on a thread, and where it will play.
        warming: Option<(Receiver<Made>, Stage, String)>,
        /// The path this PC needs (a Composition that showed nothing): kept for the session.
        path: Option<Path>,
        notes: Vec<String>,
    }

    /// Draws the scene at t: its shapes, and the picture a scene that paints itself hands over.
    fn draw(gpu: &Gpu, window: &mut Overlay, scene: &mut dyn Scene, t: f64) -> Result<scenes::prim::Frame, String> {
        // A scene with its own renderer draws straight into the window's still picture; nothing is read back.
        let (frame, pixels) = shoot_into(scene, t, window.still_texture());
        if let Some(pixels) = pixels {
            window.set_still_pixels(gpu, &pixels);
        }
        window.present(gpu, &frame)?;
        Ok(frame)
    }

    impl StageScenes {
        fn note(&mut self, line: String) {
            self.notes.push(line);
        }

        /// The GPU: the chip the desktop is on first (a hybrid laptop's other chip may present nothing), then the
        /// system's choice, then WARP.
        fn open_gpu(&mut self) -> Result<(), String> {
            if self.gpu.is_some() {
                return Ok(());
            }
            self.note(format!("Scene: adapters {:?}; monitors on {:04x?}", stage::paint::adapters(), stage::window::display_ids()));
            let mut why = Vec::new();
            for which in [Adapter::Display, Adapter::Default, Adapter::Software] {
                match Gpu::new(which) {
                    Ok(gpu) => {
                        self.note(format!("Scene: GPU {which:?}: {}", gpu.name()));
                        self.gpu = Some(gpu);
                        return Ok(());
                    }
                    Err(error) => why.push(format!("{which:?}: {error}")),
                }
            }
            Err(format!("no GPU: {}", why.join("; ")))
        }

        fn start(&mut self, key: &str, stage: Stage) -> Result<(), String> {
            self.open_gpu()?;
            let Some(gpu) = self.gpu.as_ref() else { return Ok(()) };
            let inner = super::placement(&stage).stage();
            if stage::clock::WARMED.contains(&key) {
                // Its pictures take 0.6 to 2.5 s: made on a thread, on the same device.
                let gpu = Gpu {
                    instance: gpu.instance.clone(),
                    adapter: gpu.adapter.clone(),
                    device: gpu.device.clone(),
                    queue: gpu.queue.clone(),
                };
                let (sender, made) = channel();
                let made_key = key.to_string();
                std::thread::Builder::new()
                    .name("SceneWarm".into())
                    .spawn(move || {
                        let _ = sender.send(stage::scene::make_on(&made_key, &inner, &gpu));
                    })
                    .map_err(|error| error.to_string())?;
                self.warming = Some((made, stage, key.to_string()));
                return Ok(());
            }
            match stage::scene::make_on(key, &inner, gpu) {
                Some(scene) => self.show(key, scene, stage),
                None => Err("this version has no such scene".into()),
            }
        }

        /// The window for the scene, shown with its first frame: the forced or learned path, else Composition then
        /// Layered; on a hardware chip that fails both, WARP's layered window.
        fn show(&mut self, key: &str, mut scene: Box<dyn Scene + Send>, stage: Stage) -> Result<(), String> {
            let area = super::xywh(stage.game);
            let prefer = stage::window::forced_path().or(self.path);
            match self.open_window(key, scene.as_mut(), area, prefer) {
                Ok((window, before)) => {
                    self.playing = Some(Playing { key: key.into(), scene, window, since: Instant::now(), times: Vec::new(), before });
                    Ok(())
                }
                Err(error) if !self.gpu.as_ref().is_some_and(Gpu::is_software) => {
                    self.note(format!("Scene {key}: {error}; trying WARP"));
                    self.gpu = Some(Gpu::new(Adapter::Software)?);
                    self.note(format!("Scene: GPU Software: {}", self.gpu.as_ref().map(Gpu::name).unwrap_or_default()));
                    let (window, before) = self.open_window(key, scene.as_mut(), area, Some(Path::Layered))?;
                    self.playing = Some(Playing { key: key.into(), scene, window, since: Instant::now(), times: Vec::new(), before });
                    Ok(())
                }
                Err(error) => Err(error),
            }
        }

        fn open_window(
            &mut self,
            key: &str,
            scene: &mut (dyn Scene + Send),
            area: [i32; 4],
            prefer: Option<Path>,
        ) -> Result<(Overlay, Option<Vec<u8>>), String> {
            let Some(gpu) = self.gpu.as_ref() else { return Err("no GPU".into()) };
            let started = Instant::now();
            let mut window = Overlay::open(gpu, area, prefer).map_err(|e| format!("no window: {e}"))?;
            if let Some(still) = scene.still() {
                window.set_still(gpu, &still);
            }
            let path = window.path();
            // The desktop before the scene: what Composition's pixels are judged against.
            let before = (path == Path::Composition).then(|| stage::window::capture(area).ok()).flatten();
            draw(gpu, &mut window, scene, 0.0).map_err(|e| format!("{path:?}: first frame not shown: {e}"))?;
            window.show().map_err(|e| format!("{path:?}: window not shown: {e}"))?;
            let tried = if window.tried.is_empty() { String::new() } else { format!(" (failed first: {})", window.tried.join("; ")) };
            let line = format!(
                "Scene {key}: playing via {path:?} at {area:?} on {}, first frame {:.0} ms{tried}",
                gpu.name(),
                started.elapsed().as_secs_f64() * 1000.0
            );
            self.note(line);
            Ok((window, before))
        }

        /// Composition only: whether the scene's pixels are on the desktop; if not, the layered window for the rest
        /// of the session, this scene moved to it.
        fn judge(&mut self, frame: &scenes::prim::Frame, t: f64) {
            let (Some(playing), Some(gpu)) = (self.playing.as_mut(), self.gpu.as_ref()) else { return };
            let Some(before) = playing.before.as_ref() else { return };
            if t < LOOK_FROM {
                return;
            }
            let area = playing.window.area();
            let after = stage::window::capture(area);
            let expected = playing.window.read_back_bgra(gpu, frame);
            let share = after.as_ref().ok().and_then(|after| stage::seen::shown_share(before, after, &expected));
            let key = playing.key.clone();
            match share {
                Some(share) if share >= stage::seen::SHOWN => {
                    playing.before = None;
                    self.note(format!("Scene {key}: on screen ({:.0} % of its pixels)", share * 100.0));
                }
                Some(share) => {
                    playing.before = None;
                    self.note(format!("Scene {key}: Composition showed {:.0} % of its pixels on screen: using Layered", share * 100.0));
                    self.path = Some(Path::Layered);
                    self.move_to_layered();
                }
                None if t > LOOK_UNTIL => {
                    playing.before = None;
                    let why = after.err().unwrap_or_else(|| "too few solid pixels".into());
                    self.note(format!("Scene {key}: not judged on screen: {why}"));
                }
                None => {}
            }
        }

        fn move_to_layered(&mut self) {
            let (Some(playing), Some(gpu)) = (self.playing.as_mut(), self.gpu.as_ref()) else { return };
            let area = playing.window.area();
            match Overlay::open(gpu, area, Some(Path::Layered)) {
                Ok(mut window) => {
                    if let Some(still) = playing.scene.still() {
                        window.set_still(gpu, &still);
                    }
                    let t = playing.since.elapsed().as_secs_f64();
                    let shown = draw(gpu, &mut window, playing.scene.as_mut(), t).and_then(|_| window.show());
                    playing.window.hide();
                    playing.window = window;
                    if let Err(error) = shown {
                        self.notes.push(format!("Scene: Layered not shown: {error}"));
                    }
                }
                Err(error) => self.notes.push(format!("Scene: no Layered window: {error}")),
            }
        }
    }

    impl ScenePlayer for StageScenes {
        fn play(&mut self, scene_key: &str, stage: Stage) {
            self.stop();
            if stage.target != Target::Screen {
                self.note(format!("Scene {scene_key}: only into 直播模式's window (基础模式), not over the game"));
                return;
            }
            if let Err(error) = self.start(scene_key, stage) {
                self.note(format!("Scene {scene_key}: not played: {error}"));
            }
        }

        fn stop(&mut self) {
            self.warming = None;
            if let Some(playing) = self.playing.take() {
                playing.window.hide();
            }
        }

        fn tick(&mut self) {
            if let Some((made, stage, key)) = &self.warming {
                match made.try_recv() {
                    Ok(scene) => {
                        let (stage, key) = (*stage, key.clone());
                        self.warming = None;
                        let shown = match scene {
                            Some(scene) => self.show(&key, scene, stage),
                            None => Err("this version has no such scene".into()),
                        };
                        if let Err(error) = shown {
                            self.note(format!("Scene {key}: not played: {error}"));
                        }
                    }
                    Err(std::sync::mpsc::TryRecvError::Empty) => return,
                    Err(std::sync::mpsc::TryRecvError::Disconnected) => {
                        self.note(format!("Scene {key}: not played: its pictures were not made"));
                        self.warming = None;
                    }
                }
            }
            let (Some(playing), Some(gpu)) = (self.playing.as_mut(), self.gpu.as_ref()) else { return };
            let t = playing.since.elapsed().as_secs_f64();
            if t >= playing.scene.duration() {
                return self.stop();
            }
            let started = Instant::now();
            let drawn = draw(gpu, &mut playing.window, playing.scene.as_mut(), t);
            stage::window::pump();
            match drawn {
                Ok(frame) => {
                    if playing.times.len() < TIMED {
                        playing.times.push(started.elapsed().as_secs_f64() * 1000.0);
                        if playing.times.len() == TIMED {
                            let line = format!("Scene {}: first frames {:.1?} ms", playing.key, playing.times);
                            self.note(line);
                        }
                    }
                    self.judge(&frame, t);
                }
                Err(error) => {
                    let (key, path) = (playing.key.clone(), playing.window.path());
                    self.note(format!("Scene {key}: frame not shown via {path:?}: {error}"));
                    if path == Path::Composition {
                        self.path = Some(Path::Layered);
                        self.move_to_layered();
                    } else {
                        self.stop();
                    }
                }
            }
        }

        fn notes(&mut self) -> Vec<String> {
            std::mem::take(&mut self.notes)
        }

        /// A scene over the game, or about to be (ui._border_on_screen): it covers 推演成功, so the 400 ms glance
        /// would read the lobby as gone, or start a check that stops the scene it is looking through.
        fn covers_screen(&self) -> bool {
            self.playing.is_some() || self.warming.is_some()
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

#[cfg(all(test, windows))]
mod windows_tests {
    use super::super::stubs::{Rect, ScenePlayer, Stage, Target};
    use super::StageScenes;

    /// P0-2: the glance waits while a scene is over the game (ui._border_on_screen), and only then.
    #[test]
    fn the_stage_covers_the_screen_only_while_a_scene_plays() {
        let mut scenes = StageScenes::default();
        assert!(!scenes.covers_screen(), "nothing plays yet");
        let game = Rect { x: 0, y: 0, w: 640, h: 360 };
        let stage = Stage { game, button: Rect { x: 200, y: 250, w: 240, h: 40 }, target: Target::Screen };
        // claw is made on a thread: covered from the play on, before its first frame.
        scenes.play("claw", stage);
        let notes = scenes.notes();
        if notes.iter().any(|note| note.contains("no GPU")) {
            return;
        }
        assert!(scenes.covers_screen(), "a scene is on its way: {notes:?}");
        scenes.stop();
        assert!(!scenes.covers_screen(), "stopped");
        // Into 直播模式's window only: nothing over the game.
        scenes.play("stars", Stage { target: Target::Stream, ..stage });
        assert!(!scenes.covers_screen());
    }
}
