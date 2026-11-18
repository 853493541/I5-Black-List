//! With allow_sound on (as only the real app turns it), sound reaches the output; still a Recorder here, so no
//! audio device is opened. A file of its own: allow_sound is for the whole process.

use std::path::Path;

use sound::{allow_sound, sound_allowed, Player, Recorder};

fn assets() -> std::path::PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../blacklist_detect/assets")
}

#[test]
fn allowed_sound_plays_and_mute_stops_it() {
    let rec = Recorder::default();
    let mut player = Player::new(Box::new(rec.clone()), Box::new(|| 0.0), assets(), None);
    assert!(!sound_allowed() || std::env::var("BLACKLIST_DETECT_SOUND").as_deref() == Ok("1"));
    allow_sound();
    assert!(sound_allowed());
    assert_eq!(player.play_tune("ice"), "ice");
    assert_eq!(player.play_tune("classic"), "", "经典 greets in silence");
    player.set_muted(true);
    assert_eq!(player.play_tune("ice"), "", "静音 plays nothing");
    assert!(player.muted());
    player.set_muted(false);
    player.stop();
    let got = rec.0.lock().unwrap();
    let shape: Vec<Option<f64>> = got.iter().map(|c| c.as_ref().map(sound::Clip::seconds)).collect();
    assert_eq!(shape, vec![Some(5.0), None, None, None, None]);
}

#[test]
fn a_float_wav_goes_to_the_decoder() {
    let dir = std::env::temp_dir().join(format!("sound-float-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("float.wav");
    let spec = hound::WavSpec { channels: 2, sample_rate: 22050, bits_per_sample: 32, sample_format: hound::SampleFormat::Float };
    let mut w = hound::WavWriter::create(&path, spec).unwrap();
    for i in 0..22050 {
        let v = (i as f32 * 0.03).sin() * 0.5;
        w.write_sample(v).unwrap();
        w.write_sample(v).unwrap();
    }
    w.finalize().unwrap();
    let d = sound::decode(&path).unwrap();
    assert_eq!(d.samples.len(), 44100);
    assert!(!d.cut);
    let peak = d.samples.iter().map(|&s| i32::from(s).abs()).max().unwrap();
    assert!((16000..=16500).contains(&peak), "{peak}");
    std::fs::remove_dir_all(&dir).unwrap();
}
