//! Notices: the corner result cards of 基础模式 (检查中, the result, 嘉宾, 没有找到大厅, 检查失败), the
//! toast at the bottom of a window, the red glow round a game with 黑名单 players, the update offer
//! (发现新版本) and the update dialog (正在更新), and the sample game screen. Ported from
//! blacklist_detect/ui_notice.py, ui_kit.Toast, ui_alert.py, ui_update.py and ui_demo.py.
//!
//! The words and the timings live in plain Rust (`corner`, `queue`, `toast`, `update`, `glow`),
//! tested against the Python app; ui/notices/*.slint draws them; `view` fills the Slint windows from
//! the Rust state; `render` draws them without a display for the pictures.
//!
//! For the app-wiring package, what the app must do:
//! - Corner notices: keep one [`queue::CornerNotice`]; call `show_checking` on the hotkey,
//!   `show_result` / `show_missing` / `show_error` when the check ends, `tick(now)` every
//!   [`corner::TICK_MS`] while `visible()`, `hover` and `click` from each card's window. Show one
//!   `NoticeWindow` per visible card at `pos`, never taking the focus, topmost (win crate).
//! - Toast: one [`toast::Toast`] per window; `show_message` returns an id the app keeps its callback
//!   against; when the action is clicked, `act()` says whether to run it.
//! - Update: [`update::UpdateDialog`] turns buttons and download reports into [`update::Effect`]s the
//!   app carries out (download on a thread with data::update::fetch, open the releases page, close,
//!   restart into the launcher after 900 ms).
//! - Glow: the overlay draws [`glow::rings`] with opacity [`glow::breath`] after a [`glow::fade`].

// The app-wiring package calls these; until it lands only the tests do.
#![allow(dead_code)]

pub mod corner;
pub mod glow;
pub mod queue;
#[cfg(test)]
pub mod render;
pub mod toast;
pub mod update;
pub mod view;

/// What the notices ask of the app; the app-wiring package carries these out.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Action {
    /// Run the toast's action (撤销 and the like) kept against this toast id.
    RunToast(u64),
    /// An update dialog effect.
    Update(update::Effect),
    /// 立即更新 on the 发现新版本 card.
    InstallOffered,
    /// 稍后 on the 发现新版本 card: the card closes, 有更新 stays.
    OfferLater,
}

#[cfg(test)]
mod render_tests;
#[cfg(test)]
mod tests;
