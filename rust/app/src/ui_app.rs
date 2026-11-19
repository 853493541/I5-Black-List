//! The main window with its pages, filled from data::Store, and what the player does there turned into
//! [`UiEvent`]s: the store-side ones done here, the dialogs opened here, the rest handed to the runner.

#![allow(dead_code)]

use std::cell::RefCell;
use std::rc::Rc;

use chrono::{DateTime, FixedOffset, Local};
use data::store::Store;
use slint::ComponentHandle;

use crate::guests::model::{Lists, Page as GuestsModel};
use crate::guests::view::GuestsView;
use crate::history::{self, HistoryAction};
use crate::list::{bind, ops, ListAction};
use crate::settings::rows::SettingsState;
use crate::shell::{ShellAction, ShellModel};
use crate::ui_dialogs::{self, About, Opened};
use crate::ui_events::{dialog_for, Bus, Dialog, UiEvent, Yes};
use crate::{ConfirmDialog, DisclaimerDialog, MainWindow};

pub type Shared = Rc<RefCell<Store>>;

fn now() -> DateTime<FixedOffset> {
    Local::now().fixed_offset()
}

fn lists(store: &Store) -> Lists<'_> {
    Lists {
        likes: &store.likes,
        combos: &store.combos,
        me: &store.me,
        player_name: &store.settings.player_name,
        scans: &store.scans,
    }
}

/// The main window and the pages' state.
pub struct MainUi {
    pub window: MainWindow,
    pub bus: Bus,
    store: Shared,
    list: bind::Page,
    undo: RefCell<ops::Undo>,
    guests: GuestsView,
    history: RefCell<history::View>,
    /// The dialogs open now, kept alive while they show.
    dialogs: RefCell<Vec<Box<dyn std::any::Any>>>,
    /// The dialog open now that answers on the bus (添加, 批量导入, 嘉宾, 组合, 场景管理, the guides).
    current: RefCell<Option<Opened>>,
    /// What the yes of the question open now does.
    asking: Rc<RefCell<Option<Yes>>>,
    version: String,
    /// Under the hotkey box: a key another program holds (Runner::hotkey_note).
    hotkey_note: RefCell<String>,
}

impl MainUi {
    pub fn new(store: Shared, version: &str) -> Result<MainUi, slint::PlatformError> {
        let window = MainWindow::new()?;
        let bus = Bus::default();
        crate::shell::connect(&window, bus.sender(UiEvent::Shell));
        history::connect(&window, bus.sender(UiEvent::History));
        let list = bind::Page::new(&window);
        let searched = store.clone();
        let guests = GuestsView::new(&window, bus.sender(UiEvent::Guests), move |text| {
            GuestsModel::build(&lists(&searched.borrow()), text, now())
        });
        let settings = bus.clone();
        window.on_settings_chosen(move |row, value| {
            if let Some(action) = crate::settings::action(&row, Some(&value)) {
                settings.send(UiEvent::Settings(action));
            }
        });
        let settings = bus.clone();
        window.on_settings_pressed(move |row| {
            if let Some(action) = crate::settings::action(&row, None) {
                settings.send(UiEvent::Settings(action));
            }
        });
        let ui = MainUi {
            window,
            bus,
            store,
            list,
            undo: RefCell::default(),
            guests,
            history: RefCell::default(),
            dialogs: RefCell::default(),
            current: RefCell::default(),
            asking: Rc::default(),
            version: version.to_string(),
            hotkey_note: RefCell::default(),
        };
        ui.refresh();
        Ok(ui)
    }

    /// Every page from the store as it is now.
    pub fn refresh(&self) {
        let store = self.store.borrow();
        let mut model = ShellModel::from_settings(&store.settings);
        model.version = self.version.clone();
        model.hotkey_note = self.hotkey_note.borrow().clone();
        model.blacklist_count = store.entries.len();
        model.guests_count = store.likes.len();
        model.page = crate::shell::Page::from_index(self.window.get_page()).unwrap_or(model.page);
        crate::shell::apply(&self.window, &model);
        history::fill(&self.window, &store, &self.history.borrow(), now());
        self.list.refresh(&self.window, &store);
        self.guests.show(&self.window, &lists(&store), now());
        let state = SettingsState::new(&store.settings, false, cfg!(windows), &self.version);
        crate::settings::model::show_settings_main(&self.window, &state);
    }

    /// The hotkey box's note, shown at once when it changed.
    pub fn set_hotkey_note(&self, note: &str) {
        if *self.hotkey_note.borrow() != note {
            *self.hotkey_note.borrow_mut() = note.to_string();
            self.refresh();
        }
    }

    /// Drains what the player did: the store-side part is done here and the dialogs opened; what is left (the
    /// header's and 检查's actions, the app-side settings, sounds, the update) goes back to the runner.
    pub fn pump(&self) -> Vec<UiEvent> {
        let mut events = self.bus.drain();
        let listed = {
            let mut store = self.store.borrow_mut();
            self.list.handle(&self.window, &mut store, &mut self.undo.borrow_mut()).unwrap_or_default()
        };
        events.extend(listed.into_iter().map(UiEvent::List));
        let mut left = Vec::new();
        let mut changed = false;
        for event in events {
            let store = self.store.clone();
            let questions = move |yes: &Yes| question(&store.borrow(), yes);
            if let Some(dialog) = dialog_for(&event, &questions) {
                // 发现新版本 needs the release the runner holds.
                if dialog == Dialog::Update {
                    left.push(event);
                } else {
                    self.open(dialog);
                }
                continue;
            }
            let answered = self.answer(&event);
            match answered.or_else(|| self.apply(&event)) {
                Some(true) => changed = true,
                Some(false) => {}
                None => left.push(event),
            }
        }
        if changed {
            self.refresh();
        }
        left
    }

    /// The store's part of an event: Some(changed) when done here, None for the runner.
    fn apply(&self, event: &UiEvent) -> Option<bool> {
        let mut store = self.store.borrow_mut();
        match event {
            UiEvent::History(HistoryAction::Pick(scan)) => self.history.borrow_mut().picked = *scan,
            UiEvent::History(HistoryAction::ToggleDay(day)) => {
                let closed = &mut self.history.borrow_mut().closed;
                if !closed.remove(day) {
                    closed.insert(day.clone());
                }
            }
            UiEvent::History(HistoryAction::Delete(scan)) => store.remove_scan(*scan),
            UiEvent::List(action @ (ListAction::Clear | ListAction::RemoveTag(_) | ListAction::Delete(_))) => {
                let outcome = self.list.apply(&mut store, &mut self.undo.borrow_mut(), action).ok()?;
                if let Some(outcome) = outcome {
                    bind::Page::say(&self.window, &outcome);
                }
            }
            UiEvent::Settings(action) => match crate::settings::apply(&mut store, action.clone()).ok()? {
                crate::settings::Applied::Saved => {}
                crate::settings::Applied::ForApp(_) => return None,
            },
            UiEvent::Shell(ShellAction::RenamePlayer(name)) => {
                store.settings.player_name = name.clone();
                store.save_settings().ok()?;
            }
            UiEvent::Shell(ShellAction::PageShown(_)) => {}
            _ => return None,
        }
        Some(true)
    }

    /// Opens a dialog over the window; its answer comes back on the bus.
    fn open(&self, dialog: Dialog) {
        let shown: Result<Box<dyn std::any::Any>, slint::PlatformError> = match dialog {
            Dialog::Confirm { heading, body, confirm, yes } => (|| {
                let ask = ConfirmDialog::new()?;
                ask.set_heading(heading.into());
                ask.set_body(body.into());
                ask.set_confirm(confirm.into());
                *self.asking.borrow_mut() = Some(yes);
                let (bus, asking, weak) = (self.bus.clone(), self.asking.clone(), ask.as_weak());
                ask.on_answered(move |yes| {
                    let wanted = asking.borrow_mut().take().filter(|_| yes);
                    if let Some(event) = wanted.as_ref().and_then(Yes::event) {
                        bus.send(event);
                    }
                    if let Some(ask) = weak.upgrade() {
                        let _ = ask.hide();
                    }
                });
                let weak = ask.as_weak();
                ask.on_closed(move || {
                    if let Some(ask) = weak.upgrade() {
                        let _ = ask.hide();
                    }
                });
                ask.show()?;
                Ok(Box::new(ask) as Box<dyn std::any::Any>)
            })(),
            Dialog::Disclaimer => (|| {
                let card = DisclaimerDialog::new()?;
                card.set_asking(false);
                let weak = card.as_weak();
                card.on_closed(move || {
                    if let Some(card) = weak.upgrade() {
                        let _ = card.hide();
                    }
                });
                card.show()?;
                Ok(Box::new(card) as Box<dyn std::any::Any>)
            })(),
            other => {
                let made = {
                    let store = self.store.borrow();
                    let dark = self.window.get_dark();
                    match other {
                        Dialog::AddName { tag } => ui_dialogs::add_name(&store, &self.bus, &tag, None),
                        Dialog::EditName(index) => ui_dialogs::add_name(&store, &self.bus, "", Some(index)),
                        Dialog::BatchAdd => ui_dialogs::batch(&store, &self.bus, ""),
                        Dialog::Guest(index) => ui_dialogs::guest(&store, &self.bus, index, false),
                        Dialog::EditMe => ui_dialogs::guest(&store, &self.bus, None, true),
                        Dialog::Combo(index) => ui_dialogs::combo(&store, &self.bus, index),
                        Dialog::SceneManager => ui_dialogs::scenes(&store, &self.bus),
                        Dialog::DisplayGuide => ui_dialogs::display_guide(&self.bus),
                        Dialog::StreamGuide => ui_dialogs::stream_guide(&self.bus, dark),
                        _ => return,
                    }
                };
                self.show_current(made);
                return;
            }
        };
        match shown {
            Ok(dialog) => self.dialogs.borrow_mut().push(dialog),
            Err(error) => eprintln!("dialog: {error}"),
        }
    }
}

impl MainUi {
    /// Puts `made` in place of the dialog open now.
    fn show_current(&self, made: Result<Opened, slint::PlatformError>) {
        self.close_current();
        match made {
            Ok(opened) => *self.current.borrow_mut() = Some(opened),
            Err(error) => eprintln!("dialog: {error}"),
        }
    }

    fn close_current(&self) {
        if let Some(opened) = self.current.borrow_mut().take() {
            (opened.close)();
        }
    }

    /// What the open dialog is about, if any.
    pub fn about(&self) -> Option<About> {
        self.current.borrow().as_ref().map(|opened| opened.about.clone())
    }

    /// A dialog's answer: Some(changed) when done here, None for the runner (sounds, hotkeys) or not an answer.
    fn answer(&self, event: &UiEvent) -> Option<bool> {
        use crate::dialogs::DialogAction as D;
        use crate::guestedit::{ComboAction as C, GuestAction as G, SceneAction as S};
        let about = self.about()?;
        let saved = |result: std::io::Result<()>| {
            if let Err(error) = result {
                eprintln!("save: {error}");
            }
        };
        match (event, about) {
            (UiEvent::Dialog(D::SaveName { name, tags, detail }), About::Name(edit)) => {
                let mut store = self.store.borrow_mut();
                saved(match edit {
                    None => store.add(name, detail, tags).map(drop),
                    Some(index) => store.update_at(index, name, tags, detail).map(drop),
                });
            }
            (UiEvent::Dialog(D::DeleteName), About::Name(Some(index))) => {
                self.close_current();
                return self.apply(&UiEvent::List(ListAction::Delete(index)));
            }
            (UiEvent::Dialog(D::ImportChecked(records)), About::Batch(..)) => {
                let found = ui_dialogs::suggestions(&self.store.borrow(), records);
                if let Some(found) = found {
                    self.show_current(ui_dialogs::suggest(&self.bus, records.clone(), found));
                    return Some(false);
                }
                self.import(records);
            }
            (UiEvent::Dialog(D::ImportWithTags(records)), About::Suggest(..)) => self.import(records),
            (UiEvent::Dialog(D::BackToPaste), About::Suggest(records, _)) => {
                let text = records.iter().map(|record| record.0.clone()).collect::<Vec<_>>().join("\n");
                let made = ui_dialogs::batch(&self.store.borrow(), &self.bus, &text);
                self.show_current(made);
                return Some(false);
            }
            (UiEvent::Dialog(D::Closed), _) | (UiEvent::GuestEdit(G::Close), _) | (UiEvent::Combo(C::Close), _) => {}
            (UiEvent::Scenes(S::Close), _) => {}
            (UiEvent::GuestEdit(G::Save { name, nickname, reason, scenes }), about) => {
                let mut store = self.store.borrow_mut();
                let scenes = &ui_dialogs::to_store(scenes);
                saved(match about {
                    About::Me => store.set_me(scenes),
                    About::Guest(Some(index)) => store.update_like(index, name, nickname, reason, scenes).map(drop),
                    _ => store.add_like(name, nickname, reason, scenes).map(drop),
                });
            }
            (UiEvent::GuestEdit(G::Delete), About::Guest(Some(index))) => saved(self.store.borrow_mut().remove_like(index)),
            (UiEvent::Combo(action @ (C::Save { .. } | C::Delete)), About::Combo(index)) => {
                let mut store = self.store.borrow_mut();
                let mut combos = store.combos.clone();
                match (action, index) {
                    (C::Save { names, scenes }, None) => combos.push(data::store::Combo { names: names.clone(), scenes: ui_dialogs::to_store(scenes) }),
                    (C::Save { names, scenes }, Some(at)) if at < combos.len() => {
                        combos[at] = data::store::Combo { names: names.clone(), scenes: ui_dialogs::to_store(scenes) };
                    }
                    (C::Delete, Some(at)) if at < combos.len() => drop(combos.remove(at)),
                    _ => {}
                }
                saved(store.set_combos(combos));
            }
            _ => return None,
        }
        self.close_current();
        Some(true)
    }

    fn import(&self, records: &[data::import::Record]) {
        let rows: Vec<(String, Vec<String>, String, Option<usize>)> = records
            .iter()
            .map(|(name, tags, reason, target)| (name.clone(), tags.clone(), reason.clone(), usize::try_from(*target).ok()))
            .collect();
        let outcome = ops::import(&mut self.store.borrow_mut(), &mut self.undo.borrow_mut(), &rows);
        match outcome {
            Ok(outcome) => bind::Page::say(&self.window, &outcome),
            Err(error) => eprintln!("import: {error}"),
        }
    }
}

/// The words of a question that depend on the store.
pub fn question(store: &Store, yes: &Yes) -> String {
    match yes {
        Yes::ClearList => ops::clear_question(store),
        Yes::RemoveTag(tag) => crate::list::model::remove_tag_question(&store.entries, tag),
        Yes::ClearRecords => format!("将删除 {} 条记录，确定清空吗？", store.scans.len()),
        Yes::ClearGuests => format!("将删除 {} 位嘉宾，确定清空吗？", store.likes.len()),
        Yes::Reset => crate::settings::rows::RESET_CONFIRM.0.to_string(),
    }
}

#[cfg(test)]
#[path = "ui_app_tests.rs"]
mod tests;
