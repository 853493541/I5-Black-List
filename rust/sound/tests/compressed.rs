//! The release's compressed tunes (rust/assets/sounds/*.ogg, tools/size/sound_compress.py) play as their WAVs do:
//! the same length to the sample at every 音量, taste and resume, and a difference below hearing.

use std::path::{Path, PathBuf};

use sound::tunes::tune_path;
use sound::{render, tune_seconds, Clip, TUNES};

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")
}
fn wav(file: &str) -> PathBuf {
    root().join("blacklist_detect/assets").join(file)
}
fn ogg(file: &str) -> PathBuf {
    root().join("rust/assets/sounds").join(file).with_extension("ogg")
}

/// The difference of two clips in dB below full scale: its RMS and its biggest sample.
fn difference(a: &Clip, b: &Clip) -> (f64, f64) {
    let (mut sum, mut peak) = (0.0f64, 0.0f64);
    for (x, y) in a.samples.iter().zip(&b.samples) {
        let d = (f64::from(*x) - f64::from(*y)) / 32768.0;
        sum += d * d;
        peak = peak.max(d.abs());
    }
    let db = |v: f64| 20.0 * v.max(1e-12).log10();
    (db((sum / a.samples.len().max(1) as f64).sqrt()), db(peak))
}

#[test]
fn every_tune_ships_compressed() {
    for (_, file) in TUNES {
        assert!(ogg(file).is_file(), "{file}: run tools/size/sound_compress.py");
        let (wav, ogg) = (std::fs::metadata(wav(file)).unwrap().len(), std::fs::metadata(ogg(file)).unwrap().len());
        assert!(ogg * 5 < wav, "{file}: {ogg} bytes against {wav}");
    }
}

#[test]
fn compressed_tunes_play_as_their_wavs() {
    for (key, file) in TUNES {
        let (w, o) = (wav(file), ogg(file));
        let (sw, so) = (tune_seconds(Some(&w)), tune_seconds(Some(&o)));
        assert!((sw - so).abs() < 1e-9, "{key}: {sw} s against {so} s");
        let cases = [(100, None, 0.0), (35, None, 0.0), (100, Some(1.5), 0.0), (80, None, 2.5), (5, Some(1.5), 0.0)];
        for (volume, seconds, start) in cases {
            let a = render(&w, volume, seconds, start).unwrap();
            let b = render(&o, volume, seconds, start).unwrap();
            assert_eq!((a.channels, a.rate, a.samples.len()), (b.channels, b.rate, b.samples.len()), "{key} {volume}");
            let (rms, peak) = difference(&a, &b);
            // Measured at 100 %: rms -42 to -51 dB, peak -24 to -35 dB below full scale (the codec's noise, shaped
            // under the music, where Vorbis q6 is held transparent).
            assert!(rms < -40.0 && peak < -20.0, "{key} {volume}%: rms {rms:.1} dB, peak {peak:.1} dB");
        }
    }
}

#[test]
fn a_release_folder_plays_the_ogg_and_the_source_the_wav() {
    let dir = std::env::temp_dir().join(format!("sound-compressed-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::copy(wav("lyre.wav"), dir.join("lyre.wav")).unwrap();
    assert_eq!(tune_path(&dir, "lyre").unwrap(), dir.join("lyre.wav"));
    std::fs::copy(ogg("lyre.wav"), dir.join("lyre.ogg")).unwrap();
    assert_eq!(tune_path(&dir, "lyre").unwrap(), dir.join("lyre.ogg"));
    assert_eq!(tune_path(&dir, "classic"), None);
    std::fs::remove_dir_all(&dir).unwrap();
}
