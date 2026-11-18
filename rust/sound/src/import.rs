//! A player's own sound, read once as it is chosen (sound_import.decode): mono 16-bit at 44.1 kHz, at most
//! MAX_DECODE_S of it. WAV is read as Python's `wave` reads it, sample for sample; everything else goes through
//! symphonia, bundled, where Python handed it to Windows' own decoders through Qt (see `FILTER` for the gaps).

use std::path::Path;

use crate::npmath::{interp_unit, to_i16_f32};
use crate::wav::{self, WavError};

/// What the 上传 file dialog offers (sound_import.FILTER).
pub const FILTER: &str = "*.mp3 *.m4a *.aac *.mp4 *.mov *.wav *.flac *.wma *.webm *.mkv *.amr";
/// Offered, but symphonia has no decoder for them: they are refused with 这个文件放不了 (Windows decoded them).
pub const UNDECODED: [&str; 2] = ["wma", "amr"];
/// Videos: their sound is what is kept.
pub const VIDEO_SUFFIXES: [&str; 4] = ["mp4", "mov", "webm", "mkv"];
pub const RATE: u32 = 44100;
/// The most of a file read: a longer one is read this far, and flagged (Decoded::cut).
pub const MAX_DECODE_S: u32 = 600;

/// Why a file cannot be used. `Player`'s message is for the player, word for word the Python app's.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ImportError {
    Player(&'static str),
    /// Not a scene key (a caller's mistake, Python's ValueError).
    NotAKey(String),
}

impl ImportError {
    pub fn message(&self) -> &str {
        match self {
            Self::Player(text) => text,
            Self::NotAKey(_) => "not a scene key",
        }
    }
}

impl std::fmt::Display for ImportError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.message())
    }
}

impl std::error::Error for ImportError {}

/// A file's sound, mono 16-bit at RATE. seconds: how much was read; cut: only its start was read.
#[derive(Debug, Clone, PartialEq)]
pub struct Decoded {
    pub samples: Vec<i16>,
    pub seconds: f64,
    pub name: String,
    pub cut: bool,
}

fn suffix(source: &Path) -> String {
    source.extension().and_then(|e| e.to_str()).unwrap_or("").to_ascii_lowercase()
}

/// The sound of source, mono 16-bit at RATE, at most MAX_DECODE_S of it.
pub fn decode(source: &Path) -> Result<Decoded, ImportError> {
    let size = std::fs::metadata(source).map_err(|_| ImportError::Player("找不到这个文件"))?.len();
    if size == 0 {
        return Err(ImportError::Player("这个文件是空的"));
    }
    let kind = suffix(source);
    let video = VIDEO_SUFFIXES.contains(&kind.as_str());
    let mut read = None;
    if kind == "wav" {
        match read_wav(source) {
            Ok(found) => read = Some(found),
            Err(WavError::Io(_)) => return Err(ImportError::Player("这个文件打不开")),
            Err(WavError::Format(_)) => {}
        }
    }
    let (samples, cut) = match read {
        Some(found) => found,
        None => crate::decode::read_any(source, &kind)
            .ok_or(ImportError::Player(if video { "这个视频里没有能放的声音" } else { "这个文件放不了" }))?,
    };
    if (samples.len() as f64) < crate::level::MIN_S * f64::from(RATE) {
        return Err(ImportError::Player(if video { "这个视频里没有能放的声音" } else { "这个文件没有声音" }));
    }
    let name = source.file_stem().and_then(|s| s.to_str()).unwrap_or("").to_string();
    Ok(Decoded { seconds: samples.len() as f64 / f64::from(RATE), samples, name, cut })
}

/// An integer PCM WAV, 8 to 32 bits, any rate and channels (sound_import._read_wav).
fn read_wav(source: &Path) -> Result<(Vec<i16>, bool), WavError> {
    let pcm = wav::read(source, None)?;
    if pcm.width > 4 || pcm.channels < 1 || pcm.rate < 1000 {
        return Err(WavError::Format(format!("{}-bit, {} channels at {} Hz", pcm.width * 8, pcm.channels, pcm.rate)));
    }
    let wanted = pcm.frames.min(u64::from(MAX_DECODE_S) * u64::from(pcm.rate));
    let nch = usize::from(pcm.channels);
    let keep = (wanted as usize * nch).min(pcm.samples.len());
    let floats: Vec<f32> = pcm.samples[..keep]
        .iter()
        .map(|&v| match pcm.width {
            1 | 2 => v as f32 / if pcm.width == 1 { 128.0 } else { 32768.0 },
            3 => v as f32 / (1 << 23) as f32,
            _ => (f64::from(v) / f64::from(1u32 << 31)) as f32,
        })
        .collect();
    let mono = to_mono(&floats, nch);
    Ok((resample(&mono, pcm.rate), pcm.frames > wanted))
}

/// Interleaved float samples, the channels mixed into one, as int16 (sound_import._to_mono).
pub fn to_mono(samples: &[f32], channels: usize) -> Vec<i16> {
    if channels <= 1 {
        return samples.iter().map(|&v| to_i16_f32(v * 32768.0)).collect();
    }
    samples
        .chunks_exact(channels)
        .map(|frame| {
            let sum = frame.iter().fold(0.0f32, |acc, &v| acc + v);
            to_i16_f32(sum / channels as f32 * 32768.0)
        })
        .collect()
}

/// int16 samples at rate, at RATE: straight lines between them (sound_import._resample).
pub fn resample(samples: &[i16], rate: u32) -> Vec<i16> {
    if rate == RATE || samples.is_empty() {
        return samples.to_vec();
    }
    let count = (samples.len() as f64 * f64::from(RATE) / f64::from(rate)) as usize;
    let ratio = f64::from(rate) / f64::from(RATE);
    let fp: Vec<f64> = samples.iter().map(|&s| f64::from(s)).collect();
    (0..count).map(|i| crate::npmath::to_i16(interp_unit(i as f64 * ratio, &fp))).collect()
}
