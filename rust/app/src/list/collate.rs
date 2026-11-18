//! 名字 in the order a Chinese reader expects, as ui._ordered_entries gets it from QCollator (zh_CN, numeric mode):
//! signs first, then numbers by their value, then Chinese by pinyin, then letters without regard to case or accents.
//! A key per name, compared piece by piece; the golden order in collate_golden.json is what QCollator gave.
//! A character with two readings takes the one ICU's pinyin order files it under (READINGS), else the common one.

use std::cmp::Ordering;

use pinyin::ToPinyin;
use unicode_normalization::char::is_combining_mark;
use unicode_normalization::UnicodeNormalization;

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
enum Piece {
    /// Space and punctuation, then symbols: before everything else, as in the Unicode collation.
    Sign(bool, char),
    /// A run of digits, by its value (leading zeros dropped), then by its length.
    Number(String, usize),
    /// A Chinese character: its pinyin without tone, then the tone, then the character.
    Han(String, u8, char),
    /// A letter of the Latin or another alphabet: its base letter, case-blind; case and accents only break a tie.
    Letter(String),
}

/// Characters with more than one reading, filed under the reading ICU's zh pinyin order gives them.
const READINGS: [(char, &str, u8); 4] = [('重', "chong", 2), ('长', "zhang", 3), ('行', "xing", 2), ('乐', "le", 4)];

/// Signs the Unicode collation files as symbols, after punctuation.
const SYMBOLS: &str = "`^~+<=>|$¥￥°©®×÷";

fn pieces(name: &str) -> Vec<Piece> {
    let chars: Vec<char> = name.chars().collect();
    let mut out = Vec::with_capacity(chars.len());
    let mut at = 0;
    while at < chars.len() {
        let ch = chars[at];
        if ch.is_ascii_digit() {
            let start = at;
            while at < chars.len() && chars[at].is_ascii_digit() {
                at += 1;
            }
            let run: String = chars[start..at].iter().collect();
            let value = run.trim_start_matches('0');
            // Longer numbers are bigger: compare the length first, by padding to a common width.
            out.push(Piece::Number(format!("{:0>20}", value), run.len()));
            continue;
        }
        at += 1;
        if let Some(&(_, sound, tone)) = READINGS.iter().find(|(own, _, _)| *own == ch) {
            out.push(Piece::Han(sound.to_string(), tone, ch));
        } else if let Some(sound) = ch.to_pinyin() {
            let toned = sound.with_tone_num_end();
            let tone = toned.chars().last().and_then(|last| last.to_digit(10)).unwrap_or(5) as u8;
            out.push(Piece::Han(sound.plain().to_string(), tone, ch));
        } else if ch.is_alphanumeric() {
            let base: String = std::iter::once(ch).nfd().filter(|c| !is_combining_mark(*c)).collect();
            out.push(Piece::Letter(base.to_lowercase()));
        } else {
            out.push(Piece::Sign(SYMBOLS.contains(ch), ch));
        }
    }
    out
}

/// QCollator(zh_CN, numeric).compare, closely enough for player names.
pub fn compare(left: &str, right: &str) -> Ordering {
    pieces(left).cmp(&pieces(right)).then_with(|| left.cmp(right))
}
