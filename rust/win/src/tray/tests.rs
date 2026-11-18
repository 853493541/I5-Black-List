//! The tray model against tests/golden/tray.json, which tools/rust_golden_tray.py reads from the Python app.

use super::icon::{entries, pick, APP_ICO};
use super::model::*;
use super::TrayAction;
use serde_json::Value;
use sha1::{Digest, Sha1};

fn golden() -> Value {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/golden/tray.json");
    serde_json::from_str(&std::fs::read_to_string(path).expect("tray.json")).expect("json")
}

fn state_of(entry: &Value) -> TrayState {
    TrayState {
        close_to_tray: entry["close_to_tray"].as_bool().unwrap(),
        dark: entry["appearance"].as_str() == Some("dark"),
    }
}

fn does(action: Option<TrayAction>) -> Vec<&'static str> {
    match action {
        Some(TrayAction::ShowMainWindow) => vec!["show"],
        Some(TrayAction::Quit) => vec!["close"],
        None => vec![],
    }
}

#[test]
fn menu_matches_python_in_every_state() {
    let data = golden();
    let states = data["states"].as_array().unwrap();
    assert_eq!(states.len(), 4);
    for entry in states {
        let state = state_of(entry);
        let ours = menu(&state);
        let theirs = entry["items"].as_array().unwrap();
        assert_eq!(ours.len(), theirs.len(), "{state:?}");
        for (mine, py) in ours.iter().zip(theirs) {
            assert_eq!(mine.text, py["text"].as_str().unwrap());
            assert_eq!(mine.enabled, py["enabled"].as_bool().unwrap());
            assert_eq!(mine.checkable, py["checkable"].as_bool().unwrap());
            assert_eq!(mine.checked, py["checked"].as_bool().unwrap());
            assert_eq!(mine.separator, py["separator"].as_bool().unwrap());
            let py_does: Vec<&str> = py["does"].as_array().unwrap().iter().map(|v| v.as_str().unwrap()).collect();
            assert_eq!(does(mine.action), py_does, "{}", mine.text);
        }
        assert_eq!(TOOLTIP, entry["tooltip"].as_str().unwrap());
    }
}

#[test]
fn clicks_match_python() {
    let data = golden();
    for entry in data["states"].as_array().unwrap() {
        let clicks = entry["clicks"].as_object().unwrap();
        assert_eq!(clicks.len(), Click::ALL.len());
        for click in Click::ALL {
            let py: Vec<&str> = clicks[click.qt_name()].as_array().unwrap().iter().map(|v| v.as_str().unwrap()).collect();
            let ours = match on_click(click) {
                ClickOutcome::Send(action) => does(Some(action)),
                // Qt opens the context menu itself; _on_tray does nothing for it.
                ClickOutcome::OpenMenu | ClickOutcome::Nothing => vec![],
            };
            assert_eq!(ours, py, "{click:?}");
        }
        assert_eq!(on_click(Click::Context), ClickOutcome::OpenMenu);
    }
}

#[test]
fn x_button_matches_python() {
    let data = golden();
    for entry in data["states"].as_array().unwrap() {
        let state = state_of(entry);
        let want = match entry["x_button"].as_str().unwrap() {
            "hide" => CloseOutcome::HideToTray,
            _ => CloseOutcome::Quit,
        };
        assert_eq!(x_button(state.close_to_tray, true), want);
    }
    // No icon in the tray: X always quits, or there is no way back.
    assert_eq!(x_button(true, false), CloseOutcome::Quit);
}

#[test]
fn command_ids_round_trip() {
    let state = TrayState::default();
    for (index, item) in menu(&state).iter().enumerate() {
        assert_eq!(action_for_command(&state, command_id(index)), item.action);
    }
    assert_eq!(action_for_command(&state, 0), None);
    assert_eq!(action_for_command(&state, 99), None);
}

#[test]
fn tray_events_map_like_qt() {
    assert_eq!(click_for_event(NIN_SELECT), Some(Click::Trigger));
    assert_eq!(click_for_event(NIN_KEYSELECT), Some(Click::Trigger));
    assert_eq!(click_for_event(WM_LBUTTONDBLCLK), Some(Click::DoubleClick));
    assert_eq!(click_for_event(WM_CONTEXTMENU), Some(Click::Context));
    assert_eq!(click_for_event(WM_MBUTTONUP), Some(Click::MiddleClick));
    // Mouse moves and the button-down halves do nothing.
    assert_eq!(click_for_event(0x0200), None);
    assert_eq!(click_for_event(0x0201), None);
}

#[test]
fn icon_is_the_python_one() {
    let sum: String = Sha1::digest(APP_ICO).iter().map(|b| format!("{b:02x}")).collect();
    assert_eq!(sum, golden()["icon_sha1"].as_str().unwrap());
    let all = entries(APP_ICO).unwrap();
    assert_eq!(all.iter().map(|e| e.size).collect::<Vec<_>>(), [16, 20, 24, 32, 40, 48, 64, 128, 256]);
}

#[test]
fn icon_size_is_picked_up_from_the_request() {
    let png = |size| &pick(APP_ICO, size).unwrap()[..4];
    assert_eq!(png(16), b"\x89PNG");
    let len = |size| pick(APP_ICO, size).unwrap().len();
    let by_size = |want| entries(APP_ICO).unwrap().into_iter().find(|e| e.size == want).unwrap().len;
    assert_eq!(len(16), by_size(16));
    assert_eq!(len(18), by_size(20)); // 16 px at 112 %: the next one up
    assert_eq!(len(24), by_size(24)); // 150 %
    assert_eq!(len(32), by_size(32)); // 200 %
    assert_eq!(len(300), by_size(256)); // bigger than any: the biggest
}

#[test]
fn broken_icons_are_refused() {
    assert_eq!(entries(b""), None);
    assert_eq!(entries(&[0, 0, 2, 0, 0, 0]), None); // a cursor file
    let mut cut = APP_ICO[..200].to_vec();
    cut.truncate(200);
    assert_eq!(entries(&cut), None); // entries point past the end
}

#[test]
fn tooltip_text_is_cut_to_fit() {
    let tip: [u16; 4] = wide_fixed("显示主窗口");
    assert_eq!(tip, ['显' as u16, '示' as u16, '主' as u16, 0]);
    let empty: [u16; 128] = wide_fixed(TOOLTIP);
    assert!(empty.iter().all(|&u| u == 0));
}
