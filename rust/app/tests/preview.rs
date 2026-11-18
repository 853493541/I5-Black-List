//! The preview build (`cargo test -p app --features preview`): the real exe, started twice in a %APPDATA% of the
//! test's own that holds a made-up v1.0.1 folder, copies that folder's lists once into its own data folder and
//! leaves the old files as they were.
#![cfg(feature = "preview")]

use std::path::{Path, PathBuf};
use std::process::Command;

fn start(home: &Path) -> String {
    let status = Command::new(env!("CARGO_BIN_EXE_blacklist-detect"))
        .arg("--quit-after-start")
        .env("APPDATA", home)
        .env("XDG_CONFIG_HOME", home)
        .env("HOME", home)
        .env("USERPROFILE", home)
        .env_remove("BLACKLIST_DETECT_SOUND")
        .status()
        .expect("the exe starts");
    let log = std::fs::read_to_string(home.join(app::preview::FOLDER).join("logs").join("app.log")).unwrap_or_default();
    assert!(status.success(), "exit code; log:\n{log}");
    log
}

fn files(root: &Path) -> Vec<(PathBuf, Vec<u8>, std::time::SystemTime)> {
    let mut found: Vec<_> = ["blacklist.json", "likes.json", "settings.json", "custom_sounds/a.wav"]
        .iter()
        .map(|name| {
            let path = root.join(name);
            (path.clone(), std::fs::read(&path).unwrap(), std::fs::metadata(&path).unwrap().modified().unwrap())
        })
        .collect();
    found.sort();
    found
}

#[test]
fn the_preview_copies_the_old_lists_once_and_never_changes_them() {
    let home = tempfile::tempdir().unwrap();
    let old = home.path().join("BlackListDetect");
    std::fs::create_dir_all(old.join("custom_sounds")).unwrap();
    std::fs::write(old.join("blacklist.json"), r#"{"entries": [{"name": "示例坏人", "reason": "", "tags": []}]}"#).unwrap();
    std::fs::write(old.join("likes.json"), r#"{"entries": []}"#).unwrap();
    std::fs::write(old.join("settings.json"), r#"{"hotkey": "F8"}"#).unwrap();
    std::fs::write(old.join("custom_sounds").join("a.wav"), b"RIFF made-up").unwrap();
    let before = files(&old);

    let log = start(home.path());
    assert!(log.contains(app::preview::NAME), "{log}");
    assert!(log.contains("Preview: copied "), "{log}");
    assert!(log.contains("Start-up: autostart ok (off in the preview)"), "{log}");
    let new = home.path().join(app::preview::FOLDER);
    assert_eq!(std::fs::read(new.join("blacklist.json")).unwrap(), std::fs::read(old.join("blacklist.json")).unwrap());
    assert!(new.join("custom_sounds").join("a.wav").is_file());

    let log = start(home.path());
    assert!(log.contains("Preview: nothing copied from"), "the second run copies nothing:\n{log}");
    assert_eq!(files(&old), before, "old files byte-identical, mtimes unchanged");
    assert!(!old.join("logs").exists(), "nothing is written in the old folder");
}
