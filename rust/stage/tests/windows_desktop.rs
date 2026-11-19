//! Every scene through the real stage window over a full-screen lobby, judged on the DESKTOP (a GDI copy of the
//! screen, not the swap chain): the scene's solid pixels must be on screen, both ways (Composition, Layered).
//! On WARP (CI has no GPU). Writes the desktop mid-scene to STAGE_SHOTS when set.
#![cfg(windows)]

use std::time::{Duration, Instant};

use stage::geom::sample_stage;
use stage::paint::{Adapter, Gpu};
use stage::scene::{make_on, shoot_into, KEYS};
use stage::seen::{shown_share, SHOWN};
use stage::window::{capture, pump, screen_size, Backdrop, Overlay, Path};

/// The sample lobby (made-up names), stretched over the screen, BGRA.
fn lobby(w: i32, h: i32) -> Vec<u8> {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/../../blacklist_detect/assets/sample-lobby.jpg");
    let mut px = image::open(path)
        .expect("sample lobby")
        .resize_exact(w as u32, h as u32, image::imageops::FilterType::Triangle)
        .to_rgba8()
        .into_raw();
    stage::seen::swap_red_blue(&mut px);
    px
}

fn wait(ms: u64) {
    let until = Instant::now() + Duration::from_millis(ms);
    while Instant::now() < until {
        pump();
        std::thread::sleep(Duration::from_millis(15));
    }
}

fn save(name: &str, area: [i32; 4], bgra: &[u8]) {
    let Some(dir) = std::env::var_os("STAGE_SHOTS") else { return };
    let mut rgba = bgra.to_vec();
    stage::seen::swap_red_blue(&mut rgba);
    for p in rgba.chunks_exact_mut(4) {
        p[3] = 255;
    }
    let _ = std::fs::create_dir_all(&dir);
    let _ = image::save_buffer(std::path::Path::new(&dir).join(name), &rgba, area[2] as u32, area[3] as u32, image::ExtendedColorType::Rgba8);
}

/// The share of `key`'s solid pixels seen on the desktop through `path`.
fn played(gpu: &Gpu, key: &str, path: Path, area: [i32; 4]) -> Result<f64, String> {
    let stage = sample_stage(f64::from(area[2]), f64::from(area[3]));
    let mut scene = make_on(key, &stage, gpu).ok_or("no such scene")?;
    let mut window = Overlay::open(gpu, area, Some(path))?;
    if let Some(still) = scene.still() {
        window.set_still(gpu, &still);
    }
    wait(150);
    let before = capture(area)?;
    let t = (scene.duration() * 0.45).min(3.0);
    let mut last = None;
    for i in 0..3 {
        let (frame, pixels) = shoot_into(scene.as_mut(), t + f64::from(i) * 0.01, window.still_texture());
        if let Some(pixels) = pixels {
            window.set_still_pixels(gpu, &pixels);
        }
        window.present(gpu, &frame)?;
        if i == 0 {
            window.show()?;
        }
        last = Some(frame);
        wait(60);
    }
    wait(250);
    let after = capture(area)?;
    let frame = last.ok_or("no frame")?;
    let expected = window.read_back_bgra(gpu, &frame);
    save(&format!("{key}-{path:?}.png"), area, &after);
    window.hide();
    drop(window);
    wait(100);
    shown_share(&before, &after, &expected).ok_or_else(|| "too few solid pixels to judge".into())
}

#[test]
fn every_scene_reaches_the_desktop_both_ways() {
    let gpu = Gpu::new(Adapter::Software).expect("WARP");
    let (w, h) = screen_size();
    let area = [0, 0, w, h];
    let _game = Backdrop::show(area, &lobby(w, h)).expect("backdrop");
    wait(300);
    save("lobby.png", area, &capture(area).expect("capture"));
    let mut failed = Vec::new();
    eprintln!("SCENES on {} at {w}x{h}", gpu.name());
    for key in KEYS {
        for path in [Path::Composition, Path::Layered] {
            let seen = played(&gpu, key, path, area);
            eprintln!("SCENE {key:<9} {path:?}: {}", match &seen {
                Ok(share) => format!("{:.0} % of its pixels on the desktop", share * 100.0),
                Err(e) => format!("ERROR {e}"),
            });
            match seen {
                Ok(share) if share >= SHOWN => {}
                other => failed.push(format!("{key} {path:?}: {other:?}")),
            }
        }
    }
    assert!(failed.is_empty(), "not on the desktop: {failed:#?}");
}
