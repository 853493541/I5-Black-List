//! The marks drawn on the game over the 黑名单 and 嘉宾 seats (blacklist_detect/ui_overlay.py).
//!
//! Two parts:
//! - Platform-free: [`layout::plan`] lays the marks out for a check (the cover ring on 准备案件还原, the 黑名单 card on
//!   its right, the 嘉宾 card on its left, the badge) and draws each with tiny-skia; [`layout::compose`] puts them
//!   in one premultiplied RGBA picture. tiny-skia, not the scenes crate's wgpu path: the marks are a few dozen
//!   small paths and some text drawn once per check, UpdateLayeredWindow wants the pixels in memory anyway (a GPU
//!   draw would need a readback), and the CPU path runs the same on CI, in tests and on any PC.
//! - Windows ([`window`], cfg(windows)): one topmost, click-through, layered tool window that never takes focus,
//!   per-monitor DPI aware, shown with UpdateLayeredWindow and moved with the game.
//!
//! The app-wiring package drives it through [`Overlay`] (Windows) or [`render`] (anywhere):
//! - `Overlay::show(game_rect, &CheckResult, &look)`: the marks for a check, over the game.
//! - `Overlay::show_checking(button, "检查中")`: the gold block while a check runs.
//! - `Overlay::follow(game_rect)`: the game window moved; the marks move with it (call on the 400 ms glance).
//! - `Overlay::hide()`: the lobby is gone (the app hides the marks when the 推演成功 title leaves, as
//!   `_hide_panel_after_title` does).
//!
//! Scenes that draw their own marks (演说家遇袭's claw, 竖琴清风's lyre) give a [`look::Look`] whose `marks` is
//! their [`look::MarkHook`].
#![cfg_attr(not(windows), forbid(unsafe_code))]
#![cfg_attr(windows, deny(unsafe_code))]

pub mod canvas;
pub mod cards;
pub mod layout;
pub mod look;
pub mod marks;
pub mod paint;
pub mod text;
#[cfg(windows)]
#[allow(unsafe_code)]
pub mod window;

pub use cards::Person;
pub use layout::{CheckResult, Extras, Rect, Seat, SeatKind};
pub use look::{look_for, rose, Look, MarkHook};
pub use marks::{Mode, Moment, Style};

/// The marks for a check in one picture: its top-left in device pixels and its premultiplied RGBA pixels, or
/// None when there is nothing to show (no 准备案件还原 found). `area` is the free part of the game's screen in
/// device pixels, `ratio` the screen's scale.
pub fn render(result: &CheckResult, extras: Extras, area: [i32; 4], style: &Style) -> Option<Frame> {
    render_without(result, extras, area, style, &[])
}

/// As `render`, leaving out the marks named in `left_out` ("hit_card": 直播画面 never shows 黑名单's names).
pub fn render_without(result: &CheckResult, extras: Extras, area: [i32; 4], style: &Style, left_out: &[&str]) -> Option<Frame> {
    let ratio = style.ratio;
    let button = result.button_box?;
    let logical = Rect {
        x: py(area[0] as f32 / ratio),
        y: py(area[1] as f32 / ratio),
        w: py((area[2] - area[0]) as f32 / ratio),
        h: py((area[3] - area[1]) as f32 / ratio),
    };
    let mut marks = layout::plan(button, result, extras, logical, style);
    marks.retain(|mark| !left_out.contains(&mark.what));
    let (at, canvas) = layout::compose(&marks, ratio)?;
    Some(Frame { x: (at.x as f32 * ratio).round() as i32, y: (at.y as f32 * ratio).round() as i32, pixmap: canvas.pixmap })
}

fn py(v: f32) -> i32 {
    paint::py_round(v)
}

/// One picture of the marks, placed in device pixels.
pub struct Frame {
    pub x: i32,
    pub y: i32,
    pub pixmap: tiny_skia::Pixmap,
}

#[cfg(windows)]
pub use window::Overlay;
