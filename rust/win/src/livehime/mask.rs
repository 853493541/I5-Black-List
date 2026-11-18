//! What 直播模式 hides from viewers: a page or a mark that may be on stream never shows a 黑名单 name.
//!
//! The API for the overlay and the UI (ui_widgets.masked_name, MainWindow._names_hidden and ui_stream._marks):
//! - [`masked_name`]: how a 黑名单 name is shown masked: its first character, then a star for each after it.
//! - [`names_hidden`]: whether 黑名单's names are masked on the pages (黑名单, 记录, toasts, questions): by the eye in
//!   黑名单's header, or always while 直播模式 is on. In 直播模式 the eye is locked ([`eye_locked`]).
//! - [`Mark`] and [`mirrored`]: which marks 直播画面 copies for viewers. The red ring and glow say a 黑名单 player is
//!   there, never who: the 黑名单 card with the names is never copied.
//! - [`record_seat`]: how a seat on 记录 is shown, with the name kept apart for 复制名字.

/// First character, then a star for every character after it, and always at least one star; "" stays "".
pub fn masked_name(name: &str) -> String {
    let mut chars = name.chars();
    let Some(first) = chars.next() else { return String::new() };
    let stars = chars.count().max(1);
    format!("{first}{}", "*".repeat(stars))
}

/// Whether the pages mask 黑名单's names: the eye says so, or 直播模式 is on (the page may be on stream).
pub fn names_hidden(eye_hides: bool, stream_mode: bool) -> bool {
    eye_hides || stream_mode
}

/// Whether 黑名单's eye is locked shut: in 直播模式 it cannot show the names.
pub fn eye_locked(stream_mode: bool) -> bool {
    stream_mode
}

/// The marks the app draws over the game.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Mark {
    /// The 嘉宾 card.
    LikeCard,
    /// The ring round the 准备 button and its heart badge (the panel), with a 嘉宾 or 黑名单 player there or 我's 场景.
    Ring,
    /// The mark that clears a 嘉宾-only lobby (shown with the ring in its "liked" mode).
    ClearMark,
    /// The 嘉宾 flower border while it plays.
    Border,
    /// The red glow.
    Glow,
    /// The card with the 黑名单 names (hit_card).
    BlacklistCard,
}

/// Whether 直播画面 copies this mark for viewers: every mark but the 黑名单 card.
pub fn mirrored(mark: Mark) -> bool {
    mark != Mark::BlacklistCard
}

/// The panel's mode, as ui_stream reads it: "liked", "hit", "both" show the ring; "liked" also the clear mark.
pub fn ring_shown(panel_mode: &str) -> bool {
    matches!(panel_mode, "liked" | "hit" | "both")
}

pub fn clear_mark_shown(panel_mode: &str) -> bool {
    panel_mode == "liked"
}

/// A seat on 记录 with a 黑名单 match: what is shown, and the name kept for 复制名字 ("" when nothing is masked).
/// In 直播模式 a matched seat is masked unless its reading was unclear.
pub fn record_seat(name: &str, matched: bool, unclear: bool, stream_mode: bool) -> (String, String) {
    if matched && stream_mode {
        let kept = if unclear { String::new() } else { name.to_string() };
        return (masked_name(name), kept);
    }
    (name.to_string(), String::new())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn names_mask_by_character() {
        assert_eq!(masked_name("示例坏人"), "示***");
        assert_eq!(masked_name("示"), "示*");
        assert_eq!(masked_name(""), "");
        assert!(names_hidden(false, true) && !names_hidden(false, false));
        assert!(!mirrored(Mark::BlacklistCard) && mirrored(Mark::Glow));
        assert_eq!(record_seat("示例坏人", true, false, true), ("示***".into(), "示例坏人".into()));
        assert_eq!(record_seat("示例坏人", true, false, false), ("示例坏人".into(), String::new()));
    }
}
