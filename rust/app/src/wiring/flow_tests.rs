//! The check flow against ui.py's behaviour, with fakes: the sample lobby as the screen, a scripted checker, the
//! real lists in a data folder of their own, and every mark, notice, scene and sound recorded instead of shown.

use super::flow::{Done, Flow, Job, Mode, Ports, Status};
use super::records::StoreRecords;
use super::stubs::*;
use super::worker::{run, Screen};
use data::store::sounds::Scenes;
use data::store::{Clock, Store};
use std::cell::RefCell;
use std::collections::VecDeque;
use std::rc::Rc;
use win::frame::Frame;

type Calls = Rc<RefCell<Vec<String>>>;

struct Fake(Calls);

impl Fake {
    fn note(&self, call: String) {
        self.0.borrow_mut().push(call);
    }
}

impl Overlay for Fake {
    fn show(&mut self, _game: Rect, result: &CheckResult, look: Look, target: Target) {
        self.note(format!("overlay {look:?} {target:?} {}", result.hits.len()));
    }
    fn hide(&mut self) {
        self.note("overlay hide".into());
    }
    fn checking(&mut self, _button: Rect) {
        self.note("overlay checking".into());
    }
}

impl Notice for Fake {
    fn show(&mut self, kind: NoticeKind) {
        self.note(format!("notice {kind:?}"));
    }
    fn hide(&mut self) {
        self.note("notice hide".into());
    }
}

impl ScenePlayer for Fake {
    fn play(&mut self, key: &str, stage: Stage) {
        self.note(format!("scene {key} {:?}", stage.target));
    }
    fn stop(&mut self) {}
}

impl Player for Fake {
    fn play_tune(&mut self, key: &str) {
        self.note(format!("tune {key}"));
    }
    fn play_alert(&mut self) {
        self.note("alert".into());
    }
    fn set_muted(&mut self, _muted: bool) {}
}

/// The sample lobby (assets/sample-lobby.jpg) as every screen.
struct SampleScreen(Frame);

fn sample() -> Frame {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/../../blacklist_detect/assets/sample-lobby.jpg");
    let picture = image::open(path).expect("sample lobby").to_rgb8();
    Frame { width: picture.width() as usize, height: picture.height() as usize, rgb: picture.into_raw() }
}

impl Screen for SampleScreen {
    fn displays(&mut self) -> Result<Vec<Frame>, CheckError> {
        Ok(vec![self.0.clone()])
    }
    fn top_band(&mut self) -> Result<Frame, CheckError> {
        Ok(self.0.clone())
    }
}

/// Answers from a script, and checks it was handed the sample frame.
struct Scripted {
    checks: VecDeque<Result<CheckResult, CheckError>>,
    glances: VecDeque<bool>,
    size: (usize, usize),
}

impl Checker for Scripted {
    fn check(&mut self, frame: &Frame) -> Result<CheckResult, CheckError> {
        assert_eq!((frame.width, frame.height), self.size);
        self.checks.pop_front().expect("a scripted check")
    }
    fn glance(&mut self, _band: &Frame) -> Result<bool, CheckError> {
        Ok(self.glances.pop_front().unwrap_or(false))
    }
}

struct Rig {
    flow: Flow,
    calls: Calls,
    store: Rc<RefCell<Store>>,
    screen: SampleScreen,
    checker: Scripted,
    _dir: tempfile::TempDir,
}

fn lobby(names: &[&str], hits: &[usize]) -> CheckResult {
    let slot = |(index, name): (usize, &&str)| Slot {
        index,
        raw: name.to_string(),
        visible: name.to_string(),
        unclear: name.is_empty(),
        ..Slot::default()
    };
    CheckResult {
        header_found: true,
        names: names.iter().enumerate().map(slot).collect(),
        hits: hits.iter().map(|&index| Hit { index, name: names[index].into(), line: String::new() }).collect(),
        button_box: Some(Rect { x: 100, y: 100, w: 800, h: 450 }),
        game_box: Some(Rect { x: 0, y: 0, w: 1920, h: 1080 }),
        message: String::new(),
        seats: Vec::new(),
        // The pipeline matches the 嘉宾: here, 心动小鹿 at a seat that is no 黑名单 player's.
        likes: names
            .iter()
            .enumerate()
            .filter(|&(index, name)| *name == "心动小鹿" && !hits.contains(&index))
            .map(|(_, name)| name.to_string())
            .take(1)
            .collect(),
    }
}

fn no_lobby() -> CheckResult {
    CheckResult { message: "没有找到大厅".into(), ..CheckResult::default() }
}

fn failed(plain: bool) -> CheckError {
    CheckError { message: if plain { "识别模型没有找到".into() } else { "OSError: [WinError 5]".into() }, models: plain, plain, step: if plain { "OCR load" } else { "read" }, ..CheckError::default() }
}

impl Rig {
    fn new(mode: Mode, checks: Vec<Result<CheckResult, CheckError>>) -> Rig {
        let dir = tempfile::tempdir().unwrap();
        let mut store = Store::open(Some(dir.path().to_path_buf()), Clock::default());
        store.add("示例坏人", "", &[]).unwrap();
        store.add_like("心动小鹿", "", "", &Scenes { keys: vec!["stars".into()], random: false }).unwrap();
        store.set_me(&Scenes { keys: Vec::new(), random: false }).unwrap();
        let store = Rc::new(RefCell::new(store));
        let calls: Calls = Rc::default();
        let ports = Ports {
            overlay: Box::new(Fake(calls.clone())),
            notice: Box::new(Fake(calls.clone())),
            scenes: Box::new(Fake(calls.clone())),
            player: Box::new(Fake(calls.clone())),
            records: Box::new(StoreRecords::new(store.clone(), 0)),
        };
        let frame = sample();
        let size = (frame.width, frame.height);
        let checker = Scripted { checks: checks.into(), glances: VecDeque::new(), size };
        Rig { flow: Flow::new(mode, ports), calls, store, screen: SampleScreen(frame), checker, _dir: dir }
    }

    /// Does a job and every job it leads to, the way the worker thread would.
    fn drive(&mut self, mut job: Option<Job>, now: f64) {
        while let Some(next) = job {
            let done = run(next, &mut self.screen, &mut self.checker);
            job = self.flow.done(done, now);
        }
    }

    fn press(&mut self, now: f64) {
        let job = self.flow.hotkey(now);
        assert_eq!(job, Some(Job::Check));
        self.drive(job, now);
    }

    fn calls(&self) -> Vec<String> {
        std::mem::take(&mut *self.calls.borrow_mut())
    }
}

fn full() -> Mode {
    Mode { auto: false, safe: false, stream: false, disclaimer: true }
}

#[test]
fn a_blacklisted_seat_gets_the_red_ring_and_the_alert() {
    let mut rig = Rig::new(full(), vec![Ok(lobby(&["示例坏人", "心动星星", ""], &[0]))]);
    rig.press(0.0);
    assert_eq!(rig.calls(), ["overlay Hit Screen 1", "alert"]);
    assert_eq!(rig.flow.status, Status::Shown(Look::Hit));
    assert_eq!(rig.store.borrow().scans.len(), 1, "the check is in 记录");
    assert!(rig.flow.log.iter().any(|line| line == "Check 1 (hotkey): 3 seats read, 1 黑名单."));
}

#[test]
fn a_guest_seat_gets_the_rose_ring_its_scene_and_music() {
    let mut rig = Rig::new(full(), vec![Ok(lobby(&["心动星星", "心动小鹿"], &[]))]);
    rig.press(0.0);
    assert_eq!(rig.calls(), ["tune stars", "overlay Liked Screen 0", "scene stars Screen"]);
    assert_eq!(rig.flow.status, Status::Shown(Look::Liked));
}

#[test]
fn blacklist_and_guest_show_both_cards_and_the_guest_still_greets() {
    let mut rig = Rig::new(full(), vec![Ok(lobby(&["示例坏人", "心动小鹿"], &[0]))]);
    rig.press(0.0);
    assert_eq!(rig.calls(), ["tune stars", "overlay Both Screen 1", "alert", "scene stars Screen"]);
}

#[test]
fn the_same_lobby_checked_again_does_not_replay_its_scene() {
    let checks = vec![Ok(lobby(&["心动小鹿"], &[])), Ok(lobby(&["心动小鹿", "心动星星"], &[]))];
    let mut rig = Rig::new(full(), checks);
    rig.press(0.0);
    rig.calls();
    rig.press(10.0);
    // The marks turn into 检查中 while it reads, then back: no tune, no scene again.
    assert_eq!(rig.calls(), ["overlay checking", "overlay Liked Screen 0"]);
}

#[test]
fn nobody_listed_shows_the_plain_ring() {
    let mut rig = Rig::new(full(), vec![Ok(lobby(&["心动星星"], &[]))]);
    rig.press(0.0);
    assert_eq!(rig.calls(), ["overlay Clear Screen 0"]);
}

#[test]
fn a_failed_check_looks_twice_then_says_check_failed() {
    let mode = Mode { safe: true, ..full() };
    let mut rig = Rig::new(mode, vec![Err(failed(false)), Err(failed(false))]);
    rig.press(0.0);
    let calls = rig.calls();
    assert_eq!(calls.iter().filter(|call| *call == "notice Checking").count(), 1, "the second look is quiet");
    assert_eq!(calls.last().unwrap(), "notice Failed(\"等会儿再试\")", "a library's message is not shown");
    assert_eq!(rig.flow.status, Status::Failed("OSError: [WinError 5]".into()));
    assert!(rig.checker.checks.is_empty(), "exactly one second look");
}

#[test]
fn a_plain_failure_is_shown_as_it_is() {
    let mode = Mode { safe: true, ..full() };
    let mut rig = Rig::new(mode, vec![Err(failed(true)), Err(failed(true))]);
    rig.press(0.0);
    assert_eq!(rig.calls().last().unwrap(), "notice Failed(\"识别模型没有找到\")");
}

#[test]
fn a_frame_without_a_lobby_says_so_after_a_second_look() {
    let mut rig = Rig::new(full(), vec![Ok(no_lobby()), Ok(no_lobby())]);
    rig.press(0.0);
    assert_eq!(rig.calls(), ["overlay hide", "notice Missing"]);
    assert_eq!(rig.flow.status, Status::NoLobby);
    assert!(rig.store.borrow().scans.is_empty(), "nothing in 记录");
}

#[test]
fn a_second_look_that_finds_the_lobby_shows_it() {
    let mut rig = Rig::new(full(), vec![Ok(no_lobby()), Ok(lobby(&["示例坏人"], &[0]))]);
    rig.press(0.0);
    assert_eq!(rig.calls(), ["overlay Hit Screen 1", "alert"]);
    assert_eq!(rig.flow.check_number, 1, "the second look is the same check");
}

#[test]
fn basic_mode_shows_the_corner_message_and_nothing_over_the_game() {
    let mode = Mode { safe: true, ..full() };
    let mut rig = Rig::new(mode, vec![Ok(lobby(&["示例坏人", ""], &[0]))]);
    rig.press(0.0);
    assert_eq!(rig.calls(), ["notice Checking", "notice Result { hits: 1, unclear: 1 }"]);
}

#[test]
fn basic_mode_with_stream_mode_draws_only_into_the_stream() {
    let mode = Mode { safe: true, stream: true, ..full() };
    let mut rig = Rig::new(mode, vec![Ok(lobby(&["示例坏人"], &[0]))]);
    rig.press(0.0);
    assert!(rig.calls().contains(&"overlay Hit Stream 1".to_string()));
}

#[test]
fn no_check_before_the_disclaimer_nor_while_one_runs() {
    let mut rig = Rig::new(Mode { disclaimer: false, ..full() }, vec![]);
    assert_eq!(rig.flow.hotkey(0.0), None);
    assert!(rig.flow.log.iter().any(|line| line == "Hotkey: 使用声明 not agreed to yet, no check."));
    assert!(!rig.flow.log.iter().any(|line| line.contains("busy")), "{:?}", rig.flow.log);
    rig.flow.mode.disclaimer = true;
    assert_eq!(rig.flow.hotkey(0.0), Some(Job::Check));
    assert_eq!(rig.flow.hotkey(0.1), None, "busy: the press is ignored");
    assert!(rig.flow.log.iter().any(|line| line == "Hotkey: busy, the press was ignored."));
}

#[test]
fn auto_checks_once_per_appearance_of_the_lobby() {
    let mode = Mode { auto: true, ..full() };
    let mut rig = Rig::new(mode, vec![Ok(lobby(&["示例坏人"], &[0])), Ok(lobby(&["心动星星"], &[]))]);
    let glance = |rig: &mut Rig, seen: bool, now: f64| {
        assert_eq!(rig.flow.tick(now), Some(Job::Glance));
        let job = rig.flow.done(Done::Glanced(Ok(seen)), now);
        rig.drive(job, now);
    };
    glance(&mut rig, true, 0.4);
    assert_eq!(rig.flow.check_number, 1);
    assert!(rig.flow.log.iter().any(|line| line == "Check 1 (auto): 1 seats read, 1 黑名单."));
    glance(&mut rig, true, 0.8);
    rig.calls();
    glance(&mut rig, false, 1.2);
    assert_eq!(rig.calls(), ["overlay hide"], "the title went: the marks come down at once");
    glance(&mut rig, true, 1.6);
    assert_eq!(rig.flow.check_number, 1, "a blink is the same lobby: not checked again");
    glance(&mut rig, false, 2.0);
    glance(&mut rig, false, 3.0);
    glance(&mut rig, true, 3.4);
    assert_eq!(rig.flow.check_number, 2, "a new lobby is checked");
}

#[test]
fn a_failed_glance_pauses_the_watch() {
    let mut rig = Rig::new(Mode { auto: true, ..full() }, vec![]);
    assert_eq!(rig.flow.tick(0.0), Some(Job::Glance));
    rig.flow.done(Done::Glanced(Err(failed(true))), 0.0);
    assert_eq!(rig.flow.tick(14.9), None, "a missing model is not reloaded every 0.4 s");
    assert_eq!(rig.flow.tick(15.0), Some(Job::Glance));
}

#[test]
fn manual_mode_does_not_glance_without_marks() {
    let mut rig = Rig::new(full(), vec![Ok(lobby(&["示例坏人"], &[0]))]);
    assert_eq!(rig.flow.tick(0.0), None);
    rig.press(0.0);
    assert_eq!(rig.flow.tick(0.4), Some(Job::Glance), "marks are up: glance to take them down");
}

#[test]
fn switching_to_basic_mode_takes_the_marks_off() {
    let mut rig = Rig::new(full(), vec![Ok(lobby(&["示例坏人"], &[0]))]);
    rig.press(0.0);
    rig.calls();
    rig.flow.set_mode(Mode { safe: true, ..full() });
    assert_eq!(rig.calls(), ["overlay hide"]);
    assert!(!rig.flow.watching());
}

#[test]
fn checking_shows_on_the_button_once_the_lobby_is_placed_and_on_marks_already_up() {
    let mut rig = Rig::new(full(), vec![Ok(lobby(&["示例坏人"], &[0])), Ok(lobby(&["示例坏人"], &[0]))]);
    let button = Rect { x: 100, y: 100, w: 800, h: 450 };
    rig.flow.lobby_placed(button);
    assert!(rig.calls().is_empty(), "no check runs: nothing to place");
    rig.press(0.0);
    rig.calls();
    let job = rig.flow.hotkey(1.0);
    assert_eq!(rig.calls(), ["overlay checking"], "the marks up turn into 检查中 at once");
    rig.flow.lobby_placed(button);
    assert_eq!(rig.calls(), ["overlay checking"]);
    rig.drive(job, 1.0);
    assert_eq!(rig.calls(), ["overlay Hit Screen 1", "alert"]);
}

#[test]
fn the_scene_hotkey_plays_over_the_last_lobby_and_ends_on_its_own() {
    let mut rig = Rig::new(Mode { disclaimer: false, ..full() }, Vec::new());
    let screen = Rect { x: 0, y: 0, w: 1920, h: 1080 };
    assert!(!rig.flow.quick_play("stars", screen, 0.0), "not before 使用声明");
    rig.flow.set_mode(full());
    rig.calls();
    assert!(rig.flow.quick_play("stars", screen, 0.0));
    assert_eq!(rig.calls(), ["tune stars", "overlay Liked Screen 0", "scene stars Screen"]);
    rig.flow.tick(stage::clock::duration("stars") + 0.1);
    assert_eq!(rig.calls(), ["overlay hide"]);
}

// The header pill (ui.py _report_problem / _clear_problem): every failed check says so in 完整模式 too.

fn capture_failed() -> CheckError {
    CheckError { message: "截图失败，再试一次".into(), plain: true, capture: true, step: "capture", ..CheckError::default() }
}

fn label(rig: &Rig) -> Option<(&str, String)> {
    rig.flow.problem.as_ref().map(|problem| (problem.label.as_str(), problem.tip.clone()))
}

#[test]
fn a_failed_check_in_full_mode_puts_check_failed_in_the_pill() {
    let mut rig = Rig::new(full(), vec![Err(failed(false)), Err(failed(false))]);
    rig.press(0.0);
    assert_eq!(label(&rig), Some(("检查失败：读名字", "检查失败，等会儿再试".to_string())), "never silent in 完整模式");
    assert!(rig.flow.log.iter().any(|line| line == "检查失败：读名字 (step: read): OSError: [WinError 5]"), "{:?}", rig.flow.log);
}

#[test]
fn missing_models_say_recognition_is_not_ready() {
    let mut rig = Rig::new(full(), vec![Err(failed(true)), Err(failed(true))]);
    rig.press(0.0);
    assert_eq!(label(&rig), Some(("识别还没准备好", "识别模型没有找到".to_string())));
}

#[test]
fn a_failed_screen_copy_says_the_screen_cannot_be_read() {
    let mut rig = Rig::new(full(), vec![Err(capture_failed()), Err(capture_failed())]);
    rig.press(0.0);
    assert_eq!(label(&rig), Some(("读不到屏幕", "截图失败，再试一次".to_string())));
}

#[test]
fn a_failed_glance_says_so_and_a_good_one_clears_it() {
    let mut rig = Rig::new(Mode { auto: true, ..full() }, vec![]);
    rig.flow.tick(0.0);
    rig.flow.done(Done::Glanced(Err(capture_failed())), 0.0);
    assert_eq!(label(&rig).map(|(label, _)| label), Some("读不到屏幕"));
    rig.flow.tick(5.0);
    rig.flow.done(Done::Glanced(Ok(false)), 5.0);
    assert_eq!(rig.flow.problem, None, "back to 自动检查中");
    assert!(rig.flow.log.iter().any(|line| line == "Checks work again."));
}

#[test]
fn a_check_that_reads_the_lobby_clears_the_problem() {
    let mut rig = Rig::new(full(), vec![Err(failed(false)), Err(failed(false)), Ok(lobby(&["示例坏人"], &[0]))]);
    rig.press(0.0);
    assert!(rig.flow.problem.is_some());
    rig.press(1.0);
    assert_eq!(rig.flow.problem, None, "back to 手动检查");
}

#[test]
fn the_same_problem_is_logged_once() {
    let mut rig = Rig::new(full(), vec![Err(failed(false)), Err(failed(false)), Err(failed(false)), Err(failed(false))]);
    rig.press(0.0);
    rig.press(1.0);
    assert_eq!(rig.flow.log.iter().filter(|line| line.starts_with("检查失败：读名字 (step: read)")).count(), 1);
}

#[test]
fn no_lobby_leaves_the_pill_as_it_was_and_shows_the_corner_message() {
    let mut rig = Rig::new(full(), vec![Ok(no_lobby()), Ok(no_lobby())]);
    rig.press(0.0);
    assert_eq!(rig.flow.problem, None);
    assert!(rig.calls().iter().any(|call| *call == "notice Missing"), "没有找到大厅 in 完整模式 too");
}

struct Panics;

impl Checker for Panics {
    fn check(&mut self, _frame: &Frame) -> Result<CheckResult, CheckError> {
        panic!("onnxruntime.dll would not load")
    }
    fn glance(&mut self, _band: &Frame) -> Result<bool, CheckError> {
        panic!("onnxruntime.dll would not load")
    }
}

#[test]
fn a_panic_in_a_check_is_check_failed_not_silence() {
    let mut rig = Rig::new(full(), vec![]);
    let done = run(Job::Check, &mut rig.screen, &mut Panics);
    let Done::Checked(Err(error)) = &done else { panic!("{done:?}") };
    assert_eq!(error.detail, "panic: onnxruntime.dll would not load");
    assert_eq!(rig.flow.hotkey(0.0), Some(Job::Check));
    let again = rig.flow.done(done, 0.0);
    assert_eq!(again, Some(Job::Check), "one second look");
    rig.flow.done(run(Job::Check, &mut rig.screen, &mut Panics), 0.0);
    assert_eq!(label(&rig).map(|(label, _)| label), Some("检查失败：程序出错"));
    assert!(!rig.flow.busy(), "the next press checks again");
    assert_eq!(rig.flow.hotkey(1.0), Some(Job::Check));
}

#[test]
fn the_worker_thread_lives_through_a_panic() {
    let worker = super::worker::Worker::start(Box::new(SampleScreen(sample())), Box::new(Panics));
    for _ in 0..2 {
        worker.request(Job::Check);
        let done = worker.results.recv_timeout(std::time::Duration::from_secs(20)).expect("an answer, not silence");
        assert!(matches!(done, Done::Checked(Err(_))), "{done:?}");
    }
}

#[test]
fn a_read_lobby_is_written_to_the_history_and_says_so() {
    let mut rig = Rig::new(full(), vec![Ok(lobby(&["示例坏人", "心动小鹿"], &[0]))]);
    rig.press(0.0);
    assert_eq!(rig.store.borrow().scans.len(), 1, "a 记录 entry after the check");
    assert!(rig.flow.log.iter().any(|line| line == "Check 1: 记录 added."), "{:?}", rig.flow.log);
    assert_eq!(rig.flow.problem, None);
}

#[test]
fn a_history_that_cannot_be_written_says_so_in_the_pill() {
    let mut rig = Rig::new(full(), vec![Ok(lobby(&["示例坏人"], &[0]))]);
    let history = rig.store.borrow().history_path();
    std::fs::create_dir_all(&history).unwrap(); // a folder where the file goes: the write fails
    rig.press(0.0);
    assert_eq!(label(&rig).map(|(label, _)| label), Some("检查失败：记录没存上"));
    assert!(rig.flow.log.iter().any(|line| line == "Check 1: 记录 unsaved."), "{:?}", rig.flow.log);
}
