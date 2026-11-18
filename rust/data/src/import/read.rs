//! importing.read_paste and plan_import: every person in a paste, and what importing each one does.

use std::collections::{HashMap, HashSet};

use super::model::Entry;
use super::paste::{
    pieces, sections, split_names, split_spaced, width_halves, JOINED_NAMES, KEEP_SPACE, NAME_MAX, NAME_NOTE,
    OPEN, OTHER, REASON_LABEL, REASON_WORDS, TITLE,
};
use super::tags::{is_shared, merge_reason, order_tags, parse_shared, tags_and_reason, MAX_NAME, MAX_NOTE};
use super::text::{clean_stored_name, fold, head, is_digits, len, strip, strip_chars};

/// A name this long or longer that starts another is the same person, cut short by the game.
const SAME_PREFIX: usize = 4;

/// What importing a row does to the list.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Status {
    New,
    Merge,
    Same,
    Odd,
    /// On the other list (黑名单 when importing into 嘉宾, and the other way round).
    Elsewhere,
}

impl Status {
    /// The name importing.py gives it.
    pub fn key(self) -> &'static str {
        match self {
            Status::New => "new",
            Status::Merge => "merge",
            Status::Same => "same",
            Status::Odd => "odd",
            Status::Elsewhere => "elsewhere",
        }
    }
}

/// One person from a paste, and what importing them would do.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ImportRow {
    pub name: String,
    pub tags: Vec<String>,
    pub reason: String,
    pub status: Status,
    /// The entry a Merge or Same row matches; -1 for none.
    pub target: i64,
    pub checked: bool,
}

/// One person: name, 标签, 原因.
pub type Person = (String, Vec<String>, String);

fn clean(name: &str) -> String {
    head(&clean_stored_name(&name.replace(KEEP_SPACE, " ")), MAX_NAME).to_string()
}

fn contains_tag(word: &str, catalog: &[String]) -> bool {
    catalog.iter().any(|tag| word.contains(tag.as_str()))
}

/// A line without brackets: names, or one name with 标签 and 原因 after it.
fn read_plain(text: &str, catalog: &[String], pairs: bool) -> Vec<Person> {
    let spaced = split_spaced(text);
    if spaced.len() == 2 && !clean(spaced[0]).is_empty() && !contains_tag(spaced[1], catalog) && (pairs || REASON_WORDS.is_match(spaced[1])) {
        return vec![(clean(spaced[0]), Vec::new(), head(spaced[1], MAX_NOTE).to_string())];
    }
    if let Some(joined) = JOINED_NAMES.captures(strip(text)) {
        let (tags, reason) = tags_and_reason(&joined[2], catalog);
        return split_names(&joined[1])
            .iter()
            .map(|name| clean(name))
            .filter(|name| !name.is_empty())
            .map(|name| (name, tags.clone(), reason.clone()))
            .collect();
    }
    if let Some(matched) = NAME_NOTE.captures(text) {
        let name = clean(&matched[1]);
        if !name.is_empty() {
            let (tags, reason) = tags_and_reason(&matched[2], catalog);
            return vec![(name, tags, reason)];
        }
    }
    let mut names: Vec<String> = Vec::new();
    let mut tags: Vec<String> = Vec::new();
    let mut notes: Vec<String> = Vec::new();
    for word in split_names(strip_chars(text, "）")) {
        let detail = !tags.is_empty() || !notes.is_empty();
        if catalog.contains(&word) {
            if !tags.contains(&word) {
                tags.push(word);
            }
        } else if !names.is_empty()
            && (detail || word.contains([':', '：']) || contains_tag(&word, catalog) || width_halves(&clean(&word)) > 2 * NAME_MAX)
        {
            let note = strip_chars(&OTHER.replace(&word, ""), ":： ").to_string();
            if !note.is_empty() {
                notes.push(note);
            }
        } else {
            names.push(word);
        }
    }
    let reason = notes.join("，");
    let (found, _kept) = tags_and_reason(&reason, catalog);
    let mut all = tags;
    for tag in found {
        if !all.contains(&tag) {
            all.push(tag);
        }
    }
    let picked = order_tags(&all, catalog);
    names
        .iter()
        .map(|name| clean(name))
        .filter(|name| !name.is_empty())
        .map(|name| (name, picked.clone(), head(&reason, MAX_NOTE).to_string()))
        .collect()
}

/// Whether this paste is 名字 原因, line by line: most of its two-word lines carry a 标签.
fn mostly_pairs(lines: &[&str], catalog: &[String]) -> bool {
    let two: Vec<Vec<&str>> =
        lines.iter().filter(|line| !line.contains(OPEN)).map(|line| split_spaced(line)).filter(|w| w.len() == 2).collect();
    let tagged = two.iter().filter(|words| contains_tag(words[1], catalog)).count();
    two.len() >= 2 && tagged * 2 >= two.len()
}

/// (name, 标签, 原因, from a chat header line) for every person, in the paste's order.
fn read(text: &str, catalog: &[String]) -> Vec<(String, Vec<String>, String, bool)> {
    if is_shared(text) {
        return parse_shared(text).into_iter().map(|(name, tags, reason)| (name, tags, reason, false)).collect();
    }
    let mut people = Vec::new();
    let blocks = sections(text, catalog);
    let all_lines: Vec<&str> = blocks.iter().flat_map(|(block, _)| super::text::splitlines(block)).collect();
    let pairs = mostly_pairs(&all_lines, catalog);
    for (block, heading) in &blocks {
        let mut found: Vec<(String, Vec<String>, String, bool)> = Vec::new();
        for (names, note, header) in pieces(block) {
            let Some(note) = note else {
                found.extend(read_plain(&names, catalog, pairs).into_iter().map(|(n, t, r)| (n, t, r, header)));
                continue;
            };
            let unlabelled = REASON_LABEL.replace(&note, "");
            let (tags, reason) = tags_and_reason(strip_chars(&unlabelled, " :：，,"), catalog);
            for name in split_names(strip_chars(&names, " :：-—－~～\t）")) {
                let name = clean(&name);
                if !name.is_empty() {
                    found.push((name, tags.clone(), reason.clone(), header));
                }
            }
        }
        for (name, tags, reason, header) in found {
            let merged = if heading.is_empty() {
                tags
            } else {
                let mut all = heading.clone();
                all.extend(tags.into_iter().filter(|t| !heading.contains(t)));
                order_tags(&all, catalog)
            };
            people.push((name, merged, reason, header));
        }
    }
    people
}

/// Every person in a paste, as (name, 标签, 原因), in the paste's order.
pub fn read_paste(text: &str, catalog: &[String]) -> Vec<Person> {
    read(text, catalog).into_iter().map(|(name, tags, reason, _)| (name, tags, reason)).collect()
}

/// The entry this name is: the same name, or one of the two is the other cut short.
fn find(name: &str, entries: &[Entry]) -> i64 {
    let key = fold(name);
    if let Some(index) = entries.iter().position(|entry| fold(&entry.name) == key) {
        return index as i64;
    }
    for (index, entry) in entries.iter().enumerate() {
        let other = fold(&entry.name);
        let (short, long) = if len(&other) < len(&key) { (&other, &key) } else { (&key, &other) };
        if len(short) >= SAME_PREFIX && long.starts_with(short.as_str()) {
            return index as i64;
        }
    }
    -1
}

fn adds_to(row: &ImportRow, entry: &Entry) -> bool {
    let longer = len(&fold(&row.name)) > len(&fold(&entry.name));
    row.tags.iter().any(|tag| !entry.tags.contains(tag)) || merge_reason(&entry.reason, &row.reason) != entry.reason || longer
}

fn looks_odd(name: &str) -> bool {
    width_halves(name) > 2 * NAME_MAX || is_digits(name) || TITLE.is_match(name)
}

/// What 导入 would do with this paste: one row per person, checked if it changes the list.
///
/// A name on the other list (elsewhere) is shown but unchecked: a player is on one list.
pub fn plan_import(text: &str, entries: &[Entry], catalog: &[String], elsewhere: &[Entry]) -> Vec<ImportRow> {
    let mut rows: Vec<ImportRow> = Vec::new();
    let mut by_key: HashMap<String, usize> = HashMap::new();
    let mut headers: HashSet<String> = HashSet::new();
    for (name, tags, reason, header) in read(text, catalog) {
        let key = fold(&name);
        if key.is_empty() {
            continue;
        }
        if let Some(&twin) = by_key.get(&key) {
            // The same person twice in one paste: one row with both 原因.
            let twin = &mut rows[twin];
            let mut all = twin.tags.clone();
            all.extend(tags.into_iter().filter(|t| !twin.tags.contains(t)));
            twin.tags = order_tags(&all, catalog);
            twin.reason = merge_reason(&twin.reason, &reason);
            continue;
        }
        let reason = head(&reason, MAX_NOTE).to_string();
        by_key.insert(key.clone(), rows.len());
        rows.push(ImportRow { name, tags, reason, status: Status::New, target: -1, checked: true });
        if header {
            headers.insert(key);
        }
    }
    for row in &mut rows {
        let key = fold(&row.name);
        if looks_odd(&row.name) || headers.contains(&key) {
            (row.status, row.checked) = (Status::Odd, false);
            continue;
        }
        if elsewhere.iter().any(|other| fold(&other.name) == key) {
            (row.status, row.checked) = (Status::Elsewhere, false);
            continue;
        }
        row.target = find(&row.name, entries);
        if row.target >= 0 {
            let changes = adds_to(row, &entries[row.target as usize]);
            (row.status, row.checked) = if changes { (Status::Merge, true) } else { (Status::Same, false) };
        }
    }
    rows
}
