//! 嘉宾 scenes (model.Scenes, as likes.json keeps them) and 场景管理's sounds (as settings.json keeps them), with every
//! older form storage.py still reads.

use super::py::{cut, float, num, plain_int, round_even, strip};
use super::text::{shown, MAX_NAME, SCENE_KEYS};
use serde_json::{json, Map, Value};
use std::path::Path;

const MAX_SCENES: usize = 64;
pub const MAX_SONGS: usize = 3;

/// model.Scenes: the keys ticked and whether 随机. Neither is 不放.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Scenes {
    pub keys: Vec<String>,
    pub random: bool,
}

impl Scenes {
    pub fn any() -> Self {
        Scenes { keys: Vec::new(), random: true }
    }

    pub fn off(&self) -> bool {
        !self.random && self.keys.is_empty()
    }

    /// storage._scenes: each key once (a replaced one as its replacement), at most 64.
    pub fn cleaned(keys: &[Value], random: bool) -> Self {
        let mut kept: Vec<String> = Vec::new();
        for key in keys.iter().filter_map(Value::as_str) {
            let key = strip(key);
            if key.is_empty() {
                continue;
            }
            let key = shown(&cut(key, 40));
            if !kept.contains(&key) {
                kept.push(key);
            }
        }
        kept.truncate(MAX_SCENES);
        Scenes { keys: kept, random }
    }

    pub fn of(keys: &[String], random: bool) -> Self {
        Self::cleaned(&keys.iter().map(|k| Value::String(k.clone())).collect::<Vec<_>>(), random)
    }

    /// storage._saved_scenes: "scenes" and "random"; up to v0.9.14 "no_scene"; up to v0.9.13 one "theme".
    pub fn saved(item: &Map<String, Value>) -> Self {
        let list = |v: Option<&Value>| v.and_then(Value::as_array).cloned().unwrap_or_default();
        if item.contains_key("random") {
            return Self::cleaned(&list(item.get("scenes")), item.get("random") == Some(&Value::Bool(true)));
        }
        // Up to v0.9.13 one "theme"; "no_scene" (v0.9.14) only beside "scenes".
        let keys = if item.contains_key("scenes") {
            list(item.get("scenes"))
        } else {
            item.get("theme").filter(|t| t.is_string()).cloned().into_iter().collect()
        };
        if item.contains_key("scenes") && item.get("no_scene") == Some(&Value::Bool(true)) {
            return Scenes::default();
        }
        let scenes = Self::cleaned(&keys, false);
        if scenes.keys.is_empty() { Scenes::any() } else { scenes }
    }

    /// storage._scenes_saved, "no_scene" still written for v0.9.14.
    pub fn save_into(&self, map: &mut Map<String, Value>) {
        map.insert("scenes".into(), json!(self.keys));
        map.insert("random".into(), json!(self.random));
        map.insert("no_scene".into(), json!(self.off()));
    }
}

/// One of a 场景's songs: its file in custom_sounds, the file it came from, the part kept.
#[derive(Debug, Clone, PartialEq)]
pub struct Song {
    pub file: String,
    pub name: String,
    pub start: Option<f64>,
    pub length: Option<f64>,
}

impl Song {
    fn to_value(&self) -> Map<String, Value> {
        let mut map = Map::new();
        map.insert("file".into(), json!(self.file));
        map.insert("name".into(), json!(self.name));
        for (field, seconds) in [("start", self.start), ("length", self.length)] {
            if let Some(s) = seconds {
                map.insert(field.into(), float(s));
            }
        }
        map
    }
}

/// A 场景's own 音量 and the player's songs, with the one chosen ("" for 默认). `chosen` is None with no songs.
#[derive(Debug, Clone, PartialEq)]
pub struct SceneSound {
    pub volume: i64,
    pub songs: Vec<Song>,
    pub chosen: Option<String>,
}

impl Default for SceneSound {
    fn default() -> Self {
        SceneSound { volume: 100, songs: Vec::new(), chosen: None }
    }
}

impl SceneSound {
    pub fn is_default(&self) -> bool {
        self.songs.is_empty() && self.volume == 100
    }

    /// storage._scene_sound_saved: the chosen song copied beside the songs, for v0.9.15.
    pub fn to_value(&self) -> Value {
        let mut saved = Map::new();
        saved.insert("volume".into(), json!(self.volume));
        if !self.songs.is_empty() {
            let chosen = self.chosen.clone().unwrap_or_default();
            if let Some(song) = self.songs.iter().find(|s| Some(&s.file) == self.chosen.as_ref()) {
                saved.extend(song.to_value());
            }
            saved.insert("songs".into(), Value::Array(self.songs.iter().map(|s| Value::Object(s.to_value())).collect()));
            saved.insert("chosen".into(), json!(chosen));
        }
        Value::Object(saved)
    }
}

/// storage._volume: 0 to 100 in steps of 5, else 100.
pub fn volume(value: &Value) -> i64 {
    match (value, num(value)) {
        (Value::Number(_), Some(v)) if (0.0..=100.0).contains(&v) => round_even(v / 5.0) as i64 * 5,
        _ => 100,
    }
}

/// storage._scene_volume: 1 to 4 kept, which only folding in v0.9.14's 声音 leaves.
pub fn scene_volume(value: &Value) -> i64 {
    match plain_int(value) {
        Some(v) if 0 < v && v < 5 => v,
        _ => volume(value),
    }
}

/// storage._folded: a 场景's 音量 with v0.9.14's 声音 taken in, never louder, never 0 from two above 0.
pub fn folded(own: i64, sound: i64) -> i64 {
    let level = (own * sound).div_euclid(500) * 5;
    if level == 0 && own > 0 && sound > 0 {
        return (round_even(own as f64 * sound as f64 / 100.0) as i64).max(1);
    }
    level
}

/// storage._seconds: 0 up to a day, as a float.
pub fn seconds(value: &Value) -> Option<f64> {
    match (value, num(value)) {
        (Value::Number(_), Some(v)) if (0.0..86400.0).contains(&v) => Some(v),
        _ => None,
    }
}

fn song(value: &Value, folder: &Path) -> Option<Song> {
    let item = value.as_object()?;
    let file = item.get("file")?.as_str()?;
    let bare = Path::new(file).file_name().and_then(|n| n.to_str()) == Some(file) && !file.contains(['/', '\\']);
    if file.is_empty() || !bare || file.contains(':') || !folder.join(file).is_file() {
        return None;
    }
    let name = item.get("name").and_then(Value::as_str).map(|n| cut(strip(n), MAX_NAME * 4)).unwrap_or_default();
    let get = |k: &str| item.get(k).and_then(seconds);
    Some(Song { file: file.into(), name, start: get("start"), length: get("length") })
}

/// storage._scene_sound: None when all default, or not a sound. Up to v0.9.15 one song, its "file", always chosen.
pub fn scene_sound(value: &Value, folder: &Path) -> Option<SceneSound> {
    let item = value.as_object()?;
    let mut entry = SceneSound { volume: scene_volume(item.get("volume").unwrap_or(&Value::Null)), ..Default::default() };
    let listed = item.contains_key("songs");
    let saved: Vec<Value> = if listed {
        item.get("songs").and_then(Value::as_array).cloned().unwrap_or_default()
    } else {
        vec![value.clone()]
    };
    for s in saved.iter().filter_map(|s| song(s, folder)) {
        if entry.songs.iter().all(|kept| kept.file != s.file) {
            entry.songs.push(s);
        }
    }
    if !entry.songs.is_empty() {
        entry.songs.truncate(MAX_SONGS);
        let chosen = if listed { item.get("chosen").cloned().unwrap_or(Value::Null) } else { json!(entry.songs[0].file) };
        let found = entry.songs.iter().any(|s| Some(s.file.as_str()) == chosen.as_str());
        entry.chosen = Some(if found { chosen.as_str().unwrap_or_default().to_string() } else { String::new() });
    }
    if entry.is_default() { None } else { Some(entry) }
}

pub type Sounds = Vec<(String, SceneSound)>;

pub fn set(sounds: &mut Sounds, key: &str, entry: SceneSound) {
    match sounds.iter_mut().find(|(k, _)| k == key) {
        Some(slot) => slot.1 = entry,
        None => sounds.push((key.to_string(), entry)),
    }
}

pub fn get<'a>(sounds: &'a Sounds, key: &str) -> Option<&'a SceneSound> {
    sounds.iter().find(|(k, _)| k == key).map(|(_, e)| e)
}

/// storage._scene_sounds: by scene key; a replaced scene's is its replacement's unless that has its own.
pub fn scene_sounds(value: Option<&Value>, folder: &Path, unlisted: bool) -> Sounds {
    let mut sounds: Sounds = Vec::new();
    if let Some(Value::Object(map)) = value {
        for (raw, saved) in map {
            let key = shown(&cut(strip(raw), 40));
            if let Some(entry) = scene_sound(saved, folder) {
                if !key.is_empty() && !(key != *raw && map.contains_key(&key)) {
                    set(&mut sounds, &key, entry);
                }
            }
        }
    }
    if unlisted {
        unlisted_songs(&mut sounds, folder);
    }
    sounds
}

/// storage._wav_seconds: frames over rate, as Python's wave module reads a PCM WAV.
pub fn wav_seconds(path: &Path) -> Option<f64> {
    let bytes = std::fs::read(path).ok()?;
    if bytes.len() < 12 || &bytes[0..4] != b"RIFF" || &bytes[8..12] != b"WAVE" {
        return None;
    }
    let (mut at, mut format) = (12usize, None);
    while at + 8 <= bytes.len() {
        let id = &bytes[at..at + 4];
        let size = u32::from_le_bytes(bytes[at + 4..at + 8].try_into().ok()?) as usize;
        let body = &bytes[at + 8..(at + 8 + size).min(bytes.len())];
        if id == b"fmt " && body.len() >= 16 {
            let tag = u16::from_le_bytes([body[0], body[1]]);
            let channels = u16::from_le_bytes([body[2], body[3]]) as usize;
            let rate = u32::from_le_bytes(body[4..8].try_into().ok()?) as f64;
            let width = (u16::from_le_bytes([body[14], body[15]]) as usize).div_ceil(8);
            let pcm = tag == 1 || (tag == 0xFFFE && body.len() >= 26 && body[24..26] == [1, 0]);
            if !pcm || channels == 0 || width == 0 || rate == 0.0 {
                return None;
            }
            format = Some((channels * width, rate));
        } else if id == b"data" {
            let (frame, rate) = format?;
            return seconds(&float((size / frame) as f64 / rate));
        }
        at += 8 + size + (size & 1);
    }
    None
}

/// storage._unlisted_songs: songs in the folder (<key>-<n>.wav) the settings do not list, back in their 场景's.
fn unlisted_songs(sounds: &mut Sounds, folder: &Path) {
    let mut found: Vec<(String, Vec<(u64, String)>)> = Vec::new();
    let mut names: Vec<String> = std::fs::read_dir(folder)
        .map(|dir| dir.filter_map(|e| e.ok()?.file_name().into_string().ok()).collect())
        .unwrap_or_default();
    names.sort();
    for name in names {
        let Some((key, n)) = name.strip_suffix(".wav").and_then(|stem| stem.split_once('-')) else { continue };
        let lower = !key.is_empty() && key.chars().all(|c| c.is_ascii_lowercase());
        if !lower || n.is_empty() || !n.chars().all(|c| c.is_ascii_digit()) || !SCENE_KEYS.contains(&key) {
            continue;
        }
        let Ok(number) = n.parse::<u64>() else { continue };
        match found.iter_mut().find(|(k, _)| k == key) {
            Some((_, list)) => list.push((number, name.clone())),
            None => found.push((key.to_string(), vec![(number, name.clone())])),
        }
    }
    for (key, mut numbered) in found {
        let mut entry = get(sounds, &key).cloned().unwrap_or_default();
        numbered.sort();
        for (_, file) in &numbered {
            if entry.songs.iter().all(|s| &s.file != file) {
                let length = wav_seconds(&folder.join(file)).map_or(Value::Null, float);
                if let Some(s) = song(&json!({"file": file, "length": length}), folder) {
                    entry.songs.push(s);
                }
            }
        }
        let order = |file: &str| numbered.iter().find(|(_, f)| f == file).map_or(-1, |(n, _)| *n as i128);
        entry.songs.sort_by_key(|s| order(&s.file));
        let chosen = entry.chosen.clone().unwrap_or_default();
        while entry.songs.len() > MAX_SONGS {
            let Some(at) = entry.songs.iter().rposition(|s| s.file != chosen) else { break };
            entry.songs.remove(at);
        }
        if !entry.songs.is_empty() {
            entry.chosen = Some(chosen);
            set(sounds, &key, entry);
        }
    }
}
