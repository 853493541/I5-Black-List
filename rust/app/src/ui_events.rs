//! Every area's action, as one event the wiring consumes: the header and 检查 panel (ShellAction), 记录, 黑名单,
//! 嘉宾, 设置, 直播模式, the dialogs, 添加嘉宾 / 组合 / 场景管理 and the update notice. [`Bus`] queues them as the
//! callbacks fire (a callback must not reach back into the window it came from), and [`dialog_for`] says which
//! dialog an event opens.

#![allow(dead_code)]

use std::cell::RefCell;
use std::collections::VecDeque;
use std::rc::Rc;

use crate::dialogs::DialogAction;
use crate::guestedit::{ComboAction, GuestAction as GuestEditAction, SceneAction};
use crate::guests::GuestAction;
use crate::history::HistoryAction;
use crate::list::ListAction;
use crate::notices::update::Effect;
use crate::settings::Action as SettingsAction;
use crate::shell::ShellAction;
use crate::stream::StreamAction;

/// One thing the player did, from whichever area.
#[derive(Debug, Clone, PartialEq)]
pub enum UiEvent {
    Shell(ShellAction),
    History(HistoryAction),
    List(ListAction),
    Guests(GuestAction),
    Settings(SettingsAction),
    Stream(StreamAction),
    Dialog(DialogAction),
    GuestEdit(GuestEditAction),
    Combo(ComboAction),
    Scenes(SceneAction),
    Update(Effect),
}

/// A dialog an event opens. The ones that ask carry what the yes does.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Dialog {
    /// 添加 (with the tag picked beside the list) or 编辑 (the entry at this index).
    AddName { tag: String },
    EditName(usize),
    /// 批量导入, then 确认导入.
    BatchAdd,
    /// A question: heading, body, the yes button, and the event a yes sends.
    Confirm { heading: String, body: String, confirm: String, yes: Yes },
    /// 添加嘉宾 / 编辑嘉宾 (index into the 嘉宾; None adds), 编辑我.
    Guest(Option<usize>),
    EditMe,
    /// 添加组合 / 编辑组合.
    Combo(Option<usize>),
    SceneManager,
    Disclaimer,
    StreamGuide,
    DisplayGuide,
    Update,
}

/// What a yes to a [`Dialog::Confirm`] does.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Yes {
    ClearList,
    RemoveTag(String),
    ClearRecords,
    ClearGuests,
    Reset,
}

impl Yes {
    /// The event the yes sends.
    pub fn event(&self) -> Option<UiEvent> {
        match self {
            Yes::ClearList => Some(UiEvent::List(ListAction::Clear)),
            Yes::RemoveTag(tag) => Some(UiEvent::List(ListAction::RemoveTag(tag.clone()))),
            // Done by the wiring itself (no area action for them).
            Yes::ClearRecords | Yes::ClearGuests | Yes::Reset => None,
        }
    }
}

fn confirm(heading: &str, body: String, confirm: &str, yes: Yes) -> Dialog {
    Dialog::Confirm { heading: heading.into(), body, confirm: confirm.into(), yes }
}

/// The dialog `event` opens, if any. `questions` gives the words of the questions that depend on the store.
pub fn dialog_for(event: &UiEvent, questions: &dyn Fn(&Yes) -> String) -> Option<Dialog> {
    let ask = |heading: &str, button: &str, yes: Yes| Some(confirm(heading, questions(&yes), button, yes));
    match event {
        UiEvent::Shell(ShellAction::OpenUpdate) => Some(Dialog::Update),
        UiEvent::Shell(ShellAction::ShowDisplayGuide) => Some(Dialog::DisplayGuide),
        UiEvent::Shell(ShellAction::ShowStreamGuide) | UiEvent::Stream(StreamAction::ShowGuide) => Some(Dialog::StreamGuide),
        UiEvent::History(HistoryAction::AskClear) => ask("清空记录", "清空", Yes::ClearRecords),
        UiEvent::List(ListAction::Add { tag }) => Some(Dialog::AddName { tag: tag.clone() }),
        UiEvent::List(ListAction::Edit(index)) => Some(Dialog::EditName(*index)),
        UiEvent::List(ListAction::AddMany) => Some(Dialog::BatchAdd),
        UiEvent::List(ListAction::AskClear) => ask("清空黑名单", "清空", Yes::ClearList),
        UiEvent::List(ListAction::AskRemoveTag(tag)) => ask("删除标签", "删除", Yes::RemoveTag(tag.clone())),
        UiEvent::Guests(GuestAction::AddGuest) => Some(Dialog::Guest(None)),
        UiEvent::Guests(GuestAction::EditGuest(index)) => Some(Dialog::Guest(Some(*index))),
        UiEvent::Guests(GuestAction::EditMe) => Some(Dialog::EditMe),
        UiEvent::Guests(GuestAction::AddCombo) => Some(Dialog::Combo(None)),
        UiEvent::Guests(GuestAction::EditCombo(index)) => Some(Dialog::Combo(Some(*index))),
        UiEvent::Guests(GuestAction::ManageScenes) => Some(Dialog::SceneManager),
        UiEvent::Guests(GuestAction::ClearList) => ask("清空嘉宾", "清空", Yes::ClearGuests),
        UiEvent::Settings(SettingsAction::ShowDisclaimer) => Some(Dialog::Disclaimer),
        UiEvent::Settings(SettingsAction::AskReset) => ask("清空数据", "清空", Yes::Reset),
        _ => None,
    }
}

/// The queue the callbacks push into; the wiring drains it on the window's thread.
#[derive(Clone, Default)]
pub struct Bus(Rc<RefCell<VecDeque<UiEvent>>>);

impl Bus {
    pub fn send(&self, event: UiEvent) {
        self.0.borrow_mut().push_back(event);
    }

    /// A sender that wraps an area's action into its event.
    pub fn sender<A: 'static>(&self, wrap: fn(A) -> UiEvent) -> impl Fn(A) + 'static {
        let bus = self.clone();
        move |action| bus.send(wrap(action))
    }

    /// Everything queued, oldest first.
    pub fn drain(&self) -> Vec<UiEvent> {
        self.0.borrow_mut().drain(..).collect()
    }
}

/// A seat clicked in 记录 (ui._on_history_cell): a 黑名单 player's opens its 编辑, a 嘉宾's the 嘉宾 dialog; a seat on
/// neither list (or the player's own, or one too unclear to read) does nothing. `entries` and `likes` are the names.
pub fn seat_dialog<'a>(
    action: &HistoryAction,
    entries: impl IntoIterator<Item = &'a str>,
    likes: impl IntoIterator<Item = &'a str>,
) -> Option<Dialog> {
    use crate::history::Tone;
    let HistoryAction::Seat { name, tone, .. } = action else { return None };
    match tone {
        Tone::Hit => entries.into_iter().position(|entry| entry == name).map(Dialog::EditName),
        Tone::Like => likes.into_iter().position(|like| like == name).map(|index| Dialog::Guest(Some(index))),
        Tone::Me | Tone::Unclear | Tone::Plain => None,
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn a_seat_in_the_records_opens_its_entry_or_guest() {
        use super::{seat_dialog, Dialog};
        use crate::history::{HistoryAction, Tone};
        let seat = |name: &str, tone| HistoryAction::Seat { scan: 0, seat: 1, name: name.into(), tone };
        let (entries, likes) = (["甲", "示例坏人"], ["心动小鹿"]);
        assert_eq!(seat_dialog(&seat("示例坏人", Tone::Hit), entries, likes), Some(Dialog::EditName(1)));
        assert_eq!(seat_dialog(&seat("心动小鹿", Tone::Like), entries, likes), Some(Dialog::Guest(Some(0))));
        assert_eq!(seat_dialog(&seat("心动星星", Tone::Plain), entries, likes), None);
        assert_eq!(seat_dialog(&seat("不在名单", Tone::Hit), entries, likes), None);
    }

    use super::*;

    fn words(yes: &Yes) -> String {
        format!("{yes:?}?")
    }

    #[test]
    fn each_dialog_comes_from_its_action() {
        let cases = [
            (UiEvent::List(ListAction::Add { tag: "炸房".into() }), Some(Dialog::AddName { tag: "炸房".into() })),
            (UiEvent::List(ListAction::Edit(3)), Some(Dialog::EditName(3))),
            (UiEvent::List(ListAction::AddMany), Some(Dialog::BatchAdd)),
            (UiEvent::Guests(GuestAction::AddGuest), Some(Dialog::Guest(None))),
            (UiEvent::Guests(GuestAction::EditCombo(1)), Some(Dialog::Combo(Some(1)))),
            (UiEvent::Guests(GuestAction::ManageScenes), Some(Dialog::SceneManager)),
            (UiEvent::Shell(ShellAction::OpenUpdate), Some(Dialog::Update)),
            (UiEvent::Settings(SettingsAction::ShowDisclaimer), Some(Dialog::Disclaimer)),
            (UiEvent::Stream(StreamAction::ShowGuide), Some(Dialog::StreamGuide)),
            (UiEvent::List(ListAction::Delete(0)), None),
            (UiEvent::Shell(ShellAction::SetSafeMode(true)), None),
        ];
        for (event, dialog) in cases {
            assert_eq!(dialog_for(&event, &words), dialog, "{event:?}");
        }
    }

    #[test]
    fn a_question_carries_its_words_and_what_the_yes_does() {
        let asked = dialog_for(&UiEvent::List(ListAction::AskRemoveTag("挂机".into())), &words).unwrap();
        let Dialog::Confirm { heading, body, yes, .. } = asked else { panic!("a question") };
        assert_eq!((heading.as_str(), body.as_str()), ("删除标签", "RemoveTag(\"挂机\")?"));
        assert_eq!(yes.event(), Some(UiEvent::List(ListAction::RemoveTag("挂机".into()))));
        assert_eq!(Yes::ClearList.event(), Some(UiEvent::List(ListAction::Clear)));
    }

    #[test]
    fn the_bus_keeps_the_order_and_empties() {
        let bus = Bus::default();
        let list = bus.sender(UiEvent::List);
        let shell = bus.sender(UiEvent::Shell);
        list(ListAction::Undo);
        shell(ShellAction::BeginHotkey);
        assert_eq!(bus.drain(), vec![UiEvent::List(ListAction::Undo), UiEvent::Shell(ShellAction::BeginHotkey)]);
        assert!(bus.drain().is_empty());
    }
}
