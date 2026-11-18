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
    CheckError { message: format!("截图失败：{error:?}"), models: false, plain: true }
}

#[cfg(not(windows))]
impl Screen for RealScreen {
    fn displays(&mut self) -> Result<Vec<Frame>, CheckError> {
        Err(CheckError { message: "这台电脑不能截图".into(), models: false, plain: true })
    }
    fn top_band(&mut self) -> Result<Frame, CheckError> {
        self.displays().map(|_| Frame { width: 0, height: 0, rgb: Vec::new() })
    }
}

/// One job, done here and now (the worker thread's body; the tests call it straight).
pub fn run(job: Job, screen: &mut dyn Screen, checker: &mut dyn Checker) -> Done {
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
    pub results: Receiver<Done>,
    thread: Option<JoinHandle<()>>,
}

impl Worker {
    pub fn start(mut screen: Box<dyn Screen>, mut checker: Box<dyn Checker>) -> Worker {
        let (jobs, inbox) = channel::<Job>();
        let (outbox, results) = channel::<Done>();
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
        Worker { jobs: Some(jobs), results, thread }
    }

    pub fn request(&self, job: Job) {
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
