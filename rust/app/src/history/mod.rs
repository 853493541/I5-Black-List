//! 记录, the checks so far (ui.py `_history_page`, `_reload_history`, `_show_history_scan`, `_set_history_seat`).
//!
//! `ui/history/page.slint` exports `HistoryPage` and the `HistoryData` global it reads. [`model`] works out its lines
//! and seats from the store; [`fill`] puts them in the window; [`connect`] turns the player's clicks into
//! [`HistoryAction`]s for the app (the ones that change the store or open a dialog).

#![allow(dead_code)]

#[cfg(test)]
mod tests;

/// ui_shots' 嘉宾 for the pictures: 心动小鹿 (昵称 小鹿) and 心动星星 (tests and `--shots`).
pub fn tests_seed_likes() -> Vec<data::store::Like> {
    [("心动小鹿", "小鹿"), ("心动星星", "")]
        .iter()
        .map(|(name, nickname)| data::store::Like {
            name: (*name).into(),
            nickname: (*nickname).into(),
            reason: String::new(),
            added_at: String::new(),
            scenes: Default::default(),
        })
        .collect()
}

use std::collections::{HashMap, HashSet};

use chrono::{DateTime, FixedOffset, Timelike};
use data::store::Store;
use lobby::matching::{match_label, NameLabel};
use slint::{ComponentHandle, Global, ModelRc, SharedString, VecModel};

use crate::list::model::local_moment;
use crate::{HistoryData, HistoryItem, HistorySeat};

/// What the player asked for on 记录.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum HistoryAction {
    /// A check's time: show its seats.
    Pick(usize),
    /// A day folded or opened.
    ToggleDay(String),
    /// A seat clicked: 添加 a stranger, 编辑 a listed one (the seat's name as read).
    Seat { scan: usize, seat: usize, name: String, tone: Tone },
    /// 更多 › 删除: the check shown.
    Delete(usize),
    /// 更多 › 清空记录: ask first.
    AskClear,
}

/// How a seat reads.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Tone {
    Hit,
    Like,
    Me,
    Unclear,
    Plain,
}

impl Tone {
    pub fn key(self) -> &'static str {
        match self {
            Tone::Hit => "hit",
            Tone::Like => "like",
            Tone::Me => "me",
            Tone::Unclear => "unclear",
            Tone::Plain => "plain",
        }
    }

    fn from_key(key: &str) -> Tone {
        [Tone::Hit, Tone::Like, Tone::Me, Tone::Unclear].into_iter().find(|tone| tone.key() == key).unwrap_or(Tone::Plain)
    }
}

/// A line of the left column.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Line {
    pub day: String,
    /// None for the day itself; the check's index and time for a check.
    pub time: Option<(usize, String)>,
    pub hits: usize,
}

/// ui._day_and_clock: 今天 / 昨天 / 11月3日, and HH:MM; a time that cannot be read is its own day-less line.
pub fn day_and_clock(stamp: &str, now: DateTime<FixedOffset>) -> (String, String) {
    let Ok(moment) = DateTime::parse_from_rfc3339(stamp) else {
        return (String::new(), stamp.to_string());
    };
    let local = local_moment(stamp, now).unwrap_or(moment);
    let days = (now.date_naive() - local.date_naive()).num_days();
    let day = match days {
        0 => "今天".to_string(),
        1 => "昨天".to_string(),
        _ => format!("{}月{}日", chrono::Datelike::month(&moment), chrono::Datelike::day(&moment)),
    };
    (day, format!("{:02}:{:02}", moment.hour(), moment.minute()))
}

/// The left column, newest check first, grouped by day in the order the days first come.
pub fn lines(store: &Store, now: DateTime<FixedOffset>) -> Vec<Line> {
    let hits = crate::list::model::hit_counts(&store.entries, &store.scans);
    let mut days: Vec<(String, Vec<Line>)> = Vec::new();
    let mut seen: HashMap<String, usize> = HashMap::new();
    for (index, scan) in store.scans.iter().enumerate() {
        let (day, clock) = day_and_clock(&scan.at, now);
        let key = if day.is_empty() { clock.clone() } else { day };
        let slot = *seen.entry(key.clone()).or_insert_with(|| {
            days.push((key.clone(), Vec::new()));
            days.len() - 1
        });
        days[slot].1.push(Line { day: key, time: Some((index, clock)), hits: hits.get(&index).copied().unwrap_or(0) });
    }
    days.into_iter()
        .flat_map(|(day, times)| std::iter::once(Line { day, time: None, hits: 0 }).chain(times))
        .collect()
}

fn label(name: &str) -> NameLabel {
    NameLabel { raw: name.into(), visible: name.into(), truncated: false, unclear: false }
}

fn entries(names: impl Iterator<Item = String>) -> Vec<lobby::model::Entry> {
    names.map(|name| lobby::model::Entry { name, ..Default::default() }).collect()
}

/// The seats of check `scan`, as _set_history_seat shows them: the 嘉宾's 昵称, masked 黑名单 names in 直播模式.
pub fn seats(store: &Store, scan: usize) -> Vec<(String, Tone)> {
    let Some(scan) = store.scans.get(scan) else {
        return Vec::new();
    };
    let listed = entries(store.entries.iter().map(|entry| entry.name.clone()));
    let likes = entries(store.likes.iter().map(|like| like.name.clone()));
    let me = entries(std::iter::once(store.settings.player_name.clone()).filter(|name| !name.is_empty()));
    let streaming = !store.settings.stream_mode.is_empty() && store.settings.stream_mode != "off";
    scan.names
        .iter()
        .map(|seat| {
            if seat.unclear || seat.name.trim().is_empty() {
                return ("未识别".to_string(), Tone::Unclear);
            }
            let read = label(&seat.name);
            if let Some(hit) = match_label(&read, &listed).first() {
                let shown = store.entries[hit.index].name.clone();
                let shown = if streaming { crate::list::model::masked_name(&shown) } else { shown };
                return (shown, Tone::Hit);
            }
            if let Some(like) = match_label(&read, &likes).first() {
                let like = &store.likes[like.index];
                let shown = if like.nickname.is_empty() { like.name.clone() } else { like.nickname.clone() };
                return (shown, Tone::Like);
            }
            if !match_label(&read, &me).is_empty() {
                return (seat.name.clone(), Tone::Me);
            }
            (seat.name.clone(), Tone::Plain)
        })
        .collect()
}

/// The page's state: which days are folded and which check is shown.
#[derive(Debug, Default)]
pub struct View {
    pub closed: HashSet<String>,
    pub picked: usize,
}

/// Puts the store's checks into the window.
pub fn fill<C: ComponentHandle>(window: &C, store: &Store, view: &View, now: DateTime<FixedOffset>)
where
    for<'a> HistoryData<'a>: Global<'a, C>,
{
    let data = window.global::<HistoryData>();
    let items: Vec<HistoryItem> = lines(store, now)
        .into_iter()
        .map(|line| HistoryItem {
            kind: SharedString::from(if line.time.is_some() { "time" } else { "day" }),
            text: SharedString::from(line.time.as_ref().map(|(_, clock)| clock.as_str()).unwrap_or(&line.day)),
            open: !view.closed.contains(&line.day),
            day: SharedString::from(line.day),
            scan: line.time.as_ref().map(|(index, _)| *index as i32).unwrap_or(-1),
            hits: line.hits as i32,
        })
        .collect();
    let picked = if store.scans.is_empty() { -1 } else { view.picked.min(store.scans.len() - 1) as i32 };
    let shown: Vec<HistorySeat> = if picked < 0 { Vec::new() } else { seats(store, picked as usize) }
        .into_iter()
        .map(|(name, tone)| HistorySeat { name: name.into(), tone: tone.key().into() })
        .collect();
    data.set_items(ModelRc::new(VecModel::from(items)));
    data.set_seats(ModelRc::new(VecModel::from(shown)));
    data.set_picked(picked);
    data.set_empty(store.scans.is_empty());
}

/// Sends what the player does on 记录 to `act`.
pub fn connect<C: ComponentHandle + 'static>(window: &C, act: impl Fn(HistoryAction) + 'static)
where
    for<'a> HistoryData<'a>: Global<'a, C>,
{
    let act = std::rc::Rc::new(act);
    let data = window.global::<HistoryData>();
    let a = act.clone();
    data.on_picked_scan(move |scan| a(HistoryAction::Pick(scan.max(0) as usize)));
    let a = act.clone();
    data.on_day_toggled(move |day| a(HistoryAction::ToggleDay(day.to_string())));
    let (a, weak) = (act.clone(), window.as_weak());
    data.on_seat_clicked(move |seat| {
        let Some(window) = weak.upgrade() else { return };
        let data = window.global::<HistoryData>();
        let Some(shown) = slint::Model::row_data(&data.get_seats(), seat as usize) else { return };
        let tone = Tone::from_key(&shown.tone);
        if tone != Tone::Unclear {
            let scan = data.get_picked().max(0) as usize;
            a(HistoryAction::Seat { scan, seat: seat as usize, name: shown.name.to_string(), tone });
        }
    });
    let (a, weak) = (act.clone(), window.as_weak());
    data.on_delete_record(move || {
        if let Some(window) = weak.upgrade() {
            let picked = window.global::<HistoryData>().get_picked();
            if picked >= 0 {
                a(HistoryAction::Delete(picked as usize));
            }
        }
    });
    data.on_clear_records(move || act(HistoryAction::AskClear));
}
