//! The 黑名单 page bound to the store: fills `ListPage` from it and collects what the player asks for.

use std::cell::RefCell;
use std::collections::HashMap;
use std::rc::Rc;

use chrono::{DateTime, FixedOffset, Local};
use data::store::Store;
use slint::{ComponentHandle, ModelRc, SharedString, VecModel};

use super::model::{self, SortColumn, View};
use super::{ops, ListAction};
use crate::{ListData, ListRow, ListWindow, TagRow};

/// 原因 takes whatever width is left (ui._FLEX_COLUMN).
const FLEX: usize = 2;
const MIN_COLUMN: i64 = 72;

/// What the page keeps between refreshes: how it is looked at, the tags in the side list, 最近遇到 per entry
/// (worked out once per change of the list or the records, as ui._last_met_stamps caches it), and the actions asked.
#[derive(Default)]
pub struct State {
    pub view: View,
    tags: Vec<String>,
    met: HashMap<usize, String>,
    asked: Vec<Asked>,
}

/// A callback as it came: most are actions as they are; the copies get their text from the store when taken.
#[derive(Clone)]
enum Asked {
    Do(ListAction),
    CopyName(usize),
    Share,
    /// The search, the picked tag or the sort changed: only the rows need drawing again.
    Redraw,
}

pub struct Page {
    pub state: Rc<RefCell<State>>,
    rows: Rc<VecModel<ListRow>>,
    tags: Rc<VecModel<TagRow>>,
}

impl Page {
    /// Hook the page's callbacks up. Searching, picking a tag and sorting are done here; everything else waits in
    /// `take_actions` for the app.
    pub fn new(window: &ListWindow) -> Page {
        let ui = window.global::<ListData>();
        let page = Page {
            state: Rc::new(RefCell::new(State::default())),
            rows: Rc::new(VecModel::default()),
            tags: Rc::new(VecModel::default()),
        };
        ui.set_rows(ModelRc::from(page.rows.clone()));
        ui.set_tags(ModelRc::from(page.tags.clone()));
        let ask = |action: fn(usize) -> Asked| {
            let state = page.state.clone();
            move |value: i32| state.borrow_mut().asked.push(action(value.max(0) as usize))
        };
        ui.on_edit(ask(|index| Asked::Do(ListAction::Edit(index))));
        ui.on_delete(ask(|index| Asked::Do(ListAction::Delete(index))));
        ui.on_copy_name(ask(Asked::CopyName));
        let push = |asked: Asked| {
            let state = page.state.clone();
            move || state.borrow_mut().asked.push(asked.clone())
        };
        ui.on_add_many(push(Asked::Do(ListAction::AddMany)));
        ui.on_clear(push(Asked::Do(ListAction::AskClear)));
        ui.on_recheck(push(Asked::Do(ListAction::RecheckTags)));
        ui.on_undo(push(Asked::Do(ListAction::Undo)));
        ui.on_share(push(Asked::Share));
        let state = page.state.clone();
        ui.on_add(move || {
            let mut state = state.borrow_mut();
            let tag = state.view.tag.clone();
            state.asked.push(Asked::Do(ListAction::Add { tag }));
        });
        let state = page.state.clone();
        ui.on_eye(move |hidden| state.borrow_mut().asked.push(Asked::Do(ListAction::NamesHidden(hidden))));
        let state = page.state.clone();
        ui.on_new_tag_named(move |name| state.borrow_mut().asked.push(Asked::Do(ListAction::NewTag(name.into()))));
        let state = page.state.clone();
        ui.on_rename_tag(move |old, new| {
            state.borrow_mut().asked.push(Asked::Do(ListAction::RenameTag { old: old.into(), new: new.into() }))
        });
        let state = page.state.clone();
        ui.on_remove_tag(move |tag| state.borrow_mut().asked.push(Asked::Do(ListAction::AskRemoveTag(tag.into()))));
        let state = page.state.clone();
        ui.on_search_edited(move |text| {
            let mut state = state.borrow_mut();
            state.view.search = text.into();
            state.asked.push(Asked::Redraw);
        });
        let state = page.state.clone();
        ui.on_tag_chosen(move |row| {
            let mut state = state.borrow_mut();
            state.view.tag = state.tags.get(row as usize).cloned().unwrap_or_default();
            state.asked.push(Asked::Redraw);
        });
        let state = page.state.clone();
        ui.on_sort(move |column| {
            let mut state = state.borrow_mut();
            match column {
                0 => state.view.click_sort(SortColumn::Name),
                3 => state.view.click_sort(SortColumn::Met),
                _ => return,
            }
            state.asked.push(Asked::Redraw);
        });
        page
    }

    /// What the player asked since the last call, oldest first. 复制名字 and 复制名单 come out with their text.
    pub fn take_actions(&self, store: &Store) -> Vec<ListAction> {
        let taken = std::mem::take(&mut self.state.borrow_mut().asked);
        taken
            .into_iter()
            .filter_map(|asked| match asked {
                Asked::Do(action) => Some(action),
                Asked::CopyName(index) => ops::copy_name(store, index),
                Asked::Share => ops::share_list(store),
                Asked::Redraw => None,
            })
            .collect()
    }

    /// Everything asked since the last call: redraw for a search, tag or sort; do what needs no dialog through
    /// [`Page::apply`] (then refresh and show the toast); hand back the rest (dialogs, questions, the clipboard).
    pub fn handle(&self, window: &ListWindow, store: &mut Store, undo: &mut ops::Undo) -> std::io::Result<Vec<ListAction>> {
        let redraw = self.state.borrow().asked.iter().any(|asked| matches!(asked, Asked::Redraw));
        let mut rest = Vec::new();
        let mut changed = false;
        for action in self.take_actions(store) {
            match self.apply(store, undo, &action)? {
                Some(outcome) => {
                    changed = true;
                    if !outcome.say.is_empty() {
                        Page::say(window, &outcome);
                    }
                }
                None => rest.push(action),
            }
        }
        if changed {
            self.refresh(window, store);
        } else if redraw {
            self.redraw(window, store, Local::now().fixed_offset());
        }
        Ok(rest)
    }

    /// ops::apply, keeping the page in step: a picked tag that is renamed stays picked under its new name.
    pub fn apply(&self, store: &mut Store, undo: &mut ops::Undo, action: &ListAction) -> std::io::Result<Option<ops::Outcome>> {
        let outcome = ops::apply(store, undo, action)?;
        if let (ListAction::RenameTag { old, .. }, Some(ops::Outcome { pick_tag: Some(new), .. })) = (action, &outcome) {
            let mut state = self.state.borrow_mut();
            if state.view.tag == *old {
                state.view.tag = new.clone();
            }
        }
        Ok(outcome)
    }

    /// The list, the tags or the records changed: work 最近遇到 out again, then redraw.
    pub fn refresh(&self, window: &ListWindow, store: &Store) {
        self.state.borrow_mut().met = model::last_met(&store.entries, &store.scans);
        self.redraw(window, store, Local::now().fixed_offset());
    }

    /// Redraw from what is kept (after a search letter, a tag picked or a sort).
    pub fn redraw(&self, window: &ListWindow, store: &Store, now: DateTime<FixedOffset>) {
        let ui = window.global::<ListData>();
        let mut state = self.state.borrow_mut();
        // First, since a tag that is gone also drops out of the filter.
        let catalog = store.tag_catalog();
        if !catalog.contains(&state.view.tag) {
            state.view.tag.clear();
        }
        let tag_rows = model::tag_rows(&store.entries, &catalog);
        state.tags = tag_rows.iter().map(|(tag, _)| tag.clone()).collect();
        let picked = state.tags.iter().position(|tag| *tag == state.view.tag).unwrap_or(0);
        self.tags.set_vec(
            tag_rows.into_iter().map(|(tag, count)| TagRow { tag: tag.into(), count: count as i32 }).collect::<Vec<_>>(),
        );
        ui.set_picked_tag(picked as i32);
        let hidden = ops::names_hidden(store);
        let rows = model::rows(&store.entries, &state.met, &state.view, hidden, now);
        let widths = fit_columns(&store.settings.column_widths, &store.settings.column_order, ui.get_table_width() as i64);
        let tag_room = widths[1] as f32;
        self.rows.set_vec(rows.iter().map(|row| list_row(row, tag_room)).collect::<Vec<_>>());
        let empty = model::empty(store.entries.len(), rows.len(), &state.view);
        ui.set_empty_text(empty.text().into());
        ui.set_count(store.entries.len() as i32);
        ui.set_names_hidden(hidden);
        ui.set_names_locked(!store.settings.stream_mode.is_empty());
        let order = column_order(&store.settings.column_order);
        ui.set_column_order(ModelRc::new(VecModel::from(order.iter().map(|&c| c as i32).collect::<Vec<_>>())));
        ui.set_widths(ModelRc::new(VecModel::from(widths.iter().map(|&w| w as f32).collect::<Vec<_>>())));
        match state.view.sort {
            None => ui.set_sort_column(-1),
            // 名字 first click: A to Z, the arrow up; 最近遇到 first click: newest first, the arrow down.
            Some((SortColumn::Name, first)) => {
                ui.set_sort_column(0);
                ui.set_sort_up(first);
            }
            Some((SortColumn::Met, first)) => {
                ui.set_sort_column(3);
                ui.set_sort_up(!first);
            }
        }
    }

    /// The toast after an action (ui._say).
    pub fn say(window: &ListWindow, outcome: &ops::Outcome) {
        let ui = window.global::<ListData>();
        ui.set_notice(outcome.say.as_str().into());
        ui.set_notice_undo(outcome.undo);
    }
}

fn list_row(row: &model::Row, room: f32) -> ListRow {
    let (shown, more) = tag_row_layout(&row.tags, room);
    ListRow {
        index: row.index as i32,
        name: row.name.as_str().into(),
        tags: ModelRc::new(VecModel::from(
            row.tags[..shown].iter().map(|tag| SharedString::from(tag.as_str())).collect::<Vec<_>>(),
        )),
        more: more.into(),
        reason: row.reason.as_str().into(),
        met: row.met.as_str().into(),
        met_known: row.met_known,
    }
}

/// A pill's width: its words at 12 px semibold (a Chinese character 12 px, the rest about 7) and 9 px each side.
fn pill_width(text: &str) -> f32 {
    text.chars().map(|ch| if ch.is_ascii() { 7.0 } else { 12.0 }).sum::<f32>() + 18.0
}

/// ui_widgets.tag_row_layout: how many tags fit in a cell this wide, and the +N pill for the rest ("" when all fit).
pub fn tag_row_layout(tags: &[String], width: f32) -> (usize, String) {
    let room = width - 24.0;
    let widths: Vec<f32> = tags.iter().map(|tag| pill_width(tag)).collect();
    for keep in (0..=tags.len()).rev() {
        let hidden = tags.len() - keep;
        let mut needed = widths[..keep].iter().sum::<f32>() + 6.0 * keep.saturating_sub(1) as f32;
        if hidden > 0 {
            needed += if keep > 0 { 6.0 } else { 0.0 } + pill_width(&format!("+{hidden}"));
        }
        if needed <= room || keep == 0 {
            return (keep, if hidden > 0 { format!("+{hidden}") } else { String::new() });
        }
    }
    (0, String::new())
}

/// The saved order when it is a reordering of the four columns, else 名字, 标签, 原因, 最近遇到.
pub fn column_order(saved: &[i64]) -> Vec<usize> {
    let mut sorted = saved.to_vec();
    sorted.sort_unstable();
    if sorted == [0, 1, 2, 3] {
        saved.iter().map(|&c| c as usize).collect()
    } else {
        vec![0, 1, 2, 3]
    }
}

/// ui._fit_blacklist_columns (no column being dragged): the saved widths, with 原因 taking what is left and the
/// columns right of it giving way, last first, when the table is too narrow.
pub fn fit_columns(saved: &[i64], order: &[i64], available: i64) -> [i64; 4] {
    let mut width: [i64; 4] = match saved {
        [a, b, c, d] => [*a, *b, *c, *d],
        _ => data::store::settings::DEFAULT_COLUMN_WIDTHS,
    };
    for w in &mut width {
        *w = (*w).max(MIN_COLUMN);
    }
    if available < MIN_COLUMN {
        return width;
    }
    let logicals = column_order(order);
    let fixed: Vec<usize> = logicals.iter().copied().filter(|&c| c != FLEX).collect();
    let mut overflow = fixed.iter().map(|&c| width[c]).sum::<i64>() + MIN_COLUMN - available;
    for &column in fixed.iter().rev() {
        if overflow <= 0 {
            break;
        }
        let cut = (width[column] - MIN_COLUMN).max(0).min(overflow);
        width[column] -= cut;
        overflow -= cut;
    }
    width[FLEX] = (available - fixed.iter().map(|&c| width[c]).sum::<i64>()).max(MIN_COLUMN);
    width
}
