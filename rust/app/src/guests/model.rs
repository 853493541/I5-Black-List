//! What the 嘉宾 page shows, from the store's lists: ui_likes.LikesPage.refresh and its helpers, without Qt.
//!
//! `Page::build` is the whole page for one search: the 我 row, the 组合, the 嘉宾 (the last saved on top), the
//! toolbar's state and the empty state. Every text is the Python page's, proven on golden.json.

use chrono::{DateTime, FixedOffset};
use data::store::scans::{parse_at, Scan};
use data::store::sounds::Scenes;
use data::store::text::{shown, SCENE_KEYS};
use data::store::{Combo, Like};
use lobby::fold;
use std::collections::HashMap;

/// love_scenes.SCENES: (key, name), in 设置's order.
pub const SCENES: [(&str, &str); 11] = [
    ("classic", "经典"),
    ("lace", "玫瑰花边"),
    ("ice", "冰蓝极光"),
    ("stars", "星河许愿"),
    ("cyber", "赛博朋克（一）"),
    ("neon", "赛博朋克（二）"),
    ("angel", "金色传说"),
    ("equation", "数学公式"),
    ("fluffy", "毛茸茸保护协会"),
    ("claw", "演说家遇袭"),
    ("lyre", "竖琴清风"),
];
/// 最近遇到 for someone not met in any record yet (ui_widgets.NEVER_MET).
pub const NEVER_MET: &str = "—";
pub const NO_NAME: &str = "点右上角填写游戏名";
pub const TOO_FEW: &str = "先添加至少两位嘉宾";
pub const EMPTY: &str = "嘉宾列表还是空的";

/// What a row is: the 我 row, a 组合 (by its place in the combos), or a 嘉宾 (by its place in the likes).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RowKind {
    Me,
    Combo(usize),
    Guest(usize),
}

/// One item of a row's right-click menu; Separator is the line before 删除.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MenuItem {
    Edit,
    CopyName,
    ToTop,
    Separator,
    Delete,
}

impl MenuItem {
    pub fn label(self) -> &'static str {
        match self {
            MenuItem::Edit => "编辑",
            MenuItem::CopyName => "复制名字",
            MenuItem::ToTop => "置顶",
            MenuItem::Separator => "-",
            MenuItem::Delete => "删除",
        }
    }
}

/// One row as the list draws it.
#[derive(Debug, Clone, PartialEq)]
pub struct Row {
    pub kind: RowKind,
    /// 名字: the 嘉宾's name, a 组合's 嘉宾 joined by " + ", or the player's own name (NO_NAME before there is one).
    pub name: String,
    /// A 组合's 嘉宾 as shown, each with whether they are still on the list.
    pub people: Vec<(String, bool)>,
    pub nickname: String,
    /// The keys of the dots before 场景's words ("random" for 随机).
    pub dots: Vec<String>,
    pub scene: String,
    pub reason: String,
    pub met: String,
    pub menu: Vec<MenuItem>,
}

/// The page for one search.
#[derive(Debug, Clone, PartialEq)]
pub struct Page {
    pub rows: Vec<Row>,
    /// The first `fixed` rows (我 and the 组合) neither drag nor take a drop.
    pub fixed: usize,
    pub show_table: bool,
    pub show_toolbar: bool,
    pub show_search: bool,
    pub show_more: bool,
    pub add_combo_enabled: bool,
    /// The empty state's icon ("heart" or "search") and words; its buttons only on an empty list.
    pub empty_icon: &'static str,
    pub empty_text: String,
    pub empty_buttons: bool,
    pub drag: bool,
}

/// What the page reads from the store.
pub struct Lists<'a> {
    pub likes: &'a [Like],
    pub combos: &'a [Combo],
    pub me: &'a Scenes,
    pub player_name: &'a str,
    pub scans: &'a [Scan],
}

/// A scene as the list says it: its name, the scene that replaced a dropped one, 经典 for one this version lacks.
pub fn scene_name(key: &str) -> &'static str {
    let key = shown(key);
    SCENES.iter().find(|(k, _)| *k == key).unwrap_or(&SCENES[0]).1
}

/// ui_guests.scene_dots: none on 不放, "random" for any scene, else each scene ticked that this version plays.
pub fn scene_dots(scenes: &Scenes) -> Vec<String> {
    if scenes.off() {
        return Vec::new();
    }
    let mut keys: Vec<String> = Vec::new();
    if !scenes.random {
        for key in scenes.keys.iter().map(|key| shown(key)) {
            if SCENE_KEYS.contains(&key.as_str()) && !keys.contains(&key) {
                keys.push(key);
            }
        }
    }
    if keys.is_empty() {
        keys.push("random".into());
    }
    keys
}

/// ui_guests.scenes_said: nothing on 不放, 随机, the one scene's name, or N个场景.
pub fn scenes_said(scenes: &Scenes) -> String {
    let keys = scene_dots(scenes);
    match keys.as_slice() {
        [] => String::new(),
        [one] if one == "random" => "随机".into(),
        [one] => scene_name(one).into(),
        many => format!("{}个场景", many.len()),
    }
}

/// ui_likes.share_likes: 名字（原因）, one per line, the shape 批量导入 reads.
pub fn share_likes(likes: &[Like]) -> String {
    let lines: Vec<String> = likes
        .iter()
        .map(|like| if like.reason.is_empty() { like.name.clone() } else { format!("{}（{}）", like.name, like.reason) })
        .collect();
    lines.join("\n")
}

/// ui_widgets._zh_ago: how long ago, in words; empty for a stamp that does not parse.
pub fn zh_ago(stamp: &str, now: DateTime<FixedOffset>) -> String {
    let Some(moment) = parse_at(stamp, *now.offset()) else { return String::new() };
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

fn shown_name(like: &Like) -> &str {
    if like.nickname.is_empty() { &like.name } else { &like.nickname }
}

/// guests.members: a 组合's 嘉宾 as shown, each with whether they are still on 嘉宾.
pub fn members(combo: &Combo, likes: &[Like]) -> Vec<(String, bool)> {
    let by_key: HashMap<String, &Like> = likes.iter().map(|like| (fold(&like.name), like)).collect();
    combo
        .names
        .iter()
        .map(|name| match by_key.get(&fold(name)) {
            Some(like) => (shown_name(like).to_string(), true),
            None => (name.clone(), false),
        })
        .collect()
}

fn lobby_scans(scans: &[Scan]) -> Vec<lobby::Scan> {
    scans
        .iter()
        .map(|scan| lobby::Scan {
            at: scan.at.clone(),
            names: scan.names.iter().map(|seat| lobby::ScanSeat { name: seat.name.clone(), unclear: seat.unclear }).collect(),
        })
        .collect()
}

fn entry(name: &str) -> lobby::Entry {
    lobby::Entry::named(name)
}

/// ui_likes.combos_met: when all of each 组合's 嘉宾 were last in one record, by its place in combos.
pub fn combos_met(combos: &[Combo], likes: &[Like], scans: &[lobby::Scan]) -> HashMap<usize, String> {
    let taken: Vec<String> = likes.iter().map(|like| fold(&like.name)).collect();
    let mut people: Vec<lobby::Entry> = likes.iter().map(|like| entry(&like.name)).collect();
    let mut gone: Vec<String> = Vec::new();
    for name in combos.iter().flat_map(|combo| &combo.names) {
        let key = fold(name);
        if !taken.contains(&key) && !gone.contains(&key) {
            gone.push(key);
            people.push(entry(name));
        }
    }
    let keys: Vec<String> = people.iter().map(|person| fold(&person.name)).collect();
    let wanted: Vec<Vec<String>> = combos.iter().map(|combo| combo.names.iter().map(|name| fold(name)).collect()).collect();
    let mut found = HashMap::new();
    for scan in scans {
        if found.len() == combos.len() {
            break;
        }
        let here: Vec<&String> = lobby::last_seen(&people, std::slice::from_ref(scan)).0.keys().map(|&index| &keys[index]).collect();
        for (number, names) in wanted.iter().enumerate() {
            if !found.contains_key(&number) && names.iter().all(|name| here.contains(&name)) {
                found.insert(number, scan.at.clone());
            }
        }
    }
    found
}

fn met_words(met: &HashMap<usize, String>, place: usize, now: DateTime<FixedOffset>) -> String {
    met.get(&place).map_or_else(|| NEVER_MET.to_string(), |stamp| zh_ago(stamp, now))
}

impl Page {
    /// The page for this search (the search box's text as typed), at `now`.
    pub fn build(lists: &Lists, search: &str, now: DateTime<FixedOffset>) -> Page {
        let query = search.trim();
        let folded = fold(query);
        let (likes, combos) = (lists.likes, lists.combos);
        let scans = lobby_scans(lists.scans);
        let has_any = !likes.is_empty() || !combos.is_empty();
        let mut rows = Vec::new();
        if has_any && (folded.is_empty() || fold(lists.player_name).contains(&folded)) {
            let name = if lists.player_name.is_empty() { NO_NAME } else { lists.player_name };
            rows.push(Row {
                kind: RowKind::Me,
                name: name.into(),
                people: Vec::new(),
                nickname: String::new(),
                dots: scene_dots(lists.me),
                scene: scenes_said(lists.me),
                reason: String::new(),
                met: String::new(),
                menu: vec![MenuItem::Edit],
            });
        }
        let nicknames: HashMap<String, &str> = likes.iter().map(|like| (fold(&like.name), like.nickname.as_str())).collect();
        let combo_met = combos_met(combos, likes, &scans);
        for (number, combo) in combos.iter().enumerate() {
            let hit = query.is_empty()
                || combo.names.iter().any(|name| {
                    fold(name).contains(&folded) || nicknames.get(&fold(name)).is_some_and(|nick| nick.contains(query))
                });
            if !hit {
                continue;
            }
            let people = members(combo, likes);
            rows.push(Row {
                kind: RowKind::Combo(number),
                name: people.iter().map(|(name, _)| name.as_str()).collect::<Vec<_>>().join(" + "),
                people,
                nickname: String::new(),
                dots: scene_dots(&combo.scenes),
                scene: scenes_said(&combo.scenes),
                reason: String::new(),
                met: met_words(&combo_met, number, now),
                menu: vec![MenuItem::Edit, MenuItem::Separator, MenuItem::Delete],
            });
        }
        let fixed = rows.len();
        let people: Vec<lobby::Entry> = likes.iter().map(|like| entry(&like.name)).collect();
        let met = lobby::last_seen(&people, &scans).0;
        for (index, like) in likes.iter().enumerate().rev() {
            let text = format!("{} {}", like.nickname, like.reason);
            if !query.is_empty() && !fold(&like.name).contains(&folded) && !text.contains(query) {
                continue;
            }
            let mut menu = vec![MenuItem::Edit, MenuItem::CopyName];
            if index + 1 != likes.len() {
                menu.push(MenuItem::ToTop);
            }
            menu.extend([MenuItem::Separator, MenuItem::Delete]);
            rows.push(Row {
                kind: RowKind::Guest(index),
                name: like.name.clone(),
                people: Vec::new(),
                nickname: like.nickname.clone(),
                dots: scene_dots(&like.scenes),
                scene: scenes_said(&like.scenes),
                reason: like.reason.split_whitespace().collect::<Vec<_>>().join(" "),
                met: met_words(&met, index, now),
                menu,
            });
        }
        let shown = !rows.is_empty();
        let searched = has_any && !shown;
        Page {
            drag: query.is_empty() && rows.len() - fixed > 1,
            fixed,
            show_table: shown,
            show_toolbar: has_any,
            show_search: has_any || !search.is_empty(),
            show_more: !likes.is_empty(),
            add_combo_enabled: likes.len() >= 2,
            empty_icon: if searched { "search" } else { "heart" },
            empty_text: if searched { format!("没有找到「{query}」") } else { EMPTY.into() },
            empty_buttons: !has_any,
            rows,
        }
    }
}
