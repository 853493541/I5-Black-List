//! win: Windows capture, hotkeys, single instance and autostart, ported from blacklist_detect/capture.py,
//! hotkey.py, single.py and autostart.py (docs/dev/research/rust-plan-2026-11-18.md).
//!
//! The pure parts (hotkey text, frame geometry, the instance key, the start-up decision) build and are
//! tested on every system. The Windows calls are compiled on Windows only; each `unsafe` block sits in a
//! small wrapper with a SAFETY comment.

pub mod autostart;
pub mod frame;
pub mod hotkey;
pub mod instance;
pub mod livehime;
pub mod settle;
pub mod wgc;

#[cfg(windows)]
pub mod capture;
#[cfg(windows)]
pub mod global_hotkey;
#[cfg(windows)]
pub mod process;
