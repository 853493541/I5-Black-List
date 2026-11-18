//! The layered window on Windows (the windows-latest CI job): made off-screen, given a frame, its styles checked,
//! moved, hidden, destroyed.
#![cfg(windows)]

use overlay::window::{LayeredWindow, Overlay, EX_STYLE};
use overlay::{look_for, CheckResult, Seat, SeatKind};
use windows::Win32::UI::WindowsAndMessaging::{WS_EX_LAYERED, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_EX_TRANSPARENT};

#[test]
fn layered_click_through_topmost_and_updated() {
    let window = LayeredWindow::new().expect("window");
    let style = window.ex_style();
    for flag in [WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE, WS_EX_TOPMOST] {
        assert_ne!(style & flag.0, 0, "style {style:#x} lacks {:#x}", flag.0);
    }
    assert_eq!(style & EX_STYLE.0, EX_STYLE.0);
    let mut frame = tiny_skia::Pixmap::new(64, 48).unwrap();
    frame.fill(tiny_skia::Color::from_rgba8(168, 38, 47, 200));
    window.update(-4000, -4000, &frame, 255).expect("UpdateLayeredWindow");
    window.move_to(-4100, -4000).expect("move");
    window.hide();
}

#[test]
fn overlay_shows_follows_and_hides() {
    let mut overlay = Overlay::new().expect("overlay");
    let game = [-3000, -2000, -1080, -920];
    let result = CheckResult {
        seats: vec![Seat { name: "示例坏人".into(), rect: [0; 4], kind: SeatKind::Blacklist { tags: vec!["炸房".into()] } }],
        button_box: Some([-2200, -1000, -1900, -924]),
        game_box: Some(game),
    };
    assert!(overlay.show(game, &result, &look_for("lace")).expect("show"));
    assert!(overlay.is_shown());
    overlay.follow([-2990, -2000, -1070, -920]).expect("follow");
    overlay.hide();
    assert!(!overlay.is_shown());
    assert!(!overlay.show(game, &CheckResult::default(), &look_for("lace")).expect("nothing to show"));
}
