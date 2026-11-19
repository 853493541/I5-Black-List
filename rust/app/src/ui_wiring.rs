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
        UiEvent::Shell(ShellAction::AnswerDisclaimer(true)) => {
            runner.log.info("使用声明 agreed to.");
            setting(runner, |s| replace(&mut s.disclaimer_accepted, true))
        }
        UiEvent::Shell(ShellAction::AnswerDisclaimer(false)) => {
            runner.log.info("使用声明 declined: closing.");
            let _ = slint::quit_event_loop();
            true
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
        UiEvent::Settings(SettingsAction::RunEnvironmentTest) => {
            runner.start_env_test();
            true
        }
        UiEvent::Settings(SettingsAction::ExportLogs) => {
            export_logs(runner);
            true
        }
        UiEvent::Update(Effect::StartDownload) => {
            if !runner.start_install() {
                runner.log.warn("Update: nothing to download (no release offered, or run from source).");
            }
            true
        }
        UiEvent::Update(Effect::RestartAfter(ms)) => {
            restart_after(runner, *ms);
            true
        }
        UiEvent::Update(Effect::OpenUrl(url)) => {
            open_url(url);
            true
        }
        _ => false,
    }
}

/// Whether the pages show what `event` changed, so they are drawn again from the store after it is handled: 显示,
/// 方式 and 直播模式 only send their choice, and the panel shows the store's value.
pub fn changes_pages(event: &UiEvent) -> bool {
    matches!(
        event,
        UiEvent::Shell(
            ShellAction::SetSafeMode(_)
                | ShellAction::SetAutoCapture(_)
                | ShellAction::SetStreamMode(_)
                | ShellAction::AnswerDisclaimer(true)
        )
            | UiEvent::Stream(StreamAction::SetStreamMode(_))
    )
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
    if app::preview::ON {
        // The Run entry is v1.0.1's: the preview never adds, changes or removes it.
        runner.log.info(&format!("Autostart {on}: off in the preview; v1.0.1's entry is left as it is."));
        return;
    }
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

/// 导出日志: the file on the Desktop, shown in Explorer.
thread_local! {
    /// 导出's last word for its row in 设置 (ui._say): "" until it was pressed.
    static EXPORT_NOTE: std::cell::RefCell<String> = const { std::cell::RefCell::new(String::new()) };
}

/// What 导出 said last, for 设置's 导出日志 row.
pub fn export_note() -> String {
    EXPORT_NOTE.with(|note| note.borrow().clone())
}

/// ui._export_logs's words: the file's name when it was written, else why not.
pub fn export_words(written: &std::io::Result<std::path::PathBuf>) -> String {
    match written {
        Ok(path) => format!("已存到桌面：{}", path.file_name().map(|name| name.to_string_lossy().into_owned()).unwrap_or_default()),
        Err(_) => "桌面存不了文件，日志没导出".to_string(),
    }
}

fn export_logs(runner: &mut Runner) {
    use app::wiring::export;
    let account = export::account();
    let report = runner.flow_report.clone().unwrap_or_default();
    let written =
        export::export_into(&runner.root, &runner.store.borrow(), app::wiring::startup::VERSION, &report, &export::desktop(&account), &account);
    EXPORT_NOTE.with(|note| *note.borrow_mut() = export_words(&written));
    match written {
        Ok(path) => {
            runner.log.info(&format!("Logs exported: {}", path.display()));
            // explorer reads `/select,"<path>"` itself: as one quoted argument it ignored it and opened Documents.
            #[cfg(windows)]
            {
                use std::os::windows::process::CommandExt;
                let _ = std::process::Command::new("explorer").raw_arg(format!("/select,\"{}\"", path.display())).spawn();
            }
        }
        Err(error) => runner.log.warn(&format!("Logs not exported: {error}")),
    }
}

/// 前往下载: the releases page in the browser.
pub fn open_url(url: &str) {
    #[cfg(windows)]
    let _ = std::process::Command::new("explorer").arg(url).spawn();
    #[cfg(not(windows))]
    let _ = url;
}

/// The 检查 and 场景 hotkeys as last registered: when 设置 changes them, the old ones go and the new ones are taken.
pub fn rekey(runner: &mut Runner, last: &mut (String, String)) {
    let now = {
        let settings = &runner.store.borrow().settings;
        (settings.hotkey.clone(), settings.effect_hotkey.clone())
    };
    if now == *last {
        return;
    }
    *last = now;
    // Released first: Windows refuses a key this window still holds.
    runner.set_keys(Box::new(app::wiring::runner::NoKeys));
    let keys = super::keys(&runner.store.borrow(), &runner.log);
    runner.set_keys(keys);
    runner.log.info(&format!("Hotkeys: {} / {}", last.0, last.1));
}

/// After `ms`, the launcher starts to lay the update over, and this app ends.
pub fn restart_after(runner: &mut Runner, ms: u64) {
    let Some(install) = app::wiring::startup::install_root() else {
        runner.log.warn("Update: no release folder to restart into.");
        return;
    };
    runner.log.info(&format!("Update: restarting into it in {ms} ms."));
    slint::Timer::single_shot(std::time::Duration::from_millis(ms), move || {
        if app::wiring::updates::restart_into_update(&install, false) {
            let _ = slint::quit_event_loop();
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn export_says_where_the_file_went_or_why_not() {
        let written = Ok(std::path::PathBuf::from(r"C:\Users\a\Desktop\模仿者小工具_日志_20261119-1200.txt"));
        assert_eq!(export_words(&written), "已存到桌面：模仿者小工具_日志_20261119-1200.txt");
        assert_eq!(export_words(&Err(std::io::Error::other("no desktop"))), "桌面存不了文件，日志没导出");
    }

    #[test]
    fn the_check_panel_choices_redraw_the_pages() {
        // 显示, 方式 and 直播模式 only send the choice: without a redraw the panel kept showing the old one.
        for event in [
            UiEvent::Shell(ShellAction::SetSafeMode(false)),
            UiEvent::Shell(ShellAction::SetAutoCapture(true)),
            UiEvent::Shell(ShellAction::SetStreamMode(true)),
            UiEvent::Stream(StreamAction::SetStreamMode(false)),
        ] {
            assert!(changes_pages(&event), "{event:?}");
        }
        assert!(changes_pages(&UiEvent::Shell(ShellAction::AnswerDisclaimer(true))));
        assert!(!changes_pages(&UiEvent::Shell(ShellAction::BeginHotkey)));
        assert!(!changes_pages(&UiEvent::Settings(SettingsAction::ExportLogs)));
    }
}
