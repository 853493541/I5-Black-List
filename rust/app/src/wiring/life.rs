//! The app's life outside a check: when to look for updates, what closing the window does, the tray menu, and
//! how 显示 / 方式 / 直播模式 changes are saved (ui.py MainWindow).

use super::flow::Mode;
use super::stubs::TrayAction;
use data::store::settings::Settings;

/// The first look for a new version, after start (UPDATE_FIRST_MS).
pub const UPDATE_FIRST_MS: u64 = 1_000;
/// The look while the app is open (UPDATE_EVERY_MS).
pub const UPDATE_EVERY_MS: u64 = 30 * 60 * 1000;
/// The window back in front looks again when the last look is this old (UPDATE_AGAIN_MS).
pub const UPDATE_AGAIN_MS: u64 = 10 * 60 * 1000;

/// What a look for a new version does with one it finds.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum UpdateLook {
    /// At start, or 检查更新: a new version installs.
    Install,
    /// On the timer or when the window comes back: offered as 有更新, not installed.
    Offer,
}

/// When to look (_check_updates, _check_updates_later, _check_updates_on_return). Times in ms since start.
#[derive(Debug, Clone, Default)]
pub struct UpdateClock {
    /// Only an installed copy updates (updater.app_root() is not None); a build run from source never does.
    pub installed: bool,
    pub updating: bool,
    first_done: bool,
    last_look: Option<u64>,
    next_timer: u64,
}

impl UpdateClock {
    pub fn new(installed: bool) -> Self {
        UpdateClock { installed, next_timer: UPDATE_EVERY_MS, ..Self::default() }
    }

    fn look(&mut self, now: u64, how: UpdateLook) -> Option<UpdateLook> {
        self.last_look = Some(now);
        Some(how)
    }

    /// Called on a timer; returns the look due now, if any.
    pub fn tick(&mut self, now: u64) -> Option<UpdateLook> {
        if !self.installed {
            return None;
        }
        if !self.first_done && now >= UPDATE_FIRST_MS {
            self.first_done = true;
            return self.look(now, UpdateLook::Install);
        }
        if now >= self.next_timer {
            self.next_timer = now + UPDATE_EVERY_MS;
            if !self.updating {
                return self.look(now, UpdateLook::Offer);
            }
        }
        None
    }

    /// The window is in front again.
    pub fn on_return(&mut self, now: u64) -> Option<UpdateLook> {
        let old = self.last_look.is_some_and(|last| now.saturating_sub(last) >= UPDATE_AGAIN_MS);
        if !self.installed || self.updating || !old {
            return None;
        }
        self.look(now, UpdateLook::Offer)
    }
}

/// What the window's X does (closeEvent).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Close {
    /// Hidden, still checking from the tray.
    ToTray,
    /// Everything stops and the app quits.
    Quit,
}

/// The player's X closes to the tray when 关闭时 says so and the tray icon is up; without one there would be no
/// way back, so X quits. 退出 in the tray, or the installer's quit, always quits.
pub fn on_close(settings: &Settings, tray_visible: bool, by_player: bool) -> Close {
    if by_player && settings.close_to_tray && tray_visible {
        Close::ToTray
    } else {
        Close::Quit
    }
}

/// What the runner does for a tray click or a second launch.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Do {
    ShowWindow,
    ShowSettings,
    CheckNow,
    Quit,
}

pub fn on_tray(action: TrayAction) -> Do {
    match action {
        TrayAction::Show => Do::ShowWindow,
        TrayAction::Settings => Do::ShowSettings,
        TrayAction::Check => Do::CheckNow,
        TrayAction::Quit => Do::Quit,
    }
}

/// A second launch's message on the pipe (listen_for_instances): b"show" shows the window, b"quit" quits.
pub fn on_instance_message(message: &[u8]) -> Option<Do> {
    match message {
        b"show" => Some(Do::ShowWindow),
        b"quit" => Some(Do::Quit),
        _ => None,
    }
}

/// Started with Windows stays in the tray unless a first open or the environment check needs the window (run_app).
pub fn start_quiet(background: bool, tray_visible: bool, first_run: bool, settings: &Settings, version: &str) -> bool {
    background && tray_visible && !first_run && settings.disclaimer_accepted && settings.env_checked == version
}

/// The flow's mode as 设置 has it.
pub fn mode_of(settings: &Settings) -> Mode {
    Mode {
        auto: settings.auto_capture,
        safe: settings.safe_mode,
        stream: !settings.stream_mode.is_empty(),
        disclaimer: settings.disclaimer_accepted,
    }
}

/// 方式 picked (_on_auto_mode): 自动 is not offered in 基础模式; the player's own choice ends auto_resume.
/// Returns whether 设置 changed (and is to be saved).
pub fn set_auto(settings: &mut Settings, auto: bool) -> bool {
    if auto && settings.safe_mode {
        return false;
    }
    let changed = settings.auto_capture != auto || settings.auto_resume;
    settings.auto_resume = false;
    settings.auto_capture = auto;
    changed
}

/// 显示 picked (_set_safe_mode): 基础模式 checks on the hotkey only, and 自动检查 comes back with 完整模式.
pub fn set_safe(settings: &mut Settings, safe: bool) -> bool {
    let before = (settings.safe_mode, settings.auto_capture, settings.auto_resume);
    settings.safe_mode = safe;
    if safe && settings.auto_capture {
        settings.auto_resume = true;
        settings.auto_capture = false;
    } else if !safe && settings.auto_resume {
        settings.auto_resume = false;
        settings.auto_capture = true;
    }
    before != (settings.safe_mode, settings.auto_capture, settings.auto_resume)
}

/// 直播模式 (_set_stream_mode): stored as "on" or "".
pub fn set_stream(settings: &mut Settings, on: bool) -> bool {
    let value = if on { "on" } else { "" };
    let changed = settings.stream_mode != value;
    settings.stream_mode = value.into();
    changed
}

#[cfg(test)]
#[path = "life_tests.rs"]
mod tests;
