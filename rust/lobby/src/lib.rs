//! lobby: part of the Rust rewrite of 模仿者小工具 (see docs/dev/research/rust-plan-2026-11-18.md).
//!
//! A pure-logic port of `blacklist_detect/layout.py` (the lobby header, its name boxes) and
//! `blacklist_detect/match.py` (names read against the lists). No OCR and no images: the lines come in read.
#![forbid(unsafe_code)]

pub mod anchor;
pub mod header;
pub mod matching;
pub mod model;
pub mod text;

pub use anchor::{find_anchor, game_screen, ready_strip, Anchor, PxBox, NAME_BOXES};
pub use header::{contains_title, countdown_in, ready_in};
pub use matching::{
    clean_stored_name, fold, format_hit, is_lobby_chrome, last_seen, listed_tail, match_label, normalize_text, seat_number,
    split_ellipsis, strip_noise, with_game_ellipsis, MatchKind, NameLabel, NameMatch, Scan, ScanSeat,
};
pub use model::{Combo, Entry, OcrLine, Rect, Scenes};
