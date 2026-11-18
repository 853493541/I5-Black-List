//! ocr: part of the Rust rewrite of 模仿者小工具 (see docs/dev/research/rust-plan-2026-11-18.md).
//!
//! The detection side of blacklist_detect/onnx_ocr.py, ported step for step: resize, normalise, the DB
//! post-process with its unclip, the reading-order sort and the straightened crops. Parity is proven on golden
//! data the Python code writes (tools/rust_golden_det.py, tests/det_golden.rs).
#![deny(unsafe_code)]

mod clip;
pub mod crop;
pub mod db;
pub mod det;
pub mod read;
pub mod rec;

pub use crop::{crop_by_polys, rotate_crop, sort_boxes};
pub use db::{db_boxes, Quad};
pub use det::{det_resize, init_runtime, ocr_threads, DetParams, Detection, TextDetector, DET_PARAMS};

/// What can go wrong reading a frame: the runtime, OpenCV, or the model's own files.
#[derive(Debug)]
pub enum Error {
    Ort(String),
    OpenCv(opencv::Error),
    Config(String),
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Error::Ort(text) => write!(f, "onnx runtime: {text}"),
            Error::OpenCv(err) => write!(f, "opencv: {err}"),
            Error::Config(text) => write!(f, "model config: {text}"),
        }
    }
}

impl std::error::Error for Error {}

/// The model file in `model_dir`: inference.ort (ONNX Runtime's own format, which a minimal ONNX Runtime build needs;
/// tools/size/ort_build.txt) when there is one, else inference.onnx.
pub fn model_file(model_dir: &std::path::Path) -> std::path::PathBuf {
    let ort_format = model_dir.join("inference.ort");
    if ort_format.is_file() {
        ort_format
    } else {
        model_dir.join("inference.onnx")
    }
}

impl From<opencv::Error> for Error {
    fn from(err: opencv::Error) -> Self {
        Error::OpenCv(err)
    }
}

impl<T> From<ort::Error<T>> for Error {
    fn from(err: ort::Error<T>) -> Self {
        Error::Ort(err.to_string())
    }
}

pub type Result<T> = std::result::Result<T, Error>;

#[cfg(test)]
mod model_file_tests {
    use super::model_file;

    #[test]
    fn prefers_the_ort_format_model_when_there_is_one() {
        let dir = std::env::temp_dir().join(format!("ocr-model-file-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("inference.onnx"), b"").unwrap();
        assert_eq!(model_file(&dir), dir.join("inference.onnx"));
        std::fs::write(dir.join("inference.ort"), b"").unwrap();
        assert_eq!(model_file(&dir), dir.join("inference.ort"));
        std::fs::remove_dir_all(&dir).unwrap();
    }
}
