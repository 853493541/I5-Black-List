//! Parity with ui_overlay.py: every mark tools/rust_golden_overlay.py painted with Qt, drawn here and laid over
//! the sample lobby both ways. Sizes must match to the pixel; pictures within a PSNR floor (text rasterizes a
//! little differently). OVERLAY_SHOTS=1 writes side-by-side PNGs and the numbers to rust/overlay/shots/.

use std::path::{Path, PathBuf};

use image::{Rgba, RgbaImage};
use overlay::canvas::Canvas;
use overlay::cards::{hit_card, like_card, Person};
use overlay::marks::{badge, panel, Mode, Moment, Style};
use overlay::text::Face;
use overlay::{look_for, Look};

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).to_path_buf()
}

fn people(list: &[(&str, &[&str])]) -> Vec<Person> {
    list.iter().map(|(n, t)| Person { name: n.to_string(), tags: t.iter().map(|s| s.to_string()).collect() }).collect()
}

/// Straight-alpha RGBA from a canvas.
fn unpremultiply(c: &Canvas) -> RgbaImage {
    let p = &c.pixmap;
    RgbaImage::from_fn(p.width(), p.height(), |x, y| {
        let px = p.pixel(x, y).unwrap().demultiply();
        Rgba([px.red(), px.green(), px.blue(), px.alpha()])
    })
}

/// `mark` laid over the sample lobby at a fixed spot, RGB.
fn over_lobby(lobby: &RgbaImage, mark: &RgbaImage) -> Vec<f32> {
    let mut out = Vec::with_capacity((mark.width() * mark.height() * 3) as usize);
    for (x, y, m) in mark.enumerate_pixels() {
        let b = lobby.get_pixel((x + 300) % lobby.width(), (y + 300) % lobby.height());
        let a = m[3] as f32 / 255.0;
        for c in 0..3 {
            out.push(m[c] as f32 * a + b[c] as f32 * (1.0 - a));
        }
    }
    out
}

struct Case {
    name: String,
    canvas: Canvas,
}

fn cases(face: &Face) -> Vec<Case> {
    let mut out = Vec::new();
    for (size, (w, h)) in [("full", (176, 82)), ("small", (170, 51))] {
        for (mode, key) in ["hit", "clear", "liked", "both", "checking"].iter().flat_map(|m| {
            let keys: &[&str] = if matches!(*m, "liked" | "both") { &["lace", "ice", "stars"] } else { &["lace"] };
            keys.iter().map(move |k| (*m, *k))
        }) {
            let m = match mode {
                "hit" => Mode::Hit,
                "clear" => Mode::Clear,
                "liked" => Mode::Liked,
                "both" => Mode::Both,
                _ => Mode::Checking,
            };
            let text = if m == Mode::Checking { "检查中" } else { "" };
            let look = look_for(key);
            let style = Style { look: &look, face: Some(face), at: Moment { phase: 0.3, t: 0.0 }, ratio: 1.0 };
            let canvas = panel(w, h, m, text, &style);
            out.push(Case { name: format!("ring_{mode}_{key}_{size}"), canvas });
        }
        for (heart, key) in [(false, "lace"), (true, "lace"), (true, "ice"), (true, "stars")] {
            let canvas = badge(h, heart, &look_for(key), 0.0, 1.0);
            out.push(Case { name: format!("badge_{}_{key}_{size}", if heart { "heart" } else { "check" }), canvas });
        }
        let hits = people(&[("示例坏人", &["炸房"]), ("路过的捣蛋鬼", &["场外", "挂机"])]);
        out.push(Case { name: format!("card_hit_{size}"), canvas: hit_card(face, &hits, h, 1.0) });
        for key in ["lace", "ice", "stars"] {
            let likes = people(&[("心动小鹿", &[]), ("一起开黑的朋友", &[])]);
            let look: Look = look_for(key);
            out.push(Case { name: format!("card_like_{key}_{size}"), canvas: like_card(face, &look, &likes, h, 0.0, 1.0) });
        }
    }
    out
}

fn psnr(a: &[f32], b: &[f32]) -> (f64, f64) {
    let n = a.len().max(1) as f64;
    let mse: f64 = a.iter().zip(b).map(|(x, y)| ((x - y) as f64).powi(2)).sum::<f64>() / n;
    let mean: f64 = a.iter().zip(b).map(|(x, y)| (x - y).abs() as f64).sum::<f64>() / n;
    (if mse == 0.0 { 99.0 } else { 10.0 * (255.0f64 * 255.0 / mse).log10() }, mean)
}

#[test]
fn marks_match_python() {
    // Qt's metrics come from the face fontconfig puts first for Microsoft YaHei here (Inter), the glyphs from WenQuanYi.
    let inter = std::fs::read("/usr/share/fonts/opentype/inter/Inter-SemiBold.otf").ok();
    let Some(face) = Face::system().map(|f| match inter { Some(b) => f.with_metrics(b), None => f }) else {
        eprintln!("no Chinese face installed: parity skipped");
        return;
    };
    let golden = root().join("golden");
    let lobby = image::open(root().join("../../blacklist_detect/assets/sample-lobby.jpg")).unwrap().to_rgba8();
    let shots = std::env::var_os("OVERLAY_SHOTS").is_some();
    let mut report = String::from("mark | size | PSNR dB | mean diff\n---|---|---|---\n");
    let mut worst = 99.0f64;
    for case in cases(&face) {
        let want = image::open(golden.join(format!("{}.png", case.name))).unwrap().to_rgba8();
        let got = unpremultiply(&case.canvas);
        assert_eq!((got.width(), got.height()), (want.width(), want.height()), "{}: size", case.name);
        let (a, b) = (over_lobby(&lobby, &got), over_lobby(&lobby, &want));
        let (db, mean) = psnr(&a, &b);
        worst = worst.min(db);
        report += &format!("{} | {}x{} | {db:.1} | {mean:.2}\n", case.name, got.width(), got.height());
        if shots {
            let (w, h) = (got.width(), got.height());
            let side = RgbaImage::from_fn(w * 2 + 4, h, |x, y| {
                let (src, i) = if x < w { (&b, (y * w + x) as usize) } else if x >= w + 4 { (&a, (y * w + x - w - 4) as usize) } else { return Rgba([255, 0, 255, 255]) };
                Rgba([src[i * 3] as u8, src[i * 3 + 1] as u8, src[i * 3 + 2] as u8, 255])
            });
            side.save(root().join("shots").join(format!("{}.png", case.name))).unwrap();
        }
    }
    if shots {
        std::fs::write(root().join("shots/parity.md"), format!("Left: Python (Qt). Right: Rust (tiny-skia). Over the sample lobby.\n\n{report}")).unwrap();
    }
    eprintln!("{report}");
    assert!(worst >= 30.0, "worst PSNR {worst:.1} dB\n{report}");
}
