//! Where the marks go (ui.py _show_panel_at, _place_beside, _show_like_card) and what each case shows.

use overlay::canvas::Canvas;
use overlay::cards::{like_card, Person};
use overlay::layout::{plan, Placed};
use overlay::paint::RectF;
use overlay::text::Face;
use overlay::{look_for, render, render_without, CheckResult, Extras, Look, MarkHook, Moment, Rect, Seat, SeatKind, Style};
use std::sync::Arc;

const SCREEN: Rect = Rect { x: 0, y: 0, w: 1920, h: 1040 };
const BUTTON: [i32; 4] = [880, 970, 1180, 1046];

fn seat(name: &str, kind: SeatKind) -> Seat {
    Seat { name: name.into(), rect: [0; 4], kind }
}

fn bad(name: &str) -> Seat {
    seat(name, SeatKind::Blacklist { tags: vec!["炸房".into()] })
}

fn result(seats: Vec<Seat>, button: [i32; 4]) -> CheckResult {
    CheckResult { seats, button_box: Some(button), game_box: Some([0, 0, 1920, 1080]) }
}

fn marks(r: &CheckResult, extras: Extras, area: Rect, look: &Look, face: &Face) -> Vec<Placed> {
    plan(r.button_box.unwrap(), r, extras, area, &Style { look, face: Some(face), at: Moment::default(), ratio: 1.0 })
}

fn find<'a>(marks: &'a [Placed], what: &str) -> &'a Placed {
    marks.iter().find(|m| m.what == what).unwrap_or_else(|| panic!("no {what}"))
}

fn face() -> Option<Face> {
    Face::system()
}

#[test]
fn hit_and_guest_ring_cards_beside() {
    let Some(face) = face() else { return };
    let look = look_for("lace");
    let r = result(vec![bad("示例坏人"), seat("心动小鹿", SeatKind::Guest)], [880, 950, 1180, 1026]);
    let m = marks(&r, Extras::default(), SCREEN, &look, &face);
    let names: Vec<&str> = m.iter().map(|p| p.what).collect();
    assert_eq!(names, ["cover", "hit_card", "like_card"]);
    // The cover reaches 3 px past the button, and its window GLOW (9) further.
    let cover = Rect { x: 877, y: 947, w: 306, h: 82 };
    assert_eq!(find(&m, "cover").at, Rect { x: cover.x - 9, y: cover.y - 9, w: cover.w + 18, h: cover.h + 18 });
    let hit = find(&m, "hit_card").at;
    assert_eq!(hit.x, cover.x + cover.w + 16);
    assert_eq!(hit.y, cover.y + (cover.h - hit.h) / 2);
    let like = find(&m, "like_card").at;
    assert_eq!((like.x + like.w, like.y, like.h), (cover.x - 16, cover.y - 12, cover.h + 12));
}

#[test]
fn clear_badge_lines_up_by_what_it_draws() {
    let Some(face) = face() else { return };
    let r = result(vec![seat("路过的猫", SeatKind::None)], [880, 950, 1180, 1026]);
    let m = marks(&r, Extras::default(), SCREEN, &look_for("lace"), &face);
    assert_eq!(m.len(), 2);
    let badge = find(&m, "badge").at;
    assert_eq!((badge.x, badge.w), (877 + 306 + 16 - 9, 57 + 18));
}

#[test]
fn no_room_on_the_right_card_goes_left_and_like_card_under_it() {
    let Some(face) = face() else { return };
    let r = result(vec![bad("示例坏人"), seat("心动小鹿", SeatKind::Guest)], [40, 500, 340, 576]);
    let m = marks(&r, Extras::default(), Rect { x: 0, y: 0, w: 600, h: 1040 }, &look_for("lace"), &face);
    let hit = find(&m, "hit_card").at;
    assert!(hit.x + hit.w <= 600 - 8, "{hit:?}");
    let like = find(&m, "like_card").at;
    assert_eq!((like.x, like.y), (hit.x, hit.y + hit.h + 8));
}

#[test]
fn checking_is_the_cover_alone_and_no_button_no_marks() {
    let Some(face) = face() else { return };
    let r = result(vec![bad("示例坏人")], BUTTON);
    let m = marks(&r, Extras { checking: Some("检查中"), mine: false }, SCREEN, &look_for("lace"), &face);
    assert_eq!(m.iter().map(|p| p.what).collect::<Vec<_>>(), ["cover"]);
    let style = Style { look: &look_for("lace"), face: Some(&face), at: Moment::default(), ratio: 1.0 };
    assert!(render(&CheckResult::default(), Extras::default(), [0, 0, 1920, 1080], &style).is_none());
}

#[test]
fn the_same_person_twice_is_one_row() {
    let Some(face) = face() else { return };
    let once = marks(&result(vec![bad("示例坏人")], BUTTON), Extras::default(), SCREEN, &look_for("lace"), &face);
    let twice = marks(&result(vec![bad("示例坏人"), bad("示例坏人")], BUTTON), Extras::default(), SCREEN, &look_for("lace"), &face);
    assert_eq!(find(&once, "hit_card").at, find(&twice, "hit_card").at);
}

#[test]
fn at_150_percent_the_frame_is_drawn_in_device_pixels() {
    let Some(face) = face() else { return };
    let look = look_for("ice");
    let r = result(vec![seat("心动小鹿", SeatKind::Guest)], [1320, 1155, 1770, 1269]);
    let one = render(&r, Extras::default(), [0, 0, 2880, 1560], &Style { look: &look, face: Some(&face), at: Moment::default(), ratio: 1.0 }).unwrap();
    let big = render(&r, Extras::default(), [0, 0, 2880, 1560], &Style { look: &look, face: Some(&face), at: Moment::default(), ratio: 1.5 }).unwrap();
    // 150 %: the button is 300 x 76 logical, the cover 82 high, the frame from the like card's top (12 above the
    // cover) to the glow's bottom (9 below): 103 logical pixels, 155 device ones.
    assert_eq!(big.pixmap.height(), 155);
    assert_eq!(one.pixmap.height(), 120 + 12 + 9);
    assert!(big.x > 0 && big.y > 0 && big.y < 1155);
    let opaque = big.pixmap.pixels().iter().filter(|p| p.alpha() == 255).count();
    assert!(opaque > 1000);
}

#[test]
fn like_card_is_as_tall_as_the_cover_with_many_names() {
    let Some(face) = face() else { return };
    let people: Vec<Person> = ["心动小鹿", "心动星星", "柠檬汽水", "棉花糖"].iter().map(|n| Person { name: n.to_string(), tags: vec![] }).collect();
    for h in [51, 82] {
        let card = like_card(&face, &look_for("stars"), &people, h, 0.0, 1.0);
        assert_eq!(card.pixmap.height() as i32, h + 12);
    }
}

/// A scene that draws its own ring and card, as 演说家遇袭 and 竖琴清风 do.
struct Claw;

impl MarkHook for Claw {
    fn ring(&self, canvas: &mut Canvas, cover: RectF, _t: f32) -> bool {
        let p = overlay::paint::rrect(cover, 0.0).unwrap();
        canvas.fill(&p, tiny_skia::Shader::SolidColor(tiny_skia::Color::from_rgba8(0, 255, 0, 255)));
        true
    }
    fn draws_card(&self) -> bool {
        true
    }
    fn card(&self, _canvas: &mut Canvas, _rect: RectF, _t: f32) -> bool {
        true
    }
    fn card_top(&self) -> Option<i32> {
        Some(30)
    }
}

#[test]
fn a_scene_draws_its_own_marks_through_the_hook() {
    let Some(face) = face() else { return };
    let look = Look { marks: Some(Arc::new(Claw)), ..look_for("lace") };
    let r = result(vec![seat("心动小鹿", SeatKind::Guest)], BUTTON);
    let m = marks(&r, Extras::default(), SCREEN, &look, &face);
    let cover = &find(&m, "cover").canvas.pixmap;
    let mid = cover.pixel(cover.width() / 2, cover.height() / 2).unwrap();
    assert_eq!((mid.red(), mid.green(), mid.alpha()), (0, 255, 255));
    let like = find(&m, "like_card");
    assert_eq!(like.at.h, 82 + 30);
    // No plain card face and no knot: the top-left corner stays clear.
    assert_eq!(like.canvas.pixmap.pixel(1, 40).unwrap().alpha(), 0);
}

#[test]
fn the_stream_picture_leaves_out_the_card_with_the_names() {
    let Some(face) = face() else { return };
    let look = look_for("lace");
    let style = Style { look: &look, face: Some(&face), at: Moment::default(), ratio: 1.0 };
    let r = result(vec![bad("示例坏人")], BUTTON);
    let all = render(&r, Extras::default(), [0, 0, 1920, 1080], &style).unwrap();
    let stream = render_without(&r, Extras::default(), [0, 0, 1920, 1080], &style, &["hit_card"]).unwrap();
    assert!(stream.pixmap.width() < all.pixmap.width() || stream.pixmap.height() < all.pixmap.height());
    let same = render_without(&r, Extras::default(), [0, 0, 1920, 1080], &style, &[]).unwrap();
    assert_eq!(same.pixmap.data(), all.pixmap.data());
}
