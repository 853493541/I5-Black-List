//! Names read against the lists: a port of `blacklist_detect/match.py`. Names are not corrected against a dictionary.

use std::collections::HashMap;

use crate::model::Entry;
use crate::text::{digit_run, is_digit};

pub use common::text::{clean_stored_name, fold, normalize_text, split_ellipsis, strip_noise, MIN_PREFIX_CHARS};

/// Keep the cutoff the lobby prints. Matching still uses the letters in front of it.
pub fn with_game_ellipsis(visible: &str, truncated: bool) -> String {
    if truncated && !visible.is_empty() && !visible.ends_with("...") {
        return format!("{visible}...");
    }
    visible.to_string()
}

/// What the list adds after a name the game cut short: "" when the two are the same name, None when
/// they differ in more than the cut.
pub fn listed_tail(read: &str, listed: &str) -> Option<String> {
    if fold(read) == fold(listed) {
        return Some(String::new());
    }
    let cut = read.chars().count();
    let listed_chars: Vec<char> = listed.chars().collect();
    if listed_chars.len() > cut
        && fold(&listed_chars[..cut].iter().collect::<String>()) == fold(read)
    {
        return Some(listed_chars[cut..].iter().collect());
    }
    None
}

/// `倒计时[:：]?\d+秒`, the whole text.
fn is_countdown_chrome(folded: &str) -> bool {
    let chars: Vec<char> = folded.chars().collect();
    let head: Vec<char> = "倒计时".chars().collect();
    if !chars.starts_with(&head) {
        return false;
    }
    let mut at = head.len();
    if chars.get(at).is_some_and(|&ch| ch == ':' || ch == '：') {
        at += 1;
    }
    let digits = digit_run(&chars, at);
    digits > 0
        && at + digits + 1 == chars.len()
        && chars[at + digits] == '秒'
        && chars[at..at + digits].iter().all(|&c| is_digit(c))
}

/// Lobby status, not a player name. 准备就绪 is one of these lines.
pub fn is_lobby_chrome(text: &str) -> bool {
    let folded = normalize_text(text);
    if folded.is_empty() {
        return false;
    }
    folded.starts_with("准备就绪")
        || folded.contains("准备案件还原")
        || folded == "推演成功"
        || (folded.contains("模仿者狂欢") && folded.contains("12人"))
        || is_countdown_chrome(&folded)
}

/// One seat as read: the raw text, what is shown, whether the game cut it, and whether it was too unclear to use.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct NameLabel {
    pub raw: String,
    pub visible: String,
    pub truncated: bool,
    pub unclear: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MatchKind {
    Exact,
    Prefix,
}

impl MatchKind {
    pub fn as_str(self) -> &'static str {
        match self {
            MatchKind::Exact => "exact",
            MatchKind::Prefix => "prefix",
        }
    }
}

/// A listed entry a seat matched: its index in the list given, and how.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NameMatch {
    pub index: usize,
    pub visible: String,
    pub truncated: bool,
    pub kind: MatchKind,
}

fn match_refs(label: &NameLabel, entries: &[&Entry]) -> Vec<NameMatch> {
    if label.unclear
        || label.visible.is_empty()
        || is_lobby_chrome(&label.raw)
        || is_lobby_chrome(&label.visible)
    {
        return Vec::new();
    }
    let folded_visible: Vec<char> = fold(&label.visible).chars().collect();
    if folded_visible.is_empty() {
        return Vec::new();
    }
    let head = &folded_visible[..MIN_PREFIX_CHARS.min(folded_visible.len())];
    let mut exact = Vec::new();
    let mut hits = Vec::new();
    for (index, entry) in entries.iter().enumerate() {
        let folded_entry: Vec<char> = fold(&entry.name).chars().collect();
        if folded_entry.is_empty() || is_lobby_chrome(&entry.name) {
            continue;
        }
        let found = |kind, truncated| NameMatch {
            index,
            visible: label.visible.clone(),
            truncated,
            kind,
        };
        if folded_visible == folded_entry {
            exact.push(found(MatchKind::Exact, label.truncated));
            continue;
        }
        let cut = label.truncated || folded_visible.len() != folded_entry.len();
        let long_enough =
            folded_visible.len() >= MIN_PREFIX_CHARS && folded_entry.len() >= MIN_PREFIX_CHARS;
        if cut && long_enough && folded_entry.starts_with(head) {
            hits.push(found(MatchKind::Prefix, true));
        }
    }
    if exact.is_empty() {
        hits
    } else {
        exact
    }
}

/// Match the first four characters when one of the two names is cut off; the same name, when listed,
/// is the only match. `NameMatch::index` points into `entries`.
pub fn match_label(label: &NameLabel, entries: &[Entry]) -> Vec<NameMatch> {
    let refs: Vec<&Entry> = entries.iter().collect();
    match_refs(label, &refs)
}

/// One seat of a saved check record.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct ScanSeat {
    pub name: String,
    pub unclear: bool,
}

/// One saved check record: when, and the seats.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Scan {
    pub at: String,
    pub names: Vec<ScanSeat>,
}

fn head_key(folded: &str) -> String {
    folded.chars().take(MIN_PREFIX_CHARS).collect()
}

/// When each listed name was last in a record (records newest first), and how many listed names each record held.
pub fn last_seen(
    entries: &[Entry],
    scans: &[Scan],
) -> (HashMap<usize, String>, HashMap<usize, usize>) {
    let mut found = HashMap::new();
    let mut hits = HashMap::new();
    let mut groups: HashMap<String, Vec<usize>> = HashMap::new();
    for (index, entry) in entries.iter().enumerate() {
        let folded = fold(&entry.name);
        if !folded.is_empty() {
            groups.entry(head_key(&folded)).or_default().push(index);
        }
    }
    for (number, scan) in scans.iter().enumerate() {
        for seat in &scan.names {
            if seat.unclear || seat.name.is_empty() {
                continue;
            }
            let Some(candidates) = groups.get(&head_key(&fold(&seat.name))) else {
                continue;
            };
            let refs: Vec<&Entry> = candidates.iter().map(|&index| &entries[index]).collect();
            let label = NameLabel {
                raw: seat.name.clone(),
                visible: seat.name.clone(),
                truncated: false,
                unclear: false,
            };
            let matches = match_refs(&label, &refs);
            if !matches.is_empty() {
                *hits.entry(number).or_insert(0) += 1;
            }
            for found_match in matches {
                found
                    .entry(candidates[found_match.index])
                    .or_insert_with(|| scan.at.clone());
            }
        }
    }
    (found, hits)
}

/// Top row, left to right, is 1–6. Bottom row, left to right, is 7–12.
pub fn seat_number(index: usize) -> usize {
    index + 1
}

pub fn format_hit(read_text: &str, entry_name: &str, note: &str) -> String {
    let mut line = format!("读到「{read_text}」，是黑名单里的「{entry_name}」");
    if !note.trim().is_empty() {
        line.push_str(&format!("。{}", note.trim()));
    }
    line
}
