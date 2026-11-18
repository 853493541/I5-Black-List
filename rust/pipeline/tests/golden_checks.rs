//! The Rust check against what the Python check finds (tools/rust_golden_pipeline.py): the lobby, the countdown and
//! ready count, the button and game boxes, the twelve seats (names as hashes) and the marks on two lists. The models
//! and frames are not in git: PIPELINE_MODELS (default /tmp/pl/models), PIPELINE_FRAMES (/tmp/pl/frames) and
//! PIPELINE_ORT_LIB (libonnxruntime of the onnxruntime 1.32.0 wheel) say where they are; without them the test says
//! so and passes.

use std::path::PathBuf;

use lobby::Entry;
use opencv::core::Mat;
use opencv::{imgcodecs, imgproc};
use pipeline::check::mark_names;
use pipeline::{CheckResult, Checker, Hit, ModelDirs, NameSlot};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

const GOLDEN: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/golden/checks.json");
const ORT_LIB: &str = "/tmp/pl/venv/lib/python3.12/site-packages/onnxruntime/capi/libonnxruntime.so.1.32.0";

fn setting(name: &str, default: &str) -> PathBuf {
    PathBuf::from(std::env::var(name).unwrap_or_else(|_| default.to_string()))
}

fn hashed(text: &str) -> String {
    Sha256::digest(text.as_bytes()).iter().take(8).map(|b| format!("{b:02x}")).collect()
}

fn entry(name: &str, reason: &str, tags: &[&str], nickname: &str) -> Entry {
    Entry { reason: reason.into(), tags: tags.iter().map(|t| t.to_string()).collect(), nickname: nickname.into(), ..Entry::named(name) }
}

fn made_up() -> (Vec<Entry>, Vec<Entry>) {
    (vec![entry("示例坏人", "炸房两次", &["贴脸", "炸房"], "")], vec![entry("心动小鹿", "", &[], "心动星星")])
}

fn derived(index: usize, names: &[NameSlot]) -> (Vec<Entry>, Vec<Entry>) {
    let (mut black, mut likes) = made_up();
    if !names.is_empty() {
        let warned = &names[index % names.len()];
        let liked = &names[(index + 5) % names.len()];
        if !warned.visible.is_empty() {
            black.push(entry(&warned.visible, "测试", &[], ""));
        }
        if !liked.visible.is_empty() {
            likes.push(Entry::named(liked.visible.chars().take(4).collect::<String>()));
        }
    }
    (black, likes)
}

fn marks(hits: &[Hit], likes: &[(usize, usize)]) -> Value {
    let hits: Vec<Value> =
        hits.iter().map(|h| json!({"seat": h.index, "entry": h.entry, "line": hashed(&h.line), "truncated": h.truncated})).collect();
    json!({"hits": hits, "likes": likes.iter().map(|l| json!([l.0, l.1])).collect::<Vec<_>>()})
}

fn record(name: &str, result: &CheckResult, index: usize) -> Value {
    let (black, likes) = derived(index, &result.names);
    let (more_hits, more_likes) = mark_names(&result.names, &black, &likes);
    json!({
        "frame": name,
        "header_found": result.header_found,
        "message": result.message,
        "countdown": result.countdown_seconds,
        "ready": result.ready_count,
        "button_box": result.button_box,
        "game_box": result.game_box,
        "spot": result.timings.spot,
        "seats": result.names.iter().map(|s| json!({
            "box": s.bbox, "raw": hashed(&s.raw), "visible": hashed(&s.visible),
            "truncated": s.truncated, "unclear": s.unclear, "confidence": s.confidence,
        })).collect::<Vec<_>>(),
        "made_up": marks(&result.hits, &result.likes),
        "derived": marks(&more_hits, &more_likes),
    })
}

/// Equal, with floats within 1e-5 (scores) and boxes as numbers whatever their JSON type.
fn same(a: &Value, b: &Value) -> bool {
    match (a, b) {
        (Value::Number(x), Value::Number(y)) => (x.as_f64().unwrap() - y.as_f64().unwrap()).abs() <= 1e-5,
        (Value::Array(x), Value::Array(y)) => x.len() == y.len() && x.iter().zip(y).all(|(p, q)| same(p, q)),
        (Value::Object(x), Value::Object(y)) => x.len() == y.len() && x.iter().all(|(k, v)| y.get(k).is_some_and(|w| same(v, w))),
        _ => a == b,
    }
}

fn load(path: &std::path::Path) -> Mat {
    let bgr = imgcodecs::imread(path.to_str().unwrap(), imgcodecs::IMREAD_COLOR).unwrap();
    let mut rgb = Mat::default();
    imgproc::cvt_color_def(&bgr, &mut rgb, imgproc::COLOR_BGR2RGB).unwrap();
    rgb
}

#[test]
fn every_check_matches_the_python_check() {
    let (lib, models, frames) =
        (setting("PIPELINE_ORT_LIB", ORT_LIB), setting("PIPELINE_MODELS", "/tmp/pl/models"), setting("PIPELINE_FRAMES", "/tmp/pl/frames"));
    if !lib.is_file() || !models.is_dir() || !frames.is_dir() {
        eprintln!("skipped: no ONNX Runtime at {}, models at {} or frames at {}", lib.display(), models.display(), frames.display());
        return;
    }
    let golden: Value = serde_json::from_str(&std::fs::read_to_string(GOLDEN).unwrap()).unwrap();
    let env = pipeline::runtime(&lib).unwrap();
    let mut checker = Checker::new(env, &ModelDirs::under(&models).unwrap(), 4).unwrap();
    let checks = golden["checks"].as_array().unwrap();
    let fields = ["header_found", "message", "countdown", "ready", "button_box", "game_box", "spot", "seats", "made_up", "derived"];
    let mut differ = vec![0usize; fields.len()];
    let (mut seats, mut seats_same) = (0, 0);
    for (index, want) in checks.iter().enumerate() {
        let name = want["frame"].as_str().unwrap();
        let (black, likes) = made_up();
        let result = checker.check(&[load(&frames.join(name))], &black, &likes, None).unwrap();
        let got = record(name, &result, index);
        for (count, field) in differ.iter_mut().zip(fields) {
            if !same(&got[field], &want[field]) {
                *count += 1;
                eprintln!("{index} {name} {field}: rust {} python {}", got[field], want[field]);
            }
        }
        for (a, b) in got["seats"].as_array().unwrap().iter().zip(want["seats"].as_array().unwrap()) {
            seats += 1;
            seats_same += usize::from(same(a, b));
        }
    }
    eprintln!("{} checks; seats identical {seats_same}/{seats}; checks differing per field:", checks.len());
    for (field, count) in fields.iter().zip(&differ) {
        eprintln!("  {field}: {count}");
    }
    assert!(differ.iter().all(|&count| count == 0), "the Rust check differs from the Python check");
}
