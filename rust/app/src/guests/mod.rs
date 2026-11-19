//! The 嘉宾 page (blacklist_detect/ui_likes.py LikesPage, with ui_guests.py's scene words): the 我 row in green, the
//! 组合 with their blue tag, then the 嘉宾, newest first until dragged; search, 场景管理, 添加组合, 添加嘉宾 and 更多
//! (复制名单, 清空嘉宾列表); a row's click, keys and right-click menu; the empty states.
//!
//! The page changes nothing itself. Everything it asks for goes out as a [`GuestAction`], which the app-wiring package
//! performs on the store, then calls [`view::GuestsView::show`] again with the lists as they are now:
//!
//! | action | what the app does (as ui_likes.py does) |
//! |---|---|
//! | `ManageScenes` | opens 场景管理 (ui-guest-edit) |
//! | `AddGuest` | opens 添加嘉宾; on 添加: store.add_like, toast 「名字」加进嘉宾了 with 撤销 |
//! | `AddCombo` | opens 添加组合; on 添加: store.set_combos(combos + new) |
//! | `Say(text)` | a toast (TOO_FEW when 添加组合 is asked for with fewer than two 嘉宾) |
//! | `EditGuest(i)` / `EditCombo(n)` / `EditMe` | opens 编辑嘉宾 / 编辑组合 / 我的场景 on that one |
//! | `DeleteGuest(i)` | store.remove_like(i), toast 已删除「shown」 with 撤销 |
//! | `DeleteCombo(n)` | store.set_combos without it, toast 已删除组合「a + b」 with 撤销 |
//! | `CopyName(i)` | the name to the clipboard, toast 已复制「name」 |
//! | `ToTop(i)` | store.move_like(i, likes.len() - 1) |
//! | `Move { index, to }` | store.move_like(index, to): a 嘉宾 row dragged onto another's place |
//! | `CopyList` | model::share_likes to the clipboard, toast 已复制 N 人 |
//! | `ClearList` | asks 清空嘉宾 (将删除 N 位嘉宾，确定清空吗？ / 清空, danger), then store.clear_likes, toast 已清空 N 人 |

// The app-wiring package calls these; until it lands only the tests do.
#![allow(dead_code)]

pub mod model;
pub mod render;
pub mod view;

#[cfg(test)]
mod tests;

use model::{MenuItem, Page, RowKind, TOO_FEW};

/// What the 嘉宾 page asks the app to do. Indexes are places in store.likes / store.combos.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GuestAction {
    ManageScenes,
    AddGuest,
    AddCombo,
    Say(String),
    EditGuest(usize),
    EditCombo(usize),
    EditMe,
    DeleteGuest(usize),
    DeleteCombo(usize),
    CopyName(usize),
    ToTop(usize),
    Move { index: usize, to: usize },
    CopyList,
    ClearList,
}

/// What a 嘉宾 action did to the store (ui_likes.py): whether the lists changed, the toast, and text for the clipboard.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Done {
    pub changed: bool,
    pub say: String,
    pub copy: Option<String>,
}

/// The 嘉宾 actions that change the store or the clipboard without a dialog: 删除, 删除组合, 复制名字, 置顶, a row
/// dragged, 复制名单. None for the rest (the dialogs, Say) and for an index that is no longer there.
pub fn effect(store: &mut data::store::Store, action: &GuestAction) -> Option<std::io::Result<Done>> {
    let shown = |like: &data::store::Like| if like.nickname.is_empty() { like.name.clone() } else { like.nickname.clone() };
    let moved = |changed: bool| Done { changed, ..Done::default() };
    Some(match action {
        GuestAction::DeleteGuest(index) => {
            let like = store.likes.get(*index).cloned()?;
            store.remove_like(*index).map(|()| Done { changed: true, say: format!("已删除「{}」", shown(&like)), copy: None })
        }
        GuestAction::DeleteCombo(number) => {
            let mut combos = store.combos.clone();
            if *number >= combos.len() {
                return None;
            }
            let gone = combos.remove(*number);
            store.set_combos(combos).map(|()| Done { changed: true, say: format!("已删除组合「{}」", gone.names.join(" + ")), copy: None })
        }
        GuestAction::CopyName(index) => {
            let like = store.likes.get(*index)?;
            Ok(Done { changed: false, say: format!("已复制「{}」", like.name), copy: Some(like.name.clone()) })
        }
        GuestAction::ToTop(index) => {
            let last = store.likes.len().checked_sub(1)?;
            store.move_like(*index, last).map(moved)
        }
        GuestAction::Move { index, to } => store.move_like(*index, *to).map(moved),
        GuestAction::CopyList => {
            let count = store.likes.len();
            if count == 0 {
                return None;
            }
            Ok(Done { changed: false, say: format!("已复制 {count} 人"), copy: Some(model::share_likes(&store.likes)) })
        }
        _ => return None,
    })
}

/// A key pressed on the list's current row.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RowKey {
    Enter,
    Delete,
}

/// What a click on a row's any cell asks for: 我的场景, 编辑组合 or 编辑嘉宾.
pub fn on_click(page: &Page, row: usize) -> Option<GuestAction> {
    Some(match page.rows.get(row)?.kind {
        RowKind::Me => GuestAction::EditMe,
        RowKind::Combo(number) => GuestAction::EditCombo(number),
        RowKind::Guest(index) => GuestAction::EditGuest(index),
    })
}

/// Enter edits the row as a click does; Delete deletes a 嘉宾 or a 组合 (the 我 row has no 删除).
pub fn on_key(page: &Page, row: usize, key: RowKey) -> Option<GuestAction> {
    match (page.rows.get(row)?.kind, key) {
        (_, RowKey::Enter) => on_click(page, row),
        (RowKind::Me, RowKey::Delete) => None,
        (RowKind::Combo(number), RowKey::Delete) => Some(GuestAction::DeleteCombo(number)),
        (RowKind::Guest(index), RowKey::Delete) => Some(GuestAction::DeleteGuest(index)),
    }
}

/// The right-click menu's item `item` (an index into the row's menu) on row `row`.
pub fn on_menu(page: &Page, row: usize, item: usize) -> Option<GuestAction> {
    let shown = page.rows.get(row)?;
    let chosen = *shown.menu.get(item)?;
    Some(match (shown.kind, chosen) {
        (_, MenuItem::Separator) => return None,
        (_, MenuItem::Edit) => return on_click(page, row),
        (RowKind::Combo(number), MenuItem::Delete) => GuestAction::DeleteCombo(number),
        (RowKind::Guest(index), MenuItem::Delete) => GuestAction::DeleteGuest(index),
        (RowKind::Guest(index), MenuItem::CopyName) => GuestAction::CopyName(index),
        (RowKind::Guest(index), MenuItem::ToTop) => GuestAction::ToTop(index),
        _ => return None,
    })
}

/// A row dragged onto another: only 嘉宾 rows move, onto a 嘉宾 row's place, and only while nothing is searched.
pub fn on_move(page: &Page, row: usize, to: usize) -> Option<GuestAction> {
    if !page.drag || row == to {
        return None;
    }
    match (page.rows.get(row)?.kind, page.rows.get(to)?.kind) {
        (RowKind::Guest(index), RowKind::Guest(target)) => Some(GuestAction::Move { index, to: target }),
        _ => None,
    }
}

/// 添加组合: it waits for two 嘉宾.
pub fn on_add_combo(page: &Page) -> GuestAction {
    if page.add_combo_enabled { GuestAction::AddCombo } else { GuestAction::Say(TOO_FEW.into()) }
}

/// 更多's items: 复制名单 (0) and 清空嘉宾列表 (1); both only with 嘉宾 on the list.
pub fn on_more(page: &Page, item: usize) -> Option<GuestAction> {
    if !page.show_more {
        return None;
    }
    match item {
        0 => Some(GuestAction::CopyList),
        1 => Some(GuestAction::ClearList),
        _ => None,
    }
}
