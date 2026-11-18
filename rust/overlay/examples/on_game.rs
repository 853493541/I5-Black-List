//! The on-game cases of tools/ui_shots.py (game_黑名单和嘉宾, game_我的场景) drawn by this crate over the sample
//! lobby, beside the Python shots, with PSNR over the marks this crate draws (the 场景, the red glow and a
//! scene's own card come from other packages).
//!
//! cargo run -p overlay --example on_game -- <ui_shots 100-normal folder>

use std::path::{Path, PathBuf};

use image::{imageops, Rgba, RgbaImage};
use overlay::layout::{plan, Placed};
use overlay::paint::py_round;
use overlay::text::Face;
use overlay::{look_for, CheckResult, Extras, Moment, Rect, Seat, SeatKind, Style};

/// The offscreen screen ui_shots runs on, and the game in its middle, six tenths of it wide, 16:9.
const SCREEN: Rect = Rect { x: 0, y: 0, w: 800, h: 600 };
const GAME: Rect = Rect { x: 160, y: 165, w: 480, h: 270 };
/// ui_demo.BUTTON: 准备案件还原 on the sample lobby.
const BUTTON: [f32; 4] = [0.430, 0.776, 0.572, 0.846];

fn main() {
    let folder = PathBuf::from(std::env::args().nth(1).expect("the ui_shots 100-normal folder"));
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let inter = std::fs::read("/usr/share/fonts/opentype/inter/Inter-SemiBold.otf").ok();
    let face = Face::system().map(|f| match inter { Some(b) => f.with_metrics(b), None => f }).expect("a Chinese face");
    let lobby = image::open(root.join("../../blacklist_detect/assets/sample-lobby.jpg")).unwrap().to_rgba8();
    // ui_demo.sample_screen: the crop on a whole 16:9 screen (SCREEN_IN_CROP), the rest the game's edge color.
    let mut screen = RgbaImage::from_pixel(3600, 2025, Rgba([12, 16, 23, 255]));
    imageops::overlay(&mut screen, &lobby, 56, 52);
    let lobby = imageops::resize(&screen, GAME.w as u32, GAME.h as u32, imageops::FilterType::Triangle);
    let button = [0, 1, 2, 3].map(|i| py_round([GAME.x, GAME.y][i % 2] as f32 + BUTTON[i] * [GAME.w, GAME.h][i % 2] as f32));
    let seat = |name: &str, kind: SeatKind| Seat { name: name.into(), rect: [0; 4], kind };
    let both = CheckResult {
        seats: vec![seat("示例坏人", SeatKind::Blacklist { tags: vec!["炸房".into()] }), seat("心动小鹿", SeatKind::Guest)],
        button_box: Some(button),
        game_box: Some([GAME.x, GAME.y, GAME.x + GAME.w, GAME.y + GAME.h]),
    };
    let mine = CheckResult { seats: vec![], ..both.clone() };
    let look = look_for("lace");
    let style = Style { look: &look, face: Some(&face), at: Moment::default(), ratio: 1.0 };
    let cases = [
        ("33_game_黑名单和嘉宾", plan(button, &both, Extras::default(), SCREEN, &style), &["hit_card"][..]),
        ("34_game_我的场景", plan(button, &mine, Extras { mine: true, ..Extras::default() }, SCREEN, &style), &["cover", "badge"][..]),
    ];
    let mut report = String::from("case | marks compared | PSNR dB | mean diff\n---|---|---|---\n");
    for (name, marks, compared) in cases {
        let python = image::open(folder.join(format!("{name}.png"))).unwrap().to_rgba8();
        let mut ours = lobby.clone();
        for m in &marks {
            lay(&mut ours, m);
        }
        let (db, mean) = region_psnr(&python, &ours, marks.iter().filter(|m| compared.contains(&m.what)));
        report += &format!("{name} | {} | {db:.1} | {mean:.2}\n", compared.join(", "));
        let mut side = RgbaImage::from_pixel(GAME.w as u32 * 2 + 4, GAME.h as u32, Rgba([255, 0, 255, 255]));
        imageops::overlay(&mut side, &python, 0, 0);
        imageops::overlay(&mut side, &ours, GAME.w as i64 + 4, 0);
        side.save(root.join("shots").join(format!("on_{name}.png"))).unwrap();
    }
    std::fs::write(root.join("shots/on_game.md"), format!("Left: Python (ui_shots, with the scene). Right: Rust marks only.\n\n{report}")).unwrap();
    print!("{report}");
}

/// A mark over the picture of the game, source over.
fn lay(picture: &mut RgbaImage, m: &Placed) {
    let p = &m.canvas.pixmap;
    for y in 0..p.height() {
        for x in 0..p.width() {
            let (gx, gy) = (m.at.x - GAME.x + x as i32, m.at.y - GAME.y + y as i32);
            if gx < 0 || gy < 0 || gx >= GAME.w || gy >= GAME.h {
                continue;
            }
            let s = p.pixel(x, y).unwrap();
            let d = picture.get_pixel_mut(gx as u32, gy as u32);
            let rest = 1.0 - s.alpha() as f32 / 255.0;
            for (c, v) in [s.red(), s.green(), s.blue()].into_iter().enumerate() {
                d[c] = (v as f32 + d[c] as f32 * rest).round().min(255.0) as u8;
            }
        }
    }
}

fn region_psnr<'a>(a: &RgbaImage, b: &RgbaImage, marks: impl Iterator<Item = &'a Placed>) -> (f64, f64) {
    let (mut sq, mut abs, mut n) = (0.0f64, 0.0f64, 0.0f64);
    for m in marks {
        for y in m.at.y.max(GAME.y)..(m.at.y + m.at.h).min(GAME.y + GAME.h) {
            for x in m.at.x.max(GAME.x)..(m.at.x + m.at.w).min(GAME.x + GAME.w) {
                let (p, q) = (a.get_pixel((x - GAME.x) as u32, (y - GAME.y) as u32), b.get_pixel((x - GAME.x) as u32, (y - GAME.y) as u32));
                for c in 0..3 {
                    let d = p[c] as f64 - q[c] as f64;
                    sq += d * d;
                    abs += d.abs();
                    n += 1.0;
                }
            }
        }
    }
    let mse = sq / n.max(1.0);
    (if mse == 0.0 { 99.0 } else { 10.0 * (255.0f64.powi(2) / mse).log10() }, abs / n.max(1.0))
}
