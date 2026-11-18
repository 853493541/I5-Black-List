//! settings.json: every 设置 the store keeps, read from any version's file and written as the Python app writes it.

use super::py::{self, cut, dict, num, py_str, truthy, Res};
use super::sounds::{scene_sounds, volume, Sounds};
use super::text::{clean_stored_name, clean_tag, parse_hotkey, shown, two_keys, MAX_NAME, SCENE_KEYS, TAGS};
use serde_json::{json, Map, Value};
use std::path::Path;

pub const DEFAULT_COLUMN_WIDTHS: [i64; 4] = [200, 176, 340, 120];
pub const DEFAULT_HOTKEY: &str = "Alt+1";
pub const DEFAULT_EFFECT_HOTKEY: &str = "Alt+F12";
const THEMES: [&str; 5] = ["蓝色", "棕色", "紫色", "绿色", "红色"];

#[derive(Debug, Clone, PartialEq)]
pub struct Settings {
    pub hotkey: String,
    pub auto_capture: bool,
    pub auto_resume: bool,
    pub save_debug_frames: bool,
    pub panel_pos: Option<(i64, i64)>,
    pub window_size: Option<(i64, i64)>,
    pub window_geometry: String,
    pub theme: String,
    pub appearance: String,
    pub player_name: String,
    pub custom_tags: Vec<String>,
    pub hidden_tags: Vec<String>,
    pub column_order: Vec<i64>,
    pub column_widths: Vec<i64>,
    pub names_hidden: bool,
    pub env_checked: String,
    pub welcomed: bool,
    pub close_to_tray: bool,
    pub safe_mode: bool,
    pub sound_muted: bool,
    pub scene_sounds: Sounds,
    pub quick_scene: String,
    pub effect_hotkey: String,
    pub dropped_hotkey: String,
    pub dropped_effect_hotkey: String,
    pub stream_mode: String,
    pub consented: Vec<String>,
    pub disclaimer_accepted: bool,
    pub stream_guided: bool,
    /// Up to v0.9.14: 声音 and 嘉宾 › 场景 off, folded in at open (Store::fold_old_settings).
    pub old_volume: i64,
    pub old_scenes_off: bool,
}

impl Default for Settings {
    fn default() -> Self {
        Settings {
            hotkey: DEFAULT_HOTKEY.into(),
            auto_capture: false,
            auto_resume: false,
            save_debug_frames: false,
            panel_pos: None,
            window_size: None,
            window_geometry: String::new(),
            theme: "蓝色".into(),
            appearance: "light".into(),
            player_name: String::new(),
            custom_tags: Vec::new(),
            hidden_tags: Vec::new(),
            column_order: vec![0, 1, 2, 3],
            column_widths: DEFAULT_COLUMN_WIDTHS.to_vec(),
            names_hidden: false,
            env_checked: String::new(),
            welcomed: false,
            close_to_tray: true,
            safe_mode: true,
            sound_muted: false,
            scene_sounds: Vec::new(),
            quick_scene: "classic".into(),
            effect_hotkey: DEFAULT_EFFECT_HOTKEY.into(),
            dropped_hotkey: String::new(),
            dropped_effect_hotkey: String::new(),
            stream_mode: String::new(),
            consented: Vec::new(),
            disclaimer_accepted: false,
            stream_guided: false,
            old_volume: 100,
            old_scenes_off: false,
        }
    }
}

fn pair(value: Option<&Value>) -> Option<(i64, i64)> {
    let list = value?.as_array().filter(|a| a.len() == 2)?;
    Some((py::int(&list[0]).ok()?, py::int(&list[1]).ok()?))
}

fn column_widths(value: Option<&Value>) -> Option<Vec<i64>> {
    let list = value?.as_array().filter(|a| a.len() == 4)?;
    list.iter().map(|v| py::int(v).ok().filter(|w| (72..=2000).contains(w))).collect()
}

/// `isinstance(order, list) and sorted(order) == [0, 1, 2, 3]`, with the TypeError Python's sort raises on a mix.
fn column_order(value: Option<&Value>) -> Res<Option<Vec<i64>>> {
    let Some(Value::Array(list)) = value else { return Ok(None) };
    if list.len() < 2 {
        return Ok(None);
    }
    if list.iter().all(|v| v.is_string()) {
        return Ok(None);
    }
    let Some(mut numbers) = list.iter().map(num).collect::<Option<Vec<f64>>>() else { return py::bad("sort") };
    numbers.sort_by(f64::total_cmp);
    if numbers != [0.0, 1.0, 2.0, 3.0] {
        return Ok(None);
    }
    list.iter().map(py::int).collect::<Res<Vec<i64>>>().map(Some)
}

/// Store._load_settings on a file read whole, into `s` as Python fills `self`: on Err (the file is set aside by the
/// caller) what was read before the error stays, as it does in Python.
pub fn read(data: &Value, sound_folder: &Path, s: &mut Settings) -> Res<()> {
    let map = dict(data)?;
    let get = |k: &str| map.get(k);
    let text = |k: &str| get(k).filter(|v| truthy(v)).map_or(String::new(), py_str);
    let flag = |k: &str, default: bool| get(k).map_or(default, truthy);
    let saved = Some(text("hotkey")).filter(|t| !t.is_empty()).unwrap_or_else(|| DEFAULT_HOTKEY.into());
    let hotkey = two_keys(&saved);
    let check = parse_hotkey(&hotkey);
    s.dropped_hotkey = if check.is_none() { saved } else { String::new() };
    s.hotkey = check.map_or_else(|| DEFAULT_HOTKEY.into(), |c| c.0);
    s.auto_capture = flag("auto_capture", false);
    s.auto_resume = flag("auto_resume", false);
    s.save_debug_frames = flag("save_debug_frames", false);
    s.panel_pos = pair(get("panel_pos"));
    s.window_size = pair(get("window_size")).filter(|(w, h)| *w > 0 && *h > 0).map(|(w, h)| (w.max(900), h.max(560)));
    s.window_geometry = text("window_geometry");
    let theme = text("theme");
    if THEMES.contains(&theme.as_str()) {
        s.theme = theme;
    }
    let appearance = text("appearance");
    if ["light", "dark", "system"].contains(&appearance.as_str()) {
        s.appearance = appearance;
    }
    s.player_name = cut(&clean_stored_name(&text("player_name")), MAX_NAME);
    s.custom_tags.clear();
    s.hidden_tags.clear();
    if let Some(order) = column_order(get("column_order"))? {
        s.column_order = order;
    }
    if let Some(widths) = column_widths(get("column_widths")) {
        s.column_widths = widths;
    }
    s.names_hidden = flag("names_hidden", false);
    s.env_checked = text("env_checked");
    s.welcomed = flag("welcomed", true);
    s.close_to_tray = flag("close_to_tray", true);
    s.safe_mode = flag("safe_mode", true);
    let muted = match get("sound_muted") {
        Some(v) => v.clone(),
        None => json!(get("love_music") == Some(&json!("off"))),
    };
    s.sound_muted = muted == json!(true);
    s.scene_sounds = scene_sounds(get("scene_sounds"), sound_folder, get("scene_songs") != Some(&json!(true)));
    let scene = shown(&text("quick_scene"));
    s.quick_scene = if SCENE_KEYS.contains(&scene.as_str()) { scene } else { "classic".into() };
    let saved_effect = get("effect_hotkey").cloned().unwrap_or(json!(DEFAULT_EFFECT_HOTKEY));
    let effect_text = if truthy(&saved_effect) { py_str(&saved_effect) } else { String::new() };
    let effect = parse_hotkey(&two_keys(&effect_text));
    s.effect_hotkey = if saved_effect == json!("") {
        String::new()
    } else {
        effect.as_ref().map_or_else(|| DEFAULT_EFFECT_HOTKEY.into(), |e| e.0.clone())
    };
    s.dropped_effect_hotkey = if effect.is_none() { effect_text } else { String::new() };
    if s.hotkey == s.effect_hotkey {
        if get("hotkey").is_some_and(truthy) && s.dropped_hotkey.is_empty() {
            s.effect_hotkey = String::new();
        } else {
            s.hotkey = String::new();
        }
    }
    s.stream_mode = if matches!(get("stream_mode").and_then(Value::as_str), Some("on" | "key" | "alpha")) { "on".into() } else { String::new() };
    s.disclaimer_accepted = get("disclaimer_accepted") == Some(&json!(true));
    s.stream_guided = get("stream_guided") == Some(&json!(true));
    let agreed = get("consented").filter(|v| truthy(v)).cloned().unwrap_or(json!([]));
    s.consented = ["full", "auto"].iter().filter(|m| agreed.as_array().is_some_and(|a| a.contains(&json!(m)))).map(|m| m.to_string()).collect();
    for raw in py::iter(&get("hidden_tags").filter(|v| truthy(v)).cloned().unwrap_or(json!([])))? {
        let tag = clean_tag(&py_str(&raw));
        if TAGS.contains(&tag.as_str()) && !s.hidden_tags.contains(&tag) {
            s.hidden_tags.push(tag);
        }
    }
    for raw in py::iter(&get("custom_tags").filter(|v| truthy(v)).cloned().unwrap_or(json!([])))? {
        s.add_custom_tag(&py_str(&raw));
    }
    s.old_volume = volume(get("sound_volume").unwrap_or(&Value::Null));
    s.old_scenes_off = get("love_scene") == Some(&json!("off"));
    Ok(())
}

impl Settings {
    /// Store.tag_catalog: the built-in tags not hidden, then the player's own.
    pub fn tag_catalog(&self) -> Vec<String> {
        let mut names: Vec<String> = TAGS.iter().filter(|t| !self.hidden_tags.iter().any(|h| h == *t)).map(|t| t.to_string()).collect();
        for tag in &self.custom_tags {
            if !names.contains(tag) {
                names.push(tag.clone());
            }
        }
        names
    }

    /// Store.add_custom_tag.
    pub fn add_custom_tag(&mut self, raw: &str) -> bool {
        let tag = clean_tag(raw);
        if tag.is_empty() || self.tag_catalog().contains(&tag) {
            return false;
        }
        if TAGS.contains(&tag.as_str()) {
            self.hidden_tags.retain(|t| *t != tag);
        } else if self.custom_tags.len() >= 24 {
            return false;
        } else {
            self.custom_tags.push(tag);
        }
        true
    }

    /// Store.save_settings' payload, key for key.
    pub fn to_value(&self) -> Value {
        let mut sounds = Map::new();
        for (key, entry) in self.scene_sounds.iter().filter(|(_, e)| !e.is_default()) {
            sounds.insert(key.clone(), entry.to_value());
        }
        let pair = |p: Option<(i64, i64)>| p.map_or(Value::Null, |(a, b)| json!([a, b]));
        json!({
            "hotkey": self.hotkey,
            "auto_capture": self.auto_capture,
            "auto_resume": self.auto_resume,
            "save_debug_frames": self.save_debug_frames,
            "panel_pos": pair(self.panel_pos),
            "window_size": pair(self.window_size),
            "window_geometry": self.window_geometry,
            "theme": self.theme,
            "appearance": self.appearance,
            "player_name": self.player_name,
            "custom_tags": self.custom_tags,
            "hidden_tags": self.hidden_tags,
            "column_order": self.column_order,
            "column_widths": self.column_widths,
            "names_hidden": self.names_hidden,
            "env_checked": self.env_checked,
            "welcomed": self.welcomed,
            "close_to_tray": self.close_to_tray,
            "safe_mode": self.safe_mode,
            "sound_muted": self.sound_muted,
            "scene_sounds": sounds,
            "scene_songs": true,
            "quick_scene": self.quick_scene,
            "effect_hotkey": self.effect_hotkey,
            "stream_mode": self.stream_mode,
            "consented": self.consented,
            "disclaimer_accepted": self.disclaimer_accepted,
            "stream_guided": self.stream_guided,
        })
    }
}
