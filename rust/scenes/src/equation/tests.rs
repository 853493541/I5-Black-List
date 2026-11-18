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
    assert_eq!(&c[5..10], &[0.0, 128.0 / 255.0, 1.0, 128.0 / 255.0, 0.0]);
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

#[test]
fn a_slanted_edge_covers_by_area() {
    // A triangle under the diagonal of a 4x4 box: pixels on the diagonal half covered.
    let mut s = Shape::default();
    s.add_rect(0.0, 0.0, 0.0, 0.0);
    let mut t = Shape::default();
    t.lines = vec![([0.0, 0.0], [4.0, 4.0]), ([4.0, 4.0], [0.0, 4.0]), ([0.0, 4.0], [0.0, 0.0])];
    let c = t.raster(0.0, 0.0, 4, 4, 1.0);
    for y in 0..4 {
        for x in 0..4 {
            let want = if x == y { 0.5 } else if x < y { 1.0 } else { 0.0 };
            assert!((c[y * 4 + x] - want).abs() < 0.01, "({x}, {y}): {} {c:?}", c[y * 4 + x]);
        }
    }
    let mut t = Shape::default();
    t.lines = vec![([0.0, 0.0], [1.0, 4.0]), ([1.0, 4.0], [0.0, 4.0]), ([0.0, 4.0], [0.0, 0.0])];
    let c = t.raster(0.0, 0.0, 2, 4, 1.0);
    // Row 0: the edge runs from x 0 to 0.25, covering 0.125 of the pixel.
    assert!((c[0] - 0.125).abs() < 0.01 && (c[6] - 0.875).abs() < 0.01, "{c:?}");
}


/// The PSNR floor against the Python frames (rust/scenes/equation/py_t*.png, made here with FreeSerif):
/// only where those fonts are what Fonts::load finds and a Vulkan (or other) adapter exists.
#[test]
fn frames_stay_close_to_python() {
    let dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("equation");
    let Some(fonts) = fonts() else { return };
    if !std::path::Path::new("/usr/share/fonts/truetype/freefont/FreeSerif.ttf").exists() || std::path::Path::new("C:\\Windows\\Fonts\\cambria.ttc").exists() {
        return;
    }
    let Ok(lobby) = image::open(dir.join("lobby_1920.png")) else { return };
    let scene = Equation::sample(1920.0, 1080.0, &fonts);
    let Ok(gpu) = gpu::Renderer::new(1920, 1080, lobby.to_rgba8().as_raw(), &scene.atlas) else { return };
    gpu.set_paper(&scene.paper());
    for (t, floor) in [(0.5, 44.0), (3.0, 38.5)] {
        gpu.render(&scene.paint(t));
        let ours = gpu.read();
        let theirs = image::open(dir.join(format!("py_t{t:.1}.png"))).expect("python frame").to_rgba8();
        let sq: f64 = ours.chunks(4).zip(theirs.as_raw().chunks(4)).map(|(a, b)| (0..3).map(|c| (f64::from(a[c]) - f64::from(b[c])).powi(2)).sum::<f64>()).sum();
        let psnr = 10.0 * (255.0f64.powi(2) / (sq / (1920.0 * 1080.0 * 3.0)).max(1e-9)).log10();
        assert!(psnr >= floor, "t={t}: PSNR {psnr:.1} dB under {floor}");
    }
}
