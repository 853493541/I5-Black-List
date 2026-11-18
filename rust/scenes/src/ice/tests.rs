use std::path::Path;

use image::RgbaImage;

use super::check::compare;
use super::gpu::Renderer;
use super::Ice;

#[test]
fn lays_out_the_same_every_time() {
    let (a, b) = (Ice::sample(1920.0, 1080.0), Ice::sample(1920.0, 1080.0));
    assert_eq!(a.dust.len(), 46);
    assert_eq!(a.sparks.len(), 12);
    assert!(a.frost.len() > 30, "{}", a.frost.len());
    assert_eq!(a.frost[5].b[0].to_bits(), b.frost[5].b[0].to_bits());
    assert_eq!(a.paint(2.0).main.prims.len(), b.paint(2.0).main.prims.len());
    assert_eq!(a.glass_px, 208);
}

#[test]
fn nothing_but_the_lobby_at_the_start() {
    let f = Ice::sample(1920.0, 1080.0).paint(0.0);
    assert!(!f.aurora.drawn() && f.within.is_none());
    assert!(f.main.prims.iter().skip(1).all(|p| p.colors.iter().all(|c| c[3] == 0.0)));
}

/// The Rust frames against the Python ones (ice/py_t*.png, written by ice/py_frames.py).
#[test]
fn matches_the_python_frames() {
    let dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let lobby = image::open(dir.join("spike/lobby_1920.png")).expect("lobby").to_rgba8();
    let scene = Ice::sample(1920.0, 1080.0);
    // No Vulkan, Metal or DX12 driver at all: nothing to test here.
    let Ok(gpu) = Renderer::new(&scene, lobby.as_raw()) else { return };
    for (t, floor) in [(1.5, 45.0), (2.0, 45.0)] {
        gpu.render(&scene.paint(t));
        let ours = RgbaImage::from_raw(1920, 1080, gpu.read()).expect("frame");
        // The Python frames are made locally by ice/py_frames.py and kept out of git.
        let Ok(theirs) = image::open(dir.join(format!("ice/py_t{t:.1}.png"))) else { return };
        let theirs = theirs.to_rgba8();
        let (_, _, _, psnr) = compare(&ours, &theirs);
        assert!(psnr >= floor, "t={t}: PSNR {psnr:.1} dB < {floor}");
    }
}
