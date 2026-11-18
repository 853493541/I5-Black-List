//! The scenes that draw with a renderer of their own (every scene but stars): each is made once for the
//! stage with its pictures baked, draws onto transparent (its lobby texture left empty: the game shows
//! through), and hands its frames back as premultiplied RGBA bytes, which the stage shows through the
//! still picture (`Scene::pixels`, `Painter::set_still_pixels`).

use std::path::PathBuf;

use scenes::prim::Frame;

use crate::geom::Stage;
use crate::scene::Scene;

/// Draws the frame at t seconds and reads it back.
type Draw = Box<dyn FnMut(f64) -> Vec<u8> + Send>;

/// A scene drawn by its own renderer.
pub struct Own {
    duration: f64,
    size: [f64; 2],
    draw: Draw,
}

impl Scene for Own {
    fn duration(&self) -> f64 {
        self.duration
    }
    fn frame(&mut self, _t: f64) -> Frame {
        picture(self.size)
    }
    fn pixels(&mut self, t: f64) -> Option<Vec<u8>> {
        Some((self.draw)(t))
    }
}

/// One whole-stage picture of the still texture (layer 1), with no hole rubbed out of it.
pub fn picture(size: [f64; 2]) -> Frame {
    let mut f = Frame::new();
    f.picture(1, size, [-1e5, -1e5, 0.0, 0.0], 1.0);
    f
}

/// Where the app's pictures are (blacklist_detect/assets): BLACKLIST_DETECT_ASSETS, `assets` beside the
/// exe, or the checkout's.
pub fn assets_dir() -> PathBuf {
    if let Some(dir) = std::env::var_os("BLACKLIST_DETECT_ASSETS") {
        return dir.into();
    }
    let beside = std::env::current_exe().ok().and_then(|exe| exe.parent().map(|d| d.join("assets")));
    match beside {
        Some(dir) if dir.is_dir() => dir,
        _ => PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../blacklist_detect/assets"),
    }
}

/// The scene with this key (not stars), its renderer made and its pictures baked; Err when the key is
/// unknown, or there is no graphics chip, or a font or picture it needs is missing.
pub fn make_own(key: &str, stage: &Stage) -> Result<Own, String> {
    build(key, stage, None)
}

/// The same over a lobby picture (RGBA, opaque, the stage's size): a preview, as the 场景管理 tiles and
/// the parity checks draw it.
pub fn preview(key: &str, stage: &Stage, lobby: &[u8]) -> Result<Own, String> {
    build(key, stage, Some(lobby))
}

fn build(key: &str, stage: &Stage, lobby: Option<&[u8]>) -> Result<Own, String> {
    let (w, h, gap) = (stage.width, stage.height, stage.gap);
    let (pw, ph) = (w.round().max(1.0) as u32, h.round().max(1.0) as u32);
    let empty = vec![0u8; pw as usize * ph as usize * 4];
    let clear: &[u8] = lobby.unwrap_or(&empty);
    let draw: Draw = match key {
        "classic" => {
            use scenes::classic::{soft::TitleMask, Classic};
            let scene = Classic::new(w, h, gap, &TitleMask::built_in()?);
            let mut gpu = scenes::lace::gpu::Renderer::new(pw, ph, clear)?;
            let (aw, ah, atlas) = scene.atlas();
            gpu.set_atlas(aw, ah, atlas);
            Box::new(move |t| {
                gpu.render(&scene.paint(t));
                gpu.read()
            })
        }
        "lace" => {
            let scene = scenes::lace::Lace::new(w, h, gap);
            let gpu = scenes::lace::gpu::Renderer::new(pw, ph, clear)?;
            let [under, over] = scene.layers();
            gpu.set_layer(0, &under);
            gpu.set_layer(1, &over);
            Box::new(move |t| {
                gpu.render(&scene.paint(t));
                gpu.read()
            })
        }
        "ice" => {
            let scene = scenes::ice::Ice::new(w, h, gap);
            let gpu = scenes::ice::gpu::Renderer::new(&scene, clear)?;
            Box::new(move |t| {
                gpu.render(&scene.paint(t));
                gpu.read()
            })
        }
        "angel" => {
            let scene = scenes::angel::Angel::new(w, h, gap);
            let (atlas, art) = scene.bake();
            let gpu = scenes::angel::gpu::Renderer::new(pw, ph, clear, &atlas)?;
            gpu.set_galaxy(&scene.warmth());
            Box::new(move |t| {
                gpu.render(&scene.paint(t, &art));
                gpu.read()
            })
        }
        "equation" => {
            use scenes::equation::{text::Fonts, Equation};
            let scene = Equation::new(w, h, gap, &Fonts::load()?);
            let gpu = scenes::equation::gpu::Renderer::new(pw, ph, clear, &scene.atlas)?;
            gpu.set_paper(&scene.paper());
            Box::new(move |t| {
                gpu.render(&scene.paint(t));
                gpu.read()
            })
        }
        "fluffy" => {
            let scene = scenes::fluffy::Fluffy::new(w, h, gap);
            let gpu = scenes::fluffy::gpu::Renderer::new(&scene, clear)?;
            Box::new(move |t| {
                gpu.render(&scene, t);
                gpu.read()
            })
        }
        "cyber" => {
            let scene = scenes::cyber::Cyber::new(w, h, gap);
            let gpu = scenes::cyber::gfx::Renderer::new(pw, ph, clear, scene.atlas())?;
            gpu.render(&scene.wash());
            Box::new(move |t| {
                gpu.render(&scene.paint(t));
                gpu.read()
            })
        }
        "neon" => {
            let scene = scenes::neon::Neon::new(w, h, gap);
            let atlas = scene.atlas(4096);
            let gpu = scenes::neon::gpu::Renderer::new(pw, ph, clear, &atlas, scene.gap)?;
            Box::new(move |t| {
                gpu.render(&scene.paint(t, &atlas.at));
                gpu.read()
            })
        }
        "lyre" => {
            use scenes::lyre::{art::Art, Geo};
            let art = Art::new(Geo::new(w, h, gap), 1.0)?;
            let gpu = scenes::lyre::gpu::Renderer::new(pw, ph, clear, &art)?;
            Box::new(move |t| {
                gpu.render(&scenes::lyre::paint::paint(&art, t));
                gpu.read()
            })
        }
        "claw" => {
            use scenes::claw::{frame::Frame as ClawFrame, gpu::Renderer, Claw};
            let mut scene = Claw::new(w, h, gap, &stage.seats, &assets_dir())?;
            let mut gpu = Renderer::new(pw, ph)?;
            scene.upload(&mut gpu);
            let size = (pw as usize, ph as usize);
            let backdrop = lobby.map(|bytes| gpu.add(size.0, size.1, bytes));
            Box::new(move |t| {
                let mut f = ClawFrame::default();
                if let Some(b) = backdrop {
                    f.image(b, size, [0.0, 0.0, w, h], None, None);
                }
                let veil = scene.paint(t, &mut f);
                gpu.render(veil.as_ref().map(|v| (v, scene.veil_target())), &f);
                gpu.read()
            })
        }
        _ => return Err(format!("no scene {key:?}")),
    };
    Ok(Own {
        duration: crate::clock::duration(key),
        size: [w, h],
        draw,
    })
}

#[cfg(test)]
#[path = "scene_own_tests.rs"]
mod tests;
