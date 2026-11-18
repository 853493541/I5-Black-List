//! 模仿者小工具, the real exe (blacklist_detect/__main__.py and ui.run_app): start-up, then the window, the tray and
//! the checks until 退出. `--quit-after-start` runs the start-up steps and leaves before any window opens.

// deny, not forbid: the code Slint generates from ui/ allows unsafe in its own items.
#![deny(unsafe_code)]

use app::wiring::flow::Ports;
use app::wiring::life::{self, Close, Do};
use app::wiring::records::StoreRecords;
use app::wiring::runner::{Keys, Parts, Runner};
use app::wiring::startup::{self, Options, Outcome, Started, VERSION};
use app::wiring::stubs::{NoChecker, Quiet, Tray, TrayAction};
use app::wiring::worker::{RealScreen, Worker};
use std::cell::RefCell;
use std::process::ExitCode;
use std::rc::Rc;
use std::time::Duration;

slint::include_modules!();

fn main() -> ExitCode {
    // v1.0.1's launcher starts runtime\模仿者小工具.exe as "-m blacklist_detect [args]" (rust-switchover.md).
    let args = data::update::switchover::app_args(std::env::args().skip(1));
    let options = Options::parse(&args);
    let started = match startup::start(&options) {
        Ok(Outcome::Run(started)) => started,
        Ok(Outcome::AlreadyRunning) => return ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("{error}");
            return ExitCode::FAILURE;
        }
    };
    if options.quit_after_start {
        started.log.info("Start-up done; quitting (--quit-after-start).");
        startup::finish(&started, 0);
        return ExitCode::SUCCESS;
    }
    match run(*started, &options) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("{error}");
            ExitCode::FAILURE
        }
    }
}

/// The 检查 and 场景 hotkeys of 设置, registered on the window's thread.
#[cfg(windows)]
fn keys(store: &data::store::Store, log: &startup::AppLog) -> Box<dyn Keys> {
    Box::new(app::wiring::runner::SystemKeys::register(&store.settings, log))
}

#[cfg(not(windows))]
fn keys(_store: &data::store::Store, _log: &startup::AppLog) -> Box<dyn Keys> {
    Box::new(app::wiring::runner::NoKeys)
}

fn run(started: Started, options: &Options) -> Result<(), Box<dyn std::error::Error>> {
    let Started { root, log, store, models, claim, install } = started;
    if models.is_none() {
        log.warn("No OCR models: checks will say 检查失败 until they are installed.");
    }
    let keys = keys(&store, &log);
    let first_run = store.first_run();
    let store = Rc::new(RefCell::new(store));
    // stub: tray (the icon and its menu send TrayAction on this channel)
    let (_tray_sender, tray_actions) = std::sync::mpsc::channel::<TrayAction>();
    let tray = Quiet;
    let tray_visible = tray.visible();
    let ports = Ports {
        overlay: Box::new(Quiet),    // stub: overlay
        notice: Box::new(Quiet),     // stub: notice
        scenes: Box::new(Quiet),     // stub: stage
        player: Box::new(Quiet),     // stub: sound (allow_sound is the real app's alone)
        records: Box::new(StoreRecords(store.clone())),
    };
    let parts = Parts {
        ports,
        // stub: pipeline (the real Checker reads the lobby with the ocr and lobby crates)
        worker: Worker::start(Box::new(RealScreen), Box::new(NoChecker)),
        keys,
        update_check: Box::new(Quiet), // stub: updater
        tray: Box::new(tray),
        tray_actions,
        installed: install.is_some(),
    };
    let runner = Rc::new(RefCell::new(Runner::new(root, log, claim, store.clone(), parts)));

    // stub: shell (MainWindow from ui/shell/main.slint with its pages; the 设置 mock-up until it lands)
    let window = SettingsWindow::new()?;
    let quiet = life::start_quiet(options.background, tray_visible, first_run, &store.borrow().settings, VERSION);
    if quiet {
        runner.borrow().log.info("Started with Windows; staying in the tray.");
    } else {
        window.show()?;
    }
    if let Some(install) = install {
        // Up and running: tell the launcher, and sweep what the release no longer ships, off the window's thread.
        let data_root = runner.borrow().root.clone();
        let started = std::thread::Builder::new().name("AfterStart".into()).spawn(move || {
            let cleaned = data::update::switchover::after_good_start(&install, VERSION);
            startup::AppLog::open(&data_root).info(&format!(
                "After start: confirmed {}, {} old files deleted, {} left for the next start.",
                cleaned.confirmed, cleaned.files, cleaned.failed
            ));
        });
        if let Err(error) = started {
            runner.borrow().log.warn(&format!("After start: not run: {error}"));
        }
    }
    let on_close = runner.clone();
    window.window().on_close_requested(move || {
        if on_close.borrow_mut().close(true) == Close::Quit {
            let _ = slint::quit_event_loop();
        }
        slint::CloseRequestResponse::HideWindow
    });
    let timer = slint::Timer::default();
    let (pumped, shown) = (runner.clone(), window.as_weak());
    timer.start(slint::TimerMode::Repeated, Duration::from_millis(50), move || {
        let asks = pumped.borrow_mut().pump();
        for ask in asks {
            match ask {
                Do::ShowWindow | Do::ShowSettings => {
                    if let Some(window) = shown.upgrade() {
                        let _ = window.show();
                        pumped.borrow_mut().window_returned();
                    }
                }
                Do::Quit => {
                    let _ = slint::quit_event_loop();
                }
                Do::CheckNow => {}
            }
        }
    });
    slint::run_event_loop_until_quit()?;
    timer.stop();
    runner.borrow_mut().quit(0);
    Ok(())
}
