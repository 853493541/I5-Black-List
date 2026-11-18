//! 经典's frames drawn with wgpu at 1920x1080 over the sample lobby, beside the Python frames
//! (rust/scenes/classic/py_frames.py writes them; the lobby is the spike's lobby_1920.png).
//!
//! Run from rust/: cargo run --release -p scenes --bin classic_frames
//! Writes classic/rust_t<t>.png, side_t<t>.png (Python left, Rust right, half size) and crop_t<t>.png
//! (full size: the title, the top left corner, the frame's ends by the button), prints how
//! far each frame is from Python's and the median frame time over the whole scene at 30 fps.

use std::path::Path;
use std::time::Instant;

use image::RgbaImage;
use scenes::lace::check::{compare, crops, load, side_by_side};
use scenes::lace::gpu::Renderer;
use scenes::classic::{soft::TitleMask, Classic, DURATION};

const W: u32 = 1920;
const H: u32 = 1080;
pub const TIMES: [f64; 5] = [0.5, 1.5, 2.0, 3.0, 4.0];

fn main() -> Result<(), String> {
    let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("classic");
    let lobby = load(&dir.join("../spike/lobby_1920.png"))?;
    let mut gpu = Renderer::new(W, H, lobby.as_raw())?;
    println!("adapter: {}", gpu.adapter);
    let scene = Classic::sample(f64::from(W), f64::from(H), &title_mask(&dir)?);
    let (aw, ah, atlas) = scene.atlas();
    gpu.set_atlas(aw, ah, atlas);
    for t in TIMES {
        gpu.render(&scene.paint(t));
        let ours = RgbaImage::from_raw(W, H, gpu.read()).ok_or("short read")?;
        ours.save(dir.join(format!("rust_t{t:.1}.png"))).map_err(|e| e.to_string())?;
        let theirs = load(&dir.join(format!("py_t{t:.1}.png")))?;
        let d = compare(&ours, &theirs);
        println!("| {t:.1} s | {:.2}/255 | {:.2} % | {:.3} % | {:.1} dB |", d.mean, d.over8, d.over32, d.psnr);
        side_by_side(&theirs, &ours).save(dir.join(format!("side_t{t:.1}.png"))).map_err(|e| e.to_string())?;
        let boxes = [[700, 0, 520, 120], [0, 0, 300, 220], [480, 960, 960, 120]];
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

/// The words 心动嘉宾 as Qt sets them (py_frames.py writes title_mask.png and the font's height).
pub fn title_mask(dir: &Path) -> Result<TitleMask, String> {
    let img = image::open(dir.join("title_mask.png")).map_err(|e| e.to_string())?.to_luma8();
    let text = std::fs::read_to_string(dir.join("title.txt")).map_err(|e| e.to_string())?;
    let text_height = text.trim().parse::<f64>().map_err(|e| e.to_string())?;
    let words = img.pixels().map(|p| f32::from(p[0]) / 255.0).collect();
    Ok(TitleMask { w: img.width() as usize, h: img.height() as usize, words, text_height })
}
