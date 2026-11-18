//! Each 嘉宾 scene's own sound (ui_music.TUNES) and how a tune is made quieter, cut short or started part way
//! (ui_music.scaled_tune), here in memory rather than as a copy on disk: rodio plays samples, not only files.

use std::path::{Path, PathBuf};

use crate::npmath::{linspace, to_i16};
use crate::wav;

/// Each scene's sound, by the scene's key, as the file name in blacklist_detect/assets. 经典 has none.
pub const TUNES: [(&str, &str); 10] = [
    ("lace", "wedding-organ.wav"),
    ("ice", "theme-ice.wav"),
    ("stars", "theme-stars.wav"),
    ("cyber", "theme-cyber.wav"),
    ("neon", "theme-neon.wav"),
    ("angel", "wedding-bells.wav"),
    ("equation", "wedding-canon.wav"),
    ("fluffy", "theme-fluffy.wav"),
    ("claw", "ambush.wav"),
    ("lyre", "lyre.wav"),
];
/// A 场景's 音量 in 场景管理 moves in steps of this many percent; 100 is each tune as made.
pub const VOLUME_STEP: i32 = 5;
/// What 音量's slider plays as it is let go: this long, fading out over SAMPLE_FADE_S.
pub const SAMPLE_S: f64 = 1.5;
pub const SAMPLE_FADE_S: f64 = 0.25;
/// A sound played on from a moment rises over this long (no click).
pub const RESUME_FADE_S: f64 = 0.015;
/// The same 嘉宾 players found again this soon are the same lobby: no second tune.
pub const SAME_LOBBY_S: f64 = 60.0;

/// The file name of a scene's own sound, or None (经典, or no such scene).
pub fn tune_file(scene: &str) -> Option<&'static str> {
    TUNES.iter().find(|(key, _)| *key == scene).map(|(_, file)| *file)
}

/// A scene's own sound in the assets folder.
pub fn tune_path(assets: &Path, scene: &str) -> Option<PathBuf> {
    tune_file(scene).map(|file| assets.join(file))
}

/// Sound ready to play: 16-bit samples, interleaved.
#[derive(Debug, Clone, PartialEq)]
pub struct Clip {
    pub channels: u16,
    pub rate: u32,
    pub samples: Vec<i16>,
}

impl Clip {
    pub fn seconds(&self) -> f64 {
        if self.rate == 0 || self.channels == 0 {
            return 0.0;
        }
        (self.samples.len() / self.channels as usize) as f64 / f64::from(self.rate)
    }
}

/// The tune at `volume` percent, with `seconds` only its start fading out over SAMPLE_FADE_S, or with `start`
/// what comes from that many seconds on, rising over RESUME_FADE_S: the samples scaled_tune writes. None when
/// the file is no 16-bit WAV that can be read: better nothing than a tune too loud.
pub fn render(path: &Path, volume: i32, seconds: Option<f64>, start: f64) -> Option<Clip> {
    let pcm = wav::read(path, None).ok()?;
    if pcm.width != 2 {
        return None;
    }
    let nch = usize::from(pcm.channels.max(1));
    let have = (pcm.samples.len() / nch) as u64;
    let nframes = pcm.frames.min(have);
    let rate = f64::from(pcm.rate);
    let skip = nframes.min((start * rate).round_ties_even().max(0.0) as u64);
    let rest = nframes - skip;
    let frames = match seconds {
        Some(s) => rest.min((s * rate).round_ties_even().max(0.0) as u64),
        None => rest,
    };
    let begin = skip as usize * nch;
    let gain = f64::from(volume) / 100.0;
    let mut samples: Vec<f64> = pcm.samples[begin..begin + frames as usize * nch].iter().map(|&s| f64::from(s) * gain).collect();
    let count = samples.len() / nch;
    if seconds.is_some() {
        let fade = count.min((SAMPLE_FADE_S * rate).round_ties_even() as usize);
        let from = samples.len() - fade * nch;
        for (i, g) in linspace(1.0, 0.0, fade, true).into_iter().enumerate() {
            for s in &mut samples[from + i * nch..from + (i + 1) * nch] {
                *s *= g;
            }
        }
    }
    if start > 0.0 {
        let rise = count.min((RESUME_FADE_S * rate).round_ties_even() as usize);
        for (i, g) in linspace(0.0, 1.0, rise, true).into_iter().enumerate() {
            for s in &mut samples[i * nch..(i + 1) * nch] {
                *s *= g;
            }
        }
    }
    Some(Clip { channels: pcm.channels, rate: pcm.rate, samples: samples.into_iter().map(to_i16).collect() })
}

/// How long a tune plays, in seconds: 0 for none, or one that cannot be read (ui_music.tune_seconds).
pub fn tune_seconds(path: Option<&Path>) -> f64 {
    let Some(path) = path else { return 0.0 };
    let Ok(reader) = hound::WavReader::open(path) else { return 0.0 };
    let rate = reader.spec().sample_rate;
    if rate == 0 {
        return 0.0;
    }
    f64::from(reader.duration()) / f64::from(rate)
}
