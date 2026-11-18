//! Debug: writes one frame's normalised input and probability map as raw float32 (args: ort lib, model dir, png).
use std::path::Path;

use ocr::{init_runtime, TextDetector, DET_PARAMS};
use opencv::prelude::*;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let env = init_runtime(Path::new(&args[1])).unwrap();
    let mut det = TextDetector::new(&env, Path::new(&args[2]), 4).unwrap();
    let image = opencv::imgcodecs::imread(&args[3], opencv::imgcodecs::IMREAD_COLOR).unwrap();
    let (resized, _) = ocr::det_resize(&image, 64, DET_PARAMS.limit_type, 4000).unwrap();
    let input: Vec<u8> = det.normalize(&resized).unwrap().iter().flat_map(|v| v.to_le_bytes()).collect();
    std::fs::write("/tmp/rs_input.f32", input).unwrap();
    let (pred, h, w, _) = det.predict(&image, &DET_PARAMS).unwrap();
    std::fs::write("/tmp/rs_pred.f32", pred.iter().flat_map(|v| v.to_le_bytes()).collect::<Vec<u8>>()).unwrap();
    println!("{h} x {w}, {} cols", image.cols());
}
