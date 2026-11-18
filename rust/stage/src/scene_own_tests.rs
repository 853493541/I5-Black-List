//! Every scene drawn onto transparent and laid over the lobby on the CPU matches the same scene drawn
//! over the lobby by its renderer: what shows over the game is what the parity checks measured.

use super::*;
use crate::geom::sample_stage;
use crate::scene::{make, shoot, KEYS};

fn lobby() -> Option<Vec<u8>> {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/../scenes/spike/lobby_1920.png");
    Some(image::open(path).ok()?.to_rgba8().into_raw())
}

/// PSNR over the color channels of two RGBA pictures.
fn psnr(a: &[u8], b: &[u8]) -> f64 {
    let (mut sq, mut n) = (0f64, 0f64);
    for (pa, pb) in a.chunks(4).zip(b.chunks(4)) {
        for c in 0..3 {
            let d = f64::from(pa[c]) - f64::from(pb[c]);
            sq += d * d;
            n += 1.0;
        }
    }
    10.0 * (255.0f64.powi(2) / (sq / n).max(1e-9)).log10()
}

/// src over dst, both premultiplied, dst opaque.
fn over(src: &[u8], dst: &[u8]) -> Vec<u8> {
    src.chunks(4)
        .zip(dst.chunks(4))
        .flat_map(|(s, d)| {
            let keep = 1.0 - f64::from(s[3]) / 255.0;
            let mix = |c: usize| (f64::from(s[c]) + f64::from(d[c]) * keep).round().min(255.0) as u8;
            [mix(0), mix(1), mix(2), 255]
        })
        .collect()
}

#[test]
fn every_scene_over_the_game_is_its_preview_less_the_lobby() {
    let Some(lobby) = lobby() else { return };
    let stage = sample_stage(1920.0, 1080.0);
    let only: Option<String> = std::env::var("SCENE").ok();
    for key in KEYS.iter().filter(|k| **k != "stars" && only.as_deref().is_none_or(|o| o == **k)) {
        let Ok(mut bare) = make_own(key, &stage) else { return };
        let mut shown = preview(key, &stage, &lobby).expect("preview");
        let t = 1.5;
        let mine = bare.pixels(t).expect("pixels");
        assert_eq!(mine.len(), lobby.len(), "{key}");
        let g = stage.gap;
        let middle = ((g[1] + g[3] / 2.0) as usize * 1920 + (g[0] + g[2] / 2.0) as usize) * 4;
        assert!(mine[middle + 3] < 255, "{key}: the game shows through the gap");
        let p = psnr(&over(&mine, &lobby), &shown.pixels(t).unwrap());
        eprintln!("{key}: over the lobby vs preview {p:.1} dB");
        assert!(p > 40.0, "{key}: {p:.1} dB");
    }
}

#[test]
fn make_knows_every_key_and_shoot_gives_pixels_for_own_scenes() {
    let stage = sample_stage(500.0, 270.0);
    let Ok(_) = make_own("ice", &stage) else { return };
    for key in ["ice", "lace"] {
        let mut scene = make(key, &stage).expect(key);
        assert_eq!(scene.duration(), crate::clock::duration(key));
        let (frame, pixels) = shoot(scene.as_mut(), 1.0);
        assert_eq!(frame.prims.len(), 1);
        assert_eq!(pixels.map(|p| p.len()), Some(500 * 270 * 4));
    }
    let (_, pixels) = shoot(make("stars", &stage).unwrap().as_mut(), 1.0);
    assert!(pixels.is_none());
}

#[test]
fn on_the_stages_device_frames_are_copied_not_read_back() {
    use crate::paint::{Adapter, Gpu, Offscreen, Painter};
    use crate::scene::{make_on, shoot_into};
    let Ok(gpu) = Gpu::new(Adapter::Default) else { return };
    let stage = sample_stage(640.0, 360.0);
    let format = wgpu::TextureFormat::Rgba8Unorm;
    let painter = Painter::new(&gpu, 640, 360, format, None);
    let off = Offscreen::new(&gpu, 640, 360, format);
    for key in ["angel", "neon", "claw"] {
        let mut shared = make_on(key, &stage, &gpu).expect(key);
        let (frame, pixels) = shoot_into(shared.as_mut(), 1.5, painter.still_texture());
        assert!(pixels.is_none(), "{key}: nothing read back");
        painter.render(&gpu, &frame, &off.view);
        let copied = off.read(&gpu);
        let mut own = make_own(key, &stage).expect(key);
        let (frame, pixels) = shoot(&mut own, 1.5);
        painter.set_still_pixels(&gpu, &pixels.expect("pixels"));
        painter.render(&gpu, &frame, &off.view);
        let read = off.read(&gpu);
        assert!(psnr(&copied, &read) > 60.0, "{key}: {:.1} dB", psnr(&copied, &read));
        assert!(copied.chunks(4).any(|p| p[3] > 0), "{key}: drawn");
    }
}

/// Median ms a frame at 1920x1080, scene drawn and shown through the painter, read back vs copied on the
/// chip: `cargo test --release -p stage frame_times -- --ignored --nocapture`.
#[test]
#[ignore]
fn frame_times() {
    use crate::paint::{finish, Adapter, Gpu, Offscreen, Painter};
    use crate::scene::{make_on, shoot_into};
    let Ok(gpu) = Gpu::new(Adapter::Default) else { return };
    let stage = sample_stage(1920.0, 1080.0);
    let format = wgpu::TextureFormat::Rgba8Unorm;
    let painter = Painter::new(&gpu, 1920, 1080, format, None);
    let off = Offscreen::new(&gpu, 1920, 1080, format);
    let median = |mut v: Vec<f64>| {
        v.sort_by(f64::total_cmp);
        v[v.len() / 2]
    };
    for key in KEYS.iter().filter(|k| **k != "stars") {
        let (mut read, mut copied) = (Vec::new(), Vec::new());
        let mut own = make_own(key, &stage).expect(key);
        let mut shared = make_on(key, &stage, &gpu).expect(key);
        for i in 0..30 {
            let t = f64::from(i) / 6.0;
            let start = std::time::Instant::now();
            let (frame, pixels) = shoot(&mut own, t);
            painter.set_still_pixels(&gpu, &pixels.expect("pixels"));
            painter.render(&gpu, &frame, &off.view);
            finish(&gpu);
            read.push(start.elapsed().as_secs_f64() * 1000.0);
            let start = std::time::Instant::now();
            let (frame, _) = shoot_into(shared.as_mut(), t, painter.still_texture());
            painter.render(&gpu, &frame, &off.view);
            finish(&gpu);
            copied.push(start.elapsed().as_secs_f64() * 1000.0);
        }
        eprintln!("{key}: read back {:.1} ms, on the chip {:.1} ms", median(read), median(copied));
    }
}
