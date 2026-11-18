//! The records of `blacklist_detect/model.py` that the lobby and the matching use.

/// A box as left, top, right, bottom, in pixels of the capture (or fractions of the reference shot).
pub type Rect = [f64; 4];

/// One line the reader found: its text, how sure it is, and where it is.
#[derive(Debug, Clone, PartialEq)]
pub struct OcrLine {
    pub text: String,
    pub confidence: f64,
    pub bbox: Rect,
}

impl OcrLine {
    pub fn new(text: impl Into<String>, confidence: f64, bbox: Rect) -> Self {
        Self { text: text.into(), confidence, bbox }
    }
}

/// The 场景 a 嘉宾 or a 组合 is greeted with: keys ticked, 随机, or 不放 (neither).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Scenes {
    pub keys: Vec<String>,
    pub random: bool,
}

impl Scenes {
    /// 随机: any scene.
    pub fn any() -> Self {
        Self { keys: Vec::new(), random: true }
    }

    /// 不放: neither random nor any scene ticked.
    pub fn off(&self) -> bool {
        !self.random && self.keys.is_empty()
    }
}

impl Default for Scenes {
    fn default() -> Self {
        Self::any()
    }
}

/// One listed player: the name, a written reason, tags, when it was added, and for a 嘉宾 its nickname and scenes.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Entry {
    pub name: String,
    pub reason: String,
    pub tags: Vec<String>,
    pub added_at: String,
    pub nickname: String,
    pub scenes: Scenes,
}

impl Entry {
    pub fn named(name: impl Into<String>) -> Self {
        Self { name: name.into(), ..Self::default() }
    }

    /// What a lobby shows for this player: the nickname, or the full name.
    pub fn shown(&self) -> &str {
        if self.nickname.is_empty() {
            &self.name
        } else {
            &self.nickname
        }
    }
}

/// 嘉宾 who, all in one lobby, are greeted by scenes of their own.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Combo {
    pub names: Vec<String>,
    pub scenes: Scenes,
}
