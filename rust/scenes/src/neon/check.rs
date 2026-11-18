//! The port against Python's own frames (rust/scenes/neon/py_t*.png, from py_frames.py): each frame
//! must stay above the PSNR it reaches here. Skipped where there is no graphics adapter at all.

use std::path::Path;

use super::gpu::Renderer;
use super::Neon;

/// PSNR in dB over RGB between two RGBA pictures of one size.
pub fn psnr(a: &[u8], b: &[u8]) -> f64 {
    let (mut sq, mut n) = (0f64, 0f64);
    for (pa, pb) in a.chunks_exact(4).zip(b.chunks_exact(4)) {
        for c in 0..3 {
            let d = f64::from(pa[c]) - f64::from(pb[c]);
            sq += d * d;
            n += 1.0;
        }
    }
    10.0 * (255.0f64.powi(2) / (sq / n).max(1e-9)).log10()
}

#[test]
fn frames_stay_close_to_python() {
    let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("neon");
    // The frames are made by py_frames.py and not committed (as the spike's): nothing to check without them.
    let Ok(lobby) = image::open(dir.join("lobby_1920.png")) else { return };
    let lobby = lobby.to_rgba8();
    let scene = Neon::sample(1920.0, 1080.0);
    let atlas = scene.atlas(4096);
    let Ok(gpu) = Renderer::new(1920, 1080, lobby.as_raw(), &atlas, scene.gap) else { return };
    // The floors: what this port reaches on llvmpipe, less about 3 dB for another rasterizer's rounding.
    for (t, name, floor) in [(0.5, "py_t0.5.png", 49.0), (1.5, "py_t1.5.png", 34.0), (3.0, "py_t3.0.png", 39.0), (3.75, "py_t3.8.png", 35.0)] {
        gpu.render(&scene.paint(t, &atlas.at));
        let Ok(theirs) = image::open(dir.join(name)) else { return };
        let theirs = theirs.to_rgba8();
        let db = psnr(&gpu.read(), theirs.as_raw());
        assert!(db >= floor, "t={t}: {db:.1} dB, floor {floor}");
    }
}
