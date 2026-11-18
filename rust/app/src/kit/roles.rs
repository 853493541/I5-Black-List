//! The fields of the Slint Palette by their ui_theme role names, for the golden check. Generated with palettes.slint.

use crate::Palette;

/// Each ui_theme role and its colour in `p`.
pub fn roles(p: &Palette) -> Vec<(&'static str, slint::Color)> {
    vec![
        ("bg", p.bg),
        ("surface", p.surface),
        ("surface_alt", p.surface_alt),
        ("border", p.border),
        ("text", p.text),
        ("muted", p.muted),
        ("hover", p.hover),
        ("selected", p.selected),
        ("accent", p.accent),
        ("accent_line", p.accent_line),
        ("accent_hover", p.accent_hover),
        ("accent_press", p.accent_press),
        ("accent_wash", p.accent_wash),
        ("on_accent", p.on_accent),
        ("red", p.red),
        ("red_wash", p.red_wash),
        ("red_hover", p.red_hover),
        ("green", p.green),
        ("green_wash", p.green_wash),
        ("green_hover", p.green_hover),
        ("blue", p.blue),
        ("blue_wash", p.blue_wash),
        ("rose", p.rose),
        ("rose_wash", p.rose_wash),
        ("rose_hover", p.rose_hover),
        ("gray", p.gray),
        ("gray_wash", p.gray_wash),
        ("gray_hover", p.gray_hover),
        ("danger", p.danger),
        ("danger_hover", p.danger_hover),
        ("warning", p.warning),
        ("chip_bg", p.chip_bg),
        ("chip_text", p.chip_text),
        ("chip_off_bg", p.chip_off_bg),
        ("chip_off_line", p.chip_off_line),
        ("field_line", p.field_line),
        ("toast_bg", p.toast_bg),
        ("toast_text", p.toast_text),
        ("toast_action", p.toast_action),
    ]
}
