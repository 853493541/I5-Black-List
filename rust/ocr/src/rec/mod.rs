//! Name recognition: an exact port of blacklist_detect/onnx_ocr.py's TextRecognizer and of the name preparation in
//! blacklist_detect/ocr_engine.py (prepare_name_line, prepare_name_line_plain, choose_name_read, read_names).
//! tools/rust_golden_rec.py writes the golden data the tests compare against.

pub mod ctc;
pub mod names;
pub mod prepare;
mod recognizer;

pub use names::{choose_name_read, read_names};
pub use prepare::{prepare_name_line, prepare_name_line_plain};
pub use recognizer::{ocr_threads, Recognizer};

/// Every error of the recognition path: ONNX Runtime, OpenCV, the model's inference.yml or a file.
pub type Error = Box<dyn std::error::Error + Send + Sync>;
pub type Result<T> = std::result::Result<T, Error>;

/// One read: the text and its mean character probability (as Python's float, from numpy's float32 mean).
pub type Read = (String, f64);
