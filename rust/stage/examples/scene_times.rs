//! Each 嘉宾 scene's frame time at 1920x1080 over the sample stage, the way the overlay window draws it (make_on,
//! shoot_into, render, wait), for the preview check on CI (docs/dev/preview-check.md).
//!
//! cargo run --release -p stage --example scene_times [-- <keys...>]
//! Prints `adapter\t<name>`, then per scene `<key>\t<frames>\t<median ms>\t<p95 ms>\t<worst ms>` (or `<key>\tskipped\t<why>`).

use std::time::Instant;

use stage::geom::sample_stage;
use stage::paint::{finish, Adapter, Gpu, Offscreen, Painter};
use stage::scene::{make_on, shoot_into, KEYS};

const W: u32 = 1920;
const H: u32 = 1080;
/// At most this many frames per scene (`SCENE_FRAMES`, default 150), spread evenly over the scene at 30 fps or less:
/// the software adapter on CI takes about a second a frame.
fn frames_cap() -> usize {
    std::env::var("SCENE_FRAMES").ok().and_then(|v| v.parse().ok()).filter(|&n| n > 0).unwrap_or(150)
}

fn main() -> Result<(), String> {
    let asked: Vec<String> = std::env::args().skip(1).collect();
    let gpu = Gpu::new(Adapter::Default)?;
    println!("adapter\t{}", gpu.name());
    let stage = sample_stage(f64::from(W), f64::from(H));
    let format = wgpu::TextureFormat::Bgra8Unorm;
    for key in KEYS.iter().filter(|key| asked.is_empty() || asked.iter().any(|a| a == *key)) {
        let made = Instant::now();
        let Some(mut scene) = make_on(key, &stage, &gpu) else {
            println!("{key}\tskipped\tcannot be made here");
            continue;
        };
        let made_ms = made.elapsed().as_secs_f64() * 1000.0;
        let painter = Painter::new(&gpu, W, H, format, None);
        if let Some(still) = scene.still() {
            painter.set_still(&gpu, &still);
        }
        let off = Offscreen::new(&gpu, W, H, format);
        let count = ((scene.duration() * 30.0) as usize).clamp(1, frames_cap());
        let step = scene.duration() / count as f64;
        let mut spent = Vec::with_capacity(count);
        for i in 0..count {
            let start = Instant::now();
            let (frame, pixels) = shoot_into(scene.as_mut(), i as f64 * step, painter.still_texture());
            if let Some(pixels) = pixels {
                painter.set_still_pixels(&gpu, &pixels);
            }
            painter.render(&gpu, &frame, &off.view);
            finish(&gpu);
            spent.push(start.elapsed().as_secs_f64() * 1000.0);
        }
        spent.sort_by(f64::total_cmp);
        let at = |q: f64| spent[((spent.len() - 1) as f64 * q).round() as usize];
        println!("{key}\t{count}\t{:.2}\t{:.2}\t{:.2}\tmade {made_ms:.0} ms", at(0.5), at(0.95), at(1.0));
    }
    Ok(())
}
