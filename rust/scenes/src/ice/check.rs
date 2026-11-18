//! How far a Rust frame is from the Python one, and the side-by-side pictures.

use image::RgbaImage;

/// Mean absolute difference per channel, the share of pixels (in %) off by more than 8 and 32 on
/// any channel, and the PSNR in dB, over RGB.
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

/// Python left, Rust right, each at half size.
pub fn side_by_side(left: &RgbaImage, right: &RgbaImage) -> RgbaImage {
    let (w, h) = (left.width(), left.height());
    let half = |img: &RgbaImage| image::imageops::resize(img, w / 2, h / 2, image::imageops::FilterType::Triangle);
    let mut out = RgbaImage::new(w, h / 2);
    image::imageops::replace(&mut out, &half(left), 0, 0);
    image::imageops::replace(&mut out, &half(right), i64::from(w / 2), 0);
    out
}

/// Full-size crops, Python left, Rust right, one row per (x, y, w, h).
pub fn crops(left: &RgbaImage, right: &RgbaImage, areas: &[[u32; 4]]) -> RgbaImage {
    let width = areas.iter().map(|a| a[2]).max().unwrap_or(1) * 2;
    let mut out = RgbaImage::new(width, areas.iter().map(|a| a[3]).sum::<u32>().max(1));
    let mut y = 0;
    for &[ax, ay, aw, ah] in areas {
        image::imageops::replace(&mut out, &*image::imageops::crop_imm(left, ax, ay, aw, ah), 0, i64::from(y));
        image::imageops::replace(&mut out, &*image::imageops::crop_imm(right, ax, ay, aw, ah), i64::from(aw), i64::from(y));
        y += ah;
    }
    out
}
