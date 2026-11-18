//! 模仿者小工具, the real exe (blacklist_detect/__main__.py and ui.run_app): start-up, then the window, the tray and
//! the checks until 退出. `--quit-after-start` runs the start-up steps and leaves before any window opens.

// deny, not forbid: the code Slint generates from ui/ allows unsafe in its own items.
#![deny(unsafe_code)]

use app::wiring::life::{self, Close, Do};
use app::wiring::runner::{Keys, Parts, Runner};
use app::wiring::startup::{self, Options, Outcome, Started, VERSION};
use app::wiring::assemble::assemble;
use app::wiring::worker::{RealScreen, Worker};
use std::cell::RefCell;
use std::process::ExitCode;
use std::rc::Rc;
use std::time::Duration;

mod cli;
mod corner_port;
mod stream_marks;
mod ui_wiring;

// The UI areas, each its own package's; the shell's MainWindow takes their pages.
mod dialogs;
mod guestedit;
mod guests;
mod history;
#[allow(dead_code)]
mod kit;
mod list;
mod notices;
#[allow(dead_code)]
mod settings;
mod shell;
mod shots;
mod stream;
mod ui_app;
mod ui_dialogs;
mod ui_events;

slint::include_modules!();

fn main() -> ExitCode {
    // The OCR's own thread count (paths.ocr_threads); the one this copy was started with is only logged.
    let inherited = std::env::var("OMP_NUM_THREADS").ok();
    std::env::set_var("OMP_NUM_THREADS", common::paths::ocr_threads().to_string());
    // v1.0.1's launcher starts runtime\模仿者小工具.exe as "-m blacklist_detect [args]" (rust-switchover.md).
    let args = data::update::switchover::app_args(std::env::args().skip(1));
    if args.first().map(String::as_str) == Some("--wgc") {
        // diagnose.ask_in_child: whether Windows lets another process copy these windows.
        for line in wgc_answers(&args[1..]) {
            println!("{line}");
        }
        return ExitCode::SUCCESS;
    }
    match cli::parse(&args) {
        Err(cli::UsageError) => {
            eprintln!("{}", cli::usage("blacklist-detect"));
            return ExitCode::from(cli::USAGE_CODE as u8);
        }
        Ok(cli::Command::Check { image }) => return check_image(&image),
        Ok(cli::Command::DownloadModels) => return download_models(),
        Ok(cli::Command::Window { .. }) => {}
    }
    let options = Options::parse(&args);
    let started = match startup::start(&options) {
        Ok(Outcome::Run(started)) => started,
        Ok(Outcome::AlreadyRunning) => return ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("{error}");
            return ExitCode::FAILURE;
        }
    };
    if let Some(threads) = &inherited {
        started.log.info(&format!("Started with OMP_NUM_THREADS={threads} from the program that started it; dropped."));
    }
    started.log.info(&format!("OCR threads: {}", common::paths::ocr_threads()));
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

/// `check <image>`: the lobby in one picture, read against the player's 黑名单 (__main__._check_cli).
fn check_image(image: &str) -> ExitCode {
    let store = data::store::Store::open(None, data::store::Clock::default());
    let blacklist = app::wiring::engine::Lists::of(&store).blacklist;
    let install = startup::install_root();
    let result = match app::wiring::engine::check_image(std::path::Path::new(image), &blacklist, install.as_deref()) {
        Ok(result) => result,
        Err(error) => {
            eprintln!("{error}");
            return ExitCode::FAILURE;
        }
    };
    let check = cli::Check {
        message: result.message.clone(),
        seats: result
            .names
            .iter()
            .map(|slot| (slot.index, cli::SeatState::of(slot.unclear, slot.truncated), slot.confidence, slot.raw.clone()))
            .collect(),
        hits: result.hits.iter().map(|hit| hit.line.clone()).collect(),
        header_found: result.header_found,
    };
    for line in check.lines() {
        println!("{line}");
    }
    ExitCode::from(check.exit_code() as u8)
}

/// `download-models`: the models ship in the release, so this only says whether they are here.
fn download_models() -> ExitCode {
    let install = startup::install_root();
    if pipeline::ModelDirs::find(&startup::model_roots(install.as_deref())).is_some() {
        println!("{}", cli::DOWNLOAD_OK);
        ExitCode::SUCCESS
    } else {
        eprintln!("{}", pipeline::Unavailable);
        ExitCode::FAILURE
    }
}

#[cfg(windows)]
fn wgc_answers(windows: &[String]) -> Vec<String> {
    win::wgc::answer_lines(windows, &win::wgc::capture::answer)
}

#[cfg(not(windows))]
fn wgc_answers(windows: &[String]) -> Vec<String> {
    win::wgc::answer_lines(windows, &|_| None)
}

/// A seed for the draws of the run (love_scenes' random): the clock's.
fn seed() -> u32 {
    std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map_or(0, |since| since.subsec_nanos() ^ since.as_secs() as u32)
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
    let mut parts = assemble(&store, install.as_deref(), &log, seed());
    parts.ports.notice = Box::new(corner_port::CornerPort::new());
    let screen_marks = std::mem::replace(&mut parts.ports.overlay, Box::new(app::wiring::stubs::Quiet));
    parts.ports.overlay = Box::new(stream_marks::WithStream::new(screen_marks, store.clone()));
    let tray_visible = parts.tray.visible();
    // The real app's run is the only one that makes a sound (ui_music.allow_sound).
    sound::allow_sound();
    let parts = Parts {
        ports: parts.ports,
        worker: Worker::start(Box::new(RealScreen), Box::new(parts.checker)),
        keys,
        update_check: Box::new(app::wiring::updates::NetUpdate::online(VERSION, root.clone())),
        tray: parts.tray,
        tray_actions: parts.tray_actions,
        installed: install.is_some(),
        before_check: Some(parts.before_check),
        placed: Some(parts.placed),
        tester: Some(parts.tester),
    };
    let runner = Rc::new(RefCell::new(Runner::new(root, log, claim, store.clone(), parts)));

    let ui = Rc::new(ui_app::MainUi::new(store.clone(), VERSION)?);
    let window = ui.window.clone_strong();
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
    let pages = ui.clone();
    let mut hotkeys = {
        let settings = &store.borrow().settings;
        (settings.hotkey.clone(), settings.effect_hotkey.clone())
    };
    timer.start(slint::TimerMode::Repeated, Duration::from_millis(50), move || {
        for event in pages.pump() {
            if !ui_wiring::handle(&mut pumped.borrow_mut(), &event) {
                pumped.borrow().log.info(&format!("UI: {event:?}"));
            }
        }
        ui_wiring::rekey(&mut pumped.borrow_mut(), &mut hotkeys);
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
