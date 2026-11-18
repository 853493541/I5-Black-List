//! The lines of 直播姬's log that say what its canvas is (livehime_layout._read and its patterns, matched by hand
//! as Python's `re` matches them).

#![forbid(unsafe_code)]

use super::layout::Studio;

/// Python's str.splitlines(): every line break Python knows, no empty line after a last break.
pub fn splitlines(text: &str) -> Vec<&str> {
    let mut lines = Vec::new();
    let mut start = 0;
    let mut chars = text.char_indices().peekable();
    while let Some((at, c)) = chars.next() {
        let breaks = matches!(c, '\n' | '\r' | '\x0b' | '\x0c' | '\x1c' | '\x1d' | '\x1e' | '\u{85}' | '\u{2028}' | '\u{2029}');
        if !breaks {
            continue;
        }
        lines.push(&text[start..at]);
        let mut next = at + c.len_utf8();
        if c == '\r' && chars.peek().is_some_and(|&(_, n)| n == '\n') {
            chars.next();
            next += 1;
        }
        start = next;
    }
    if start < text.len() {
        lines.push(&text[start..]);
    }
    lines
}

fn digits(text: &str, count: usize) -> Option<&str> {
    let part = text.get(..count)?;
    part.bytes().all(|b| b.is_ascii_digit()).then_some(part)
}

/// "MMDD HHMMSS" from a line's stamp: 直播姬 8.2's `[17476:1014/002232.668:...` at the start, or 7.64's
/// `2026-10-14/14-39-08` in its first 80 characters; "" when it has none.
pub fn stamp(line: &str) -> String {
    if let Some(rest) = line.strip_prefix('[') {
        let lead = rest.bytes().take_while(u8::is_ascii_digit).count();
        if lead > 0 {
            let rest = &rest[lead..];
            if let Some(rest) = rest.strip_prefix(':') {
                if let (Some(day), Some(time)) = (digits(rest, 4), rest.get(4..).and_then(|r| r.strip_prefix('/')).and_then(|r| digits(r, 6))) {
                    return format!("{day} {time}");
                }
            }
        }
    }
    let head: String = line.chars().take(80).collect();
    let chars: Vec<char> = head.chars().collect();
    let shape = "dddd-dd-dd/dd-dd-dd";
    for start in 0..chars.len().saturating_sub(shape.len() - 1) {
        let window = &chars[start..start + shape.len()];
        let fits = shape.chars().zip(window).all(|(want, &got)| if want == 'd' { got.is_ascii_digit() } else { want == got });
        if fits {
            let at = |from: usize, to: usize| window[from..to].iter().collect::<String>();
            return format!("{}{} {}{}{}", at(5, 7), at(8, 10), at(11, 13), at(14, 16), at(17, 19));
        }
    }
    String::new()
}

fn lead_digits(text: &str) -> &str {
    &text[..text.bytes().take_while(u8::is_ascii_digit).count()]
}

/// `is_double_screen-(\d) main_width-(\d+) main_height-(\d+)`: (double screen, width, height).
fn canvas(line: &str) -> Option<(bool, i64, i64)> {
    const HEAD: &str = "is_double_screen-";
    line.match_indices(HEAD).find_map(|(at, _)| {
        let rest = &line[at + HEAD.len()..];
        let double = digits(rest, 1)?;
        let rest = rest[1..].strip_prefix(" main_width-")?;
        let width = lead_digits(rest);
        let rest = rest[width.len()..].strip_prefix(" main_height-")?;
        let height = lead_digits(rest);
        if width.is_empty() || height.is_empty() {
            return None;
        }
        Some((double == "1", width.parse().ok()?, height.parse().ok()?))
    })
}

/// `BililiveOBSView::OnLiveProgramModeChanged : (\d)`
fn program(line: &str) -> Option<bool> {
    const HEAD: &str = "BililiveOBSView::OnLiveProgramModeChanged : ";
    line.match_indices(HEAD).find_map(|(at, _)| digits(&line[at + HEAD.len()..], 1)).map(|d| d == "1")
}

/// `scene '.*' (?:add|remove) item : `
fn edit(line: &str) -> bool {
    let Some(at) = line.find("scene '") else { return false };
    let from = at + "scene '".len();
    ["' add item : ", "' remove item : "].iter().any(|tail| line[from..].contains(tail))
}

/// `found`, brought up to date with these log lines; a new start of 直播姬 begins afresh.
pub fn read_log(mut found: Studio, text: &str) -> Studio {
    for line in splitlines(text) {
        if line.contains("--- Application Startup ---") {
            found = Studio::default();
            continue;
        }
        if let Some((double, width, height)) = canvas(line) {
            found.double_screen = Some(double);
            found.canvas = Some((width, height));
        }
        if let Some(on) = program(line) {
            found.two_canvas = Some(on);
        }
        if line.contains("[ProgramMode] ButtonPressed OpenProgramView") {
            let when = stamp(line);
            if !when.is_empty() {
                found.synced = when;
            }
        } else if edit(line) {
            let when = stamp(line);
            if !when.is_empty() {
                found.edited = when;
            }
        }
    }
    found
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stamps_of_both_versions() {
        assert_eq!(stamp("[17476:1014/002232.668:INFO] x"), "1014 002232");
        assert_eq!(stamp("[tid:8:2026-10-14/14-39-08:INFO]"), "1014 143908");
        assert_eq!(stamp("no stamp"), "");
    }

    #[test]
    fn lines_split_as_python_splits_them() {
        assert_eq!(splitlines("a\r\nb\rc\u{2028}d\n"), vec!["a", "b", "c", "d"]);
        assert!(edit("scene '' add item : y") && !edit("scene ' add item : y"));
    }
}
