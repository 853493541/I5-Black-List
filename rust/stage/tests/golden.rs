//! Parity with the Python app on golden data it wrote (tools/rust_golden_stage.py).

use scenes::pyrand::PyRandom;
use serde_json::Value;
use stage::clock::{duration, READY_S, TICK_MS, WARMED};
use stage::geom::{sample_stage, Placement};
use stage::pick::{choose, Choice, Picker, REPLACED, SCENES};

fn golden() -> Value {
    serde_json::from_str(include_str!("golden/stage.json")).expect("golden json")
}

fn choice(v: &Value) -> Choice {
    match v {
        Value::String(s) => Choice::One(s.clone()),
        Value::Array(list) => Choice::Some(list.iter().map(|k| k.as_str().unwrap().to_string()).collect()),
        _ => panic!("choice {v}"),
    }
}

fn floats(v: &Value) -> Vec<f64> {
    v.as_array().unwrap().iter().map(|x| x.as_f64().unwrap()).collect()
}

fn close(a: &[f64], b: &[f64], what: &str) {
    assert_eq!(a.len(), b.len(), "{what}");
    for (x, y) in a.iter().zip(b) {
        assert!((x - y).abs() < 1e-9, "{what}: {a:?} vs {b:?}");
    }
}

#[test]
fn scenes_their_lengths_and_replacements() {
    let g = golden();
    let scenes = g["scenes"].as_array().unwrap();
    assert_eq!(scenes.len(), SCENES.len());
    for (s, (key, name)) in scenes.iter().zip(SCENES) {
        assert_eq!(s["key"], key);
        assert_eq!(s["name"], name);
        assert_eq!(s["duration"].as_f64().unwrap(), duration(key), "{key}");
    }
    // Module-level warm (made ahead) is lyre's; claw and lyre both make theirs before playing.
    assert!(scenes.iter().filter(|s| s["warm"] == true).all(|s| WARMED.contains(&s["key"].as_str().unwrap())));
    let replaced = g["replaced"].as_object().unwrap();
    assert_eq!(replaced.len(), REPLACED.len());
    for (old, new) in REPLACED {
        assert_eq!(replaced[old], new);
    }
    assert_eq!(g["tick_ms"].as_u64().unwrap(), TICK_MS);
    assert_eq!(g["ready_s"].as_f64().unwrap(), READY_S);
}

#[test]
fn choose_matches_python_draw_for_draw() {
    let g = golden();
    let cases = g["choose"].as_array().unwrap();
    for case in cases {
        let mut rng = PyRandom::new(case["seed"].as_u64().unwrap() as u32);
        let c = choice(&case["choice"]);
        let last = case["last"].as_str().unwrap();
        let ours: Vec<String> = (0..6).map(|_| choose(&c, last, &mut rng)).collect();
        let theirs: Vec<&str> = case["picks"].as_array().unwrap().iter().map(|p| p.as_str().unwrap()).collect();
        assert_eq!(ours, theirs, "{case}");
    }
    assert_eq!(cases.len(), 240);
}

#[test]
fn picker_matches_love_border() {
    let g = golden();
    for run in g["picker"].as_array().unwrap() {
        let mut p = Picker::new(run["seed"].as_u64().unwrap() as u32);
        let mut got = Vec::new();
        for op in run["ops"].as_array().unwrap() {
            match op[0].as_str().unwrap() {
                "choice" => p.choice = choice(&op[1]),
                "pick" => got.push(p.pick()),
                "heard" => p.heard(op[1].as_str().unwrap()),
                "draw_again" => p.draw_again(),
                "play" => {
                    let scene = p.pick();
                    if !scene.is_empty() {
                        p.last = scene;
                    }
                }
                other => panic!("op {other}"),
            }
        }
        let theirs: Vec<&str> = run["picks"].as_array().unwrap().iter().map(|p| p.as_str().unwrap()).collect();
        assert_eq!(got, theirs, "{run}");
    }
}

#[test]
fn stage_geometry_matches_python() {
    let g = golden();
    for case in g["gaps"].as_array().unwrap() {
        let int4 = |v: &Value| -> [i32; 4] {
            let f = floats(v);
            [f[0] as i32, f[1] as i32, f[2] as i32, f[3] as i32]
        };
        let badge = floats(&case["badge"]);
        let seats: Vec<[f64; 4]> = case["seats"].as_array().unwrap().iter().map(|s| floats(s).try_into().unwrap()).collect();
        let place = Placement { area: int4(&case["area"]), keep_clear: int4(&case["keep"]), badge: Some([badge[0] as i32, badge[1] as i32]), seats };
        let stage = place.stage();
        close(&stage.gap, &floats(&case["gap"]), "gap");
        close(&[stage.unit()], &[case["unit"].as_f64().unwrap()], "unit");
        close(&stage.heart(), &floats(&case["heart"]), "heart");
        let names: Vec<f64> = stage.names().concat();
        let theirs: Vec<f64> = case["names"].as_array().unwrap().iter().flat_map(floats).collect();
        close(&names, &theirs, "names");
        let bare = stage::geom::Stage::new(stage.width, stage.height, stage.gap);
        close(&bare.heart(), &floats(&case["bare_heart"]), "bare heart");
        let theirs: Vec<f64> = case["bare_names"].as_array().unwrap().iter().flat_map(floats).collect();
        close(&bare.names().concat(), &theirs, "layout names");
    }
    for s in g["samples"].as_array().unwrap() {
        let size = floats(&s["size"]);
        let stage = sample_stage(size[0], size[1]);
        close(&stage.gap, &floats(&s["gap"]), "sample gap");
        close(&stage.badge.unwrap(), &floats(&s["badge"]), "sample badge");
        close(&[stage.unit()], &[s["unit"].as_f64().unwrap()], "sample unit");
    }
}
