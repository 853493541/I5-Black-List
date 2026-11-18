//! The frames against Python's: the floor each frame reaches (skipped without a Vulkan adapter or
//! without the Python frames, which rust/scenes/cyber/py_frames.py writes).

use std::path::Path;

use super::gfx::Renderer;
use super::Cyber;

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
fn frames_match_python() {
    let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("cyber");
    let Ok(lobby) = image::open(dir.join("lobby_1920.png")) else { return };
    let scene = Cyber::sample(1920.0, 1080.0);
    let Ok(gpu) = Renderer::new(1920, 1080, lobby.to_rgba8().as_raw(), scene.atlas()) else { return };
    gpu.render(&scene.wash());
    // The floors reached: the lettering on the panels and rails is not drawn yet (see README).
    for (t, floor) in [(0.5, 50.0), (1.5, 30.0), (3.0, 30.0)] {
        let Ok(theirs) = image::open(dir.join(format!("py_t{t:.1}.png"))) else { continue };
        gpu.render(&scene.paint(t));
        let got = psnr(&gpu.read(), theirs.to_rgba8().as_raw());
        assert!(got >= floor, "t={t}: {got:.1} dB");
    }
}
