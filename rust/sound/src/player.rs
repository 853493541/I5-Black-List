//! The app's sound, as the app-wiring package calls it: `Player`. Only the app as the player runs it is heard
//! ([`allow_sound`], off by default; CLAUDE.md: tests, tools and agents stay silent). Everything else, tests
//! included, goes through the same logic into an output that drops it, so no audio device is ever opened.

use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, OnceLock};

use crate::music::{Clock, Output, SoundsOf, ThemeMusic};
use crate::tunes::Clip;

static ALLOWED: AtomicBool = AtomicBool::new(false);

/// The app is running for the player: its sounds are heard from now on (ui_music.allow_sound).
pub fn allow_sound() {
    ALLOWED.store(true, Ordering::SeqCst);
}

/// Whether sound is heard: allow_sound was called, or BLACKLIST_DETECT_SOUND=1 asks for it to check one by ear.
pub fn sound_allowed() -> bool {
    static ENV: OnceLock<bool> = OnceLock::new();
    ALLOWED.load(Ordering::SeqCst) || *ENV.get_or_init(|| std::env::var("BLACKLIST_DETECT_SOUND").as_deref() == Ok("1"))
}

/// Drops everything: the output wherever sound is not heard.
#[derive(Debug, Default, Clone, Copy)]
pub struct NullSink;

impl Output for NullSink {
    fn play(&mut self, _clip: Option<Clip>) {}
}

/// What was asked to play, in order, for tests: Some(seconds and first samples) or None for a stop.
#[derive(Debug, Default, Clone)]
pub struct Recorder(pub Arc<Mutex<Vec<Option<Clip>>>>);

impl Output for Recorder {
    fn play(&mut self, clip: Option<Clip>) {
        self.0.lock().expect("recorder").push(clip);
    }
}

/// Passes sound on only while it is allowed (ui_music.play_tune's AUDIBLE): a stop as much as a start.
struct Gate(Box<dyn Output + Send>);

impl Output for Gate {
    fn play(&mut self, clip: Option<Clip>) {
        if sound_allowed() {
            self.0.play(clip);
        }
    }
}

/// An alert the app may sound. The Python app sounds none: its alert (ui_alert.AlertGlow) is light only.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Alert {
    /// A 黑名单 player found.
    Blacklist,
    /// A check failed (检查失败).
    Failed,
}

/// The app's sound: each 场景's tune once per lobby, the previews 场景管理 and 选择片段 play, 全局声音.
pub struct Player {
    music: ThemeMusic,
}

impl Player {
    /// Sound into `device` once [`allow_sound`] is on, never before.
    pub fn new(device: Box<dyn Output + Send>, clock: Clock, assets: PathBuf, sounds: Option<SoundsOf>) -> Self {
        Self { music: ThemeMusic::new(Box::new(Gate(device)), clock, assets, sounds) }
    }

    /// The system's speakers on Windows (opened on the first sound heard), nothing elsewhere.
    pub fn system(assets: PathBuf, sounds: Option<SoundsOf>) -> Self {
        let started = std::time::Instant::now();
        Self::new(system_output(), Box::new(move || started.elapsed().as_secs_f64()), assets, sounds)
    }

    /// The 嘉宾 / 场景 logic itself: lobby, mine, ungreet, preview, taste, song, trial.
    pub fn music(&mut self) -> &mut ThemeMusic {
        &mut self.music
    }

    /// A scene's sound now, at its 音量 (场景管理's ▶). Returns the scene played, or "" for nothing.
    pub fn play_tune(&mut self, scene: &str) -> String {
        self.music.preview(scene, 0.0)
    }

    /// The Python app plays no alert sound, so neither does this: false, nothing played.
    pub fn play_alert(&mut self, _kind: Alert) -> bool {
        false
    }

    pub fn stop(&mut self) {
        self.music.stop();
    }

    /// 全局声音: 静音 stops what plays and keeps every sound quiet until 播放.
    pub fn set_muted(&mut self, muted: bool) {
        self.music.muted = muted;
        if muted {
            self.music.stop();
        }
    }

    pub fn muted(&self) -> bool {
        self.music.muted
    }
}

#[cfg(windows)]
fn system_output() -> Box<dyn Output + Send> {
    Box::new(crate::device::Speakers::default())
}

#[cfg(not(windows))]
fn system_output() -> Box<dyn Output + Send> {
    Box::new(NullSink)
}
