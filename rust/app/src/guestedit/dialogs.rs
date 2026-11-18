//! Opening the dialogs: each made, filled and wired to its handler; the 场景 ticks follow pane.rs.

use std::cell::RefCell;
use std::rc::Rc;

use slint::{ComponentHandle, Model, ModelRc, PlatformError, SharedString, VecModel};

use super::pane::Pane;
use super::poster::poster;
use super::{dot, ComboAction, GuestAction, SceneAction, Scenes, RANDOM, SCENES};
use crate::{ComboDialog, ComboPersonItem, GuestDialog, GuestSceneItem, SceneManagerDialog, SceneSongItem};

/// The rows of a ScenePane: 随机, then every scene, each box as the pane has it.
pub fn pane_rows(pane: &Pane) -> Vec<GuestSceneItem> {
    std::iter::once((RANDOM.0, RANDOM.1))
        .chain(SCENES.iter().map(|(key, name, _)| (*key, *name)))
        .map(|(key, name)| GuestSceneItem {
            key: key.into(),
            name: name.into(),
            dot: dot(key),
            ticked: pane.ticked(key),
            own: false,
        })
        .collect()
}

/// The rows of 场景管理's list: every scene, the ✓ on the hotkey's, the ♪ on those in `own`.
pub fn manager_rows(hotkey_scene: &str, own: &[&str]) -> Vec<GuestSceneItem> {
    SCENES
        .iter()
        .map(|(key, name, _)| GuestSceneItem {
            key: (*key).into(),
            name: (*name).into(),
            dot: dot(key),
            ticked: *key == super::shown(hotkey_scene),
            own: own.contains(key),
        })
        .collect()
}

/// A 随机 pick: the clock's nanoseconds are random enough to pick a scene to show.
fn draw(count: usize) -> usize {
    let nanos = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map_or(0, |d| d.subsec_nanos());
    nanos as usize % count.max(1)
}

// The pane's callbacks, the same on both dialogs: the boxes redrawn from the pane after each change.
macro_rules! wire_pane {
    ($ui:expr, $pane:expr, $rows:expr, $on:expr, $Act:ident) => {{
        let ui = $ui.as_weak();
        let (pane, rows) = ($pane.clone(), $rows.clone());
        let redraw = move |pane: &Pane| {
            rows.set_vec(pane_rows(pane));
            if let Some(ui) = ui.upgrade() {
                ui.set_playing(pane.playing());
                ui.set_selected(pane.selected.as_str().into());
            }
        };
        let redraw = Rc::new(redraw);
        let (p, r) = (pane.clone(), redraw.clone());
        $ui.on_play_toggled(move || {
            p.borrow_mut().toggle_play();
            r(&p.borrow());
        });
        let (p, r) = (pane.clone(), redraw.clone());
        $ui.on_ticked(move |key| {
            p.borrow_mut().tick(&key);
            r(&p.borrow());
        });
        let (p, r, on, ui) = (pane.clone(), redraw, $on.clone(), $ui.as_weak());
        let showing = Rc::new(RefCell::new(pane.borrow().selected.clone()));
        $ui.on_picked(move |key| {
            let scene = p.borrow_mut().pick(&key, &showing.borrow(), draw);
            r(&p.borrow());
            if let Some(ui) = ui.upgrade() {
                ui.set_frame(poster(&scene));
            }
            *showing.borrow_mut() = scene.clone();
            on($Act::Play(scene));
        });
        let on = $on.clone();
        $ui.on_replay(move || on($Act::Replay));
    }};
}

/// What 添加嘉宾 / 编辑嘉宾 opens on.
#[derive(Debug, Clone, Default)]
pub struct GuestFields {
    pub name: String,
    pub nickname: String,
    pub reason: String,
    pub scenes: Scenes,
    /// 编辑嘉宾 (保存 and 删除) rather than 添加嘉宾.
    pub editing: bool,
}

/// 添加嘉宾 / 编辑嘉宾, filled and wired; the caller shows it.
pub fn guest(fields: GuestFields, on: impl Fn(GuestAction) + 'static) -> Result<GuestDialog, PlatformError> {
    let ui = GuestDialog::new()?;
    let on: Rc<dyn Fn(GuestAction)> = Rc::new(on);
    let pane = Rc::new(RefCell::new(Pane::new(fields.scenes)));
    let rows = Rc::new(VecModel::from(pane_rows(&pane.borrow())));
    ui.set_editing(fields.editing);
    ui.set_name(fields.name.into());
    ui.set_nickname(fields.nickname.into());
    ui.set_reason(fields.reason.into());
    ui.set_scenes(ModelRc::from(rows.clone()));
    ui.set_playing(pane.borrow().playing());
    ui.set_selected(pane.borrow().selected.as_str().into());
    ui.set_frame(poster(&pane.borrow().selected));
    wire_pane!(ui, pane, rows, on, GuestAction);
    let (weak, p, o) = (ui.as_weak(), pane.clone(), on.clone());
    ui.on_save(move || {
        if let Some(ui) = weak.upgrade() {
            let (name, nickname, reason) = (ui.get_name().into(), ui.get_nickname().into(), ui.get_reason().into());
            o(GuestAction::Save { name, nickname, reason, scenes: p.borrow().value() });
        }
    });
    let o = on.clone();
    ui.on_remove(move || o(GuestAction::Delete));
    ui.on_dismiss(move || on(GuestAction::Close));
    Ok(ui)
}

/// One 嘉宾 a 组合 can pick: the name saved and the name the list shows (its 昵称, if it has one).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Person {
    pub name: String,
    pub shown: String,
}

/// 添加组合 (combo None) / 编辑组合: `likes` in the store's order, `combo` its 嘉宾 and 场景.
pub fn combo(likes: &[Person], combo: Option<(&[String], Scenes)>, on: impl Fn(ComboAction) + 'static) -> Result<ComboDialog, PlatformError> {
    let ui = ComboDialog::new()?;
    let on: Rc<dyn Fn(ComboAction)> = Rc::new(on);
    let (names, scenes) = combo.map_or((&[][..], Scenes::default()), |(names, scenes)| (names, scenes));
    let people = Rc::new(RefCell::new(combo_people(likes, names)));
    let shown: Vec<ComboPersonItem> = people.borrow().iter().map(|(_, item)| item.clone()).collect();
    let rows_people = Rc::new(VecModel::from(shown));
    let pane = Rc::new(RefCell::new(Pane::new(scenes)));
    let rows = Rc::new(VecModel::from(pane_rows(&pane.borrow())));
    ui.set_editing(!names.is_empty());
    ui.set_people(ModelRc::from(rows_people.clone()));
    ui.set_scenes(ModelRc::from(rows.clone()));
    ui.set_playing(pane.borrow().playing());
    ui.set_selected(pane.borrow().selected.as_str().into());
    ui.set_frame(poster(&pane.borrow().selected));
    wire_pane!(ui, pane, rows, on, ComboAction);
    let (pp, weak) = (people.clone(), ui.as_weak());
    ui.on_person_toggled(move |index| {
        let mut people = pp.borrow_mut();
        if let Some((_, item)) = people.get_mut(index as usize) {
            item.ticked = !item.ticked;
            rows_people.set_row_data(index as usize, item.clone());
        }
        if let Some(ui) = weak.upgrade() {
            ui.set_people_error(SharedString::new());
        }
    });
    // The 嘉宾 ticked, in the order they were saved, then those gone still ticked.
    let order: Vec<String> = likes.iter().map(|like| like.name.clone()).chain(names.iter().cloned()).collect();
    let (p, o) = (pane.clone(), on.clone());
    ui.on_save(move || {
        let people = people.borrow();
        let mut picked: Vec<String> = Vec::new();
        for name in &order {
            if people.iter().any(|(n, item)| n == name && item.ticked) && !picked.contains(name) {
                picked.push(name.clone());
            }
        }
        o(ComboAction::Save { names: picked, scenes: p.borrow().value() });
    });
    let o = on.clone();
    ui.on_remove(move || o(ComboAction::Delete));
    ui.on_dismiss(move || on(ComboAction::Close));
    Ok(ui)
}

/// The 组合's 嘉宾 rows: its own first (in the list's order, its top first, then those gone, struck out), then the
/// others. The list's top is the store's last.
pub fn combo_people(likes: &[Person], names: &[String]) -> Vec<(String, ComboPersonItem)> {
    let fold = |name: &str| name.trim().to_lowercase();
    let mine = |name: &str| names.iter().any(|n| fold(n) == fold(name));
    let on_list = |name: &str| likes.iter().any(|like| fold(&like.name) == fold(name));
    let row = |like: &Person, ticked: bool, gone: bool| {
        (like.name.clone(), ComboPersonItem { name: like.shown.as_str().into(), ticked, gone })
    };
    let listed: Vec<&Person> = likes.iter().rev().collect();
    let gone = names.iter().filter(|name| !on_list(name)).map(|name| Person { name: name.clone(), shown: name.clone() });
    let mut rows: Vec<_> = listed.iter().filter(|like| mine(&like.name)).map(|like| row(like, true, false)).collect();
    rows.extend(gone.map(|like| row(&like, true, true)));
    rows.extend(listed.iter().filter(|like| !mine(&like.name)).map(|like| row(like, false, false)));
    rows
}

/// 场景管理 as the store has it: the scene shown, the hotkey's, those with the player's own song, the songs of the one
/// shown (默认（无声） first) and which is chosen.
#[derive(Debug, Clone, Default)]
pub struct ManagerState {
    pub shown: String,
    pub hotkey_scene: String,
    pub hotkey: String,
    pub own: Vec<String>,
    pub songs: Vec<String>,
    pub chosen_song: usize,
    pub volume: i32,
}

/// 场景管理, filled and wired; the caller shows it, and sets its rows again when the store changes.
pub fn scene_manager(state: &ManagerState, on: impl Fn(SceneAction) + 'static) -> Result<SceneManagerDialog, PlatformError> {
    let ui = SceneManagerDialog::new()?;
    let on: Rc<dyn Fn(SceneAction)> = Rc::new(on);
    let own: Vec<&str> = state.own.iter().map(String::as_str).collect();
    ui.set_scenes(ModelRc::from(Rc::new(VecModel::from(manager_rows(&state.hotkey_scene, &own)))));
    ui.set_selected(state.shown.as_str().into());
    ui.set_hotkey(state.hotkey.as_str().into());
    ui.set_frame(poster(&state.shown));
    ui.set_volume(state.volume);
    let songs: Vec<SceneSongItem> = std::iter::once("默认（无声）".to_string())
        .chain(state.songs.iter().cloned())
        .enumerate()
        .map(|(index, name)| SceneSongItem { name: name.into(), chosen: index == state.chosen_song, own: index > 0 })
        .collect();
    ui.set_songs(ModelRc::from(Rc::new(VecModel::from(songs))));
    let (o, weak) = (on.clone(), ui.as_weak());
    ui.on_picked(move |key| {
        if let Some(ui) = weak.upgrade() {
            ui.set_selected(key.clone());
            ui.set_frame(poster(&key));
        }
        o(SceneAction::Show(key.into()));
    });
    let (o, weak) = (on.clone(), ui.as_weak());
    ui.on_give_hotkey(move |key| {
        if let Some(ui) = weak.upgrade() {
            let rows: Vec<GuestSceneItem> = ui.get_scenes().iter().map(|row| GuestSceneItem { ticked: row.key == key, ..row }).collect();
            ui.set_scenes(ModelRc::from(Rc::new(VecModel::from(rows))));
        }
        o(SceneAction::GiveHotkey(key.into()));
    });
    let o = on.clone();
    ui.on_play(move || o(SceneAction::Play));
    let o = on.clone();
    ui.on_volume_set(move |volume| o(SceneAction::Volume(volume)));
    let o = on.clone();
    ui.on_choose_song(move |index| o(SceneAction::ChooseSong(index as usize)));
    let o = on.clone();
    ui.on_listen(move |index| o(SceneAction::Listen(index as usize)));
    let o = on.clone();
    ui.on_upload(move || o(SceneAction::Upload));
    ui.on_dismiss(move || on(SceneAction::Close));
    Ok(ui)
}
