//! The 黑名单 page against the Python app: its rows, tags, sort, toasts and undo, and every state rendered.

use std::collections::HashMap;

use chrono::{DateTime, FixedOffset};
use data::store::Entry;

use super::bind::{column_order, fit_columns, tag_row_layout};
use super::model::{self, Empty, SortColumn, View};
use super::ops::{self, Undo};
use super::render::{render, seeded};
use super::{collate, ListAction};

fn now() -> DateTime<FixedOffset> {
    DateTime::parse_from_rfc3339("2026-11-18T12:00:00+08:00").unwrap()
}

fn entry(name: &str, tags: &[&str], reason: &str) -> Entry {
    Entry { name: name.into(), reason: reason.into(), tags: tags.iter().map(|t| t.to_string()).collect(), added_at: String::new() }
}

fn names(rows: &[model::Row]) -> Vec<&str> {
    rows.iter().map(|row| row.name.as_str()).collect()
}

#[test]
fn masked_name_keeps_one_star_at_least() {
    assert_eq!(model::masked_name(""), "");
    assert_eq!(model::masked_name("示"), "示*");
    assert_eq!(model::masked_name("示例坏人"), "示***");
}

#[test]
fn zh_ago_as_python() {
    let cases = [
        ("2026-11-18T11:59:30+08:00", "刚刚"),
        ("2026-11-18T11:55:00+08:00", "5分钟前"),
        ("2026-11-18T01:00:00+00:00", "3小时前"),
        ("2026-11-16T12:00:00+08:00", "2天前"),
        ("2026-07-18T12:00:00+08:00", "4个月前"),
        ("2024-11-18T12:00:00+08:00", "2年前"),
        ("2026-11-18T09:00:00", "3小时前"),
        ("not a time", ""),
    ];
    for (stamp, want) in cases {
        assert_eq!(model::zh_ago(stamp, now()), want, "{stamp}");
    }
}

#[test]
fn search_tag_filter_and_empty_states() {
    let entries = vec![
        entry("示例坏人", &["炸房"], "开局就退"),
        entry("Night Owl", &["挂机"], "约好的车不来"),
        entry("夜猫子", &[], "AFK all game"),
    ];
    let met = HashMap::new();
    let mut view = View::default();
    assert_eq!(names(&model::rows(&entries, &met, &view, false, now())), ["示例坏人", "Night Owl", "夜猫子"]);
    // The name folds (case and marks drop out), tags and reasons match case-blind.
    for (query, want) in [("night-owl", vec!["Night Owl"]), ("挂机", vec!["Night Owl"]), ("afk", vec!["夜猫子"]), ("  开局 ", vec!["示例坏人"])] {
        view.search = query.into();
        assert_eq!(names(&model::rows(&entries, &met, &view, false, now())), want, "{query}");
    }
    view.search = "没有的人".into();
    assert_eq!(model::empty(3, 0, &view), Empty::NotFound("没有找到「没有的人」".into()));
    view.search.clear();
    view.tag = "炸房".into();
    assert_eq!(names(&model::rows(&entries, &met, &view, true, now())), ["示***"]);
    view.tag = "送人头".into();
    assert_eq!(model::empty(3, 0, &view).text(), "没有使用「送人头」标签的玩家");
    assert_eq!(model::empty(0, 0, &View::default()).text(), "黑名单还是空的");
    assert_eq!(model::empty(3, 1, &view), Empty::No);
}

#[test]
fn sorts_by_name_then_back_and_by_met_newest_first() {
    let entries = vec![entry("夜猫子", &[], ""), entry("abc", &[], ""), entry("阿狸", &[], ""), entry("示例坏人", &[], "")];
    let met: HashMap<usize, String> =
        [(0, "2026-11-18T10:00:00+08:00".to_string()), (3, "2026-11-17T10:00:00+08:00".to_string())].into();
    let mut view = View::default();
    view.click_sort(SortColumn::Name);
    assert_eq!(names(&model::rows(&entries, &met, &view, false, now())), ["阿狸", "示例坏人", "夜猫子", "abc"]);
    view.click_sort(SortColumn::Name);
    assert_eq!(names(&model::rows(&entries, &met, &view, false, now())), ["abc", "夜猫子", "示例坏人", "阿狸"]);
    view.click_sort(SortColumn::Met);
    let rows = model::rows(&entries, &met, &view, false, now());
    assert_eq!(names(&rows), ["夜猫子", "示例坏人", "abc", "阿狸"]);
    assert_eq!((rows[0].met.as_str(), rows[2].met.as_str(), rows[2].met_known), ("2小时前", model::NEVER_MET, false));
    view.click_sort(SortColumn::Met);
    assert_eq!(names(&model::rows(&entries, &met, &view, false, now())), ["示例坏人", "夜猫子", "abc", "阿狸"]);
}

#[test]
fn name_order_matches_qcollator() {
    let golden: Vec<String> = serde_json::from_str(include_str!("collate_golden.json")).unwrap();
    let mut ours = golden.clone();
    ours.reverse();
    ours.sort_by(|a, b| collate::compare(a, b));
    assert_eq!(ours, golden);
}

#[test]
fn tag_counts_and_remove_question() {
    let entries = vec![entry("a1", &["炸房", "挂机"], ""), entry("b1", &["挂机"], "")];
    let catalog: Vec<String> = ["炸房", "挂机", "送人头"].iter().map(|t| t.to_string()).collect();
    let rows = model::tag_rows(&entries, &catalog);
    assert_eq!(rows, [("".into(), 2), ("炸房".into(), 1), ("挂机".into(), 2), ("送人头".into(), 0)]);
    assert_eq!(model::remove_tag_question(&entries, "挂机"), "「挂机」2 人正在使用，是否确定删除？");
    assert_eq!(model::remove_tag_question(&entries, "送人头"), "确定删除标签「送人头」吗？");
}

#[test]
fn columns_fit_and_tags_fold_into_more() {
    assert_eq!(fit_columns(&[200, 176, 340, 120], &[0, 1, 2, 3], 700), [200, 176, 204, 120]);
    // Too narrow: 原因 keeps its minimum and the columns give way from the right.
    assert_eq!(fit_columns(&[200, 176, 340, 120], &[0, 1, 2, 3], 400), [184, 72, 72, 72]);
    assert_eq!(column_order(&[3, 2, 1, 0]), [3, 2, 1, 0]);
    assert_eq!(column_order(&[0, 0, 1]), [0, 1, 2, 3]);
    let tags: Vec<String> = ["炸房", "挂机", "不尊重底牌还骂人"].iter().map(|t| t.to_string()).collect();
    assert_eq!(tag_row_layout(&tags, 400.0), (3, String::new()));
    assert_eq!(tag_row_layout(&tags, 176.0), (2, "+1".into()));
    assert_eq!(tag_row_layout(&tags, 30.0), (0, "+3".into()));
}

#[test]
fn delete_clear_and_undo_with_toasts() {
    let mut store = seeded("normal");
    let mut undo = Undo::default();
    let done = ops::apply(&mut store, &mut undo, &ListAction::Delete(0)).unwrap().unwrap();
    assert_eq!((done.say.as_str(), done.undo, store.entries.len()), ("已删除「示例坏人」", true, 4));
    let back = ops::apply(&mut store, &mut undo, &ListAction::Undo).unwrap().unwrap();
    assert_eq!((back.say.as_str(), store.entries[0].name.as_str()), ("已撤销", "示例坏人"));
    assert_eq!(ops::clear_question(&store), "将删除 5 条黑名单，确定清空吗？");
    let cleared = ops::apply(&mut store, &mut undo, &ListAction::Clear).unwrap().unwrap();
    assert_eq!((cleared.say.as_str(), store.entries.len()), ("已清空 5 人", 0));
    ops::apply(&mut store, &mut undo, &ListAction::Undo).unwrap();
    assert_eq!(store.entries.len(), 5);
    // 直播模式 masks the name in the toast; the clipboard still gets the name itself.
    store.settings.stream_mode = "on".into();
    assert_eq!(
        ops::copy_name(&store, 0),
        Some(ListAction::Copy { text: "示例坏人".into(), say: "已复制「示***」".into() })
    );
    assert!(matches!(ops::share_list(&store), Some(ListAction::Copy { say, .. }) if say == "已复制 5 人"));
    assert_eq!(ops::apply(&mut store, &mut undo, &ListAction::AskClear).unwrap(), None);
    let _ = std::fs::remove_dir_all(&store.root);
}

#[test]
fn tags_new_rename_remove() {
    let mut store = seeded("normal");
    let mut undo = Undo::default();
    let taken = ops::apply(&mut store, &mut undo, &ListAction::NewTag("炸房".into())).unwrap().unwrap();
    assert_eq!(taken.say, "标签已存在");
    ops::apply(&mut store, &mut undo, &ListAction::NewTag(" 迟到 ".into())).unwrap();
    assert!(store.tag_catalog().contains(&"迟到".to_string()));
    let renamed = ops::apply(&mut store, &mut undo, &ListAction::RenameTag { old: "挂机".into(), new: "摸鱼".into() })
        .unwrap()
        .unwrap();
    assert_eq!(renamed.pick_tag.as_deref(), Some("摸鱼"));
    assert_eq!(store.entries[4].tags, ["摸鱼"]);
    ops::apply(&mut store, &mut undo, &ListAction::RemoveTag("摸鱼".into())).unwrap();
    assert!(store.entries.iter().all(|entry| !entry.tags.contains(&"摸鱼".to_string())));
    let _ = std::fs::remove_dir_all(&store.root);
}

/// Every state draws: the three data sets in light, the normal one in dark. LIST_SHOTS=<dir> keeps the pictures.
#[test]
fn every_state_renders() {
    let dir = std::env::var_os("LIST_SHOTS")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| std::env::temp_dir().join(format!("list-render-{}", std::process::id())));
    let sizes = render(&dir, &[("normal", false), ("empty", false), ("stress", false), ("normal", true)], 1.5).unwrap();
    assert_eq!(sizes, [(1350, 732); 4]);
    for name in ["rust-normal.png", "rust-empty.png", "rust-stress.png", "rust-normal-dark.png"] {
        assert!(dir.join(name).metadata().unwrap().len() > 10_000, "{name}");
    }
}
