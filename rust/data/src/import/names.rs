//! names.py: what the app is called, and what its files are called.
//!
//! The app was 黑名单检测 until v0.4.2. A folder unzipped before then keeps its old file names when it
//! updates itself, so everything that looks for the launcher or the app's process takes either name, new first.

pub use common::names::{launcher_in, LAUNCHERS, PROCESSES};

pub const APP_NAME: &str = "模仿者小工具";

