//! pipeline: one check, from captured frames to the twelve seats with their marks (blacklist_detect/pipeline.py,
//! the ONNX Runtime half of ocr_engine.py, the model finding of ocr_engine.model_dirs, and game_area.py).
//!
//! # For the app, the overlay and the Python bridge
//!
//! ```ignore
//! let env = pipeline::runtime(Path::new("onnxruntime.dll"))?;          // once per process
//! let dirs = pipeline::ModelDirs::find(&pipeline::search_roots()).ok_or(pipeline::Unavailable)?;
//! let mut checker = pipeline::Checker::new(env, &dirs, threads)?;
//! let frame = pipeline::rgb_frame(width, height, &rgb_bytes)?;       // or any CV_8UC3 RGB Mat
//! let result = checker.check(&[frame], &blacklist, &likes, None)?;
//! for seat in result.seats() { /* seat.index, seat.bbox, seat.name, seat.mark: Mark::Blacklist(i) | Guest(i) | None */ }
//! ```
//!
//! `check` takes every monitor's copy; the first one with the lobby is read. `result.message` is the line the app
//! shows, `result.button_box` and `result.game_box` place the marks (in that frame's pixels; `result.frame` says
//! which), `result.hits` the warnings and `result.likes` the 嘉宾 in seat order. A check remembers where the lobby
//! was and skips the search next time when its title looks as it did. Models missing: `Unavailable`, whose text is
//! what the app shows.
#![deny(unsafe_code)]

pub mod check;
pub mod engine;
pub mod game_area;
pub mod image;
pub mod models;
pub mod pixel;
pub mod spot;

use std::sync::OnceLock;

pub use check::{CheckResult, Checker, Hit, Mark, NameSlot, Seat, Timings, NAME_CONFIDENCE_MIN};
pub use engine::Engine;
pub use image::rgb_frame;
pub use models::{search_roots, ModelDirs};
pub use spot::LobbySpot;

pub type Error = Box<dyn std::error::Error + Send + Sync>;
pub type Result<T> = std::result::Result<T, Error>;

/// The reader could not be loaded (OcrUnavailable); its text is what the player sees.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Unavailable;

impl std::fmt::Display for Unavailable {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("识别功能没装好，重新解压一遍安装包")
    }
}

impl std::error::Error for Unavailable {}

/// ONNX Runtime from this library file, loaded once for the process; later calls get the same one.
pub fn runtime(library: &std::path::Path) -> Result<&'static ort::environment::Environment> {
    static ENV: OnceLock<ort::environment::Environment> = OnceLock::new();
    if let Some(env) = ENV.get() {
        return Ok(env);
    }
    // Unavailable, with ONNX Runtime's own words kept for the log.
    let env = ocr::init_runtime(library).map_err(|error| -> Error { format!("{Unavailable} ({error})").into() })?;
    Ok(ENV.get_or_init(|| env))
}
