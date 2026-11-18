//! The names on the cards: a Chinese face (Microsoft YaHei on Windows, as ui_theme.chinese_family picks),
//! measured as QFontMetrics measures it and drawn with ab_glyph's coverage rasterizer.

use ab_glyph::{Font, FontVec, PxScale, ScaleFont};
use tiny_skia::Color;

use crate::canvas::Canvas;

pub struct Face {
    font: FontVec,
    /// The face Qt takes the line metrics from when the glyphs come from a fallback (fontconfig maps
    /// Microsoft YaHei to the system sans, Inter on the Linux CI, and draws the Chinese from WenQuanYi).
    metrics: Option<FontVec>,
}

fn em_scale(font: &FontVec, px: f32) -> PxScale {
    match font.units_per_em() {
        // An em of `px` pixels, as Qt sizes a font: PxScale is the ascent-to-descent height.
        Some(em) => PxScale::from(px * font.height_unscaled() / em),
        None => PxScale::from(px),
    }
}

/// Where a Chinese face is, first found first: Windows' own, then the Linux ones CI and tests have.
pub const SYSTEM_FACES: &[(&str, u32)] = &[
    ("C:\\Windows\\Fonts\\msyh.ttc", 0),
    ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 2),
    ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0),
];

impl Face {
    pub fn from_bytes(bytes: Vec<u8>, index: u32) -> Option<Face> {
        FontVec::try_from_vec_and_index(bytes, index).ok().map(|font| Face { font, metrics: None })
    }

    /// The first Chinese face installed, or None (the caller shows the marks without names then).
    pub fn system() -> Option<Face> {
        SYSTEM_FACES.iter().find_map(|(path, index)| std::fs::read(path).ok().and_then(|b| Face::from_bytes(b, *index)))
    }

    /// Line metrics from `bytes` (the primary face Qt resolved), glyphs still from this face.
    pub fn with_metrics(mut self, bytes: Vec<u8>) -> Face {
        self.metrics = FontVec::try_from_vec(bytes).ok();
        self
    }

    fn scale(&self, px: f32) -> PxScale {
        em_scale(&self.font, px)
    }

    fn lines(&self) -> &FontVec {
        self.metrics.as_ref().unwrap_or(&self.font)
    }

    /// QFontMetrics.horizontalAdvance with full hinting: each advance whole pixels.
    pub fn advance(&self, text: &str, px: f32) -> i32 {
        let font = self.font.as_scaled(self.scale(px));
        text.chars().map(|c| font.h_advance(font.glyph_id(c)).round() as i32).sum()
    }

    /// Ascent and descent in whole pixels, as FreeType's hinted metrics round them.
    pub fn ascent(&self, px: f32) -> i32 {
        self.lines().as_scaled(em_scale(self.lines(), px)).ascent().round() as i32
    }

    pub fn descent(&self, px: f32) -> i32 {
        (-self.lines().as_scaled(em_scale(self.lines(), px)).descent()).round() as i32
    }

    /// QFontMetrics.height.
    pub fn height(&self, px: f32) -> i32 {
        self.ascent(px) + self.descent(px)
    }

    /// The ink's box of `text` at the origin's baseline (QPainterPath.addText(...).boundingRect()).
    pub fn ink(&self, text: &str, px: f32) -> (f32, f32, f32, f32) {
        let scale = self.scale(px);
        let font = self.font.as_scaled(scale);
        let (mut x, mut b) = (0.0, (f32::MAX, f32::MAX, f32::MIN, f32::MIN));
        let (sx, sy) = (font.h_scale_factor(), font.v_scale_factor());
        for c in text.chars() {
            let id = font.glyph_id(c);
            // The outline's exact box, as a QPainterPath has it (font units, y up).
            if let Some(o) = self.font.outline(id) {
                let r = o.bounds;
                b = (b.0.min(x + r.min.x * sx), b.1.min(-r.max.y * sy), b.2.max(x + r.max.x * sx), b.3.max(-r.min.y * sy));
            }
            x += font.h_advance(id);
        }
        if b.0 > b.2 { (0.0, 0.0, 0.0, 0.0) } else { b }
    }

    /// `text` with its baseline at (x, baseline) logical pixels.
    pub fn draw(&self, canvas: &mut Canvas, text: &str, x: f32, baseline: f32, px: f32, color: Color) {
        let ratio = canvas.ratio;
        let scale = self.scale(px * ratio);
        let font = self.font.as_scaled(scale);
        let mut pen = (x * ratio).floor();
        let base = (baseline * ratio).floor();
        for c in text.chars() {
            let id = font.glyph_id(c);
            let glyph = id.with_scale_and_position(scale, ab_glyph::point(pen, base));
            if let Some(outline) = self.font.outline_glyph(glyph) {
                let b = outline.px_bounds();
                outline.draw(|gx, gy, cov| canvas.blend(b.min.x as i32 + gx as i32, b.min.y as i32 + gy as i32, color, cov));
            }
            pen += (font.h_advance(id) / ratio).round() * ratio;
        }
    }
}
