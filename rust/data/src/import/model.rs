//! The parts of model.py that importing and the 嘉宾 scene choice read.

/// model.Scenes: the 场景 a 嘉宾 or a 组合 is greeted with: keys ticked, 随机 (random), or neither (不放).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Scenes {
    pub keys: Vec<String>,
    pub random: bool,
}

impl Scenes {
    /// 不放: neither random nor any scene ticked.
    pub fn off(&self) -> bool {
        !self.random && self.keys.is_empty()
    }
}

impl Default for Scenes {
    /// model.ANY_SCENE: 随机.
    fn default() -> Self {
        Scenes { keys: Vec::new(), random: true }
    }
}

/// model.Entry: one listed player.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Entry {
    pub name: String,
    pub reason: String,
    pub tags: Vec<String>,
    pub added_at: String,
    pub nickname: String,
    pub scenes: Scenes,
}

impl Entry {
    pub fn new(name: &str, reason: &str, tags: &[&str]) -> Self {
        Entry { name: name.into(), reason: reason.into(), tags: tags.iter().map(|t| t.to_string()).collect(), ..Self::default() }
    }

    /// What a lobby shows for this player: the nickname, or the full name.
    pub fn shown(&self) -> &str {
        if self.nickname.is_empty() { &self.name } else { &self.nickname }
    }
}

/// model.Combo: 嘉宾 who, all in one lobby, are greeted by scenes of their own.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Combo {
    pub names: Vec<String>,
    pub scenes: Scenes,
}
