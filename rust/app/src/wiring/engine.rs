//! The real check (pipeline.py's check_frames and glance_title): the OCR models on ONNX Runtime, loaded on the
//! worker thread at the first check, reading the screen copies against the lists as they are when the check starts.
//! The pipeline matches the 嘉宾 itself, so the flow takes its `likes` as they are.

use super::stubs::{CheckError, CheckResult, Checker, Hit, MarkKind, Rect, SeatMark, Slot};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, PoisonError};
use win::frame::Frame;

/// The lists a check reads, copied from the store when a check is asked for (the worker cannot borrow it).
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Lists {
    pub blacklist: Vec<lobby::Entry>,
    pub likes: Vec<lobby::Entry>,
}

pub type SharedLists = Arc<Mutex<Lists>>;

impl Lists {
    pub fn of(store: &data::store::Store) -> Lists {
        let blacklist = store
            .entries
            .iter()
            .map(|entry| lobby::Entry {
                name: entry.name.clone(),
                reason: entry.reason.clone(),
                tags: entry.tags.clone(),
                ..lobby::Entry::default()
            })
            .collect();
        let likes = store
            .likes
            .iter()
            .map(|like| lobby::Entry { name: like.name.clone(), nickname: like.nickname.clone(), ..lobby::Entry::default() })
            .collect();
        Lists { blacklist, likes }
    }
}

/// Copies the store's lists into `shared`.
pub fn share(store: &data::store::Store, shared: &SharedLists) {
    *shared.lock().unwrap_or_else(PoisonError::into_inner) = Lists::of(store);
}

/// ONNX Runtime's library (rust-switchover.md): the release's blacklist_detect\onnxruntime.dll, else one beside the
/// exe, else the system's.
pub fn ort_library(install: Option<&Path>) -> PathBuf {
    let name = if cfg!(windows) { "onnxruntime.dll" } else { "libonnxruntime.so" };
    let beside = std::env::current_exe().ok().and_then(|exe| exe.parent().map(Path::to_path_buf));
    let candidates = [install.map(|root| root.join("blacklist_detect").join(name)), beside.map(|dir| dir.join(name))];
    candidates.into_iter().flatten().find(|path| path.is_file()).unwrap_or_else(|| PathBuf::from(name))
}

/// The pipeline's checker, made at the first check.
pub struct PipelineChecker {
    pub library: PathBuf,
    pub models: Option<pipeline::ModelDirs>,
    pub threads: usize,
    pub lists: SharedLists,
    /// Where the screen copy's (0, 0) is on the virtual desktop.
    pub origin: fn() -> (i32, i32),
    /// Hears the button's box as soon as a check finds the lobby, before it reads the names.
    pub placed: Option<std::sync::mpsc::Sender<Rect>>,
    loaded: Option<pipeline::Checker>,
}

impl PipelineChecker {
    pub fn new(library: PathBuf, models: Option<pipeline::ModelDirs>, threads: usize, lists: SharedLists) -> Self {
        PipelineChecker { library, models, threads, lists, origin: desktop_origin, placed: None, loaded: None }
    }

    fn checker(&mut self) -> Result<&mut pipeline::Checker, CheckError> {
        if self.loaded.is_none() {
            let dirs = self.models.as_ref().ok_or_else(unavailable)?;
            let env = pipeline::runtime(&self.library).map_err(|_| unavailable())?;
            let made = pipeline::Checker::new(env, dirs, self.threads).map_err(|_| unavailable())?;
            self.loaded = Some(made);
        }
        self.loaded.as_mut().ok_or_else(unavailable)
    }
}

#[cfg(windows)]
fn desktop_origin() -> (i32, i32) {
    win::capture::virtual_origin()
}

#[cfg(not(windows))]
fn desktop_origin() -> (i32, i32) {
    (0, 0)
}

/// OcrUnavailable: the models or the runtime would not load.
fn unavailable() -> CheckError {
    CheckError { message: pipeline::Unavailable.to_string(), models: true, plain: true }
}

fn failed(error: pipeline::Error) -> CheckError {
    if error.downcast_ref::<pipeline::Unavailable>().is_some() {
        return unavailable();
    }
    CheckError { message: error.to_string(), models: false, plain: false }
}

fn mat(frame: &Frame) -> Result<opencv::core::Mat, CheckError> {
    pipeline::rgb_frame(frame.width as i32, frame.height as i32, &frame.rgb).map_err(failed)
}

impl PipelineChecker {
    /// The pipeline's own answer, its timings included, against no lists (环境测试).
    pub fn read_plain(&mut self, frames: &[Frame]) -> Result<pipeline::CheckResult, CheckError> {
        let mats = frames.iter().map(mat).collect::<Result<Vec<_>, _>>()?;
        self.checker()?.check(&mats, &[], &[], None).map_err(failed)
    }

    /// The next check searches for the lobby again, as a first check does.
    pub fn forget_spot(&mut self) {
        if let Some(loaded) = self.loaded.as_mut() {
            loaded.spot = None;
        }
    }
}

impl Checker for PipelineChecker {
    fn check(&mut self, frame: &Frame) -> Result<CheckResult, CheckError> {
        self.check_frames(std::slice::from_ref(frame))
    }

    fn check_frames(&mut self, frames: &[Frame]) -> Result<CheckResult, CheckError> {
        let lists = self.lists.lock().unwrap_or_else(PoisonError::into_inner).clone();
        let mats = frames.iter().map(mat).collect::<Result<Vec<_>, _>>()?;
        let origin = (self.origin)();
        let placed = self.placed.clone();
        let mut tell = move |button: lobby::PxBox| {
            if let Some(placed) = &placed {
                let _ = placed.send(desktop_rect(px(button), origin));
            }
        };
        let found = self.checker()?.check(&mats, &lists.blacklist, &lists.likes, Some(&mut tell)).map_err(failed)?;
        Ok(convert(&found, &lists, origin))
    }

    fn glance(&mut self, band: &Frame) -> Result<bool, CheckError> {
        let rgb = mat(band)?;
        let engine = &mut self.checker()?.engine;
        let (small, _) = pipeline::image::downscale(&rgb, 960).map_err(failed)?;
        let bgr = pipeline::image::to_bgr(&small).map_err(failed)?;
        let lines = engine.read_tallest_lines(&bgr, pipeline::engine::TITLE_CANDIDATES).map_err(failed)?;
        Ok(lobby::contains_title(&lines))
    }
}

/// A (left, top, right, bottom) box in the copy's pixels, on the virtual desktop.
pub fn desktop_rect(bbox: [f64; 4], (x, y): (i32, i32)) -> Rect {
    let [left, top, right, bottom] = bbox.map(|v| v.round() as i32);
    Rect { x: left + x, y: top + y, w: right - left, h: bottom - top }
}

fn px(bbox: lobby::PxBox) -> [f64; 4] {
    bbox.map(|v| v as f64)
}

/// The pipeline's answer in the flow's terms.
pub fn convert(found: &pipeline::CheckResult, lists: &Lists, origin: (i32, i32)) -> CheckResult {
    let names = found
        .names
        .iter()
        .map(|slot| Slot {
            index: slot.index,
            raw: slot.raw.clone(),
            visible: slot.visible.clone(),
            truncated: slot.truncated,
            unclear: slot.unclear,
        })
        .collect();
    let hits = found.hits.iter().map(|hit| Hit { index: hit.index, name: hit.entry_name.clone(), line: hit.line.clone() }).collect();
    let seats = found
        .seats()
        .into_iter()
        .map(|seat| {
            let (name, kind) = match seat.mark {
                pipeline::Mark::Blacklist(entry) => match lists.blacklist.get(entry) {
                    Some(listed) => (listed.name.clone(), MarkKind::Blacklist { tags: listed.tags.clone() }),
                    None => (seat.name.clone(), MarkKind::Blacklist { tags: Vec::new() }),
                },
                pipeline::Mark::Guest(entry) => match lists.likes.get(entry) {
                    Some(like) if !like.nickname.is_empty() => (like.nickname.clone(), MarkKind::Guest),
                    Some(like) => (like.name.clone(), MarkKind::Guest),
                    None => (seat.name.clone(), MarkKind::Guest),
                },
                pipeline::Mark::None => (seat.name.clone(), MarkKind::None),
            };
            SeatMark { name, rect: desktop_rect(px(seat.bbox), origin), kind }
        })
        .collect();
    let mut likes: Vec<String> = Vec::new();
    for &(_, entry) in &found.likes {
        if let Some(like) = lists.likes.get(entry) {
            if !likes.contains(&like.name) {
                likes.push(like.name.clone());
            }
        }
    }
    CheckResult {
        header_found: found.header_found,
        names,
        hits,
        button_box: found.button_box.map(|bbox| desktop_rect(px(bbox), origin)),
        game_box: found.game_box.map(|bbox| desktop_rect(bbox, origin)),
        message: found.message.clone(),
        seats,
        likes,
    }
}

/// `check <image>` (pipeline.check_image): one picture read against the 黑名单, without the window. Err: the
/// message for stderr.
pub fn check_image(image: &Path, blacklist: &[lobby::Entry], install: Option<&Path>) -> Result<pipeline::CheckResult, String> {
    use opencv::prelude::*;
    // Read by Rust and decoded from memory: imread takes no path with Chinese in it on Windows.
    let bytes = std::fs::read(image).map_err(|e| format!("读不了这张图片：{}：{e}", image.display()))?;
    let bytes = opencv::core::Vector::<u8>::from_slice(&bytes);
    let bgr = opencv::imgcodecs::imdecode(&bytes, opencv::imgcodecs::IMREAD_COLOR).map_err(|e| e.to_string())?;
    if bgr.empty() {
        return Err(format!("读不了这张图片：{}", image.display()));
    }
    let mut rgb = opencv::core::Mat::default();
    opencv::imgproc::cvt_color_def(&bgr, &mut rgb, opencv::imgproc::COLOR_BGR2RGB).map_err(|e| e.to_string())?;
    let dirs = pipeline::ModelDirs::find(&super::startup::model_roots(install)).ok_or_else(|| unavailable().message)?;
    let env = pipeline::runtime(&ort_library(install)).map_err(|e| e.to_string())?;
    let mut checker = pipeline::Checker::new(env, &dirs, common::paths::ocr_threads()).map_err(|e| e.to_string())?;
    checker.check(&[rgb], blacklist, &[], None).map_err(|e| e.to_string())
}

#[cfg(test)]
#[path = "engine_tests.rs"]
mod tests;
