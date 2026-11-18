//! 竖琴清风's own checks: the timing curves, a sprite, and the whole frame against Python's on the chip.

use super::art::Art;
use super::gpu::Renderer;
use super::paint::paint;
use super::{flight, sprites, strum, Geo, FLY};

#[test]
fn strings_ring_in_turn_and_the_flyer_lands() {
    let s = strum(0.95);
    assert!(s[0] > s[1] && s[1] >= s[6], "{s:?}");
    assert_eq!(flight(FLY.1 + 0.5).0, 1.0);
    let (way, flap, _, _) = flight(0.6);
    assert!(way > 0.0 && way < 1.0 && flap >= 0.0);
}

#[test]
fn a_maple_leaf_is_red_with_a_pine_shadow() {
    let leaf = sprites::maple(20.0, 30.0, 1.0, false, 7, 2.0);
    let mid = leaf.px[leaf.h / 2 * leaf.w + leaf.w / 2];
    assert!(mid[3] == 255 && mid[0] > 2 * mid[1], "{mid:?}");
}

/// The frames drawn on the chip against the Python ones in rust/scenes/lyre (skipped with no adapter).
#[test]
fn frames_match_python() {
    let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor { backends: wgpu::Backends::all(), ..Default::default() });
    if pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions::default())).is_err() {
        return;
    }
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
    let Ok(lobby) = image::open(root.join("spike/lobby_1920.png")) else { return };
    let (w, h) = (1920u32, 1080u32);
    let art = Art::new(Geo::sample(f64::from(w), f64::from(h)), 1.0).expect("pictures");
    let gpu = Renderer::new(w, h, lobby.to_rgba8().as_raw(), &art).expect("renderer");
    for (t, floor) in [(0.5, 42.0), (1.5, 50.0), (3.0, 50.0)] {
        gpu.render(&paint(&art, t));
        let ours = gpu.read();
        let theirs = image::open(root.join(format!("lyre/py_t{t:.1}.png"))).expect("python frame").to_rgba8();
        let mut sq = 0f64;
        for (a, b) in ours.chunks(4).zip(theirs.pixels()) {
            for c in 0..3 {
                sq += (f64::from(a[c]) - f64::from(b[c])).powi(2);
            }
        }
        let psnr = 10.0 * (255.0f64.powi(2) / (sq / f64::from(w * h * 3)).max(1e-9)).log10();
        assert!(psnr >= floor, "t={t}: {psnr:.1} dB under {floor}");
    }
}
