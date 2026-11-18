//! 演说家遇袭's frames: drawn with wgpu at 1920x1080 over the sample lobby, beside the Python frames
//! (rust/scenes/claw/py_frames.py writes them first).
//!
//! Run from rust/: cargo run --release -p scenes --bin claw_frames
//! Writes claw/rust_t<t>.png, claw/side_t<t>.png (Python left, Rust right, half size) and
//! claw/crop_t<t>.png (full-size crops of the busiest part), prints how far each frame is from
//! Python's and the median frame time over the whole scene at 30 fps.

use std::path::Path;
use std::time::Instant;

use image::RgbaImage;
use scenes::claw::frame::Frame;
use scenes::claw::gpu::Renderer;
use scenes::claw::{Claw, DURATION};

const W: u32 = 1920;
const H: u32 = 1080;
const TIMES: [f64; 7] = [0.5, 1.5, 3.0, 3.1, 3.4, 4.0, 5.3];
/// The sample stage's twelve name boxes at 1920x1080 (love_scenes.sample_stage(1920, 1080).names()).
pub const SEATS: [[f64; 4]; 12] = [
    [203.52, 525.96, 275.52, 43.2],
    [502.08, 528.12, 247.104, 39.96],
    [772.224, 521.64, 230.4, 48.6],
    [1025.856, 524.88, 241.92, 45.36],
    [1307.52, 524.88, 232.32, 47.52],
    [1570.56, 525.96, 232.32, 44.28],
    [232.32, 839.16, 248.64, 43.2],
    [504.0, 835.92, 241.344, 48.6],
    [775.68, 835.92, 236.16, 47.52],
    [1040.64, 834.84, 236.16, 45.36],
    [1301.76, 839.16, 241.92, 42.12],
    [1566.72, 838.08, 272.64, 43.2],
];

fn main() -> Result<(), String> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let dir = root.join("claw");
    let assets = root.join("../../blacklist_detect/assets");
    let lobby = image::open(root.join("spike/lobby_1920.png")).map_err(|e| e.to_string())?.to_rgba8();
    let mut gpu = Renderer::new(W, H)?;
    println!("adapter: {}", gpu.adapter);
    let (w, h) = (f64::from(W), f64::from(H));
    let start = Instant::now();
    let mut scene = Claw::new(w, h, Claw::sample_gap(w, h), &SEATS, &assets)?;
    println!("pictures made in {:.0} ms", start.elapsed().as_secs_f64() * 1000.0);
    scene.upload(&mut gpu);
    let backdrop = gpu.add(W as usize, H as usize, lobby.as_raw());
    let frame = |t: f64| {
        let mut f = Frame::default();
        f.image(backdrop, (W as usize, H as usize), [0.0, 0.0, w, h], None, None);
        let veil = scene.paint(t, &mut f);
        (veil, f)
    };
    let draw = |t: f64| {
        let (veil, f) = frame(t);
        gpu.render(veil.as_ref().map(|v| (v, scene.veil_target())), &f);
    };
    for t in TIMES {
        draw(t);
        let ours = RgbaImage::from_raw(W, H, gpu.read()).ok_or("short read")?;
        ours.save(dir.join(format!("rust_t{t:.1}.png"))).map_err(|e| e.to_string())?;
        let theirs = image::open(dir.join(format!("py_t{t:.1}.png"))).map_err(|e| e.to_string())?.to_rgba8();
        let (mean, over8, over32, psnr) = compare(&ours, &theirs);
        println!("| {t:.1} s | {mean:.2}/255 | {over8:.2} % | {over32:.3} % | {psnr:.1} dB |");
        side_by_side(&theirs, &ours).save(dir.join(format!("side_t{t:.1}.png"))).map_err(|e| e.to_string())?;
        crop(&theirs, &ours, 560, 300, 800, 380).save(dir.join(format!("crop_t{t:.1}.png"))).map_err(|e| e.to_string())?;
    }
    let mut spent = Vec::new();
    let mut t = 0.0;
    while t <= DURATION {
        let start = Instant::now();
        draw(t);
        spent.push(start.elapsed().as_secs_f64() * 1000.0);
        t += 1.0 / 30.0;
    }
    spent.sort_by(f64::total_cmp);
    println!("frame (build + draw + wait): median {:.1} ms, worst {:.1} ms at {W}x{H}", spent[spent.len() / 2], spent[spent.len() - 1]);
    Ok(())
}

/// Mean absolute difference per channel, the share of pixels off by more than 8 and 32 on any
/// channel, and the PSNR, over RGB.
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

/// The same w x h window of both, full size, Python left.
fn crop(left: &RgbaImage, right: &RgbaImage, x: u32, y: u32, w: u32, h: u32) -> RgbaImage {
    let mut out = RgbaImage::new(w * 2, h);
    image::imageops::replace(&mut out, &image::imageops::crop_imm(left, x, y, w, h).to_image(), 0, 0);
    image::imageops::replace(&mut out, &image::imageops::crop_imm(right, x, y, w, h).to_image(), i64::from(w), 0);
    out
}
