//! The 嘉宾 marks dressed for the scene that greets them (ui_overlay.LoveLook, LOOKS), and the hook a scene
//! uses to draw marks of its own (演说家遇袭's claw, 竖琴清风's lyre: love_scenes `ring`, `badge`, `card`, `lead`).

use std::fmt;
use std::sync::Arc;

use crate::canvas::Canvas;
use crate::paint::RectF;

/// "#rrggbb" colors; glows are (r, g, b).
#[derive(Clone)]
pub struct Look {
    pub key: &'static str,
    pub glow: (u8, u8, u8),
    /// The fine outer rim of the ring and of the badge.
    pub rim: &'static str,
    /// The ring's band: at its two ends, and in its middle.
    pub band: (&'static str, &'static str),
    /// The card, top to bottom; its edge; the names on it.
    pub card: (&'static str, &'static str),
    pub edge: &'static str,
    pub ink: &'static str,
    /// The two flowers of the knots and before the names, each (tip, middle, heart).
    pub flowers: [Flower; 2],
    /// The badge, middle to edge, and the heart on it, top to bottom.
    pub disc: (&'static str, &'static str),
    pub heart: (&'static str, &'static str),
    /// The 嘉宾 half of a ring shared with 黑名单 players, and its glow.
    pub deep: &'static str,
    pub deep_glow: (u8, u8, u8),
    /// A scene that draws marks itself (the scene packages fill this in), or None: the look only colors them.
    pub marks: Option<Arc<dyn MarkHook>>,
}

pub type Flower = (&'static str, &'static str, &'static str);

impl fmt::Debug for Look {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("Look").field("key", &self.key).field("marks", &self.marks.is_some()).finish()
    }
}

/// What a scene can draw of the marks itself (ui_overlay._HOOKS and the constants `_theme` reads). Every method
/// has the default "not mine": the mark is drawn as the look colors it. `t` is seconds since the mark showed.
pub trait MarkHook: Send + Sync {
    /// The 嘉宾 ring round the cover; true when drawn.
    fn ring(&self, _canvas: &mut Canvas, _cover: RectF, _t: f32) -> bool {
        false
    }
    /// The heart badge in its box; true when drawn.
    fn badge(&self, _canvas: &mut Canvas, _box: RectF, _t: f32) -> bool {
        false
    }
    /// The card under the names (the whole card rect); true when drawn: no knot, no plain card then.
    fn card(&self, _canvas: &mut Canvas, _rect: RectF, _t: f32) -> bool {
        false
    }
    /// Whether `card` draws the card (asked before layout, as `_theme(look, "card") is None` is).
    fn draws_card(&self) -> bool {
        false
    }
    /// The mark before name `index`, `size` logical px across: Some(None) for none, None for the flowers.
    fn lead(&self, _size: f32, _index: usize) -> Option<Option<tiny_skia::Pixmap>> {
        None
    }
    /// CARD_TOP: room above the card for the scene's ornament.
    fn card_top(&self) -> Option<i32> {
        None
    }
    /// CARD_PAD: the body's margins round the names at full size (left, top, right, bottom).
    fn card_pad(&self) -> Option<[i32; 4]> {
        None
    }
    /// MARKS_ANIMATED: the marks move, so the window repaints about 30 times a second.
    fn animated(&self) -> bool {
        false
    }
}

const PINK: Flower = ("#fff0f6", "#ff9cc4", "#ff6fa6");
const BLUE: Flower = ("#f2f9ff", "#a8d6ff", "#6fb4ff");

/// 玫瑰花边 (lace): the marks before a scene dresses them.
pub fn rose() -> Look {
    Look {
        key: "lace",
        glow: (255, 150, 200),
        rim: "#f3c1d0",
        band: ("#ff9cc4", "#d7c6ff"),
        card: ("#fff4f9", "#fadcec"),
        edge: "#e8a7bd",
        ink: "#8a2d55",
        flowers: [PINK, BLUE],
        disc: ("#fff3f8", "#f7b3cb"),
        heart: ("#ff7fb0", "#d92f6b"),
        deep: "#c2306b",
        deep_glow: (235, 95, 155),
        marks: None,
    }
}

/// The look for a scene key, as ui_overlay.LOOKS has it; 玫瑰花边's for any other (随机, 无, a scene that
/// brings its own LOOK, which its package gives with `Look { marks, .. }`).
pub fn look_for(key: &str) -> Look {
    match key {
        "ice" => Look {
            key: "ice",
            glow: (110, 190, 255),
            rim: "#cfe8ff",
            band: ("#7fd0ff", "#b9b0ff"),
            card: ("#f4fbff", "#dcefff"),
            edge: "#9cc9ec",
            ink: "#1f4f7a",
            flowers: [("#f2f9ff", "#a8d6ff", "#5aa8f0"), ("#f6f2ff", "#c9b8ff", "#8f74f0")],
            disc: ("#f4fbff", "#b9defb"),
            heart: ("#8fd0ff", "#2f6fd9"),
            deep: "#2f6fd9",
            deep_glow: (90, 160, 255),
            marks: None,
        },
        "stars" => Look {
            key: "stars",
            glow: (185, 163, 255),
            rim: "#f6d68a",
            band: ("#b9a3ff", "#f6d68a"),
            card: ("#2e2758", "#1b1838"),
            edge: "#c9a95a",
            ink: "#f8e7b4",
            flowers: [("#fff8e0", "#f6d68a", "#e0a93a"), ("#f3eeff", "#b9a3ff", "#8a6fe0")],
            disc: ("#3a3274", "#1d1a40"),
            heart: ("#ffe39a", "#e0a93a"),
            deep: "#7a5fe0",
            deep_glow: (150, 120, 255),
            marks: None,
        },
        _ => rose(),
    }
}

impl Look {
    pub(crate) fn hook(&self) -> Option<&dyn MarkHook> {
        self.marks.as_deref()
    }
}
