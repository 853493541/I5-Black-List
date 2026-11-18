//! WAV in and out, as Python's `wave` reads and writes it: integer PCM only (a float WAV is for the decoder).

use std::fs::File;
use std::io::BufReader;
use std::path::Path;

/// A WAV's integer samples, interleaved, as read (8-bit made signed, as hound does: the byte less 128).
#[derive(Debug, Clone, PartialEq)]
pub struct Pcm {
    pub channels: u16,
    pub rate: u32,
    /// Bytes per sample: 1 to 4.
    pub width: u16,
    /// Frames the header says the file holds (Python's getnframes).
    pub frames: u64,
    pub samples: Vec<i32>,
}

#[derive(Debug)]
pub enum WavError {
    /// Not a WAV `wave` reads: float samples, a broken header. The decoder may still read it.
    Format(String),
    /// The file cannot be opened.
    Io(std::io::Error),
}

/// Read an integer PCM WAV, at most `max_frames` of it; a file shorter than its header says gives what it has.
pub fn read(path: &Path, max_frames: Option<u64>) -> Result<Pcm, WavError> {
    let file = File::open(path).map_err(WavError::Io)?;
    let reader = hound::WavReader::new(BufReader::new(file)).map_err(|e| match e {
        hound::Error::IoError(io) if io.kind() != std::io::ErrorKind::UnexpectedEof => WavError::Io(io),
        other => WavError::Format(other.to_string()),
    })?;
    let spec = reader.spec();
    if spec.sample_format != hound::SampleFormat::Int {
        return Err(WavError::Format("float samples".into()));
    }
    let width = spec.bits_per_sample.div_ceil(8);
    let frames = u64::from(reader.duration());
    let wanted = max_frames.map_or(frames, |m| m.min(frames));
    let channels = spec.channels.max(1);
    let take = (wanted * u64::from(channels)) as usize;
    let mut samples = Vec::with_capacity(take);
    for sample in reader.into_samples::<i32>().take(take) {
        match sample {
            Ok(v) => samples.push(v),
            Err(_) => break,
        }
    }
    samples.truncate(samples.len() / channels as usize * channels as usize);
    Ok(Pcm { channels: spec.channels, rate: spec.sample_rate, width, frames, samples })
}

/// Write 16-bit samples, interleaved, as Python's `wave` writes them.
pub fn write(path: &Path, channels: u16, rate: u32, samples: &[i16]) -> std::io::Result<()> {
    let spec = hound::WavSpec { channels, sample_rate: rate, bits_per_sample: 16, sample_format: hound::SampleFormat::Int };
    let to_io = |e: hound::Error| match e {
        hound::Error::IoError(io) => io,
        other => std::io::Error::other(other.to_string()),
    };
    let mut writer = hound::WavWriter::create(path, spec).map_err(to_io)?;
    let mut fast = writer.get_i16_writer(samples.len() as u32);
    for &s in samples {
        fast.write_sample(s);
    }
    fast.flush().map_err(to_io)?;
    writer.finalize().map_err(to_io)
}
