//! lyre.py's own marks (ring, badge, card, lead) for the overlay: `marks`'s pictures, made once per size and
//! sharpness as `_mark` keeps them, laid into the overlay's canvas with the soft dots of the ring's shimmer.

use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use overlay::canvas::Canvas;
use overlay::paint::RectF;
use overlay::{Look, MarkHook};
use tiny_skia::{Color, FilterQuality, GradientStop, IntSize, PathBuilder, Pixmap, PixmapPaint, Point, RadialGradient, SpreadMode, Transform};

use super::img::Pic;
use super::marks::{badge_art, card_art, lead, ring_art, ring_shimmer};
use super::{ANEMO, CARD_TOP, LOOK, MARKS_ANIMATED};

/// A cached picture: where it goes (points; the ring's reaches past its cover) and its pixels.
type Art = ([f64; 4], Arc<Pixmap>, Vec<[f64; 2]>, Vec<f64>);

#[derive(Default)]
pub struct LyreMarks {
    made: Mutex<HashMap<String, Art>>,
}

/// The overlay's look for 竖琴清风: lyre.py's LOOK, its marks drawn by `LyreMarks`.
pub fn look() -> Look {
    Look {
        key: "lyre",
        glow: LOOK.glow,
        rim: LOOK.rim,
        band: LOOK.band,
        card: LOOK.card,
        edge: LOOK.edge,
        ink: LOOK.ink,
        flowers: LOOK.flowers,
        disc: LOOK.disc,
        heart: LOOK.heart,
        deep: LOOK.deep,
        deep_glow: LOOK.deep_glow,
        marks: Some(Arc::new(LyreMarks::default())),
    }
}

pub fn pixmap(pic: &Pic) -> Option<Pixmap> {
    let size = IntSize::from_wh(pic.w as u32, pic.h as u32)?;
    Pixmap::from_vec(pic.px.iter().flatten().copied().collect(), size)
}

/// _sharpness: device pixels a point where the canvas draws.
fn sharpness(c: &Canvas) -> f64 {
    let t = c.transform();
    (f64::from(t.sx.hypot(t.ky)) * 100.0).round() / 100.0
}

fn r1(v: f32) -> f64 {
    (f64::from(v) * 10.0).round() / 10.0
}

/// drawImage(rect, image), smooth, at an opacity.
fn lay(c: &mut Canvas, rect: [f64; 4], pm: &Pixmap, opacity: f32) {
    let (sx, sy) = (rect[2] / f64::from(pm.width()), rect[3] / f64::from(pm.height()));
    let at = Transform::from_row(sx as f32, 0.0, 0.0, sy as f32, rect[0] as f32, rect[1] as f32).post_concat(c.transform());
    let paint = PixmapPaint { opacity, quality: FilterQuality::Bilinear, ..PixmapPaint::default() };
    c.pixmap.draw_pixmap(0, 0, pm.as_ref(), &paint, at, c.clip.as_ref());
}

/// draw.soft_dot: a radial glow, alpha at the middle, 0.35 of it a third of the way out, none at the edge.
pub fn soft_dot(c: &mut Canvas, x: f64, y: f64, r: f64, color: &str, alpha: f64) {
    if alpha <= 0.01 || r <= 0.2 {
        return;
    }
    let [cr, cg, cb] = crate::draw::hex(color);
    let a = alpha.clamp(0.0, 1.0) as f32;
    let at = |k: f32| Color::from_rgba(cr, cg, cb, k).unwrap_or(Color::TRANSPARENT);
    let stops = vec![GradientStop::new(0.0, at(a)), GradientStop::new(0.35, at(a * 0.35)), GradientStop::new(1.0, at(0.0))];
    let centre = Point::from_xy(x as f32, y as f32);
    let Some(shader) = RadialGradient::new(centre, centre, r as f32, stops, SpreadMode::Pad, Transform::identity()) else { return };
    let Some(path) = PathBuilder::from_circle(x as f32, y as f32, r as f32) else { return };
    c.fill(&path, shader);
}

impl LyreMarks {
    fn art(&self, key: String, make: impl FnOnce() -> ([f64; 4], Pic, Vec<[f64; 2]>, Vec<f64>)) -> Option<Art> {
        let mut made = self.made.lock().ok()?;
        if !made.contains_key(&key) {
            let (area, pic, pts, s) = make();
            made.insert(key.clone(), (area, Arc::new(pixmap(&pic)?), pts, s));
        }
        made.get(&key).cloned()
    }
}

impl MarkHook for LyreMarks {
    fn ring(&self, c: &mut Canvas, cover: RectF, t: f32) -> bool {
        let scale = sharpness(c);
        let rect = [f64::from(cover.x), f64::from(cover.y), f64::from(cover.w), f64::from(cover.h)];
        let key = format!("ring {} {} {} {} {scale}", r1(cover.x), r1(cover.y), r1(cover.w), r1(cover.h));
        let Some((area, pm, pts, s)) = self.art(key, || ring_art(rect, scale)) else { return false };
        let (opacity, dots) = ring_shimmer(&pts, &s, f64::from(t));
        lay(c, area, &pm, opacity as f32);
        for (x, y, r, color, alpha) in dots {
            soft_dot(c, x, y, r, color, alpha);
        }
        true
    }

    fn badge(&self, c: &mut Canvas, b: RectF, t: f32) -> bool {
        let scale = sharpness(c);
        let (w, h) = (f64::from(b.w), f64::from(b.h));
        let key = format!("badge {} {} {scale}", r1(b.w), r1(b.h));
        let Some((_, pm, _, _)) = self.art(key, || ([0.0; 4], badge_art(w, h, scale), Vec::new(), Vec::new())) else { return false };
        let since = f64::from(t).rem_euclid(3.2);
        let swell = (1.0 - (-since / 0.05).exp()) * (-since * 2.2).exp();
        let (cx, cy) = (f64::from(b.x) + w / 2.0, f64::from(b.y) + h / 2.0);
        soft_dot(c, cx, cy, w.min(h) * 0.375 * 1.35, ANEMO, 0.18 + 0.3 * swell);
        lay(c, [f64::from(b.x), f64::from(b.y), w, h], &pm, 1.0);
        true
    }

    fn card(&self, c: &mut Canvas, r: RectF, _t: f32) -> bool {
        let scale = sharpness(c);
        let rect = [f64::from(r.x), f64::from(r.y), f64::from(r.w), f64::from(r.h)];
        let key = format!("card {} {} {scale}", r1(r.w), r1(r.h));
        let Some((_, pm, _, _)) = self.art(key, || ([0.0; 4], card_art(rect, scale), Vec::new(), Vec::new())) else { return false };
        lay(c, rect, &pm, 1.0);
        true
    }

    fn draws_card(&self) -> bool {
        true
    }

    /// A feather or a maple leaf, `size` pixels across (drawn unscaled by the overlay), from lyre.lead's
    /// three-pixels-a-point picture.
    fn lead(&self, size: f32, index: usize) -> Option<Option<Pixmap>> {
        let big = pixmap(&lead(f64::from(size), index))?;
        let n = size.ceil().max(1.0) as u32;
        let mut out = Pixmap::new(n, n)?;
        let k = size / big.width() as f32;
        let paint = PixmapPaint { quality: FilterQuality::Bilinear, ..PixmapPaint::default() };
        out.draw_pixmap(0, 0, big.as_ref(), &paint, Transform::from_scale(k, k), None);
        Some(Some(out))
    }

    fn card_top(&self) -> Option<i32> {
        Some(CARD_TOP as i32)
    }

    fn animated(&self) -> bool {
        MARKS_ANIMATED
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn shown(c: &Canvas) -> usize {
        c.pixmap.pixels().iter().filter(|p| p.alpha() > 0).count()
    }

    #[test]
    fn the_overlay_gets_lyres_own_marks() {
        let look = look();
        let hook = look.marks.clone().expect("lyre draws its marks");
        let mut c = Canvas::new(400, 200, 1.5);
        assert!(hook.ring(&mut c, RectF::new(40.0, 40.0, 160.0, 50.0), 1.0));
        let ring = shown(&c);
        assert!(ring > 2000, "{ring}");
        assert!(hook.badge(&mut c, RectF::new(260.0, 30.0, 48.0, 48.0), 0.5));
        assert!(hook.card(&mut c, RectF::new(40.0, 110.0, 200.0, 70.0), 0.0));
        assert!(shown(&c) > ring + 5000);
        // made once per size and sharpness
        assert!(hook.ring(&mut c, RectF::new(40.0, 40.0, 160.0, 50.0), 2.0));
        assert_eq!(hook.lead(27.0, 1).flatten().map(|p| (p.width(), p.height())), Some((27, 27)));
        assert!(hook.animated() && hook.draws_card());
    }
}
