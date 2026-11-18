//! 冰蓝极光's frames drawn with wgpu at 1920x1080 over the sample lobby, beside the Python ones
//! (rust/scenes/ice/py_frames.py writes them; the lobby is spike/lobby_1920.png).
//!
//! Run from rust/: cargo run --release -p scenes --bin ice_frames
//! Writes ice/side_t<t>.png (Python left, Rust right, half size) and ice/crop_t<t>.png (full size:
//! the heart and the aurora, the frost), prints how far each frame is from Python's and the median
//! frame time over the whole scene at 30 fps.

use std::path::Path;
use std::time::Instant;

use image::RgbaImage;
use scenes::ice::check::{compare, crops, side_by_side};
use scenes::ice::gpu::Renderer;
use scenes::ice::{Ice, DURATION};

const W: u32 = 1920;
const H: u32 = 1080;

fn main() -> Result<(), String> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let dir = root.join("ice");
    let lobby = image::open(root.join("spike/lobby_1920.png")).map_err(|e| e.to_string())?.to_rgba8();
    let scene = Ice::sample(f64::from(W), f64::from(H));
    let gpu = Renderer::new(&scene, lobby.as_raw())?;
    println!("adapter: {}", gpu.adapter);
    let areas = [[0, 0, 560, 380], [700, 0, 760, 260], [0, 820, 480, 260]];
    for t in [0.5, 1.5, 2.0, 3.0, 4.4] {
        gpu.render(&scene.paint(t));
        let ours = RgbaImage::from_raw(W, H, gpu.read()).ok_or("short read")?;
        let theirs = image::open(dir.join(format!("py_t{t:.1}.png"))).map_err(|e| e.to_string())?.to_rgba8();
        if std::env::var_os("ICE_SAVE_RUST").is_some() {
            ours.save(dir.join(format!("rust_t{t:.1}.png"))).map_err(|e| e.to_string())?;
        }
        let (mean, over8, over32, psnr) = compare(&ours, &theirs);
        println!("| {t:.1} s | {mean:.2}/255 | {over8:.2} % | {over32:.3} % | {psnr:.1} dB |");
        side_by_side(&theirs, &ours).save(dir.join(format!("side_t{t:.1}.png"))).map_err(|e| e.to_string())?;
        crops(&theirs, &ours, &areas).save(dir.join(format!("crop_t{t:.1}.png"))).map_err(|e| e.to_string())?;
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
    println!("frame (build + draw + wait): median {:.1} ms, worst {:.1} ms; building the shapes alone: median {:.3} ms", spent[mid], spent[last], built[mid]);
    Ok(())
}
