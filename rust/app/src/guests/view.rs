//! The 嘉宾 page's model given to Slint (ui/guests/page.slint), and its callbacks turned into [`GuestAction`]s.
//!
//! [`rows`] and [`GuestsView::show`] are what the app-wiring package uses: the page is a `GuestsPage` inside the main
//! window, whose properties take the same values as `GuestsPreview`'s here.

use std::cell::RefCell;
use std::rc::Rc;

use chrono::{DateTime, FixedOffset};
use slint::{Color, ComponentHandle, ModelRc, SharedString, VecModel};

use super::model::{Lists, Page, RowKind};
use super::{on_add_combo, on_click, on_key, on_menu, on_more, on_move, GuestAction, RowKey};
use crate::{GuestPerson, GuestRow, GuestsPreview};

/// ui_love_pick.scene_dot: each scene's dot, its look's glow; "random" is 随机's.
pub fn dot_color(key: &str) -> Color {
    let rgb: u32 = match key {
        "classic" => 0xe9c987,
        "lace" => 0xff96c8,
        "ice" => 0x6ebeff,
        "stars" => 0xb9a3ff,
        "cyber" => 0x21f6ff,
        "neon" => 0xff2bd6,
        "angel" => 0xffd078,
        "equation" => 0x7fd8ff,
        "fluffy" => 0x6ccdc4,
        "claw" => 0xb08cff,
        "lyre" => 0x38b66a,
        _ => 0xa0d23c,
    };
    Color::from_rgb_u8((rgb >> 16) as u8, (rgb >> 8) as u8, rgb as u8)
}

fn strings(items: impl Iterator<Item = String>) -> ModelRc<SharedString> {
    ModelRc::new(VecModel::from(items.map(SharedString::from).collect::<Vec<_>>()))
}

/// The page's rows as Slint draws them.
pub fn rows(page: &Page) -> ModelRc<GuestRow> {
    let rows: Vec<GuestRow> = page
        .rows
        .iter()
        .map(|row| GuestRow {
            kind: match row.kind {
                RowKind::Me => 0,
                RowKind::Combo(_) => 1,
                RowKind::Guest(_) => 2,
            },
            name: row.name.as_str().into(),
            people: ModelRc::new(VecModel::from(
                row.people
                    .iter()
                    .map(|(name, present)| GuestPerson { name: name.as_str().into(), present: *present })
                    .collect::<Vec<_>>(),
            )),
            nickname: row.nickname.as_str().into(),
            dots: ModelRc::new(VecModel::from(row.dots.iter().map(|key| dot_color(key)).collect::<Vec<_>>())),
            scene: row.scene.as_str().into(),
            reason: row.reason.as_str().into(),
            met: row.met.as_str().into(),
            menu: strings(row.menu.iter().map(|item| item.label().to_string())),
        })
        .collect();
    ModelRc::new(VecModel::from(rows))
}

/// Puts one page on the preview window.
pub fn apply(ui: &GuestsPreview, page: &Page) {
    ui.set_rows(rows(page));
    ui.set_fixed(page.fixed as i32);
    ui.set_show_table(page.show_table);
    ui.set_show_toolbar(page.show_toolbar);
    ui.set_show_search(page.show_search);
    ui.set_show_more(page.show_more);
    ui.set_add_combo_enabled(page.add_combo_enabled);
    ui.set_empty_icon(page.empty_icon.into());
    ui.set_empty_text(page.empty_text.as_str().into());
    ui.set_empty_buttons(page.empty_buttons);
}

/// The page as shown now, so a click on row r means what row r showed.
pub struct GuestsView {
    page: Rc<RefCell<Page>>,
}

impl GuestsView {
    /// Wires the page's callbacks to `act`; the search box's edits redraw it through `search` (the app gives the page
    /// for a query from the store as it is).
    pub fn new(
        ui: &GuestsPreview,
        act: impl Fn(GuestAction) + 'static,
        search: impl Fn(&str) -> Page + 'static,
    ) -> GuestsView {
        let page = Rc::new(RefCell::new(search("")));
        apply(ui, &page.borrow());
        let act = Rc::new(act);
        let handle = ui.as_weak();
        let held = page.clone();
        ui.global::<crate::GuestsBridge>().on_search_edited(move |text| {
            let fresh = search(&text);
            if let Some(ui) = handle.upgrade() {
                apply(&ui, &fresh);
            }
            *held.borrow_mut() = fresh;
        });
        let bridge = ui.global::<crate::GuestsBridge>();
        let send = |pick: fn(&Page, i32, i32) -> Option<GuestAction>| {
            let (page, act) = (page.clone(), act.clone());
            move |a: i32, b: i32| {
                if let Some(action) = pick(&page.borrow(), a, b) {
                    act(action);
                }
            }
        };
        let click = send(|page, row, _| on_click(page, row.max(0) as usize));
        bridge.on_row_clicked(move |row| click(row, 0));
        bridge.on_row_key(send(|page, row, key| {
            let key = if key == 0 { RowKey::Enter } else { RowKey::Delete };
            on_key(page, usize::try_from(row).ok()?, key)
        }));
        bridge.on_row_menu(send(|page, row, item| on_menu(page, usize::try_from(row).ok()?, usize::try_from(item).ok()?)));
        bridge.on_row_moved(send(|page, row, to| on_move(page, usize::try_from(row).ok()?, usize::try_from(to).ok()?)));
        let more = send(|page, item, _| on_more(page, usize::try_from(item).ok()?));
        bridge.on_more_chosen(move |item| more(item, 0));
        let combo = send(|page, _, _| Some(on_add_combo(page)));
        bridge.on_add_combo(move || combo(0, 0));
        let (guest, scenes) = (act.clone(), act);
        bridge.on_add_guest(move || guest(GuestAction::AddGuest));
        bridge.on_manage_scenes(move || scenes(GuestAction::ManageScenes));
        GuestsView { page }
    }

    /// The page after the store changed (an action done, or a theme change).
    pub fn show(&self, ui: &GuestsPreview, lists: &Lists, now: DateTime<FixedOffset>) {
        let fresh = Page::build(lists, &ui.get_search(), now);
        apply(ui, &fresh);
        *self.page.borrow_mut() = fresh;
    }

    /// The page as shown now.
    pub fn page(&self) -> Page {
        self.page.borrow().clone()
    }
}
