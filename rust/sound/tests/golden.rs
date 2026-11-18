//! Parity with the Python app on the golden data tools/rust_golden_sound.py writes from its own code.

use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

use serde_json::Value;
use sound::music::{Output, ThemeMusic};
use sound::trim::{self, Grip, Trim};
use sound::{decode, level, render, save_clip, song_name, tune_seconds, Clip, Recorder};

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")
}
fn golden_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/golden")
}
fn assets() -> PathBuf {
    root().join("blacklist_detect/assets")
}
fn golden() -> Value {
    serde_json::from_str(&std::fs::read_to_string(golden_dir().join("sound.json")).unwrap()).unwrap()
}
fn tmp(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("sound-golden-{}-{name}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    dir
}

fn fnv(samples: &[i16]) -> String {
    let mut h: u64 = 0xcbf29ce484222325;
    for s in samples {
        for b in s.to_le_bytes() {
            h = (h ^ u64::from(b)).wrapping_mul(0x100000001b3);
        }
    }
    format!("{h:016x}")
}

fn read16(path: &Path) -> Vec<i16> {
    hound::WavReader::open(path).unwrap().into_samples::<i16>().map(Result::unwrap).collect()
}

/// Same length, and the same samples: exactly (fnv), or else every 997th within tol. Returns whether exact.
fn same(what: &str, got: &[i16], want: &Value, tol: i32) -> bool {
    assert_eq!(got.len() as u64, want["len"].as_u64().unwrap(), "{what}: length");
    if fnv(got) == want["fnv"].as_str().unwrap() {
        return true;
    }
    for (i, w) in want["every"].as_array().unwrap().iter().enumerate() {
        let diff = (i32::from(got[i * 997]) - w.as_i64().unwrap() as i32).abs();
        assert!(diff <= tol, "{what}: sample {} off by {diff}", i * 997);
    }
    eprintln!("{what}: within {tol}, not exact");
    false
}

fn f(v: &Value) -> f64 {
    v.as_f64().unwrap()
}

#[test]
fn tunes_table_matches() {
    let g = golden();
    let want = g["tunes"].as_object().unwrap();
    assert_eq!(want.len(), sound::TUNES.len());
    for (key, file) in sound::TUNES {
        assert_eq!(want[key].as_str().unwrap(), file, "{key}");
    }
}

#[test]
fn assets_decode_scale_and_keep_as_python_does() {
    let g = golden();
    let dir = tmp("assets");
    for (key, want) in g["assets"].as_object().unwrap() {
        let path = sound::tunes::tune_path(&assets(), key).unwrap();
        assert!((tune_seconds(Some(&path)) - f(&want["seconds"])).abs() < 1e-12, "{key}");
        let d = decode(&path).unwrap();
        assert!(same(&format!("{key} decoded"), &d.samples, &want["decoded"], 0), "{key}: decode is exact");
        assert_eq!(d.cut, want["cut"].as_bool().unwrap());
        let peaks: Vec<f64> = want["peaks560"].as_array().unwrap().iter().map(f).collect();
        assert_eq!(trim::peaks(&d.samples, 560), peaks, "{key} peaks");
        let rolling = level::rolling_gain(&d.samples);
        let want_rolling: Vec<f64> = want["rolling"].as_array().unwrap().iter().map(f).collect();
        assert_eq!(rolling.len(), want_rolling.len());
        for (a, b) in rolling.iter().zip(&want_rolling) {
            assert!((a - b).abs() <= 1e-12 * b.abs(), "{key} rolling {a} {b}");
        }
        let part = level::part_gain(&d.samples, 1.0, 2.0);
        assert_eq!(part.is_some(), !want["part_gain"].is_null());
        if let Some(p) = part {
            assert!((p - f(&want["part_gain"])).abs() <= 1e-12 * p);
        }
        for (label, want_scaled) in want["scaled"].as_object().unwrap() {
            let parts: Vec<&str> = label.split('/').collect();
            let seconds = parts[1].parse::<f64>().ok();
            let clip = render(&path, parts[0].parse().unwrap(), seconds, parts[2].parse().unwrap()).unwrap();
            assert!(same(&format!("{key} scaled {label}"), &clip.samples, want_scaled, 0), "{key} {label}: exact");
        }
        let kept = save_clip(&d, key, &dir, 0.7, 3.2).unwrap();
        same(&format!("{key} clip"), &read16(&kept.path), &want["clip"], 1);
        assert_eq!(kept.start_s, f(&want["clip"]["start_s"]));
        assert_eq!(kept.length_s, f(&want["clip"]["length_s"]));
        let rest = level::save_rest(&d, 1.3, &dir.join("rest.wav"), 60, None).unwrap();
        same(&format!("{key} rest"), &read16(&rest), &want["rest"], 1);
    }
}

#[test]
fn made_up_sounds_decode_keep_and_refuse_as_python_does() {
    let g = golden();
    let dir = tmp("made");
    for (name, want) in g["made_up"].as_object().unwrap() {
        let got = decode(&golden_dir().join(name));
        if let Some(error) = want.get("error") {
            assert_eq!(got.unwrap_err().message(), error.as_str().unwrap(), "{name}");
            continue;
        }
        let d = got.unwrap();
        assert!(same(&format!("{name} decoded"), &d.samples, &want["decoded"], 0), "{name}: decode is exact");
        assert_eq!(d.cut, want["cut"].as_bool().unwrap());
        let want_rolling: Vec<f64> = want["rolling"].as_array().unwrap().iter().map(f).collect();
        let rolling = level::rolling_gain(&d.samples);
        assert_eq!(rolling.len(), want_rolling.len(), "{name} rolling length");
        for (a, b) in rolling.iter().zip(&want_rolling) {
            assert!((a - b).abs() <= 1e-12 * b.abs(), "{name} rolling {a} {b}");
        }
        for (label, (start, length)) in [("a", (0.0, 5.0)), ("b", (2.5, 9.0)), ("c", (6.9, 1.0)), ("d", (0.3, 0.04))] {
            let want_clip = &want[format!("clip_{label}")];
            match save_clip(&d, "k", &dir, start, length) {
                Ok(kept) => {
                    same(&format!("{name} clip {label}"), &read16(&kept.path), want_clip, 1);
                    assert_eq!(kept.length_s, f(&want_clip["length_s"]));
                }
                Err(e) => assert_eq!(e.message(), want_clip["error"].as_str().unwrap_or("kept"), "{name} {label}"),
            }
        }
        for vol in [100, 35] {
            let rest = level::save_rest(&d, 0.5, &dir.join("rest.wav"), vol, None).unwrap();
            same(&format!("{name} rest {vol}"), &read16(&rest), &want[format!("rest_{vol}")], 1);
        }
    }
}

#[test]
fn refusals_and_song_names_match() {
    let g = golden();
    let dir = tmp("refuse");
    assert_eq!(decode(&dir.join("nope.mp3")).unwrap_err().message(), g["errors"]["missing"].as_str().unwrap());
    std::fs::write(dir.join("empty.mp3"), b"").unwrap();
    assert_eq!(decode(&dir.join("empty.mp3")).unwrap_err().message(), g["errors"]["empty"].as_str().unwrap());
    for n in [1, 2, 4] {
        std::fs::write(dir.join(format!("ice-{n}.wav")), b"x").unwrap();
    }
    let names = [song_name("ice", &dir), song_name("stars", &dir)];
    assert_eq!(names.as_slice(), g["song_name"].as_array().unwrap().iter().map(|v| v.as_str().unwrap()).collect::<Vec<_>>());
}

#[test]
fn other_formats_decode_close_to_what_windows_gave_python() {
    let g = golden();
    for (name, want) in g["qt_decoded"].as_object().unwrap() {
        let got = decode(&root().join("tests/fixtures/sounds").join(name));
        if let Some(error) = want.get("error") {
            assert_eq!(got.unwrap_err().message(), error.as_str().unwrap(), "{name}");
            continue;
        }
        let d = got.unwrap_or_else(|e| panic!("{name}: {e}"));
        let len = want["len"].as_i64().unwrap();
        let rms = (d.samples.iter().map(|&s| f64::from(s).powi(2)).sum::<f64>() / d.samples.len() as f64).sqrt();
        let peak = d.samples.iter().map(|&s| i32::from(s).abs()).max().unwrap();
        eprintln!("{name}: {} samples (Python {len}), rms {rms:.1} ({:.1}), peak {peak} ({})", d.samples.len(), f(&want["rms"]), want["peak"]);
        assert!((d.samples.len() as i64 - len).abs() <= 2048, "{name}: length");
        assert!((rms / f(&want["rms"]) - 1.0).abs() < 0.03, "{name}: rms");
        assert!((f64::from(peak) / f(&want["peak"]) - 1.0).abs() < 0.05, "{name}: peak");
    }
}

struct Fnvs(Arc<Mutex<Vec<Option<String>>>>);
impl Output for Fnvs {
    fn play(&mut self, clip: Option<Clip>) {
        self.0.lock().unwrap().push(clip.map(|c| fnv(&c.samples)));
    }
}

#[test]
fn theme_music_plays_what_python_plays() {
    let g = golden();
    let music_g = &g["music"];
    let volumes = music_g["volumes"].clone();
    let own = golden_dir().join("loud.wav");
    let gone = std::env::temp_dir().join("sound-golden-gone.wav");
    let (own2, gone2) = (own.clone(), gone.clone());
    let clock = Arc::new(Mutex::new(0.0f64));
    let c2 = clock.clone();
    let played = Arc::new(Mutex::new(Vec::new()));
    let sounds = move |scene: &str| {
        let song = match scene {
            "neon" => Some(own2.clone()),
            "lace" => Some(gone2.clone()),
            _ => None,
        };
        (song, volumes.get(scene).and_then(Value::as_i64).unwrap_or(100) as i32)
    };
    let mut m = ThemeMusic::new(Box::new(Fnvs(played.clone())), Box::new(move || *c2.lock().unwrap()), assets(), Some(Box::new(sounds)));
    let names = |v: &Value| v.as_array().unwrap().iter().map(|s| s.as_str().unwrap().to_string()).collect::<Vec<_>>();
    for step in music_g["ops"].as_array().unwrap() {
        let op = step["op"].as_array().unwrap();
        let before = played.lock().unwrap().len();
        let got: Value = match op[0].as_str().unwrap() {
            "tick" => {
                *clock.lock().unwrap() += f(&op[1]);
                Value::Null
            }
            "lobby" => m.lobby(&names(&op[1]), op[2].as_str().unwrap(), op[3].as_bool().unwrap()).into(),
            "mine" => m.mine(&names(&op[1]), op[2].as_str().unwrap(), op[3].as_bool().unwrap()).into(),
            "ungreet" => {
                m.ungreet();
                Value::Null
            }
            "preview" => m.preview(op[1].as_str().unwrap(), f(&op[2])).into(),
            "taste" => m.taste(op[1].as_str().unwrap()).into(),
            "song" => m.song(op[1].as_str().unwrap(), (op[2] == "own").then_some(own.as_path()), f(&op[3])).into(),
            "trial" => m.trial(&own, op[2].as_str().unwrap()).into(),
            "stop" => {
                m.stop();
                Value::Null
            }
            _ => {
                m.muted = op[1].as_bool().unwrap();
                Value::Null
            }
        };
        assert_eq!(got, step["got"], "{op:?}");
        let now: Vec<Value> = played.lock().unwrap()[before..].iter().map(|p| p.clone().map_or(Value::Null, Value::from)).collect();
        assert_eq!(&now, step["played"].as_array().unwrap(), "{op:?} played");
    }
}

#[test]
fn trim_rules_match() {
    let g = golden();
    let t = &g["trim"];
    for (v, want) in t["clock"].as_object().unwrap() {
        assert_eq!(trim::clock(v.parse().unwrap()), want.as_str().unwrap(), "{v}");
    }
    let samples: Vec<i16> = t["peaks"]["samples"].as_array().unwrap().iter().map(|v| v.as_i64().unwrap() as i16).collect();
    let floats = |v: &Value| v.as_array().unwrap().iter().map(f).collect::<Vec<_>>();
    assert_eq!(trim::peaks(&samples, 560), floats(&t["peaks"]["560"]));
    assert_eq!(trim::peaks(&samples, 7), floats(&t["peaks"]["7"]));
    assert_eq!(trim::peaks(&samples[..5], 9), floats(&t["peaks"]["short"]));
    assert_eq!(trim::peaks(&[], 3), floats(&t["peaks"]["none"]));
    let w = &t["waveform"];
    let mut trim = Trim::new(12300, 1000, trim::LIMIT_S);
    assert_eq!(trim.duration, f(&w["duration"]));
    assert_eq!(trim.limit, f(&w["limit"]));
    for step in w["steps"].as_array().unwrap() {
        let (a, b) = (f(&step["a"]), f(&step["b"]));
        match step["op"].as_str().unwrap() {
            "set" => trim.set_selection(a, b),
            "nudge" => trim.nudge(a),
            "cut" => trim.cut(a),
            "drag_left" => trim.drag(Grip::Left, a),
            _ => trim.drag(Grip::Right, a),
        };
        assert_eq!((trim.start, trim.length), (f(&step["start"]), f(&step["length"])), "{step}");
        assert_eq!(trim.x_of(trim.start), f(&step["x_of"]));
        assert_eq!(trim.time_at(123.0), f(&step["time_at"]));
        for (x, want) in step["grips"].as_object().unwrap() {
            let got = match trim.grip_at(x.parse().unwrap()) {
                Grip::Left => "left",
                Grip::Right => "right",
                Grip::Seek => "seek",
            };
            assert_eq!(got, want.as_str().unwrap(), "x {x} at {step}");
        }
    }
    for (time, want) in t["levels"].as_object().unwrap() {
        let got = trim::wave_levels(time.parse().unwrap());
        for (a, b) in got.iter().zip(floats(want)) {
            assert!((a - b).abs() < 1e-12, "levels at {time}");
        }
    }
}

#[test]
fn recorder_is_silent_and_nothing_heard_without_allow_sound() {
    let rec = Recorder::default();
    let mut player = sound::Player::new(Box::new(rec.clone()), Box::new(|| 0.0), assets(), None);
    assert_eq!(player.play_tune("ice"), "ice");
    // Not allowed (tests never call allow_sound): the gate passes nothing on, not even a stop.
    assert!(rec.0.lock().unwrap().is_empty());
    assert!(!player.play_alert(sound::Alert::Blacklist));
}
