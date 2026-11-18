//! The Rust import gives exactly what the Python app gives, on every golden case (tools/rust_golden_import.py).

use data::import::guests::{lobby_choice, lobby_scene, members, ticked_here, Choice};
use data::import::{names, plan_import, read_paste, suggest_tags, text, with_tags, Combo, Entry, Scenes};
use serde_json::Value;

fn golden(name: &str) -> Value {
    let path = format!("{}/tests/golden/import/{name}", env!("CARGO_MANIFEST_DIR"));
    serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap()
}

fn strings(value: &Value) -> Vec<String> {
    value.as_array().unwrap().iter().map(|v| v.as_str().unwrap().to_string()).collect()
}

fn s(value: &Value) -> &str {
    value.as_str().unwrap()
}

fn entries(value: &Value) -> Vec<Entry> {
    let list = value.as_array().unwrap();
    list.iter()
        .map(|e| Entry { name: s(&e["name"]).into(), reason: s(&e["reason"]).into(), tags: strings(&e["tags"]), ..Entry::default() })
        .collect()
}

fn check(failures: &mut Vec<String>, what: &str, input: &Value, got: Value, want: &Value) {
    if &got != want {
        failures.push(format!("{what} {input}\n  got  {got}\n  want {want}"));
    }
}

fn report(failures: Vec<String>, total: usize) {
    let shown: Vec<&String> = failures.iter().take(15).collect();
    assert!(failures.is_empty(), "{} of {total} differ:\n{}", failures.len(), shown.iter().map(|f| f.as_str()).collect::<Vec<_>>().join("\n"));
}

#[test]
fn fold_and_clean_match_python() {
    let cases = golden("fold.json");
    let mut failures = Vec::new();
    for case in cases.as_array().unwrap() {
        let input = &case["text"];
        check(&mut failures, "fold", input, Value::from(text::fold(s(input))), &case["fold"]);
        check(&mut failures, "clean", input, Value::from(text::clean_stored_name(s(input))), &case["clean"]);
    }
    report(failures, cases.as_array().unwrap().len());
}

#[test]
fn read_paste_matches_python() {
    let cases = golden("read.json");
    let mut failures = Vec::new();
    for case in cases.as_array().unwrap() {
        let got: Vec<Value> = read_paste(s(&case["text"]), &strings(&case["catalog"]))
            .into_iter()
            .map(|(name, tags, reason)| serde_json::json!([name, tags, reason]))
            .collect();
        check(&mut failures, "read", &serde_json::json!([case["text"], case["catalog"]]), Value::from(got), &case["read"]);
    }
    report(failures, cases.as_array().unwrap().len());
}

#[test]
fn plan_import_matches_python() {
    let cases = golden("plan.json");
    let mut failures = Vec::new();
    for case in cases.as_array().unwrap() {
        let rows = plan_import(s(&case["text"]), &entries(&case["entries"]), &strings(&case["catalog"]), &entries(&case["elsewhere"]));
        let got: Vec<Value> = rows
            .into_iter()
            .map(|r| {
                serde_json::json!({"name": r.name, "tags": r.tags, "reason": r.reason, "status": r.status.key(),
                    "target": r.target, "checked": r.checked})
            })
            .collect();
        let input = serde_json::json!([case["text"], case["entries"], case["elsewhere"], case["catalog"]]);
        check(&mut failures, "plan", &input, Value::from(got), &case["rows"]);
    }
    report(failures, cases.as_array().unwrap().len());
}

#[test]
fn suggest_tags_match_python() {
    let all = golden("suggest.json");
    let mut failures = Vec::new();
    let record = |r: &Value| (s(&r[0]).to_string(), strings(&r[1]), s(&r[2]).to_string(), r[3].as_i64().unwrap());
    for case in all["suggest"].as_array().unwrap() {
        let rows: Vec<_> = case["rows"].as_array().unwrap().iter().map(record).collect();
        let found = suggest_tags(&rows, &strings(&case["catalog"]));
        let got: Vec<Value> =
            found.iter().map(|f| serde_json::json!({"tag": f.tag, "existing": f.existing, "rows": f.rows})).collect();
        check(&mut failures, "suggest", &case["rows"], Value::from(got), &case["found"]);
        let tagged: Vec<Value> = with_tags(&rows, &found).into_iter().map(|(n, t, r, g)| serde_json::json!([n, t, r, g])).collect();
        check(&mut failures, "with_tags", &case["rows"], Value::from(tagged), &case["tagged"]);
    }
    assert_eq!(strings(&all["game_words"]), data::import::GAME_WORDS.to_vec());
    for (word, want) in all["is_game_word"].as_object().unwrap() {
        assert_eq!(data::import::is_game_word(word), want.as_bool().unwrap(), "{word}");
    }
    report(failures, all["suggest"].as_array().unwrap().len());
}

fn scenes(value: &Value) -> Scenes {
    Scenes { keys: strings(&value["keys"]), random: value["random"].as_bool().unwrap() }
}

fn choice(value: Choice) -> Value {
    match value {
        Choice::One(key) => Value::from(key),
        Choice::Many(keys) => Value::from(keys),
    }
}

#[test]
fn guests_match_python() {
    let cases = golden("guests.json");
    let mut failures = Vec::new();
    for case in cases.as_array().unwrap() {
        let likes: Vec<Entry> = case["likes"]
            .as_array()
            .unwrap()
            .iter()
            .map(|l| Entry { name: s(&l["name"]).into(), nickname: s(&l["nickname"]).into(), scenes: scenes(&l["scenes"]), ..Entry::default() })
            .collect();
        let combos: Vec<Combo> =
            case["combos"].as_array().unwrap().iter().map(|c| Combo { names: strings(&c["names"]), scenes: scenes(&c["scenes"]) }).collect();
        let present: Vec<Entry> = case["present"].as_array().unwrap().iter().map(|p| Entry::new(s(&p["name"]), "", &[])).collect();
        let me = scenes(&case["me"]);
        let blacklisted = case["blacklisted"].as_bool().unwrap();
        check(&mut failures, "lobby_choice", case, choice(lobby_choice(&likes, &combos, &present, "classic")), &case["lobby_choice"]);
        let (who, picked) = lobby_scene(&likes, &combos, &present, &me, blacklisted);
        check(&mut failures, "lobby_scene", case, serde_json::json!([who, choice(picked)]), &case["lobby_scene"]);
        let ticked: Vec<Vec<String>> = likes.iter().map(|l| ticked_here(&l.scenes)).collect();
        check(&mut failures, "ticked", case, serde_json::json!(ticked), &case["ticked"]);
        let shown: Vec<Value> = combos.iter().map(|c| serde_json::json!(members(c, &likes))).collect();
        check(&mut failures, "members", case, Value::from(shown), &case["members"]);
    }
    report(failures, cases.as_array().unwrap().len());
}

#[test]
fn names_match_python() {
    let all = golden("names.json");
    assert_eq!(all["app_name"], names::APP_NAME);
    assert_eq!(strings(&all["launchers"]), names::LAUNCHERS.to_vec());
    assert_eq!(strings(&all["processes"]), names::PROCESSES.to_vec());
    let dir = std::env::temp_dir().join(format!("import-names-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    assert_eq!(names::launcher_in(&dir), None);
    std::fs::write(dir.join(names::LAUNCHERS[1]), b"").unwrap();
    assert_eq!(names::launcher_in(&dir), Some(dir.join(names::LAUNCHERS[1])));
    std::fs::write(dir.join(names::LAUNCHERS[0]), b"").unwrap();
    assert_eq!(names::launcher_in(&dir), Some(dir.join(names::LAUNCHERS[0])));
    std::fs::remove_dir_all(&dir).unwrap();
}
