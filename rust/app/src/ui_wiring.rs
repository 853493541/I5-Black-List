//! What the pages leave to the runner (MainUi::pump's leftover UiEvents): 检查's mode, 直播模式, the app-side 设置,
//! the 场景 hotkey's play and the update offer, each sent to the part that does it.

use crate::notices::update::Effect;
use crate::settings::Action as SettingsAction;
use crate::shell::ShellAction;
use crate::stream::StreamAction;
use crate::ui_events::UiEvent;
use app::wiring::runner::Runner;

/// Carries out one event; false when it is not the runner's (only logged).
pub fn handle(runner: &mut Runner, event: &UiEvent) -> bool {
    match event {
        UiEvent::Shell(ShellAction::SetSafeMode(on)) => setting(runner, |s| replace(&mut s.safe_mode, *on)),
        UiEvent::Shell(ShellAction::SetAutoCapture(on)) => setting(runner, |s| replace(&mut s.auto_capture, *on)),
        UiEvent::Shell(ShellAction::SetStreamMode(on)) | UiEvent::Stream(StreamAction::SetStreamMode(on)) => {
            let value = if *on { "on" } else { "" }.to_string();
            setting(runner, |s| replace(&mut s.stream_mode, value))
        }
        UiEvent::Stream(StreamAction::EndQuickPlay) => {
            runner.flow.end_quick();
            true
        }
        UiEvent::Settings(SettingsAction::SetMuted(muted)) => {
            runner.set_muted(*muted);
            true
        }
        UiEvent::Settings(SettingsAction::CheckUpdates) => {
            runner.check_updates_now();
            true
        }
        UiEvent::Settings(SettingsAction::SetAutostart(on)) => {
            autostart(runner, *on);
            true
        }
        UiEvent::Update(Effect::OpenUrl(url)) => {
            open_url(url);
            true
        }
        _ => false,
    }
}

fn replace<T: PartialEq>(slot: &mut T, value: T) -> bool {
    let changed = *slot != value;
    *slot = value;
    changed
}

fn setting(runner: &mut Runner, change: impl FnOnce(&mut data::store::settings::Settings) -> bool) -> bool {
    runner.change_settings(change);
    true
}

/// 开机启动 (autostart.set_enabled), the app's own command with the tray-only flag.
#[cfg(windows)]
fn autostart(runner: &mut Runner, on: bool) {
    let launcher = app::wiring::startup::install_root().and_then(|root| win::autostart::launcher_in(&root));
    let command = launcher.as_deref().map(win::autostart::command);
    let entry = win::autostart::RunEntry::app();
    if on && command.is_none() {
        runner.log.warn("开机启动没设上: no launcher (a build run from source).");
    } else if !entry.set(if on { command.as_deref() } else { None }) {
        runner.log.warn("开机启动没设上.");
    }
}

#[cfg(not(windows))]
fn autostart(runner: &mut Runner, on: bool) {
    runner.log.info(&format!("Autostart {on}: only on Windows."));
}

/// 前往下载: the releases page in the browser.
fn open_url(url: &str) {
    #[cfg(windows)]
    let _ = std::process::Command::new("explorer").arg(url).spawn();
    #[cfg(not(windows))]
    let _ = url;
}
