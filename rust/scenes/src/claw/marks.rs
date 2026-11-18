//! The 嘉宾 marks 演说家遇袭 draws itself, instead of a look from ui_overlay.LOOKS (claw.py's ring,
//! badge, card and lead): a lilac rim round the button with claw marks at two corners that strike
//! again every 3.6 s, the 指挥家's role icon on a dark disc, misty glass with a glowing ♫, and a
//! small claw mark before each name.
//!
//! How the overlay hands them over: each mark is painted into its own window's frame, in that
//! window's points, with `scale` its pixels per point (devicePixelRatio times the painter's scale,
//! rounded to 0.01, as claw._sharpness). `Marks::new` makes the pictures for the windows' sizes
//! (the ring's cover, the badge's box, the card's rect, the names' size) once, `upload` puts them
//! on the chip, and ring / badge / card / lead draw them t seconds after the marks showed (they move:
//! MARKS_ANIMATED; redraw about 30 times a second). LOOK below still colors the shared ring and the
//! card's names, scroll bar and fade.

use super::art::{LILAC, PURPLE};
use super::frame::Frame;
use super::geom::Affine;
use super::gpu::Renderer;
use super::light::{Pic, Pt};
use super::marks_art::{claw_marks, disc, glass, note, role};
use crate::draw::clamp;
use crate::prim::{stops, Paint};

pub const MARKS_ANIMATED: bool = true;
/// Room above the card body: the note on its corner rises above its top edge.
pub const CARD_TOP: f64 = 20.0;

/// claw.LOOK: ui_overlay.LoveLook's fields for what the marks above do not draw.
pub struct Look {
    pub glow: [u8; 3],
    pub rim: &'static str,
    pub band: (&'static str, &'static str),
    pub card: (&'static str, &'static str),
    pub edge: &'static str,
    pub ink: &'static str,
    pub flowers: [[&'static str; 3]; 2],
    pub disc: (&'static str, &'static str),
    pub heart: (&'static str, &'static str),
    pub deep: &'static str,
    pub deep_glow: [u8; 3],
}

pub const LOOK: Look = Look {
    glow: [176, 140, 255],
    rim: LILAC,
    band: (PURPLE, "#e4dcff"),
    card: ("#252c3d", "#141925"),
    edge: "#9d86e8",
    ink: "#efeaff",
    flowers: [["#ffffff", "#e4dcff", "#a98bff"], ["#f4f7ff", "#c7d3e6", "#8fa3b8"]],
    disc: ("#2a3142", "#141925"),
    heart: ("#e4dcff", PURPLE),
    deep: PURPLE,
    deep_glow: [150, 110, 255],
};

/// The sizes the marks are made for, in points.
pub struct Sizes {
    /// The ring's cover height.
    pub cover_h: f64,
    /// The badge's side.
    pub badge: f64,
    /// The card's window (w, h).
    pub card: [f64; 2],
    /// The names' height, for lead.
    pub lead: f64,
}

pub struct Marks {
    scale: f64,
    pics: Vec<Pic>,
    tip: Pt,
    tex: Vec<usize>,
}

const RING: usize = 0;
const DISC: usize = 1;
const GLOW: usize = 2;
const ROLE: usize = 3;
const GLASS: usize = 4;
const NOTE: usize = 5;
const LEAD: usize = 6;

impl Marks {
    /// The marks' pictures at `scale` pixels per point; `assets` holds role_conductor.png.
    pub fn new(s: &Sizes, scale: f64, assets: &std::path::Path) -> Result<Self, String> {
        let size = (s.cover_h * 0.62).min(44.0);
        let ring = claw_marks(size, (size * 0.09).max(1.6), scale, -40.0, 3, None);
        let (glow, role, tip) = role(s.badge, scale, &assets.join("role_conductor.png"))?;
        let high = ((s.card[1] - CARD_TOP) * 0.35).min(28.0);
        let lead = |i: f64| claw_marks(s.lead * 0.62, (s.lead * 0.07).max(0.9), 3.0, -50.0 + 12.0 * i, 2, Some(s.lead * 0.16));
        let pics = vec![ring, disc(s.badge, scale), glow, role, glass(s.card, CARD_TOP, scale), note(high, scale), lead(0.0), lead(1.0)];
        Ok(Self { scale, pics, tip, tex: Vec::new() })
    }

    pub fn upload(&mut self, gpu: &mut Renderer) {
        self.tex = self.pics.iter().map(|p| gpu.add(p.w, p.h, &p.bytes())).collect();
    }

    /// The marks' pictures, in the order `Pen::picture` numbers them when nothing was uploaded.
    pub fn pics(&self) -> &[Pic] {
        &self.pics
    }

    fn draw(&self, f: &mut impl Pen, which: usize, r: [f64; 4], clip: Option<[f64; 4]>) {
        let p = &self.pics[which];
        f.picture(self.tex.get(which).copied().unwrap_or(which), (p.w, p.h), r, clip);
    }

    /// A fine lilac rim round the button in a purple haze, claw marks torn across two corners.
    pub fn ring(&self, f: &mut impl Pen, cover: [f64; 4], t: f64) {
        let [x, y, w, h] = cover;
        let radius = (h * 0.3).min(18.0);
        let c = [x + w / 2.0, y + h / 2.0];
        let halo = Paint::Radial(c, w * 0.62, stops(&[(0.6, PURPLE, 0.0), (0.85, PURPLE, 0.22), (1.0, PURPLE, 0.0)]));
        f.rrect([x - 8.0, y - 8.0, w + 16.0, h + 16.0], radius + 8.0, &halo);
        for (inset, color, alpha, width) in [(1.0, LILAC, 0.9, 2.0), (3.6, "#ffffff", 0.5, 0.9)] {
            let r = [x + inset, y + inset, w - 2.0 * inset, h - 2.0 * inset];
            f.rrect_pen(r, (radius - inset).max(1.0), width, &Paint::Solid(crate::draw::hex(color), alpha));
        }
        let side = self.pics[RING].w as f64 / self.scale;
        let cycle = t % 3.6;
        for (corner, at) in [(0.0, [x + side * 0.26, y + side * 0.24]), (1.0, [x + w - side * 0.26, y + h - side * 0.24])] {
            let strike = clamp((cycle - corner * 0.12) / 0.12);
            f.save();
            f.set_tf(f.tf().translate(at[0], at[1]));
            f.set_opacity(0.75 + 0.25 * (t * 2.4 + corner).sin());
            let clip = (strike < 1.0).then_some([-side / 2.0, -side / 2.0, side * strike, side]);
            self.draw(f, RING, [-side / 2.0, -side / 2.0, side, side], clip);
            f.restore();
        }
    }

    /// A dark misty disc in a lilac rim with the 指挥家's icon glowing on it, the baton's tip glinting.
    pub fn badge(&self, f: &mut impl Pen, b: [f64; 4], t: f64) {
        let side = b[2];
        let c = [b[0] + side / 2.0, b[1] + b[3] / 2.0];
        f.ellipse(c[0], c[1], side * 0.75, &Paint::Radial(c, side * 0.75, stops(&[(0.55, PURPLE, 0.35), (1.0, PURPLE, 0.0)])));
        self.draw(f, DISC, b, None);
        let o = f.opacity();
        f.set_opacity(0.75 + 0.25 * (t * 3.0).sin());
        self.draw(f, GLOW, b, None);
        f.set_opacity(o);
        self.draw(f, ROLE, b, None);
        let glint = clamp(1.0 - ((t % 3.4) - 0.3).abs() / 0.3);
        if glint > 0.0 {
            let at = [c[0] + self.tip[0], c[1] + self.tip[1]];
            f.soft_dot(at[0], at[1], side * 0.16, LILAC, 0.55 * glint);
            f.soft_dot(at[0], at[1], side * 0.06, "#ffffff", glint);
        }
    }

    /// Misty slate glass, a lilac edge, and the 指挥家's ♫ glowing on its top right corner.
    pub fn card(&self, f: &mut impl Pen, r: [f64; 4], t: f64) {
        self.draw(f, GLASS, r, None);
        let high = ((r[3] - CARD_TOP) * 0.35).min(28.0);
        let (w, h) = (self.pics[NOTE].w as f64 / self.scale, self.pics[NOTE].h as f64 / self.scale);
        let beat = (t * 2.2).sin();
        f.save();
        f.set_tf(f.tf().translate(r[0] + r[2] - high * 0.75, r[1] + CARD_TOP - 1.5 - 0.6 * beat));
        f.soft_dot(0.0, 0.0, high * 0.8, PURPLE, 0.22 + 0.1 * (t * 4.4).sin());
        f.set_tf(f.tf().rotate(-5.0 + 4.0 * beat));
        self.draw(f, NOTE, [-w / 2.0, -h / 2.0, w, h], None);
        f.restore();
    }

    /// The small claw mark before the index-th name, its top left at `at` (made at 3 pixels a point).
    pub fn lead(&self, f: &mut impl Pen, at: Pt, index: usize) {
        let p = &self.pics[LEAD + index % 2];
        self.draw(f, LEAD + index % 2, [at[0], at[1], p.w as f64 / 3.0, p.h as f64 / 3.0], None);
    }
}

/// What the marks draw with: claw's GPU frame (pictures by uploaded texture) or the overlay's canvas
/// (`hook`, pictures by their place in `Marks::pics`).
pub trait Pen {
    fn tf(&self) -> Affine;
    fn set_tf(&mut self, tf: Affine);
    fn opacity(&self) -> f64;
    fn set_opacity(&mut self, opacity: f64);
    fn save(&mut self);
    fn restore(&mut self);
    fn ellipse(&mut self, x: f64, y: f64, r: f64, paint: &Paint);
    fn rrect(&mut self, r: [f64; 4], radius: f64, paint: &Paint);
    fn rrect_pen(&mut self, r: [f64; 4], radius: f64, width: f64, paint: &Paint);
    fn soft_dot(&mut self, x: f64, y: f64, r: f64, color: &str, alpha: f64);
    fn picture(&mut self, id: usize, size: (usize, usize), r: [f64; 4], clip: Option<[f64; 4]>);
}

impl Pen for Frame {
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
        Frame::save(self);
    }
    fn restore(&mut self) {
        Frame::restore(self);
    }
    fn ellipse(&mut self, x: f64, y: f64, r: f64, paint: &Paint) {
        Frame::ellipse(self, x, y, r, paint);
    }
    fn rrect(&mut self, r: [f64; 4], radius: f64, paint: &Paint) {
        Frame::rrect(self, r, radius, paint);
    }
    fn rrect_pen(&mut self, r: [f64; 4], radius: f64, width: f64, paint: &Paint) {
        Frame::rrect_pen(self, r, radius, width, paint);
    }
    fn soft_dot(&mut self, x: f64, y: f64, r: f64, color: &str, alpha: f64) {
        Frame::soft_dot(self, x, y, r, color, alpha);
    }
    fn picture(&mut self, id: usize, size: (usize, usize), r: [f64; 4], clip: Option<[f64; 4]>) {
        self.image(id, size, r, clip, None);
    }
}
