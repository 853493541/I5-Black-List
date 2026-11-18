//! Before this copy opens its window: does another copy answer, and is one stuck? (single.settle)

use std::time::Duration;

/// What settle needs from the system, so the decision is tested without processes.
pub trait Host {
    /// Whether the open copy answered on its pipe (and was asked to show itself).
    fn answers(&mut self) -> bool;
    /// Other processes running this folder's copy of the app.
    fn copies(&mut self) -> Vec<u32>;
    /// Write a dump of a stuck copy; its file name, or why not.
    fn dump(&mut self, pid: u32) -> Result<String, String>;
    /// End these processes; the ones ended.
    fn end(&mut self, pids: &[u32]) -> Vec<u32>;
    /// Time since an arbitrary start.
    fn now(&mut self) -> Duration;
    fn sleep(&mut self, time: Duration);
    fn warn(&mut self, _message: &str) {}
}

pub const WAIT_OTHER_OWNS: Duration = Duration::from_secs(8);
pub const WAIT_FIRST: Duration = Duration::from_secs(3);
const STEP: Duration = Duration::from_millis(250);

/// True when another copy answered (this one should leave). `first` is whether this start owns the mutex.
/// A copy that holds the mutex but does not answer may still be starting, so it gets a few seconds; a
/// copy from this folder that never answers is stuck: it is dumped, then ended.
pub fn settle(host: &mut impl Host, first: bool, wait: Duration) -> bool {
    if host.answers() {
        return true;
    }
    if first && host.copies().is_empty() {
        return false;
    }
    let deadline = host.now() + if first { WAIT_FIRST } else { wait };
    while host.now() < deadline {
        host.sleep(STEP);
        if host.answers() {
            return true;
        }
    }
    let stuck = host.copies();
    if !stuck.is_empty() {
        let mut dumps = Vec::new();
        for &pid in &stuck {
            match host.dump(pid) {
                Ok(name) => dumps.push(name),
                Err(error) => host.warn(&format!("Could not write a dump of the copy {pid} that does not answer: {error}")),
            }
        }
        let ended = host.end(&stuck);
        let written = if dumps.is_empty() { "no dump".to_string() } else { dumps.join(", ") };
        host.warn(&format!("A copy was open but its pipe did not answer; wrote {written}; ended it: {ended:?}"));
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Default)]
    struct Fake {
        answer_on: Option<usize>,
        asked: usize,
        copies: Vec<u32>,
        dump_fails: bool,
        dumped: Vec<u32>,
        ended: Vec<u32>,
        clock: Duration,
    }

    impl Host for Fake {
        fn answers(&mut self) -> bool {
            self.asked += 1;
            self.answer_on.is_some_and(|n| self.asked >= n)
        }
        fn copies(&mut self) -> Vec<u32> {
            self.copies.clone()
        }
        fn dump(&mut self, pid: u32) -> Result<String, String> {
            self.dumped.push(pid);
            if self.dump_fails { Err("denied".into()) } else { Ok(format!("stuck-{pid}.dmp")) }
        }
        fn end(&mut self, pids: &[u32]) -> Vec<u32> {
            self.ended.extend(pids);
            self.copies.clear();
            pids.to_vec()
        }
        fn now(&mut self) -> Duration {
            self.clock
        }
        fn sleep(&mut self, time: Duration) {
            self.clock += time;
        }
    }

    #[test]
    fn the_only_copy_opens_at_once() {
        let mut host = Fake::default();
        assert!(!settle(&mut host, true, WAIT_OTHER_OWNS));
        assert_eq!((host.asked, host.clock), (1, Duration::ZERO));
    }

    #[test]
    fn a_copy_that_never_answers_is_dumped_then_ended() {
        let mut host = Fake { copies: vec![42], ..Fake::default() };
        assert!(!settle(&mut host, true, WAIT_OTHER_OWNS));
        assert_eq!((host.dumped.as_slice(), host.ended.as_slice()), (&[42][..], &[42][..]));
        assert_eq!(host.clock, WAIT_FIRST);
    }

    #[test]
    fn a_dump_that_fails_still_ends_the_copy() {
        let mut host = Fake { copies: vec![7], dump_fails: true, ..Fake::default() };
        assert!(!settle(&mut host, false, WAIT_OTHER_OWNS));
        assert_eq!(host.ended, vec![7]);
        assert_eq!(host.clock, WAIT_OTHER_OWNS);
    }

    #[test]
    fn a_copy_that_answers_is_left_alone() {
        let mut host = Fake { copies: vec![9], answer_on: Some(1), ..Fake::default() };
        assert!(settle(&mut host, false, WAIT_OTHER_OWNS));
        assert!(host.ended.is_empty());
    }

    #[test]
    fn a_copy_still_starting_gets_time_to_answer() {
        let mut host = Fake { copies: vec![9], answer_on: Some(4), ..Fake::default() };
        assert!(settle(&mut host, false, WAIT_OTHER_OWNS));
        assert_eq!(host.asked, 4);
        assert!(host.ended.is_empty() && host.dumped.is_empty());
    }

    #[test]
    fn another_start_holding_the_mutex_with_no_copy_here_waits_then_opens() {
        let mut host = Fake::default();
        assert!(!settle(&mut host, false, WAIT_OTHER_OWNS));
        assert!(host.ended.is_empty());
        assert_eq!(host.asked, 1 + (WAIT_OTHER_OWNS.as_millis() / STEP.as_millis()) as usize);
    }
}
