//! The 嘉宾 场景 dialogs: 添加嘉宾 / 编辑嘉宾 (ui_likes.LikeDialog), 添加组合 / 编辑组合 (ui_guests.ComboDialog) and
//! 场景管理 (ui_effects.EffectsDialog), drawn by ui/guestedit/*.slint.
//!
//! For the app-wiring package: open a dialog with `dialogs::guest`, `dialogs::combo` or `dialogs::scene_manager`,
//! each taking what it shows and a handler. What the player asks of the app comes out through that handler:
//! - `GuestAction` for 添加嘉宾 / 编辑嘉宾: `Save` (check the name with the data crate's fold and clean_stored_name,
//!   then `GuestDialog::set_name_error` with 请填写名字 / 名字里要有文字或数字 / 已经是嘉宾了 / 已经在黑名单里了, or
//!   store it and close), `Delete`, `Close`, `Play` (play this scene over the sample lobby, silent, in the
//!   preview: the stage package's frames go into the dialog's `frame`), `Replay` (▶: the scene showing from its start).
//! - `ComboAction` for 添加组合 / 编辑组合: the same, `Save` carrying the 嘉宾 ticked (至少选两位嘉宾 and
//!   已有这几位嘉宾的组合 are said through `ComboDialog::set_people_error`).
//! - `SceneAction` for 场景管理: `Show` a scene, `GiveHotkey` (store.quick_scene, saved), `Play` (▶ 播放 with its
//!   music), `Volume`, `ChooseSong`, `Listen`, `Upload`, `Hotkey` (a new key for the 场景 hotkey), `Close`.
//!
//! The 场景 ticks themselves are kept here (pane.rs, ScenePane's rules); `Save` carries their value.

// The dialogs are opened by the app-wiring package; until it lands, only the tests and the renderer use them.
#![allow(dead_code)]

pub mod dialogs;
pub mod pane;
pub mod poster;
#[cfg(test)]
mod render;
#[cfg(test)]
mod tests;

use slint::Color;

/// 随机's key and name, the first row of every ScenePane list (ui_love_pick.RANDOM).
pub const RANDOM: (&str, &str) = ("random", "随机");
const RANDOM_DOT: u32 = 0xa0d23c;

/// love_scenes.SCENES with each scene's dot, its look's glow (ui_overlay.LOOKS): the order every list shows.
// stub: scenes. The scenes crate will own this catalog; the keys, names and colours are the Python app's.
pub const SCENES: [(&str, &str, u32); 11] = [
    ("classic", "经典", 0xe9c987),
    ("lace", "玫瑰花边", 0xff96c8),
    ("ice", "冰蓝极光", 0x6ebeff),
    ("stars", "星河许愿", 0xb9a3ff),
    ("cyber", "赛博朋克（一）", 0x21f6ff),
    ("neon", "赛博朋克（二）", 0xff2bd6),
    ("angel", "金色传说", 0xffd078),
    ("equation", "数学公式", 0x7fd8ff),
    ("fluffy", "毛茸茸保护协会", 0x6ccdc4),
    ("claw", "演说家遇袭", 0xb08cff),
    ("lyre", "竖琴清风", 0x38b66a),
];

/// love_scenes.shown: a scene that was replaced is its replacement.
pub fn shown(key: &str) -> &str {
    if key == "champagne" {
        "angel"
    } else {
        key
    }
}

/// Whether this version plays the scene.
pub fn known(key: &str) -> bool {
    SCENES.iter().any(|(k, _, _)| *k == key)
}

/// model.Scenes, the shape of the data crate's `store::Scenes`: the keys ticked and whether 随机; neither is 不放.
// stub: data. The app crate does not depend on the data crate yet; the wiring copies the two fields across.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Scenes {
    pub keys: Vec<String>,
    pub random: bool,
}

impl Scenes {
    pub fn off(&self) -> bool {
        !self.random && self.keys.is_empty()
    }

    pub fn any() -> Self {
        Scenes { keys: Vec::new(), random: true }
    }

    pub fn of(keys: &[&str]) -> Self {
        Scenes { keys: keys.iter().map(|key| key.to_string()).collect(), random: false }
    }
}

/// What 添加嘉宾 / 编辑嘉宾 asks of the app.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GuestAction {
    Save { name: String, nickname: String, reason: String, scenes: Scenes },
    Delete,
    Close,
    Play(String),
    Replay,
}

/// What 添加组合 / 编辑组合 asks of the app: `Save` carries the 嘉宾 ticked, in the list's saved order.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ComboAction {
    Save { names: Vec<String>, scenes: Scenes },
    Delete,
    Close,
    Play(String),
    Replay,
}

/// What 场景管理 asks of the app.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SceneAction {
    Show(String),
    GiveHotkey(String),
    Play,
    Volume(i32),
    ChooseSong(usize),
    Listen(usize),
    Upload,
    Hotkey(String),
    Close,
}

/// A scene's dot colour in the lists.
pub fn dot(key: &str) -> Color {
    let rgb = if key == RANDOM.0 {
        RANDOM_DOT
    } else {
        SCENES.iter().find(|(k, _, _)| *k == key).map_or(SCENES[0].2, |(_, _, rgb)| *rgb)
    };
    Color::from_rgb_u8((rgb >> 16) as u8, (rgb >> 8) as u8, rgb as u8)
}
