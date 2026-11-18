//! The spike's frames: 星河许愿 drawn with wgpu at 1920x1080 over the sample lobby, beside the Python
//! frames (rust/scenes/spike/py_frames.py writes them and lobby_1920.png first).
//!
//! Run from rust/: cargo run --release -p scenes --bin stars_spike
//! Writes spike/rust_t<t>.png and spike/side_t<t>.png (Python left, Rust right, half size), prints
//! how far each frame is from Python's and the median frame time over the whole scene at 30 fps.

use std::path::Path;
use std::time::Instant;

use image::RgbaImage;
use scenes::gpu::Renderer;
use scenes::stars::{Stars, DURATION};

const W: u32 = 1920;
const H: u32 = 1080;

fn main() -> Result<(), String> {
    let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("spike");
    let lobby = image::open(dir.join("lobby_1920.png")).map_err(|e| e.to_string())?.to_rgba8();
    let gpu = Renderer::new(W, H, lobby.as_raw())?;
    println!("adapter: {}", gpu.adapter);
    let scene = Stars::sample(f64::from(W), f64::from(H));
    gpu.set_galaxy(&scene.milky_way());
    for t in [0.5, 1.5, 3.0] {
        gpu.render(&scene.paint(t));
        let ours = RgbaImage::from_raw(W, H, gpu.read()).ok_or("short read")?;
        ours.save(dir.join(format!("rust_t{t:.1}.png"))).map_err(|e| e.to_string())?;
        let theirs = image::open(dir.join(format!("py_t{t:.1}.png"))).map_err(|e| e.to_string())?.to_rgba8();
        let (mean, over8, over32, psnr) = compare(&ours, &theirs);
        println!("t={t:.1}: mean |diff| {mean:.2}/255, pixels off by >8: {over8:.2}%, >32: {over32:.3}%, PSNR {psnr:.1} dB");
        side_by_side(&theirs, &ours).save(dir.join(format!("side_t{t:.1}.png"))).map_err(|e| e.to_string())?;
    }
    let (mut spent, mut built) = (Vec::new(), Vec::new());
    let mut t = 0.0;
    while t <= DURATION {
        let start = Instant::now();
        let frame = scene.paint(t);
        built.push(start.elapsed().as_secs_f64() * 1000.0);
        gpu.render(&frame);
        spent.push(start.elapsed().as_secs_f64() * 1000.0);
        t += 1.0 / 30.0;
    }
    spent.sort_by(f64::total_cmp);
    built.sort_by(f64::total_cmp);
    let (mid, last) = (spent.len() / 2, spent.len() - 1);
    println!("frame (build + draw + wait): median {:.1} ms, worst {:.1} ms at {W}x{H}; building the shape list alone: median {:.3} ms", spent[mid], spent[last], built[mid]);
    Ok(())
}

/// Mean absolute difference per channel, the share of pixels off by more than 8 and 32 on any
/// channel, and the PSNR, over RGB.
fn compare(a: &RgbaImage, b: &RgbaImage) -> (f64, f64, f64, f64) {
    let (mut sum, mut sq, mut over8, mut over32) = (0f64, 0f64, 0usize, 0usize);
    for (pa, pb) in a.pixels().zip(b.pixels()) {
        let mut worst = 0i32;
        for c in 0..3 {
            let d = i32::from(pa[c]) - i32::from(pb[c]);
            sum += f64::from(d.abs());
            sq += f64::from(d * d);
            worst = worst.max(d.abs());
        }
        over8 += usize::from(worst > 8);
        over32 += usize::from(worst > 32);
    }
    let n = f64::from(a.width() * a.height());
    let mse = sq / (n * 3.0);
    (sum / (n * 3.0), over8 as f64 * 100.0 / n, over32 as f64 * 100.0 / n, 10.0 * (255.0f64.powi(2) / mse.max(1e-9)).log10())
}

fn side_by_side(left: &RgbaImage, right: &RgbaImage) -> RgbaImage {
    let half = |img: &RgbaImage| image::imageops::resize(img, W / 2, H / 2, image::imageops::FilterType::Triangle);
    let mut out = RgbaImage::new(W, H / 2);
    image::imageops::replace(&mut out, &half(left), 0, 0);
    image::imageops::replace(&mut out, &half(right), i64::from(W / 2), 0);
    out
}
