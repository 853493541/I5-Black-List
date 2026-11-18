# sound

The app's sound: blacklist_detect/ui_music.py, sound_import.py and the data of ui_sound_trim.py / ui_soundwave.py.

- `player::Player`: what the app wiring calls (`play_tune`, `play_alert`, `stop`, `set_muted`, and `music()` for
  `lobby` / `mine` / `ungreet` / `preview` / `taste` / `song` / `trial`). Nothing is heard until `allow_sound()`
  (or `BLACKLIST_DETECT_SOUND=1`); tests use `Recorder` / `NullSink` and never open a device.
- Playback: rodio 0.20 on Windows only (`device.rs`, its own thread, opened on the first sound heard). rodio rather
  than raw cpal: it gives a sink that a new sound replaces and stops, all that winsound's SND_ASYNC did, in about
  40 lines; its decoders are off, it is handed samples. Volume, the 1.5 s taste's fade and the resume rise are
  rendered in memory (`tunes::render`), sample for sample what `scaled_tune` wrote to disk, so no copies folder.
- Decoding: plain PCM WAV as Python's `wave` reads it; the rest through symphonia (mp3, AAC in m4a/mp4/mov, FLAC,
  ALAC, Vorbis in webm/mkv, float WAV), where Python used Windows' decoders through Qt.
- `play_alert` plays nothing: the Python app has no alert sound (ui_alert.AlertGlow is light only).

Parity (`tests/golden.rs` on `tests/golden/sound.json`, written by `tools/rust_golden_sound.py`): every scene tune's
decode, its 5 `scaled_tune` cases, `save_clip`, `save_rest` and 560-column peaks, and six made-up WAVs (8/16/24/32
bit, 1-3 channels, 8-48 kHz, limiter, silence), are exact to the sample; rolling gains within 1e-12; the 嘉宾 / 我
greeting script, trim rules, clock and bar levels exact. mp3 decodes to Python's length and loudness; AAC keeps up
to 1023 samples (< 24 ms) of encoder padding at its end that Windows trimmed (symphonia reads no mp4 edit list).

Gaps: .wma and .amr (in the 上传 filter) and Opus in webm have no symphonia decoder: refused with 这个文件放不了.
No decode timeout (这个文件读不完): symphonia reads on the caller's thread, so the UI package runs it off the UI thread.
Needs a real PC: hearing every tune, the taste and resume fades, and stop / replace by ear (the user checks sounds).
