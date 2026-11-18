//! When a 场景's sound plays (ui_music.ThemeMusic): once per lobby, at the 场景's own 音量, or nothing while
//! muted. What plays goes to an [`Output`]; whether it is heard is the output's business (see `player`).

use std::collections::BTreeSet;
use std::path::{Path, PathBuf};

use crate::tunes::{render, tune_path, Clip, SAMPLE_S, SAME_LOBBY_S};

/// Where sound goes: `Some` starts it (stopping whatever played), `None` stops it.
pub trait Output {
    fn play(&mut self, clip: Option<Clip>);
}

/// A 场景's own sound as the player set it in 场景管理: their song chosen (None for the scene's own) and its 音量.
pub type SoundsOf = Box<dyn Fn(&str) -> (Option<PathBuf>, i32) + Send>;
/// Seconds on a clock that only goes forward.
pub type Clock = Box<dyn Fn() -> f64 + Send>;

type Names = BTreeSet<String>;

pub struct ThemeMusic {
    out: Box<dyn Output + Send>,
    clock: Clock,
    assets: PathBuf,
    sounds: Option<SoundsOf>,
    last_lobby: Names,
    last_at: f64,
    last_mine: Names,
    last_mine_at: f64,
    before_greeting: Option<(Names, f64, Names, f64)>,
    pub muted: bool,
}

impl ThemeMusic {
    /// assets: the folder the scenes' own tunes are in. sounds: each 场景's own sound (None: every scene plays
    /// its own at 100%).
    pub fn new(out: Box<dyn Output + Send>, clock: Clock, assets: PathBuf, sounds: Option<SoundsOf>) -> Self {
        Self {
            out,
            clock,
            assets,
            sounds,
            last_lobby: Names::new(),
            last_at: f64::NEG_INFINITY,
            last_mine: Names::new(),
            last_mine_at: f64::NEG_INFINITY,
            before_greeting: None,
            muted: false,
        }
    }

    fn own(&self, scene: &str) -> (Option<PathBuf>, i32) {
        match &self.sounds {
            Some(sounds) if !scene.is_empty() => sounds(scene),
            _ => (None, 100),
        }
    }

    /// The file a 场景's sound plays from: the player's song while it is there, else its own; None for none (经典).
    pub fn tune_of(&self, scene: &str) -> Option<PathBuf> {
        match self.own(scene).0 {
            Some(own) if own.is_file() => Some(own),
            _ => tune_path(&self.assets, scene),
        }
    }

    /// The tune for a scene: the scene's key while it has one, or "" for none.
    pub fn pick<'a>(&self, scene: &'a str) -> &'a str {
        if self.tune_of(scene).is_some() {
            scene
        } else {
            ""
        }
    }

    /// How loud a scene's sound plays, in percent: the 场景's own 音量.
    pub fn level(&self, scene: &str) -> i32 {
        self.own(scene).1
    }

    pub fn audible(&self) -> bool {
        !self.muted
    }

    fn remember(&mut self) {
        self.before_greeting = Some((self.last_lobby.clone(), self.last_at, self.last_mine.clone(), self.last_mine_at));
    }

    /// A lobby with these 嘉宾 players, greeted by this scene: its sound, unless one just greeted them. now=false:
    /// the tune that greets them, for the caller to play as its scene starts. Returns the scene played, or "".
    pub fn lobby(&mut self, likes: &[String], scene: &str, now: bool) -> String {
        if likes.is_empty() || !self.audible() {
            return String::new();
        }
        self.remember();
        let players: Names = likes.iter().cloned().collect();
        let at = (self.clock)();
        if players == self.last_lobby && at - self.last_at < SAME_LOBBY_S {
            return String::new();
        }
        self.last_lobby = players;
        self.last_at = at;
        self.greet(scene, now)
    }

    /// A lobby nobody listed is in, greeted by 我's own 场景, with these names read: its sound, unless 我's
    /// greeted the same lobby within SAME_LOBBY_S (half the names read last time read again, or either read none).
    pub fn mine(&mut self, names: &[String], scene: &str, now: bool) -> String {
        if !self.audible() {
            return String::new();
        }
        self.remember();
        let players: Names = names.iter().cloned().collect();
        let at = (self.clock)();
        let before = std::mem::replace(&mut self.last_mine, players);
        let shared = before.intersection(&self.last_mine).count();
        if at - self.last_mine_at < SAME_LOBBY_S && (before.is_empty() || self.last_mine.is_empty() || 2 * shared >= before.len()) {
            return String::new();
        }
        self.last_mine_at = at;
        self.greet(scene, now)
    }

    /// The last greeting (now=false) was never heard: checked again, that lobby is greeted as new.
    pub fn ungreet(&mut self) {
        if let Some((lobby, at, mine, mine_at)) = self.before_greeting.take() {
            (self.last_lobby, self.last_at, self.last_mine, self.last_mine_at) = (lobby, at, mine, mine_at);
        }
    }

    fn greet(&mut self, scene: &str, now: bool) -> String {
        if self.pick(scene).is_empty() || self.level(scene) <= 0 {
            return String::new();
        }
        if now {
            self.preview(scene, 0.0)
        } else {
            scene.to_string()
        }
    }

    /// A scene's sound now, with `at` from that many seconds on; with none, or muted, stop what plays.
    pub fn preview(&mut self, scene: &str, at: f64) -> String {
        let tune = self.pick(scene).to_string();
        let file = self.tune_of(&tune);
        if self.start(file.as_deref(), self.level(&tune), None, at) {
            tune
        } else {
            String::new()
        }
    }

    /// A moment of a 场景's sound as loud as it plays, for its 音量 in 场景管理.
    pub fn taste(&mut self, scene: &str) -> bool {
        let file = self.tune_of(scene);
        self.start(file.as_deref(), self.level(scene), Some(SAMPLE_S), 0.0)
    }

    /// One of a 场景's sounds whole as loud as that 场景 plays: the player's song at path, or its 默认.
    pub fn song(&mut self, scene: &str, path: Option<&Path>, at: f64) -> bool {
        let file = path.map(Path::to_path_buf).or_else(|| tune_path(&self.assets, scene));
        self.start(file.as_deref(), self.level(scene), None, at)
    }

    /// A sound not yet a 场景's (选择片段's 试听), as loud as that 场景 plays.
    pub fn trial(&mut self, path: &Path, scene: &str) -> bool {
        self.start(Some(path), self.level(scene), None, 0.0)
    }

    /// Ready samples as they are (选择片段's song from a moment on), unless muted.
    pub fn play_clip(&mut self, clip: Clip) -> bool {
        let clip = (!self.muted).then_some(clip);
        let playing = clip.is_some();
        self.out.play(clip);
        playing
    }

    fn start(&mut self, tune: Option<&Path>, volume: i32, seconds: Option<f64>, start: f64) -> bool {
        let clip = match tune {
            Some(file) if !self.muted && volume > 0 => render(file, volume, seconds, start),
            _ => None,
        };
        let playing = clip.is_some();
        self.out.play(clip);
        playing
    }

    pub fn stop(&mut self) {
        self.out.play(None);
    }
}
