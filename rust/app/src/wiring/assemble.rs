//! The real parts put together for the exe: the pipeline's checker, the marks, the scenes, the sound and the tray,
//! each the crate's own on Windows and `Quiet` where it cannot run.

use super::engine::{self, PipelineChecker, SharedLists};
use super::flow::Ports;
use super::parts::{self, SharedSounds, Sound};
use super::records::StoreRecords;
use super::startup::{model_roots, AppLog};
use super::stubs::{Overlay, Quiet, ScenePlayer, Tray, TrayAction};
use data::store::Store;
use std::cell::RefCell;
use std::path::{Path, PathBuf};
use std::rc::Rc;
use std::sync::mpsc::{channel, Receiver};

/// What main hands the runner and the worker.
pub struct Assembled {
    pub ports: Ports,
    pub checker: PipelineChecker,
    pub before_check: Box<dyn Fn(&Store)>,
    pub tray: Box<dyn Tray>,
    pub tray_actions: Receiver<TrayAction>,
    pub placed: Receiver<super::stubs::Rect>,
    pub tester: (super::runner::MakeChecker, PathBuf),
}

/// The app's pictures and tunes: the release's blacklist_detect\assets, else beside the exe, else the source's.
pub fn assets_dir(install: Option<&Path>) -> PathBuf {
    let beside = std::env::current_exe().ok().and_then(|exe| exe.parent().map(|dir| dir.join("assets")));
    let candidates =
        [install.map(|root| root.join("blacklist_detect").join("assets")), beside, Some(PathBuf::from("../blacklist_detect/assets"))];
    candidates.into_iter().flatten().find(|dir| dir.is_dir()).unwrap_or_else(|| PathBuf::from("assets"))
}

pub fn assemble(store: &Rc<RefCell<Store>>, install: Option<&Path>, log: &AppLog, seed: u32) -> Assembled {
    let lists = SharedLists::default();
    let sounds = SharedSounds::default();
    let copy = {
        let (lists, sounds) = (lists.clone(), sounds.clone());
        move |store: &Store| {
            engine::share(store, &lists);
            parts::share_sounds(store, &sounds);
        }
    };
    copy(&store.borrow());
    let library = engine::ort_library(install);
    let dirs = pipeline::ModelDirs::find(&model_roots(install));
    log.info(&format!("OCR: runtime {}, models {}", library.display(), if dirs.is_some() { "found" } else { "missing" }));
    let tester: super::runner::MakeChecker = {
        let (library, dirs) = (library.clone(), dirs.clone());
        Box::new(move || PipelineChecker::new(library.clone(), dirs.clone(), common::paths::ocr_threads(), SharedLists::default()))
    };
    let mut checker = PipelineChecker::new(library, dirs, common::paths::ocr_threads(), lists);
    let (placed_sender, placed) = channel();
    checker.placed = Some(placed_sender);
    let mut player = Sound::system(assets_dir(install), sounds);
    player.0.set_muted(store.borrow().settings.sound_muted);
    let (sender, tray_actions) = channel::<TrayAction>();
    let ports = Ports {
        overlay: overlay(),
        notice: Box::new(Quiet),
        scenes: scenes(),
        player: Box::new(player),
        records: Box::new(StoreRecords::new(store.clone(), seed)),
    };
    Assembled { ports, checker, before_check: Box::new(copy), tray: tray(sender, log), tray_actions, placed, tester: (tester, assets_dir(install)) }
}

#[cfg(windows)]
fn overlay() -> Box<dyn Overlay> {
    Box::new(super::marks::ScreenMarks::default())
}

#[cfg(not(windows))]
fn overlay() -> Box<dyn Overlay> {
    Box::new(Quiet)
}

#[cfg(windows)]
fn scenes() -> Box<dyn ScenePlayer> {
    Box::new(super::scenes::StageScenes::default())
}

#[cfg(not(windows))]
fn scenes() -> Box<dyn ScenePlayer> {
    Box::new(Quiet)
}

#[cfg(windows)]
fn tray(sender: std::sync::mpsc::Sender<TrayAction>, log: &AppLog) -> Box<dyn Tray> {
    match parts::SystemTray::spawn(sender) {
        Ok(tray) => Box::new(tray),
        Err(error) => {
            log.warn(&format!("Tray: no icon: {error:?}"));
            Box::new(Quiet)
        }
    }
}

#[cfg(not(windows))]
fn tray(_sender: std::sync::mpsc::Sender<TrayAction>, _log: &AppLog) -> Box<dyn Tray> {
    Box::new(Quiet)
}
