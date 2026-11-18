//! The Rust store against the files the Python Store wrote (tools/rust_golden_store.py): the same steps from the same
//! files, with the same frozen clock, must leave the same bytes; and every file it wrote reads back and saves the same.

use chrono::DateTime;
use data::store::scans::Seat;
use data::store::sounds::Scenes;
use data::store::{Clock, Store};
use std::fs;
use std::path::{Path, PathBuf};

fn golden(case: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/golden/store").join(case)
}

fn clock() -> Clock {
    Clock { fixed: Some(DateTime::parse_from_rfc3339("2026-11-18T09:30:05+00:00").unwrap()) }
}

fn copy_dir(from: &Path, to: &Path) {
    fs::create_dir_all(to).unwrap();
    for entry in fs::read_dir(from).unwrap() {
        let path = entry.unwrap().path();
        let target = to.join(path.file_name().unwrap());
        if path.is_dir() {
            copy_dir(&path, &target);
        } else {
            fs::copy(&path, &target).unwrap();
        }
    }
}

/// Every file under a folder, by its path inside it; CRLF read as LF (Python's write_text gives CRLF on Windows).
fn files(root: &Path) -> Vec<(String, Vec<u8>)> {
    let mut out = Vec::new();
    let mut stack = vec![root.to_path_buf()];
    while let Some(dir) = stack.pop() {
        for entry in fs::read_dir(&dir).unwrap() {
            let path = entry.unwrap().path();
            if path.is_dir() {
                stack.push(path);
            } else {
                let rel = path.strip_prefix(root).unwrap().to_string_lossy().replace('\\', "/");
                let bytes = fs::read(&path).unwrap();
                let text = if rel.ends_with(".json") { String::from_utf8(bytes.clone()).unwrap().replace("\r\n", "\n").into_bytes() } else { bytes };
                out.push((rel, text));
            }
        }
    }
    out.sort();
    out
}

fn s(items: &[&str]) -> Vec<String> {
    items.iter().map(|t| t.to_string()).collect()
}

fn scenes(keys: &[&str], random: bool) -> Scenes {
    Scenes { keys: s(keys), random }
}

/// The steps tools/rust_golden_store.py takes, one for one.
fn steps(store: &mut Store) {
    store.add("示例坏人二号", "炸房，开局就走", &s(&["炸房", "新标签"])).unwrap();
    assert!(store.add("示例坏人二号", "", &[]).unwrap().is_none());
    assert!(store.add("。。", "", &[]).unwrap().is_none());
    store.update_at(1, "Bad Guy Two", &s(&["贴脸", "场外"]), "又见到了").unwrap();
    store.remove_at(2).unwrap();
    store.rename_tag("演戏", "演员").unwrap();
    store.remove_custom_tag("炸房").unwrap();
    let rows = vec![
        ("示例坏人三号".to_string(), s(&["贴脸"]), "新来的".to_string(), None),
        ("示例坏人二号加长".to_string(), s(&["挂机"]), "又一个原因".to_string(), Some(2)),
    ];
    store.import_rows(&rows).unwrap();
    store.recheck_tags().unwrap();
    store.add_like("心动小鹿", "", "", &Scenes::any()).unwrap();
    store.add_like("新的嘉宾", "  昵 称 ", "好人", &scenes(&["lyre", "champagne"], false)).unwrap();
    store.update_like(0, "心动小鹿改名", "鹿", "更好", &scenes(&[], true)).unwrap();
    store.move_like(0, 2).unwrap();
    store.set_me(&scenes(&["classic"], true)).unwrap();
    store.set_scene_volume("stars", 35);
    store.choose_scene_song("angel", "angel-2.wav").unwrap();
    let lobby: Vec<Seat> = (1..=12).map(|i| Seat { seat: i, name: format!("示例玩家{i}"), unclear: i == 5 }).collect();
    store.add_scan(&lobby, Some(1.005));
    store.add_scan(&[Seat { seat: 5, name: "心动小鹿改名".into(), unclear: false }], Some(0.5));
    store.settings.hotkey = "Ctrl+F9".into();
    store.settings.theme = "绿色".into();
    store.settings.names_hidden = true;
    store.save_settings().unwrap();
}

fn replay(case: &str) {
    let work = tempfile::tempdir().unwrap();
    let input = golden(case).join("input");
    if input.exists() {
        copy_dir(&input, work.path());
    }
    let mut store = Store::open(Some(work.path().to_path_buf()), clock());
    let warning = fs::read_to_string(golden(case).join("load_warning.txt")).unwrap();
    assert_eq!(store.load_warning, warning);
    steps(&mut store);
    let (want, got) = (files(&golden(case).join("output")), files(work.path()));
    assert_eq!(want.iter().map(|f| &f.0).collect::<Vec<_>>(), got.iter().map(|f| &f.0).collect::<Vec<_>>(), "{case}: the files");
    for ((name, w), (_, g)) in want.iter().zip(&got) {
        assert!(w == g, "{case}/{name} differs:\n--- python\n{}\n--- rust\n{}", String::from_utf8_lossy(w), String::from_utf8_lossy(g));
    }
}

#[test]
fn migrate_replays_byte_for_byte() {
    replay("migrate");
}

#[test]
fn fresh_replays_byte_for_byte() {
    replay("fresh");
}

/// What the Python app left reads to the same values and saves back to the same bytes.
#[test]
fn python_output_reads_and_saves_back_the_same() {
    for case in ["migrate", "fresh"] {
        let work = tempfile::tempdir().unwrap();
        copy_dir(&golden(case).join("output"), work.path());
        let before = files(work.path());
        let store = Store::open(Some(work.path().to_path_buf()), clock());
        assert_eq!(store.load_warning, "");
        store.save_entries().unwrap();
        store.save_likes().unwrap();
        store.save_settings().unwrap();
        store.save_scans();
        assert_eq!(files(work.path()), before, "{case}");
        let again = Store::open(Some(work.path().to_path_buf()), clock());
        assert_eq!((&again.entries, &again.likes, &again.combos, &again.me), (&store.entries, &store.likes, &store.combos, &store.me));
        assert_eq!((&again.scans, &again.settings), (&store.scans, &store.settings));
    }
}

/// A backup the store made is the list as it was before the day's first change, and opens as that list.
#[test]
fn backup_round_trips() {
    let work = tempfile::tempdir().unwrap();
    let mut store = Store::open(Some(work.path().to_path_buf()), clock());
    store.add("示例坏人", "开局就走", &s(&["炸房"])).unwrap();
    let first = store.entries.clone();
    let before = fs::read(work.path().join("blacklist.json")).unwrap();
    store.add("示例坏人九号", "", &[]).unwrap();
    let backup = work.path().join("backups/blacklist-2026-11-18.json");
    assert_eq!(fs::read(&backup).unwrap(), before);
    store.add("示例坏人十号", "", &[]).unwrap();
    assert_eq!(fs::read(&backup).unwrap(), before, "one copy a day, the first");
    let restored = tempfile::tempdir().unwrap();
    fs::copy(&backup, restored.path().join("blacklist.json")).unwrap();
    assert_eq!(Store::open(Some(restored.path().to_path_buf()), clock()).entries, first);
}

/// Seven copies kept, the oldest dropped.
#[test]
fn backups_keep_a_week() {
    let work = tempfile::tempdir().unwrap();
    let folder = work.path().join("backups");
    fs::create_dir_all(&folder).unwrap();
    for day in 1..=9 {
        fs::write(folder.join(format!("blacklist-2026-11-0{day}.json")), "{}").unwrap();
    }
    let mut store = Store::open(Some(work.path().to_path_buf()), clock());
    store.add("示例坏人", "", &[]).unwrap();
    store.add("心动星星", "", &[]).unwrap();
    let mut left: Vec<String> = fs::read_dir(&folder).unwrap().map(|e| e.unwrap().file_name().into_string().unwrap()).collect();
    left.sort();
    assert_eq!(left.first().map(String::as_str), Some("blacklist-2026-11-04.json"));
    assert_eq!(left.len(), 7);
}

#[test]
fn a_broken_file_is_set_aside_with_its_warning() {
    let work = tempfile::tempdir().unwrap();
    fs::write(work.path().join("blacklist.json"), "{not json").unwrap();
    fs::write(work.path().join("history.json"), r#"{"scans": [{"names": [{"seat": "x"}]}]}"#).unwrap();
    let store = Store::open(Some(work.path().to_path_buf()), clock());
    assert_eq!(store.load_warning, "黑名单文件坏了，已备份，先用空名单；记录文件坏了，已备份，先用空记录");
    assert!(work.path().join("blacklist.unreadable-20261118-093005.json").exists());
    assert!(work.path().join("history.unreadable-20261118-093005.json").exists());
}
