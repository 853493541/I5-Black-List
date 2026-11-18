//! src/cli.rs against what __main__.py does with the same arguments (tools/rust_golden_diag.py's "cli" cases).
#[path = "../src/cli.rs"]
mod cli;

use cli::{Command, SeatState};
use serde_json::Value;

fn golden() -> Value {
    let text = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/../data/tests/golden/diag.json")).unwrap();
    serde_json::from_str(&text).unwrap()
}

#[test]
fn accepts_and_refuses_the_same_arguments_as_python() {
    let golden = golden();
    let cases = golden["cli"].as_array().unwrap();
    assert!(cases.len() >= 10);
    for case in cases {
        let args: Vec<&str> = case["args"].as_array().unwrap().iter().map(|a| a.as_str().unwrap()).collect();
        let got = cli::parse(&args);
        match case["way"].as_array().map(|w| w.as_slice()) {
            None => {
                assert_eq!(got, Err(cli::UsageError), "{args:?}");
                assert_eq!(case["code"], cli::USAGE_CODE);
                assert_eq!(case["stderr"].as_str().unwrap(), cli::usage("python -m blacklist_detect") + "\n");
            }
            Some([way, rest @ ..]) => {
                let want = match (way.as_str().unwrap(), rest) {
                    ("window", [background]) => Command::Window { background: background.as_bool().unwrap() },
                    ("check", [image]) => Command::Check { image: image.as_str().unwrap().into() },
                    ("download-models", []) => Command::DownloadModels,
                    other => panic!("unknown way {other:?}"),
                };
                assert_eq!(got, Ok(want), "{args:?}");
            }
            Some([]) => panic!("empty way"),
        }
    }
}

#[test]
fn seat_lines_match_python() {
    for case in golden()["slot_lines"].as_array().unwrap() {
        let state = match case["state"].as_str().unwrap() {
            "完整" => SeatState::Whole,
            "截断" => SeatState::Truncated,
            _ => SeatState::Unclear,
        };
        let line = cli::seat_line(case["index"].as_u64().unwrap() as usize, state, case["confidence"].as_f64().unwrap(), case["raw"].as_str().unwrap());
        assert_eq!(line, case["line"].as_str().unwrap());
    }
}

#[test]
fn check_prints_message_seats_hits_and_exits_by_header() {
    assert_eq!(SeatState::of(true, true), SeatState::Unclear);
    assert_eq!(SeatState::of(false, true), SeatState::Truncated);
    assert_eq!(SeatState::of(false, false), SeatState::Whole);
    let check = cli::Check {
        message: "读到 12 个名字".into(),
        seats: vec![(8, SeatState::Whole, 0.98, "示例坏人".into())],
        hits: vec!["示例坏人 在黑名单".into()],
        header_found: false,
    };
    assert_eq!(check.lines(), ["读到 12 个名字", " 9  完整    0.98  示例坏人", "示例坏人 在黑名单"]);
    assert_eq!(check.exit_code(), 1);
    assert_eq!(cli::Check { header_found: true, ..check }.exit_code(), 0);
    assert_eq!(cli::DOWNLOAD_OK, "PaddleOCR 中文模型已在本机可用。");
}
