//! The main window with its pages, filled from data::Store, and what the player does there turned into
//! [`UiEvent`]s: the store-side ones done here, the dialogs opened here, the rest handed to the runner.

#![allow(dead_code)]

use std::cell::RefCell;
use std::rc::Rc;

use chrono::{DateTime, FixedOffset, Local};
use data::store::Store;
use slint::ComponentHandle;

use app::wiring::preview_play::{self, ScenePreview};

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
    /// 导出's last word, under 设置's 导出日志 row.
    export_note: RefCell<String>,
    /// The hotkey box waits for a key (BeginHotkey until a key is taken or Escape), and what is wrong with the last.
    hotkey_waiting: std::cell::Cell<bool>,
    key_note: RefCell<String>,
    /// A check's problem, over the pill until checks work again (Flow::problem).
    problem: RefCell<Option<app::wiring::flow::Problem>>,
    /// The scene in the open dialog's preview, its frames on `preview_timer`, and what happened for the log.
    preview: Rc<RefCell<ScenePreview>>,
    preview_timer: slint::Timer,
    notes: RefCell<Vec<String>>,
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
            export_note: RefCell::default(),
            hotkey_waiting: std::cell::Cell::new(false),
            key_note: RefCell::default(),
            problem: RefCell::default(),
            preview: Rc::new(RefCell::new(ScenePreview::new(preview_play::lobby(
                &app::wiring::assemble::assets_dir(app::wiring::startup::install_root().as_deref()).join("sample-lobby.jpg"),
            )))),
            preview_timer: slint::Timer::default(),
            notes: RefCell::default(),
        };
        ui.refresh();
        Ok(ui)
    }

    /// Every page from the store as it is now.
    pub fn refresh(&self) {
        let store = self.store.borrow();
        let mut model = ShellModel::from_settings(&store.settings);
        model.version = self.version.clone();
        let key_note = self.key_note.borrow();
        model.hotkey_note = if key_note.is_empty() { self.hotkey_note.borrow().clone() } else { key_note.clone() };
        model.hotkey_waiting = self.hotkey_waiting.get();
        model.blacklist_count = store.entries.len();
        model.guests_count = store.likes.len();
        model.page = crate::shell::Page::from_index(self.window.get_page()).unwrap_or(model.page);
        model.show_problem(self.problem.borrow().as_ref());
        crate::shell::apply(&self.window, &model);
        history::fill(&self.window, &store, &self.history.borrow(), now());
        self.list.refresh(&self.window, &store);
        self.guests.show(&self.window, &lists(&store), now());
        let mut state = SettingsState::new(&store.settings, false, cfg!(windows), &self.version);
        state.export_note = self.export_note.borrow().clone();
        crate::settings::model::show_settings_main(&self.window, &state);
    }

    /// The check flow's problem, shown in the pill when it changes (the 50 ms timer hands it over every turn). Returns
    /// the pill's words when they changed.
    pub fn show_problem(&self, problem: Option<&app::wiring::flow::Problem>) -> Option<String> {
        if self.problem.borrow().as_ref() == problem {
            return None;
        }
        *self.problem.borrow_mut() = problem.cloned();
        let mut model = ShellModel::from_settings(&self.store.borrow().settings);
        model.show_problem(problem);
        crate::shell::apply_status(&self.window, &model);
        Some(model.status_text)
    }

    /// 使用声明 to agree to, over the window, when this data folder has not agreed yet (show_first_run_guide): no
    /// check starts before it. The answer goes to the runner as AnswerDisclaimer; closing it declines.
    pub fn ask_disclaimer(&self) {
        if self.store.borrow().settings.disclaimer_accepted {
            return;
        }
        let Ok(card) = DisclaimerDialog::new() else { return };
        card.set_asking(true);
        let (bus, weak) = (self.bus.clone(), card.as_weak());
        card.on_answered(move |yes| {
            bus.send(UiEvent::Shell(ShellAction::AnswerDisclaimer(yes)));
            if let Some(card) = weak.upgrade() {
                let _ = card.hide();
            }
        });
        let (bus, weak) = (self.bus.clone(), card.as_weak());
        card.on_closed(move || {
            bus.send(UiEvent::Shell(ShellAction::AnswerDisclaimer(false)));
            if let Some(card) = weak.upgrade() {
                let _ = card.hide();
            }
        });
        ui_dialogs::set_host(self.window.window());
        ui_dialogs::place(card.window());
        if card.show().is_ok() {
            self.dialogs.borrow_mut().push(Box::new(card));
        }
    }

    /// Whether the hotkey box waits for a key (the hotkeys are let go meanwhile, so the key reaches the box).
    pub fn hotkey_waiting(&self) -> bool {
        self.hotkey_waiting.get()
    }

    /// A key pressed in the waiting box (MainWindow._take_hotkey): a good one becomes 检查's hotkey and ends the wait;
    /// a wrong one is said under the box, which keeps waiting.
    fn take_hotkey(&self, store: &mut Store, pressed: crate::shell::Pressed, modifiers: &[win::hotkey::Modifier]) -> bool {
        use crate::shell::Pressed;
        let key = match pressed {
            Pressed::Modifier => return false,
            Pressed::Escape => {
                self.hotkey_waiting.set(false);
                self.key_note.borrow_mut().clear();
                return true;
            }
            Pressed::Key(key) => key,
        };
        match win::hotkey::take_key(key.as_deref(), modifiers, &store.settings.effect_hotkey) {
            Ok(display) => {
                store.settings.hotkey = display;
                let _ = store.save_settings();
                self.hotkey_waiting.set(false);
                self.key_note.borrow_mut().clear();
            }
            Err(note) => *self.key_note.borrow_mut() = note.to_string(),
        }
        true
    }

    /// A toast at the foot of 嘉宾 (ui._say) that goes after a few seconds.
    fn say_guests(&self, text: &str) {
        self.window.global::<crate::GuestsBridge>().set_notice(text.into());
        let window = self.window.as_weak();
        slint::Timer::single_shot(std::time::Duration::from_millis(2500), move || {
            if let Some(window) = window.upgrade() {
                window.global::<crate::GuestsBridge>().set_notice("".into());
            }
        });
    }

    /// 导出's note, shown at once when it changed.
    pub fn set_export_note(&self, note: &str) {
        if *self.export_note.borrow() != note {
            *self.export_note.borrow_mut() = note.to_string();
            self.refresh();
        }
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
            if let UiEvent::History(seat @ HistoryAction::Seat { .. }) = &event {
                // 记录's seats: the entry's or 嘉宾's dialog, or nothing for a seat on neither list (never the runner).
                let dialog = {
                    let store = self.store.borrow();
                    crate::ui_events::seat_dialog(seat, store.entries.iter().map(|e| e.name.as_str()), store.likes.iter().map(|l| l.name.as_str()))
                };
                if let Some(dialog) = dialog {
                    self.open(dialog);
                }
                continue;
            }
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
            UiEvent::List(ListAction::Copy { text, say }) => {
                // 复制名字 / 复制名单 (ui._copy_text): the clipboard, then the toast.
                #[cfg(windows)]
                let copied = win::clipboard::set_text(text);
                #[cfg(not(windows))]
                let copied = !text.is_empty();
                let words = if copied { say.as_str() } else { "复制失败，再试一次" };
                self.window.global::<crate::ListData>().set_notice(words.into());
                return Some(false);
            }
            UiEvent::Guests(crate::guests::GuestAction::Say(text)) => {
                // ui._say on 嘉宾 (添加组合 with fewer than two 嘉宾).
                self.say_guests(text);
                return Some(false);
            }
            UiEvent::Guests(action) => {
                // 删除, 删除组合, 复制名字, 置顶, a dragged row, 复制名单 (ui_likes.py): the store, then the toast.
                let done = crate::guests::effect(&mut store, action)?.ok()?;
                drop(store);
                if let Some(text) = &done.copy {
                    #[cfg(windows)]
                    let _ = win::clipboard::set_text(text);
                    #[cfg(not(windows))]
                    let _ = text;
                }
                if !done.say.is_empty() {
                    self.say_guests(&done.say);
                }
                return Some(done.changed);
            }
            UiEvent::Shell(ShellAction::BeginHotkey) => {
                self.hotkey_waiting.set(true);
                self.key_note.borrow_mut().clear();
            }
            UiEvent::Shell(ShellAction::TakeHotkey { text, ctrl, alt, shift, win: meta }) => {
                use win::hotkey::Modifier;
                let held = [(*ctrl, Modifier::Ctrl), (*alt, Modifier::Alt), (*shift, Modifier::Shift), (*meta, Modifier::Win)];
                let modifiers: Vec<Modifier> = held.iter().filter(|(on, _)| *on).map(|(_, m)| *m).collect();
                return Some(self.take_hotkey(&mut store, crate::shell::pressed_key(text), &modifiers));
            }
            _ => return None,
        }
        Some(true)
    }

    /// Opens a dialog over the window; its answer comes back on the bus.
    fn open(&self, dialog: Dialog) {
        ui_dialogs::set_host(self.window.window());
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
                ui_dialogs::place(ask.window());
                ask.show()?;
                Ok(Box::new(ask) as Box<dyn std::any::Any>)
            })(),
            Dialog::Disclaimer => (|| {
                let card = DisclaimerDialog::new()?;
                card.set_asking(false);
                // 知道了 answers too: without this the button did nothing.
                let answered = card.as_weak();
                card.on_answered(move |_| {
                    if let Some(card) = answered.upgrade() {
                        let _ = card.hide();
                    }
                });
                let weak = card.as_weak();
                card.on_closed(move || {
                    if let Some(card) = weak.upgrade() {
                        let _ = card.hide();
                    }
                });
                ui_dialogs::place(card.window());
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
        self.preview_timer.stop();
        self.preview.borrow_mut().stop();
        if let Some(opened) = self.current.borrow_mut().take() {
            (opened.close)();
        }
    }

    /// What the open dialog is about, if any.
    pub fn about(&self) -> Option<About> {
        self.current.borrow().as_ref().map(|opened| opened.about.clone())
    }

    /// What happened that the log should keep (each preview click's outcome), taken once.
    pub fn notes(&self) -> Vec<String> {
        let mut notes = std::mem::take(&mut *self.notes.borrow_mut());
        notes.append(&mut self.preview.borrow_mut().notes);
        notes
    }

    /// A 播放 / 预览 click in the open dialog: the scene plays in its preview. None for any other event.
    fn preview_click(&self, event: &UiEvent) -> Option<String> {
        use crate::guestedit::{ComboAction as C, GuestAction as G, SceneAction as S};
        let mut preview = self.preview.borrow_mut();
        let (what, played) = match event {
            UiEvent::GuestEdit(G::Play(key)) | UiEvent::Combo(C::Play(key)) | UiEvent::Scenes(S::Show(key)) => {
                (key.clone(), preview.start(crate::guestedit::shown(key)))
            }
            UiEvent::GuestEdit(G::Replay) | UiEvent::Combo(C::Replay) => ("replay".into(), preview.restart()),
            UiEvent::Scenes(S::Play) => {
                let key = preview.key().map(str::to_string).unwrap_or_else(|| self.store.borrow().settings.quick_scene.clone());
                (format!("{key} (▶ 播放, silent: its 配乐 is not wired yet)"), preview.start(crate::guestedit::shown(&key)))
            }
            _ => return None,
        };
        drop(preview);
        let set = self.current.borrow().as_ref().and_then(|opened| opened.frame.clone());
        match (&played, set) {
            (Ok(_), Some(set)) => {
                let preview = self.preview.clone();
                self.preview_timer.start(slint::TimerMode::Repeated, std::time::Duration::from_millis(33), move || {
                    if let Some(rgba) = preview.borrow_mut().frame() {
                        let buffer = slint::SharedPixelBuffer::<slint::Rgba8Pixel>::clone_from_slice(
                            &rgba,
                            preview_play::WIDTH,
                            preview_play::HEIGHT,
                        );
                        set(slint::Image::from_rgba8(buffer));
                    }
                });
                Some(format!("Preview {what}: playing, {}", played.unwrap_or_default()))
            }
            (Ok(_), None) => Some(format!("Preview {what}: not played: this dialog has no preview")),
            (Err(error), _) => Some(format!("Preview {what}: not played: {error}")),
        }
    }

    /// A dialog's answer: Some(changed) when done here, None for the runner (sounds, hotkeys) or not an answer.
    fn answer(&self, event: &UiEvent) -> Option<bool> {
        use crate::dialogs::DialogAction as D;
        use crate::guestedit::{ComboAction as C, GuestAction as G, SceneAction as S};
        let about = self.about()?;
        if let Some(note) = self.preview_click(event) {
            self.notes.borrow_mut().push(note);
            return Some(false);
        }
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
