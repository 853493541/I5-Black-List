//! 金色传说 on the graphics chip against the Python frames (angel/py_t*.png, made by angel/py_frames.py):
//! the PSNR floor each frame reached when it was ported. Skipped when there is no Vulkan, Metal or
//! DX12 adapter, or when the Python frames are not made yet (they are not in git: run py_frames.py).

use std::path::Path;

use super::gpu::Renderer;
use super::Angel;

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

#[test]
fn frames_match_python() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    if !root.join("angel/py_t4.0.png").exists() {
        eprintln!("skipped: no Python frames; run PYTHONPATH=. python rust/scenes/angel/py_frames.py from the root");
        return;
    }
    let lobby = image::open(root.join("spike/lobby_1920.png")).expect("lobby").to_rgba8();
    let scene = Angel::sample(1920.0, 1080.0);
    let (atlas, art) = scene.bake();
    let Ok(gpu) = Renderer::new(1920, 1080, lobby.as_raw(), &atlas) else { return };
    gpu.set_galaxy(&scene.warmth());
    for (t, floor) in [(0.5, 47.5), (1.5, 45.0), (3.0, 44.0), (4.0, 42.5)] {
        gpu.render(&scene.paint(t, &art));
        let theirs = image::open(root.join(format!("angel/py_t{t:.1}.png"))).expect("python frame").to_rgba8();
        let got = psnr(&gpu.read(), theirs.as_raw());
        assert!(got >= floor, "t={t}: PSNR {got:.1} dB, under {floor} dB");
    }
}
