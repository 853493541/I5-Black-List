//! The main thread's watch (logs.Watchdog), as a clock-driven state: beat() from the window's thread,
//! tick() from the watch's own. The stack dump to crash.log is the win crate's (faulthandler's part).

pub const BEAT_S: f64 = 2.0;
pub const DUMP_S: f64 = 30.0;
pub const QUIET_S: f64 = 10.0;
pub const ASLEEP_S: f64 = 20.0;

pub struct Watchdog {
    pub dump_after: f64,
    pub quiet_after: f64,
    pub asleep_after: f64,
    beat: f64,
    last_tick: f64,
    frozen_since: Option<f64>,
}

impl Watchdog {
    pub fn new(now: f64, dump_after: f64, quiet_after: f64, asleep_after: f64) -> Self {
        Self { dump_after, quiet_after, asleep_after, beat: now, last_tick: now, frozen_since: None }
    }

    /// On the main thread: it is answering.
    pub fn beat(&mut self, now: f64) {
        self.beat = now;
    }

    /// On the watch's thread, every period. Returns the warning to log, if any; `since` formats the
    /// local wall time the beat stopped (time.strftime("%H:%M:%S") in Python) from seconds ago.
    pub fn tick(&mut self, now: f64, since: impl Fn(f64) -> String) -> Option<String> {
        let gap = now - self.last_tick;
        self.last_tick = now;
        if gap > self.asleep_after {
            // The PC slept: nobody ran, so it is no freeze.
            self.beat = now;
            return None;
        }
        let silent = now - self.beat;
        match self.frozen_since {
            None if silent >= self.quiet_after => {
                self.frozen_since = Some(self.beat);
                Some(format!(
                    "Main thread not answering for {silent:.0} s (since {}); its stack goes to crash.log after {:.0} s.",
                    since(silent),
                    self.dump_after
                ))
            }
            Some(start) if silent < self.quiet_after => {
                self.frozen_since = None;
                Some(format!("Main thread answering again after {:.0} s.", self.beat - start))
            }
            _ => None,
        }
    }
}
