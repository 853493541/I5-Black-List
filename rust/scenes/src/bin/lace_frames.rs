//! 玫瑰花边's frames drawn with wgpu at 1920x1080 over the sample lobby, beside the Python frames
//! (rust/scenes/lace/py_frames.py writes them and lobby_1920.png first).
//!
//! Run from rust/: cargo run --release -p scenes --bin lace_frames
//! Writes lace/rust_t<t>.png, side_t<t>.png (Python left, Rust right, half size) and crop_t<t>.png
//! (full size: a swag and its knot, the frame's curls by the button, a corner's roses), prints how
//! far each frame is from Python's and the median frame time over the whole scene at 30 fps.

use std::path::Path;
use std::time::Instant;

use image::RgbaImage;
use scenes::lace::check::{compare, crops, load, side_by_side};
use scenes::lace::gpu::Renderer;
use scenes::lace::{Lace, DURATION};

const W: u32 = 1920;
const H: u32 = 1080;
pub const TIMES: [f64; 4] = [0.5, 1.5, 3.0, 4.2];

fn main() -> Result<(), String> {
    let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("lace");
    let lobby = load(&dir.join("lobby_1920.png"))?;
    let gpu = Renderer::new(W, H, lobby.as_raw())?;
    println!("adapter: {}", gpu.adapter);
    let scene = Lace::sample(f64::from(W), f64::from(H));
    let [under, over] = scene.layers();
    gpu.set_layer(0, &under);
    gpu.set_layer(1, &over);
    for t in TIMES {
        gpu.render(&scene.paint(t));
        let ours = RgbaImage::from_raw(W, H, gpu.read()).ok_or("short read")?;
        ours.save(dir.join(format!("rust_t{t:.1}.png"))).map_err(|e| e.to_string())?;
        let theirs = load(&dir.join(format!("py_t{t:.1}.png")))?;
        let d = compare(&ours, &theirs);
        println!("| {t:.1} s | {:.2}/255 | {:.2} % | {:.3} % | {:.1} dB |", d.mean, d.over8, d.over32, d.psnr);
        side_by_side(&theirs, &ours).save(dir.join(format!("side_t{t:.1}.png"))).map_err(|e| e.to_string())?;
        let boxes = [[400, 0, 560, 300], [560, 940, 560, 140], [0, 820, 360, 260]];
        crops(&theirs, &ours, &boxes).save(dir.join(format!("crop_t{t:.1}.png"))).map_err(|e| e.to_string())?;
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
