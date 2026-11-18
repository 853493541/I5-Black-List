//! Parity with the Python app on golden data it wrote (tools/rust_golden_common.py).

use std::collections::BTreeMap;
use std::path::Path;

use common::limits::{MAX_NAME, MAX_NOTE, MAX_TAG, OLD_SHARE_MARKS, SCENE_KEYS, SHARE_MARK, TAGS};
use common::names::{LAUNCHERS, PROCESSES};
use common::text::{clean_stored_name, fold, normalize_text, split_ellipsis, strip_noise, MIN_PREFIX_CHARS};
use common::{app_dir_for, child_env_from, custom_sound_dir, ocr_threads_for};
use serde_json::Value;

fn golden() -> Value {
    let text = std::fs::read_to_string(Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/golden.json")).unwrap();
    serde_json::from_str(&text).unwrap()
}

fn strings(value: &Value) -> Vec<String> {
    value.as_array().unwrap().iter().map(|v| v.as_str().unwrap().to_string()).collect()
}

#[test]
fn name_rules_match_python() {
    let golden = golden();
    let texts = golden["texts"].as_array().unwrap();
    assert!(texts.len() >= 600);
    let mut wrong = Vec::new();
    for case in texts {
        let raw = case["raw"].as_str().unwrap();
        let (visible, cut) = split_ellipsis(raw);
        let split = &case["split_ellipsis"];
        let same = normalize_text(raw) == case["normalize_text"]
            && visible == split[0]
            && cut == split[1]
            && strip_noise(raw) == case["strip_noise"]
            && fold(raw) == case["fold"]
            && clean_stored_name(raw) == case["clean_stored_name"];
        if !same {
            wrong.push(raw.to_string());
        }
    }
    assert!(wrong.is_empty(), "{} of {} differ: {wrong:?}", wrong.len(), texts.len());
    assert_eq!(golden["min_prefix_chars"], MIN_PREFIX_CHARS);
}

#[test]
fn app_dir_matches_python() {
    let golden = golden();
    for case in golden["app_dirs"].as_array().unwrap() {
        let env: BTreeMap<String, String> = serde_json::from_value(case["env"].clone()).unwrap();
        let windows = case["windows"].as_bool().unwrap();
        let dir = app_dir_for(windows, |name| env.get(name).cloned(), Path::new("/home/u"));
        let shown = dir.to_string_lossy().replace('\\', "/");
        assert_eq!(shown, case["dir"].as_str().unwrap(), "{case}");
    }
    assert_eq!(custom_sound_dir(Path::new("/data/root")).to_string_lossy().replace('\\', "/"), golden["custom_sound_dir"]);
}

#[test]
fn child_env_matches_python() {
    let golden = golden();
    let given: BTreeMap<String, String> = serde_json::from_value(golden["child_env_in"].clone()).unwrap();
    let want: BTreeMap<String, String> = serde_json::from_value(golden["child_env_out"].clone()).unwrap();
    let got: BTreeMap<String, String> = child_env_from(given).into_iter().collect();
    assert_eq!(got, want);
}

#[test]
fn ocr_threads_match_python() {
    let golden = golden();
    for (cores, threads) in golden["ocr_threads"].as_object().unwrap() {
        assert_eq!(ocr_threads_for(cores.parse().unwrap()), threads.as_u64().unwrap() as usize, "{cores} cores");
    }
}

#[test]
fn constants_match_python() {
    let golden = golden();
    assert_eq!(strings(&golden["launchers"]), LAUNCHERS);
    assert_eq!(strings(&golden["processes"]), PROCESSES);
    assert_eq!(strings(&golden["tags"]), TAGS);
    assert_eq!(strings(&golden["old_share_marks"]), OLD_SHARE_MARKS);
    assert_eq!(strings(&golden["scene_keys"]), SCENE_KEYS);
    assert_eq!(golden["share_mark"], SHARE_MARK);
    assert_eq!((golden["max_name"].as_u64(), golden["max_note"].as_u64(), golden["max_tag"].as_u64()),
               (Some(MAX_NAME as u64), Some(MAX_NOTE as u64), Some(MAX_TAG as u64)));
}
