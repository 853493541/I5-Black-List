//! Which scene plays: love_scenes.SCENES and choose, and LoveBorder's pick / draw_again / heard.
//!
//! The choice itself comes from 嘉宾 settings (guests.lobby_choice in the data / lobby crates): a key,
//! keys to pick one of, any ("random"), or none ("off").

use scenes::pyrand::PyRandom;

/// (key, name in 设置), in the order 设置 lists them. 经典 is the default.
pub const SCENES: [(&str, &str); 11] = [
    ("classic", "经典"),
    ("lace", "玫瑰花边"),
    ("ice", "冰蓝极光"),
    ("stars", "星河许愿"),
    ("cyber", "赛博朋克（一）"),
    ("neon", "赛博朋克（二）"),
    ("angel", "金色传说"),
    ("equation", "数学公式"),
    ("fluffy", "毛茸茸保护协会"),
    ("claw", "演说家遇袭"),
    ("lyre", "竖琴清风"),
];
/// A scene that is gone, and the one a player who chose it gets now.
pub const REPLACED: [(&str, &str); 1] = [("champagne", "angel")];

pub fn keys() -> impl Iterator<Item = &'static str> {
    SCENES.iter().map(|&(key, _)| key)
}

pub fn known(key: &str) -> bool {
    keys().any(|k| k == key)
}

/// A saved 嘉宾场景 choice as this version has it: a scene that was replaced is its replacement.
pub fn shown(choice: &str) -> &str {
    REPLACED.iter().find(|&&(old, _)| old == choice).map_or(choice, |&(_, new)| new)
}

/// A 嘉宾场景 choice: Python's str (a key, "random" or "off") or tuple of keys.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Choice {
    One(String),
    Some(Vec<String>),
}

impl Choice {
    pub fn random() -> Self {
        Self::One("random".into())
    }
}

/// love_scenes.choose: the scene to play for a choice ("" for none). Picked from several, it is never
/// the last one again when another is there; a key this version does not have plays 经典 alone and is
/// left out among others.
pub fn choose(choice: &Choice, last: &str, rng: &mut PyRandom) -> String {
    let several = match choice {
        Choice::One(key) if key == "random" => keys().map(String::from).collect(),
        Choice::One(key) => {
            let key = shown(key);
            return match key {
                "off" => String::new(),
                _ if known(key) => key.to_string(),
                _ => "classic".to_string(),
            };
        }
        Choice::Some(list) => list.clone(),
    };
    let mut ticked: Vec<&str> = Vec::new();
    for key in several.iter().map(|k| shown(k)) {
        if known(key) && !ticked.contains(&key) {
            ticked.push(key);
        }
    }
    if ticked.is_empty() {
        ticked = keys().collect();
    }
    let others: Vec<&str> = ticked.iter().copied().filter(|&k| k != last).collect();
    let pool = if others.is_empty() { ticked } else { others };
    rng.choice(&pool).to_string()
}

/// LoveBorder's pick state: the scene settled for this lobby's play and the one played last.
pub struct Picker {
    /// 嘉宾场景's choice for this lobby.
    pub choice: Choice,
    /// The scene played or heard last: the next one drawn from several is another.
    pub last: String,
    picked: Option<(Choice, String)>,
    rng: PyRandom,
}

impl Picker {
    pub fn new(seed: u32) -> Self {
        Self { choice: Choice::random(), last: String::new(), picked: None, rng: PyRandom::new(seed) }
    }

    /// The scene this lobby's play plays ("" for none), settled now so the 嘉宾 marks can be dressed
    /// for it; once settled it stays, until the choice changes or draw_again.
    pub fn pick(&mut self) -> String {
        match &self.picked {
            Some((choice, scene)) if *choice == self.choice => scene.clone(),
            _ => {
                let scene = choose(&self.choice, &self.last, &mut self.rng);
                self.picked = Some((self.choice.clone(), scene.clone()));
                scene
            }
        }
    }

    /// A new lobby: the next pick draws its own scene.
    pub fn draw_again(&mut self) {
        self.picked = None;
    }

    /// scene's sound greeted a lobby, shown or not: the next one is another.
    pub fn heard(&mut self, scene: &str) {
        self.last = scene.to_string();
    }
}
