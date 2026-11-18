//! Python's text rules as the reference code relies on them: NFKC, `str.isspace` (`\s`), `\w`, `\d`,
//! Unicode categories and `str.casefold`.

use unicode_general_category::{get_general_category, GeneralCategory as G};
use unicode_normalization::UnicodeNormalization;

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

/// Python's `\w` in a `str` pattern: `str.isalnum()` or the underscore.
pub fn is_word(ch: char) -> bool {
    ch == '_' || is_letter_or_number(ch)
}

/// Python's `\d` in a `str` pattern: a decimal digit of any script (category Nd).
pub fn is_digit(ch: char) -> bool {
    get_general_category(ch) == G::DecimalNumber
}

/// The value of a decimal digit, as `int()` reads it. Every script's digits are runs of ten from 0
/// (a few runs sit back to back), so the value is the place in its run.
pub fn digit_value(ch: char) -> u32 {
    if ch.is_ascii_digit() {
        return ch as u32 - '0' as u32;
    }
    let mut code = ch as u32;
    let mut place = 0;
    while let Some(before) = code.checked_sub(1).and_then(char::from_u32) {
        if !is_digit(before) {
            break;
        }
        place += 1;
        code -= 1;
    }
    place % 10
}

/// `int(digits)` for a short run of decimal digits.
pub fn digits_value(digits: &[char]) -> i64 {
    digits
        .iter()
        .fold(0, |total, &ch| total * 10 + i64::from(digit_value(ch)))
}

/// `str.casefold()`: full case folding.
pub fn casefold(text: &str) -> String {
    caseless::default_case_fold_str(text)
}

/// Drop every `\s` character.
pub fn drop_space(text: &str) -> String {
    text.chars().filter(|&ch| !is_space(ch)).collect()
}

/// The length of the run of decimal digits starting at `start`.
pub fn digit_run(chars: &[char], start: usize) -> usize {
    chars[start.min(chars.len())..]
        .iter()
        .take_while(|&&ch| is_digit(ch))
        .count()
}

/// The positions where `needle` starts in `chars`, in order.
pub fn find_all(chars: &[char], needle: &str) -> Vec<usize> {
    let needle: Vec<char> = needle.chars().collect();
    if needle.is_empty() || chars.len() < needle.len() {
        return Vec::new();
    }
    (0..=chars.len() - needle.len())
        .filter(|&at| chars[at..at + needle.len()] == needle[..])
        .collect()
}
