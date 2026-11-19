//! A scene in a dialog's preview (添加嘉宾 / 编辑嘉宾, 组合, 场景管理): drawn offscreen over the sample lobby, silent,
//! read back as RGBA for the dialog's `frame` (love_scenes.Stage over sample_stage, as the Python preview plays it).

use std::path::Path;
use std::time::Instant;

use stage::geom::sample_stage;
use stage::paint::{Adapter, Gpu, Offscreen, Painter};
use stage::scene::{make_on, shoot_into, Scene};

/// The preview's pixels: 16:9, twice the 448 px the dialogs show it at, less 192 for the GPU's sake.
pub const WIDTH: u32 = 704;
pub const HEIGHT: u32 = 396;
const FORMAT: wgpu::TextureFormat = wgpu::TextureFormat::Rgba8Unorm;

struct Playing {
    key: String,
    scene: Box<dyn Scene + Send>,
    painter: Painter,
    since: Instant,
    ended: bool,
}

/// One scene at a time; the GPU opened at the first.
pub struct ScenePreview {
    gpu: Option<Gpu>,
    off: Option<Offscreen>,
    lobby: Vec<u8>,
    playing: Option<Playing>,
}

/// The sample lobby (made-up names) at the preview's size, RGBA; a dark plain one where it cannot be read.
pub fn lobby(path: &Path) -> Vec<u8> {
    match image::open(path) {
        Ok(picture) => picture.resize_exact(WIDTH, HEIGHT, image::imageops::FilterType::Triangle).to_rgba8().into_raw(),
        Err(_) => [24, 22, 30, 255].repeat((WIDTH * HEIGHT) as usize),
    }
}

impl ScenePreview {
    pub fn new(lobby: Vec<u8>) -> Self {
        Self { gpu: None, off: None, lobby, playing: None }
    }

    /// Plays `key` from its start. Ok says how (for the log); Err why nothing plays.
    pub fn start(&mut self, key: &str) -> Result<String, String> {
        self.playing = None;
        if self.gpu.is_none() {
            let gpu = Gpu::new(Adapter::Default).or_else(|first| Gpu::new(Adapter::Software).map_err(|e| format!("{first}; WARP: {e}")))?;
            self.off = Some(Offscreen::new(&gpu, WIDTH, HEIGHT, FORMAT));
            self.gpu = Some(gpu);
        }
        let Some(gpu) = self.gpu.as_ref() else { return Err("no GPU".into()) };
        let made = Instant::now();
        let stage = sample_stage(f64::from(WIDTH), f64::from(HEIGHT));
        let scene = make_on(key, &stage, gpu).ok_or("this version has no such scene")?;
        let painter = Painter::new(gpu, WIDTH, HEIGHT, FORMAT, Some(&self.lobby));
        if let Some(still) = scene.still() {
            painter.set_still(gpu, &still);
        }
        let said = format!("made in {:.0} ms on {}", made.elapsed().as_secs_f64() * 1000.0, gpu.name());
        self.playing = Some(Playing { key: key.into(), scene, painter, since: Instant::now(), ended: false });
        Ok(said)
    }

    /// The scene showing, from its start again.
    pub fn restart(&mut self) -> Result<String, String> {
        let key = self.playing.as_ref().map(|p| p.key.clone()).ok_or("nothing to play again")?;
        self.start(&key)
    }

    pub fn stop(&mut self) {
        self.playing = None;
    }

    pub fn key(&self) -> Option<&str> {
        self.playing.as_ref().map(|p| p.key.as_str())
    }

    /// The next frame, RGBA WIDTH x HEIGHT; None when nothing plays or the scene has ended (its last frame stays).
    pub fn frame(&mut self) -> Option<Vec<u8>> {
        let (Some(gpu), Some(off), Some(playing)) = (self.gpu.as_ref(), self.off.as_ref(), self.playing.as_mut()) else { return None };
        if playing.ended {
            return None;
        }
        let duration = playing.scene.duration();
        let mut t = playing.since.elapsed().as_secs_f64();
        if t >= duration {
            playing.ended = true;
            t = (duration - 0.05).max(0.0);
        }
        Some(Self::draw(gpu, off, playing, t))
    }

    /// The frame at t (tests).
    pub fn frame_at(&mut self, t: f64) -> Option<Vec<u8>> {
        let (Some(gpu), Some(off), Some(playing)) = (self.gpu.as_ref(), self.off.as_ref(), self.playing.as_mut()) else { return None };
        Some(Self::draw(gpu, off, playing, t))
    }

    fn draw(gpu: &Gpu, off: &Offscreen, playing: &mut Playing, t: f64) -> Vec<u8> {
        let (frame, pixels) = shoot_into(playing.scene.as_mut(), t, playing.painter.still_texture());
        if let Some(pixels) = pixels {
            playing.painter.set_still_pixels(gpu, &pixels);
        }
        playing.painter.render(gpu, &frame, &off.view);
        off.read(gpu)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn preview() -> Option<ScenePreview> {
        let mut preview = ScenePreview::new(lobby(Path::new("no-such-lobby.jpg")));
        // No adapter here (no Mesa, no WARP): nothing to draw on.
        match preview.start("stars") {
            Ok(_) => Some(preview),
            Err(error) => {
                eprintln!("no adapter: {error}");
                None
            }
        }
    }

    #[test]
    fn a_picked_scene_plays_over_the_lobby_and_moves() {
        let Some(mut preview) = preview() else { return };
        let plain = lobby(Path::new("no-such-lobby.jpg"));
        let early = preview.frame_at(1.0).unwrap();
        let late = preview.frame_at(2.5).unwrap();
        assert_eq!(early.len(), (WIDTH * HEIGHT * 4) as usize);
        let differ = |a: &[u8], b: &[u8]| a.chunks(4).zip(b.chunks(4)).filter(|(x, y)| x[..3] != y[..3]).count();
        assert!(differ(&early, &plain) > early.len() / 4 / 20, "the scene is not over the lobby");
        assert!(differ(&early, &late) > 100, "the scene does not move");
        assert!(preview.frame().is_some());
    }

    #[test]
    fn replay_starts_the_same_scene_again_and_an_unknown_one_says_why() {
        let Some(mut preview) = preview() else { return };
        assert!(preview.restart().is_ok());
        assert_eq!(preview.key(), Some("stars"));
        assert!(preview.start("no-such-scene").is_err());
        assert_eq!(preview.key(), None);
        assert!(preview.restart().is_err());
    }

    #[test]
    fn every_scene_plays_in_the_preview() {
        let Some(mut preview) = preview() else { return };
        for key in stage::scene::KEYS {
            assert!(preview.start(key).is_ok(), "{key}");
            assert!(preview.frame_at(1.5).is_some(), "{key}");
        }
    }
}
