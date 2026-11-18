//! Parity with the Python code on every lobby-corpus frame: tools/rust_golden_lobby.py wrote what the Python
//! reader read and what layout.py and match.py decided; the same lines in must give the same answers here.

use std::fs;
use std::path::PathBuf;

use lobby::{
    clean_stored_name, countdown_in, find_anchor, fold, game_screen, is_lobby_chrome, listed_tail,
    match_label, normalize_text, ready_in, ready_strip, split_ellipsis, strip_noise,
    with_game_ellipsis, Entry, NameLabel, OcrLine, NAME_BOXES,
};
use serde::Deserialize;

#[derive(Deserialize)]
struct Line {
    text: String,
    confidence: f64,
    #[serde(rename = "box")]
    bbox: [f64; 4],
}

#[derive(Deserialize)]
struct AnchorRecord {
    found: bool,
    reason: String,
    countdown_seconds: Option<i64>,
    ready_count: Option<i64>,
    scale: f64,
    name_boxes: Vec<[i64; 4]>,
    button_box: Option<[i64; 4]>,
    title_box: Option<[f64; 4]>,
    mode_box: Option<[f64; 4]>,
    countdown_box: Option<[f64; 4]>,
}

#[derive(Deserialize)]
struct Texts {
    text: String,
    normalize_text: String,
    split_ellipsis: (String, bool),
    with_game_ellipsis: String,
    strip_noise: String,
    fold: String,
    clean_stored_name: String,
    is_lobby_chrome: bool,
    countdown_in: Option<i64>,
    ready_in: Option<i64>,
}

#[derive(Deserialize)]
struct Seat {
    raw: String,
    visible: String,
    truncated: bool,
    unclear: bool,
    matches: Vec<(usize, String, bool)>,
    texts: Texts,
    listed_tail: Vec<Option<String>>,
}

#[derive(Deserialize)]
struct Frame {
    frame: u32,
    width: i64,
    height: i64,
    lines: Vec<Line>,
    anchor: AnchorRecord,
    contains_title: bool,
    ready_strip: Option<[f64; 4]>,
    game_screen: Option<[f64; 4]>,
    texts: Vec<Texts>,
    seats: Vec<Seat>,
    entries: Vec<String>,
}

fn golden_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/golden")
}

fn frames() -> Vec<Frame> {
    let mut paths: Vec<PathBuf> = fs::read_dir(golden_dir())
        .expect("golden folder")
        .map(|item| item.expect("entry").path())
        .filter(|path| {
            path.file_name()
                .is_some_and(|name| name.to_string_lossy().starts_with("frame_"))
        })
        .collect();
    paths.sort();
    paths
        .iter()
        .map(|path| serde_json::from_str(&fs::read_to_string(path).expect("read")).expect("parse"))
        .collect()
}

fn check_texts(frame: u32, want: &Texts) {
    let text = &want.text;
    let at = format!("frame {frame}, text #{}", text.chars().count());
    assert_eq!(
        normalize_text(text),
        want.normalize_text,
        "{at} normalize_text"
    );
    let split = split_ellipsis(text);
    assert_eq!(split, want.split_ellipsis, "{at} split_ellipsis");
    assert_eq!(
        with_game_ellipsis(&split.0, split.1),
        want.with_game_ellipsis,
        "{at} with_game_ellipsis"
    );
    assert_eq!(strip_noise(text), want.strip_noise, "{at} strip_noise");
    assert_eq!(fold(text), want.fold, "{at} fold");
    assert_eq!(
        clean_stored_name(text),
        want.clean_stored_name,
        "{at} clean_stored_name"
    );
    assert_eq!(
        is_lobby_chrome(text),
        want.is_lobby_chrome,
        "{at} is_lobby_chrome"
    );
    assert_eq!(countdown_in(text), want.countdown_in, "{at} countdown_in");
    assert_eq!(ready_in(text), want.ready_in, "{at} ready_in");
}

#[test]
fn name_boxes_match_python() {
    #[derive(Deserialize)]
    struct Constants {
        name_boxes: Vec<[f64; 4]>,
    }
    let text = fs::read_to_string(golden_dir().join("constants.json")).expect("constants");
    let constants: Constants = serde_json::from_str(&text).expect("parse");
    assert_eq!(*NAME_BOXES, constants.name_boxes);
}

#[test]
fn every_frame_finds_the_same_lobby() {
    let frames = frames();
    assert!(frames.len() >= 80, "golden frames: {}", frames.len());
    for frame in &frames {
        let n = frame.frame;
        let lines: Vec<OcrLine> = frame
            .lines
            .iter()
            .map(|line| OcrLine::new(line.text.clone(), line.confidence, line.bbox))
            .collect();
        let anchor = find_anchor(&lines, frame.width, frame.height);
        let want = &frame.anchor;
        assert_eq!(anchor.found, want.found, "frame {n} found");
        assert_eq!(anchor.reason, want.reason, "frame {n} reason");
        assert_eq!(
            anchor.countdown_seconds, want.countdown_seconds,
            "frame {n} countdown"
        );
        assert_eq!(anchor.ready_count, want.ready_count, "frame {n} ready");
        assert_eq!(anchor.scale, want.scale, "frame {n} scale");
        assert_eq!(anchor.name_boxes, want.name_boxes, "frame {n} name boxes");
        assert_eq!(anchor.button_box, want.button_box, "frame {n} button");
        assert_eq!(anchor.title_box, want.title_box, "frame {n} title");
        assert_eq!(anchor.mode_box, want.mode_box, "frame {n} mode");
        assert_eq!(
            anchor.countdown_box, want.countdown_box,
            "frame {n} countdown box"
        );
        assert_eq!(
            lobby::contains_title(&lines),
            frame.contains_title,
            "frame {n} title seen"
        );
        assert_eq!(
            ready_strip(&anchor),
            frame.ready_strip,
            "frame {n} ready strip"
        );
        assert_eq!(
            game_screen(&anchor),
            frame.game_screen,
            "frame {n} game screen"
        );
    }
}

#[test]
fn every_line_reads_the_same() {
    for frame in frames() {
        for texts in &frame.texts {
            check_texts(frame.frame, texts);
        }
    }
}

#[test]
fn every_seat_matches_the_same_entries() {
    let mut matched = 0;
    for frame in frames() {
        let entries: Vec<Entry> = frame.entries.iter().map(Entry::named).collect();
        for (seat_index, seat) in frame.seats.iter().enumerate() {
            let at = format!("frame {} seat {}", frame.frame, seat_index + 1);
            check_texts(frame.frame, &seat.texts);
            let label = NameLabel {
                raw: seat.raw.clone(),
                visible: seat.visible.clone(),
                truncated: seat.truncated,
                unclear: seat.unclear,
            };
            let got: Vec<(usize, String, bool)> = match_label(&label, &entries)
                .into_iter()
                .map(|found| {
                    (
                        found.index,
                        found.kind.as_str().to_string(),
                        found.truncated,
                    )
                })
                .collect();
            assert_eq!(got, seat.matches, "{at} matches");
            matched += got.len();
            let tails: Vec<Option<String>> = entries
                .iter()
                .map(|entry| listed_tail(&seat.visible, &entry.name))
                .collect();
            assert_eq!(tails, seat.listed_tail, "{at} listed_tail");
        }
    }
    assert!(matched > 100, "golden matches: {matched}");
}
