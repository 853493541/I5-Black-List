//! 场景管理: each 场景's own 音量 and the player's songs for it, as storage.py changes and saves them.

use super::sounds::{self, scene_volume, SceneSound, Song, MAX_SONGS};
use super::Store;
use serde_json::json;
use std::io;
use std::path::PathBuf;

impl Store {
    /// A 场景's sound: the song chosen (None for 默认, the scene's own) and its 音量.
    pub fn scene_sound(&self, key: &str) -> (Option<PathBuf>, i64) {
        let entry = sounds::get(&self.settings.scene_sounds, key).cloned().unwrap_or_default();
        let file = entry.chosen.filter(|f| !f.is_empty()).map(|f| self.sound_dir().join(f));
        (file, scene_volume(&json!(entry.volume)))
    }

    pub fn scene_songs(&self, key: &str) -> Vec<Song> {
        sounds::get(&self.settings.scene_sounds, key).map(|e| e.songs.clone()).unwrap_or_default()
    }

    fn set_scene_sound(&mut self, key: &str, entry: SceneSound) {
        if entry.is_default() {
            self.settings.scene_sounds.retain(|(k, _)| k != key);
        } else {
            sounds::set(&mut self.settings.scene_sounds, key, entry);
        }
    }

    /// A 场景's 音量, not saved yet: 场景管理's slider saves it as it is let go.
    pub fn set_scene_volume(&mut self, key: &str, volume: i64) {
        let mut entry = sounds::get(&self.settings.scene_sounds, key).cloned().unwrap_or_default();
        entry.volume = scene_volume(&json!(volume));
        self.set_scene_sound(key, entry);
    }

    /// A song kept for a 场景 (its file already in custom_sounds), the one it plays from now on; past MAX_SONGS the
    /// oldest goes, its file too.
    pub fn add_scene_song(&mut self, key: &str, song: Song) -> io::Result<()> {
        let mut entry = sounds::get(&self.settings.scene_sounds, key).cloned().unwrap_or_default();
        let mut songs: Vec<Song> = entry.songs.into_iter().filter(|k| k.file != song.file).collect();
        songs.push(song.clone());
        let extra = songs.len().saturating_sub(MAX_SONGS);
        for gone in songs.drain(..extra) {
            let _ = std::fs::remove_file(self.sound_dir().join(gone.file));
        }
        entry.songs = songs;
        entry.chosen = Some(song.file);
        self.set_scene_sound(key, entry);
        self.save_settings()
    }

    /// A 场景's song gone from its list (its file is the caller's); 默认 plays if it was the one chosen.
    pub fn remove_scene_song(&mut self, key: &str, file: &str) -> io::Result<()> {
        let mut entry = sounds::get(&self.settings.scene_sounds, key).cloned().unwrap_or_default();
        entry.songs.retain(|s| s.file != file);
        entry.chosen = if entry.songs.is_empty() {
            None
        } else {
            Some(entry.chosen.filter(|c| c != file).unwrap_or_default())
        };
        self.set_scene_sound(key, entry);
        self.save_settings()
    }

    /// The sound a 场景 plays: one of its songs by its file, or "" (or one that is none) for 默认.
    pub fn choose_scene_song(&mut self, key: &str, file: &str) -> io::Result<()> {
        let Some(mut entry) = sounds::get(&self.settings.scene_sounds, key).cloned() else { return Ok(()) };
        if entry.songs.is_empty() {
            return Ok(());
        }
        let found = entry.songs.iter().any(|s| s.file == file);
        entry.chosen = Some(if found { file.to_string() } else { String::new() });
        self.set_scene_sound(key, entry);
        self.save_settings()
    }
}
