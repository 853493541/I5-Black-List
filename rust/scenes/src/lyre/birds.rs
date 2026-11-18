//! The birds, cut out of the friend's picture (blacklist_detect/assets/birds, read as lyre.py's _bird does):
//! halved a step at a time while more than twice as wide as wanted, then made wide pixels across and
//! BIRD_TALL taller, smoothly, in premultiplied color.

use image::imageops::{flip_horizontal, resize, FilterType};
use image::RgbaImage;

use super::img::Pic;

pub const BIRD_TALL: f64 = 1.12;
/// birds.json: where the wings grow from the front bird's sides, and the wing's own root and tip.
pub const FRONT_RIGHT: (f64, f64) = (540.0, 417.0);
pub const FRONT_LEFT: (f64, f64) = (36.0, 417.0);
pub const WING_ROOT: (f64, f64) = (40.0, 447.0);
pub const WING_TIP: (f64, f64) = (232.0, -25.0);
pub const FRONT_SIZE: (f64, f64) = (574.0, 640.0);

fn dir() -> std::path::PathBuf {
    std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../blacklist_detect/assets/birds")
}

fn premultiplied(path: &std::path::Path) -> Result<RgbaImage, String> {
    let mut img = image::open(path).map_err(|e| format!("{}: {e}", path.display()))?.to_rgba8();
    for p in img.pixels_mut() {
        let a = u32::from(p[3]);
        for c in 0..3 {
            p[c] = ((u32::from(p[c]) * a + 127) / 255) as u8;
        }
    }
    Ok(img)
}

/// Cut-out `name` ("perch", "lily", "flyer", each or with "_blink", or "wing") made `wide` pixels across.
pub fn bird(name: &str, wide: f64) -> Result<Pic, String> {
    let file = name.replace("flyer", "front");
    let mut source = premultiplied(&dir().join(format!("{file}.png")))?;
    if name.starts_with("lily") {
        source = flip_horizontal(&source);
    }
    let wide = if name == "wing" { wide * f64::from(source.width()) / FRONT_SIZE.0 } else { wide };
    while f64::from(source.width()) > 2.0 * wide {
        let w = source.width() / 2;
        let h = (f64::from(source.height()) * f64::from(w) / f64::from(source.width())).round() as u32;
        source = resize(&source, w, h.max(1), FilterType::Triangle);
    }
    let high = f64::from(source.height()) * wide / f64::from(source.width()) * BIRD_TALL;
    let (w, h) = ((wide.round() as u32).max(1), (high.round() as u32).max(1));
    let out = resize(&source, w, h, FilterType::Triangle);
    Ok(Pic { w: w as usize, h: h as usize, px: out.pixels().map(|p| p.0).collect() })
}
