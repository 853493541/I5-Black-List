//! The Rust name reader against what the Python app reads (tools/rust_golden_rec.py): the prepared images byte for
//! byte, the texts exactly, the scores within 1e-6. The models and the crops are not in git: REC_MODELS (default
//! /tmp/rec/onnx), REC_CROPS (/tmp/rec/crops) and REC_ORT_LIB (libonnxruntime.so of the onnxruntime 1.32.0 wheel)
//! say where they are; without them the tests say so and pass.
//!
//! The plain line is checked against the reads Python makes with Intel IPP off. opencv-python 4.10 resizes
//! INTER_CUBIC through IPP, and an OpenCV built without it (Ubuntu's libopencv 4.6.0) gives other pixels at
//! non-integer scales; the `*_with_ipp` test, ignored, compares against the app's own reads and shows that gap.

use std::path::{Path, PathBuf};
use std::sync::OnceLock;

use ocr::rec::{prepare, read_names, Read, Recognizer};
use opencv::core::Mat;
use opencv::imgcodecs;
use opencv::imgproc;
use opencv::prelude::*;
use ort::environment::Environment;
use serde_json::Value;
use sha2::{Digest, Sha256};

const GOLDEN: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/golden/rec/strips.json");
const ORT_LIB: &str = "/tmp/rec/venv/lib/python3.12/site-packages/onnxruntime/capi/libonnxruntime.so.1.32.0";

fn setting(name: &str, default: &str) -> PathBuf {
    PathBuf::from(std::env::var(name).unwrap_or_else(|_| default.to_string()))
}

fn golden() -> Vec<Value> {
    let data: Value = serde_json::from_str(&std::fs::read_to_string(GOLDEN).unwrap()).unwrap();
    data["frames"].as_array().unwrap().clone()
}

fn crops_dir() -> Option<PathBuf> {
    let dir = setting("REC_CROPS", "/tmp/rec/crops");
    if dir.is_dir() {
        Some(dir)
    } else {
        eprintln!("skipped: no crops at {}", dir.display());
        None
    }
}

fn environment() -> Option<&'static Environment> {
    static ENV: OnceLock<Option<Environment>> = OnceLock::new();
    ENV.get_or_init(|| {
        let lib = setting("REC_ORT_LIB", ORT_LIB);
        if !lib.is_file() || !setting("REC_MODELS", "/tmp/rec/onnx").is_dir() {
            eprintln!("skipped: no ONNX Runtime at {} or no models", lib.display());
            return None;
        }
        Some(ort::init_from(lib).unwrap().build().unwrap())
    })
    .as_ref()
}

fn recognizer(model: &str) -> Recognizer {
    Recognizer::new(environment().unwrap(), &setting("REC_MODELS", "/tmp/rec/onnx").join(model), 12).unwrap()
}

/// The crop as the Python side had it: RGB.
fn load_rgb(dir: &Path, name: &str) -> Mat {
    let bgr = imgcodecs::imread(dir.join(name).to_str().unwrap(), imgcodecs::IMREAD_COLOR).unwrap();
    let mut rgb = Mat::default();
    imgproc::cvt_color_def(&bgr, &mut rgb, imgproc::COLOR_BGR2RGB).unwrap();
    rgb
}

fn sha(mat: &Mat) -> String {
    Sha256::digest(prepare::bytes(mat).unwrap()).iter().map(|b| format!("{b:02x}")).collect()
}

fn shape(mat: &Mat) -> Value {
    serde_json::json!([mat.rows(), mat.cols(), mat.channels()])
}

/// The golden value of `key` for the plain line: as the app reads it (IPP), or with IPP off.
fn plain<'a>(strip: &'a Value, key: &str, ipp: bool) -> &'a Value {
    if ipp {
        &strip[key]
    } else {
        &strip["noipp"][key]
    }
}

#[test]
fn prepared_images_match_python_byte_for_byte() {
    check_prepared(false);
}

#[test]
#[ignore = "opencv-python 4.10 resizes INTER_CUBIC with Intel IPP; the system OpenCV here has none"]
fn prepared_images_match_python_byte_for_byte_with_ipp() {
    check_prepared(true);
}

fn check_prepared(ipp: bool) {
    let Some(dir) = crops_dir() else { return };
    let mut failures = Vec::new();
    let mut count = 0;
    for frame in golden() {
        for strip in frame["strips"].as_array().unwrap() {
            let name = strip["crop"].as_str().unwrap();
            let rgb = load_rgb(&dir, name);
            assert_eq!(sha(&rgb), strip["crop_sha"], "{name}: the crop on disk is not the golden one");
            let line = prepare::prepare_name_line(&rgb).unwrap();
            if shape(&line) != strip["prepared_shape"] || sha(&line) != strip["prepared_sha"] {
                failures.push(format!("{name} prepared"));
            }
            let line_plain = prepare::prepare_name_line_plain(&rgb).unwrap();
            if shape(&line_plain) != strip["plain_shape"] || sha(&line_plain) != *plain(strip, "plain_sha", ipp) {
                failures.push(format!("{name} plain"));
            }
            count += 1;
        }
    }
    assert!(count >= 200, "only {count} strips");
    assert!(failures.is_empty(), "{} of {count} strips differ: {:?}", failures.len(), &failures[..failures.len().min(10)]);
}

fn compare(label: &str, got: &[Read], want: &[&Value], failures: &mut Vec<String>) {
    assert_eq!(got.len(), want.len());
    for (slot, (read, golden)) in got.iter().zip(want).enumerate() {
        let score = golden["score"].as_f64().unwrap();
        if read.0 != golden["text"].as_str().unwrap() || (read.1 - score).abs() > 1e-6 {
            failures.push(format!("{label} #{slot}: score {} vs {score}", read.1));
        }
    }
}

#[test]
fn reads_match_python_texts_and_scores() {
    check_reads(false);
}

#[test]
#[ignore = "opencv-python 4.10 resizes INTER_CUBIC with Intel IPP; the system OpenCV here has none"]
fn reads_match_python_texts_and_scores_with_ipp() {
    check_reads(true);
}

fn check_reads(ipp: bool) {
    let Some(dir) = crops_dir() else { return };
    if environment().is_none() {
        return;
    }
    let (mut v6, mut v5) = (recognizer("PP-OCRv6_medium_rec"), recognizer("PP-OCRv5_mobile_rec"));
    let mut failures = Vec::new();
    for frame in golden() {
        let label = frame["frame"].as_str().unwrap().to_string();
        let strips: Vec<&Value> = frame["strips"].as_array().unwrap().iter().collect();
        let crops: Vec<Mat> = strips.iter().map(|s| load_rgb(&dir, s["crop"].as_str().unwrap())).collect();
        let prepared: Vec<Mat> = crops.iter().map(|c| prepare::prepare_name_line(c).unwrap()).collect();
        let lines_plain: Vec<Mat> = crops.iter().map(|c| prepare::prepare_name_line_plain(c).unwrap()).collect();
        let pick = |key: &str| strips.iter().map(|s| &s[key]).collect::<Vec<_>>();
        let pick_plain = |key: &str| strips.iter().map(|s| plain(s, key, ipp)).collect::<Vec<_>>();
        compare(&format!("{label} v6"), &v6.read(&prepared).unwrap(), &pick("v6"), &mut failures);
        compare(&format!("{label} v6 plain"), &v6.read(&lines_plain).unwrap(), &pick_plain("v6_plain"), &mut failures);
        compare(&format!("{label} v5"), &v5.read(&prepared).unwrap(), &pick("v5"), &mut failures);
        compare(&format!("{label} final"), &read_names(&mut v6, &crops).unwrap(), &pick_plain("final"), &mut failures);
    }
    assert!(failures.is_empty(), "{} reads differ: {:?}", failures.len(), &failures[..failures.len().min(10)]);
}
