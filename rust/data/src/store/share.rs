//! 分享: a list copied as text (storage.share_text) and read back by 批量添加 (parse_shared), and a warning line's
//! tags and reason (describe_entry).

use super::py::{cut, is_space, strip};
use super::text::{clean_stored_name, clean_tag, fold, order_tags, MAX_NAME, MAX_NOTE, TAGS};
use super::Entry;
pub use common::limits::{OLD_SHARE_MARKS, SHARE_MARK};

const REASON_MARK: &str = "原因：";

/// storage.tag_text.
pub fn tag_text(entry: &Entry) -> String {
    order_tags(&entry.tags, &TAGS).join("、")
}

/// storage.describe_entry: tags, then the written reason.
pub fn describe_entry(entry: &Entry) -> String {
    let (tags, reason) = (tag_text(entry), strip(&entry.reason));
    match (tags.is_empty(), reason.is_empty()) {
        (false, false) => format!("{tags}。原因：{reason}"),
        (true, false) => format!("原因：{reason}"),
        _ => tags,
    }
}

/// storage.share_text: 名字，炸房，贴脸，原因：说明, one line per player, under SHARE_MARK.
pub fn share_text(entries: &[Entry]) -> String {
    let mut lines = vec![format!("{SHARE_MARK} {}人", entries.len())];
    for entry in entries {
        let mut bits = vec![entry.name.clone()];
        bits.extend(order_tags(&entry.tags, &TAGS));
        let reason = entry.reason.split(is_space).filter(|p| !p.is_empty()).collect::<Vec<_>>().join(" ");
        if !reason.is_empty() {
            bits.push(format!("{REASON_MARK}{reason}"));
        }
        lines.push(bits.join("，"));
    }
    lines.join("\n")
}

/// storage.is_shared.
pub fn is_shared(text: &str) -> bool {
    text.lines().any(|line| {
        let line = strip(line);
        line.starts_with(SHARE_MARK) || OLD_SHARE_MARKS.iter().any(|m| line.starts_with(m))
    })
}

/// storage.parse_shared: (name, tags, reason) for each line; every part before 原因： is a tag.
pub fn parse_shared(text: &str) -> Vec<(String, Vec<String>, String)> {
    let mut rows = Vec::new();
    let mut seen: Vec<String> = Vec::new();
    for raw in text.lines() {
        let line = strip(raw);
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let parts: Vec<&str> = line.split([',', '，']).map(strip).collect();
        let name = cut(&clean_stored_name(parts[0]), MAX_NAME);
        let key = fold(&name);
        if key.is_empty() || seen.contains(&key) {
            continue;
        }
        seen.push(key);
        let (mut tags, mut reason) = (Vec::new(), String::new());
        for (index, part) in parts.iter().enumerate().skip(1) {
            if let Some(rest) = part.strip_prefix(REASON_MARK) {
                let mut all = vec![rest];
                all.extend(&parts[index + 1..]);
                reason = strip(&all.join("，")).to_string();
                break;
            }
            let tag = clean_tag(part);
            if !tag.is_empty() && !tags.contains(&tag) {
                tags.push(tag);
            }
        }
        rows.push((name, tags, cut(&reason, MAX_NOTE)));
    }
    rows
}
