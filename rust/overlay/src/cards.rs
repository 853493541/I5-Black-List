//! The cards beside the cover: who on the 黑名单 is here, crimson edged in gold with their tags (HitCard), and the
//! 嘉宾 here, in the look of their scene with a flower before each name and a knot on top (LikeCard). Laid out
//! as Qt's layouts lay out the Python widgets; three names show and the rest wait under a fade.

use tiny_skia::{Color, Shader};

use crate::canvas::Canvas;
use crate::look::Look;
use crate::paint::{flower, hex, knot, linear, py_round, rrect, RectF};
use crate::text::Face;

/// The cover's height round 准备案件还原 on a full-screen 1080 px game (FULL_COVER), and the smallest card text.
pub const FULL_COVER: i32 = 82;
pub const CARD_MIN_PT: f32 = 9.0;
pub const OVERLAY_PT: f32 = 13.5;
const SMALL_PT: f32 = 9.0;
const SHOWN: usize = 3;

/// A person on a card: the name shown and, on the 黑名单 card, up to three tags.
#[derive(Clone, Debug, PartialEq)]
pub struct Person {
    pub name: String,
    pub tags: Vec<String>,
}

fn px(point: f32) -> f32 {
    point * 96.0 / 72.0
}

fn round1(v: f32) -> f32 {
    (v * 10.0).round() / 10.0
}

/// The names' point size for a cover `height` high.
pub fn point_for(height: i32) -> f32 {
    round1((OVERLAY_PT * (height as f32 / FULL_COVER as f32).min(1.0)).max(CARD_MIN_PT))
}

struct Row {
    lead: i32,
    name_w: i32,
    pills: Vec<(String, i32)>,
    height: i32,
}

/// Where everything on a card goes, in the card's logical pixels.
struct Layout {
    point: f32,
    scale: f32,
    pad: [i32; 4],
    spacing: i32,
    name_w: i32,
    rows: Vec<Row>,
    content_w: i32,
    visible: i32,
    full: i32,
    pill_h: i32,
}

impl Layout {
    fn new(face: &Face, people: &[Person], point: f32, pad: [i32; 4], lead: i32) -> Layout {
        let scale = point / OVERLAY_PT;
        let pad = pad.map(|p| py_round(p as f32 * scale));
        let spacing = py_round(4.0 * scale).max(2);
        let name_px = px(point);
        // A QLabel's height: the line and one pixel (QLabel.sizeHint).
        let label_h = face.height(name_px) + 1;
        let name_w = people.iter().map(|p| face.advance(&p.name, name_px)).max().unwrap_or(0);
        let pill_h = face.height(px(SMALL_PT)) + 7;
        let rows: Vec<Row> = people
            .iter()
            .map(|p| {
                let pills: Vec<(String, i32)> =
                    p.tags.iter().take(3).map(|t| (t.clone(), face.advance(t, px(SMALL_PT)) + 18)).collect();
                let height = if pills.is_empty() { label_h.max(lead) } else { label_h.max(pill_h).max(lead) };
                Row { lead, name_w, pills, height }
            })
            .collect();
        let width = |r: &Row| (if r.lead > 0 { r.lead + 6 } else { 0 }) + r.name_w + 8 + r.pills.iter().map(|(_, w)| 6 + w).sum::<i32>();
        let content_w = rows.iter().map(width).max().unwrap_or(0).max(1);
        let sum = |n: usize| rows.iter().take(n).map(|r| r.height).sum::<i32>() + spacing * (n.max(1) as i32 - 1);
        let (visible, full) = (sum(rows.len().min(SHOWN)).max(1), sum(rows.len()).max(1));
        Layout { point, scale, pad, spacing, name_w, rows, content_w, visible, full, pill_h }
    }

    fn bar(&self) -> i32 {
        if self.rows.len() > SHOWN {
            9
        } else {
            0
        }
    }

    fn width(&self) -> i32 {
        self.pad[0] + self.content_w + self.bar() + self.pad[2]
    }

    fn body_height(&self) -> i32 {
        self.pad[1] + self.visible + self.pad[3]
    }
}

/// The colors and extras that make a card a 黑名单 one or a 嘉宾 one.
struct Dress<'a> {
    colors: (Color, Color),
    edge: Color,
    radius: f32,
    ink: Color,
    look: Option<&'a Look>,
}

fn paint_rows(canvas: &mut Canvas, face: &Face, layout: &Layout, people: &[Person], dress: &Dress, at: (i32, i32), room: i32) {
    let name_px = px(layout.point);
    let (ascent, label_h) = (face.ascent(name_px), face.height(name_px) + 1);
    let (small, small_h) = (px(SMALL_PT), face.height(px(SMALL_PT)));
    let mut y = at.1;
    for (index, (row, person)) in layout.rows.iter().zip(people).enumerate() {
        if y - at.1 >= room {
            break;
        }
        let mut x = at.0;
        if row.lead > 0 {
            if let Some(look) = dress.look {
                lead(canvas, look, layout.scale, index, x, y + (row.height - row.lead) / 2);
            }
            x += row.lead + 6;
        }
        let label_y = y + (row.height - label_h) / 2;
        face.draw(canvas, &person.name, x as f32, (label_y + ascent) as f32, name_px, dress.ink);
        x += layout.name_w + 8;
        for (tag, w) in &row.pills {
            x += 6;
            let top = y + (row.height - layout.pill_h) / 2;
            let body = RectF::new(x as f32, (top + 1) as f32, (*w - 1) as f32, (layout.pill_h - 2) as f32);
            if let Some(p) = rrect(body, body.h / 2.0) {
                canvas.fill(&p, Shader::SolidColor(hex("#2a0a0e", 1.0)));
            }
            let tx = body.x + 9.0 + ((body.w - 18.0) - face.advance(tag, small) as f32) / 2.0;
            let baseline = body.y + (body.h - small_h as f32) / 2.0 + face.ascent(small) as f32;
            face.draw(canvas, tag, tx, baseline.floor(), small, hex("#ffcf9e", 1.0));
            x += w;
        }
        y += row.height + layout.spacing;
    }
}

/// The flower before a 嘉宾's name (flower_pixmap), or the scene's own lead.
fn lead(canvas: &mut Canvas, look: &Look, scale: f32, index: usize, x: i32, y: i32) {
    if let Some(hook) = look.hook() {
        if let Some(picture) = hook.lead(18.0 * scale, index) {
            if let Some(p) = picture {
                let r = canvas.ratio;
                canvas.draw_pixmap((x as f32 * r).round() as i32, (y as f32 * r).round() as i32, &p);
            }
            return;
        }
    }
    let radius = 7.5 * scale;
    let side = py_round(radius * 2.4) as f32;
    let which = index % 2;
    flower(canvas, x as f32 + side / 2.0, y as f32 + side / 2.0 + radius * 0.05, radius, look.flowers[which], [18.0, 40.0][which], 1.15);
}

fn card_face(canvas: &mut Canvas, body: RectF, dress: &Dress) {
    let fill = linear((body.x, body.y), (body.x, body.bottom()), &[(0.0, dress.colors.0), (1.0, dress.colors.1)]);
    if let Some(p) = rrect(body, dress.radius) {
        canvas.fill(&p, fill);
    }
    if let Some(p) = rrect(body.adjusted(0.5, 0.5, -0.5, -0.5), dress.radius - 0.5) {
        canvas.stroke(&p, Shader::SolidColor(dress.edge), 1.0);
    }
}

/// The bottom of a card with more than three names fades out (_Fade).
fn fade(canvas: &mut Canvas, x: i32, bottom: i32, width: i32, color: Color) {
    let top = (bottom - 16) as f32;
    let (mut clear, mut deep) = (color, color);
    clear.set_alpha(0.0);
    deep.set_alpha(235.0 / 255.0);
    if let Some(p) = rrect(RectF::new(x as f32, top, width as f32, 16.0), 0.0) {
        canvas.fill(&p, linear((0.0, top), (0.0, bottom as f32), &[(0.0, clear), (1.0, deep)]));
    }
}

/// The 黑名单 card for a cover `cover_height` high.
pub fn hit_card(face: &Face, people: &[Person], cover_height: i32, ratio: f32) -> Canvas {
    let layout = Layout::new(face, people, point_for(cover_height), [12, 8, 12, 8], 0);
    let (w, h) = (layout.width(), layout.body_height());
    let mut canvas = Canvas::new(w, h, ratio);
    let dress = Dress {
        colors: (hex("#7a1620", 1.0), hex("#4e0c13", 1.0)),
        edge: Color::from_rgba8(228, 196, 126, 220),
        radius: 8.0,
        ink: hex("#fff3e0", 1.0),
        look: None,
    };
    card_face(&mut canvas, RectF::new(0.0, 0.0, w as f32, h as f32), &dress);
    paint_rows(&mut canvas, face, &layout, people, &dress, (layout.pad[0], layout.pad[1]), layout.visible);
    if layout.full > layout.visible {
        fade(&mut canvas, layout.pad[0], layout.pad[1] + layout.visible, layout.content_w, dress.colors.1);
    }
    canvas
}

/// Room above the 嘉宾 card for its knot, or the scene's ornament (LikeCard.top).
pub fn like_top(look: &Look) -> i32 {
    look.hook().and_then(|h| h.card_top()).unwrap_or(12)
}

/// The 嘉宾 card: as tall as the cover, its names in the middle, smaller when three would not fit at full size.
pub fn like_card(face: &Face, look: &Look, people: &[Person], cover_height: i32, t: f32, ratio: f32) -> Canvas {
    let hook = look.hook();
    let pad = hook.and_then(|h| h.card_pad()).unwrap_or([12, 8, 12, 8]);
    let mut point = point_for(cover_height);
    let lead_for = |point: f32| if hook.is_some_and(|h| h.lead(18.0, 0).is_some()) { py_round(18.0 * point / OVERLAY_PT) } else { py_round(7.5 * point / OVERLAY_PT * 2.4) };
    let mut layout = Layout::new(face, people, point, pad, lead_for(point));
    while layout.body_height() > cover_height && point > CARD_MIN_PT {
        point = round1((point - 0.5).max(CARD_MIN_PT));
        layout = Layout::new(face, people, point, pad, lead_for(point));
    }
    let top = like_top(look);
    let w = layout.width();
    let mut canvas = Canvas::new(w, cover_height + top, ratio);
    let whole = RectF::new(0.0, 0.0, w as f32, (cover_height + top) as f32);
    let drawn = hook.is_some_and(|h| h.draws_card()) && hook.is_some_and(|h| h.card(&mut canvas, whole, t));
    let dress = Dress {
        colors: (hex(look.card.0, 1.0), hex(look.card.1, 1.0)),
        edge: hex(look.edge, 1.0),
        radius: 10.0,
        ink: hex(look.ink, 1.0),
        look: Some(look),
    };
    if !drawn {
        card_face(&mut canvas, RectF::new(0.0, top as f32, w as f32, cover_height as f32), &dress);
    }
    let room = (cover_height - layout.pad[1] - layout.pad[3]).max(1);
    let shown = layout.visible.min(room);
    let y = top + layout.pad[1] + (room - shown) / 2;
    paint_rows(&mut canvas, face, &layout, people, &dress, (layout.pad[0], y), shown);
    if layout.full > shown {
        fade(&mut canvas, layout.pad[0], y + shown, layout.content_w, dress.colors.1);
    }
    if !drawn {
        // The knot of flowers on the card's top edge (_CardKnot, 40 x 28, centered).
        let x = ((w - 40) / 2) as f32;
        knot(&mut canvas, x + 20.0, 12.0, 10.0, 1.3, look);
    }
    canvas
}
