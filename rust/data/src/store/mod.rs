//! The store: an exact port of blacklist_detect/storage.py (the 黑名单, 嘉宾, 记录 and 设置 files) and of paths.py's
//! data folder. It reads every file the Python app wrote and writes what the Python app reads back the same, byte for
//! byte (CRLF on Windows, as Python's write_text gives). Nothing is encrypted or locked: storage.py does neither.

pub mod files;
mod ops;
mod scene_ops;
pub mod share;
pub mod py;
pub mod scans;
pub mod settings;
pub mod sounds;
pub mod text;

use chrono::{DateTime, FixedOffset, Local, NaiveDateTime, Utc};
use py::{cut, dict, py_str, strip, truthy, Res};
use scans::Scan;
use serde_json::{json, Map, Value};
use settings::Settings;
use sounds::{folded, scene_volume, SceneSound, Scenes};
use std::collections::HashSet;
use std::io;
use std::path::{Path, PathBuf};
use text::{clean_nickname, clean_stored_name, coerce_tags, fold, order_tags, MAX_NAME, MAX_NOTE, SCENE_KEYS, TAGS};

/// A 黑名单 entry.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub name: String,
    pub reason: String,
    pub tags: Vec<String>,
    pub added_at: String,
}

/// A 嘉宾: no tags; a nickname shown instead of the name, and the 场景 that greet them.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Like {
    pub name: String,
    pub nickname: String,
    pub reason: String,
    pub added_at: String,
    pub scenes: Scenes,
}

/// 嘉宾 who, all in one lobby, get a scene of their own.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Combo {
    pub names: Vec<String>,
    pub scenes: Scenes,
}

/// The time the store stamps with: this PC's clock, or one fixed (the golden tests replay a frozen clock).
#[derive(Debug, Clone, Copy, Default)]
pub struct Clock {
    pub fixed: Option<DateTime<FixedOffset>>,
}

impl Clock {
    /// `datetime.now().astimezone()`, to the second.
    pub fn local(&self) -> DateTime<FixedOffset> {
        let now = self.fixed.unwrap_or_else(|| Local::now().fixed_offset());
        now.with_timezone(now.offset()) - chrono::Duration::nanoseconds(now.timestamp_subsec_nanos().into())
    }

    /// `datetime.now()`: the wall clock, for backups and set-aside names.
    pub fn naive(&self) -> NaiveDateTime {
        self.local().naive_local()
    }

    /// `datetime.now(timezone.utc).replace(microsecond=0).isoformat()`: when an entry was added.
    pub fn utc_stamp(&self) -> String {
        self.local().with_timezone(&Utc).format("%Y-%m-%dT%H:%M:%S+00:00").to_string()
    }
}

pub struct Store {
    pub root: PathBuf,
    pub clock: Clock,
    pub entries: Vec<Entry>,
    pub likes: Vec<Like>,
    pub combos: Vec<Combo>,
    pub me: Scenes,
    pub scans: Vec<Scan>,
    pub settings: Settings,
    pub load_warning: String,
    unread: HashSet<PathBuf>,
}

impl Store {
    /// Store(root): the files in root (paths.app_dir when None), read now.
    pub fn open(root: Option<PathBuf>, clock: Clock) -> Store {
        let mut store = Store {
            root: root.unwrap_or_else(files::app_dir),
            clock,
            entries: Vec::new(),
            likes: Vec::new(),
            combos: Vec::new(),
            me: Scenes::default(),
            scans: Vec::new(),
            settings: Settings::default(),
            load_warning: String::new(),
            unread: HashSet::new(),
        };
        store.load();
        store
    }

    pub fn blacklist_path(&self) -> PathBuf {
        self.root.join("blacklist.json")
    }
    pub fn likes_path(&self) -> PathBuf {
        self.root.join("likes.json")
    }
    pub fn settings_path(&self) -> PathBuf {
        self.root.join("settings.json")
    }
    pub fn history_path(&self) -> PathBuf {
        self.root.join("history.json")
    }
    pub fn sound_dir(&self) -> PathBuf {
        files::custom_sound_dir(&self.root)
    }

    /// The app opens as new: on a new PC, or after 清空数据.
    pub fn first_run(&self) -> bool {
        !self.settings.welcomed
    }

    /// Read a file: None when it is not there, Some(false) when it did not read (set aside here, with the warning).
    fn read(&mut self, path: &Path, parse: &mut dyn FnMut(&mut Store, &Value) -> Res<()>, kept: &str, held: &str) -> Option<bool> {
        match files::read_json(path) {
            Err(None) => return None,
            Err(Some(_)) => {}
            Ok(data) => {
                if parse(self, &data).is_ok() {
                    return Some(true);
                }
            }
        }
        let backup = files::set_aside(path, self.clock.naive());
        if backup.is_none() {
            self.unread.insert(path.to_path_buf());
        }
        let part = if backup.is_some() { kept } else { held };
        self.load_warning = [self.load_warning.as_str(), part].iter().filter(|p| !p.is_empty()).copied().collect::<Vec<_>>().join("；");
        Some(false)
    }

    pub fn load(&mut self) {
        self.entries.clear();
        self.settings.custom_tags.clear();
        self.settings.hidden_tags.clear();
        self.settings.column_order = vec![0, 1, 2, 3];
        self.settings.column_widths = settings::DEFAULT_COLUMN_WIDTHS.to_vec();
        self.load_warning.clear();
        self.unread.clear();
        self.settings.old_volume = 100;
        self.settings.old_scenes_off = false;
        let (path, folder) = (self.settings_path(), self.sound_dir());
        let mut parse = |s: &mut Store, data: &Value| settings::read(data, &folder, &mut s.settings);
        if self.read(&path, &mut parse, "设置文件坏了，已备份，先用默认设置", "设置文件读不了，这次改动不保存") == Some(false) {
            // The songs uploaded in 场景管理 are still in their folder: back in their 场景's, as for v0.9.15's file.
            let mut merged = sounds::scene_sounds(None, &folder, true);
            for (key, entry) in std::mem::take(&mut self.settings.scene_sounds) {
                sounds::set(&mut merged, &key, entry);
            }
            self.settings.scene_sounds = merged;
        }
        if !self.settings.consented.iter().any(|c| c == "full") {
            self.settings.safe_mode = true;
        }
        if self.settings.safe_mode {
            self.settings.auto_resume = self.settings.auto_resume || self.settings.auto_capture;
            self.settings.auto_capture = false;
        }
        let path = self.blacklist_path();
        let ok = self.read(&path, &mut |s, data| s.read_entries(data), "黑名单文件坏了，已备份，先用空名单", "黑名单文件读不了，这次改动不保存");
        if ok == Some(false) {
            self.entries.clear();
        }
        self.load_likes();
        self.fold_old_settings();
        let (mut discovered, mut stripped) = (false, false);
        let hidden = self.settings.hidden_tags.clone();
        for i in 0..self.entries.len() {
            let kept: Vec<String> = self.entries[i].tags.iter().filter(|t| !hidden.contains(t)).cloned().collect();
            if kept != self.entries[i].tags {
                self.entries[i].tags = kept;
                stripped = true;
            }
            for tag in self.entries[i].tags.clone() {
                if !TAGS.contains(&tag.as_str()) && self.settings.add_custom_tag(&tag) {
                    discovered = true;
                }
            }
            self.entries[i].tags = order_tags(&self.entries[i].tags, &self.settings.tag_catalog());
        }
        let _ = (|| -> io::Result<()> {
            if discovered {
                self.save_settings()?;
            }
            if stripped {
                self.save_entries()?;
            }
            Ok(())
        })();
        self.scans.clear();
        let path = self.history_path();
        let ok = self.read(&path, &mut |s, data| scans::read(data).map(|v| s.scans = v), "记录文件坏了，已备份，先用空记录", "记录文件读不了，这次记录不保存");
        if ok == Some(false) {
            self.scans.clear();
        }
        let collapsed = scans::collapse(self.scans.clone());
        let changed = collapsed.len() != self.scans.len();
        self.scans = collapsed;
        if changed {
            self.save_scans();
        }
    }

    fn read_entries(&mut self, data: &Value) -> Res<()> {
        for item in py::iter(dict(data)?.get("entries").unwrap_or(&json!([])))? {
            let item = dict(&item)?;
            let name = clean_stored_name(&item.get("name").map_or(String::new(), py_str));
            if name.is_empty() {
                continue;
            }
            let reasons = item.get("reasons").filter(|v| truthy(v)).cloned().unwrap_or(json!([]));
            let tags = item.get("tags").cloned().unwrap_or(reasons);
            let tags: Vec<String> = if truthy(&tags) { py::iter(&tags)?.iter().map(py_str).collect() } else { Vec::new() };
            let reason = match item.get("reason") {
                Some(r) => py_str(r),
                None => item.get("note").map_or(String::new(), py_str),
            };
            let (tags, reason) = coerce_tags(&tags, &reason);
            let added_at = item.get("added_at").map_or(String::new(), py_str);
            self.entries.push(Entry { name: cut(&name, MAX_NAME), reason, tags, added_at });
        }
        Ok(())
    }

    fn load_likes(&mut self) {
        self.likes.clear();
        self.combos.clear();
        self.me = Scenes::default();
        let path = self.likes_path();
        let ok = self.read(&path, &mut |s, data| s.read_likes(data), "嘉宾文件坏了，已备份，先用空列表", "嘉宾文件读不了，这次改动不保存");
        if ok == Some(false) {
            self.likes.clear();
            self.combos.clear();
            self.me = Scenes::default();
        }
    }

    fn read_likes(&mut self, data: &Value) -> Res<()> {
        let data = dict(data)?;
        if let Some(Value::Object(me)) = data.get("me") {
            self.me = Scenes::saved(me);
        }
        for item in py::iter(data.get("likes").unwrap_or(&json!([])))? {
            let item = dict(&item)?;
            let name = clean_stored_name(&item.get("name").map_or(String::new(), py_str));
            if name.is_empty() || self.likes.iter().any(|l| fold(&l.name) == fold(&name)) {
                continue;
            }
            let text = |k: &str| item.get(k).map_or(String::new(), py_str);
            self.likes.push(Like {
                name: cut(&name, MAX_NAME),
                reason: cut(strip(&text("reason")), MAX_NOTE),
                added_at: text("added_at"),
                nickname: clean_nickname(&text("nickname")),
                scenes: Scenes::saved(item),
            });
        }
        for item in py::iter(data.get("combos").unwrap_or(&json!([])))? {
            let item = dict(&item)?;
            let mut names: Vec<String> = Vec::new();
            for name in py::iter(item.get("names").unwrap_or(&json!([])))? {
                let raw = py_str(&name);
                let cleaned = cut(&clean_stored_name(&raw), MAX_NAME);
                if !strip(&raw).is_empty() && !names.contains(&cleaned) {
                    names.push(cleaned);
                }
            }
            if names.iter().map(|n| fold(n)).collect::<HashSet<_>>().len() >= 2 {
                self.combos.push(Combo { names, scenes: Scenes::saved(item) });
            }
        }
        Ok(())
    }

    /// Settings saved up to v0.9.14, once, into what took their place (storage._fold_old_settings).
    fn fold_old_settings(&mut self) {
        let old = self.settings.old_volume;
        let folding = old < 100;
        if folding {
            let mut keys: Vec<String> = SCENE_KEYS.iter().map(|k| k.to_string()).collect();
            keys.extend(self.settings.scene_sounds.iter().map(|(k, _)| k.clone()).filter(|k| !SCENE_KEYS.contains(&k.as_str())));
            for key in keys {
                let mut entry = sounds::get(&self.settings.scene_sounds, &key).cloned().unwrap_or(SceneSound { volume: 100, ..Default::default() });
                entry.volume = folded(scene_volume(&json!(entry.volume)), old);
                sounds::set(&mut self.settings.scene_sounds, &key, entry);
            }
        }
        let off = self.settings.old_scenes_off;
        let mut save = || -> io::Result<()> {
            if off {
                self.likes.iter_mut().for_each(|l| l.scenes = Scenes::default());
                self.combos.iter_mut().for_each(|c| c.scenes = Scenes::default());
                if !self.likes.is_empty() || !self.combos.is_empty() {
                    self.save_likes()?;
                }
            }
            if folding || off {
                self.save_settings()?;
            }
            Ok(())
        };
        let _ = save();
        self.settings.old_volume = 100;
        self.settings.old_scenes_off = false;
    }

    /// False for a file not read at open and still there (another program held it): it waits for the next open.
    fn saves(&self, path: &Path) -> bool {
        !self.unread.contains(path)
    }

    pub fn save_likes(&self) -> io::Result<()> {
        let path = self.likes_path();
        if !self.saves(&path) {
            return Ok(());
        }
        files::daily_backup(&path, self.clock.naive());
        let scenes = |base: Map<String, Value>, s: &Scenes| {
            let mut map = base;
            s.save_into(&mut map);
            Value::Object(map)
        };
        let likes: Vec<Value> = self
            .likes
            .iter()
            .map(|l| {
                let base = json!({"name": l.name, "nickname": l.nickname, "reason": l.reason, "added_at": l.added_at});
                scenes(base.as_object().cloned().unwrap_or_default(), &l.scenes)
            })
            .collect();
        let combos: Vec<Value> =
            self.combos.iter().map(|c| scenes(json!({"names": c.names}).as_object().cloned().unwrap_or_default(), &c.scenes)).collect();
        files::atomic_write(&path, &json!({"likes": likes, "combos": combos, "me": scenes(Map::new(), &self.me)}))
    }

    pub fn save_entries(&self) -> io::Result<()> {
        let path = self.blacklist_path();
        if !self.saves(&path) {
            return Ok(());
        }
        files::daily_backup(&path, self.clock.naive());
        let entries: Vec<Value> =
            self.entries.iter().map(|e| json!({"name": e.name, "reason": e.reason, "tags": e.tags, "added_at": e.added_at})).collect();
        files::atomic_write(&path, &json!({ "entries": entries }))
    }

    pub fn save_settings(&self) -> io::Result<()> {
        let path = self.settings_path();
        if !self.saves(&path) {
            return Ok(());
        }
        files::atomic_write(&path, &self.settings.to_value())
    }

    /// Never fails: 记录 are the least of the files, and one that cannot be saved must not cost a check its marks.
    pub fn save_scans(&self) {
        let path = self.history_path();
        if self.saves(&path) {
            let _ = files::atomic_write(&path, &scans::to_value(&self.scans));
        }
    }
}
