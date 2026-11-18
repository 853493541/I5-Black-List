//! The real exe's wiring (ui.py MainWindow and __main__.py, outside the drawing): start-up, the check flow, the
//! worker thread, update timing, the tray, closing. The parts other packages build are traits in `stubs`.

pub mod engine;
pub mod flow;
pub mod life;
pub mod records;
pub mod runner;
pub mod startup;
pub mod stubs;
pub mod watch;
pub mod worker;

#[cfg(test)]
mod flow_tests;
