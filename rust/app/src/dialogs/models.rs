//! What the dialogs show, worked out from the data crate's types: 标签 flowed into lines, import previews, the
//! name check of 添加 / 编辑, and 环境测试's bars laid out in pixels.

use data::import::{ImportRow, Record, Status, TagSuggestion};
use data::store::text::{clean_stored_name, fold};
use slint::{Color, ModelRc, SharedString, VecModel};

use crate::{FlowBarData, FlowPart, PreviewRow, TagChip, TagLine};

/// The room for pills in 添加 / 编辑 (440 px card less its 24 px sides) and beside 确认导入's 新标签 / 已有标签.
pub const NAME_TAG_ROOM: f32 = 392.0;
pub const SUGGEST_TAG_ROOM: f32 = 568.0;
/// 环境测试's bars: 500 px card less its sides.
pub const FLOW_BAR_WIDTH: f32 = 452.0;
const PILL_GAP: f32 = 8.0;

/// How wide text is at `size` px: a full width for CJK and other wide characters, about 0.55 for the rest.
/// An estimate (no font is measured), close enough to break lines where Qt breaks them.
pub fn text_width(text: &str, size: f32) -> f32 {
    text.chars()
        .map(|ch| {
            if (ch as u32) >= 0x2e80 {
                size
            } else {
                size * 0.55
            }
        })
        .sum()
}

/// A pill's width: its words at 12 px and 9 px either side (ui_widgets.TagPill).
pub fn pill_width(tag: &str) -> f32 {
    text_width(tag, 12.0) + 18.0
}

/// Pills in lines, each as many as fit in `room` px with 8 px between them: _FlowHost's wrapping.
pub fn flow(chips: &[(String, bool)], room: f32) -> Vec<Vec<(String, bool)>> {
    let mut lines: Vec<Vec<(String, bool)>> = Vec::new();
    let mut used = 0.0;
    for (text, active) in chips {
        let wide = pill_width(text);
        let fits = lines
            .last()
            .is_some_and(|line| !line.is_empty() && used + PILL_GAP + wide <= room);
        if fits {
            used += PILL_GAP + wide;
        } else {
            lines.push(Vec::new());
            used = wide;
        }
        lines
            .last_mut()
            .expect("a line")
            .push((text.clone(), *active));
    }
    lines
}

fn chips_model(chips: &[(String, bool)]) -> ModelRc<TagChip> {
    let items: Vec<TagChip> = chips
        .iter()
        .map(|(text, active)| TagChip {
            text: text.into(),
            active: *active,
        })
        .collect();
    ModelRc::new(VecModel::from(items))
}

/// The lines of pills as the dialogs take them.
pub fn tag_lines(chips: &[(String, bool)], room: f32) -> ModelRc<TagLine> {
    let lines: Vec<TagLine> = flow(chips, room)
        .iter()
        .map(|line| TagLine {
            chips: chips_model(line),
        })
        .collect();
    ModelRc::new(VecModel::from(lines))
}

/// 添加 / 编辑's pills: the record's own 标签 first, in catalog order, then the rest of the catalog.
pub fn name_chips(catalog: &[String], tags: &[String]) -> Vec<(String, bool)> {
    let mut order: Vec<String> = catalog
        .iter()
        .filter(|tag| tags.contains(tag))
        .cloned()
        .collect();
    for tag in tags.iter().chain(catalog) {
        if !order.contains(tag) {
            order.push(tag.clone());
        }
    }
    order
        .into_iter()
        .map(|tag| {
            let on = tags.contains(&tag);
            (tag, on)
        })
        .collect()
}

/// Why 添加 / 编辑 cannot save `typed`, or "" when it can: AddNameDialog._accept. `taken` holds the folded
/// names already on the list.
pub fn name_problem(typed: &str, taken: &[String]) -> &'static str {
    let key = fold(&clean_stored_name(typed));
    if typed.trim().is_empty() {
        "请填写名字"
    } else if key.is_empty() {
        "名字里要有文字或数字"
    } else if taken.contains(&key) {
        "已经在黑名单里了"
    } else {
        ""
    }
}

/// The name as 直播模式 shows it: its first character, then a star for each one after, at least one.
pub fn masked_name(name: &str) -> String {
    let mut chars = name.chars();
    match chars.next() {
        None => String::new(),
        Some(first) => format!("{first}{}", "*".repeat(chars.count().max(1))),
    }
}

/// What importing a row does, in 批量导入's last column.
pub fn status_words(status: Status) -> &'static str {
    match status {
        Status::Merge => "合并",
        Status::Same => "已在黑名单",
        Status::Odd => "可能不是名字",
        Status::Elsewhere => "已在嘉宾列表",
        Status::New => "",
    }
}

fn preview_row(
    name: &str,
    tags: &[String],
    reason: &str,
    status: Status,
    checked: bool,
) -> PreviewRow {
    let chips: Vec<(String, bool)> = tags.iter().map(|tag| (tag.clone(), true)).collect();
    PreviewRow {
        name: name.into(),
        tags: chips_model(&chips),
        reason: reason.into(),
        status: status_words(status).into(),
        merge: status == Status::Merge,
        checked,
        locked: status == Status::Elsewhere,
    }
}

/// 批量导入's preview, one row per person.
pub fn preview_rows(rows: &[ImportRow]) -> ModelRc<PreviewRow> {
    let items: Vec<PreviewRow> = rows
        .iter()
        .map(|row| preview_row(&row.name, &row.tags, &row.reason, row.status, row.checked))
        .collect();
    ModelRc::new(VecModel::from(items))
}

/// The count on 批量导入's button: the rows still checked.
pub fn checked_count(rows: &[ImportRow]) -> i32 {
    rows.iter().filter(|row| row.checked).count() as i32
}

/// 确认导入's pills, 新标签 and 已有标签, each on while `on` holds it.
pub fn suggestion_lines(
    suggestions: &[TagSuggestion],
    on: &[String],
    existing: bool,
) -> ModelRc<TagLine> {
    let chips: Vec<(String, bool)> = suggestions
        .iter()
        .filter(|suggestion| suggestion.existing == existing)
        .map(|suggestion| (suggestion.tag.clone(), on.contains(&suggestion.tag)))
        .collect();
    tag_lines(&chips, SUGGEST_TAG_ROOM)
}

/// 确认导入's people, each with the 标签 they will get once the ones still on are added.
pub fn people_rows(
    rows: &[Record],
    suggestions: &[TagSuggestion],
    on: &[String],
) -> ModelRc<PreviewRow> {
    let picked: Vec<TagSuggestion> = suggestions
        .iter()
        .filter(|suggestion| on.contains(&suggestion.tag))
        .cloned()
        .collect();
    let items: Vec<PreviewRow> = data::import::with_tags(rows, &picked)
        .iter()
        .map(|(name, tags, reason, _target)| preview_row(name, tags, reason, Status::New, true))
        .collect();
    ModelRc::new(VecModel::from(items))
}

/// One step of a check as 环境测试 reports it: its key (capture, glance, find, read), its words, its seconds.
pub type Step = (String, String, f64);

fn step_color(key: &str) -> Color {
    let hex = match key {
        "capture" => 0x8fa3bf,
        "glance" => 0xa58bff,
        "find" => 0x4f8fdc,
        "read" => 0xe58aa8,
        _ => 0x12325a,
    };
    Color::from_rgb_u8(
        (hex >> 16) as u8,
        (hex >> 8 & 0xff) as u8,
        (hex & 0xff) as u8,
    )
}

/// One bar of 环境测试 (_FlowBar): each step a part, as wide as its share of `scale` seconds, its seconds under
/// it and never over the label before.
pub fn flow_bar(title: &str, steps: &[Step], scale: f64) -> FlowBarData {
    let scale = scale.max(0.1);
    let total: f64 = steps.iter().map(|step| step.2).sum();
    let mut parts = Vec::new();
    let (mut x, mut free) = (0.0f32, 0.0f32);
    for (key, words, seconds) in steps {
        let span = FLOW_BAR_WIDTH * (*seconds / scale) as f32;
        if span <= 0.0 {
            continue;
        }
        let label = format!("{words} {seconds:.2}");
        let spot = x.max(free);
        free = spot + text_width(&label, 12.0) + 12.0;
        parts.push(FlowPart {
            x,
            width: span.max(2.0),
            tone: step_color(key),
            label: SharedString::from(label),
            label_x: spot,
        });
        x += span;
    }
    FlowBarData {
        title: title.into(),
        total: format!("{total:.1} 秒").into(),
        parts: ModelRc::new(VecModel::from(parts)),
    }
}
