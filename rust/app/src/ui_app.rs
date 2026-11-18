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
    /// What the yes of the question open now does.
    asking: Rc<RefCell<Option<Yes>>>,
    version: String,
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
            asking: Rc::default(),
            version: version.to_string(),
        };
        ui.refresh();
        Ok(ui)
    }

    /// Every page from the store as it is now.
    pub fn refresh(&self) {
        let store = self.store.borrow();
        let mut model = ShellModel::from_settings(&store.settings);
        model.version = self.version.clone();
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
                self.open(dialog);
                continue;
            }
            match self.apply(&event) {
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
            UiEvent::List(action @ (ListAction::Clear | ListAction::RemoveTag(_))) => {
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
            // stub: assemble-ui (the other dialogs open from the runner's next round; logged until then)
            other => {
                eprintln!("dialog not wired yet: {other:?}");
                return;
            }
        };
        match shown {
            Ok(dialog) => self.dialogs.borrow_mut().push(dialog),
            Err(error) => eprintln!("dialog: {error}"),
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
mod tests {
    use super::*;
    use crate::list::ListAction;

    /// Each tab shows its own page in the main window (pictures in $BLACKLIST_SHOTS/main), and an action that
    /// asks first opens its question; a yes comes back as the area's action.
    #[test]
    fn the_main_window_shows_each_page_and_opens_the_questions() {
        crate::shots::init();
        let mut seeded = crate::list::render::seeded("normal");
        seeded.likes = crate::history::tests_seed_likes();
        let store = Rc::new(RefCell::new(seeded));
        let ui = MainUi::new(store.clone(), "1.2.0").unwrap();
        let dir = std::env::var_os("BLACKLIST_SHOTS").map(std::path::PathBuf::from).map(|d| d.join("main"));
        let mut pictures = Vec::new();
        for (page, name) in ["记录", "黑名单", "嘉宾", "设置"].iter().enumerate() {
            ui.window.set_page(page as i32);
            ui.refresh();
            let picture = crate::shots::draw(&ui.window, (900.0, 560.0), 1.5).unwrap();
            if let Some(dir) = &dir {
                crate::shots::save(&dir.join(format!("page_{name}.png")), &picture).unwrap();
            }
            pictures.push(picture);
        }
        for (i, a) in pictures.iter().enumerate() {
            for b in &pictures[i + 1..] {
                assert_ne!(a.rgb, b.rgb, "every page draws differently");
            }
        }
        ui.bus.send(UiEvent::List(ListAction::AskClear));
        assert!(ui.pump().is_empty());
        assert_eq!(ui.dialogs.borrow().len(), 1, "清空黑名单 asks first");
        assert_eq!(*ui.asking.borrow(), Some(Yes::ClearList));
        ui.bus.send(UiEvent::Shell(ShellAction::BeginHotkey));
        assert_eq!(ui.pump(), vec![UiEvent::Shell(ShellAction::BeginHotkey)], "the runner's own");
        let root = store.borrow().root.clone();
        let _ = std::fs::remove_dir_all(root);
    }
}
