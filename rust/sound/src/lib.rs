//! The app's sound (blacklist_detect/ui_music.py, sound_import.py, the data of ui_sound_trim.py and
//! ui_soundwave.py): each 嘉宾 scene's tune, when it plays and how loud, a player's own sound read and kept, and
//! the numbers 选择片段 draws from. Playback is rodio on Windows, decoding symphonia; nothing is heard until the
//! app calls [`allow_sound`].
#![forbid(unsafe_code)]

mod decode;
#[cfg(windows)]
mod device;
pub mod import;
pub mod level;
pub mod music;
pub mod npmath;
pub mod player;
pub mod trim;
pub mod tunes;
pub mod wav;

pub use import::{decode, Decoded, ImportError};
pub use level::{save_clip, save_rest, song_name, Imported};
pub use music::{Output, ThemeMusic};
pub use player::{allow_sound, sound_allowed, Alert, NullSink, Player, Recorder};
pub use tunes::{render, tune_seconds, Clip, TUNES};
