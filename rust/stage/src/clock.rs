//! LoveBorder's lifecycle without a window: play, the 33 ms tick, the scene's clock, stop.
//!
//! Time is given in seconds by the caller (a monotonic clock in the app, made-up times in tests), and
//! the window follows what each call returns: show on Started, draw the frame at t, hide on Stopped
//! or Dropped. A scene whose pictures take a while (演说家遇袭, 竖琴清风) has them made first; the caller
//! makes them off the screen's thread and says whether they are done, and the scene starts once they are.

use crate::geom::{Placement, Stage};
use crate::pick::Picker;

/// The tick: about 30 frames a second.
pub const TICK_MS: u64 = 33;
/// How long play waits for pictures made already (or nearly): this soon, it starts at once.
pub const READY_S: f64 = 0.02;

/// Scenes whose pictures are made before their first frame (paint.warm in Python).
pub const WARMED: [&str; 2] = ["claw", "lyre"];

/// The scene's length in seconds (each module's DURATION).
pub fn duration(scene: &str) -> f64 {
    match scene {
        "classic" => 4.4,
        "lace" => 4.6,
        "claw" => 6.6,
        _ => 5.0,
    }
}

/// What play did.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Play {
    /// The choice plays none (不放): nothing shows.
    Off,
    /// Its clock started: show the window and its first frame now (the music hangs on it).
    Started,
    /// Its pictures are being made: it starts on a later tick.
    Waiting,
}

/// What one tick asks of the window.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Tick {
    /// Nothing plays.
    Idle,
    /// Still making the pictures: nothing shows yet.
    Waiting,
    /// Draw the scene at t seconds; started: its clock started on this tick (show the window).
    Frame { t: f64, started: bool },
    /// The scene ran its length: hide the window.
    Stopped,
}

#[derive(Clone, Copy, Debug, PartialEq)]
enum State {
    Idle,
    Warming,
    Playing { since: f64 },
}

/// One border window's player: what it plays, where, and since when.
pub struct Player {
    pub picker: Picker,
    /// The scene playing or played last.
    pub scene: String,
    stage: Stage,
    state: State,
}

impl Player {
    pub fn new(seed: u32) -> Self {
        Self { picker: Picker::new(seed), scene: "classic".into(), stage: Stage::new(0.0, 0.0, [0.0; 4]), state: State::Idle }
    }

    /// Cover the game's screen and play, leaving the button and its marks bare. ready: for a scene in
    /// WARMED, whether its pictures were done within READY_S; ignored for the others.
    pub fn play(&mut self, now: f64, place: &Placement, ready: bool) -> Play {
        let scene = self.picker.pick();
        if scene.is_empty() {
            return Play::Off;
        }
        self.picker.last.clone_from(&scene);
        self.stage = place.stage();
        let warms = WARMED.contains(&scene.as_str());
        self.scene = scene;
        if warms && !ready {
            self.state = State::Warming;
            return Play::Waiting;
        }
        self.state = State::Playing { since: now };
        Play::Started
    }

    /// Where it plays, in the window's own points.
    pub fn stage(&self) -> &Stage {
        &self.stage
    }

    /// Its pictures are being made: it starts once they are.
    pub fn waiting(&self) -> bool {
        self.state == State::Warming
    }

    pub fn playing(&self) -> bool {
        self.state != State::Idle
    }

    /// Seconds since its clock started; 0 before.
    pub fn elapsed(&self, now: f64) -> f64 {
        match self.state {
            State::Playing { since } => now - since,
            _ => 0.0,
        }
    }

    /// One 33 ms tick. warmed: the pictures being made are done (only read while waiting).
    pub fn tick(&mut self, now: f64, warmed: bool) -> Tick {
        match self.state {
            State::Idle => Tick::Idle,
            State::Warming if warmed => {
                self.state = State::Playing { since: now };
                Tick::Frame { t: 0.0, started: true }
            }
            State::Warming => Tick::Waiting,
            State::Playing { since } if now - since >= duration(&self.scene) => {
                self.state = State::Idle;
                Tick::Stopped
            }
            State::Playing { since } => Tick::Frame { t: now - since, started: false },
        }
    }

    /// Stop now. True when it was stopped while its pictures were being made, before it ever showed
    /// (LoveBorder.dropped).
    pub fn stop(&mut self) -> bool {
        let never_shown = self.waiting();
        self.state = State::Idle;
        never_shown
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::pick::Choice;

    fn place() -> Placement {
        Placement { area: [0, 0, 1920, 1080], keep_clear: [812, 970, 300, 90], ..Default::default() }
    }

    #[test]
    fn plays_once_for_its_length_then_stops() {
        let mut p = Player::new(1);
        p.picker.choice = Choice::One("stars".into());
        assert_eq!(p.play(10.0, &place(), false), Play::Started);
        assert_eq!(p.tick(10.033, false), Tick::Frame { t: 10.033 - 10.0, started: false });
        assert!(matches!(p.tick(14.99, false), Tick::Frame { .. }));
        assert_eq!(p.tick(15.0, false), Tick::Stopped);
        assert_eq!(p.tick(15.033, false), Tick::Idle);
        assert!(!p.playing());
    }

    #[test]
    fn off_plays_nothing() {
        let mut p = Player::new(1);
        p.picker.choice = Choice::One("off".into());
        assert_eq!(p.play(0.0, &place(), true), Play::Off);
        assert_eq!(p.tick(0.1, false), Tick::Idle);
    }

    #[test]
    fn a_warmed_scene_waits_for_its_pictures_and_drops_if_stopped() {
        let mut p = Player::new(1);
        p.picker.choice = Choice::One("lyre".into());
        assert_eq!(p.play(0.0, &place(), false), Play::Waiting);
        assert_eq!(p.tick(0.033, false), Tick::Waiting);
        assert_eq!(p.elapsed(0.5), 0.0);
        assert_eq!(p.tick(0.5, true), Tick::Frame { t: 0.0, started: true });
        assert_eq!(p.elapsed(1.0), 0.5);
        assert!(!p.stop(), "it showed, so it is not dropped");
        assert_eq!(p.play(2.0, &place(), false), Play::Waiting);
        assert!(p.stop(), "stopped before it ever showed");
        // Made already: it starts at once.
        assert_eq!(p.play(3.0, &place(), true), Play::Started);
    }

    #[test]
    fn played_scene_is_the_last_one() {
        let mut p = Player::new(3);
        p.picker.choice = Choice::Some(vec!["stars".into(), "ice".into()]);
        p.play(0.0, &place(), true);
        let first = p.scene.clone();
        p.stop();
        p.picker.draw_again();
        p.play(1.0, &place(), true);
        assert_ne!(p.scene, first);
    }
}
