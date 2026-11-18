//! The dialogs of blacklist_detect/ui_dialogs.py, ui_kit.ConfirmDialog and the sound views (ui/dialogs/*.slint).
//!
//! For the app-wiring package: each dialog component has an `out property card-height` (its card's natural
//! height) and callbacks for what the player does. What the app must then do is one [`DialogAction`]:
//!
//! | Dialog (component) | Callbacks | Action |
//! |---|---|---|
//! | 添加 / 编辑 (`AddNameDialog`) | save, delete, toggled(tag), reveal, closed | `SaveName`, `DeleteName`, `Closed` |
//! | 批量导入 (`BatchAddDialog`) | edited(text), toggled(row), import, closed | `ImportChecked` |
//! | 确认导入 (`TagSuggestDialog`) | toggled(tag), back, import, closed | `ImportWithTags`, `BackToPaste` |
//! | 清空黑名单 and other asks (`ConfirmDialog`) | answered(bool), closed | `Answered` |
//! | 使用声明 (`DisclaimerDialog`) | answered(bool), closed | `Answered` (false while asking: quit the app) |
//! | 欢迎 (`GuideDialog`) | start, closed | `Closed` |
//! | 显示 / 直播模式说明 (`PictureGuideDialog`) | done, closed | `Closed` |
//! | 环境测试 (`FlowReportDialog`) | export-log, done, closed | `ExportLog`, `Closed` |
//! | 选择片段 (`SoundTrimDialog`) | pressed/dragged/released(x), toggle-song, cut, nudge(±1), toggle-preview, ok, closed | `PlayFrom`, `Preview`, `StopSound`, `KeepPart` |
//!
//! × and Esc close without saving; a click outside the card closes unless something was typed or picked.
// The app-wiring package calls these; until then only the tests do.
#![allow(dead_code)]

pub mod models;
pub mod trim;

#[cfg(test)]
mod render;

/// What a dialog asks the app to do.
#[derive(Clone, Debug, PartialEq)]
pub enum DialogAction {
    /// 添加 / 保存 a 黑名单 record (the name as typed, its 标签 in catalog order, its 原因).
    SaveName {
        name: String,
        tags: Vec<String>,
        detail: String,
    },
    /// 删除 the record being edited.
    DeleteName,
    /// 批量导入: the rows left checked, as (name, 标签, 原因, target or -1).
    ImportChecked(Vec<data::import::Record>),
    /// 确认导入: import the rows with the 标签 still on.
    ImportWithTags(Vec<data::import::Record>),
    /// 确认导入's 返回: back to the pasted text.
    BackToPaste,
    /// A ConfirmDialog or 使用声明 answered: true for the confirm / 同意 button.
    Answered(bool),
    /// 环境测试's 导出日志.
    ExportLog,
    /// 选择片段: play the sound from this many seconds to its end, play the part (start, length), or stop.
    PlayFrom(f64),
    Preview {
        start: f64,
        length: f64,
    },
    StopSound,
    /// 选择片段's 确定: keep this part, to the millisecond.
    KeepPart {
        start: f64,
        length: f64,
    },
    /// Closed with nothing to do (×, Esc, 知道了, 开始使用).
    Closed,
}

#[cfg(test)]
mod golden;
