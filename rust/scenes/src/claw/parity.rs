//! Parity with the Python scene: frames drawn here against the ones claw/py_frames.py wrote.

use super::frame::Frame;
use super::gpu::Renderer;
use super::marks::{Marks, Sizes};
use super::Claw;
use std::path::{Path, PathBuf};

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).to_path_buf()
}

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

fn python(name: &str, w: u32, h: u32) -> Vec<u8> {
    let img = image::open(root().join("claw").join(name)).expect("python frame").to_rgba8();
    image::imageops::crop_imm(&img, 0, 0, w, h).to_image().into_raw()
}

#[test]
fn the_strike_matches_python() {
    let (w, h) = (1920u32, 1080u32);
    // The Python frames are not committed (claw/py_frames.py writes them): nothing to compare with.
    if !root().join("claw/py_t3.1.png").exists() {
        eprintln!("claw/py_t*.png missing: run rust/scenes/claw/py_frames.py to compare with Python");
        return;
    }
    // No Vulkan, Metal or DX12 driver at all: nothing to test here.
    let Ok(mut gpu) = Renderer::new(w, h) else { return };
    let (fw, fh) = (f64::from(w), f64::from(h));
    let seats = crate::claw::seats_1920();
    let mut scene = Claw::new(fw, fh, Claw::sample_gap(fw, fh), &seats, &root().join("../../blacklist_detect/assets")).unwrap();
    scene.upload(&mut gpu);
    let lobby = image::open(root().join("spike/lobby_1920.png")).unwrap().to_rgba8();
    let backdrop = gpu.add(w as usize, h as usize, lobby.as_raw());
    for t in [1.5, 3.1] {
        let mut f = Frame::default();
        f.image(backdrop, (w as usize, h as usize), [0.0, 0.0, fw, fh], None, None);
        let veil = scene.paint(t, &mut f);
        gpu.render(veil.as_ref().map(|v| (v, scene.veil_target())), &f);
        let db = psnr(&gpu.read(), &python(&format!("py_t{t:.1}.png"), w, h));
        assert!(db >= 45.0, "t={t}: {db:.1} dB");
    }
}

#[test]
fn the_marks_match_python() {
    let Ok(mut gpu) = Renderer::new(512, 320) else { return };
    let mut m = Marks::new(&Sizes { cover_h: 80.0, badge: 60.0, card: [260.0, 140.0], lead: 24.0 }, 1.0, &root().join("../../blacklist_detect/assets")).unwrap();
    m.upload(&mut gpu);
    let mut f = Frame::default();
    f.rect([0.0, 0.0, 512.0, 320.0], &crate::prim::solid("#30343c", 1.0));
    m.ring(&mut f, [40.0, 40.0, 300.0, 80.0], 2.0);
    m.badge(&mut f, [380.0, 50.0, 60.0, 60.0], 2.0);
    m.card(&mut f, [40.0, 150.0, 260.0, 140.0], 2.0);
    for i in 0..2 {
        m.lead(&mut f, [330.0 + 40.0 * i as f64, 200.0], i);
    }
    gpu.render(None, &f);
    let ours: Vec<u8> = gpu.read().chunks(512 * 4).flat_map(|row| row[..480 * 4].to_vec()).collect();
    let db = psnr(&ours, &python("py_marks.png", 480, 320));
    assert!(db >= 44.0, "{db:.1} dB");
}
