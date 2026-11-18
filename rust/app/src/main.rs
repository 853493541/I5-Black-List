//! A look mock-up of 设置, the settings window, in Slint. No logic: fixed values and made-up data.
//!
//! `settings-mock` shows the window. `settings-mock --png <dir>` draws it without a display, through
//! Slint's software renderer, as `<dir>/slint-light.png` and `<dir>/slint-dark.png` at 900 x 560.
//! `MOCK_QUIT_MS=<ms>` closes the shown window after that long and prints the process's memory.

// deny, not forbid: the code Slint generates from ui/ allows unsafe in its own items.
#![deny(unsafe_code)]

mod guestedit;
mod guests;
mod headless;
mod stream;
#[allow(dead_code)] // wired by the app-wiring package
mod settings;

use std::path::PathBuf;

slint::include_modules!();

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    if let Some(at) = args.iter().position(|arg| arg == "--png") {
        let dir = PathBuf::from(args.get(at + 1).ok_or("--png needs a folder")?);
        headless::render_all(&dir)?;
        println!("{}", memory());
        return Ok(());
    }
    let window = SettingsWindow::new()?;
    window.set_dark(args.iter().any(|arg| arg == "--dark"));
    if let Some(ms) = std::env::var("MOCK_QUIT_MS").ok().and_then(|ms| ms.parse::<u64>().ok()) {
        slint::Timer::single_shot(std::time::Duration::from_millis(ms), || {
            println!("{}", memory());
            let _ = slint::quit_event_loop();
        });
    }
    window.run()?;
    Ok(())
}

/// The resident memory now and at its highest, from /proc (Linux only; empty elsewhere).
fn memory() -> String {
    let status = std::fs::read_to_string("/proc/self/status").unwrap_or_default();
    status
        .lines()
        .filter(|line| line.starts_with("VmRSS") || line.starts_with("VmHWM"))
        .map(|line| line.split_whitespace().collect::<Vec<_>>().join(" "))
        .collect::<Vec<_>>()
        .join(", ")
}
