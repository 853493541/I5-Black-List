//! 竖琴清风's frames drawn with wgpu at 1920x1080 over the sample lobby, beside the Python frames
//! (rust/scenes/lyre/py_frames.py writes py_t*.png first; the lobby is spike/lobby_1920.png).
//!
//! Run from rust/: cargo run --release -p scenes --bin lyre_frames
//! Writes lyre/rust_t<t>.png, lyre/side_t<t>.png (Python left, Rust right, half size) and crops, prints
//! how far each frame is from Python's and the median frame time over the whole scene at 30 fps.

use std::path::Path;
use std::time::Instant;

use image::RgbaImage;
use scenes::lyre::art::Art;
use scenes::lyre::gpu::Renderer;
use scenes::lyre::paint::paint;
use scenes::lyre::{Geo, DURATION};

const W: u32 = 1920;
const H: u32 = 1080;
const TIMES: [f64; 5] = [0.5, 1.5, 3.0, 4.0, 4.7];

fn main() -> Result<(), String> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let dir = root.join("lyre");
    let lobby = image::open(root.join("spike/lobby_1920.png")).map_err(|e| e.to_string())?.to_rgba8();
    let start = Instant::now();
    let art = Art::new(Geo::sample(f64::from(W), f64::from(H)), 1.0)?;
    println!("pictures made in {:.0} ms", start.elapsed().as_secs_f64() * 1000.0);
    let gpu = Renderer::new(W, H, lobby.as_raw(), &art)?;
    println!("adapter: {}", gpu.adapter);
    for t in TIMES {
        gpu.render(&paint(&art, t));
        let ours = RgbaImage::from_raw(W, H, gpu.read()).ok_or("short read")?;
        ours.save(dir.join(format!("rust_t{t:.1}.png"))).map_err(|e| e.to_string())?;
        let Ok(theirs) = image::open(dir.join(format!("py_t{t:.1}.png"))) else { continue };
        let theirs = theirs.to_rgba8();
        let (mean, over8, over32, psnr) = compare(&ours, &theirs);
        println!("| {t:.1} s | {mean:.2}/255 | {over8:.2} % | {over32:.3} % | {psnr:.1} dB |");
        side_by_side(&theirs, &ours).save(dir.join(format!("side_t{t:.1}.png"))).map_err(|e| e.to_string())?;
        crops(&theirs, &ours).save(dir.join(format!("crop_t{t:.1}.png"))).map_err(|e| e.to_string())?;
    }
    let (mut spent, mut built) = (Vec::new(), Vec::new());
    let mut t = 0.0;
    while t <= DURATION {
        let start = Instant::now();
        let frame = paint(&art, t);
        built.push(start.elapsed().as_secs_f64() * 1000.0);
        gpu.render(&frame);
        spent.push(start.elapsed().as_secs_f64() * 1000.0);
        t += 1.0 / 30.0;
    }
    spent.sort_by(f64::total_cmp);
    built.sort_by(f64::total_cmp);
    let (mid, last) = (spent.len() / 2, spent.len() - 1);
    println!("frame (build + draw + wait): median {:.1} ms, worst {:.1} ms; building the list alone: median {:.2} ms", spent[mid], spent[last], built[mid]);
    Ok(())
}

/// Mean absolute difference per channel, the share of pixels off by more than 8 and 32, and the PSNR, over RGB.
pub fn compare(a: &RgbaImage, b: &RgbaImage) -> (f64, f64, f64, f64) {
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

/// The busiest parts at full size, Python left, Rust right: the lyre (top) and the curl with its leaves (bottom).
fn crops(left: &RgbaImage, right: &RgbaImage) -> RgbaImage {
    let mut out = RgbaImage::new(960, 840);
    for (row, (x, y)) in [(0u32, (0u32, 0u32)), (420, (1560, 0))].iter().map(|(r, xy)| (*r, *xy)) {
        for (col, img) in [(0u32, left), (480, right)] {
            let part = image::imageops::crop_imm(img, x, y, 360, 420).to_image();
            image::imageops::replace(&mut out, &part, i64::from(col), i64::from(row));
        }
    }
    out
}
