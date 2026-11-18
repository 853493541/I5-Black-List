//! The Rust detection against what blacklist_detect/onnx_ocr.py found (tools/rust_golden_det.py): the same boxes,
//! scores within 1e-6, and byte-identical crops. Needs the model, ONNX Runtime and the decoded frames, which are not
//! in git; without them the test says so and passes.

use std::path::{Path, PathBuf};

use ocr::{crop_by_polys, det_resize, init_runtime, sort_boxes, Quad, TextDetector, DET_PARAMS};
use opencv::core::{Mat, CV_8UC3};
use opencv::prelude::*;
use serde_json::Value;
use sha2::{Digest, Sha256};

const ORT_LIB: &str = "/tmp/pyref/lib/python3.12/site-packages/onnxruntime/capi/libonnxruntime.so.1.32.0";
const MODEL: &str = "/tmp/ocr-models/PP-OCRv5_mobile_det_infer";
const FRAMES: &str = "/tmp/ocr-golden-frames";

fn place(var: &str, default: &str) -> PathBuf {
    std::env::var_os(var).map(PathBuf::from).unwrap_or_else(|| PathBuf::from(default))
}

fn sha(bytes: &[u8]) -> String {
    Sha256::digest(bytes).iter().map(|b| format!("{b:02x}")).collect()
}

fn mat_sha(mat: &Mat) -> String {
    sha(mat.try_clone().unwrap().data_bytes().unwrap())
}

/// A PNG the golden script wrote, as the BGR Mat cv2.imread gave it.
fn read_bgr(path: &Path) -> Mat {
    let decoder = png::Decoder::new(std::fs::File::open(path).unwrap());
    let mut reader = decoder.read_info().unwrap();
    let mut buf = vec![0; reader.output_buffer_size()];
    let info = reader.next_frame(&mut buf).unwrap();
    assert_eq!(info.color_type, png::ColorType::Rgb, "{}", path.display());
    let mut bgr = buf[..info.buffer_size()].to_vec();
    bgr.chunks_exact_mut(3).for_each(|px| px.swap(0, 2));
    let flat = Mat::new_rows_cols_with_data(info.height as i32, (info.width * 3) as i32, &bgr).unwrap();
    flat.reshape(3, info.height as i32).unwrap().try_clone().unwrap()
}

fn quads(value: &Value) -> Vec<Quad> {
    serde_json::from_value(value.clone()).unwrap()
}

#[test]
fn detection_matches_the_python_reference() {
    let (lib, model, frames) = (place("OCR_ORT_LIB", ORT_LIB), place("OCR_DET_MODEL", MODEL), place("OCR_GOLDEN_FRAMES", FRAMES));
    if !lib.exists() || !model.join("inference.onnx").exists() || !frames.exists() {
        eprintln!("skipped: needs {}, {} and {}", lib.display(), model.display(), frames.display());
        return;
    }
    let golden: Value = serde_json::from_str(include_str!("golden/det.json")).unwrap();
    let env = init_runtime(&lib).unwrap();
    let threads = golden["threads"].as_u64().unwrap() as usize;
    let mut det = TextDetector::new(&env, &model, threads).unwrap();
    let floats = |v: &Value| -> Vec<f64> { serde_json::from_value(v.clone()).unwrap() };
    assert_eq!(det.alpha.to_vec(), floats(&golden["alpha"]));
    assert_eq!(det.beta.to_vec(), floats(&golden["beta"]));

    let mut gaps = Vec::new();
    let (mut boxes, mut crops) = (0, 0);
    for frame in golden["frames"].as_array().unwrap() {
        let name = frame["name"].as_str().unwrap();
        let image = read_bgr(&frames.join(frame["png"].as_str().unwrap()));
        assert_eq!(image.typ(), CV_8UC3);
        assert_eq!(mat_sha(&image), frame["decoded_sha256"], "{name}: not the frame the golden data was made from");
        let (resized, shape) = det_resize(&image, DET_PARAMS.limit_side_len, DET_PARAMS.limit_type, DET_PARAMS.max_side_limit).unwrap();
        assert_eq!(shape.to_vec(), floats(&frame["shape"]), "{name}: shape");
        if mat_sha(&resized) != frame["resized_sha256"] {
            gaps.push(format!("{name}: resize (INTER_LINEAR) gives other pixels"));
        }
        let found = det.detect(&image).unwrap();
        let want = quads(&frame["polys"]);
        if found.polys != want {
            gaps.push(format!("{name}: {} boxes, want {}; first different {:?}", found.polys.len(), want.len(),
                found.polys.iter().zip(&want).position(|(a, b)| a != b)));
            continue;
        }
        for (got, want) in found.scores.iter().zip(floats(&frame["scores"])) {
            if (got - want).abs() > 1e-6 {
                gaps.push(format!("{name}: score {got} want {want}"));
            }
        }
        let ordered = sort_boxes(&found.polys);
        assert_eq!(ordered, quads(&frame["sorted"]), "{name}: sorted");
        for (i, (crop, want)) in crop_by_polys(&image, &ordered).unwrap().iter().zip(frame["crops"].as_array().unwrap()).enumerate() {
            let size = (crop.rows() as u64, crop.cols() as u64);
            if size != (want["h"].as_u64().unwrap(), want["w"].as_u64().unwrap()) || mat_sha(crop) != want["sha256"] {
                gaps.push(format!("{name}: crop {i} {size:?} differs"));
            }
        }
        boxes += want.len();
        crops += frame["crops"].as_array().unwrap().len();
    }
    eprintln!("{boxes} boxes, {crops} crops compared");
    // OpenCV 4.6 draws some slanted fillPoly masks a pixel different from the 4.10 the Python app runs: link 4.10.
    let version = opencv::core::get_version_string().unwrap();
    assert!(gaps.is_empty(), "{} gaps on OpenCV {version}:\n{}", gaps.len(), gaps.join("\n"));
}
