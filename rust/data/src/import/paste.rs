//! How a paste is cut into blocks and pieces: importing._sections, _table_row and _pieces.

use std::sync::LazyLock;

use regex::Regex;

use super::text::{len, splitlines, split_ws, strip, strip_chars};

pub const OPEN: char = '（';
pub const CLOSE: char = '）';
/// Longer than this is not a player name: the game's names are short.
pub const NAME_MAX: usize = 8;

fn re(pattern: &str) -> Regex {
    // Python's \s also takes \x1c-\x1f; Rust's does not.
    let pattern = pattern.replace(r"\S", r"[^\s\x1c-\x1f]").replace(r"\s", r"[\s\x1c-\x1f]");
    Regex::new(&pattern).unwrap()
}

macro_rules! regex {
    ($name:ident, $pattern:expr) => {
        pub static $name: LazyLock<Regex> = LazyLock::new(|| re($pattern));
    };
}

// The third choice stands for \d{1,3}\s+(?=\S): list_mark checks what follows.
regex!(LIST_MARK, r"^\s*(?:\d{1,3}\s*[.、．)）:：]\s*|[①-⑳]\s*[.、．)）:：]?\s*|(\d{1,3}\s+)|[-•·*●▪]\s*)");
regex!(STAMP, r"\d{4}\s*[/.\-年]\s*\d{1,2}\s*[/.\-月]\s*\d{1,2}日?|\d{1,2}:\d{2}(?::\d{2})?");
regex!(NAME_SPLIT, r"[，,、；;/|\s]+");
regex!(NAME_NOTE, r"^\s*([^:：\-—－~～\s，,、；;/|]+)\s*[:：\-—－~～]+\s*(.+)$");
regex!(OTHER, r"^其他[:：]?");
regex!(NAME_LABEL, r"^(?:游戏\s*ID|ID|Id|id|游戏名|角色名|角色|昵称|名字|名称|玩家)\s*[:：]\s*");
regex!(REASON_LABEL, r"\s*[，,]?\s*(?:原因|理由|备注|说明)\s*[:：]\s*");
regex!(RULE_CELL, r"^:?-{2,}:?$");
regex!(DECOR, r"^[\s\x{2190}-\x{2bff}\x{2600}-\x{27bf}\x{1F000}-\x{1FAFF}\x{FE0F}\x{200d}★☆◆◇■□▶►→⇒>*#@]+");
regex!(TITLE, r"名单|避雷|以下|汇总|整理|持续更新");
regex!(JOINED_NAMES, r"^(\S+[/、，,；;|]\S+)\s+(\S.*)$");
regex!(HEADING_WORDS, r"名单|避雷|以下|汇总|整理|其他|其它");
regex!(REASON_WORDS, "送人头|骂人|喷人|嘴臭|摆烂|秒退|傻逼|弱智|故意|不救|带节奏|白给|恶心|坑人|乱报|演戏|卖队友|搞心态|报点|不报|逃跑|退出");

const HEADER_CELLS: [&str; 17] =
    ["名字", "名称", "昵称", "id", "游戏名", "游戏id", "角色", "角色名", "玩家", "原因", "理由", "备注", "说明", "标签", "时间", "序号", "编号"];
/// Not whitespace to the name splitter, so a space between two English words survives the split.
pub const KEEP_SPACE: char = '\u{e000}';

/// _LIST_MARK.sub("", text, count=1): a list number or bullet in front taken off.
pub fn list_mark(text: &str) -> &str {
    match LIST_MARK.captures(text) {
        // (?=\S): the number and its spaces count only with something after them.
        Some(caps) if caps.get(1).is_some() && caps.get(0).unwrap().end() == text.len() => text,
        Some(caps) => &text[caps.get(0).unwrap().end()..],
        None => text,
    }
}

/// _BRACKETS: ( ) 【 】 [ ] read as （ ）.
pub fn brackets(text: &str) -> String {
    text.chars()
        .map(|ch| match ch {
            '(' | '【' | '[' => OPEN,
            ')' | '】' | ']' => CLOSE,
            other => other,
        })
        .collect()
}

/// _LATIN_SPACE.sub(_KEEP_SPACE, text): Lucky Star stays one name.
fn keep_latin_spaces(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    let latin = |at: Option<&char>| at.is_some_and(|ch| ch.is_ascii_alphanumeric());
    (0..chars.len())
        .map(|i| {
            let joins = chars[i] == ' ' && i > 0 && latin(chars.get(i - 1)) && latin(chars.get(i + 1));
            if joins { KEEP_SPACE } else { chars[i] }
        })
        .collect()
}

pub fn split_names(text: &str) -> Vec<String> {
    NAME_SPLIT.split(&keep_latin_spaces(text)).filter(|w| !w.is_empty()).map(str::to_string).collect()
}

fn split_words(text: &str) -> Vec<&str> {
    NAME_SPLIT.split(text).filter(|w| !w.is_empty()).collect()
}

pub fn ends_colon(text: &str) -> bool {
    text.ends_with([':', '：'])
}

/// The 标签 when text is nothing but 标签, else None.
fn tags_only(text: &str, catalog: &[String]) -> Option<Vec<String>> {
    let words = split_words(strip_chars(text, " :："));
    if words.is_empty() || !words.iter().all(|w| catalog.iter().any(|t| t == w)) {
        return None;
    }
    let mut unique: Vec<String> = Vec::new();
    for word in words {
        if !unique.iter().any(|u| u == word) {
            unique.push(word.to_string());
        }
    }
    Some(unique)
}

/// A spreadsheet or Markdown row as 名字：原因; "" for a header or rule row; None if not a row.
fn table_row(line: &str) -> Option<String> {
    if !line.contains('\t') && !strip(line).starts_with('|') {
        return None;
    }
    let cells: Vec<&str> = strip_chars(strip(line), "|").split(['|', '\t']).map(strip).filter(|c| !c.is_empty()).collect();
    if cells.is_empty() || cells.iter().all(|c| RULE_CELL.is_match(c)) {
        return Some(String::new());
    }
    if cells.iter().all(|c| HEADER_CELLS.contains(&super::text::lower(c).as_str())) {
        return Some(String::new());
    }
    Some(if cells.len() == 1 { cells[0].to_string() } else { format!("{}：{}", cells[0], cells[1..].join("，")) })
}

fn dedupe(tags: impl IntoIterator<Item = String>) -> Vec<String> {
    let mut unique: Vec<String> = Vec::new();
    for tag in tags {
        if !unique.contains(&tag) {
            unique.push(tag);
        }
    }
    unique
}

/// The paste in blocks, each with the 标签 a heading line gives all the names in it.
pub fn sections(text: &str, catalog: &[String]) -> Vec<(String, Vec<String>)> {
    let mut blocks: Vec<(String, Vec<String>)> = Vec::new();
    let mut lines: Vec<String> = Vec::new();
    let mut heading: Vec<String> = Vec::new();
    let mut pending = String::new();
    let close = |blocks: &mut Vec<(String, Vec<String>)>, lines: &mut Vec<String>, heading: &[String]| {
        if !lines.is_empty() {
            blocks.push((lines.join("\n"), heading.to_vec()));
            lines.clear();
        }
    };
    let translated = brackets(text);
    for raw in splitlines(&translated) {
        let undecorated = DECOR.replace(raw, "");
        let mut line = strip(list_mark(&undecorated)).to_string();
        if let Some(row) = table_row(&line) {
            line = row;
        }
        line = NAME_LABEL.replace(&line, "").into_owned();
        if line.is_empty() {
            lines.push(String::new());
            continue;
        }
        if let Some(named) = tags_only(&line, catalog) {
            if ends_colon(&line) || split_names(strip_chars(&line, " :：")).len() == named.len() {
                // 炸房： heads the names under it.
                close(&mut blocks, &mut lines, &heading);
                heading = named;
                continue;
            }
        }
        if ends_colon(&line) && !line.contains(CLOSE) && HEADING_WORDS.is_match(&line) {
            // 以下是黑名单： is a heading, with no 标签.
            close(&mut blocks, &mut lines, &heading);
            heading = Vec::new();
            pending.clear();
            continue;
        }
        if !pending.is_empty() {
            line = std::mem::take(&mut pending) + &line;
        } else if ends_colon(&line) && !line.contains(CLOSE) && len(line.trim_end_matches([':', '：', ' '])) <= NAME_MAX {
            // 小明： with the 原因 on the next line.
            pending = line;
            continue;
        }
        if line.starts_with(OPEN) && line.contains(CLOSE) {
            let (inside, rest) = line[OPEN.len_utf8()..].split_once(CLOSE).unwrap();
            if let Some(lead) = tags_only(inside, catalog) {
                if !strip(rest).is_empty() {
                    // 【炸房】小明 小红: the names on this line get the 标签.
                    close(&mut blocks, &mut lines, &heading);
                    blocks.push((rest.to_string(), dedupe(heading.iter().cloned().chain(lead))));
                    continue;
                }
            }
        }
        // 名字 原因：说明 is 名字：说明. Inside brackets the label is dropped where the 原因 is read.
        if !line.contains(OPEN) {
            if let Some(found) = REASON_LABEL.find(&line) {
                let before = strip(&line[..found.start()]);
                if !before.is_empty() {
                    line = format!("{before}：{}", &line[found.end()..]);
                }
            }
        }
        lines.push(line);
    }
    if !pending.is_empty() {
        lines.push(pending);
    }
    close(&mut blocks, &mut lines, &heading);
    blocks
}

/// (names, 原因 or None, from a chat header line) in the order the paste has them.
pub fn pieces(text: &str) -> Vec<(String, Option<String>, bool)> {
    let translated = brackets(text);
    let lines = splitlines(&translated);
    let mut pieces: Vec<(String, Option<String>, bool)> = Vec::new();
    let mut index = 0;
    while index < lines.len() {
        let mut rest = list_mark(lines[index]).to_string();
        let header = STAMP.is_match(&rest);
        if header {
            rest = STAMP.replace_all(&rest, " ").into_owned();
        }
        index += 1;
        while !strip(&rest).is_empty() {
            let Some(opening) = rest.find(OPEN) else {
                pieces.push((rest.clone(), None, header));
                break;
            };
            let names = rest[..opening].to_string();
            let after_open = opening + OPEN.len_utf8();
            let mut note;
            if let Some(closing) = rest[after_open..].find(CLOSE).map(|at| at + after_open) {
                note = rest[after_open..closing].to_string();
                let tail = rest[closing + CLOSE.len_utf8()..].trim_start_matches(['，', ',', '、', '；', ';', ' ']);
                rest = list_mark(tail).to_string();
            } else {
                note = rest[after_open..].to_string();
                rest = String::new();
                // Look ahead for the ） that closes it.
                let mut ahead = index;
                while ahead < lines.len() && !lines[ahead].contains(OPEN) && !lines[ahead].contains(CLOSE) {
                    ahead += 1;
                }
                let line = lines.get(ahead).copied().unwrap_or("");
                if let Some(close_at) = line.find(CLOSE) {
                    if line.find(OPEN).is_none_or(|open_at| close_at < open_at) {
                        note += &lines[index..ahead].concat();
                        note += &line[..close_at];
                        rest = line[close_at + CLOSE.len_utf8()..].to_string();
                        index = ahead + 1;
                    }
                }
            }
            if strip_chars(&names, "） \t").is_empty() {
                if let Some((_, Some(last_note), _)) = pieces.last_mut() {
                    // 名字（原因）（还有） is one person with a longer 原因.
                    *last_note = format!("{last_note}，{note}");
                    continue;
                }
            }
            pieces.push((names, Some(note), header));
        }
    }
    pieces
}

/// How much of the game's name room this takes: an English letter or digit is half a Chinese character.
pub fn width_halves(name: &str) -> usize {
    name.chars().map(|ch| if ch.is_ascii() { 1 } else { 2 }).sum()
}

pub fn split_spaced(text: &str) -> Vec<&str> {
    split_ws(text)
}
