//! match.py's name rules (normalize_text, split_ellipsis, strip_noise, fold, clean_stored_name) and the Python
//! text rules they rest on: NFKC, `str.isspace` (`\s`), Unicode categories and `str.casefold`.

use unicode_general_category::{get_general_category, GeneralCategory as G};
use unicode_normalization::UnicodeNormalization;

/// match.MIN_PREFIX_CHARS: a name cut short matches a listed one only from this many characters.
pub const MIN_PREFIX_CHARS: usize = 4;

/// `unicodedata.normalize("NFKC", text)`.
pub fn nfkc(text: &str) -> String {
    text.nfkc().collect()
}

/// Python's `str.isspace`, which is what `\s` matches in a `str` pattern: White_Space plus the
/// four separators U+001C to U+001F.
pub fn is_space(ch: char) -> bool {
    ch.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&ch)
}

/// The first letter of the Unicode category is L (a letter) or N (a number).
pub fn is_letter_or_number(ch: char) -> bool {
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

/// `str.casefold()`: full case folding.
pub fn casefold(text: &str) -> String {
    caseless::default_case_fold_str(text)
}

/// Drop every `\s` character.
pub fn drop_space(text: &str) -> String {
    text.chars().filter(|&ch| !is_space(ch)).collect()
}

/// match.normalize_text: NFKC, drop whitespace. Full-width Latin becomes half-width. Case is kept.
pub fn normalize_text(raw: &str) -> String {
    drop_space(&nfkc(raw).replace('\u{3000}', ""))
}

fn is_dot_kind(ch: char) -> bool {
    matches!(ch, '.' | '·' | '。')
}

/// The tail is wholly `…`, `⋯`, or runs of two or more of `.`, `·`, `。`.
fn is_ellipsis_tail(tail: &[char]) -> bool {
    if tail.is_empty() {
        return false;
    }
    let mut at = 0;
    while at < tail.len() {
        let ch = tail[at];
        let run = tail[at..].iter().take_while(|&&next| next == ch).count();
        let fits = matches!(ch, '…' | '⋯') || (is_dot_kind(ch) && run >= 2);
        if !fits {
            return false;
        }
        at += run;
    }
    true
}

/// Where `(?:…|⋯|\.{2,}|·{2,}|。{2,})+$` first matches, if it does.
fn ellipsis_start(chars: &[char]) -> Option<usize> {
    (0..chars.len()).find(|&start| is_ellipsis_tail(&chars[start..]))
}

/// match.split_ellipsis: the visible text and whether a trailing ellipsis was removed.
pub fn split_ellipsis(raw: &str) -> (String, bool) {
    let mut chars: Vec<char> = normalize_text(raw).chars().collect();
    let mut truncated = false;
    while let Some(start) = ellipsis_start(&chars) {
        chars.truncate(start);
        truncated = true;
    }
    // This lobby's ellipsis is sometimes read as a single dot.
    if chars.last().is_some_and(|&ch| is_dot_kind(ch)) {
        chars.pop();
        truncated = true;
    }
    (chars.into_iter().collect(), truncated)
}

/// match.strip_noise: drop punctuation and symbols. A backtick in the middle of a name is not part of it.
pub fn strip_noise(text: &str) -> String {
    normalize_text(text).chars().filter(|&ch| is_letter_or_number(ch)).collect()
}

/// match.fold: the comparison form. Latin letters compare case-insensitively. Chinese is unchanged.
pub fn fold(text: &str) -> String {
    casefold(&strip_noise(text))
}

/// match.clean_stored_name: the name as saved. A trailing ellipsis or a stray mark is not part of the name.
pub fn clean_stored_name(raw: &str) -> String {
    strip_noise(&split_ellipsis(raw).0)
}
