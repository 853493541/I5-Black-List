//! Python's string rules, as importing.py, storage.py and match.py use them: whitespace, splitlines,
//! strip, slicing by code point, and match.fold / clean_stored_name.

use unicode_general_category::{get_general_category, GeneralCategory as G};

pub use common::text::{clean_stored_name, fold, is_space, normalize_text, split_ellipsis, strip_noise};

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


/// Python's str.lower().
pub fn lower(text: &str) -> String {
    text.to_lowercase()
}
