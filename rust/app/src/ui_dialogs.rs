//! The dialogs MainUi opens, filled from the store and wired to the [`Bus`]: 添加 / 编辑, 批量导入 → 确认导入,
//! 添加嘉宾 / 编辑嘉宾 / 编辑我, 添加组合 / 编辑组合, 场景管理, 显示说明 and 直播模式说明. Each returns an
//! [`Opened`]: the dialog kept alive, what its answer is about, and how to close it.

#![allow(dead_code)]

use std::cell::RefCell;
use std::rc::Rc;

use data::import::{suggest_tags, ImportRow, Record, TagSuggestion};
use data::store::Store;
use slint::{ComponentHandle, PlatformError};

use crate::dialogs::{models, DialogAction};
use crate::guestedit::dialogs::{self as edit, GuestFields, ManagerState, Person};
use crate::ui_events::{Bus, UiEvent};
use crate::{AddNameDialog, BatchAddDialog, PictureGuideDialog, TagSuggestDialog};

/// The width 添加's tag chips wrap in (as the dialogs' own pictures use).
const NAME_TAG_ROOM: f32 = 392.0;

/// What an open dialog's answer is about.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum About {
    /// 添加 (None) or 编辑 the entry at this index.
    Name(Option<usize>),
    /// 批量导入: the rows planned from the paste as it is now, and the paste.
    Batch(Rc<RefCell<Vec<ImportRow>>>, Rc<RefCell<String>>),
    /// 确认导入: the records and the suggested 标签.
    Suggest(Vec<Record>, Vec<TagSuggestion>),
    Guest(Option<usize>),
    Me,
    Combo(Option<usize>),
    Scenes,
    Info,
}

/// A dialog on screen.
pub struct Opened {
    pub about: About,
    pub close: Box<dyn Fn()>,
    _keep: Box<dyn std::any::Any>,
}

fn opened<C: ComponentHandle + 'static>(ui: C, about: About) -> Result<Opened, PlatformError> {
    ui.show()?;
    let weak = ui.as_weak();
    let close = Box::new(move || {
        if let Some(ui) = weak.upgrade() {
            let _ = ui.hide();
        }
    });
    Ok(Opened { about, close, _keep: Box::new(ui) })
}

fn send(bus: &Bus, action: DialogAction) -> impl Fn() + 'static {
    let bus = bus.clone();
    move || bus.send(UiEvent::Dialog(action.clone()))
}

fn taken(store: &Store, except: Option<usize>) -> Vec<String> {
    let names = store.entries.iter().enumerate().filter(|(index, _)| Some(*index) != except);
    names.map(|(_, entry)| common::text::fold(&entry.name)).collect()
}

/// 添加 (with `tag` ticked) or 编辑 entry `edit`.
pub fn add_name(store: &Store, bus: &Bus, tag: &str, edit: Option<usize>) -> Result<Opened, PlatformError> {
    let ui = AddNameDialog::new()?;
    let catalog = store.tag_catalog();
    let entry = edit.and_then(|index| store.entries.get(index));
    let ticked = Rc::new(RefCell::new(match entry {
        Some(entry) => entry.tags.clone(),
        None if !tag.is_empty() => vec![tag.to_string()],
        None => Vec::new(),
    }));
    if let Some(entry) = entry {
        ui.set_heading("编辑".into());
        ui.set_allow_delete(true);
        ui.set_name(entry.name.as_str().into());
        ui.set_detail(entry.reason.as_str().into());
    }
    ui.set_tag_lines(models::tag_lines(&models::name_chips(&catalog, &ticked.borrow()), NAME_TAG_ROOM));
    let (weak, held, chips) = (ui.as_weak(), ticked.clone(), catalog.clone());
    ui.on_toggled(move |tag| {
        let mut on = held.borrow_mut();
        match on.iter().position(|t| t.as_str() == tag.as_str()) {
            Some(at) => drop(on.remove(at)),
            None => on.push(tag.to_string()),
        }
        if let Some(ui) = weak.upgrade() {
            ui.set_tag_lines(models::tag_lines(&models::name_chips(&chips, &on), NAME_TAG_ROOM));
        }
    });
    let (weak, names) = (ui.as_weak(), taken(store, edit));
    ui.on_name_edited(move |typed| {
        if let Some(ui) = weak.upgrade() {
            ui.set_name_error(models::name_problem(&typed, &names).into());
        }
    });
    let (weak, names, bus_save) = (ui.as_weak(), taken(store, edit), bus.clone());
    ui.on_save(move || {
        let Some(ui) = weak.upgrade() else { return };
        let problem = models::name_problem(&ui.get_name(), &names);
        ui.set_name_error(problem.into());
        if problem.is_empty() {
            let tags = data::store::text::order_tags(&ticked.borrow(), &catalog);
            let action = DialogAction::SaveName { name: ui.get_name().to_string(), tags, detail: ui.get_detail().to_string() };
            bus_save.send(UiEvent::Dialog(action));
        }
    });
    ui.on_delete(send(bus, DialogAction::DeleteName));
    ui.on_closed(send(bus, DialogAction::Closed));
    opened(ui, About::Name(edit))
}

fn checked(rows: &[ImportRow]) -> Vec<Record> {
    rows.iter().filter(|row| row.checked).map(|row| (row.name.clone(), row.tags.clone(), row.reason.clone(), row.target)).collect()
}

/// 批量导入: the paste read as it is typed; 导入 sends the rows left ticked.
pub fn batch(store: &Store, bus: &Bus, text: &str) -> Result<Opened, PlatformError> {
    let ui = BatchAddDialog::new()?;
    let rows = Rc::new(RefCell::new(Vec::new()));
    let paste = Rc::new(RefCell::new(text.to_string()));
    let entries: Vec<data::import::Entry> =
        store.entries.iter().map(|entry| {
            let tags: Vec<&str> = entry.tags.iter().map(String::as_str).collect();
            data::import::Entry::new(&entry.name, &entry.reason, &tags)
        }).collect();
    let elsewhere: Vec<data::import::Entry> = store.likes.iter().map(|like| data::import::Entry::new(&like.name, "", &[])).collect();
    let catalog = store.tag_catalog();
    let show = {
        let (weak, rows) = (ui.as_weak(), rows.clone());
        Rc::new(move |text: &str| {
            *rows.borrow_mut() = data::import::plan_import(text, &entries, &catalog, &elsewhere);
            if let Some(ui) = weak.upgrade() {
                let rows = rows.borrow();
                ui.set_rows(models::preview_rows(&rows));
                ui.set_count(models::checked_count(&rows));
                ui.set_error(if rows.is_empty() && !text.trim().is_empty() { "没有读到名字" } else { "" }.into());
            }
        })
    };
    ui.set_text(text.into());
    show(text);
    let (again, typed) = (show.clone(), paste.clone());
    ui.on_edited(move |text| {
        *typed.borrow_mut() = text.to_string();
        again(&text)
    });
    let (weak, held) = (ui.as_weak(), rows.clone());
    ui.on_toggled(move |row| {
        if let Some(row) = held.borrow_mut().get_mut(row.max(0) as usize) {
            row.checked = !row.checked;
        }
        if let Some(ui) = weak.upgrade() {
            ui.set_rows(models::preview_rows(&held.borrow()));
            ui.set_count(models::checked_count(&held.borrow()));
        }
    });
    let (held, bus_import) = (rows.clone(), bus.clone());
    ui.on_import(move || bus_import.send(UiEvent::Dialog(DialogAction::ImportChecked(checked(&held.borrow())))));
    ui.on_closed(send(bus, DialogAction::Closed));
    opened(ui, About::Batch(rows, paste))
}

/// The suggestions for `records`, or None when there are none (import at once).
pub fn suggestions(store: &Store, records: &[Record]) -> Option<Vec<TagSuggestion>> {
    Some(suggest_tags(records, &store.tag_catalog())).filter(|found| !found.is_empty())
}

/// The records with each 标签 that is on added to the rows it was suggested for.
pub fn with_tags(records: &[Record], suggestions: &[TagSuggestion], on: &[String]) -> Vec<Record> {
    let mut out = records.to_vec();
    for found in suggestions.iter().filter(|found| on.contains(&found.tag)) {
        for &row in &found.rows {
            if let Some(record) = out.get_mut(row) {
                if !record.1.contains(&found.tag) {
                    record.1.push(found.tag.clone());
                }
            }
        }
    }
    out
}

/// 确认导入: the suggested 标签, all on at first.
pub fn suggest(bus: &Bus, records: Vec<Record>, found: Vec<TagSuggestion>) -> Result<Opened, PlatformError> {
    let ui = TagSuggestDialog::new()?;
    let on = Rc::new(RefCell::new(found.iter().map(|s| s.tag.clone()).collect::<Vec<_>>()));
    let fill = {
        let (weak, on, records, found) = (ui.as_weak(), on.clone(), records.clone(), found.clone());
        move || {
            if let Some(ui) = weak.upgrade() {
                let on = on.borrow();
                ui.set_new_tags(models::suggestion_lines(&found, &on, false));
                ui.set_old_tags(models::suggestion_lines(&found, &on, true));
                ui.set_people(models::people_rows(&records, &found, &on));
            }
        }
    };
    fill();
    let held = on.clone();
    ui.on_toggled(move |tag| {
        {
            let mut on = held.borrow_mut();
            match on.iter().position(|t| t.as_str() == tag.as_str()) {
                Some(at) => drop(on.remove(at)),
                None => on.push(tag.to_string()),
            }
        }
        fill();
    });
    let (bus_import, rows, tags) = (bus.clone(), records.clone(), found.clone());
    ui.on_import(move || bus_import.send(UiEvent::Dialog(DialogAction::ImportWithTags(with_tags(&rows, &tags, &on.borrow())))));
    ui.on_back(send(bus, DialogAction::BackToPaste));
    ui.on_closed(send(bus, DialogAction::Closed));
    opened(ui, About::Suggest(records, found))
}

/// The data crate's scenes as the dialogs hold them, and back.
pub fn from_store(scenes: &data::store::sounds::Scenes) -> crate::guestedit::Scenes {
    crate::guestedit::Scenes { keys: scenes.keys.clone(), random: scenes.random }
}

pub fn to_store(scenes: &crate::guestedit::Scenes) -> data::store::sounds::Scenes {
    data::store::sounds::Scenes { keys: scenes.keys.clone(), random: scenes.random }
}

fn people(store: &Store) -> Vec<Person> {
    let shown = |like: &data::store::Like| if like.nickname.is_empty() { like.name.clone() } else { like.nickname.clone() };
    store.likes.iter().map(|like| Person { name: like.name.clone(), shown: shown(like) }).collect()
}

/// 添加嘉宾 (None), 编辑嘉宾 (Some) or, with `me`, 编辑我 (the player's own scenes).
pub fn guest(store: &Store, bus: &Bus, index: Option<usize>, me: bool) -> Result<Opened, PlatformError> {
    let like = index.and_then(|index| store.likes.get(index));
    let fields = match (me, like) {
        (true, _) => GuestFields {
            name: store.settings.player_name.clone(),
            nickname: String::new(),
            reason: String::new(),
            scenes: from_store(&store.me),
            editing: true,
        },
        (false, Some(like)) => GuestFields {
            name: like.name.clone(),
            nickname: like.nickname.clone(),
            reason: like.reason.clone(),
            scenes: from_store(&like.scenes),
            editing: true,
        },
        _ => GuestFields { name: String::new(), nickname: String::new(), reason: String::new(), scenes: Default::default(), editing: false },
    };
    let ui = edit::guest(fields, bus.sender(UiEvent::GuestEdit))?;
    opened(ui, if me { About::Me } else { About::Guest(index) })
}

/// 添加组合 (None) or 编辑组合 (Some).
pub fn combo(store: &Store, bus: &Bus, index: Option<usize>) -> Result<Opened, PlatformError> {
    let held = index.and_then(|index| store.combos.get(index));
    let ui = edit::combo(&people(store), held.map(|c| (c.names.as_slice(), from_store(&c.scenes))), bus.sender(UiEvent::Combo))?;
    opened(ui, About::Combo(index))
}

/// 场景管理.
pub fn scenes(store: &Store, bus: &Bus) -> Result<Opened, PlatformError> {
    let state = ManagerState {
        shown: store.settings.quick_scene.clone(),
        hotkey_scene: store.settings.quick_scene.clone(),
        hotkey: store.settings.effect_hotkey.clone(),
        volume: 100,
        ..ManagerState::default()
    };
    let ui = edit::scene_manager(&state, bus.sender(UiEvent::Scenes))?;
    opened(ui, About::Scenes)
}

/// 显示 › ⓘ: the two modes in pictures.
pub fn display_guide(bus: &Bus) -> Result<Opened, PlatformError> {
    let ui = PictureGuideDialog::new()?;
    ui.set_which("display".into());
    ui.on_done(send(bus, DialogAction::Closed));
    ui.on_closed(send(bus, DialogAction::Closed));
    opened(ui, About::Info)
}

/// 直播模式 › ⓘ: ui_dialogs.StreamGuideDialog is a PictureGuideDialog of one page, so it is the same card as 显示's.
pub fn stream_guide(bus: &Bus, dark: bool) -> Result<Opened, PlatformError> {
    let ui = PictureGuideDialog::new()?;
    ui.set_which("stream".into());
    ui.set_dark(dark);
    ui.on_done(send(bus, DialogAction::Closed));
    ui.on_closed(send(bus, DialogAction::Closed));
    opened(ui, About::Info)
}
