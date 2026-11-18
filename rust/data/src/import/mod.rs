//! 批量导入 and the 嘉宾 scene choice: an exact port of blacklist_detect/importing.py, guests.py and names.py,
//! with the parts of storage.py, match.py and model.py they use. Parity is proven on golden data the Python
//! code writes (tools/rust_golden_import.py, tests/import_golden.rs).

pub mod guests;
pub mod model;
pub mod names;
mod paste;
mod read;
mod suggest;
pub mod tags;
pub mod text;

pub use model::{Combo, Entry, Scenes};
pub use read::{plan_import, read_paste, ImportRow, Person, Status};
pub use suggest::{is_game_word, suggest_tags, with_tags, Record, TagSuggestion, GAME_WORDS};

/// The built-in 标签 as a catalog.
pub fn default_catalog() -> Vec<String> {
    tags::TAGS.iter().map(|tag| tag.to_string()).collect()
}
