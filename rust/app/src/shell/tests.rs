use super::render::{draw, render_all, shots, Shot};
use super::*;

#[test]
fn pages_in_header_order() {
    let labels: Vec<_> = Page::ALL.iter().map(|page| page.label()).collect();
    assert_eq!(labels, ["记录", "黑名单", "嘉宾", "设置"]);
    assert_eq!(Page::from_index(3), Some(Page::Settings));
    assert_eq!(Page::from_index(4), None);
    assert_eq!(Page::from_index(-1), None);
}

#[test]
fn initial_is_first_letter_upper() {
    assert_eq!(initial("  测试主播"), "测");
    assert_eq!(initial("abc"), "A");
    assert_eq!(initial("   "), "");
}

#[test]
fn window_size_never_under_minimum() {
    let mut settings = Settings::default();
    assert_eq!(window_size(&settings), (900, 560));
    settings.window_size = Some((1200, 700));
    assert_eq!(window_size(&settings), (1200, 700));
    settings.window_size = Some((300, -5));
    assert_eq!(window_size(&settings), (900, 560));
}

#[test]
fn close_hides_to_tray_only_when_asked_and_a_tray_is_there() {
    assert_eq!(close_outcome(true, true, true), CloseOutcome::HideToTray);
    assert_eq!(close_outcome(true, true, false), CloseOutcome::Quit);
    assert_eq!(close_outcome(true, false, true), CloseOutcome::Quit);
    // 退出 in the tray menu, or an update: always quits.
    assert_eq!(close_outcome(false, true, true), CloseOutcome::Quit);
}

#[test]
fn model_from_settings_follows_the_store() {
    let mut settings = Settings::default();
    let model = ShellModel::from_settings(&settings);
    assert_eq!((model.status_text.as_str(), model.tone), ("手动检查", Tone::WatchOff));
    assert_eq!(model.status_key, "Alt+1");
    assert!(model.safe_mode && !model.stream_on);
    settings.auto_capture = true;
    settings.safe_mode = false;
    settings.stream_mode = "on".into();
    let model = ShellModel::from_settings(&settings);
    assert_eq!((model.status_text.as_str(), model.tone, model.status_key.as_str()), ("自动检查中", Tone::WatchOn, ""));
    assert!(model.stream_on);
    // A hotkey that is none shows no key.
    assert_eq!(status_key(""), "");
}

/// Renders every page and the panel, light and dark, without error, and checks the panel draws over the page.
#[test]
fn every_shot_renders() {
    for shot in shots() {
        for dark in [false, true] {
            let shot = Shot { model: ShellModel { dark, ..shot.model.clone() }, ..shot };
            let picture = draw(&shot, 1.5, MIN_SIZE).expect(shot.name);
            assert_eq!((picture.width, picture.height), (1350, 840), "{}", shot.name);
            break_if_blank(&picture, shot.name);
        }
    }
    let closed = draw(&shots().remove(0), 1.5, MIN_SIZE).unwrap();
    let open = draw(&shots().into_iter().find(|s| s.panel_open).unwrap(), 1.5, MIN_SIZE).unwrap();
    // The card's empty right of 方式 (logical 700, 150) is surface white over the page's background.
    let at = |p: &render::Picture| {
        let i = ((225 * p.width + 1050) * 3) as usize;
        [p.rgb[i], p.rgb[i + 1], p.rgb[i + 2]]
    };
    assert_ne!(at(&closed), at(&open));
    assert_eq!(at(&open), [0xff, 0xff, 0xff]);
}

fn break_if_blank(picture: &render::Picture, name: &str) {
    let first = &picture.rgb[..3];
    assert!(picture.rgb.chunks(3).any(|px| px != first), "{name} is one colour");
}

/// The side-by-side pictures: SHELL_PY_SHOTS=<ui_shots.py 150-normal folder> writes them into shots/shell/.
#[test]
fn side_by_side_pictures() {
    let Some(python) = std::env::var_os("SHELL_PY_SHOTS") else { return };
    let dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("shots/shell");
    let written = render_all(&dir, Some(std::path::Path::new(&python))).unwrap();
    assert!(written.iter().any(|path| path.to_string_lossy().ends_with("_side.png")));
}

/// tests/test_dialog_fit.py for the panel: it opens over the window, so it fits the 900 x 560 window, and its
/// controls are in view (the card ends above the window's bottom).
#[test]
fn panel_fits_the_smallest_window() {
    let shot = shots().into_iter().find(|s| s.name == "header_检查_直播模式").unwrap();
    let picture = draw(&Shot { model: ShellModel { hotkey_note: "这个快捷键已被其他程序占用".into(), ..shot.model }, ..shot }, 1.0, MIN_SIZE).unwrap();
    // Logical 900 x 560 at 100%: the window's bottom rows are the page's background, not the card.
    let bottom = (559 * picture.width * 3) as usize;
    let background: &[u8] = &[0xf2, 0xf6, 0xfb];
    assert!(picture.rgb[bottom..bottom + 900 * 3].chunks(3).all(|px| px == background));
    // The card ends well above the window's bottom: column 700 is back to the page under it by y = 300.
    let at = |y: u32| &picture.rgb[((y * picture.width + 700) * 3) as usize..][..3];
    assert_eq!(at(150), [0xff, 0xff, 0xff]);
    assert_ne!(at(300), [0xff, 0xff, 0xff]);
}

#[test]
fn a_key_in_the_hotkey_box_is_read_as_python_reads_it() {
    use slint::platform::Key;
    assert_eq!(pressed_key("a"), Pressed::Key(Some("A".into())));
    assert_eq!(pressed_key("1"), Pressed::Key(Some("1".into())));
    assert_eq!(pressed_key(&char::from(Key::F12).to_string()), Pressed::Key(Some("F12".into())));
    assert_eq!(pressed_key(&char::from(Key::Escape).to_string()), Pressed::Escape);
    assert_eq!(pressed_key("\u{1b}"), Pressed::Escape);
    assert_eq!(pressed_key(&char::from(Key::Alt).to_string()), Pressed::Modifier);
    assert_eq!(pressed_key(" "), Pressed::Key(None));
}

#[test]
fn a_check_problem_turns_the_pill_red_and_clearing_it_brings_back_the_idle_words() {
    use app::wiring::flow::Problem;
    use app::wiring::stubs::CheckError;
    let settings = Settings { hotkey: "F8".into(), ..Settings::default() };
    let errors = [
        (CheckError { message: "OSError".into(), ..CheckError::default() }, "检查失败", "检查失败，等会儿再试"),
        (CheckError { message: "识别功能没装好".into(), models: true, plain: true, ..CheckError::default() }, "识别还没准备好", "识别功能没装好"),
        (CheckError { message: "截图失败，再试一次".into(), plain: true, capture: true, ..CheckError::default() }, "读不到屏幕", "截图失败，再试一次"),
    ];
    for (error, label, tip) in errors {
        let mut model = ShellModel::from_settings(&settings);
        model.show_problem(Some(&Problem::of(&error)));
        assert_eq!((model.status_text.as_str(), model.tone, model.status_key.as_str(), model.status_tip.as_str()), (label, Tone::Hit, "", tip));
    }
    let mut model = ShellModel::from_settings(&settings);
    model.show_problem(None);
    assert_eq!((model.status_text.as_str(), model.tone, model.status_key.as_str()), ("手动检查", Tone::WatchOff, "F8"));
    let auto = Settings { auto_capture: true, ..settings };
    let mut model = ShellModel::from_settings(&auto);
    model.show_problem(None);
    assert_eq!((model.status_text.as_str(), model.tone), ("自动检查中", Tone::WatchOn));
}
