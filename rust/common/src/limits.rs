//! storage.py's limits and fixed words, which the store and importing both keep, and love_scenes.KEYS.

/// The 标签 every list starts with (storage.TAGS).
pub const TAGS: [&str; 5] = ["炸房", "贴脸", "挂机", "场外", "不尊重底牌"];
/// The longest 标签, in characters.
pub const MAX_TAG: usize = 12;
/// The longest name, in characters.
pub const MAX_NAME: usize = 64;
/// The longest 原因, in characters.
pub const MAX_NOTE: usize = 200;
/// The first line of a list copied with 分享.
pub const SHARE_MARK: &str = "#模仿者小工具 黑名单";
/// What that line said before the app was renamed.
pub const OLD_SHARE_MARKS: [&str; 1] = ["#黑名单检测 名单"];
/// love_scenes.KEYS, in 设置's order.
pub const SCENE_KEYS: [&str; 11] = ["classic", "lace", "ice", "stars", "cyber", "neon", "angel", "equation", "fluffy", "claw", "lyre"];
