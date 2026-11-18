//! How far a frame is from Python's, and the pictures that show it: used by the scenes' frame tools
//! and their tests.

use std::path::Path;

use image::RgbaImage;

/// How far one frame is from another, over RGB.
#[derive(Clone, Copy, Debug)]
pub struct Diff {
    /// Mean absolute difference per channel, of 255.
    pub mean: f64,
    /// Share of pixels off by more than 8 and 32 on any channel, in percent.
    pub over8: f64,
    pub over32: f64,
    pub psnr: f64,
}

pub fn compare(a: &RgbaImage, b: &RgbaImage) -> Diff {
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
    Diff { mean: sum / (n * 3.0), over8: over8 as f64 * 100.0 / n, over32: over32 as f64 * 100.0 / n, psnr: 10.0 * (255.0f64.powi(2) / mse.max(1e-9)).log10() }
}

/// Python left, Rust right, at half size.
pub fn side_by_side(left: &RgbaImage, right: &RgbaImage) -> RgbaImage {
    let (w, h) = (left.width(), left.height());
    let half = |img: &RgbaImage| image::imageops::resize(img, w / 2, h / 2, image::imageops::FilterType::Triangle);
    let mut out = RgbaImage::new(w, h / 2);
    image::imageops::replace(&mut out, &half(left), 0, 0);
    image::imageops::replace(&mut out, &half(right), i64::from(w / 2), 0);
    out
}

/// Full-size crops (x, y, w, h) of both, Python left and Rust right, one row per crop.
pub fn crops(left: &RgbaImage, right: &RgbaImage, boxes: &[[u32; 4]]) -> RgbaImage {
    let wide = boxes.iter().map(|b| b[2]).max().unwrap_or(1);
    let tall: u32 = boxes.iter().map(|b| b[3]).sum();
    let mut out = RgbaImage::new(wide * 2 + 8, tall.max(1));
    let mut y = 0;
    for b in boxes {
        let l = image::imageops::crop_imm(left, b[0], b[1], b[2], b[3]).to_image();
        let r = image::imageops::crop_imm(right, b[0], b[1], b[2], b[3]).to_image();
        image::imageops::replace(&mut out, &l, 0, i64::from(y));
        image::imageops::replace(&mut out, &r, i64::from(wide + 8), i64::from(y));
        y += b[3];
    }
    out
}

pub fn load(path: &Path) -> Result<RgbaImage, String> {
    Ok(image::open(path).map_err(|e| format!("{}: {e}", path.display()))?.to_rgba8())
}
