//! The Rust diag gives what diagnostics.py, paths.py and __main__.py give on the golden cases
//! (tools/rust_golden_diag.py writes tests/golden/diag.json).

use data::diag::{self, FlowTest, Machine, Run, Screen, Settings};
use data::logs::export::{export_logs, Account};
use serde_json::Value;

fn golden() -> Value {
    let text = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/tests/golden/diag.json")).unwrap();
    serde_json::from_str(&text).unwrap()
}

fn run(value: &Value) -> Run {
    value.as_object().map(|o| o.iter().map(|(k, v)| (k.clone(), v.as_f64().unwrap())).collect()).unwrap_or_default()
}

fn flow(input: &Value) -> FlowTest {
    let mut test = FlowTest::default();
    let num = |key: &str| input.get(key).and_then(Value::as_f64);
    let text = |key: &str| input.get(key).and_then(Value::as_str).map(str::to_string);
    if let Some(size) = input.get("size") {
        test.size = (size[0].as_u64().unwrap() as u32, size[1].as_u64().unwrap() as u32);
    }
    test.screens = input.get("screens").and_then(Value::as_u64).unwrap_or(1) as u32;
    test.device = text("device").unwrap_or(test.device);
    test.glance = num("glance").unwrap_or(0.0);
    test.auto = input.get("auto").map(run).unwrap_or_default();
    test.runs = input.get("runs").and_then(Value::as_array).map(|runs| runs.iter().map(run).collect()).unwrap_or_default();
    test.right = input.get("right").and_then(Value::as_u64).unwrap_or(0) as u32;
    test.error = text("error").unwrap_or_default();
    test.cpu_busy = num("cpu_busy");
    test.cpu_own = num("cpu_own");
    test.power = text("power").unwrap_or_default();
    test
}

#[test]
fn flow_test_text_and_numbers_match_python() {
    for case in golden()["flow"].as_array().unwrap() {
        let test = flow(&case["input"]);
        assert_eq!(test.text(), case["text"].as_str().unwrap(), "{}", case["input"]);
        assert_eq!(test.verdict(), case["verdict"].as_str().unwrap());
        let causes: Vec<String> = case["causes"].as_array().unwrap().iter().map(|c| c.as_str().unwrap().to_string()).collect();
        assert_eq!(test.causes(), causes);
        let hotkey: Run = case["hotkey"].as_array().unwrap().iter().map(|p| (p[0].as_str().unwrap().into(), p[1].as_f64().unwrap())).collect();
        assert_eq!(test.hotkey(), hotkey);
        for (got, key) in [(test.hotkey_total(), "hotkey_total"), (test.auto_total(), "auto_total"), (test.first_total(), "first_total")] {
            assert_eq!(got, case[key].as_f64().unwrap(), "{key}");
        }
    }
}

#[test]
fn machine_line_matches_python() {
    for case in golden()["machine"].as_array().unwrap() {
        let c = &case["input"];
        let s = |key: &str| c[key].as_str().unwrap_or("").to_string();
        let cpu = if s("cpu").is_empty() { s("processor") } else { s("cpu") };
        let machine = Machine {
            cpu,
            threads: c["threads"].as_u64().unwrap() as usize,
            memory_total_gb: c["memory"][0].as_f64().unwrap(),
            memory_free_gb: c["memory"][1].as_f64().unwrap(),
            gpus: c["gpus"].as_array().unwrap().iter().map(|g| g.as_str().unwrap().to_string()).collect(),
            product: s("product"),
            display_version: s("display"),
            build: c["build"].as_u64().unwrap() as u32,
            version: s("version"),
            power: s("power"),
        };
        assert_eq!(machine.line(), case["line"].as_str().unwrap());
    }
}

#[test]
fn screens_power_threads_match_python() {
    let golden = golden();
    for case in golden["screens"].as_array().unwrap() {
        let screens: Vec<Screen> = case["input"]
            .as_array()
            .unwrap()
            .iter()
            .map(|s| Screen { width: s[0].as_f64().unwrap(), height: s[1].as_f64().unwrap(), ratio: s[2].as_f64().unwrap() })
            .collect();
        assert_eq!(diag::screens_line(Some(&screens)), case["line"].as_str().unwrap());
    }
    assert_eq!(diag::screens_line(None), "?");
    for case in golden["power"].as_array().unwrap() {
        let byte = |key: &str| case[key].as_u64().unwrap() as u8;
        assert_eq!(diag::power_note(byte("ac"), byte("percent"), byte("saver")), case["note"].as_str().unwrap());
    }
    for pair in golden["ocr_threads"].as_array().unwrap() {
        assert_eq!(diag::ocr_threads(pair[0].as_u64().unwrap() as usize), pair[1].as_str().unwrap());
    }
    let names: Vec<&str> = golden["sample_names"].as_array().unwrap().iter().map(|n| n.as_str().unwrap()).collect();
    assert_eq!(names, diag::SAMPLE_NAMES);
    let constants = &golden["constants"];
    assert_eq!((diag::SPEED_FINE, diag::SPEED_SLOW, diag::LOBBY_SHARE), (
        constants["speed_fine"].as_f64().unwrap(),
        constants["speed_slow"].as_f64().unwrap(),
        constants["lobby_share"].as_f64().unwrap()
    ));
}

fn pairs(value: &Value) -> Vec<(String, String)> {
    value.as_array().unwrap().iter().map(|p| (p[0].as_str().unwrap().into(), p[1].as_str().unwrap().into())).collect()
}

#[test]
fn child_env_matches_python() {
    for case in golden()["child_env"].as_array().unwrap() {
        assert_eq!(diag::child_env(pairs(&case["input"])), pairs(&case["output"]));
    }
}

fn clock() -> chrono::NaiveDateTime {
    chrono::NaiveDate::from_ymd_opt(2026, 11, 18).unwrap().and_hms_opt(9, 5, 7).unwrap()
}

const MACHINE_LINE: &str = "CPU 示例 CPU (8 threads); RAM 16.0 GB (8.0 GB free); GPU ?; Windows 11 Home 23H2 build 10.0.22631";

#[test]
fn summary_and_export_match_python_byte_for_byte() {
    let golden = golden();
    for case in golden["summary"].as_array().unwrap() {
        let c = &case["input"];
        let settings = Settings {
            safe_mode: c["safe_mode"].as_bool().unwrap(),
            auto_capture: c["auto_capture"].as_bool().unwrap(),
            stream_mode: c["stream_mode"].as_str().unwrap().into(),
            hotkey: c["hotkey"].as_str().unwrap().into(),
            entries: c["entries"].as_u64().unwrap() as usize,
            likes: c["likes"].as_u64().unwrap() as usize,
            scans: c["scans"].as_u64().unwrap() as usize,
        };
        let text = diag::summary_text("v9.9.9", clock(), MACHINE_LINE, "1920x1080 at 150%", c["device"].as_str().unwrap(), &settings);
        assert_eq!(text, case["text"].as_str().unwrap());
    }
    let export = &golden["export"];
    let report = flow(&golden["flow"][2]["input"]).text();
    assert_eq!(report, export["report"].as_str().unwrap());
    let dir = tempfile::tempdir().unwrap();
    let logs = data::logs::log_dir(&dir.path().join("root"));
    std::fs::create_dir_all(&logs).unwrap();
    for (name, text) in export["files"].as_object().unwrap() {
        std::fs::write(logs.join(name), text.as_str().unwrap()).unwrap();
    }
    let account = Account { home: export["home"].as_str().unwrap().into(), user: export["user"].as_str().unwrap().into(), short: String::new() };
    let summary = golden["summary"][0]["text"].as_str().unwrap();
    let path = export_logs(&dir.path().join("root"), summary, &dir.path().join("desk"), &report, &diag::export_stamp(clock()), &account).unwrap();
    assert_eq!(path.file_name().unwrap().to_str().unwrap(), export["name"].as_str().unwrap());
    let written = std::fs::read_to_string(path).unwrap().replace("\r\n", "\n");
    assert_eq!(written, export["text"].as_str().unwrap());
}

#[test]
fn cpu_numbers_follow_cpu_window() {
    use diag::SystemTimes;
    let before = SystemTimes { idle: 1_000, kernel: 2_000, user: 500 };
    let after = SystemTimes { idle: 1_300, kernel: 2_600, user: 900 };
    let (busy, own) = diag::cpu_numbers(Some(before), Some(after), 0.5, 1.0, 4).unwrap();
    assert_eq!((busy, own), (70.0, 12.5));
    assert_eq!(diag::cpu_text(Some((busy, own))), "CPU 70% (this app 12%)");
    assert_eq!(diag::cpu_numbers(None, Some(after), 0.5, 1.0, 4), None);
    assert_eq!(diag::cpu_numbers(Some(after), Some(after), 0.5, 1.0, 4), None);
    assert_eq!(diag::cpu_text(None), "");
    assert_eq!(diag::cpu_numbers(Some(before), Some(after), 1.0, 0.0, 0).unwrap().1, 1e8);
}

#[test]
fn settings_come_from_the_store_and_the_fallback_has_threads() {
    assert!(Machine::fallback().threads >= 1);
    assert!(Machine::fallback().line().starts_with("CPU "));
    assert_eq!(diag::desktop_fallback(std::path::Path::new("/h")), std::path::PathBuf::from("/h/Desktop"));
    assert_eq!(diag::start_threads(Some("1".into()), 12), (Some("1".into()), "8".into()));
}
