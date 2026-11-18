//! Python's string rules, as importing.py, storage.py and match.py use them: whitespace, splitlines,
//! strip, slicing by code point, and match.fold / clean_stored_name.

use std::sync::LazyLock;

use regex::Regex;
use unicode_general_category::{get_general_category, GeneralCategory as G};
use unicode_normalization::UnicodeNormalization;

/// Python's str.isspace for one character: Unicode White_Space and the four separators \x1c-\x1f.
pub fn is_space(ch: char) -> bool {
    ch.is_whitespace() || ('\x1c'..='\x1f').contains(&ch)
}

/// Python's str.isdigit for a whole string: every character a digit, and at least one.
pub fn is_digits(text: &str) -> bool {
    !text.is_empty() && text.chars().all(is_digit)
}

fn is_digit(ch: char) -> bool {
    matches!(get_general_category(ch), G::DecimalNumber)
        || matches!(ch as u32,
            0xB2 | 0xB3 | 0xB9 | 0x2070 | 0x2074..=0x2079 | 0x2080..=0x2089 | 0x2460..=0x2468 | 0x2474..=0x247C
            | 0x2488..=0x2490 | 0x24EA | 0x24F5..=0x24FD | 0x24FF | 0x2776..=0x277E | 0x2780..=0x2788 | 0x278A..=0x2792)
}

/// Python's str.splitlines(): no line ends, and no empty last line for a trailing break.
pub fn splitlines(text: &str) -> Vec<&str> {
    let mut lines = Vec::new();
    let mut start = 0;
    let mut iter = text.char_indices().peekable();
    while let Some((at, ch)) = iter.next() {
        let breaks = matches!(ch, '\n' | '\r' | '\x0b' | '\x0c' | '\x1c' | '\x1d' | '\x1e' | '\u{85}' | '\u{2028}' | '\u{2029}');
        if !breaks {
            continue;
        }
        lines.push(&text[start..at]);
        let mut end = at + ch.len_utf8();
        if ch == '\r' {
            if let Some(&(_, '\n')) = iter.peek() {
                iter.next();
                end += 1;
            }
        }
        start = end;
    }
    if start < text.len() {
        lines.push(&text[start..]);
    }
    lines
}

/// Python's str.split() with no separator: runs of whitespace, no empty words.
pub fn split_ws(text: &str) -> Vec<&str> {
    text.split(is_space).filter(|word| !word.is_empty()).collect()
}

/// Python's str.strip().
pub fn strip(text: &str) -> &str {
    text.trim_matches(is_space)
}

/// Python's str.strip(chars).
pub fn strip_chars<'a>(text: &'a str, chars: &str) -> &'a str {
    text.trim_matches(|ch| chars.contains(ch))
}

/// Python's text[:count], counted in code points.
pub fn head(text: &str, count: usize) -> &str {
    match text.char_indices().nth(count) {
        Some((at, _)) => &text[..at],
        None => text,
    }
}

/// Python's len(text): code points.
pub fn len(text: &str) -> usize {
    text.chars().count()
}

/// match.normalize_text: NFKC, no whitespace.
pub fn normalize_text(raw: &str) -> String {
    raw.nfkc().filter(|&ch| ch != '\u{3000}' && !is_space(ch)).collect()
}

static ELLIPSIS: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?:…|⋯|\.{2,}|·{2,}|。{2,})+$").unwrap());
static SINGLE_DOT: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[.。·]$").unwrap());

/// match.split_ellipsis: the visible text, without a trailing ellipsis or a single dot.
pub fn split_ellipsis(raw: &str) -> (String, bool) {
    let mut text = normalize_text(raw);
    let mut truncated = false;
    while let Some(found) = ELLIPSIS.find(&text) {
        text.truncate(found.start());
        truncated = true;
    }
    if let Some(found) = SINGLE_DOT.find(&text) {
        text.truncate(found.start());
        truncated = true;
    }
    (text, truncated)
}

/// match.strip_noise: letters and numbers only.
pub fn strip_noise(text: &str) -> String {
    normalize_text(text).chars().filter(|&ch| letter_or_number(ch)).collect()
}

fn letter_or_number(ch: char) -> bool {
    matches!(
        get_general_category(ch),
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

/// match.fold: the comparison form, Latin letters case-folded.
pub fn fold(text: &str) -> String {
    caseless::default_case_fold_str(&strip_noise(text))
}

/// match.clean_stored_name: the name as saved.
pub fn clean_stored_name(raw: &str) -> String {
    strip_noise(&split_ellipsis(raw).0)
}

/// Python's str.lower().
pub fn lower(text: &str) -> String {
    text.to_lowercase()
}
