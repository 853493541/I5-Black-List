//! Round trips over made-up data: whatever the store saves opens to the same values and saves to the same bytes.

use data::store::py::{dumps, float_repr, loads};
use data::store::sounds::Scenes;
use data::store::text::{fold, SCENE_KEYS};
use data::store::{Clock, Combo, Entry, Like, Store};
use proptest::prelude::*;
use std::fs;

fn name() -> impl Strategy<Value = String> {
    prop::sample::select(vec!["示例坏人", "心动小鹿", "心动星星", "Bad", "Guy", "二号", "7", "ab"])
        .prop_flat_map(|a| prop::sample::select(vec!["", "1", "号", "X", "坏人"]).prop_map(move |b| format!("{a}{b}")))
}

fn text() -> impl Strategy<Value = String> {
    "[a-z 炸房开局就走，。\"\\\\\n\t]{0,20}"
}

fn scenes() -> impl Strategy<Value = Scenes> {
    (prop::sample::subsequence(SCENE_KEYS.to_vec(), 0..4), any::<bool>())
        .prop_map(|(keys, random)| Scenes { keys: keys.into_iter().map(String::from).collect(), random })
}

fn unique<T>(items: Vec<T>, key: impl Fn(&T) -> String) -> Vec<T> {
    let mut seen = Vec::new();
    items.into_iter().filter(|i| !seen.contains(&key(i)) && { seen.push(key(i)); true }).collect()
}

proptest! {
    #![proptest_config(ProptestConfig { cases: 64, ..ProptestConfig::default() })]

    #[test]
    fn saved_lists_open_the_same(
        entries in prop::collection::vec((name(), text(), prop::sample::subsequence(vec!["炸房", "贴脸", "挂机"], 0..3)), 0..6),
        likes in prop::collection::vec((name(), "[a-z鹿]{0,6}", text(), scenes()), 0..6),
        me in scenes(),
        hidden in any::<bool>(),
        theme in prop::sample::select(vec!["蓝色", "棕色", "紫色", "绿色", "红色"]),
    ) {
        let work = tempfile::tempdir().unwrap();
        let mut store = Store::open(Some(work.path().to_path_buf()), Clock::default());
        store.entries = unique(entries, |e| fold(&e.0)).into_iter().map(|(n, r, t)| Entry {
            name: n, reason: r.trim().to_string(), tags: t.into_iter().map(String::from).collect(), added_at: "2026-11-18T00:00:00+00:00".into(),
        }).collect();
        store.likes = unique(likes, |l| fold(&l.0)).into_iter().map(|(n, nick, r, s)| Like {
            name: n, nickname: nick, reason: r.trim().to_string(), added_at: String::new(), scenes: s,
        }).collect();
        if store.likes.len() >= 2 {
            store.combos = vec![Combo { names: vec![store.likes[0].name.clone(), store.likes[1].name.clone()], scenes: Scenes::default() }];
        }
        store.me = me;
        store.settings.names_hidden = hidden;
        store.settings.theme = theme.to_string();
        store.settings.welcomed = true;
        store.save_entries().unwrap();
        store.save_likes().unwrap();
        store.save_settings().unwrap();
        let bytes: Vec<Vec<u8>> = ["blacklist.json", "likes.json", "settings.json"].iter().map(|f| fs::read(work.path().join(f)).unwrap()).collect();
        let again = Store::open(Some(work.path().to_path_buf()), Clock::default());
        prop_assert_eq!(&again.entries, &store.entries);
        prop_assert_eq!(&again.likes, &store.likes);
        prop_assert_eq!(&again.combos, &store.combos);
        prop_assert_eq!(&again.me, &store.me);
        prop_assert_eq!(&again.settings, &store.settings);
        again.save_entries().unwrap();
        again.save_likes().unwrap();
        again.save_settings().unwrap();
        let after: Vec<Vec<u8>> = ["blacklist.json", "likes.json", "settings.json"].iter().map(|f| fs::read(work.path().join(f)).unwrap()).collect();
        prop_assert_eq!(after, bytes);
    }

    #[test]
    fn json_text_round_trips(s in "\\PC{0,30}", n in any::<i64>(), f in 0.0f64..86400.0) {
        let value = serde_json::json!({"s": s, "n": n, "f": f, "l": [s, {}], "e": []});
        let text = dumps(&value);
        prop_assert_eq!(loads(text.as_bytes()).unwrap(), value);
        prop_assert_eq!(float_repr(f).parse::<f64>().unwrap(), f);
    }
}

/// Python's own spellings of the numbers the files hold.
#[test]
fn floats_are_written_as_python_writes_them() {
    for (f, want) in [(1.0, "1.0"), (1.25, "1.25"), (0.1, "0.1"), (1e-5, "1e-05"), (1e16, "1e+16"), (123456.0, "123456.0"), (0.0001, "0.0001")] {
        assert_eq!(float_repr(f), want);
    }
}
