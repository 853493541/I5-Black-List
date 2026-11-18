//! The look for a new version (updater.fetch_release) on a thread of its own, its answer picked up by the runner.

use super::stubs::UpdateCheck;
use data::update::fetch::{fetch_release, Http};
use data::update::{Release, UpdateError};
use std::path::PathBuf;
use std::sync::mpsc::{channel, Receiver};

/// What a look found: a newer release, none, or why it could not tell.
pub type Found = Result<Option<Release>, UpdateError>;

/// Makes the connection on the look's thread (the real one, or a fake in tests).
pub type Connect = Box<dyn Fn() -> Box<dyn Http + Send> + Send + Sync>;

pub struct NetUpdate {
    version: String,
    /// Holds mirrors.json (the data folder).
    folder: PathBuf,
    connect: std::sync::Arc<Connect>,
    running: Option<Receiver<Found>>,
}

impl NetUpdate {
    pub fn new(version: &str, folder: PathBuf, connect: Connect) -> NetUpdate {
        NetUpdate { version: version.into(), folder, connect: std::sync::Arc::new(connect), running: None }
    }

    /// The real network, as `BlackListDetect/<version>`.
    pub fn online(version: &str, folder: PathBuf) -> NetUpdate {
        let agent = version.to_string();
        NetUpdate::new(version, folder, Box::new(move || Box::new(data::update::net::Net::new(&agent))))
    }
}

impl UpdateCheck for NetUpdate {
    fn check(&mut self) -> bool {
        if self.running.is_some() {
            return false;
        }
        let (sender, answer) = channel();
        let (version, folder, connect) = (self.version.clone(), self.folder.clone(), self.connect.clone());
        let started = std::thread::Builder::new().name("UpdateCheck".into()).spawn(move || {
            let mut http = connect();
            let _ = sender.send(fetch_release(http.as_mut(), &version, &folder, None));
        });
        if started.is_err() {
            return false;
        }
        self.running = Some(answer);
        true
    }

    fn poll(&mut self) -> Option<Found> {
        let found = self.running.as_ref()?.try_recv();
        match found {
            Ok(found) => {
                self.running = None;
                Some(found)
            }
            Err(std::sync::mpsc::TryRecvError::Empty) => None,
            Err(std::sync::mpsc::TryRecvError::Disconnected) => {
                self.running = None;
                Some(Err(UpdateError::NoConnection))
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use data::update::fetch::{HttpError, Response};

    struct Missing;

    impl Http for Missing {
        fn get(&mut self, _url: &str) -> Result<Response, HttpError> {
            Ok(Response { status: 404, body: Vec::new() })
        }
        fn stream(&mut self, _url: &str, _chunk: &mut dyn FnMut(&[u8]) -> bool) -> Result<(), HttpError> {
            Err(HttpError("404".into()))
        }
    }

    fn wait(update: &mut NetUpdate) -> Found {
        for _ in 0..500 {
            if let Some(found) = update.poll() {
                return found;
            }
            std::thread::sleep(std::time::Duration::from_millis(10));
        }
        panic!("the look never answered");
    }

    #[test]
    fn one_look_at_a_time_and_no_release_is_no_offer() {
        let dir = tempfile::tempdir().unwrap();
        let mut update = NetUpdate::new("1.0.0", dir.path().to_path_buf(), Box::new(|| Box::new(Missing)));
        assert!(update.poll().is_none());
        assert!(update.check());
        assert!(!update.check(), "a second look waits for the first");
        assert_eq!(wait(&mut update), Ok(None));
        assert!(update.check(), "done: the next look may start");
        assert_eq!(wait(&mut update), Ok(None));
    }
}
