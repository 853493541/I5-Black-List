//! The port against the Python scene: its layout, and a whole frame against fluffy.py's own.

use super::gpu::Renderer;
use super::Fluffy;

#[test]
fn lays_out_the_same_every_time() {
    let (a, b) = (Fluffy::sample(1920.0, 1080.0), Fluffy::sample(1920.0, 1080.0));
    assert_eq!(a.sparkles.len(), 22);
    assert_eq!(a.sparkles[21][0].to_bits(), b.sparkles[21][0].to_bits());
    assert_eq!(a.rings.len(), b.rings.len());
    assert_eq!(a.atlas.canvas.px, b.atlas.canvas.px);
    assert_eq!(a.paint(2.0).frame.prims.len(), b.paint(2.0).frame.prims.len());
}

#[test]
fn nothing_but_the_lobby_at_the_start_and_end() {
    let s = Fluffy::sample(1920.0, 1080.0);
    assert_eq!(s.paint(0.0).frame.prims.len(), 1);
    assert_eq!(s.paint(5.0).frame.prims.len(), 1);
}

/// PSNR over RGB of two RGBA frames.
fn psnr(a: &[u8], b: &[u8]) -> f64 {
    let (mut sq, mut n) = (0f64, 0f64);
    for (pa, pb) in a.chunks(4).zip(b.chunks(4)) {
        for c in 0..3 {
            sq += (f64::from(pa[c]) - f64::from(pb[c])).powi(2);
            n += 1.0;
        }
    }
    10.0 * (255.0f64.powi(2) / (sq / n).max(1e-9)).log10()
}

#[test]
fn a_frame_matches_pythons() {
    let dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("fluffy");
    let (Ok(lobby), Ok(theirs)) = (image::open(dir.join("lobby_1920.png")), image::open(dir.join("py_t3.0.png"))) else {
        return;
    };
    let scene = Fluffy::sample(1920.0, 1080.0);
    // No Vulkan, Metal or DX12 driver at all: nothing to test here.
    let Ok(gpu) = Renderer::new(&scene, lobby.to_rgba8().as_raw()) else {
        return;
    };
    gpu.render(&scene, 3.0);
    let db = psnr(&gpu.read(), theirs.to_rgba8().as_raw());
    assert!(db >= 45.0, "PSNR {db:.1} dB");
}
