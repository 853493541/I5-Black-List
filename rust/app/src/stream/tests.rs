//! The stream UI against golden/stream.json, which the Python app writes (golden/make.py).

use serde_json::Value;

use super::mirror::{fit, place, to_window, Follows, Rect, Spot};
use super::*;

fn golden() -> Value {
    serde_json::from_str(include_str!("golden/stream.json")).expect("golden/stream.json parses")
}

fn state_of(case: &str) -> LivehimeState {
    match case {
        "closed" => LivehimeState::NotFound,
        "unknown" => LivehimeState::Found(SceneIssue::Unknown),
        "missing" => LivehimeState::Found(SceneIssue::Missing),
        "hidden" => LivehimeState::Found(SceneIssue::Hidden),
        "behind" => LivehimeState::Found(SceneIssue::Behind),
        "ok" => LivehimeState::Capturing,
        other => panic!("unknown case {other}"),
    }
}

#[test]
fn constants_match_python() {
    let golden = golden();
    assert_eq!(golden["title"], TITLE);
    assert_eq!(golden["frame_ms"], FRAME_MS);
    assert_eq!(golden["ask_ms"], ASK_MS);
    assert_eq!(golden["follow_ms"], FOLLOW_MS);
    let spots: Vec<&str> = Spot::ALL.iter().map(|spot| spot.key()).collect();
    assert_eq!(golden["spots"], serde_json::json!(spots));
    assert_eq!(Spot::to_try(true), &[Spot::Edge, Spot::On]);
}

#[test]
fn every_state_says_what_python_says() {
    let golden = golden();
    for (key, words) in golden["words"].as_object().unwrap() {
        assert_eq!(state_of(key).words(), words.as_str().unwrap(), "{key}");
    }
    for (case, want) in golden["status"].as_object().unwrap() {
        let state = state_of(case);
        assert_eq!(state.key(), want["state"].as_str().unwrap(), "{case}");
        assert_eq!(state.words(), want["words"].as_str().unwrap(), "{case}");
        let row = row_status(true, &state);
        let words = want["row"].as_str().unwrap();
        assert_eq!(row.as_ref().map(|(said, _)| said.as_str()).unwrap_or(""), words, "{case}");
        let tone = if want["tone"] == "ok" { Tone::Ok } else { Tone::Warn };
        if let Some((_, said)) = row {
            assert_eq!(said, tone, "{case}");
        }
    }
    assert_eq!(row_status(false, &LivehimeState::Capturing), None);
    assert_eq!(row_status(true, &LivehimeState::Error("no log".into())), None);
}

#[test]
fn names_are_masked_as_python_masks_them() {
    for (name, want) in golden()["masked"].as_object().unwrap() {
        assert_eq!(masked_name(name), want.as_str().unwrap(), "{name}");
    }
    assert_eq!(listed("示例坏人", false, true), "示***");
    assert_eq!(listed("示例坏人", true, false), "示***");
    assert_eq!(listed("示例坏人", false, false), "示例坏人");
}

#[test]
fn the_mirror_fits_the_game_as_python_does() {
    let golden = golden();
    for case in golden["fits"].as_array().unwrap() {
        let size = (case["window"][0].as_i64().unwrap() as i32, case["window"][1].as_i64().unwrap() as i32);
        let a: Vec<i32> = case["area"].as_array().unwrap().iter().map(|v| v.as_i64().unwrap() as i32).collect();
        let area = Rect::new(a[0], a[1], a[2], a[3]);
        let (scale, offset) = fit(area, size, None);
        let close = |got: f64, want: &Value| (got - want.as_f64().unwrap()).abs() < 1e-9;
        assert!(close(scale, &case["scale"]), "{case}");
        assert!(close(offset.0, &case["offset"][0]) && close(offset.1, &case["offset"][1]), "{case}");
        let point = to_window((a[0] + 40, a[1] + 30), area, size, None);
        assert!(close(point.0, &case["point"][0]) && close(point.1, &case["point"][1]), "{case}");
    }
    let follows = Follows { scale: 0.5, start: (10.0, 20.0), corner: (100, 100) };
    assert_eq!(fit(Rect::new(140, 120, 800, 600), (1920, 1080), Some(follows)), (0.5, (30.0, 30.0)));
}

#[test]
fn the_mirror_sits_where_python_puts_it() {
    let golden = golden();
    let s: Vec<i32> = golden["screen"].as_array().unwrap().iter().map(|v| v.as_i64().unwrap() as i32).collect();
    let screen = Rect::new(s[0], s[1], s[2], s[3]);
    for (case, spot) in golden["places"].as_array().unwrap().iter().zip(Spot::ALL) {
        let r = place(Rect::new(10, 10, 300, 200), spot, &[screen]);
        assert_eq!(serde_json::json!([r.x, r.y, r.width, r.height]), case["rect"], "{}", spot.key());
    }
    // Two monitors: off is right of the rightmost one, on the game's own.
    let screens = [Rect::new(0, 0, 1920, 1080), Rect::new(1920, -200, 2560, 1440)];
    assert_eq!(place(Rect::new(100, 100, 800, 600), Spot::Off, &screens), Rect::new(4543, 0, 1920, 1080));
    assert_eq!(place(Rect::new(100, 100, 800, 600), Spot::Edge, &screens), Rect::new(4479, -200, 1920, 1080));
    assert_eq!(place(Rect::new(2000, 0, 800, 600), Spot::On, &screens), Rect::new(1920, -200, 2560, 1440));
}

#[test]
fn turning_it_on_brings_the_guide_once() {
    let first = on_choice(true, false, false);
    assert!(first.contains(&StreamAction::ShowGuide) && first.contains(&StreamAction::MarkGuided));
    assert!(!on_choice(true, true, false).contains(&StreamAction::ShowGuide));
    assert!(!on_choice(false, false, false).contains(&StreamAction::ShowGuide));
    assert_eq!(set_stream_mode(true, true)[1], StreamAction::EndQuickPlay);
    assert_eq!(overlay_target(true, true), OverlayTarget::Stream);
    assert_eq!(overlay_target(true, false), OverlayTarget::Nowhere);
    assert_eq!(overlay_target(false, true), OverlayTarget::Screen);
    assert!(names_hidden(false, true));
}

/// Every page and dialog renders; STREAM_SHOTS_DIR keeps the pictures (shots/stream/ is made from them).
#[test]
fn every_page_and_dialog_renders() {
    let dir = std::env::var_os("STREAM_SHOTS_DIR")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| std::env::temp_dir().join(format!("stream-shots-{}", std::process::id())));
    let written = render::render_all(&dir).expect("the stream UI renders");
    assert_eq!(written.len(), 10);
    for path in written {
        assert!(std::fs::metadata(&path).map(|meta| meta.len() > 1000).unwrap_or(false), "{}", path.display());
    }
}
