use std::path::PathBuf;

use chrono::DateTime;
use data::store::{Like, Store};
use slint::{ComponentHandle, Model};

use super::*;
use crate::{HistoryWindow, MainWindow};

fn at(stamp: &str) -> DateTime<FixedOffset> {
    DateTime::parse_from_rfc3339(stamp).unwrap()
}

/// ui_shots' normal data: the list, two 嘉宾 (one with a 昵称), the player's name and one lobby of SEATS.
fn seeded() -> Store {
    let mut store = crate::list::render::seeded("normal");
    for (name, nickname) in [("心动小鹿", "小鹿"), ("心动星星", "")] {
        store.likes.push(Like {
            name: name.into(),
            nickname: nickname.into(),
            reason: String::new(),
            added_at: String::new(),
            scenes: Default::default(),
        });
    }
    store.settings.player_name = "柠檬汽水".into();
    store
}

#[test]
fn days_read_today_yesterday_or_the_date_and_times_hh_mm() {
    let now = at("2026-11-18T21:30:00+08:00");
    assert_eq!(day_and_clock("2026-11-18T09:05:00+08:00", now), ("今天".into(), "09:05".into()));
    assert_eq!(day_and_clock("2026-11-17T23:59:00+08:00", now), ("昨天".into(), "23:59".into()));
    assert_eq!(day_and_clock("2026-11-03T12:00:00+08:00", now), ("11月3日".into(), "12:00".into()));
    assert_eq!(day_and_clock("not a time", now), (String::new(), "not a time".into()));
}

#[test]
fn checks_group_under_their_day_in_order_with_their_hits() {
    let mut store = seeded();
    let scan = store.scans[0].clone();
    store.scans = ["2026-11-18T20:00:00+08:00", "2026-11-18T08:00:00+08:00", "2026-11-16T08:00:00+08:00"]
        .iter()
        .map(|stamp| {
            let mut scan = scan.clone();
            scan.at = (*stamp).into();
            scan
        })
        .collect();
    let lines = lines(&store, at("2026-11-18T21:30:00+08:00"));
    let shown: Vec<(String, Option<usize>)> = lines.iter().map(|l| (l.day.clone(), l.time.as_ref().map(|t| t.0))).collect();
    assert_eq!(
        shown,
        vec![
            ("今天".into(), None),
            ("今天".into(), Some(0)),
            ("今天".into(), Some(1)),
            ("11月16日".into(), None),
            ("11月16日".into(), Some(2)),
        ]
    );
    assert!(lines.iter().filter(|l| l.time.is_some()).all(|l| l.hits == 1), "示例坏人 is on the list in each");
    let _ = std::fs::remove_dir_all(&store.root);
}

#[test]
fn seats_read_as_hit_like_me_unclear_or_plain() {
    let mut store = seeded();
    let seats = seats(&store, 0);
    let tone = |name: &str| seats.iter().find(|(shown, _)| shown == name).map(|(_, tone)| *tone);
    assert_eq!(tone("示例坏人"), Some(Tone::Hit));
    assert_eq!(tone("小鹿"), Some(Tone::Like), "a 嘉宾 shows by 昵称");
    assert_eq!(tone("心动星星"), Some(Tone::Like));
    assert_eq!(tone("柠檬汽水"), Some(Tone::Me));
    assert_eq!(tone("未识别"), Some(Tone::Unclear), "摸鱼大师 was not read");
    assert_eq!(tone("路过的猫"), Some(Tone::Plain));
    store.settings.stream_mode = "on".into();
    assert!(super::seats(&store, 0).iter().all(|(name, _)| name != "示例坏人"), "直播模式 masks the list's names");
    let _ = std::fs::remove_dir_all(&store.root);
}

/// The page, alone and inside the main window, at Windows 150 %: rust-normal.png and rust-empty.png in
/// shots/history (BLACKLIST_SHOTS=<dir> keeps them elsewhere), and a click on a check and a day reaching the app.
#[test]
fn the_page_draws_and_its_clicks_reach_the_app() {
    crate::shots::init();
    let dir = std::env::var_os("BLACKLIST_SHOTS").map(PathBuf::from).map(|d| d.join("history"));
    let store = seeded();
    let palette = |ui: &HistoryWindow| ui.global::<crate::Palettes>().get_blue_light();
    for (name, store) in [("rust-normal", Some(&store)), ("rust-empty", None)] {
        let ui = HistoryWindow::new().unwrap();
        ui.set_p(palette(&ui));
        let empty = crate::list::render::seeded("empty");
        fill(&ui, store.unwrap_or(&empty), &View::default(), at("2026-11-18T21:30:00+08:00"));
        let picture = crate::shots::draw(&ui, (900.0, 560.0), 1.5).unwrap();
        assert!(picture.rgb.chunks(3).any(|p| p != &picture.rgb[..3]), "{name} draws something");
        if let Some(dir) = &dir {
            crate::shots::save(&dir.join(format!("{name}.png")), &picture).unwrap();
        }
        let _ = std::fs::remove_dir_all(&empty.root);
    }
    let window = MainWindow::new().unwrap();
    fill(&window, &store, &View::default(), at("2026-11-18T21:30:00+08:00"));
    let data = window.global::<crate::HistoryData>();
    assert_eq!(data.get_seats().row_count(), 12);
    assert!(!data.get_empty());
    let got = std::rc::Rc::new(std::cell::RefCell::new(Vec::new()));
    let kept = got.clone();
    connect(&window, move |action| kept.borrow_mut().push(action));
    data.invoke_picked_scan(0);
    data.invoke_day_toggled("今天".into());
    data.invoke_seat_clicked(7);
    data.invoke_clear_records();
    let got = got.borrow();
    assert_eq!(got[0], HistoryAction::Pick(0));
    assert_eq!(got[1], HistoryAction::ToggleDay("今天".into()));
    assert_eq!(got.len(), 3, "摸鱼大师's 未识别 seat asks nothing: {got:?}");
    assert_eq!(got[2], HistoryAction::AskClear);
    let _ = std::fs::remove_dir_all(&store.root);
}
