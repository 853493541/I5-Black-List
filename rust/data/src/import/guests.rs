//! guests.py: which 嘉宾场景 greet the 嘉宾 in a lobby.
//!
//! A combination whose 嘉宾 are all in the lobby wins, the one with the most of them first (the earlier one on a
//! tie). Else the 嘉宾 highest on the list with scenes ticked decides; else the highest on 随机: any scene. One on
//! 不放 asks for none and the next in line decides. Then 我 decides, unless a 黑名单 player is there.

use std::collections::{HashMap, HashSet};

use super::model::{Combo, Entry, Scenes};
use super::text::fold;

/// love_scenes.KEYS: the scenes this version plays.
pub const KEYS: [&str; 11] = ["classic", "lace", "ice", "stars", "cyber", "neon", "angel", "equation", "fluffy", "claw", "lyre"];

/// love_scenes.shown: a scene that was replaced is its replacement.
pub fn shown(choice: &str) -> &str {
    if choice == "champagne" { "angel" } else { choice }
}

fn plays(key: &str) -> bool {
    KEYS.contains(&key)
}

/// A choice as love_scenes.choose takes it: a key ("random", "off" included), or keys to pick one of.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Choice {
    One(String),
    Many(Vec<String>),
}

impl Choice {
    fn one(key: &str) -> Self {
        Choice::One(key.to_string())
    }
}

/// The scenes ticked that this version plays, each once.
pub fn ticked(scenes: &Scenes, known: &dyn Fn(&str) -> bool) -> Vec<String> {
    let mut keys: Vec<String> = Vec::new();
    for key in scenes.keys.iter().map(|key| shown(key)) {
        if known(key) && !keys.iter().any(|k| k == key) {
            keys.push(key.to_string());
        }
    }
    keys
}

/// ticked() with the scenes this version plays.
pub fn ticked_here(scenes: &Scenes) -> Vec<String> {
    ticked(scenes, &plays)
}

/// The 嘉宾场景 choice for a lobby with these 嘉宾 present; default with none of them here.
pub fn lobby_choice(likes: &[Entry], combos: &[Combo], present: &[Entry], default: &str) -> Choice {
    if present.is_empty() {
        return Choice::one(default);
    }
    listed(likes, combos, present, &plays).1
}

/// Who greets a lobby with a 场景, "combo", "guest", "me" or "", and the choice.
pub fn lobby_scene(likes: &[Entry], combos: &[Combo], present: &[Entry], me: &Scenes, blacklisted: bool) -> (String, Choice) {
    let (who, choice) = listed(likes, combos, present, &plays);
    if !who.is_empty() || blacklisted || me.off() {
        return (who, choice);
    }
    ("me".into(), pick(asked(me, &plays)))
}

fn listed(likes: &[Entry], combos: &[Combo], present: &[Entry], known: &dyn Fn(&str) -> bool) -> (String, Choice) {
    let here: HashSet<String> = present.iter().map(|like| fold(&like.name)).collect();
    let mut found: Vec<(usize, &Combo)> = Vec::new();
    for combo in combos {
        let members: HashSet<String> = combo.names.iter().map(|name| fold(name)).collect();
        if members.len() >= 2 && members.is_subset(&here) {
            found.push((members.len(), combo));
        }
    }
    // The most 嘉宾 first; a stable sort keeps the earlier first on a tie.
    found.sort_by_key(|(size, _)| std::cmp::Reverse(*size));
    if let Some((_, combo)) = found.iter().find(|(_, combo)| !combo.scenes.off()) {
        return ("combo".into(), pick(asked(&combo.scenes, known)));
    }
    let on: Vec<&Entry> = likes.iter().rev().filter(|like| here.contains(&fold(&like.name)) && !like.scenes.off()).collect();
    for like in &on {
        let keys = asked(&like.scenes, known);
        if !keys.is_empty() {
            return ("guest".into(), pick(keys));
        }
    }
    if on.is_empty() { (String::new(), Choice::one("off")) } else { ("guest".into(), Choice::one("random")) }
}

/// The scenes asked for by ticks: none on 随机, its ticks kept but not used.
fn asked(scenes: &Scenes, known: &dyn Fn(&str) -> bool) -> Vec<String> {
    if scenes.random { Vec::new() } else { ticked(scenes, known) }
}

fn pick(mut keys: Vec<String>) -> Choice {
    match keys.len() {
        0 => Choice::one("random"),
        1 => Choice::One(keys.remove(0)),
        _ => Choice::Many(keys),
    }
}

/// A combination's 嘉宾 as shown, each with whether they are still on 嘉宾.
pub fn members(combo: &Combo, likes: &[Entry]) -> Vec<(String, bool)> {
    let by_key: HashMap<String, &Entry> = likes.iter().map(|like| (fold(&like.name), like)).collect();
    combo
        .names
        .iter()
        .map(|name| match by_key.get(&fold(name)) {
            Some(like) => (like.shown().to_string(), true),
            None => (name.clone(), false),
        })
        .collect()
}
