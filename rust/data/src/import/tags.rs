//! The 标签 and 原因 rules of storage.py that importing uses, and its 分享 format.

use std::sync::LazyLock;

use regex::Regex;

use super::text::{clean_stored_name, fold, head, len, splitlines, strip};

/// storage.TAGS: the built-in 标签.
pub const TAGS: [&str; 5] = ["炸房", "贴脸", "挂机", "场外", "不尊重底牌"];
pub const MAX_TAG: usize = 12;
pub const MAX_NAME: usize = 64;
pub const MAX_NOTE: usize = 200;
pub const SHARE_MARK: &str = "#模仿者小工具 黑名单";
pub const OLD_SHARE_MARKS: [&str; 1] = ["#黑名单检测 名单"];
const REASON_MARK: &str = "原因：";

/// storage.clean_tag.
pub fn clean_tag(raw: &str) -> String {
    let text: String = strip(raw).chars().filter(|ch| !",，、:： \t\r\n".contains(*ch)).collect();
    if text.is_empty() || text == "其他" {
        return String::new();
    }
    head(&text, MAX_TAG).to_string()
}

/// storage.order_tags: the catalog's 标签 first, in its order, then the rest.
pub fn order_tags<S: AsRef<str>>(tags: &[S], catalog: &[String]) -> Vec<String> {
    let mut chosen: Vec<String> = catalog.iter().filter(|tag| tags.iter().any(|t| t.as_ref() == *tag)).cloned().collect();
    for tag in tags {
        if !chosen.iter().any(|c| c == tag.as_ref()) {
            chosen.push(tag.as_ref().to_string());
        }
    }
    chosen
}

/// storage.is_shared: a paste copied with 分享.
pub fn is_shared(text: &str) -> bool {
    splitlines(text).iter().any(|line| {
        let line = strip(line);
        line.starts_with(SHARE_MARK) || OLD_SHARE_MARKS.iter().any(|mark| line.starts_with(mark))
    })
}

static COMMA: LazyLock<Regex> = LazyLock::new(|| Regex::new("[,，]").unwrap());

/// storage.parse_shared: every part before 原因： is a 标签.
pub fn parse_shared(text: &str) -> Vec<(String, Vec<String>, String)> {
    let mut rows = Vec::new();
    let mut seen = std::collections::HashSet::new();
    for raw in splitlines(text) {
        let line = strip(raw);
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let parts: Vec<&str> = COMMA.split(line).map(strip).collect();
        let name = head(&clean_stored_name(parts[0]), MAX_NAME).to_string();
        let key = fold(&name);
        if key.is_empty() || !seen.insert(key) {
            continue;
        }
        let mut tags: Vec<String> = Vec::new();
        let mut reason = String::new();
        for (index, part) in parts.iter().enumerate().skip(1) {
            if let Some(after) = part.strip_prefix(REASON_MARK) {
                let mut joined = vec![after];
                joined.extend(&parts[index + 1..]);
                reason = strip(&joined.join("，")).to_string();
                break;
            }
            let tag = clean_tag(part);
            if !tag.is_empty() && !tags.contains(&tag) {
                tags.push(tag);
            }
        }
        rows.push((name, tags, head(&reason, MAX_NOTE).to_string()));
    }
    rows
}

/// storage.merge_reason: two 原因 as one, none said twice.
pub fn merge_reason(old: &str, new: &str) -> String {
    let (old, new) = (strip(old), strip(new));
    if new.is_empty() || old.contains(new) {
        return old.to_string();
    }
    if old.is_empty() || new.contains(old) {
        return head(new, MAX_NOTE).to_string();
    }
    head(&format!("{old}；{new}"), MAX_NOTE).to_string()
}

static SEPARATORS: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[,，、:：\s\x1c-\x1f]+").unwrap());

/// storage.tags_and_reason: the known 标签 in a text; the text stays the 原因 unless it is only 标签.
pub fn tags_and_reason(text: &str, catalog: &[String]) -> (Vec<String>, String) {
    let joined: String = splitlines(text).into_iter().map(strip).collect();
    let raw = strip(&joined);
    if raw.is_empty() {
        return (Vec::new(), String::new());
    }
    let mut by_length: Vec<&String> = catalog.iter().collect();
    by_length.sort_by_key(|tag| std::cmp::Reverse(len(tag)));
    let mut found: Vec<String> = Vec::new();
    for tag in by_length {
        if !tag.is_empty() && raw.contains(tag.as_str()) && !found.contains(tag) {
            found.push(tag.clone());
        }
    }
    let ordered = order_tags(&found, catalog);
    let mut stripped = raw.to_string();
    for tag in &ordered {
        stripped = stripped.replace(tag.as_str(), "");
    }
    if SEPARATORS.replace_all(&stripped, "").is_empty() {
        return (ordered, String::new());
    }
    (ordered, head(raw, MAX_NOTE).to_string())
}
