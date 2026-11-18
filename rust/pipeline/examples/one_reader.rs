//! The check with one reader or two, on the same frames, for comparing them (BLACKLIST_DETECT_ONE_READER).
//!
//!     cargo run --release -p pipeline --example one_reader -- <libonnxruntime> <models> <frames> <two|one> [fresh]
//!
//! <frames> holds the corpus JPEGs and reference-lobby.png; the checks run in the golden order (tests/golden/checks.json:
//! the reference lobby twice, then the corpus), on one checker as the app keeps one, or with the remembered spot
//! forgotten before each check when `fresh` is given. Prints one JSON line per check (names as hashes, never as text),
//! then a summary line with the time per check and the peak memory.

use std::path::{Path, PathBuf};
use std::time::Instant;

use opencv::core::Mat;
use opencv::prelude::*;
use opencv::{imgcodecs, imgproc};
use pipeline::{Checker, Engine, ModelDirs};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

const GOLDEN: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/golden/checks.json");

fn hashed(text: &str) -> String {
    Sha256::digest(text.as_bytes()).iter().take(8).map(|b| format!("{b:02x}")).collect()
}

fn load(frames: &Path, name: &str) -> Mat {
    let png = frames.join(name);
    let path = if png.is_file() { png } else { png.with_extension("jpg") };
    let bgr = imgcodecs::imread(path.to_str().unwrap(), imgcodecs::IMREAD_COLOR).unwrap();
    assert!(!bgr.empty(), "no frame at {}", path.display());
    let mut rgb = Mat::default();
    imgproc::cvt_color_def(&bgr, &mut rgb, imgproc::COLOR_BGR2RGB).unwrap();
    rgb
}

fn peak_kb() -> u64 {
    let status = std::fs::read_to_string("/proc/self/status").unwrap_or_default();
    let line = status.lines().find(|l| l.starts_with("VmHWM:")).unwrap_or("VmHWM: 0 kB");
    line.split_whitespace().nth(1).and_then(|v| v.parse().ok()).unwrap_or(0)
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let (lib, models, frames) = (PathBuf::from(&args[1]), PathBuf::from(&args[2]), PathBuf::from(&args[3]));
    let one = args[4] == "one";
    let fresh = args.get(5).is_some_and(|a| a == "fresh");
    let golden: Value = serde_json::from_str(&std::fs::read_to_string(GOLDEN).unwrap()).unwrap();
    let env = pipeline::runtime(&lib).unwrap();
    let dirs = ModelDirs::under(&models).unwrap();
    let mut checker = Checker { engine: Engine::with_readers(env, &dirs, 4, one).unwrap(), spot: None };
    let (mut find, mut read, mut wall) = (Vec::new(), Vec::new(), Vec::new());
    for want in golden["checks"].as_array().unwrap() {
        let name = want["frame"].as_str().unwrap();
        let frame = load(&frames, name);
        if fresh {
            checker.spot = None;
        }
        let started = Instant::now();
        let result = checker.check(&[frame], &[], &[], None).unwrap();
        wall.push(started.elapsed().as_secs_f64());
        find.push(result.timings.find);
        read.push(result.timings.read);
        let seats: Vec<Value> =
            result.names.iter().map(|s| json!({"box": s.bbox, "raw": hashed(&s.raw), "visible": hashed(&s.visible), "confidence": s.confidence, "unclear": s.unclear})).collect();
        let line = json!({
            "frame": name, "found": result.header_found, "countdown": result.countdown_seconds, "ready": result.ready_count,
            "button_box": result.button_box, "game_box": result.game_box, "spot": result.timings.spot, "message": result.message, "seats": seats,
        });
        println!("{line}");
    }
    let total = |v: &[f64]| v.iter().sum::<f64>();
    let mut sorted = wall.clone();
    sorted.sort_by(f64::total_cmp);
    let summary = json!({
        "summary": true, "one_reader": checker.engine.one_reader(), "checks": wall.len(), "find_s": total(&find), "read_s": total(&read),
        "wall_s": total(&wall), "median_s": sorted[sorted.len() / 2], "peak_rss_kb": peak_kb(),
    });
    println!("{summary}");
}
