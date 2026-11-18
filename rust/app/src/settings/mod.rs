//! 设置, the settings page, and 环境测试's first-run card, for the app-wiring package.
//!
//! The page (ui/settings/page.slint `SettingsPage`) takes `sections` ([`model::sections`]) and `general-rows`,
//! `help-rows`, `about-rows` ([`model::rows`] from a [`rows::SettingsState`]). What the player does comes back through
//! two callbacks, turned into an [`Action`] by [`action`]:
//! - `chosen(row-key, words)`: a dropdown's choice;
//! - `pressed(row-key)`: a button.
//!
//! [`apply`] performs the actions that only change the store (关闭窗口时, 全局声音, 主题) and saves the settings, as
//! ui.py does. Every other action is the app's: [`Applied::ForApp`] hands it back untouched. After any action the app
//! rebuilds the rows from a fresh [`rows::SettingsState`].
//!
//! The first-run card (ui/settings/setup.slint `SetupWindow`) shows a [`setup::SetupModel`]; its `retry` and `dismiss`
//! callbacks are the app's (ui_setup.py `retry` and `dismissed`).

pub mod model;
pub mod render;
pub mod rows;
pub mod setup;
#[cfg(test)]
mod tests;

use data::store::Store;

/// What a row of 设置 asks for.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Action {
    /// 开机启动: the app sets start with Windows (win crate), then shows what Windows has; "开机启动没设上" when it failed.
    SetAutostart(bool),
    /// 关闭窗口时: true for 最小化到托盘.
    SetCloseToTray(bool),
    /// 全局声音: true for 静音; the app also stops what plays now.
    SetMuted(bool),
    /// 主题: "light", "dark" or "system"; the app repaints (and follows the system for "system").
    SetAppearance(String),
    /// 环境测试 › 开始: the first open's test again (force).
    RunEnvironmentTest,
    /// 导出日志 › 导出: the logs in one text file on the Desktop, shown in Explorer.
    ExportLogs,
    /// 检查更新 (or 有更新 while a version waits).
    CheckUpdates,
    /// 使用声明 › 查看.
    ShowDisclaimer,
    /// 清空数据 › 清空: ask [`rows::RESET_CONFIRM`] first, then `Store::reset` and start over.
    AskReset,
}

/// The action for a dropdown choice (`value` set) or a button press (`value` None).
pub fn action(row: &str, value: Option<&str>) -> Option<Action> {
    if let Some(words) = value {
        let key = rows::key_of(row, words)?;
        return match row {
            rows::AUTOSTART => Some(Action::SetAutostart(key == "on")),
            rows::CLOSE_MODE => Some(Action::SetCloseToTray(key == "tray")),
            rows::MUTE => Some(Action::SetMuted(key == "on")),
            rows::APPEARANCE => Some(Action::SetAppearance(key.to_string())),
            _ => None,
        };
    }
    match row {
        rows::ENV_TEST => Some(Action::RunEnvironmentTest),
        rows::EXPORT_LOGS => Some(Action::ExportLogs),
        rows::UPDATE => Some(Action::CheckUpdates),
        rows::DISCLAIMER => Some(Action::ShowDisclaimer),
        rows::RESET => Some(Action::AskReset),
        _ => None,
    }
}

/// What [`apply`] did.
#[derive(Debug, PartialEq, Eq)]
pub enum Applied {
    /// The store has it, saved.
    Saved,
    /// Not the store's: the app performs it.
    ForApp(Action),
}

/// The store's part of an action, saved at once (ui.py `_set_close_to_tray`, `_on_mute`, `_set_appearance`).
pub fn apply(store: &mut Store, action: Action) -> std::io::Result<Applied> {
    match action {
        Action::SetCloseToTray(on) => store.settings.close_to_tray = on,
        Action::SetMuted(on) => store.settings.sound_muted = on,
        Action::SetAppearance(ref appearance) if ["light", "dark", "system"].contains(&appearance.as_str()) => {
            store.settings.appearance = appearance.clone();
        }
        Action::SetAppearance(_) => return Ok(Applied::Saved),
        other => return Ok(Applied::ForApp(other)),
    }
    store.save_settings()?;
    Ok(Applied::Saved)
}
