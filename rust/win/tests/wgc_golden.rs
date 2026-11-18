//! Parity with wgc.py and wgc_diagnose.py: tools/rust_golden_livehime.py wrote what read() and words() make of
//! answers, and the verdict and report lines wgc_diagnose gives for made-up sets of Windows' answers.

use std::fs;
use std::path::PathBuf;

use serde_json::Value;
use win::wgc::{closing_lines, read, verdict, words, Test};

fn golden() -> Value {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/golden/livehime.json");
    serde_json::from_str::<Value>(&fs::read_to_string(path).expect("golden file")).expect("golden json")["wgc"].clone()
}

fn code(value: &Value) -> Option<u32> {
    value.as_u64().map(|v| v as u32)
}

#[test]
fn answers_are_read_and_said_as_python_does() {
    let data = golden();
    for pair in data["read"].as_array().unwrap() {
        // A negative answer (Python reads "-0x1" as -1) is never printed by the asking process; Rust has None.
        let want = if pair[1].as_i64().is_some_and(|v| v < 0) { None } else { code(&pair[1]) };
        assert_eq!(read(pair[0].as_str().unwrap()), want, "{pair}");
    }
    for pair in data["words"].as_array().unwrap() {
        assert_eq!(words(code(&pair[0])), pair[1].as_str().unwrap());
    }
}

#[test]
fn verdicts_and_report_lines_match_python() {
    let data = golden();
    let sets = data["sets"].as_array().unwrap();
    for set in sets {
        let tests: Vec<Test> = set["tests"]
            .as_array()
            .unwrap()
            .iter()
            .map(|t| Test { name: t["name"].as_str().unwrap().into(), hwnd: t["hwnd"].as_i64().unwrap(), there: code(&t["there"]), here: code(&t["here"]) })
            .collect();
        let (found, fix) = verdict(&tests);
        assert_eq!([found.as_str(), fix.as_str()], [set["verdict"][0].as_str().unwrap(), set["verdict"][1].as_str().unwrap()]);
        let owned = set["owned"].as_bool().unwrap();
        let lines = closing_lines(&tests, &|_| Some(owned));
        let mut want: Vec<String> = set["lines"].as_array().unwrap().iter().map(|l| l.as_str().unwrap().to_string()).collect();
        want.push(format!("verdict: {found}"));
        if !fix.is_empty() {
            want.push(format!("fix: {fix}"));
        }
        assert_eq!(lines, want);
    }
    assert_eq!(sets.len(), 300);
}
