//! Parity with the Python 直播模式 code: tools/rust_golden_livehime.py wrote what livehime.py, livehime_layout.py,
//! ui_stream.StreamMirror and masked_name make of made-up scene files, logs, windows and screens.

use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::PathBuf;

use serde::Deserialize;
use serde_json::Value;
use win::livehime::follow::{fit, native_to_logical, to_window, where_livehime_has_it, Follow, Mirror, Screen};
use win::livehime::layout::{placements, Placement, StudioWatch};
use win::livehime::mask::masked_name;
use win::livehime::{game_capture, status, Capture, SceneWatch, Status};

#[derive(Deserialize)]
struct P {
    scene: String,
    name: String,
    title: String,
    window_class: String,
    exe: String,
    client_area: bool,
    whole_screen: bool,
    visible: bool,
    pos: (f64, f64),
    scale: (f64, f64),
    crop: (i64, i64, i64, i64),
    bounds_type: i64,
    bounds: (f64, f64),
    bounds_align: i64,
    align: i64,
    rotation: f64,
}

impl From<P> for Placement {
    fn from(p: P) -> Placement {
        let P { scene, name, title, window_class, exe, client_area, whole_screen, visible, pos, scale, crop, .. } = p;
        Placement {
            scene, name, title, window_class, exe, client_area, whole_screen, visible, pos, scale, crop,
            bounds_type: p.bounds_type, bounds: p.bounds, bounds_align: p.bounds_align, align: p.align, rotation: p.rotation,
        }
    }
}

fn golden() -> Value {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/golden/livehime.json");
    serde_json::from_str(&fs::read_to_string(path).expect("golden file")).expect("golden json")
}

fn placement(value: &Value) -> Placement {
    serde_json::from_value::<P>(value.clone()).expect("placement").into()
}

fn f(value: &Value) -> f64 {
    value.as_f64().expect("number")
}

fn work(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("livehime-golden-{}-{name}", std::process::id()));
    fs::create_dir_all(&dir).unwrap();
    dir
}

#[test]
fn on_canvas_matches_python_for_every_case() {
    let data = golden();
    let cases = data["on_canvas"].as_array().unwrap();
    for case in cases {
        let item = placement(&case["placement"]);
        let rect = item.on_canvas(f(&case["size"][0]), f(&case["size"][1]));
        let want: Vec<f64> = case["rect"].as_array().unwrap().iter().map(f).collect();
        assert_eq!(vec![rect.0, rect.1, rect.2, rect.3], want, "{case}");
    }
    assert_eq!(cases.len(), 400);
}

#[test]
fn placements_match_python() {
    let data = golden();
    for case in data["placements"].as_array().unwrap() {
        let (current, placed) = placements(case["text"].as_str().unwrap()).unwrap();
        assert_eq!(current, case["current"].as_str().unwrap());
        let want: Vec<Placement> = case["placed"].as_array().unwrap().iter().map(placement).collect();
        assert_eq!(placed, want);
    }
}

#[test]
fn studio_watch_matches_python_as_the_log_grows() {
    let data = golden();
    let dir = work("studio");
    for (index, case) in data["studio"].as_array().unwrap().iter().enumerate() {
        let path = dir.join(format!("livehime{index}.log"));
        fs::write(&path, b"").unwrap();
        let mut watch = StudioWatch::new(Some(path.clone()), case["reach"].as_u64().unwrap());
        for step in case["steps"].as_array().unwrap() {
            let bytes = step["data"].as_str().unwrap().as_bytes();
            if step["mode"] == "reset" {
                fs::write(&path, bytes).unwrap();
            } else {
                OpenOptions::new().append(true).open(&path).unwrap().write_all(bytes).unwrap();
            }
            let found = watch.studio();
            let want = &step["studio"];
            let canvas = want["canvas"].as_array().map(|c| (c[0].as_i64().unwrap(), c[1].as_i64().unwrap()));
            assert_eq!(found.canvas, canvas, "{step}");
            assert_eq!(found.double_screen, want["double_screen"].as_bool());
            assert_eq!(found.two_canvas, want["two_canvas"].as_bool());
            assert_eq!(found.synced, want["synced"].as_str().unwrap(), "{step}");
            assert_eq!(found.edited, want["edited"].as_str().unwrap(), "{step}");
            assert_eq!(found.unsynced(), want["unsynced"].as_bool().unwrap());
        }
    }
}

fn capture(value: &Value) -> Capture {
    Capture {
        title: value["title"].as_str().unwrap().into(),
        window_class: value["window_class"].as_str().unwrap().into(),
        exe: value["exe"].as_str().unwrap().into(),
        visible: value["visible"].as_bool().unwrap(),
    }
}

#[test]
fn scene_watch_status_and_game_capture_match_python() {
    let data = golden();
    let title = data["title"].as_str().unwrap();
    let dir = work("scene");
    for (index, case) in data["scene"].as_array().unwrap().iter().enumerate() {
        let path = dir.join(format!("bililive{index}.log"));
        fs::write(&path, b"x\n".repeat(case["start_size"].as_u64().unwrap() as usize / 2)).unwrap();
        let mut watch = SceneWatch::new(Some(path.clone()));
        for step in case["steps"].as_array().unwrap() {
            OpenOptions::new().append(true).open(&path).unwrap().write_all(step["data"].as_str().unwrap().as_bytes()).unwrap();
            if step["restart"].as_bool().unwrap() {
                watch = SceneWatch::new(Some(path.clone()));
            }
            let scene = watch.scene();
            let want = step["scene"].as_array().map(|items| items.iter().map(capture).collect::<Vec<_>>());
            assert_eq!(scene, want, "{step}");
            let covers: Vec<String> = step["covers"].as_array().unwrap().iter().map(|v| v.as_str().unwrap().into()).collect();
            let judge = |c: &Capture| covers.contains(&c.title);
            let key = |s: Option<Status>| s.map_or("", Status::key);
            assert_eq!(key(status(title, true, scene.as_deref(), Some(&judge))), step["status"].as_str().unwrap());
            assert_eq!(key(status(title, true, scene.as_deref(), None)), step["status_no_covers"].as_str().unwrap());
            let game = game_capture(scene.as_deref(), title).cloned();
            assert_eq!(game, step["game"].as_object().map(|_| capture(&step["game"])));
        }
    }
}

#[test]
fn follow_fit_and_to_window_match_python() {
    let data = golden();
    let title = data["title"].as_str().unwrap();
    for case in data["follow"].as_array().unwrap() {
        let placed: Vec<Placement> = case["placed"].as_array().unwrap().iter().map(placement).collect();
        let current = case["current"].as_str().unwrap();
        let scene = case["has_file"].as_bool().unwrap().then_some((current, placed.as_slice()));
        let frame = case["frame"].as_array().map(|r| (r[0].as_i64().unwrap(), r[1].as_i64().unwrap(), r[2].as_i64().unwrap(), r[3].as_i64().unwrap()));
        let m = &case["mine"];
        let mirror = Mirror {
            mine: (m[0].as_i64().unwrap(), m[1].as_i64().unwrap(), m[2].as_i64().unwrap(), m[3].as_i64().unwrap()),
            width: case["logical"][0].as_i64().unwrap(),
            height: case["logical"][1].as_i64().unwrap(),
        };
        let screens: Vec<Screen> = case["screens"]
            .as_array()
            .unwrap()
            .iter()
            .map(|s| Screen { x: s[0].as_i64().unwrap(), y: s[1].as_i64().unwrap(), width: s[2].as_i64().unwrap(), height: s[3].as_i64().unwrap(), ratio: f(&s[4]) })
            .collect();
        let to_logical = |x: f64, y: f64| native_to_logical(x, y, &screens, 1.0);
        let (follows, note) = where_livehime_has_it(scene, title, &|_| frame, &mirror, &to_logical);
        assert_eq!(note, case["note"].as_str().unwrap(), "{}", case["kind"]);
        let want = case["follows"].as_array().map(|v| Follow {
            scale: f(&v[0]),
            start: (f(&v[1]), f(&v[2])),
            corner: (v[3].as_i64().unwrap(), v[4].as_i64().unwrap()),
        });
        assert_eq!(follows, want, "{note}");
        let a = &case["area"];
        let area = (a[0].as_i64().unwrap(), a[1].as_i64().unwrap(), a[2].as_i64().unwrap(), a[3].as_i64().unwrap());
        let size = (mirror.width, mirror.height);
        let (scale, offset) = fit(area, size, follows.as_ref());
        assert_eq!(vec![scale, offset.0, offset.1], case["fit"].as_array().unwrap().iter().map(f).collect::<Vec<_>>());
        let (scale, offset) = fit(area, size, None);
        assert_eq!(vec![scale, offset.0, offset.1], case["plain_fit"].as_array().unwrap().iter().map(f).collect::<Vec<_>>());
        let point = (case["point"][0].as_i64().unwrap(), case["point"][1].as_i64().unwrap());
        let drawn = to_window(point, area, size, follows.as_ref());
        assert_eq!(vec![drawn.0, drawn.1], case["to_window"].as_array().unwrap().iter().map(f).collect::<Vec<_>>());
    }
}

#[test]
fn masked_names_and_status_words_match_python() {
    let data = golden();
    for pair in data["masked"].as_array().unwrap() {
        assert_eq!(masked_name(pair[0].as_str().unwrap()), pair[1].as_str().unwrap());
    }
    for state in Status::ALL {
        assert_eq!(state.words(), data["words"][state.key()].as_str().unwrap());
    }
}
