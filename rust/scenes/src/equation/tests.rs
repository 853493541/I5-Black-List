use super::text::{Fonts, Shape};
use super::*;

/// The fonts are on this machine (FreeSerif and WenQuanYi Zen Hei here, Cambria Math and KaiTi on Windows).
fn fonts() -> Option<Fonts> {
    Fonts::load().ok()
}

#[test]
fn advances_match_qt() {
    let Some(fonts) = fonts() else { return };
    // QFontMetricsF.horizontalAdvance in this container (FreeSerif): Qt cuts FreeType's 16.16 advance to 1/64.
    if !std::path::Path::new("/usr/share/fonts/truetype/freefont/FreeSerif.ttf").exists() {
        return;
    }
    assert_eq!(fonts.advance(false, 27.0, "0"), 13.484375);
    assert_eq!(fonts.advance(false, 27.0, ") = 13 cos "), 113.03125);
    assert_eq!(fonts.advance(false, 36.0, "lim"), 47.03125);
    assert_eq!(fonts.ascent(false, 27.0), 21.59375);
}

#[test]
fn text_outline_sits_where_qt_puts_it() {
    let Some(fonts) = fonts() else { return };
    if !std::path::Path::new("/usr/share/fonts/truetype/freefont/FreeSerif.ttf").exists() {
        return;
    }
    let mut s = Shape::default();
    s.add_text(&fonts, false, 27.0, [0.0, 0.0], "0");
    // QPainterPath.addText(..., "0").boundingRect(): (0.640625, -18.25, 12.203125, 18.625).
    let r = s.rect();
    assert!((r[0] - 0.640625).abs() < 0.02 && (r[1] + 18.25).abs() < 0.02 && (r[2] - 12.203125).abs() < 0.03, "{r:?}");
}

#[test]
fn a_filled_square_covers_its_pixels() {
    let mut s = Shape::default();
    s.add_rect(1.5, 1.0, 2.0, 2.0);
    let c = s.raster(0.0, 0.0, 5, 4, 1.0);
    assert_eq!(&c[5..10], &[0.0, 0.5, 1.0, 0.5, 0.0]);
}

#[test]
fn math_italic_letters() {
    assert_eq!(formula::it("x+h"), "\u{1d465}+ℎ");
}

#[test]
fn lays_out_the_same_every_time() {
    let Some(fonts) = fonts() else { return };
    let a = Equation::sample(1920.0, 1080.0, &fonts);
    let b = Equation::sample(1920.0, 1080.0, &fonts);
    assert_eq!(a.atlas.rgba, b.atlas.rgba);
    assert_eq!(a.paint(2.0).prims.len(), b.paint(2.0).prims.len());
    // Before anything: the lobby and the paper at nothing.
    assert!(a.paint(0.0).prims.len() <= 3);
}
