//! Stands in for the Rust app in the switch-over test (tools/rust_golden_switchover.py): put at
//! runtime\模仿者小工具.exe, it writes what the launcher started it with to probe.json in the release
//! folder, then does what the app does once it started well (switchover::after_good_start). With
//! SWITCHOVER_PROBE_FAIL set it stops first, as an app that never got going would.
#![forbid(unsafe_code)]

use data::update::switchover;

fn main() {
    let exe = std::env::current_exe().expect("own path");
    let root = switchover::install_root(&exe).unwrap_or_else(|| std::env::current_dir().expect("cwd"));
    let raw: Vec<String> = std::env::args().skip(1).collect();
    let fail = std::env::var_os("SWITCHOVER_PROBE_FAIL").is_some();
    let done = if fail { switchover::Cleaned::default() } else { switchover::after_good_start(&root, env!("CARGO_PKG_VERSION")) };
    let probe = serde_json::json!({
        "exe": exe.to_string_lossy(),
        "raw_args": raw,
        "args": switchover::app_args(raw.clone()),
        "cwd": std::env::current_dir().map(|dir| dir.to_string_lossy().into_owned()).unwrap_or_default(),
        "failed_on_purpose": fail,
        "confirmed": done.confirmed,
        "deleted": done.files,
        "not_deleted": done.failed,
    });
    std::fs::write(root.join("probe.json"), probe.to_string()).expect("probe.json");
    std::process::exit(if fail { 3 } else { 0 });
}
