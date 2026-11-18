//! claw.py's own marks (ring, badge, card, lead) for the overlay: `marks` drawn through `Pen` into the
//! overlay's tiny-skia canvas, the pictures made once per size and sharpness as claw.py keeps them.

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

use overlay::canvas::Canvas;
use overlay::paint::RectF;
use overlay::{Look, MarkHook};
use tiny_skia::{
    Color, FillRule, FilterQuality, GradientStop, IntSize, LinearGradient, Mask, Paint as SkPaint, Path, PathBuilder, Pixmap,
    PixmapPaint, Point, RadialGradient, Shader, SpreadMode, Stroke, Transform,
};

use super::geom::Affine;
use super::marks::{Marks, Pen, Sizes, CARD_TOP, LOOK, MARKS_ANIMATED};
use crate::prim::Paint;

/// The canvas as a `Pen`: the marks' transform and opacity on top of the canvas's own.
struct Sk<'a> {
    c: &'a mut Canvas,
    pics: &'a [Pixmap],
    tf: Affine,
    opacity: f64,
    saved: Vec<(Affine, f64)>,
}

fn rrect_path(r: [f64; 4], radius: f64) -> Option<Path> {
    let [x, y, w, h] = r.map(|v| v as f32);
    let k = (radius as f32).min(w / 2.0).min(h / 2.0).max(0.0);
    let c = k * 0.447_715;
    let mut b = PathBuilder::new();
    b.move_to(x + k, y);
    b.line_to(x + w - k, y);
    b.cubic_to(x + w - c, y, x + w, y + c, x + w, y + k);
    b.line_to(x + w, y + h - k);
    b.cubic_to(x + w, y + h - c, x + w - c, y + h, x + w - k, y + h);
    b.line_to(x + k, y + h);
    b.cubic_to(x + c, y + h, x, y + h - c, x, y + h - k);
    b.line_to(x, y + k);
    b.cubic_to(x, y + c, x + c, y, x + k, y);
    b.close();
    b.finish()
}

impl Sk<'_> {
    fn at(&self) -> Transform {
        let t = self.tf;
        Transform::from_row(t.m11 as f32, t.m12 as f32, t.m21 as f32, t.m22 as f32, t.dx as f32, t.dy as f32).post_concat(self.c.transform())
    }

    fn shader(&self, paint: &Paint) -> Option<Shader<'static>> {
        let o = self.opacity.clamp(0.0, 1.0);
        let color = |c: [f32; 3], a: f64| Color::from_rgba(c[0], c[1], c[2], (a * o).clamp(0.0, 1.0) as f32).unwrap_or(Color::TRANSPARENT);
        let list = |s: &[(f64, [f32; 3], f64)]| s.iter().map(|&(at, c, a)| GradientStop::new(at as f32, color(c, a))).collect::<Vec<_>>();
        let pt = |p: [f64; 2]| Point::from_xy(p[0] as f32, p[1] as f32);
        match paint {
            Paint::Solid(c, a) => Some(Shader::SolidColor(color(*c, *a))),
            Paint::Linear(a, b, s) => LinearGradient::new(pt(*a), pt(*b), list(s), SpreadMode::Pad, Transform::identity()),
            Paint::Radial(c, r, s) => RadialGradient::new(pt(*c), pt(*c), *r as f32, list(s), SpreadMode::Pad, Transform::identity()),
        }
    }

    fn fill(&mut self, path: Option<Path>, paint: &Paint) {
        let (Some(path), Some(shader)) = (path, self.shader(paint)) else { return };
        let sk = SkPaint { shader, anti_alias: true, ..SkPaint::default() };
        let at = self.at();
        self.c.pixmap.fill_path(&path, &sk, FillRule::Winding, at, self.c.clip.as_ref());
    }
}

impl Pen for Sk<'_> {
    fn tf(&self) -> Affine {
        self.tf
    }
    fn set_tf(&mut self, tf: Affine) {
        self.tf = tf;
    }
    fn opacity(&self) -> f64 {
        self.opacity
    }
    fn set_opacity(&mut self, opacity: f64) {
        self.opacity = opacity;
    }
    fn save(&mut self) {
        self.saved.push((self.tf, self.opacity));
    }
    fn restore(&mut self) {
        if let Some((tf, o)) = self.saved.pop() {
            (self.tf, self.opacity) = (tf, o);
        }
    }
    fn ellipse(&mut self, x: f64, y: f64, r: f64, paint: &Paint) {
        self.fill(PathBuilder::from_circle(x as f32, y as f32, r as f32), paint);
    }
    fn rrect(&mut self, r: [f64; 4], radius: f64, paint: &Paint) {
        self.fill(rrect_path(r, radius), paint);
    }
    fn rrect_pen(&mut self, r: [f64; 4], radius: f64, width: f64, paint: &Paint) {
        let (Some(path), Some(shader)) = (rrect_path(r, radius), self.shader(paint)) else { return };
        let sk = SkPaint { shader, anti_alias: true, ..SkPaint::default() };
        let at = self.at();
        self.c.pixmap.stroke_path(&path, &sk, &Stroke { width: width as f32, ..Stroke::default() }, at, self.c.clip.as_ref());
    }
    fn soft_dot(&mut self, x: f64, y: f64, r: f64, color: &str, alpha: f64) {
        if alpha <= 0.01 || r <= 0.2 {
            return;
        }
        let s = crate::prim::stops(&[(0.0, color, alpha), (0.35, color, alpha * 0.35), (1.0, color, 0.0)]);
        self.ellipse(x, y, r, &Paint::Radial([x, y], r, s));
    }
    fn picture(&mut self, id: usize, size: (usize, usize), r: [f64; 4], clip: Option<[f64; 4]>) {
        let Some(pm) = self.pics.get(id) else { return };
        let at = self.at();
        let place = Transform::from_row((r[2] / size.0 as f64) as f32, 0.0, 0.0, (r[3] / size.1 as f64) as f32, r[0] as f32, r[1] as f32).post_concat(at);
        let paint = PixmapPaint { opacity: self.opacity.clamp(0.0, 1.0) as f32, quality: FilterQuality::Bilinear, ..PixmapPaint::default() };
        let mask = clip.and_then(|c| {
            let mut m = Mask::new(self.c.pixmap.width(), self.c.pixmap.height())?;
            m.fill_path(&PathBuilder::from_rect(tiny_skia::Rect::from_xywh(c[0] as f32, c[1] as f32, c[2] as f32, c[3] as f32)?), FillRule::Winding, true, at);
            Some(m)
        });
        let mask = mask.as_ref().or(self.c.clip.as_ref());
        self.c.pixmap.draw_pixmap(0, 0, pm.as_ref(), &paint, place, mask);
    }
}

/// Marks made for one set of sizes and sharpness, with their pictures as pixmaps.
type Made = Arc<(Marks, Vec<Pixmap>)>;

/// claw.py's marks for the overlay, made per size and sharpness on first use.
pub struct ClawMarks {
    assets: PathBuf,
    made: Mutex<HashMap<String, Made>>,
}

impl ClawMarks {
    pub fn new(assets: PathBuf) -> Self {
        Self { assets, made: Mutex::new(HashMap::new()) }
    }

    /// Marks made for these sizes (one mark's size given, the rest at claw.py's usual), with their pixmaps.
    fn marks(&self, sizes: Sizes, scale: f64) -> Option<Made> {
        let key = format!("{} {} {:?} {} {scale}", sizes.cover_h, sizes.badge, sizes.card, sizes.lead);
        let mut made = self.made.lock().ok()?;
        if let Some(m) = made.get(&key) {
            return Some(m.clone());
        }
        let marks = Marks::new(&sizes, scale, &self.assets).ok()?;
        let pics = marks.pics().iter().map(|p| Pixmap::from_vec(p.bytes(), IntSize::from_wh(p.w as u32, p.h as u32)?)).collect::<Option<Vec<_>>>()?;
        let m = Arc::new((marks, pics));
        made.insert(key, m.clone());
        Some(m)
    }

    fn on(&self, c: &mut Canvas, sizes: Sizes, draw: impl FnOnce(&Marks, &mut Sk)) -> bool {
        let t = c.transform();
        let scale = (f64::from(t.sx.hypot(t.ky)) * 100.0).round() / 100.0;
        let Some(m) = self.marks(sizes, scale) else { return false };
        let mut pen = Sk { c, pics: &m.1, tf: Affine::default(), opacity: 1.0, saved: Vec::new() };
        draw(&m.0, &mut pen);
        true
    }
}

const USUAL: Sizes = Sizes { cover_h: 80.0, badge: 60.0, card: [260.0, 140.0], lead: 24.0 };

impl MarkHook for ClawMarks {
    fn ring(&self, c: &mut Canvas, cover: RectF, t: f32) -> bool {
        let r = [cover.x, cover.y, cover.w, cover.h].map(f64::from);
        self.on(c, Sizes { cover_h: r[3], ..USUAL }, |m, pen| m.ring(pen, r, f64::from(t)))
    }
    fn badge(&self, c: &mut Canvas, b: RectF, t: f32) -> bool {
        let r = [b.x, b.y, b.w, b.h].map(f64::from);
        self.on(c, Sizes { badge: r[2], ..USUAL }, |m, pen| m.badge(pen, r, f64::from(t)))
    }
    fn card(&self, c: &mut Canvas, rect: RectF, t: f32) -> bool {
        let r = [rect.x, rect.y, rect.w, rect.h].map(f64::from);
        self.on(c, Sizes { card: [r[2], r[3]], ..USUAL }, |m, pen| m.card(pen, r, f64::from(t)))
    }
    fn draws_card(&self) -> bool {
        true
    }
    /// The claw marks before a name, `size` pixels across (drawn unscaled by the overlay).
    fn lead(&self, size: f32, index: usize) -> Option<Option<Pixmap>> {
        let n = size.ceil().max(1.0) as u32;
        let mut c = Canvas::new(n as i32, n as i32, 1.0);
        let lead = f64::from(size);
        self.on(&mut c, Sizes { lead, ..USUAL }, |m, pen| m.lead(pen, [0.0, 0.0], index)).then_some(Some(c.pixmap))
    }
    fn card_top(&self) -> Option<i32> {
        Some(CARD_TOP as i32)
    }
    fn animated(&self) -> bool {
        MARKS_ANIMATED
    }
}

/// The overlay's look for 演说家遇袭: claw.LOOK, its marks drawn by `ClawMarks` (assets: role_conductor.png).
pub fn look(assets: PathBuf) -> Look {
    let [f0, f1] = LOOK.flowers;
    Look {
        key: "claw",
        glow: (LOOK.glow[0], LOOK.glow[1], LOOK.glow[2]),
        rim: LOOK.rim,
        band: LOOK.band,
        card: LOOK.card,
        edge: LOOK.edge,
        ink: LOOK.ink,
        flowers: [(f0[0], f0[1], f0[2]), (f1[0], f1[1], f1[2])],
        disc: LOOK.disc,
        heart: LOOK.heart,
        deep: LOOK.deep,
        deep_glow: (LOOK.deep_glow[0], LOOK.deep_glow[1], LOOK.deep_glow[2]),
        marks: Some(Arc::new(ClawMarks::new(assets))),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_overlay_gets_claws_own_marks() {
        let assets = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../blacklist_detect/assets");
        let hook = look(assets).marks.expect("claw draws its marks");
        let mut c = Canvas::new(400, 220, 1.5);
        assert!(hook.ring(&mut c, RectF::new(40.0, 40.0, 160.0, 60.0), 1.0));
        let shown = |c: &Canvas| c.pixmap.pixels().iter().filter(|p| p.alpha() > 0).count();
        let ring = shown(&c);
        assert!(ring > 2000, "{ring}");
        assert!(hook.badge(&mut c, RectF::new(260.0, 30.0, 60.0, 60.0), 0.5));
        assert!(hook.card(&mut c, RectF::new(40.0, 120.0, 260.0, 90.0), 0.0));
        assert!(shown(&c) > ring + 5000);
        let lead = hook.lead(36.0, 0).flatten().expect("lead");
        assert_eq!((lead.width(), lead.height()), (36, 36));
        assert!(lead.pixels().iter().any(|p| p.alpha() > 0));
    }

    #[test]
    fn the_canvas_draws_the_marks_as_python_does() {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let Ok(theirs) = image::open(root.join("claw/py_marks.png")) else { return };
        let theirs = theirs.to_rgba8();
        let sizes = Sizes { cover_h: 80.0, badge: 60.0, card: [260.0, 140.0], lead: 24.0 };
        let m = ClawMarks::new(root.join("../../blacklist_detect/assets"));
        let mut c = Canvas::new(512, 320, 1.0);
        c.pixmap.fill(Color::from_rgba8(0x30, 0x34, 0x3c, 255));
        assert!(m.on(&mut c, sizes, |m, pen| {
            m.ring(pen, [40.0, 40.0, 300.0, 80.0], 2.0);
            m.badge(pen, [380.0, 50.0, 60.0, 60.0], 2.0);
            m.card(pen, [40.0, 150.0, 260.0, 140.0], 2.0);
            for i in 0..2 {
                m.lead(pen, [330.0 + 40.0 * i as f64, 200.0], i);
            }
        }));
        let (mut sq, mut n) = (0f64, 0f64);
        for y in 0..320u32 {
            for x in 0..480u32 {
                let a = c.pixmap.pixel(x, y).expect("pixel");
                let b = theirs.get_pixel(x, y);
                for (p, q) in [(a.red(), b[0]), (a.green(), b[1]), (a.blue(), b[2])] {
                    sq += (f64::from(p) - f64::from(q)).powi(2);
                    n += 1.0;
                }
            }
        }
        let psnr = 10.0 * (255.0f64.powi(2) / (sq / n).max(1e-9)).log10();
        eprintln!("claw marks on the overlay's canvas: {psnr:.1} dB");
        assert!(psnr > 50.0, "{psnr:.1} dB");
    }
}
