//! 黑名单, the list page (ui.py `_list_page`, `_list_side`, `_show_list` and the handlers around them).
//!
//! `ui/list/page.slint` exports `ListPage` (to put in the main window), the `ListData` global it reads and writes,
//! and `ListWindow` (the page alone in a window). `bind::Page` fills `ListData` from the store and turns what the
//! player does into a [`ListAction`]. For the app-wiring package (bind takes a `ListWindow` today; for the main
//! window, swap the type: only `window.global::<ListData>()` is used):
//!
//! - Call `Page::new(&window)` once, `Page::refresh(&window, &store)` whenever the list, the tags, the records or the
//!   settings change (ui._list_changed), and `Page::handle(&window, &mut store, &mut undo)` after each callback: it
//!   redraws, does what needs no dialog, shows the toast, and returns the actions below.
//! - Actions the page cannot finish on its own, because they open a dialog or ask first, are handed out as they
//!   are; the rest go through [`ops::apply`], which changes the store and says what to put in the toast:
//!   * `Add { tag }`: open 添加 (ui_dialogs.AddNameDialog, the ui-dialogs package), with the picked tag ticked.
//!   * `AddMany`: open 批量导入 (BatchAddDialog, then TagSuggestDialog), then `ops::import`.
//!   * `Edit(index)`: open 编辑 for that entry; its 删除 is `Delete(index)`.
//!   * `AskClear`: ConfirmDialog「清空黑名单」with `ops::clear_question`; on yes, `Clear`.
//!   * `AskRemoveTag(tag)`: the question from `model::remove_tag_question`; on yes, `RemoveTag(tag)`.
//!   * `Copy(text)`: put the text on the clipboard (复制名字, 复制名单), then show `ops::Outcome::say`.
//!   * `Delete`, `Clear`, `Undo`, `RecheckTags`, `NewTag`, `RenameTag`, `RemoveTag`, `NamesHidden`,
//!     `ColumnWidths`, `ColumnOrder`: `ops::apply`.

// Used by the app-wiring package; until it lands only the tests reach it.
#![allow(dead_code)]

pub mod bind;
pub mod collate;
pub mod model;
pub mod ops;
#[cfg(test)]
pub(crate) mod render;
#[cfg(test)]
mod tests;

/// What the player asked for on the 黑名单 page.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ListAction {
    /// 添加, with the tag picked beside the list (empty for 全部).
    Add { tag: String },
    /// 批量导入.
    AddMany,
    /// A click on a row, Enter, or 编辑 in its menu: the entry at this store index.
    Edit(usize),
    /// Delete, or 删除 in a row's menu.
    Delete(usize),
    /// 复制名字 or 复制名单: this text to the clipboard (masked names stay masked).
    Copy { text: String, say: String },
    /// 清空黑名单 under 更多: ask first.
    AskClear,
    /// The answer yes to 清空黑名单.
    Clear,
    /// 按原因补标签.
    RecheckTags,
    /// 撤销 in the toast.
    Undo,
    /// A new tag typed into the heading.
    NewTag(String),
    /// A tag renamed in its row.
    RenameTag { old: String, new: String },
    /// 删除 on a tag: ask first.
    AskRemoveTag(String),
    /// The answer yes to removing a tag.
    RemoveTag(String),
    /// The eye on 名字.
    NamesHidden(bool),
    /// A column resized: the four widths, by column (名字, 标签, 原因, 最近遇到).
    ColumnWidths(Vec<i64>),
    /// Columns dragged into a new order: the column at each place.
    ColumnOrder(Vec<i64>),
}
