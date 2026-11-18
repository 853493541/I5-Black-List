//! common: part of the Rust rewrite of 模仿者小工具 (see docs/dev/research/rust-plan-2026-11-18.md).
//!
//! One copy of what wave 1 wrote several times over: the name rules of match.py, the records of model.py, the
//! limits and names the lists and the launcher share, and paths.py (the data folder, a child's environment, the
//! OCR's threads). The crates that had their own copy re-export these from where they were (README.md lists them).
#![forbid(unsafe_code)]

pub mod limits;
pub mod model;
pub mod names;
pub mod paths;
pub mod text;

pub use model::{Combo, Entry, OcrLine, Rect, Scenes};
pub use paths::{app_dir, app_dir_for, child_env, child_env_from, custom_sound_dir, ocr_threads, ocr_threads_for};
pub use text::{clean_stored_name, fold, normalize_text, split_ellipsis, strip_noise, MIN_PREFIX_CHARS};
