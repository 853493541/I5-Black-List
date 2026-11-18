//! What the app changes in the store, each saved as storage.py saves it.

use super::py::{cut, strip};
use super::scans::{self, Seat};
use super::settings::{Settings, DEFAULT_COLUMN_WIDTHS};
use super::sounds::Scenes;
use super::text::{clean_nickname, clean_stored_name, clean_tag, coerce_tags, fold, merge_reason, order_tags, tags_and_reason, MAX_NAME, MAX_NOTE, TAGS};
use super::{Combo, Entry, Like, Store};
use std::io;

const MAX_CUSTOM_TAGS: usize = 24;

impl Store {
    pub fn tag_catalog(&self) -> Vec<String> {
        self.settings.tag_catalog()
    }

    pub fn add_custom_tag(&mut self, raw: &str) -> bool {
        self.settings.add_custom_tag(raw)
    }

    /// Drop a tag, a built-in one too; names that had it lose it.
    pub fn remove_custom_tag(&mut self, raw: &str) -> io::Result<bool> {
        let tag = clean_tag(raw);
        if !self.tag_catalog().contains(&tag) {
            return Ok(false);
        }
        if TAGS.contains(&tag.as_str()) {
            self.settings.hidden_tags.push(tag.clone());
        } else {
            self.settings.custom_tags.retain(|t| *t != tag);
        }
        let mut changed = false;
        for entry in self.entries.iter_mut().filter(|e| e.tags.contains(&tag)) {
            entry.tags.retain(|t| *t != tag);
            changed = true;
        }
        self.save_settings()?;
        if changed {
            self.save_entries()?;
        }
        Ok(true)
    }

    /// Rename a tag on the list and on every name: renamed, same, missing, empty, or taken.
    pub fn rename_tag(&mut self, old_raw: &str, new_raw: &str) -> io::Result<&'static str> {
        let (old, new) = (clean_tag(old_raw), clean_tag(new_raw));
        let catalog = self.tag_catalog();
        if old.is_empty() || !catalog.contains(&old) {
            return Ok("missing");
        }
        if new.is_empty() {
            return Ok("empty");
        }
        if new == old {
            return Ok("same");
        }
        if catalog.contains(&new) {
            return Ok("taken");
        }
        let s: &mut Settings = &mut self.settings;
        let builtin = |t: &str| TAGS.contains(&t);
        if builtin(&old) {
            s.hidden_tags.push(old.clone());
        } else {
            remove_first(&mut s.custom_tags, &old);
        }
        if builtin(&new) {
            remove_first(&mut s.hidden_tags, &new);
        } else if s.custom_tags.len() >= MAX_CUSTOM_TAGS {
            if builtin(&old) {
                remove_first(&mut s.hidden_tags, &old);
            } else {
                s.custom_tags.push(old);
            }
            return Ok("taken");
        } else {
            s.custom_tags.push(new.clone());
        }
        let catalog = self.tag_catalog();
        let mut changed = false;
        for entry in self.entries.iter_mut().filter(|e| e.tags.contains(&old)) {
            let mut replaced: Vec<String> = Vec::new();
            for item in &entry.tags {
                let name = if *item == old { new.clone() } else { item.clone() };
                if !replaced.contains(&name) {
                    replaced.push(name);
                }
            }
            entry.tags = order_tags(&replaced, &catalog);
            changed = true;
        }
        self.save_settings()?;
        if changed {
            self.save_entries()?;
        }
        Ok("renamed")
    }

    fn remember_tags(&mut self, tags: &[String]) -> io::Result<Vec<String>> {
        let mut changed = false;
        for tag in tags {
            changed |= self.add_custom_tag(tag);
        }
        if changed {
            self.save_settings()?;
        }
        Ok(order_tags(tags, &self.tag_catalog()))
    }

    pub fn entry_index(&self, name: &str) -> Option<usize> {
        let key = fold(&clean_stored_name(name));
        self.entries.iter().position(|e| !key.is_empty() && fold(&e.name) == key)
    }

    pub fn like_index(&self, name: &str) -> Option<usize> {
        let key = fold(&clean_stored_name(name));
        self.likes.iter().position(|l| !key.is_empty() && fold(&l.name) == key)
    }

    pub fn contains_name(&self, name: &str) -> bool {
        self.entry_index(name).is_some()
    }

    /// Add one name; None when it has no letters or digits, or is on the list already.
    pub fn add(&mut self, name: &str, reason: &str, tags: &[String]) -> io::Result<Option<Entry>> {
        let cleaned = cut(&clean_stored_name(name), MAX_NAME);
        if cleaned.is_empty() || self.contains_name(&cleaned) {
            return Ok(None);
        }
        let (chosen, detail) = coerce_tags(tags, reason);
        let tags = self.remember_tags(&chosen)?;
        let entry = Entry { name: cleaned, reason: detail, tags, added_at: self.clock.utc_stamp() };
        self.entries.push(entry.clone());
        self.save_entries()?;
        Ok(Some(entry))
    }

    /// Add each (name, tags, reason, None); fold each (name, tags, reason, Some(index)) into that entry: (added, merged).
    pub fn import_rows(&mut self, rows: &[(String, Vec<String>, String, Option<usize>)]) -> io::Result<(usize, usize)> {
        let stamp = self.clock.utc_stamp();
        let mut taken: Vec<String> = self.entries.iter().map(|e| fold(&e.name)).collect();
        let (mut added, mut merged) = (0, 0);
        for (name, tags, reason, target) in rows {
            let cleaned = cut(&clean_stored_name(name), MAX_NAME);
            let key = fold(&cleaned);
            if key.is_empty() {
                continue;
            }
            let (chosen, detail) = coerce_tags(tags, reason);
            let chosen = self.remember_tags(&chosen)?;
            if let Some(target) = target.filter(|t| *t < self.entries.len()) {
                let entry = self.entries[target].clone();
                let old = fold(&entry.name);
                let fuller = key.chars().count() > old.chars().count() && key.starts_with(&old) && !taken.contains(&key);
                let mut all = entry.tags.clone();
                all.extend(chosen.iter().filter(|t| !entry.tags.contains(t)).cloned());
                all.dedup();
                self.entries[target] = Entry {
                    name: if fuller { cleaned } else { entry.name.clone() },
                    reason: merge_reason(&entry.reason, &detail),
                    tags: order_tags(&dedup(all), &self.tag_catalog()),
                    added_at: entry.added_at,
                };
                taken.push(key);
                merged += 1;
                continue;
            }
            if taken.contains(&key) {
                continue;
            }
            taken.push(key);
            self.entries.push(Entry { name: cleaned, reason: detail, tags: chosen, added_at: stamp.clone() });
            added += 1;
        }
        if added > 0 || merged > 0 {
            self.save_entries()?;
        }
        Ok((added, merged))
    }

    pub fn update_at(&mut self, index: usize, name: &str, tags: &[String], reason: &str) -> io::Result<bool> {
        if index >= self.entries.len() {
            return Ok(false);
        }
        let cleaned = cut(&clean_stored_name(name), MAX_NAME);
        let key = fold(&cleaned);
        if cleaned.is_empty() || self.entries.iter().enumerate().any(|(i, o)| i != index && fold(&o.name) == key) {
            return Ok(false);
        }
        let (chosen, reason) = coerce_tags(tags, reason);
        let tags = self.remember_tags(&chosen)?;
        let added_at = self.entries[index].added_at.clone();
        self.entries[index] = Entry { name: cleaned, reason, tags, added_at };
        self.save_entries()?;
        Ok(true)
    }

    pub fn remove_at(&mut self, index: usize) -> io::Result<()> {
        if index < self.entries.len() {
            self.entries.remove(index);
            self.save_entries()?;
        }
        Ok(())
    }

    /// Put the list back as it was (撤销).
    pub fn restore_entries(&mut self, entries: Vec<Entry>) -> io::Result<()> {
        self.entries = entries;
        self.save_entries()
    }

    pub fn clear_entries(&mut self) -> io::Result<()> {
        self.entries.clear();
        self.save_entries()
    }

    /// Add any tag whose word is already in a saved reason; the count of names that got one.
    pub fn recheck_tags(&mut self) -> io::Result<usize> {
        let catalog = self.tag_catalog();
        let mut changed = 0;
        for entry in &mut self.entries {
            let (found, _) = tags_and_reason(&entry.reason, &catalog);
            let mut merged = entry.tags.clone();
            let before = merged.len();
            merged.extend(found.into_iter().filter(|t| !entry.tags.contains(t)));
            if merged.len() == before {
                continue;
            }
            entry.tags = order_tags(&merged, &catalog);
            changed += 1;
        }
        if changed > 0 {
            self.save_entries()?;
        }
        Ok(changed)
    }

    pub fn set_me(&mut self, scenes: &Scenes) -> io::Result<()> {
        self.me = Scenes::of(&scenes.keys, scenes.random);
        self.save_likes()
    }

    /// Add one name to 嘉宾; None when it has no letters or digits, or is there already.
    pub fn add_like(&mut self, name: &str, nickname: &str, reason: &str, scenes: &Scenes) -> io::Result<Option<Like>> {
        let cleaned = cut(&clean_stored_name(name), MAX_NAME);
        if cleaned.is_empty() || self.like_index(&cleaned).is_some() {
            return Ok(None);
        }
        let like = Like {
            name: cleaned,
            reason: cut(strip(reason), MAX_NOTE),
            added_at: self.clock.utc_stamp(),
            nickname: clean_nickname(nickname),
            scenes: Scenes::of(&scenes.keys, scenes.random),
        };
        self.likes.push(like.clone());
        self.save_likes()?;
        Ok(Some(like))
    }

    pub fn update_like(&mut self, index: usize, name: &str, nickname: &str, reason: &str, scenes: &Scenes) -> io::Result<bool> {
        if index >= self.likes.len() {
            return Ok(false);
        }
        let cleaned = cut(&clean_stored_name(name), MAX_NAME);
        if cleaned.is_empty() || self.like_index(&cleaned).is_some_and(|found| found != index) {
            return Ok(false);
        }
        let current = self.likes[index].clone();
        self.likes[index] = Like {
            name: cleaned.clone(),
            reason: cut(strip(reason), MAX_NOTE),
            added_at: current.added_at,
            nickname: clean_nickname(nickname),
            scenes: Scenes::of(&scenes.keys, scenes.random),
        };
        if fold(&current.name) != fold(&cleaned) {
            for combo in &mut self.combos {
                for member in &mut combo.names {
                    if fold(member) == fold(&current.name) {
                        *member = cleaned.clone();
                    }
                }
            }
        }
        self.save_likes()?;
        Ok(true)
    }

    pub fn remove_like(&mut self, index: usize) -> io::Result<()> {
        if index < self.likes.len() {
            self.likes.remove(index);
            self.save_likes()?;
        }
        Ok(())
    }

    /// Move a 嘉宾 to another place (indexes as saved: the last is the top).
    pub fn move_like(&mut self, index: usize, to: usize) -> io::Result<bool> {
        let n = self.likes.len();
        if index >= n || to >= n || index == to {
            return Ok(false);
        }
        let like = self.likes.remove(index);
        self.likes.insert(to, like);
        self.save_likes()?;
        Ok(true)
    }

    pub fn set_combos(&mut self, combos: Vec<Combo>) -> io::Result<()> {
        self.combos = combos;
        self.save_likes()
    }

    pub fn restore_likes(&mut self, likes: Vec<Like>) -> io::Result<()> {
        self.likes = likes;
        self.save_likes()
    }

    pub fn clear_likes(&mut self) -> io::Result<()> {
        self.likes.clear();
        self.save_likes()
    }

    /// added, refreshed, filled, or skipped; the same minute keeps the first record.
    pub fn add_scan(&mut self, names: &[Seat], elapsed: Option<f64>) -> &'static str {
        let names: Vec<Seat> = names.iter().map(|s| Seat { name: cut(&s.name, MAX_NAME), ..s.clone() }).collect();
        let result = scans::add(&mut self.scans, &names, elapsed, self.clock.local());
        if result != "skipped" {
            self.save_scans();
        }
        result
    }

    pub fn remove_scan(&mut self, index: usize) {
        if index < self.scans.len() {
            self.scans.remove(index);
            self.save_scans();
        }
    }

    pub fn clear_scans(&mut self) {
        self.scans.clear();
        self.save_scans();
    }

    /// 清空数据: every name, record and setting dropped, the player's sounds too; the next open is a new app.
    pub fn reset(&mut self) -> io::Result<()> {
        self.entries.clear();
        self.likes.clear();
        self.combos.clear();
        self.me = Scenes::default();
        self.scans.clear();
        self.settings = Settings { column_widths: DEFAULT_COLUMN_WIDTHS.to_vec(), ..Settings::default() };
        let _ = std::fs::remove_dir_all(self.sound_dir());
        self.load_warning.clear();
        self.save_entries()?;
        self.save_likes()?;
        self.save_scans();
        self.save_settings()
    }
}

fn remove_first(list: &mut Vec<String>, item: &str) {
    if let Some(at) = list.iter().position(|t| t == item) {
        list.remove(at);
    }
}

fn dedup(list: Vec<String>) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    for item in list {
        if !out.contains(&item) {
            out.push(item);
        }
    }
    out
}
