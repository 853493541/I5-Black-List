//! The real exe's wiring (ui.py MainWindow and __main__.py, outside the drawing): start-up, the check flow, the
//! worker thread, update timing, the tray, closing. The parts other packages build are traits in `stubs`.

pub mod assemble;
pub mod debug;
pub mod engine;
pub mod envtest;
pub mod export;
pub mod flow;
pub mod life;
pub mod marks;
pub mod parts;
pub mod preview_play;
pub mod quick;
pub mod records;
pub mod runner;
pub mod scenes;
pub mod startup;
pub mod stubs;
pub mod updates;
pub mod watch;
pub mod worker;

#[cfg(test)]
mod flow_tests;
