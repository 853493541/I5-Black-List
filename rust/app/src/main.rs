//! 模仿者小工具, the real exe (blacklist_detect/__main__.py and ui.run_app): start-up, then the window, the tray and
//! the checks until 退出. `--quit-after-start` runs the start-up steps and leaves before any window opens.

// deny, not forbid: the code Slint generates from ui/ allows unsafe in its own items.
#![deny(unsafe_code)]
// No console window beside the app (v1.0.1 opened none). Release and preview builds only: a debug build keeps its
// console for tests. Without a console, std's prints go nowhere instead of failing; redirected (`check > file`), they
// still reach the file. The log is logs/app.log either way.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use app::wiring::life::{self, Close, Do};
use app::wiring::runner::{Keys, Parts, Runner};
use app::wiring::startup::{self, Options, Outcome, Started, VERSION};
use app::wiring::assemble::assemble;
use app::wiring::worker::{RealScreen, Worker};
use std::cell::RefCell;
use std::process::ExitCode;
use std::rc::Rc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

mod cli;
mod corner_port;
mod stream_marks;
mod update_port;
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
    // The Rust preview's name, data folder and tray (a no-op in the normal build).
    app::preview::install();
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
    // Screen pixels, not scaled ones, before any window or screen copy: at 125 % a copy made without it is cut.
    #[cfg(windows)]
    log.info(&format!("DPI awareness (per monitor v2) set here: {}", win::capture::set_dpi_awareness()));
    // 调试截图 (ui._save_debug): the worker keeps each check's capture while 设置 has it on.
    let debug_frames = Arc::new(AtomicBool::new(store.settings.save_debug_frames));
    let debug_screen = app::wiring::debug::DebugCapture { inner: RealScreen, dir: root.join("debug"), on: debug_frames.clone() };
    if models.is_none() {
        log.warn("No OCR models: the header says 识别还没准备好 until they are installed.");
    }
    let keys = keys(&store, &log);
    let first_run = store.first_run();
    let store = Rc::new(RefCell::new(store));
    let mut parts = assemble(&store, install.as_deref(), &log, seed());
    parts.ports.notice = Box::new(corner_port::CornerPort::new());
    let screen_marks = std::mem::replace(&mut parts.ports.overlay, Box::new(app::wiring::stubs::Quiet));
    parts.ports.overlay = Box::new(stream_marks::WithStream::new(screen_marks, store.clone()));
    let tray_visible = parts.tray.visible();
    // The real app's run is the only one that makes a sound (ui_music.allow_sound); BLACKLIST_DETECT_SILENT=1 keeps a
    // test run of the exe quiet.
    if std::env::var("BLACKLIST_DETECT_SILENT").as_deref() != Ok("1") {
        sound::allow_sound();
    }
    let parts = Parts {
        ports: parts.ports,
        worker: Worker::start(Box::new(debug_screen), Box::new(parts.checker)),
        keys,
        // The preview never looks for updates: it gets Quiet, and NetUpdate is not even made.
        update_check: if app::preview::ON {
            app::preview::updater(Box::new(app::wiring::stubs::Quiet), true)
        } else {
            Box::new(app::wiring::updates::NetUpdate::online(VERSION, root.clone()))
        },
        tray: parts.tray,
        tray_actions: parts.tray_actions,
        installed: install.is_some(),
        before_check: Some(parts.before_check),
        placed: Some(parts.placed),
        tester: Some(parts.tester),
    };
    let runner = Rc::new(RefCell::new(Runner::new(root, log, claim, store.clone(), parts)));
    if models.is_none() {
        // As v1.0.1's warm-up says at start: the pill shows it before the first press, not only after it.
        let unzip = startup::unzip_first(install.as_deref());
        runner.borrow_mut().flow.report_problem(&app::wiring::engine::no_models_for(unzip));
    }

    let ui = Rc::new(ui_app::MainUi::new(store.clone(), &app::preview::shown_version(VERSION, app::preview::ON))?);
    let window = ui.window.clone_strong();
    let quiet = life::start_quiet(options.background, tray_visible, first_run, &store.borrow().settings, VERSION);
    if quiet {
        runner.borrow().log.info("Started with Windows; staying in the tray.");
    } else {
        window.show()?;
        // 使用声明 first, on a data folder that has not agreed: until then no check starts. Asked once the event loop
        // runs: shown before it, its window was made first and the main window covered it exactly (real-input test).
        let asking = ui.clone();
        slint::Timer::single_shot(Duration::from_millis(300), move || asking.ask_disclaimer());
    }
    // Never in the preview: install_root is None there, and the sweep must not touch anything outside its folder.
    if let Some(install) = install.filter(|_| !app::preview::ON) {
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
    let mut updates = update_port::UpdatePort::default();
    let mut hotkeys = {
        let settings = &store.borrow().settings;
        (settings.hotkey.clone(), settings.effect_hotkey.clone())
    };
    timer.start(slint::TimerMode::Repeated, Duration::from_millis(50), move || {
        let mut redraw = false;
        for event in pages.pump() {
            if event == ui_events::UiEvent::Shell(shell::ShellAction::OpenUpdate) {
                updates.open(&mut pumped.borrow_mut());
            } else if ui_wiring::handle(&mut pumped.borrow_mut(), &event) {
                redraw |= ui_wiring::changes_pages(&event);
            } else {
                pumped.borrow().log.info(&ui_events::log_line(&event));
            }
        }
        for note in pages.notes() {
            pumped.borrow().log.info(&note);
        }
        if redraw {
            pages.refresh();
        }
        if pages.hotkey_waiting() {
            // The box waits for a key: both hotkeys let go of theirs, so either key reaches it (_begin_hotkey); the
            // empty pair makes rekey register them again once it is done.
            if hotkeys != Default::default() {
                pumped.borrow_mut().set_keys(Box::new(app::wiring::runner::NoKeys));
                hotkeys = Default::default();
            }
        } else {
            ui_wiring::rekey(&mut pumped.borrow_mut(), &mut hotkeys);
        }
        debug_frames.store(pumped.borrow().store.borrow().settings.save_debug_frames, Ordering::Relaxed);
        pages.set_hotkey_note(&pumped.borrow().hotkey_note());
        pages.set_export_note(&ui_wiring::export_note());
        updates.pump(&mut pumped.borrow_mut());
        let asks = pumped.borrow_mut().pump();
        // Every check's problem in the pill (识别还没准备好 / 读不到屏幕 / 检查失败), never silent.
        if let Some(words) = pages.show_problem(pumped.borrow().flow.problem.as_ref()) {
            pumped.borrow().log.info(&format!("Header: {words}"));
        }
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
