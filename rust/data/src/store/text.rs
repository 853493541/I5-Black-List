//! Names, tags and hotkeys as the store keeps them: match.py's fold and clean_stored_name, storage.py's tag helpers,
//! hotkey.py's parse_hotkey and two_keys, and love_scenes' keys.

use super::py::{cut, is_space, strip};
use unicode_general_category::{get_general_category as category, GeneralCategory as G};
use unicode_normalization::UnicodeNormalization;

pub const MIN_PREFIX_CHARS: usize = 4;
pub const MAX_NAME: usize = 64;
pub const MAX_NOTE: usize = 200;
pub const TAGS: [&str; 5] = ["炸房", "贴脸", "挂机", "场外", "不尊重底牌"];
const MAX_TAG: usize = 12;

/// love_scenes.KEYS, in 设置's order.
pub const SCENE_KEYS: [&str; 11] = ["classic", "lace", "ice", "stars", "cyber", "neon", "angel", "equation", "fluffy", "claw", "lyre"];

/// love_scenes.shown: a scene that was replaced is its replacement.
pub fn shown(key: &str) -> String {
    if key == "champagne" { "angel".into() } else { key.into() }
}

/// match.normalize_text: NFKC, no whitespace.
pub fn normalize(raw: &str) -> String {
    raw.nfkc().filter(|c| *c != '\u{3000}' && !is_space(*c)).collect()
}

fn letter_or_number(c: char) -> bool {
    matches!(
        category(c),
        G::UppercaseLetter
            | G::LowercaseLetter
            | G::TitlecaseLetter
            | G::ModifierLetter
            | G::OtherLetter
            | G::DecimalNumber
            | G::LetterNumber
            | G::OtherNumber
    )
}

/// match.strip_noise: letters and numbers only.
pub fn strip_noise(text: &str) -> String {
    normalize(text).chars().filter(|c| letter_or_number(*c)).collect()
}

/// match.fold: the comparison form.
pub fn fold(text: &str) -> String {
    caseless::default_case_fold_str(&strip_noise(text))
}

/// match.split_ellipsis: the visible text, without a trailing ellipsis or the single dot it is sometimes read as.
pub fn split_ellipsis(raw: &str) -> (String, bool) {
    let mut chars: Vec<char> = normalize(raw).chars().collect();
    let mut truncated = false;
    loop {
        match chars.last() {
            Some('…' | '⋯') => {
                chars.pop();
            }
            Some(&c @ ('.' | '·' | '。')) => {
                let run = chars.iter().rev().take_while(|x| **x == c).count();
                if run < 2 {
                    break;
                }
                chars.truncate(chars.len() - run);
            }
            _ => break,
        }
        truncated = true;
    }
    if matches!(chars.last(), Some('.' | '。' | '·')) {
        chars.pop();
        truncated = true;
    }
    (chars.into_iter().collect(), truncated)
}

/// match.clean_stored_name.
pub fn clean_stored_name(raw: &str) -> String {
    strip_noise(&split_ellipsis(raw).0)
}

/// storage._same_person.
pub fn same_person(left: &str, right: &str) -> bool {
    if left == right {
        return true;
    }
    let (short, long) = if left.chars().count() <= right.chars().count() { (left, right) } else { (right, left) };
    short.chars().count() >= MIN_PREFIX_CHARS && long.starts_with(short)
}

/// storage.clean_tag.
pub fn clean_tag(raw: &str) -> String {
    let text: String = strip(raw).chars().filter(|c| !",，、:： \t\r\n".contains(*c)).collect();
    if text.is_empty() || text == "其他" { String::new() } else { cut(&text, MAX_TAG) }
}

/// storage.order_tags: the catalog's tags first, in its order, then the rest.
pub fn order_tags<S: AsRef<str>>(tags: &[String], catalog: &[S]) -> Vec<String> {
    let mut chosen: Vec<String> = catalog.iter().map(|t| t.as_ref().to_string()).filter(|t| tags.contains(t)).collect();
    for tag in tags {
        if !chosen.contains(tag) {
            chosen.push(tag.clone());
        }
    }
    chosen
}

/// storage.coerce_tags.
pub fn coerce_tags(tags: &[String], reason: &str) -> (Vec<String>, String) {
    let mut picked: Vec<String> = Vec::new();
    for raw in tags {
        let tag = clean_tag(raw);
        if !tag.is_empty() && !picked.contains(&tag) {
            picked.push(tag);
        }
    }
    (order_tags(&picked, &TAGS), cut(strip(reason), MAX_NOTE))
}

/// storage._clean_nickname: one line, short.
pub fn clean_nickname(raw: &str) -> String {
    cut(&raw.split(is_space).filter(|p| !p.is_empty()).collect::<Vec<_>>().join(" "), MAX_NAME)
}

/// storage.merge_reason.
pub fn merge_reason(old: &str, new: &str) -> String {
    let (old, new) = (strip(old), strip(new));
    if new.is_empty() || old.contains(new) {
        return old.to_string();
    }
    if old.is_empty() || new.contains(old) {
        return cut(new, MAX_NOTE);
    }
    cut(&format!("{old}；{new}"), MAX_NOTE)
}

/// storage.tags_and_reason: known tags pulled out of an explanation; the rest stays the reason.
pub fn tags_and_reason(text: &str, catalog: &[String]) -> (Vec<String>, String) {
    let raw: String = text.lines().map(strip).collect::<String>();
    let raw = strip(&raw).to_string();
    if raw.is_empty() {
        return (Vec::new(), String::new());
    }
    let mut by_len: Vec<&String> = catalog.iter().collect();
    by_len.sort_by_key(|t| std::cmp::Reverse(t.chars().count()));
    let mut found: Vec<String> = Vec::new();
    for tag in by_len {
        if !tag.is_empty() && raw.contains(tag.as_str()) && !found.contains(tag) {
            found.push(tag.clone());
        }
    }
    let ordered = order_tags(&found, catalog);
    let mut stripped = raw.clone();
    for tag in &ordered {
        stripped = stripped.replace(tag.as_str(), "");
    }
    if stripped.chars().all(|c| ",，、:：".contains(c) || is_space(c)) {
        return (ordered, String::new());
    }
    (ordered, cut(&raw, MAX_NOTE))
}

const MODIFIER_ORDER: [&str; 4] = ["Ctrl", "Alt", "Shift", "Win"];

fn modifier(piece: &str) -> Option<&'static str> {
    match piece.to_lowercase().as_str() {
        "ctrl" | "control" => Some("Ctrl"),
        "alt" => Some("Alt"),
        "shift" => Some("Shift"),
        "win" | "meta" | "super" => Some("Win"),
        _ => None,
    }
}

fn canonical_key(part: &str) -> Option<String> {
    let token = strip(part);
    let mut chars = token.chars();
    if let (Some(c), None) = (chars.next(), chars.next()) {
        if c.is_ascii_alphanumeric() {
            return Some(c.to_ascii_uppercase().to_string());
        }
    }
    let upper = token.to_uppercase();
    let digits = upper.strip_prefix('F')?;
    if !digits.is_empty() && digits.chars().all(|c| c.is_ascii_digit()) {
        let n: u32 = digits.parse().ok()?;
        if (1..=12).contains(&n) {
            return Some(format!("F{n}"));
        }
    }
    None
}

fn everyday(modifiers: &[&str], key: &str) -> bool {
    if key.chars().count() == 1 && matches!(modifiers, [] | ["Shift"] | ["Win"]) {
        return true;
    }
    let combo = [modifiers.join("+"), key.to_string()].iter().filter(|s| !s.is_empty()).cloned().collect::<Vec<_>>().join("+");
    let ctrl_letter = combo.strip_prefix("Ctrl+").is_some_and(|k| k.len() == 1 && "ACFNOPSTVWXYZ".contains(k));
    ctrl_letter || matches!(combo.as_str(), "Alt+F4" | "Ctrl+F4" | "Shift+F10")
}

/// hotkey.parse_hotkey: the hotkey as shown, with its modifiers in order. None for no hotkey or one in everyday use.
pub fn parse_hotkey(text: &str) -> Option<(String, Vec<&'static str>)> {
    let raw = strip(text);
    if raw.is_empty() {
        return None;
    }
    let mut modifiers: Vec<&'static str> = Vec::new();
    let mut key: Option<String> = None;
    for part in raw.split('+') {
        let piece = strip(part);
        if piece.is_empty() {
            return None;
        }
        if let Some(m) = modifier(piece) {
            if !modifiers.contains(&m) {
                modifiers.push(m);
            }
            continue;
        }
        if key.is_some() {
            return None;
        }
        key = Some(canonical_key(piece)?);
    }
    let key = key?;
    let ordered: Vec<&'static str> = MODIFIER_ORDER.iter().copied().filter(|m| modifiers.contains(m)).collect();
    if key == "F12" && ordered.is_empty() || everyday(&ordered, &key) {
        return None;
    }
    let mut parts: Vec<&str> = ordered.clone();
    parts.push(&key);
    Some((parts.join("+"), ordered))
}

/// hotkey.two_keys: a modifier and a key at most.
pub fn two_keys(text: &str) -> String {
    match parse_hotkey(text) {
        Some((display, mods)) if mods.len() > 1 => format!("{}+{}", mods[0], display.rsplit('+').next().unwrap_or("")),
        _ => text.to_string(),
    }
}
