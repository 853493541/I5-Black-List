//! The dialogs' tests: ScenePane's rules against what the Python pane does (golden/pane.txt, written by
//! golden/pane.py), every dialog drawn, each fitting 672 px of usable height (1080p at 150 %) with its buttons in
//! view (tests/test_dialog_fit.py), and the actions each sends.

use std::cell::RefCell;
use std::path::PathBuf;
use std::rc::Rc;

use slint::{LogicalSize, Model, ModelRc, VecModel};

use super::dialogs::{self, GuestFields, ManagerState, Person};
use super::pane::Pane;
use super::render::{save, Renderer};
use super::{poster, ComboAction, GuestAction, Scenes, RANDOM, SCENES};
use crate::GuestSceneItem;

/// tests/test_dialog_fit.py: the usable height of a 1080p screen at 150 %.
const USABLE: f32 = 672.0;
/// The gray margin the renderer leaves round the card (its shadow's room).
const MARGIN: f32 = 22.0;

fn split(field: &str) -> Vec<String> {
    field.split(',').filter(|key| !key.is_empty()).map(str::to_string).collect()
}

#[test]
fn pane_matches_python() {
    let golden = include_str!("golden/pane.txt");
    let mut count = 0;
    for line in golden.lines() {
        let f: Vec<&str> = line.split('|').collect();
        let mut pane = Pane::new(Scenes { keys: split(f[0]), random: f[1] == "true" });
        assert_eq!(pane.selected, f[3], "{line}");
        for step in split(f[2]) {
            match step.strip_prefix("tick:") {
                Some(key) => pane.tick(key),
                None => pane.toggle_play(),
            }
        }
        let ticked: Vec<String> = std::iter::once(RANDOM.0)
            .chain(SCENES.iter().map(|(key, _, _)| *key))
            .filter(|key| pane.ticked(key))
            .map(str::to_string)
            .collect();
        let value = pane.value();
        assert_eq!(pane.playing(), f[4] == "true", "{line}");
        assert_eq!(ticked, split(f[5]), "{line}");
        assert_eq!(value, Scenes { keys: split(f[6]), random: f[7] == "true" }, "{line}");
        assert_eq!(pane.has_changes(), f[8] == "true", "{line}");
        count += 1;
    }
    assert_eq!(count, 55);
}

#[test]
fn every_poster_loads() {
    for (key, _, _) in SCENES {
        assert!(poster::poster(key).size().width > 0, "{key}");
    }
    // One this version does not have shows 经典's.
    assert_eq!(poster::poster("gone").size(), poster::poster("classic").size());
}

#[test]
fn combo_lists_its_own_first() {
    let likes: Vec<Person> = [("心动星星", "心动星星"), ("心动小鹿", "小鹿"), ("一起开黑的朋友", "一起开黑的朋友")]
        .iter()
        .map(|(name, shown)| Person { name: name.to_string(), shown: shown.to_string() })
        .collect();
    let names = vec!["心动星星".to_string(), "示例坏人".to_string()];
    let rows = dialogs::combo_people(&likes, &names);
    let said: Vec<(&str, bool, bool)> = rows.iter().map(|(n, item)| (n.as_str(), item.ticked, item.gone)).collect();
    assert_eq!(said, [("心动星星", true, false), ("示例坏人", true, true), ("一起开黑的朋友", false, false), ("心动小鹿", false, false)]);
}

fn sixteen(rows: ModelRc<GuestSceneItem>) -> ModelRc<GuestSceneItem> {
    let mut items: Vec<GuestSceneItem> = rows.iter().collect();
    let more: Vec<GuestSceneItem> = items.iter().take(16 + 1 - items.len()).cloned().collect();
    items.extend(more.into_iter().map(|item| GuestSceneItem { key: format!("{}2", item.key).into(), ..item }));
    ModelRc::from(Rc::new(VecModel::from(items)))
}

fn people() -> Vec<Person> {
    ["心动星星", "心动小鹿", "一起开黑的朋友"].iter().map(|name| Person { name: name.to_string(), shown: name.to_string() }).collect()
}

/// Every dialog drawn at its own size, scale 1.5; each fits USABLE with its buttons in view, and the 嘉宾 and 组合
/// dialogs keep their height as scenes are added (the list scrolls), while 场景管理 grows with each and holds 16.
/// GUESTEDIT_SHOTS=<dir> keeps the pictures there (rust/app/shots/guestedit for the side-by-side ones).
#[test]
fn dialogs_draw_and_fit() {
    let renderer = Renderer::new().unwrap();
    let dir = std::env::var_os("GUESTEDIT_SHOTS").map(PathBuf::from).unwrap_or_else(|| std::env::temp_dir().join("guestedit-shots"));
    let seen = Rc::new(RefCell::new(Vec::new()));
    let fits = |name: &str, height: f32, bottom: f32| {
        assert!(height - 2.0 * MARGIN <= USABLE, "{name}: card {height} tall");
        assert!(bottom <= height - MARGIN + 0.5, "{name}: buttons at {bottom}, window {height}");
    };
    let draw = |name: &str, size: &dyn Fn() -> (f32, f32), handle: &dyn Fn(LogicalSize) -> Result<(), Box<dyn std::error::Error>>| {
        let (w, h) = size();
        handle(LogicalSize::new(w, h)).unwrap();
        println!("{name}: {w} x {h}");
    };
    for (name, editing) in [("添加嘉宾", false), ("编辑嘉宾", true)] {
        let fields = GuestFields {
            name: if editing { "心动小鹿".into() } else { String::new() },
            nickname: if editing { "小鹿".into() } else { String::new() },
            reason: if editing { "声音好听".into() } else { String::new() },
            scenes: if editing { Scenes::of(&["stars"]) } else { Scenes::default() },
            editing,
        };
        let s = seen.clone();
        let ui = dialogs::guest(fields, move |action| s.borrow_mut().push(format!("{action:?}"))).unwrap();
        let size = || (ui.get_natural_width(), ui.get_natural_height());
        draw(name, &size, &|logical| {
            let (pixels, physical) = renderer.draw(&ui, logical)?;
            save(&dir.join(format!("rust-{name}.png")), &pixels, physical)
        });
        fits(name, ui.get_natural_height(), ui.get_buttons_bottom());
        let before = ui.get_natural_height();
        ui.set_scenes(sixteen(ui.get_scenes()));
        assert_eq!(ui.get_natural_height(), before, "{name}: a scene added scrolls the list");
    }
    for (name, editing) in [("添加组合", false), ("编辑组合", true)] {
        let names = ["心动小鹿".to_string(), "心动星星".to_string()];
        let combo = editing.then(|| (&names[..], Scenes::of(&["angel"])));
        let ui = dialogs::combo(&people(), combo, |_| {}).unwrap();
        let size = || (ui.get_natural_width(), ui.get_natural_height());
        draw(name, &size, &|logical| {
            let (pixels, physical) = renderer.draw(&ui, logical)?;
            save(&dir.join(format!("rust-{name}.png")), &pixels, physical)
        });
        fits(name, ui.get_natural_height(), ui.get_buttons_bottom());
        let before = ui.get_natural_height();
        ui.set_scenes(sixteen(ui.get_scenes()));
        assert_eq!(ui.get_natural_height(), before, "{name}: a scene added scrolls the list");
    }
    // 场景管理 at its tallest (test_scene_manager_with_three_songs_fits_a_short_screen_without_scrolling): 默认 and
    // three songs, a note of two lines under the hotkey; drawn as it usually opens, with 默认 alone.
    let mut state = ManagerState {
        shown: "classic".into(),
        hotkey_scene: "classic".into(),
        hotkey: "Alt+F12".into(),
        own: vec!["fluffy".into()],
        volume: 100,
        ..ManagerState::default()
    };
    let ui = dialogs::scene_manager(&state, |_| {}).unwrap();
    let size = || (ui.get_natural_width(), ui.get_natural_height());
    draw("场景管理", &size, &|logical| {
        let (pixels, physical) = renderer.draw(&ui, logical)?;
        save(&dir.join("rust-场景管理.png"), &pixels, physical)
    });
    state.songs = vec!["一个名字很长很长很长很长很长很长的心动音乐.mp3".into(), "小星星.wav".into(), "心动音乐.mp3".into()];
    let ui = dialogs::scene_manager(&state, |_| {}).unwrap();
    ui.set_note("场景快捷键 Ctrl+Shift+F12 已不能用，换成了 Alt+F12".into());
    assert!(ui.get_natural_height() - 2.0 * MARGIN <= USABLE - 8.0, "场景管理: card {}", ui.get_natural_height());
    fits("场景管理", ui.get_natural_height(), ui.get_buttons_bottom());
    // Its left keeps every scene in view: each one added makes it taller.
    let before = ui.get_natural_height();
    ui.set_scenes(sixteen(ui.get_scenes()));
    assert!(ui.get_natural_height() > before, "场景管理 keeps every scene in view");
}

/// test_the_combo_dialogs_fit_a_short_screen_however_many_guests: 60 嘉宾 scroll in their box, with
/// 至少选两位嘉宾 under it, and the dialog keeps its height.
#[test]
fn combo_dialog_keeps_its_height_however_many_guests() {
    let _renderer = Renderer::new().unwrap();
    let mut heights = Vec::new();
    for count in [0, 2, 20, 60] {
        let likes: Vec<Person> = (0..count)
            .map(|index| Person { name: format!("心动小鹿的好朋友{index:04}"), shown: format!("心动小鹿的好朋友{index:04}") })
            .collect();
        let ui = dialogs::combo(&likes, None, |_| {}).unwrap();
        ui.set_people_error("至少选两位嘉宾".into());
        assert!(ui.get_natural_height() - 2.0 * MARGIN <= USABLE, "{count}: {}", ui.get_natural_height());
        heights.push(ui.get_natural_height());
    }
    assert!(heights.iter().all(|height| *height == heights[0]), "{heights:?}");
}

#[test]
fn guest_dialog_says_what_was_asked() {
    let _renderer = Renderer::new().unwrap();
    let seen = Rc::new(RefCell::new(Vec::new()));
    let s = seen.clone();
    let fields = GuestFields { name: "心动小鹿".into(), scenes: Scenes::default(), editing: true, ..GuestFields::default() };
    let ui = dialogs::guest(fields, move |action| s.borrow_mut().push(action)).unwrap();
    assert!(!ui.get_playing());
    // A scene's box ticked with 播放场景 off: on, with that one alone; its name clicked plays it.
    ui.invoke_ticked("lyre".into());
    ui.invoke_picked("lyre".into());
    ui.set_reason("每次都带我赢".into());
    ui.invoke_save();
    ui.invoke_remove();
    assert!(ui.get_playing());
    let save = GuestAction::Save {
        name: "心动小鹿".into(),
        nickname: String::new(),
        reason: "每次都带我赢".into(),
        scenes: Scenes::of(&["lyre"]),
    };
    assert_eq!(*seen.borrow(), [GuestAction::Play("lyre".into()), save, GuestAction::Delete]);
}

#[test]
fn combo_dialog_saves_those_ticked_in_order() {
    let _renderer = Renderer::new().unwrap();
    let seen = Rc::new(RefCell::new(Vec::new()));
    let s = seen.clone();
    let ui = dialogs::combo(&people(), None, move |action| s.borrow_mut().push(action)).unwrap();
    assert!(!ui.get_editing());
    // The list's top is the store's last: 一起开黑的朋友, then 心动小鹿.
    ui.invoke_person_toggled(0);
    ui.invoke_person_toggled(1);
    ui.invoke_play_toggled();
    ui.invoke_save();
    let save = ComboAction::Save { names: vec!["心动小鹿".into(), "一起开黑的朋友".into()], scenes: Scenes::any() };
    assert_eq!(*seen.borrow(), [save]);
}

/// The sweep driver (UIA) finds 场景管理's ▶ 播放, the preview's ▶ and every 嘉宾 dialog button by name: each is a
/// button with an accessible label and a default action (rust-input found no 播放 button without them).
#[test]
fn the_scene_buttons_are_named_buttons_for_uiautomation() {
    let parts = include_str!("../../ui/guestedit/parts.slint");
    let manager = include_str!("../../ui/guestedit/scene_manager.slint");
    let component = |name: &str| {
        let start = parts.find(&format!("export component {name} ")).unwrap_or_else(|| panic!("{name}"));
        let end = parts[start + 1..].find("\nexport component ").map_or(parts.len(), |at| start + 1 + at);
        &parts[start..end]
    };
    for (name, label) in [("DialogButton", "accessible-label: accessible-name != \"\" ? accessible-name : label;"), ("ScenePreview", "accessible-label: \"播放\";")] {
        let body = component(name);
        assert!(body.contains("accessible-role: button;"), "{name} is not a button to UIA");
        assert!(body.contains(label), "{name} has no name for UIA");
        assert!(body.contains("accessible-action-default =>"), "{name} cannot be invoked by UIA");
    }
    assert!(manager.contains("accessible-name: sounding ? \"暂停\" : \"播放\";"), "场景管理's ▶ 播放 is not named 播放");
}
