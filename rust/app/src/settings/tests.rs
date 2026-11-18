//! 设置 against the Python widgets (golden.json, from tools/rust_golden_settings_ui.py), the store's part of each
//! action, the first-run card's model, and every section and card state drawn without error and fitting its room.

use data::store::settings::Settings;
use data::store::{Clock, Store};
use serde_json::Value;

use super::rows::{self, Control, SettingsState, ROWS, SECTIONS};
use super::setup::{self, SetupModel, State, Step};
use super::{action, apply, model, render, Action, Applied};
use crate::{SettingsPreview, SetupWindow};

const GOLDEN: &str = include_str!("golden.json");

fn golden() -> Value {
    serde_json::from_str(GOLDEN).expect("golden.json reads")
}

/// The state Python's golden run had: a new data folder, start with Windows not available (not Windows), v1.0.1.
fn fresh() -> SettingsState {
    SettingsState::new(&Settings::default(), false, false, "v1.0.1")
}

#[test]
fn sections_rows_wording_and_defaults_equal_python() {
    let golden = golden();
    let sections = golden["sections"].as_array().unwrap();
    assert_eq!(sections.len(), SECTIONS.len());
    let state = fresh();
    for (section, (key, title, _)) in sections.iter().zip(SECTIONS) {
        assert_eq!(section["key"], key);
        assert_eq!(section["title"], title);
        let ours = rows::rows(&state, key);
        let theirs = section["rows"].as_array().unwrap();
        assert_eq!(ours.len(), theirs.len(), "rows of {key}");
        for (row, py) in ours.iter().zip(theirs) {
            assert_eq!(py["name"], row.name);
            assert_eq!(py["description"], row.description.as_str(), "{}", row.name);
            let control = py["controls"].as_array().unwrap().iter().find(|c| c["kind"] != "note").unwrap();
            assert_eq!(control["kind"], row.kind, "{}", row.name);
            match row.kind {
                "choice" => {
                    let choices: Vec<&str> = control["choices"].as_array().unwrap().iter().map(|c| c.as_str().unwrap()).collect();
                    assert_eq!(choices, row.choices, "{}", row.name);
                    assert_eq!(control["value"], row.value.as_str(), "{}", row.name);
                    let spec = ROWS.iter().find(|s| s.key == row.key).unwrap();
                    let Control::Choice(options) = spec.control else { unreachable!() };
                    let keys: Vec<&str> = options.iter().map(|(k, _)| *k).collect();
                    assert_eq!(control["keys"].as_array().unwrap().iter().map(|k| k.as_str().unwrap()).collect::<Vec<_>>(), keys);
                }
                _ => assert_eq!(control["label"], row.label, "{}", row.name),
            }
        }
    }
}

#[test]
fn every_choice_lists_its_default_first() {
    for row in SECTIONS.iter().flat_map(|(key, _, _)| rows::rows(&fresh(), key)) {
        if row.kind == "choice" {
            assert_eq!(row.value, row.choices[0], "{}", row.name);
        }
    }
}

#[test]
fn rows_follow_the_state() {
    let mut state = SettingsState::new(
        &Settings { close_to_tray: false, sound_muted: true, appearance: "system".into(), ..Settings::default() },
        true,
        true,
        "v2.3.4",
    );
    state.update_waiting = true;
    state.update_note = "已是最新版本".into();
    let general = rows::rows(&state, "general");
    let values: Vec<&str> = general.iter().map(|r| r.value.as_str()).collect();
    assert_eq!(values, ["开启", "退出程序", "静音", "跟随系统"]);
    assert!(general[0].enabled && general[0].first && !general[1].first);
    let about = rows::rows(&state, "about");
    assert_eq!((about[0].description.as_str(), about[0].label, about[0].note.as_str()), ("当前版本 2.3.4", "有更新", "已是最新版本"));
    assert!(!rows::rows(&fresh(), "general")[0].enabled, "开机启动 grayed where it cannot be set");
}

#[test]
fn actions_from_choices_and_buttons() {
    assert_eq!(action("autostart", Some("开启")), Some(Action::SetAutostart(true)));
    assert_eq!(action("close_mode", Some("退出程序")), Some(Action::SetCloseToTray(false)));
    assert_eq!(action("mute", Some("静音")), Some(Action::SetMuted(true)));
    assert_eq!(action("mute", Some("播放")), Some(Action::SetMuted(false)));
    assert_eq!(action("appearance", Some("深色")), Some(Action::SetAppearance("dark".into())));
    assert_eq!(action("appearance", Some("紫色")), None);
    assert_eq!(action("env_test", None), Some(Action::RunEnvironmentTest));
    assert_eq!(action("export_logs", None), Some(Action::ExportLogs));
    assert_eq!(action("update", None), Some(Action::CheckUpdates));
    assert_eq!(action("disclaimer", None), Some(Action::ShowDisclaimer));
    assert_eq!(action("reset", None), Some(Action::AskReset));
}

#[test]
fn store_actions_are_saved_in_the_settings_file() {
    let folder = tempfile::tempdir().unwrap();
    let mut store = Store::open(Some(folder.path().to_path_buf()), Clock::default());
    assert_eq!(apply(&mut store, Action::SetCloseToTray(false)).unwrap(), Applied::Saved);
    assert_eq!(apply(&mut store, Action::SetMuted(true)).unwrap(), Applied::Saved);
    assert_eq!(apply(&mut store, Action::SetAppearance("dark".into())).unwrap(), Applied::Saved);
    assert_eq!(apply(&mut store, Action::AskReset).unwrap(), Applied::ForApp(Action::AskReset));
    let again = Store::open(Some(folder.path().to_path_buf()), Clock::default());
    let s = &again.settings;
    assert_eq!((s.close_to_tray, s.sound_muted, s.appearance.as_str()), (false, true, "dark"));
    let saved: Value = serde_json::from_str(&std::fs::read_to_string(again.settings_path()).unwrap()).unwrap();
    assert_eq!((saved["close_to_tray"].clone(), saved["sound_muted"].clone()), (Value::Bool(false), Value::Bool(true)));
}

#[test]
fn setup_card_wording_and_progress_follow_python() {
    let golden = golden();
    let py = &golden["setup"];
    assert_eq!(py["steps"].as_array().unwrap().iter().map(|s| s.as_str().unwrap()).collect::<Vec<_>>(), setup::STEPS);
    assert_eq!((py["running"].as_str(), py["ok"].as_str(), py["failed"].as_str()), (Some(setup::RUNNING), Some(setup::OK), Some(setup::FAILED)));
    assert_eq!(py["buttons"], serde_json::json!([setup::CLOSE, setup::RETRY]));
    let mut card = SetupModel::default();
    card.start();
    assert_eq!((card.state, card.heading()), (State::Running, setup::RUNNING));
    card.step(0, Step::Run, "");
    assert!((card.target - 0.18).abs() < 1e-9);
    card.advance();
    assert_eq!(card.bar(), 22, "first tick eases 12 % of the gap");
    card.step(0, Step::Ok, "12/12");
    card.step(1, Step::Run, "");
    while card.value < card.target - 0.0005 {
        assert!(card.advance());
    }
    assert!(card.advance(), "a running card keeps ticking at its target");
    card.fail(1, "识别功能没装好");
    assert_eq!((card.heading(), card.steps[1].0, card.message.as_str()), (setup::FAILED, Step::Fail, "识别功能没装好"));
    assert!(!card.advance(), "a failed card stops at its target");
    card.start();
    card.succeed();
    assert_eq!((card.heading(), card.target), (setup::OK, 1.0));
}

/// Every section and card state drawn without error; each section fits 900 x 560 and the card 672 px with its
/// buttons. With SETTINGS_SHOTS=<dir> the pictures are saved there, at the Windows scale SETTINGS_SCALE (1.5).
#[test]
fn every_section_and_card_state_renders_and_fits() {
    render::init();
    let scale: f32 = std::env::var("SETTINGS_SCALE").ok().and_then(|s| s.parse().ok()).unwrap_or(1.5);
    let out = std::env::var("SETTINGS_SHOTS").ok().map(std::path::PathBuf::from);
    let keep = |name: &str, (rgb, w, h): (Vec<u8>, u32, u32)| {
        let background = rgb[..3].to_vec();
        assert!(rgb.chunks(3).any(|p| p != background.as_slice()), "{name} draws something");
        if let Some(dir) = &out {
            std::fs::create_dir_all(dir).unwrap();
            render::save(&dir.join(format!("{name}.png")), &rgb, w, h).unwrap();
        }
    };
    let page = SettingsPreview::new().unwrap();
    model::show_settings(&page, &fresh());
    for dark in [false, true] {
        page.set_dark(dark);
        for (key, _, _) in SECTIONS {
            page.set_section(key.into());
            assert!(page.get_section_height() + 60.0 <= 560.0, "{key} fits 900 x 560: {}", page.get_section_height());
            keep(&format!("rust-settings-{key}{}", if dark { "-dark" } else { "" }), render::draw(&page, 900, 560, scale).unwrap());
        }
    }
    let card = SetupWindow::new().unwrap();
    let mut setup = SetupModel::default();
    setup.start();
    setup.step(0, Step::Ok, "");
    setup.step(1, Step::Ok, "");
    setup.step(2, Step::Ok, "12/12");
    setup.step(3, Step::Run, "");
    setup.value = setup.target;
    let long = "识别测试没读出名字：".repeat(12);
    for (name, finish) in [("running", 0), ("ok", 1), ("failed", 2)] {
        let mut shown = setup.clone();
        match finish {
            1 => {
                (3..5).for_each(|i| shown.step(i, Step::Ok, "1.2 秒"));
                shown.succeed();
                shown.value = 1.0;
            }
            2 => shown.fail(3, &long),
            _ => {}
        }
        model::show_setup(&card, &shown);
        keep(&format!("rust-setup-{name}"), render::draw(&card, 900, 560, scale).unwrap());
        assert!(card.get_card_height() <= 672.0, "{name} card fits 672 px: {}", card.get_card_height());
    }
}
