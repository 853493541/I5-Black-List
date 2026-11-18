//! Every file that is not a plain PCM WAV, through symphonia: mp3, AAC in m4a / mp4 / mov, FLAC, ALAC, Vorbis in
//! webm / mkv, float or ADPCM WAV. Mixed to mono and taken to 44.1 kHz as the WAV path is.

use std::fs::File;
use std::path::Path;

use symphonia::core::audio::SampleBuffer;
use symphonia::core::codecs::{DecoderOptions, CODEC_TYPE_AAC, CODEC_TYPE_NULL};
use symphonia::core::errors::Error;
use symphonia::core::formats::FormatOptions;
use symphonia::core::io::MediaSourceStream;
use symphonia::core::meta::MetadataOptions;
use symphonia::core::probe::Hint;

use crate::import::{resample, to_mono, MAX_DECODE_S, RATE};

const AAC_PRIMING: usize = 1024;

/// The sound of source, mono 16-bit at RATE, and whether it was cut at MAX_DECODE_S; None when it cannot be read.
pub fn read_any(source: &Path, kind: &str) -> Option<(Vec<i16>, bool)> {
    let file = File::open(source).ok()?;
    let stream = MediaSourceStream::new(Box::new(file), Default::default());
    let mut hint = Hint::new();
    hint.with_extension(kind);
    let probed = symphonia::default::get_probe()
        .format(&hint, stream, &FormatOptions { enable_gapless: true, ..Default::default() }, &MetadataOptions::default())
        .ok()?;
    let mut format = probed.format;
    let track = format.tracks().iter().find(|t| t.codec_params.codec != CODEC_TYPE_NULL)?.clone();
    let mut decoder = symphonia::default::get_codecs().make(&track.codec_params, &DecoderOptions::default()).ok()?;
    let mut rate = track.codec_params.sample_rate.unwrap_or(0);
    // AAC starts with a frame of encoder priming that mp4's edit list tells Windows to skip; symphonia does not
    // read the edit list, so the usual 1024 frames go here (the up to 1023 of padding at the end stay: < 24 ms).
    // (With gapless on, symphonia trims what a track's own header says, an mp3's LAME delay and padding.)
    let params = &track.codec_params;
    let mut skip = if params.codec == CODEC_TYPE_AAC && params.delay.is_none() { AAC_PRIMING } else { 0 };
    let mut mono: Vec<i16> = Vec::new();
    let mut cut = false;
    loop {
        let packet = match format.next_packet() {
            Ok(packet) => packet,
            Err(Error::IoError(_)) | Err(Error::ResetRequired) => break,
            Err(_) => return None,
        };
        if packet.track_id() != track.id {
            continue;
        }
        let decoded = match decoder.decode(&packet) {
            Ok(decoded) => decoded,
            Err(Error::DecodeError(_)) => continue,
            Err(_) => break,
        };
        let spec = *decoded.spec();
        rate = spec.rate;
        let mut buffer = SampleBuffer::<f32>::new(decoded.capacity() as u64, spec);
        buffer.copy_interleaved_ref(decoded);
        let channels = spec.channels.count().max(1);
        let dropped = skip.min(buffer.samples().len() / channels);
        skip -= dropped;
        mono.extend(to_mono(&buffer.samples()[dropped * channels..], channels));
        if rate > 0 && mono.len() as u64 > u64::from(MAX_DECODE_S) * u64::from(rate) {
            cut = true;
            break;
        }
    }
    if rate == 0 {
        return None;
    }
    let mut samples = resample(&mono, rate);
    let most = (MAX_DECODE_S * RATE) as usize;
    if samples.len() >= most {
        samples.truncate(most);
        cut = true;
    }
    Some((samples, cut))
}
