//! What the 黑名单 page shows, worked out without Slint: the rows as ui.py's `_ordered_entries` and `_show_list`
//! give them (tag filter, search, sort), the 标签 column beside the list, 最近遇到 and the empty state.

use std::collections::HashMap;

use chrono::{DateTime, FixedOffset, NaiveDateTime, TimeZone};
use data::store::scans::Scan;
use data::store::Entry;

use super::collate;

/// 最近遇到 for someone not met in any record yet (ui_widgets.NEVER_MET).
pub const NEVER_MET: &str = "—";

/// The two columns a click on the title sorts by (名字 and 最近遇到); the others do not sort.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SortColumn {
    Name,
    Met,
}

/// How the page is looked at: the tag picked beside it, the search box, and the sort (column, first click).
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct View {
    pub tag: String,
    pub search: String,
    pub sort: Option<(SortColumn, bool)>,
}

impl View {
    /// ui._sort_blacklist: the first click on a column sorts one way (名字 A to Z, 最近遇到 newest first), the next
    /// the other way, and so on.
    pub fn click_sort(&mut self, column: SortColumn) {
        let first = self.sort != Some((column, true));
        self.sort = Some((column, first));
    }
}

/// One row of the table.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Row {
    /// The entry's place in the store, for 编辑 and 删除.
    pub index: usize,
    pub name: String,
    pub tags: Vec<String>,
    pub reason: String,
    pub met: String,
    /// False when 最近遇到 is the gray dash.
    pub met_known: bool,
}

/// What shows in place of the table when it has no rows.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Empty {
    /// The table has rows.
    No,
    /// Nobody on the list: 黑名单还是空的, with 批量导入 and 添加.
    Blank,
    /// A search or a tag that matches nobody.
    NotFound(String),
}

impl Empty {
    pub fn text(&self) -> String {
        match self {
            Empty::No => String::new(),
            Empty::Blank => "黑名单还是空的".into(),
            Empty::NotFound(text) => text.clone(),
        }
    }
}

/// ui_widgets.masked_name: the first character, then a star for every one after it, and always at least one star.
pub fn masked_name(name: &str) -> String {
    let mut chars = name.chars();
    match chars.next() {
        None => String::new(),
        Some(first) => format!("{first}{}", "*".repeat(chars.count().max(1))),
    }
}

/// ui_widgets._local_moment: an ISO time, one without a zone read as this PC's.
pub fn local_moment(stamp: &str, now: DateTime<FixedOffset>) -> Option<DateTime<FixedOffset>> {
    if let Ok(moment) = DateTime::parse_from_rfc3339(stamp) {
        return Some(moment.with_timezone(now.offset()));
    }
    let naive = ["%Y-%m-%dT%H:%M:%S%.f", "%Y-%m-%d %H:%M:%S%.f", "%Y-%m-%dT%H:%M", "%Y-%m-%d"]
        .iter()
        .find_map(|format| NaiveDateTime::parse_from_str(stamp, format).ok())
        .or_else(|| chrono::NaiveDate::parse_from_str(stamp, "%Y-%m-%d").ok().and_then(|day| day.and_hms_opt(0, 0, 0)))?;
    now.offset().from_local_datetime(&naive).single()
}

/// ui_widgets._zh_ago: 刚刚, 5分钟前, 3小时前, 2天前, 4个月前, 1年前; "" for a time that cannot be read.
pub fn zh_ago(stamp: &str, now: DateTime<FixedOffset>) -> String {
    let Some(moment) = local_moment(stamp, now) else {
        return String::new();
    };
    let seconds = (now - moment).num_milliseconds() as f64 / 1000.0;
    if seconds < 60.0 {
        return "刚刚".into();
    }
    let minutes = (seconds / 60.0).floor() as i64;
    if minutes < 60 {
        return format!("{minutes}分钟前");
    }
    let hours = (seconds / 3600.0).floor() as i64;
    if hours < 24 {
        return format!("{hours}小时前");
    }
    let days = (seconds / 86400.0).floor() as i64;
    if days < 30 {
        return format!("{days}天前");
    }
    if days / 30 < 12 {
        return format!("{}个月前", days / 30);
    }
    format!("{}年前", days / 365)
}

/// match.last_seen through the lobby crate: when each listed name was last in a record (its record time).
pub fn last_met(entries: &[Entry], scans: &[Scan]) -> HashMap<usize, String> {
    let entries: Vec<lobby::model::Entry> = entries
        .iter()
        .map(|entry| lobby::model::Entry { name: entry.name.clone(), ..Default::default() })
        .collect();
    let scans: Vec<lobby::matching::Scan> = scans
        .iter()
        .map(|scan| lobby::matching::Scan {
            at: scan.at.clone(),
            names: scan
                .names
                .iter()
                .map(|seat| lobby::matching::ScanSeat { name: seat.name.clone(), unclear: seat.unclear })
                .collect(),
        })
        .collect();
    lobby::matching::last_seen(&entries, &scans).0
}

/// The page's rows, in ui._ordered_entries' order, as ui._show_list fills them.
pub fn rows(
    entries: &[Entry],
    met: &HashMap<usize, String>,
    view: &View,
    hidden: bool,
    now: DateTime<FixedOffset>,
) -> Vec<Row> {
    let mut picked: Vec<(usize, &Entry)> = entries.iter().enumerate().collect();
    if !view.tag.is_empty() {
        picked.retain(|(_, entry)| entry.tags.contains(&view.tag));
    }
    let query = data::store::py::strip(&view.search);
    if !query.is_empty() {
        let folded = data::store::text::fold(query);
        let lowered = caseless::default_case_fold_str(query);
        picked.retain(|(_, entry)| {
            (!folded.is_empty() && data::store::text::fold(&entry.name).contains(&folded))
                || entry.tags.iter().any(|tag| caseless::default_case_fold_str(tag).contains(&lowered))
                || caseless::default_case_fold_str(&entry.reason).contains(&lowered)
        });
    }
    match view.sort {
        None => {}
        Some((SortColumn::Name, first)) => {
            picked.sort_by(|a, b| collate::compare(&a.1.name, &b.1.name));
            if !first {
                picked.reverse();
            }
        }
        Some((SortColumn::Met, newest)) => {
            let stamp = |index: usize| {
                met.get(&index).and_then(|at| local_moment(at, now)).map(|moment| moment.timestamp_millis())
            };
            picked.sort_by_key(|(index, _)| match stamp(*index) {
                None => (true, 0, *index),
                Some(ms) => (false, if newest { -ms } else { ms }, *index),
            });
        }
    }
    picked
        .into_iter()
        .map(|(index, entry)| {
            let seen = met.get(&index).map(|at| zh_ago(at, now)).unwrap_or_default();
            Row {
                index,
                name: if hidden { masked_name(&entry.name) } else { entry.name.clone() },
                tags: entry.tags.clone(),
                reason: entry.reason.split_whitespace().collect::<Vec<_>>().join(" "),
                met_known: !seen.is_empty(),
                met: if seen.is_empty() { NEVER_MET.into() } else { seen },
            }
        })
        .collect()
}

/// ui._fill_tag_list: 全部 with everyone, then each tag of the catalog with how many names carry it.
pub fn tag_rows(entries: &[Entry], catalog: &[String]) -> Vec<(String, usize)> {
    let mut counts: HashMap<&str, usize> = HashMap::new();
    for tag in entries.iter().flat_map(|entry| entry.tags.iter()) {
        *counts.entry(tag.as_str()).or_default() += 1;
    }
    std::iter::once((String::new(), entries.len()))
        .chain(catalog.iter().map(|tag| (tag.clone(), counts.get(tag.as_str()).copied().unwrap_or(0))))
        .collect()
}

/// The empty state for these rows: none when there are rows, 黑名单还是空的 when the list is empty, else what found
/// nothing.
pub fn empty(count: usize, shown: usize, view: &View) -> Empty {
    let query = data::store::py::strip(&view.search);
    match (count, shown) {
        (_, 1..) => Empty::No,
        (0, _) => Empty::Blank,
        _ if !query.is_empty() => Empty::NotFound(format!("没有找到「{query}」")),
        _ => Empty::NotFound(format!("没有使用「{}」标签的玩家", view.tag)),
    }
}

/// ui._remove_tag's question.
pub fn remove_tag_question(entries: &[Entry], tag: &str) -> String {
    let users = entries.iter().filter(|entry| entry.tags.iter().any(|own| own == tag)).count();
    if users == 0 {
        format!("确定删除标签「{tag}」吗？")
    } else {
        format!("「{tag}」{users} 人正在使用，是否确定删除？")
    }
}
