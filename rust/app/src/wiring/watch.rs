//! 自动检查's trigger (watch.py LobbyWatch): fire once when 推演成功 appears, then wait until it has really left.
//! A blink of the title does not start another check; the title has to stay gone for a second.

/// How often the top band is glanced at, in ms (watch.GLANCE_INTERVAL_MS).
pub const GLANCE_INTERVAL_MS: u64 = 400;
/// After a check that never started or found nothing: try again this long after (RETRY_COOLDOWN_S).
pub const RETRY_COOLDOWN_S: f64 = 1.0;
const CLAIM_S: f64 = 30.0;
const ABSENCE_S: f64 = 1.0;

#[derive(Debug, Clone, PartialEq)]
pub struct LobbyWatch {
    pub cooldown: f64,
    held: bool,
    next: f64,
    gone_at: Option<f64>,
}

impl Default for LobbyWatch {
    fn default() -> Self {
        Self { cooldown: RETRY_COOLDOWN_S, held: false, next: 0.0, gone_at: None }
    }
}

impl LobbyWatch {
    pub fn wants_check(&mut self, present: bool, now: f64) -> bool {
        if !present {
            if self.held {
                match self.gone_at {
                    None => self.gone_at = Some(now),
                    Some(gone) if now - gone >= ABSENCE_S => {
                        self.held = false;
                        self.next = 0.0;
                        self.gone_at = None;
                    }
                    Some(_) => {}
                }
            }
            return false;
        }
        self.gone_at = None;
        !(self.held || now < self.next)
    }

    /// Hold the trigger until the check reports back.
    pub fn arm(&mut self, now: f64) {
        self.next = now + CLAIM_S;
    }

    /// This appearance was already checked. Wait until the title leaves.
    pub fn hold(&mut self) {
        self.held = true;
        self.gone_at = None;
    }

    /// The check never started. Try once the cooldown has passed.
    pub fn retry_after(&mut self, now: f64) {
        self.held = false;
        self.gone_at = None;
        self.next = now + self.cooldown;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // The same steps as tests/test_watch.py walks LobbyWatch through.
    #[test]
    fn fires_once_then_waits_for_the_title_to_leave() {
        let mut watch = LobbyWatch::default();
        assert!(watch.wants_check(true, 0.0));
        watch.arm(0.0);
        assert!(!watch.wants_check(true, 0.4), "armed: no second check while the first runs");
        watch.hold();
        assert!(!watch.wants_check(true, 5.0), "held while the title stays");
        assert!(!watch.wants_check(false, 5.4));
        assert!(!watch.wants_check(true, 5.8), "a blink does not count as leaving");
        assert!(!watch.wants_check(false, 6.2));
        assert!(!watch.wants_check(false, 7.2), "gone a full second: released");
        assert!(watch.wants_check(true, 7.6));
    }

    #[test]
    fn retry_waits_the_cooldown() {
        let mut watch = LobbyWatch::default();
        watch.arm(0.0);
        watch.retry_after(2.0);
        assert!(!watch.wants_check(true, 2.5));
        assert!(watch.wants_check(true, 3.0));
    }

    #[test]
    fn claim_runs_out_after_thirty_seconds() {
        let mut watch = LobbyWatch::default();
        watch.arm(0.0);
        assert!(!watch.wants_check(true, 29.9));
        assert!(watch.wants_check(true, 30.0));
    }
}
