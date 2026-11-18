//! 星河许愿 drawn over the game as the stage window draws it: on transparent, without the lobby, with
//! the gap round the button left bare. On the software adapter (llvmpipe here, WARP on Windows CI).

use stage::geom::sample_stage;
use stage::paint::{finish, Adapter, Gpu, Offscreen, Painter};
use stage::scene::make;

const W: u32 = 640;
const H: u32 = 360;

fn gpu() -> Option<Gpu> {
    match Gpu::new(Adapter::Software) {
        Ok(gpu) => Some(gpu),
        Err(e) => {
            // No software adapter (no Mesa here, no WARP): nothing to draw on.
            eprintln!("no adapter: {e}");
            None
        }
    }
}

fn draw(gpu: &Gpu, format: wgpu::TextureFormat, t: f64) -> Vec<u8> {
    let stage = sample_stage(f64::from(W), f64::from(H));
    let mut scene = make("stars", &stage).unwrap();
    let painter = Painter::new(gpu, W, H, format, None);
    painter.set_still(gpu, &scene.still().unwrap_or_default());
    let off = Offscreen::new(gpu, W, H, format);
    painter.render(gpu, &scene.frame(t), &off.view);
    finish(gpu);
    off.read(gpu)
}

#[test]
fn stars_over_the_game_is_see_through_and_premultiplied() {
    let Some(gpu) = gpu() else { return };
    eprintln!("adapter: {}", gpu.name());
    let px = draw(&gpu, wgpu::TextureFormat::Bgra8Unorm, 2.0);
    assert_eq!(px.len(), (W * H * 4) as usize);
    // Premultiplied: no channel above its alpha (one step of rounding allowed).
    let bad = px
        .chunks(4)
        .filter(|p| p[0].max(p[1]).max(p[2]) > p[3].saturating_add(1))
        .count();
    assert_eq!(bad, 0, "pixels brighter than their alpha");
    let alpha = |x: u32, y: u32| px[((y * W + x) * 4 + 3) as usize];
    // The button in the middle of the gap stays bare: the game shows there.
    let stage = sample_stage(f64::from(W), f64::from(H));
    let [gx, gy, gw, gh] = stage.gap;
    let (cx, cy) = ((gx + gw / 2.0) as u32, (gy + gh * 0.6) as u32);
    assert_eq!(alpha(cx, cy), 0, "the button is covered");
    // The scene shows somewhere, and not as an opaque sheet over the whole game.
    let shown = px.chunks(4).filter(|p| p[3] > 0).count();
    let opaque = px.chunks(4).filter(|p| p[3] == 255).count();
    assert!(shown > (W * H / 20) as usize, "only {shown} pixels drawn");
    assert!(
        opaque < (W * H / 2) as usize,
        "{opaque} opaque pixels: the game would be hidden"
    );
}

#[test]
fn nothing_shows_at_the_start_and_both_byte_orders_agree() {
    let Some(gpu) = gpu() else { return };
    // Its opacity rises from 0 over the first 0.35 s.
    assert!(draw(&gpu, wgpu::TextureFormat::Rgba8Unorm, 0.0)
        .chunks(4)
        .all(|p| p[3] == 0));
    let rgba = draw(&gpu, wgpu::TextureFormat::Rgba8Unorm, 1.5);
    let bgra = draw(&gpu, wgpu::TextureFormat::Bgra8Unorm, 1.5);
    let swapped: Vec<u8> = bgra
        .chunks(4)
        .flat_map(|p| [p[2], p[1], p[0], p[3]])
        .collect();
    let off = rgba
        .iter()
        .zip(&swapped)
        .filter(|(a, b)| a.abs_diff(**b) > 1)
        .count();
    assert_eq!(off, 0);
}

/// Median and worst time to build, draw and wait for one 1920x1080 frame over the whole scene at 30
/// fps, written past the test harness (it shows in CI logs): what the software adapter costs.
#[test]
fn frame_time_at_1080p() {
    use std::io::Write;
    use std::time::Instant;
    let Some(gpu) = gpu() else { return };
    let (w, h) = (1920u32, 1080u32);
    let stage = sample_stage(f64::from(w), f64::from(h));
    let mut scene = make("stars", &stage).unwrap();
    let painter = Painter::new(&gpu, w, h, wgpu::TextureFormat::Bgra8Unorm, None);
    painter.set_still(&gpu, &scene.still().unwrap());
    let off = Offscreen::new(&gpu, w, h, wgpu::TextureFormat::Bgra8Unorm);
    let (mut draw, mut read) = (Vec::new(), Vec::new());
    for i in 0..150 {
        let start = Instant::now();
        painter.render(&gpu, &scene.frame(f64::from(i) / 30.0), &off.view);
        finish(&gpu);
        draw.push(start.elapsed().as_secs_f64() * 1000.0);
        if i % 10 == 0 {
            let start = Instant::now();
            let _ = off.read(&gpu);
            read.push(start.elapsed().as_secs_f64() * 1000.0);
        }
    }
    draw.sort_by(f64::total_cmp);
    read.sort_by(f64::total_cmp);
    let line = format!(
        "STAGE frame time 1920x1080 on {}: draw median {:.1} ms, worst {:.1} ms; readback median {:.1} ms\n",
        gpu.name(),
        draw[draw.len() / 2],
        draw[draw.len() - 1],
        read[read.len() / 2]
    );
    let _ = std::io::stderr().write_all(line.as_bytes());
    assert!(draw[draw.len() / 2] < 2000.0);
}
