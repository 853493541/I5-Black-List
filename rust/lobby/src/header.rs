//! The lobby's header lines: 推演成功, 模仿者狂欢（12人狂欢）, 倒计时 N 秒 and 准备就绪 N/12, as
//! `blacklist_detect/layout.py` finds them among the lines read.

use crate::model::{OcrLine, Rect};
use crate::text::{digit_run, digits_value, drop_space, find_all, is_space, is_word, nfkc};

/// `_norm`: NFKC, whitespace dropped.
pub fn norm(text: &str) -> String {
    drop_space(&nfkc(text))
}

/// `_plain`: a piece of text as `norm` gives it, without symbols: letters, digits, Chinese and colons stay.
pub fn plain(text: &str) -> String {
    norm(text)
        .chars()
        .filter(|&ch| is_word(ch) || ch == ':' || ch == '：')
        .collect()
}

pub fn center(rect: &Rect) -> (f64, f64) {
    ((rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0)
}

pub fn union(rects: &[Rect]) -> Rect {
    let mut out = rects[0];
    for rect in &rects[1..] {
        out = [
            out[0].min(rect[0]),
            out[1].min(rect[1]),
            out[2].max(rect[2]),
            out[3].max(rect[3]),
        ];
    }
    out
}

pub fn height(rect: &Rect) -> f64 {
    (rect[3] - rect[1]).max(0.0)
}

fn vertical_overlap(a: &Rect, b: &Rect) -> f64 {
    let overlap = a[3].min(b[3]) - a[1].max(b[1]);
    if overlap <= 0.0 {
        return 0.0;
    }
    let smaller = height(a).min(height(b));
    if smaller <= 0.0 {
        return 0.0;
    }
    overlap / smaller
}

pub fn x_overlap(a: &Rect, b: &Rect) -> f64 {
    a[2].min(b[2]) - a[0].max(b[0])
}

fn same_row(a: &Rect, b: &Rect) -> bool {
    if vertical_overlap(a, b) >= 0.45 {
        return true;
    }
    let ay = center(a).1;
    let by = center(b).1;
    (ay - by).abs() <= 0.45 * 8.0_f64.max(height(a).min(height(b)))
}

fn skip_space(chars: &[char], mut at: usize) -> usize {
    while chars.get(at).is_some_and(|&ch| is_space(ch)) {
        at += 1;
    }
    at
}

fn skip_colon(chars: &[char], at: usize) -> usize {
    if chars.get(at).is_some_and(|&ch| ch == ':' || ch == '：') {
        at + 1
    } else {
        at
    }
}

/// `倒计时\s*[:：]?\s*(\d{1,3})\s*秒`, searched: the seconds of the first place it matches.
pub fn countdown_search(text: &str) -> Option<i64> {
    let chars: Vec<char> = text.chars().collect();
    find_all(&chars, "倒计时").into_iter().find_map(|start| {
        let at = skip_space(&chars, skip_colon(&chars, skip_space(&chars, start + 3)));
        let digits = digit_run(&chars, at);
        let after = skip_space(&chars, at + digits);
        ((1..=3).contains(&digits) && chars.get(after) == Some(&'秒'))
            .then(|| digits_value(&chars[at..at + digits]))
    })
}

/// `准备就绪\s*[:：]?\s*(\d{1,2})\s*/\s*12`, searched: the count of the first place it matches.
pub fn ready_search(text: &str) -> Option<i64> {
    let chars: Vec<char> = text.chars().collect();
    find_all(&chars, "准备就绪").into_iter().find_map(|start| {
        let at = skip_space(&chars, skip_colon(&chars, skip_space(&chars, start + 4)));
        let digits = digit_run(&chars, at);
        if !(1..=2).contains(&digits) {
            return None;
        }
        let slash = skip_space(&chars, at + digits);
        let twelve = skip_space(&chars, slash + 1);
        let fits = chars.get(slash) == Some(&'/')
            && chars.get(twelve..twelve + 2) == Some(&['1', '2'][..]);
        fits.then(|| digits_value(&chars[at..at + digits]))
    })
}

/// The seconds in one line read as 倒计时 10 秒, or None.
pub fn countdown_in(text: &str) -> Option<i64> {
    countdown_search(&plain(text))
}

/// The players ready in one line read as 准备就绪：11/12, or None.
pub fn ready_in(text: &str) -> Option<i64> {
    ready_search(&nfkc(text))
}

/// True when this frame shows the match-found title 推演成功.
pub fn contains_title(lines: &[OcrLine]) -> bool {
    lines
        .iter()
        .any(|line| norm(&line.text).contains("推演成功"))
}

/// Prefer the line that is the phrase, not the phrase plus a neighbor; of those, the tallest.
pub fn pick_tight<'a>(candidates: &[&'a OcrLine], phrase: &str) -> Option<&'a OcrLine> {
    let folded_len = norm(phrase).chars().count();
    let key = |line: &OcrLine| {
        (
            norm(&line.text).chars().count().saturating_sub(folded_len),
            -height(&line.bbox),
        )
    };
    candidates.iter().copied().min_by(|a, b| {
        key(a)
            .partial_cmp(&key(b))
            .unwrap_or(std::cmp::Ordering::Equal)
    })
}

/// 模仿者狂欢（12人狂欢）, as one line or two pieces on one row (the nearest pair).
pub fn assemble_mode(lines: &[OcrLine]) -> Option<OcrLine> {
    let has = |line: &OcrLine, part: &str| norm(&line.text).contains(part);
    let direct: Vec<&OcrLine> = lines
        .iter()
        .filter(|line| has(line, "模仿者狂欢") && has(line, "12人狂欢"))
        .collect();
    if let Some(chosen) = pick_tight(&direct, "模仿者狂欢（12人狂欢）") {
        return Some(chosen.clone());
    }
    let mut best = None;
    let mut best_gap = 1e9;
    for (ia, a) in lines
        .iter()
        .enumerate()
        .filter(|(_, line)| has(line, "模仿者狂欢"))
    {
        for (ib, b) in lines
            .iter()
            .enumerate()
            .filter(|(_, line)| has(line, "12人狂欢"))
        {
            if ia == ib || !same_row(&a.bbox, &b.bbox) {
                continue;
            }
            let gap = (center(&a.bbox).0 - center(&b.bbox).0).abs();
            if gap < best_gap {
                best_gap = gap;
                let text = if a.bbox[0] <= b.bbox[0] {
                    format!("{}{}", a.text, b.text)
                } else {
                    format!("{}{}", b.text, a.text)
                };
                best = Some(OcrLine::new(
                    text,
                    a.confidence.min(b.confidence),
                    union(&[a.bbox, b.bbox]),
                ));
            }
        }
    }
    best
}

/// `\d{1,3}|秒|\d{1,3}秒`, the whole token.
fn is_count_piece(token: &str) -> bool {
    let chars: Vec<char> = token.chars().collect();
    let digits = digit_run(&chars, 0);
    let rest = &chars[digits..];
    (digits == 0 && rest == ['秒'])
        || ((1..=3).contains(&digits) && (rest.is_empty() || rest == ['秒']))
}

/// 倒计时, a seconds count, and 秒, joined from the pieces on its row; of several, the tallest.
pub fn assemble_countdown(lines: &[OcrLine]) -> Option<(OcrLine, i64)> {
    let mut best: Option<(f64, OcrLine, i64)> = None;
    for (ib, base) in lines
        .iter()
        .enumerate()
        .filter(|(_, line)| norm(&line.text).contains("倒计时"))
    {
        let mut group = vec![base];
        let limit = 4.0 * height(&base.bbox).max(16.0);
        for (io, other) in lines.iter().enumerate() {
            if io == ib || !same_row(&base.bbox, &other.bbox) {
                continue;
            }
            if other.bbox[0] < base.bbox[0] - 8.0 || other.bbox[0] - base.bbox[2] > limit {
                continue;
            }
            if is_count_piece(&plain(&other.text)) {
                group.push(other);
            }
        }
        group.sort_by(|a, b| {
            a.bbox[0]
                .partial_cmp(&b.bbox[0])
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        let text: String = group.iter().map(|line| plain(&line.text)).collect();
        let Some(count) = countdown_search(&text) else {
            continue;
        };
        let rects: Vec<Rect> = group.iter().map(|line| line.bbox).collect();
        let bbox = union(&rects);
        let confidence = group
            .iter()
            .map(|line| line.confidence)
            .fold(f64::INFINITY, f64::min);
        let score = height(&bbox);
        if best.as_ref().is_none_or(|(top, _, _)| score > *top) {
            best = Some((score, OcrLine::new(text, confidence, bbox), count));
        }
    }
    best.map(|(_, line, count)| (line, count))
}
