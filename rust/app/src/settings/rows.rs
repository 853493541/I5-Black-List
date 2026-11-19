//! Every section and row of 设置 as blacklist_detect/ui.py `_settings_page` builds them: wording, controls, and
//! each dropdown's choices with its default first. `golden.json` (tools/rust_golden_settings_ui.py) proves it.

use data::store::settings::Settings;

/// A section of the catalog: key, title, icon (kit.slint `Icon` names).
pub const SECTIONS: [(&str, &str, &str); 3] = [("general", "常规", "settings"), ("help", "帮助", "help"), ("about", "关于", "info")];

/// What a row holds on its right.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Control {
    /// A dropdown: (key, label) per choice, the default first.
    Choice(&'static [(&'static str, &'static str)]),
    /// An outlined button with its words.
    Button(&'static str),
    /// The red button of 清空数据.
    Danger(&'static str),
}

#[derive(Clone, Copy, Debug)]
pub struct RowSpec {
    pub section: &'static str,
    pub key: &'static str,
    pub name: &'static str,
    /// The gray line under the name; empty where the name alone says it. 检查更新's is the version, filled in later.
    pub description: &'static str,
    pub control: Control,
}

pub const AUTOSTART: &str = "autostart";
pub const CLOSE_MODE: &str = "close_mode";
pub const MUTE: &str = "mute";
pub const APPEARANCE: &str = "appearance";
pub const ENV_TEST: &str = "env_test";
pub const EXPORT_LOGS: &str = "export_logs";
pub const UPDATE: &str = "update";
pub const DISCLAIMER: &str = "disclaimer";
pub const RESET: &str = "reset";

pub const ROWS: [RowSpec; 9] = [
    RowSpec {
        section: "general",
        key: AUTOSTART,
        name: "开机启动",
        description: "Windows 启动时自动打开",
        control: Control::Choice(&[("off", "关闭"), ("on", "开启")]),
    },
    RowSpec {
        section: "general",
        key: CLOSE_MODE,
        name: "关闭窗口时",
        description: "",
        control: Control::Choice(&[("tray", "最小化到托盘"), ("quit", "退出程序")]),
    },
    RowSpec { section: "general", key: MUTE, name: "全局声音", description: "", control: Control::Choice(&[("off", "播放"), ("on", "静音")]) },
    RowSpec {
        section: "general",
        key: APPEARANCE,
        name: "主题",
        description: "",
        control: Control::Choice(&[("light", "浅色"), ("dark", "深色"), ("system", "跟随系统")]),
    },
    RowSpec { section: "help", key: ENV_TEST, name: "环境测试", description: "", control: Control::Button("开始") },
    RowSpec { section: "help", key: EXPORT_LOGS, name: "导出日志", description: "", control: Control::Button("导出") },
    RowSpec { section: "about", key: UPDATE, name: "检查更新", description: "当前版本", control: Control::Button("检查更新") },
    RowSpec { section: "about", key: DISCLAIMER, name: "使用声明", description: "免费自制工具，和官方无关", control: Control::Button("查看") },
    RowSpec { section: "about", key: RESET, name: "清空数据", description: "删除黑名单、嘉宾、记录和全部设置", control: Control::Danger("清空") },
];

/// 清空数据's question before anything is dropped (ui.py `_ask_reset`): the text, the title, the button.
pub const RESET_CONFIRM: (&str, &str, &str) = ("清空数据后无法恢复，是否确定清空？", "清空数据", "清空");
/// The button 检查更新 turns into while a new version waits.
pub const UPDATE_WAITING: &str = "有更新";

/// What 设置 shows: the settings the store holds, and what only the app knows (autostart, the version, updates).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SettingsState {
    pub autostart_on: bool,
    /// False where start with Windows cannot be set (not Windows, or no permission): 开机启动 is grayed.
    pub autostart_available: bool,
    pub close_to_tray: bool,
    pub sound_muted: bool,
    pub appearance: String,
    /// `__version__`, e.g. "v1.0.1"; shown without the v.
    pub version: String,
    /// What 检查更新 found, in gray before the button; empty for none.
    pub update_note: String,
    pub update_waiting: bool,
    /// What 导出 did, in gray before its button (ui._say): 已存到桌面：<file>, or why not.
    pub export_note: String,
}

impl SettingsState {
    pub fn new(settings: &Settings, autostart_on: bool, autostart_available: bool, version: &str) -> Self {
        SettingsState {
            autostart_on,
            autostart_available,
            close_to_tray: settings.close_to_tray,
            sound_muted: settings.sound_muted,
            appearance: settings.appearance.clone(),
            version: version.to_string(),
            update_note: String::new(),
            update_waiting: false,
            export_note: String::new(),
        }
    }

    /// The chosen key of a dropdown row.
    pub fn choice_key(&self, row: &str) -> &str {
        match row {
            AUTOSTART => on_off(self.autostart_on),
            CLOSE_MODE => {
                if self.close_to_tray {
                    "tray"
                } else {
                    "quit"
                }
            }
            MUTE => on_off(self.sound_muted),
            APPEARANCE => &self.appearance,
            _ => "",
        }
    }
}

fn on_off(on: bool) -> &'static str {
    if on {
        "on"
    } else {
        "off"
    }
}

/// One row as the page draws it.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Row {
    pub section: &'static str,
    pub first: bool,
    pub key: &'static str,
    pub name: &'static str,
    pub description: String,
    /// "choice", "button" or "danger".
    pub kind: &'static str,
    pub choices: Vec<&'static str>,
    /// The chosen choice's words.
    pub value: String,
    /// The button's words.
    pub label: &'static str,
    pub note: String,
    pub enabled: bool,
}

/// The rows of one section, in order.
pub fn rows(state: &SettingsState, section: &str) -> Vec<Row> {
    ROWS.iter().filter(|spec| spec.section == section).enumerate().map(|(index, spec)| row(state, spec, index == 0)).collect()
}

fn row(state: &SettingsState, spec: &RowSpec, first: bool) -> Row {
    let description = if spec.key == UPDATE {
        // The number alone: "v0.9.15" read as a typo beside 当前版本.
        format!("{} {}", spec.description, state.version.strip_prefix('v').unwrap_or(&state.version))
    } else {
        spec.description.to_string()
    };
    let (kind, choices, value, label) = match spec.control {
        Control::Choice(options) => {
            let key = state.choice_key(spec.key);
            let value = options.iter().find(|(k, _)| *k == key).unwrap_or(&options[0]).1;
            ("choice", options.iter().map(|(_, l)| *l).collect(), value.to_string(), "")
        }
        Control::Button(words) => ("button", Vec::new(), String::new(), if spec.key == UPDATE && state.update_waiting { UPDATE_WAITING } else { words }),
        Control::Danger(words) => ("danger", Vec::new(), String::new(), words),
    };
    Row {
        section: spec.section,
        first,
        key: spec.key,
        name: spec.name,
        description,
        kind,
        choices,
        value,
        label,
        note: match spec.key {
            UPDATE => state.update_note.clone(),
            EXPORT_LOGS => state.export_note.clone(),
            _ => String::new(),
        },
        enabled: spec.key != AUTOSTART || state.autostart_available,
    }
}

/// The key of the choice whose words are `label` in a dropdown row.
pub fn key_of(row: &str, label: &str) -> Option<&'static str> {
    let spec = ROWS.iter().find(|spec| spec.key == row)?;
    let Control::Choice(options) = spec.control else { return None };
    options.iter().find(|(_, l)| *l == label).map(|(k, _)| *k)
}
