//! The worker thread (CheckWorker): one job at a time, the screen copied and read off the window's thread.

use super::flow::{Done, Job};
use super::stubs::{CheckError, CheckResult, Checker};
use std::sync::mpsc::{channel, Receiver, Sender};
use std::thread::JoinHandle;
use win::frame::Frame;

/// Where the pictures come from: the real screens, or a fixed frame in tests.
pub trait Screen: Send {
    /// Every display (capture.capture_displays).
    fn displays(&mut self) -> Result<Vec<Frame>, CheckError>;
    /// The top band of the screens, where 推演成功 shows (capture.capture_top_band).
    fn top_band(&mut self) -> Result<Frame, CheckError>;
}

/// The screens of this PC. Off Windows there is nothing to copy.
pub struct RealScreen;

#[cfg(windows)]
impl Screen for RealScreen {
    fn displays(&mut self) -> Result<Vec<Frame>, CheckError> {
        win::capture::capture_displays().map_err(capture_failed)
    }
    fn top_band(&mut self) -> Result<Frame, CheckError> {
        win::capture::capture_top_band().map_err(capture_failed)
    }
}

#[cfg(windows)]
fn capture_failed(error: win::capture::CaptureError) -> CheckError {
    CheckError { message: "截图失败，再试一次".into(), plain: true, capture: true, detail: format!("{error:?}"), step: "capture", ..CheckError::default() }
}

#[cfg(not(windows))]
impl Screen for RealScreen {
    fn displays(&mut self) -> Result<Vec<Frame>, CheckError> {
        Err(CheckError { message: "这台电脑不能截图".into(), plain: true, capture: true, step: "capture", ..CheckError::default() })
    }
    fn top_band(&mut self) -> Result<Frame, CheckError> {
        self.displays().map(|_| Frame { width: 0, height: 0, rgb: Vec::new() })
    }
}

/// One job, done here and now (the worker thread's body; the tests call it straight). A panic under it is an answer
/// too, 检查失败: a worker thread that dies leaves every later press "busy" and the player sees nothing at all.
pub fn run(job: Job, screen: &mut dyn Screen, checker: &mut dyn Checker) -> Done {
    let ran = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| run_job(job, &mut *screen, &mut *checker)));
    ran.unwrap_or_else(|panic| {
        let error = CheckError { message: "检查失败".into(), detail: format!("panic: {}", panic_text(&*panic)), step: "crash", ..CheckError::default() };
        match job {
            Job::Glance => Done::Glanced(Err(error)),
            Job::Check => Done::Checked(Err(error)),
        }
    })
}

/// What a panic said.
pub fn panic_text(panic: &(dyn std::any::Any + Send)) -> String {
    panic
        .downcast_ref::<&str>()
        .map(|text| text.to_string())
        .or_else(|| panic.downcast_ref::<String>().cloned())
        .unwrap_or_else(|| "(no message)".into())
}

fn run_job(job: Job, screen: &mut dyn Screen, checker: &mut dyn Checker) -> Done {
    match job {
        Job::Glance => Done::Glanced(screen.top_band().and_then(|band| checker.glance(&band))),
        Job::Check => Done::Checked(screen.displays().and_then(|frames| check_frames(&frames, checker))),
    }
}

/// Each screen in turn: the first with a lobby wins, else the last answer (pipeline.check_frames).
pub fn check_frames(frames: &[Frame], checker: &mut dyn Checker) -> Result<CheckResult, CheckError> {
    checker.check_frames(frames)
}

/// The thread: jobs in, results out. The window's timer drains `results`.
pub struct Worker {
    jobs: Option<Sender<Job>>,
    /// The thread could not start: each job is answered 检查失败 at once.
    no_thread: Option<Sender<Done>>,
    pub results: Receiver<Done>,
    thread: Option<JoinHandle<()>>,
}

impl Worker {
    pub fn start(mut screen: Box<dyn Screen>, mut checker: Box<dyn Checker>) -> Worker {
        let (jobs, inbox) = channel::<Job>();
        let (outbox, results) = channel::<Done>();
        let answer = outbox.clone();
        let thread = std::thread::Builder::new()
            .name("CheckWorker".into())
            .spawn(move || {
                for job in inbox {
                    if outbox.send(run(job, screen.as_mut(), checker.as_mut())).is_err() {
                        break;
                    }
                }
            })
            .ok();
        let no_thread = thread.is_none().then_some(answer);
        Worker { jobs: Some(jobs), no_thread, results, thread }
    }

    pub fn request(&self, job: Job) {
        let error = || CheckError { message: "检查失败".into(), detail: "the check thread did not start".into(), step: "worker", ..CheckError::default() };
        if let Some(outbox) = &self.no_thread {
            let _ = outbox.send(match job {
                Job::Glance => Done::Glanced(Err(error())),
                Job::Check => Done::Checked(Err(error())),
            });
            return;
        }
        if let Some(jobs) = &self.jobs {
            let _ = jobs.send(job);
        }
    }

    /// Stop taking jobs and wait for the one running: ending the thread under a check crashes on exit.
    pub fn stop(&mut self) {
        self.jobs = None;
        if let Some(thread) = self.thread.take() {
            let _ = thread.join();
        }
    }
}

impl Drop for Worker {
    fn drop(&mut self) {
        self.stop();
    }
}
