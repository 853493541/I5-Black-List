//! 诊断: why a check was slow, the 环境测试 that measures it, and the summary at the top of the logs a friend
//! can send (a port of blacklist_detect/diagnostics.py).
//!
//! Everything here is plain text from plain facts, so it builds and is tested on every system. The facts
//! themselves (CPU, memory, GPUs, Windows, screens, power, CPU times) are read by `win::machine` on Windows
//! and handed in as a [`Machine`]; elsewhere [`Machine::fallback`] stands in. The export file itself is
//! `crate::logs::export::export_logs`. paths.child_env and paths.ocr_threads are `common::paths`. Python's export is one text file, not a zip: so is this one.
//! The steps of 环境测试 (capture, glance, find, read) run in the app; [`FlowTest`] holds their timings and words.

mod flow;
mod machine;
mod summary;

pub use flow::{py_sum, FlowTest, Run, LOBBY_SHARE, SAMPLE_NAMES, SPEED_FINE, SPEED_SLOW, STEPS};
pub use machine::{cpu_numbers, cpu_text, power_note, screens_line, Machine, Screen, SystemTimes};
pub use summary::{desktop_fallback, export_stamp, summary_stamp, summary_text, Settings};
