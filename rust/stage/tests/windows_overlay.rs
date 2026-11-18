//! The stage window on Windows, on WARP (CI has no GPU): opened both ways, 星河许愿 played in it,
//! its pixels read back. What it cannot show here (see-through over a real game, a hybrid laptop's
//! choice of chip, DPI) needs a real PC.
#![cfg(windows)]

use std::io::Write;
use std::time::Instant;

use stage::geom::sample_stage;
use stage::paint::{Adapter, Gpu};
use stage::scene::make;
use stage::window::{pump, Overlay, Path};

const AREA: [i32; 4] = [80, 60, 960, 540];

fn play(path: Option<Path>) -> Path {
    let gpu = Gpu::new(Adapter::Software).expect("WARP");
    let mut overlay = Overlay::open(&gpu, AREA, path)
        .unwrap_or_else(|e| panic!("open {path:?} on {}: {e}", gpu.name()));
    let stage = sample_stage(f64::from(AREA[2]), f64::from(AREA[3]));
    let mut scene = make("stars", &stage).unwrap();
    overlay.set_still(&gpu, &scene.still().unwrap());
    overlay.show().expect("show");
    let mut times = Vec::new();
    for i in 0..30 {
        let start = Instant::now();
        overlay
            .present(&gpu, &scene.frame(0.5 + f64::from(i) / 30.0))
            .expect("present");
        pump();
        times.push(start.elapsed().as_secs_f64() * 1000.0);
    }
    times.sort_by(f64::total_cmp);
    let frame = scene.frame(2.0);
    overlay.present(&gpu, &frame).expect("present");
    let px = overlay.read_back(&gpu, &frame);
    assert_eq!(px.len(), (AREA[2] * AREA[3] * 4) as usize);
    let [gx, gy, gw, gh] = stage.gap;
    let at = |x: f64, y: f64| px[((y as usize) * AREA[2] as usize + x as usize) * 4 + 3];
    assert_eq!(at(gx + gw / 2.0, gy + gh * 0.6), 0, "the button is covered");
    let shown = px.chunks(4).filter(|p| p[3] > 0).count();
    assert!(shown > px.len() / 4 / 20, "only {shown} pixels drawn");
    let got = overlay.path();
    let line = format!(
        "STAGE {got:?} window {}x{} on {}: present median {:.1} ms, worst {:.1} ms\n",
        AREA[2],
        AREA[3],
        gpu.name(),
        times[15],
        times[29]
    );
    let _ = std::io::stderr().write_all(line.as_bytes());
    overlay.hide();
    got
}

#[test]
fn composition_window_plays_stars() {
    assert_eq!(play(Some(Path::Composition)), Path::Composition);
}

#[test]
fn layered_window_plays_stars() {
    assert_eq!(play(Some(Path::Layered)), Path::Layered);
}

#[test]
fn picks_composition_first() {
    assert_eq!(play(None), Path::Composition);
}
