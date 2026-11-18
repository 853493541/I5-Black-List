//! The real exe starts in a data folder of its own, runs every start-up step, says so in its log and quits
//! (`--quit-after-start`), before any window opens. On windows-latest this also claims the single-instance mutex.

use std::process::Command;

const STEPS: [&str; 6] = ["data folder", "logs", "single instance", "settings", "autostart", "models"];

fn start(data: &std::path::Path, extra: &[&str]) -> (bool, String) {
    let status = Command::new(env!("CARGO_BIN_EXE_blacklist-detect"))
        .args(["--quit-after-start", "--data"])
        .arg(data)
        .args(extra)
        // Nothing of the player's: %APPDATA% and the home folder point at the test's own folder, and no sound.
        .env("APPDATA", data)
        .env("HOME", data)
        .env("USERPROFILE", data)
        .env_remove("BLACKLIST_DETECT_SOUND")
        .env_remove("BLACKLIST_DETECT_MODEL_DIR")
        .status()
        .expect("the exe starts");
    let log = std::fs::read_to_string(data.join("logs").join("app.log")).unwrap_or_default();
    (status.success(), log)
}

#[test]
fn every_start_up_step_passes_and_the_exe_quits() {
    let dir = tempfile::tempdir().unwrap();
    let (ok, log) = start(dir.path(), &[]);
    assert!(ok, "exit code; log:\n{log}");
    assert!(log.contains("==== Start "), "{log}");
    for step in STEPS {
        assert!(log.contains(&format!("Start-up: {step} ")), "no line for {step}:\n{log}");
    }
    for step in &STEPS[..5] {
        assert!(log.contains(&format!("Start-up: {step} ok")), "{step} did not pass:\n{log}");
    }
    assert!(log.contains("Start-up done; quitting (--quit-after-start)."), "{log}");
    assert!(log.contains("Exit 0"), "{log}");
    assert!(!dir.path().join("logs").join("running").exists(), "the run said it closed");
}

#[test]
fn models_beside_the_data_are_found_through_the_model_variable() {
    let dir = tempfile::tempdir().unwrap();
    let models = dir.path().join("models");
    for kind in ["PP-OCRv5_mobile_det", "PP-OCRv5_mobile_rec"] {
        std::fs::create_dir_all(models.join(kind)).unwrap();
        std::fs::write(models.join(kind).join("inference.onnx"), b"x").unwrap();
    }
    let status = Command::new(env!("CARGO_BIN_EXE_blacklist-detect"))
        .args(["--quit-after-start", "--data"])
        .arg(dir.path())
        .env("APPDATA", dir.path())
        .env("HOME", dir.path())
        .env("USERPROFILE", dir.path())
        .env("BLACKLIST_DETECT_MODEL_DIR", &models)
        .status()
        .unwrap();
    assert!(status.success());
    let log = std::fs::read_to_string(dir.path().join("logs").join("app.log")).unwrap();
    assert!(log.contains("Start-up: models ok"), "{log}");
}

#[test]
fn a_run_that_never_closed_is_said_at_the_next_start() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::create_dir_all(dir.path().join("logs")).unwrap();
    std::fs::write(dir.path().join("logs").join("running"), "").unwrap();
    let (ok, log) = start(dir.path(), &[]);
    assert!(ok);
    assert!(log.contains("The last run ended without closing"), "{log}");
}
