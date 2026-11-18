//! ScenePane's rules (ui_guest_scenes.ScenePane): 播放场景 over 随机 and every scene, each with its box.
//!
//! 播放场景 off is 不放 (every box empty, their ticks kept while the dialog is open); on, 随机 or the scenes ticked.
//! A scene ticked unticks 随机, 随机 ticked unticks every scene, and the last scene unticked is 随机. A box ticked
//! with 播放场景 off turns it on, with that one alone. Opened and saved untouched, the value is what was saved.

use super::{known, shown, Scenes, RANDOM, SCENES};

#[derive(Debug, Clone)]
pub struct Pane {
    saved: Scenes,
    on: bool,
    // The boxes ticked, 随机 included, in the list's order.
    chosen: Vec<String>,
    kept: Vec<String>,
    opened: (bool, Vec<String>),
    /// The row highlighted: the scene the preview shows.
    pub selected: String,
}

impl Pane {
    pub fn new(saved: Scenes) -> Self {
        let mut kept: Vec<String> = Vec::new();
        if !saved.random {
            for key in saved.keys.iter().map(|key| shown(key)).filter(|key| known(key)) {
                if !kept.iter().any(|k| k == key) {
                    kept.push(key.to_string());
                }
            }
        }
        let mut pane = Pane { on: !saved.off(), saved, chosen: Vec::new(), kept, opened: (false, Vec::new()), selected: String::new() };
        if pane.on {
            pane.set_chosen(&pane.kept_or_random());
        }
        pane.opened = pane.shown();
        // The first ticked in the list (随机 too), else 经典.
        let first = pane.scenes().into_iter().next().or_else(|| pane.ticked(RANDOM.0).then(|| RANDOM.0.to_string()));
        pane.selected = first.unwrap_or_else(|| SCENES[0].0.to_string());
        pane
    }

    pub fn playing(&self) -> bool {
        self.on
    }

    /// Whether this row's box is ticked.
    pub fn ticked(&self, key: &str) -> bool {
        self.chosen.iter().any(|k| k == key)
    }

    /// The scenes ticked, in the list's order; 随机 is none.
    pub fn scenes(&self) -> Vec<String> {
        SCENES.iter().map(|(key, _, _)| key.to_string()).filter(|key| self.ticked(key)).collect()
    }

    fn kept_or_random(&self) -> Vec<String> {
        if self.kept.is_empty() {
            vec![RANDOM.0.to_string()]
        } else {
            self.kept.clone()
        }
    }

    fn set_chosen(&mut self, keys: &[String]) {
        self.chosen = keys.iter().map(|key| shown(key).to_string()).collect();
    }

    fn shown(&self) -> (bool, Vec<String>) {
        (self.on, if self.on { self.scenes() } else { Vec::new() })
    }

    /// Their 场景 as the boxes say them; as saved while the boxes say what they opened on.
    pub fn value(&self) -> Scenes {
        let (on, keys) = self.shown();
        if (on, &keys) == (self.opened.0, &self.opened.1) {
            return self.saved.clone();
        }
        if !on {
            return Scenes::default();
        }
        if keys.is_empty() {
            Scenes::any()
        } else {
            Scenes { keys, random: false }
        }
    }

    pub fn has_changes(&self) -> bool {
        self.shown() != self.opened
    }

    /// 播放场景 clicked: on, the ticks it had back, or 随机; off, every box empty, their ticks kept.
    pub fn toggle_play(&mut self) {
        self.on = !self.on;
        if self.on {
            self.set_chosen(&self.kept_or_random());
        } else {
            self.kept = self.scenes();
            self.chosen.clear();
        }
    }

    /// A row's box clicked.
    pub fn tick(&mut self, key: &str) {
        if !self.on {
            self.kept = if key == RANDOM.0 { Vec::new() } else { vec![key.to_string()] };
            self.toggle_play();
            return;
        }
        if self.ticked(key) {
            self.chosen.retain(|k| k != key);
        } else {
            self.chosen.push(key.to_string());
        }
        let keys = self.scenes();
        let next = if key == RANDOM.0 || keys.is_empty() { vec![RANDOM.0.to_string()] } else { keys };
        self.set_chosen(&next);
    }

    /// A row's name clicked: it is highlighted. The scene it plays: its own, or for 随机 one drawn at random,
    /// another than `showing` (`pick` draws an index below the count it is given).
    pub fn pick(&mut self, key: &str, showing: &str, pick: impl FnOnce(usize) -> usize) -> String {
        self.selected = key.to_string();
        if key != RANDOM.0 {
            return key.to_string();
        }
        let others: Vec<&str> = SCENES.iter().map(|(k, _, _)| *k).filter(|k| *k != showing).collect();
        others[pick(others.len()) % others.len()].to_string()
    }
}
