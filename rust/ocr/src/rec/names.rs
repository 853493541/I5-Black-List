//! read_names of blacklist_detect/ocr_engine.py: every name strip read in one pass on its prepared line, and the
//! strips that read blank read again on the plain line, the surer of the two kept.

use opencv::core::Mat;
use opencv::prelude::*;

use super::prepare::{prepare_name_line, prepare_name_line_plain};
use super::{Read, Recognizer, Result};

/// Python's str.split() whitespace: Unicode White_Space plus the separators U+001C to U+001F.
fn is_py_space(ch: char) -> bool {
    ch.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&ch)
}

/// _recognition_text for one read: whitespace dropped; an empty text reads as ("", 0.0).
pub fn clean(read: &Read) -> Read {
    let cleaned: String = read.0.chars().filter(|&ch| !is_py_space(ch)).collect();
    if cleaned.is_empty() || read.1 < 0.0 {
        return (String::new(), 0.0);
    }
    (cleaned, read.1)
}

/// _letters: casefolded letters, digits and CJK ideographs only.
fn letters(text: &str) -> String {
    text.chars()
        .flat_map(char::to_lowercase)
        .filter(|&ch| ch.is_alphanumeric() || ('\u{4e00}'..='\u{9fff}').contains(&ch))
        .collect()
}

/// choose_name_read: keep the surer read of the same strip. A small confidence edge does not replace the primary.
pub fn choose_name_read(primary: Read, alternate: Read) -> Read {
    if alternate.0.is_empty() {
        return primary;
    }
    if primary.0.is_empty() {
        return alternate;
    }
    if letters(&primary.0) == letters(&alternate.0) {
        return if primary.1 >= alternate.1 { primary } else { alternate };
    }
    if alternate.1 >= primary.1 + 0.08 {
        return alternate;
    }
    primary
}

/// read_names: one read per strip (RGB). Strips smaller than 4 px either way read as ("", 0.0).
pub fn read_names(rec: &mut Recognizer, images: &[Mat]) -> Result<Vec<Read>> {
    let mut results: Vec<Read> = vec![(String::new(), 0.0); images.len()];
    let mut prepared = Vec::new();
    let mut indexes = Vec::new();
    for (index, rgb) in images.iter().enumerate() {
        if rgb.empty() || rgb.rows() < 4 || rgb.cols() < 4 {
            continue;
        }
        prepared.push(prepare_name_line(rgb)?);
        indexes.push(index);
    }
    if prepared.is_empty() {
        return Ok(results);
    }
    let mut blank = Vec::new();
    for (&slot, first) in indexes.iter().zip(rec.read(&prepared)?) {
        results[slot] = clean(&first);
        if results[slot].0.is_empty() {
            blank.push(slot);
        }
    }
    if blank.is_empty() {
        return Ok(results);
    }
    let plain = blank.iter().map(|&slot| prepare_name_line_plain(&images[slot])).collect::<Result<Vec<_>>>()?;
    for (&slot, second) in blank.iter().zip(rec.read(&plain)?) {
        results[slot] = choose_name_read(std::mem::take(&mut results[slot]), clean(&second));
    }
    Ok(results)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn read(text: &str, score: f64) -> Read {
        (text.to_string(), score)
    }

    #[test]
    fn choose_keeps_primary_on_small_edge() {
        assert_eq!(choose_name_read(read("ab", 0.9), read("cd", 0.95)), read("ab", 0.9));
        assert_eq!(choose_name_read(read("ab", 0.8), read("cd", 0.9)), read("cd", 0.9));
        assert_eq!(choose_name_read(read("Ab", 0.8), read("a b", 0.85)), read("a b", 0.85));
        assert_eq!(choose_name_read(read("", 0.0), read("x", 0.1)), read("x", 0.1));
        assert_eq!(choose_name_read(read("x", 0.1), read("", 0.0)), read("x", 0.1));
    }

    #[test]
    fn clean_drops_spaces_and_blank_reads() {
        assert_eq!(clean(&read(" 示 例 ", 0.7)), read("示例", 0.7));
        assert_eq!(clean(&read("  ", 0.7)), read("", 0.0));
    }
}
