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
