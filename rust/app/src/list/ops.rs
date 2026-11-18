//! What the 黑名单 page's actions do to the store, and the toast each one shows (ui._delete_entry, _confirm_clear_list,
//! _put_back, _recheck_tags, _finish_tag_new, _finish_tag_edit, _remove_tag, _toggle_name_hiding, the column handlers).

use std::io;

use data::store::text::clean_tag;
use data::store::{Entry, Store};

use super::model::masked_name;
use super::ListAction;

/// The toast after an action: its words, and whether 撤销 shows (for eight seconds; four without it).
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Outcome {
    pub say: String,
    pub undo: bool,
    /// The tag the page should now pick (a picked tag that was renamed follows its new name).
    pub pick_tag: Option<String>,
}

impl Outcome {
    fn say(text: impl Into<String>) -> Outcome {
        Outcome { say: text.into(), ..Outcome::default() }
    }
}

/// The list as it was before the last change that 撤销 puts back (and the 嘉宾 too, after an add that moved one).
#[derive(Debug, Clone, Default)]
pub struct Undo {
    entries: Option<Vec<Entry>>,
    likes: Option<Vec<data::store::Like>>,
}

impl Undo {
    /// Remember the list now, before a change 撤销 can take back.
    pub fn keep(&mut self, store: &Store) {
        self.entries = Some(store.entries.clone());
        self.likes = None;
    }

    /// Remember the 嘉宾 too (添加 that moved a 嘉宾 over).
    pub fn keep_likes(&mut self, store: &Store) {
        self.likes = Some(store.likes.clone());
    }

    /// toast.drop(): a later change makes an older 撤销 wrong.
    pub fn drop_it(&mut self) {
        *self = Undo::default();
    }
}

/// 黑名单 names masked: by the eye, or always while 直播模式 is on (ui._names_hidden).
pub fn names_hidden(store: &Store) -> bool {
    store.settings.names_hidden || !store.settings.stream_mode.is_empty()
}

/// A name for a toast or a question, masked whenever the page masks it (ui._listed).
pub fn listed(store: &Store, name: &str) -> String {
    if names_hidden(store) {
        masked_name(name)
    } else {
        name.to_string()
    }
}

/// ConfirmDialog「清空黑名单」's words.
pub fn clear_question(store: &Store) -> String {
    format!("将删除 {} 条黑名单，确定清空吗？", store.entries.len())
}

/// 复制名字 for the entry at `index`, and 复制名单 for the whole list.
pub fn copy_name(store: &Store, index: usize) -> Option<ListAction> {
    let entry = store.entries.get(index)?;
    // ui._copy_text: the clipboard gets the name itself; the toast shows it masked when the page does.
    Some(ListAction::Copy { text: entry.name.clone(), say: format!("已复制「{}」", listed(store, &entry.name)) })
}

pub fn share_list(store: &Store) -> Option<ListAction> {
    let count = store.entries.len();
    (count > 0).then(|| ListAction::Copy {
        text: data::store::share::share_text(&store.entries),
        say: format!("已复制 {count} 人"),
    })
}

/// 批量导入's rows, once chosen: the toast, with 撤销 when something changed.
pub fn import(
    store: &mut Store,
    undo: &mut Undo,
    rows: &[(String, Vec<String>, String, Option<usize>)],
) -> io::Result<Outcome> {
    let before = store.entries.clone();
    let (added, merged) = store.import_rows(rows)?;
    if added == 0 && merged == 0 {
        return Ok(Outcome::say("都已经在黑名单里了"));
    }
    undo.drop_it();
    undo.entries = Some(before);
    let mut parts = Vec::new();
    if added > 0 {
        parts.push(format!("已添加 {added} 人"));
    }
    if merged > 0 {
        parts.push(format!("合并 {merged} 人"));
    }
    Ok(Outcome { say: parts.join("，"), undo: true, pick_tag: None })
}

/// Do an action that needs no dialog. Actions that open one come back as None (see the module notes).
pub fn apply(store: &mut Store, undo: &mut Undo, action: &ListAction) -> io::Result<Option<Outcome>> {
    let outcome = match action {
        ListAction::Delete(index) => {
            let Some(entry) = store.entries.get(*index) else { return Ok(Some(Outcome::default())) };
            let name = listed(store, &entry.name);
            undo.keep(store);
            store.remove_at(*index)?;
            Outcome { say: format!("已删除「{name}」"), undo: true, pick_tag: None }
        }
        ListAction::Clear => {
            let count = store.entries.len();
            if count == 0 {
                return Ok(Some(Outcome::default()));
            }
            undo.keep(store);
            store.clear_entries()?;
            Outcome { say: format!("已清空 {count} 人"), undo: true, pick_tag: None }
        }
        ListAction::Undo => {
            let Some(entries) = undo.entries.take() else { return Ok(Some(Outcome::default())) };
            store.restore_entries(entries)?;
            if let Some(likes) = undo.likes.take() {
                store.restore_likes(likes)?;
            }
            Outcome::say("已撤销")
        }
        ListAction::RecheckTags => {
            store.recheck_tags()?;
            Outcome::default()
        }
        ListAction::NewTag(raw) => {
            let tag = clean_tag(raw);
            if tag.is_empty() {
                Outcome::default()
            } else if store.tag_catalog().contains(&tag) {
                Outcome::say("标签已存在")
            } else {
                if store.add_custom_tag(&tag) {
                    store.save_settings()?;
                }
                Outcome::default()
            }
        }
        ListAction::RenameTag { old, new } => {
            let renamed = clean_tag(new);
            if renamed.is_empty() || &renamed == old {
                return Ok(Some(Outcome::default()));
            }
            match store.rename_tag(old, &renamed)? {
                "taken" => Outcome::say("标签已存在"),
                "renamed" => {
                    undo.drop_it();
                    Outcome { pick_tag: Some(renamed), ..Outcome::default() }
                }
                _ => Outcome::default(),
            }
        }
        ListAction::RemoveTag(tag) => {
            if store.remove_custom_tag(tag)? {
                undo.drop_it();
            }
            Outcome::default()
        }
        ListAction::NamesHidden(hidden) => {
            store.settings.names_hidden = *hidden;
            store.save_settings()?;
            Outcome::default()
        }
        ListAction::ColumnWidths(widths) => {
            store.settings.column_widths = widths.clone();
            store.save_settings()?;
            Outcome::default()
        }
        ListAction::ColumnOrder(order) => {
            store.settings.column_order = order.clone();
            store.save_settings()?;
            Outcome::default()
        }
        ListAction::Add { .. }
        | ListAction::AddMany
        | ListAction::Edit(_)
        | ListAction::Copy { .. }
        | ListAction::AskClear
        | ListAction::AskRemoveTag(_) => return Ok(None),
    };
    Ok(Some(outcome))
}
