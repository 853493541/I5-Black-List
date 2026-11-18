//! A tiny-skia pixmap drawn in logical pixels: every call goes through the base transform (the monitor's
//! scale), so a mark is laid out once in logical pixels, as Qt does, and drawn sharp at 150 %.

use tiny_skia::{Color, FillRule, Mask, Paint, Path, Pixmap, Shader, Stroke, Transform};

pub struct Canvas {
    pub pixmap: Pixmap,
    /// Logical to device pixels.
    pub ratio: f32,
    /// Extra transform on top of the scale, for painters that translate and rotate (the flowers).
    pub local: Transform,
    pub clip: Option<Mask>,
}

impl Canvas {
    /// A clear canvas `width` by `height` logical pixels at `ratio`.
    pub fn new(width: i32, height: i32, ratio: f32) -> Canvas {
        let w = ((width.max(1) as f32) * ratio).round().max(1.0) as u32;
        let h = ((height.max(1) as f32) * ratio).round().max(1.0) as u32;
        Canvas { pixmap: Pixmap::new(w, h).expect("canvas size"), ratio, local: Transform::identity(), clip: None }
    }

    pub fn transform(&self) -> Transform {
        self.local.post_scale(self.ratio, self.ratio)
    }

    pub fn fill(&mut self, path: &Path, shader: Shader<'_>) {
        let paint = Paint { shader, anti_alias: true, ..Paint::default() };
        let t = self.transform();
        self.pixmap.fill_path(path, &paint, FillRule::Winding, t, self.clip.as_ref());
    }

    pub fn stroke(&mut self, path: &Path, shader: Shader<'_>, width: f32) {
        let paint = Paint { shader, anti_alias: true, ..Paint::default() };
        let stroke = Stroke { width, ..Stroke::default() };
        let t = self.transform();
        self.pixmap.stroke_path(path, &paint, &stroke, t, self.clip.as_ref());
    }

    pub fn stroke_round(&mut self, path: &Path, color: Color, width: f32) {
        let paint = Paint { shader: Shader::SolidColor(color), anti_alias: true, ..Paint::default() };
        let stroke = Stroke { width, line_cap: tiny_skia::LineCap::Round, line_join: tiny_skia::LineJoin::Round, ..Stroke::default() };
        let t = self.transform();
        self.pixmap.stroke_path(path, &paint, &stroke, t, self.clip.as_ref());
    }

    /// Only inside `path` from now on (the window's shape, ui_overlay.LobbyPanel._mask_pill).
    pub fn clip_to(&mut self, path: &Path) {
        let mut mask = Mask::new(self.pixmap.width(), self.pixmap.height()).expect("mask size");
        mask.fill_path(path, FillRule::Winding, true, Transform::from_scale(self.ratio, self.ratio));
        self.clip = Some(mask);
    }

    /// Blend one device pixel of `color` at `coverage` (0..1), source over, for glyphs.
    pub fn blend(&mut self, x: i32, y: i32, color: Color, coverage: f32) {
        if x < 0 || y < 0 || x >= self.pixmap.width() as i32 || y >= self.pixmap.height() as i32 || coverage <= 0.0 {
            return;
        }
        let a = color.alpha() * coverage.min(1.0);
        let i = (y as u32 * self.pixmap.width() + x as u32) as usize;
        let data = self.pixmap.data_mut();
        let px = &mut data[i * 4..i * 4 + 4];
        let rest = 1.0 - a;
        for (c, src) in [color.red(), color.green(), color.blue()].into_iter().enumerate() {
            px[c] = (src * a * 255.0 + px[c] as f32 * rest).round().clamp(0.0, 255.0) as u8;
        }
        px[3] = (a * 255.0 + px[3] as f32 * rest).round().clamp(0.0, 255.0) as u8;
    }

    /// Draw another canvas's pixels at (x, y) device pixels, source over.
    pub fn draw_pixmap(&mut self, x: i32, y: i32, other: &Pixmap) {
        self.pixmap.draw_pixmap(x, y, other.as_ref(), &tiny_skia::PixmapPaint::default(), Transform::identity(), None);
    }
}
