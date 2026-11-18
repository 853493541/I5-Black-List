//! How a player's sound is kept (sound_import.save_clip, save_rest): at most CLIP_S of it, fading in and out, as
//! loud as the built-in tunes (TARGET_RMS_DBFS, peaks no higher than PEAK_DBFS), as a mono 16-bit WAV.

use std::path::{Path, PathBuf};

use crate::import::{Decoded, ImportError, RATE};
use crate::npmath::{interp, linspace, mean, pairwise_sum, to_i16, to_i16_f32};
use crate::wav;

pub const CLIP_S: f64 = 5.0;
pub const FADE_IN_S: f64 = 0.01;
pub const FADE_OUT_S: f64 = 0.25;
pub const TARGET_RMS_DBFS: f64 = -19.0;
pub const PEAK_DBFS: f64 = -3.0;
/// Shorter than this is no sound at all.
pub const MIN_S: f64 = 0.05;
/// The song's loudness is read in blocks this long (a tenth of a second).
pub const BLOCK: usize = RATE as usize / 10;
const QUIET: f64 = -70.0;

fn db(v: f64) -> f64 {
    10f64.powf(v / 20.0)
}

/// A sound kept for a 场景: the WAV at path, made from length_s seconds of the file called name (original_s
/// long, as read) from start_s on.
#[derive(Debug, Clone, PartialEq)]
pub struct Imported {
    pub path: PathBuf,
    pub name: String,
    pub original_s: f64,
    pub start_s: f64,
    pub length_s: f64,
}

/// A scene key, as `[a-z0-9_-]+`.
fn is_key(key: &str) -> bool {
    !key.is_empty() && key.bytes().all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_' || b == b'-')
}

/// The part from start_s, length_s long (at most CLIP_S), within the sound: (begin, end) in samples.
fn span(total: usize, start_s: f64, length_s: f64) -> (usize, usize) {
    let begin = ((start_s * f64::from(RATE)).round_ties_even().max(0.0) as usize).min(total);
    let len = (length_s.clamp(0.0, CLIP_S) * f64::from(RATE)).round_ties_even() as usize;
    (begin, (begin + len).min(total))
}

/// Keep length_s seconds of decoded from start_s on as folder/<key>.wav, written beside it first.
pub fn save_clip(decoded: &Decoded, key: &str, folder: &Path, start_s: f64, length_s: f64) -> Result<Imported, ImportError> {
    if !is_key(key) {
        return Err(ImportError::NotAKey(key.to_string()));
    }
    let (begin, end) = span(decoded.samples.len(), start_s, length_s);
    if ((end - begin) as f64) < MIN_S * f64::from(RATE) {
        return Err(ImportError::Player("选的这段太短了"));
    }
    let clip: Vec<f64> = decoded.samples[begin..end].iter().map(|&s| f64::from(s) / 32768.0).collect();
    let mut clip = level(clip)?;
    fade(&mut clip);
    let target = folder.join(format!("{key}.wav"));
    let part = folder.join(format!("{key}.wav.part"));
    let samples: Vec<i16> = clip.iter().map(|v| to_i16(v * 32768.0)).collect();
    let written = std::fs::create_dir_all(folder)
        .and_then(|()| wav::write(&part, 1, RATE, &samples))
        .and_then(|()| std::fs::rename(&part, &target));
    if written.is_err() {
        let _ = std::fs::remove_file(&part);
        return Err(ImportError::Player("声音存不下来，再试一次"));
    }
    let rate = f64::from(RATE);
    Ok(Imported {
        path: target,
        name: decoded.name.clone(),
        original_s: decoded.seconds,
        start_s: begin as f64 / rate,
        length_s: (end - begin) as f64 / rate,
    })
}

/// The name a 场景's next song is kept under: <key>-<n>, n the first number with no file of it in folder.
pub fn song_name(key: &str, folder: &Path) -> String {
    (1..).map(|n| format!("{key}-{n}")).find(|name| !folder.join(format!("{name}.wav")).exists()).expect("a free name")
}

fn rms(clip: &[f64]) -> f64 {
    let squares: Vec<f64> = clip.iter().map(|v| v * v).collect();
    mean(&squares).sqrt()
}

/// clip at about TARGET_RMS_DBFS, the moments that would pass PEAK_DBFS turned down on their own.
pub fn level(mut clip: Vec<f64>) -> Result<Vec<f64>, ImportError> {
    let mut now = rms(&clip);
    // Python's `rms < floor` is false for NaN (an empty clip), which then fails on; here it is no sound.
    if now.is_nan() || now < db(QUIET) {
        return Err(ImportError::Player("选的这段没有声音"));
    }
    let (target, peak) = (db(TARGET_RMS_DBFS), db(PEAK_DBFS));
    for _ in 0..4 {
        let gain = target / now;
        clip = limit(clip.iter().map(|v| v * gain).collect(), peak);
        now = rms(&clip);
        if now >= target * db(-0.25) {
            break;
        }
    }
    Ok(clip.into_iter().map(|v| v.clamp(-peak, peak)).collect())
}

/// Each 10 ms block's gain: the least it and its neighbours need to keep under peak (from each block's loudest).
fn needs(loud: impl Fn(usize) -> f64, len: usize, peak: f64, block: usize) -> Vec<f64> {
    let blocks = len.div_ceil(block);
    let need: Vec<f64> = (0..blocks)
        .map(|b| {
            let top = (b * block..((b + 1) * block).min(len)).map(&loud).fold(0.0f64, f64::max);
            (peak / top.max(1e-12)).min(1.0)
        })
        .collect();
    (0..blocks).map(|b| need[b.saturating_sub(1)].min(need[b]).min(need[(b + 1).min(blocks - 1)])).collect()
}

fn centres(blocks: usize, block: usize) -> Vec<f64> {
    (0..blocks).map(|b| (b * block) as f64 + block as f64 / 2.0).collect()
}

/// clip with no sample past peak (sound_import._limit).
pub fn limit(clip: Vec<f64>, peak: f64) -> Vec<f64> {
    let block = RATE as usize / 100;
    if clip.iter().fold(0.0f64, |m, v| m.max(v.abs())) <= peak {
        return clip;
    }
    let need = needs(|i| clip[i].abs(), clip.len(), peak, block);
    let at = centres(need.len(), block);
    clip.iter().enumerate().map(|(i, v)| v * interp(i as f64, &at, &need)).collect()
}

/// In place: FADE_IN_S up from silence, FADE_OUT_S down to it (less on a very short clip).
pub fn fade(clip: &mut [f64]) {
    let n = clip.len();
    let rise = ((FADE_IN_S * f64::from(RATE)).round_ties_even() as usize).min(n / 10);
    let fall = ((FADE_OUT_S * f64::from(RATE)).round_ties_even() as usize).min(n / 3);
    for (v, g) in clip[..rise].iter_mut().zip(linspace(0.0, 1.0, rise, false)) {
        *v *= g;
    }
    for (v, g) in clip[n - fall..].iter_mut().zip(linspace(1.0, 0.0, fall, true)) {
        *v *= g;
    }
}

/// np.convolve(a, ones(span), "same"): each entry the sum of the span round it.
fn window_sums(a: &[f64], span: usize) -> Vec<f64> {
    let (n, m) = (a.len(), span);
    let skip = (n.min(m) - 1) / 2;
    (0..n.max(m))
        .map(|i| {
            let full = i + skip;
            let lo = (full + 1).saturating_sub(m);
            let hi = full.min(n - 1);
            if lo > hi {
                0.0
            } else {
                a[lo..=hi].iter().sum()
            }
        })
        .collect()
}

/// Per BLOCK of samples, what brings the CLIP_S round it to about TARGET_RMS_DBFS (sound_import._rolling_gain).
pub fn rolling_gain(samples: &[i16]) -> Vec<f64> {
    let blocks = samples.len().div_ceil(BLOCK).max(1);
    let squares: Vec<f64> = (0..blocks)
        .map(|b| {
            let part: Vec<f64> = samples[(b * BLOCK).min(samples.len())..((b + 1) * BLOCK).min(samples.len())]
                .iter()
                .map(|&s| f64::from(s) * f64::from(s))
                .collect();
            pairwise_sum(&part)
        })
        .collect();
    let span = ((CLIP_S * f64::from(RATE) / BLOCK as f64).round_ties_even() as usize).max(1);
    let window = window_sums(&squares, span);
    let counts: Vec<f64> = window_sums(&vec![1.0; blocks], span).into_iter().map(|c| c * BLOCK as f64).collect();
    let floor = db(QUIET);
    let rms: Vec<f64> = window.iter().zip(&counts).map(|(w, c)| (w / c).sqrt() / 32768.0).collect();
    let quiet: Vec<bool> = rms.iter().map(|&r| r < floor).collect();
    if quiet.iter().all(|&q| q) {
        return vec![1.0; blocks];
    }
    let mut gains: Vec<f64> = rms.iter().map(|&r| db(TARGET_RMS_DBFS) / r.max(floor)).collect();
    let loud: Vec<usize> = (0..rms.len()).filter(|&i| !quiet[i]).collect();
    let xs: Vec<f64> = loud.iter().map(|&i| i as f64).collect();
    let ys: Vec<f64> = loud.iter().map(|&i| gains[i]).collect();
    for i in (0..rms.len()).filter(|&i| quiet[i]) {
        gains[i] = interp(i as f64, &xs, &ys);
    }
    gains
}

/// What brings the part from start_s, length_s long, to about TARGET_RMS_DBFS; None for no sound there.
pub fn part_gain(samples: &[i16], start_s: f64, length_s: f64) -> Option<f64> {
    let (begin, end) = span(samples.len(), start_s, length_s);
    if end <= begin {
        return None;
    }
    let squares: Vec<f64> = samples[begin..end].iter().map(|&s| f64::from(s) * f64::from(s)).collect();
    let rms = mean(&squares).sqrt() / 32768.0;
    (rms >= db(QUIET)).then(|| db(TARGET_RMS_DBFS) / rms)
}

/// The sound from start_s to its end, at volume percent, each moment levelled as save_clip levels the part
/// round it (gains: rolling_gain, worked out once by a caller that plays it again and again).
pub fn rest_samples(decoded: &Decoded, start_s: f64, volume: i32, gains: Option<&[f64]>) -> Vec<i16> {
    let samples = &decoded.samples;
    let begin = ((start_s * f64::from(RATE)).round_ties_even().max(0.0) as usize).min(samples.len());
    let own;
    let gains = match gains {
        Some(g) => g,
        None => {
            own = rolling_gain(samples);
            &own
        }
    };
    let middles: Vec<f64> = (0..gains.len()).map(|b| (b * BLOCK) as f64 + (BLOCK as f64 - 1.0) / 2.0).collect();
    let peak = db(PEAK_DBFS);
    let scale = f64::from(volume.max(0)) / 100.0;
    let chunk: Vec<f32> = samples[begin..]
        .iter()
        .enumerate()
        .map(|(i, &s)| (f32::from(s) / 32768.0) * interp((begin + i) as f64, &middles, gains) as f32)
        .collect();
    // Python works a minute at a time; each minute is limited on its own, as here.
    let step = 60 * RATE as usize;
    let mut out = Vec::with_capacity(chunk.len());
    for part in chunk.chunks(step) {
        let top = part.iter().fold(0.0f32, |m, v| m.max(v.abs()));
        if top <= peak as f32 {
            let (p, s) = (peak as f32, scale as f32);
            out.extend(part.iter().map(|v| to_i16_f32(v.clamp(-p, p) * s * 32768.0)));
        } else {
            let block = RATE as usize / 100;
            let need = needs(|i| f64::from(part[i].abs()), part.len(), peak, block);
            let at = centres(need.len(), block);
            out.extend(part.iter().enumerate().map(|(i, &v)| {
                let limited = f64::from(v) * interp(i as f64, &at, &need);
                to_i16(limited.clamp(-peak, peak) * scale * 32768.0)
            }));
        }
    }
    out
}

/// rest_samples as the WAV at path (sound_import.save_rest).
pub fn save_rest(decoded: &Decoded, start_s: f64, path: &Path, volume: i32, gains: Option<&[f64]>) -> Result<PathBuf, ImportError> {
    let samples = rest_samples(decoded, start_s, volume, gains);
    let written = path.parent().map_or(Ok(()), std::fs::create_dir_all).and_then(|()| wav::write(path, 1, RATE, &samples));
    if written.is_err() {
        let _ = std::fs::remove_file(path);
        return Err(ImportError::Player("放不了，再试一次"));
    }
    Ok(path.to_path_buf())
}
