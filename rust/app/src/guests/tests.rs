//! The 嘉宾 page against golden.json, which golden_guests.py writes from the Python LikesPage itself.

use super::model::{scenes_said, Lists, MenuItem, Page, RowKind};
use super::*;
use data::store::scans::{Scan, Seat};
use data::store::sounds::Scenes;
use data::store::{Combo, Like};
use serde_json::Value;

const GOLDEN: &str = include_str!("golden.json");

fn scenes(item: &Value) -> Scenes {
    let keys: Vec<String> = item["scenes"].as_array().unwrap().iter().map(|k| k.as_str().unwrap().to_string()).collect();
    Scenes::of(&keys, item["random"].as_bool().unwrap())
}

struct Case {
    likes: Vec<Like>,
    combos: Vec<Combo>,
    me: Scenes,
    player_name: String,
    scans: Vec<Scan>,
}

fn case(item: &Value) -> Case {
    let text = |v: &Value| v.as_str().unwrap().to_string();
    Case {
        likes: item["likes"]
            .as_array()
            .unwrap()
            .iter()
            .map(|l| Like {
                name: text(&l["name"]),
                nickname: text(&l["nickname"]),
                reason: text(&l["reason"]),
                added_at: String::new(),
                scenes: scenes(l),
            })
            .collect(),
        combos: item["combos"]
            .as_array()
            .unwrap()
            .iter()
            .map(|c| Combo { names: c["names"].as_array().unwrap().iter().map(text).collect(), scenes: scenes(c) })
            .collect(),
        me: scenes(&item["me"]),
        player_name: text(&item["player_name"]),
        scans: item["scans"]
            .as_array()
            .unwrap()
            .iter()
            .map(|s| Scan {
                at: text(&s["at"]),
                elapsed: Value::Null,
                names: s["names"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .enumerate()
                    .map(|(i, n)| Seat { seat: i as i64 + 1, name: text(&n[0]), unclear: n[1].as_bool().unwrap() })
                    .collect(),
            })
            .collect(),
    }
}

fn lists(case: &Case) -> Lists<'_> {
    Lists { likes: &case.likes, combos: &case.combos, me: &case.me, player_name: &case.player_name, scans: &case.scans }
}

fn golden() -> Value {
    serde_json::from_str(GOLDEN).unwrap()
}

fn now() -> chrono::DateTime<chrono::FixedOffset> {
    chrono::DateTime::parse_from_rfc3339(golden()["now"].as_str().unwrap()).unwrap()
}

#[test]
fn every_page_matches_python() {
    let all = golden();
    let mut checked = 0;
    for item in all["cases"].as_array().unwrap() {
        let case = case(item);
        assert_eq!(model::share_likes(&case.likes), item["share"].as_str().unwrap());
        for state in item["states"].as_array().unwrap() {
            let query = state["query"].as_str().unwrap();
            let page = Page::build(&lists(&case), query, now());
            let at = format!("{} / 「{query}」", item["kind"]);
            for (flag, mine) in [
                ("table", page.show_table),
                ("toolbar", page.show_toolbar),
                ("search", page.show_search),
                ("more", page.show_more),
                ("add_combo_enabled", page.add_combo_enabled),
                ("empty_buttons", page.empty_buttons),
                ("drag", page.drag),
            ] {
                assert_eq!(state[flag].as_bool().unwrap(), mine, "{flag} at {at}");
            }
            assert_eq!(state["empty_text"].as_str().unwrap(), page.empty_text, "{at}");
            let rows = state["rows"].as_array().unwrap();
            assert_eq!(rows.len(), page.rows.len(), "rows at {at}");
            for (want, row) in rows.iter().zip(&page.rows) {
                let (kind, place) = match row.kind {
                    RowKind::Me => ("me", -1),
                    RowKind::Combo(n) => ("combo", n as i64),
                    RowKind::Guest(i) => ("like", i as i64),
                };
                assert_eq!((want["kind"].as_str().unwrap(), want["place"].as_i64().unwrap()), (kind, place), "{at}");
                let cells: Vec<&str> = want["cells"].as_array().unwrap().iter().map(|c| c.as_str().unwrap()).collect();
                let nickname = if kind == "like" { row.nickname.as_str() } else { "" };
                assert_eq!(cells, [row.name.as_str(), nickname, &row.scene, &row.reason, &row.met], "{at}");
                let dots: Vec<&str> = want["dots"].as_array().unwrap().iter().map(|c| c.as_str().unwrap()).collect();
                assert_eq!(dots, row.dots, "{at}");
                let people: Vec<(String, bool)> = want["people"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(|p| (p[0].as_str().unwrap().to_string(), p[1].as_bool().unwrap()))
                    .collect();
                assert_eq!(people, row.people, "{at}");
                let menu: Vec<&str> = want["menu"].as_array().unwrap().iter().map(|c| c.as_str().unwrap()).collect();
                assert_eq!(menu, row.menu.iter().map(|m| m.label()).collect::<Vec<_>>(), "{at}");
                checked += 1;
            }
        }
    }
    assert!(checked > 30, "only {checked} rows checked");
}

#[test]
fn scene_words_match_python() {
    for item in golden()["said"].as_array().unwrap() {
        // Python's Scenes keeps keys as given; the store's Scenes cleans them the same way scene_dots reads them.
        let keys: Vec<String> = item["scenes"].as_array().unwrap().iter().map(|k| k.as_str().unwrap().to_string()).collect();
        let scenes = Scenes { keys, random: item["random"].as_bool().unwrap() };
        assert_eq!(scenes_said(&scenes), item["said"].as_str().unwrap());
        let dots: Vec<&str> = item["dots"].as_array().unwrap().iter().map(|c| c.as_str().unwrap()).collect();
        assert_eq!(model::scene_dots(&scenes), dots);
    }
}

#[test]
fn clicks_keys_and_menus_ask_for_the_right_action() {
    let all = golden();
    let list = case(&all["cases"][1]);
    let page = Page::build(&lists(&list), "", now());
    // Rows: 我, three 组合, then 棉花糖 (4), 柠檬汽水 (3), 一起开黑的朋友 (2), 心动星星 (1), 心动小鹿 (0).
    assert_eq!(on_click(&page, 0), Some(GuestAction::EditMe));
    assert_eq!(on_click(&page, 2), Some(GuestAction::EditCombo(1)));
    assert_eq!(on_click(&page, 5), Some(GuestAction::EditGuest(3)));
    assert_eq!(on_key(&page, 0, RowKey::Delete), None);
    assert_eq!(on_key(&page, 1, RowKey::Delete), Some(GuestAction::DeleteCombo(0)));
    assert_eq!(on_key(&page, 8, RowKey::Delete), Some(GuestAction::DeleteGuest(0)));
    assert_eq!(on_key(&page, 8, RowKey::Enter), Some(GuestAction::EditGuest(0)));
    let top = page.rows[5].menu.iter().position(|m| *m == MenuItem::ToTop).unwrap();
    assert_eq!(on_menu(&page, 5, top), Some(GuestAction::ToTop(3)));
    assert_eq!(on_menu(&page, 5, 1), Some(GuestAction::CopyName(3)));
    assert_eq!(on_menu(&page, 5, top + 1), None);
    assert_eq!(on_menu(&page, 3, 2), Some(GuestAction::DeleteCombo(2)));
    assert_eq!(on_move(&page, 5, 8), Some(GuestAction::Move { index: 3, to: 0 }));
    assert_eq!(on_move(&page, 5, 2), None);
    assert_eq!(on_add_combo(&page), GuestAction::AddCombo);
    assert_eq!(on_more(&page, 1), Some(GuestAction::ClearList));
    // A search: no dragging, and the empty list's 添加组合 says why it waits.
    let searched = Page::build(&lists(&list), "星星", now());
    assert_eq!(on_move(&searched, 2, 3), None);
    let empty = case(&all["cases"][0]);
    let none = Page::build(&lists(&empty), "", now());
    assert_eq!(on_add_combo(&none), GuestAction::Say(model::TOO_FEW.into()));
    assert_eq!(on_more(&none, 0), None);
}

/// Every state the page has, drawn without error, in light and dark at 150 %, into the temp folder.
#[test]
fn every_state_renders() {
    let all = golden();
    let list = case(&all["cases"][1]);
    let named = case(&all["cases"][2]);
    let empty = case(&all["cases"][0]);
    let shots = shots_lists();
    let pages = [
        ("rust-shots-list", Page::build(&lists(&shots), "", now()), false),
        ("rust-list", Page::build(&lists(&list), "", now()), false),
        ("rust-named", Page::build(&lists(&named), "", now()), false),
        ("rust-search", Page::build(&lists(&list), "星星", now()), false),
        ("rust-not-found", Page::build(&lists(&list), "没有这个人", now()), false),
        ("rust-empty", Page::build(&lists(&empty), "", now()), false),
        ("rust-list-dark", Page::build(&lists(&list), "", now()), true),
    ];
    let dir = std::env::temp_dir().join("guests-shots");
    let pictures = render::render(&dir, 1.5, &pages).unwrap();
    for (picture, (name, _, _)) in pictures.iter().zip(&pages) {
        // Not one flat colour: the page drew something.
        let first = &picture[..3];
        assert!(picture.chunks(3).any(|pixel| pixel != first), "{name} is blank");
    }
}

/// tools/ui_shots.py's normal data (_seed), for the pictures beside the Python page's.
fn shots_lists() -> Case {
    let like = |name: &str, nickname: &str, reason: &str, keys: &[&str], random: bool| Like {
        name: name.into(),
        nickname: nickname.into(),
        reason: reason.into(),
        added_at: String::new(),
        scenes: Scenes::of(&keys.iter().map(|k| k.to_string()).collect::<Vec<_>>(), random),
    };
    let seats = ["小林同学", "白日梦想家", "路过的猫", "一只团子", "夏天的风", "心动小鹿", "晚风吹过", "摸鱼大师", "示例坏人", "心动星星", "柠檬汽水", "棉花糖"];
    Case {
        likes: vec![
            like("心动小鹿", "小鹿", "声音好听", &["fluffy", "stars"], false),
            like("心动星星", "", "", &[], true),
            like("一起开黑的朋友", "", "每次都带我赢", &["cyber"], false),
        ],
        combos: vec![
            Combo { names: vec!["心动小鹿".into(), "心动星星".into()], scenes: Scenes::of(&["angel".into()], false) },
            Combo { names: vec!["心动星星".into(), "一起开黑的朋友".into()], scenes: Scenes::default() },
        ],
        me: Scenes::of(&["lace".into()], false),
        player_name: "测试主播".into(),
        scans: vec![Scan {
            at: golden()["now"].as_str().unwrap().into(),
            elapsed: Value::Null,
            names: seats
                .iter()
                .enumerate()
                .map(|(i, n)| Seat { seat: i as i64 + 1, name: n.to_string(), unclear: *n == "摸鱼大师" })
                .collect(),
        }],
    }
}
