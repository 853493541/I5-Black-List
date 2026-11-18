use super::*;
use std::time::SystemTime;

/// v1.0.1's folder as a player has it: the lists, 设置, 嘉宾, a custom sound, and files the preview leaves alone.
fn old_folder_with_data(dir: &Path) -> PathBuf {
    let old = dir.join(common::paths::FOLDER_NAME);
    std::fs::create_dir_all(old.join("custom_sounds").join("scene")).unwrap();
    std::fs::create_dir_all(old.join("logs")).unwrap();
    std::fs::create_dir_all(old.join("backups")).unwrap();
    std::fs::write(old.join("blacklist.json"), r#"{"entries": [{"name": "示例坏人", "reason": "", "tags": []}]}"#).unwrap();
    std::fs::write(old.join("likes.json"), r#"[{"name": "心动小鹿"}, {"name": "心动星星"}]"#).unwrap();
    std::fs::write(old.join("settings.json"), r#"{"hotkey": "F8"}"#).unwrap();
    std::fs::write(old.join("custom_sounds").join("scene").join("song.wav"), b"RIFF made-up").unwrap();
    std::fs::write(old.join("logs").join("app.log"), b"old log").unwrap();
    std::fs::write(old.join("backups").join("blacklist.json"), b"[]").unwrap();
    old
}

/// Every file under a folder: its path, bytes and modification time.
fn snapshot(root: &Path) -> Vec<(PathBuf, Vec<u8>, SystemTime)> {
    let mut found = Vec::new();
    let mut stack = vec![root.to_path_buf()];
    while let Some(dir) = stack.pop() {
        for entry in std::fs::read_dir(&dir).unwrap().flatten() {
            let path = entry.path();
            if path.is_dir() {
                stack.push(path);
            } else {
                let modified = std::fs::metadata(&path).unwrap().modified().unwrap();
                found.push((path.clone(), std::fs::read(&path).unwrap(), modified));
            }
        }
    }
    found.sort();
    found
}

#[test]
fn the_first_run_copies_the_old_data_and_leaves_it_as_it_was() {
    let dir = tempfile::tempdir().unwrap();
    let old = old_folder_with_data(dir.path());
    let new = dir.path().join(FOLDER);
    let before = snapshot(&old);
    std::thread::sleep(std::time::Duration::from_millis(20));

    let copied = copy_old_data(&new, &old).unwrap();
    assert_eq!(copied.skipped, None);
    assert_eq!(copied.files, ["blacklist.json", "settings.json", "likes.json", "custom_sounds/scene/song.wav"]);
    for name in ["blacklist.json", "settings.json", "likes.json", "custom_sounds/scene/song.wav"] {
        assert_eq!(std::fs::read(new.join(name)).unwrap(), std::fs::read(old.join(name)).unwrap(), "{name}");
    }
    assert!(!new.join("logs").exists() && !new.join("backups").exists(), "only the lists, 设置, 嘉宾 and sounds");
    assert!(new.join(COPIED_MARK).is_file());
    assert_eq!(snapshot(&old), before, "the old folder's files are byte-identical with the same mtimes");
    assert!(copied.line(&old).contains("blacklist.json"), "{}", copied.line(&old));
}

#[test]
fn a_second_run_copies_nothing() {
    let dir = tempfile::tempdir().unwrap();
    let old = old_folder_with_data(dir.path());
    let new = dir.path().join(FOLDER);
    copy_old_data(&new, &old).unwrap();
    // The player changes the old list after the first run: the preview keeps its own.
    std::fs::write(old.join("blacklist.json"), b"[]").unwrap();
    std::fs::remove_file(new.join("blacklist.json")).unwrap();
    let again = copy_old_data(&new, &old).unwrap();
    assert_eq!(again, Copied { files: vec![], skipped: Some("copied before") });
    assert!(!new.join("blacklist.json").exists());
}

#[test]
fn a_preview_folder_with_data_of_its_own_is_never_overwritten() {
    let dir = tempfile::tempdir().unwrap();
    let old = old_folder_with_data(dir.path());
    let new = dir.path().join(FOLDER);
    std::fs::create_dir_all(&new).unwrap();
    std::fs::write(new.join("settings.json"), b"{}").unwrap();
    let copied = copy_old_data(&new, &old).unwrap();
    assert!(copied.files.is_empty() && copied.skipped.is_some());
    assert_eq!(std::fs::read(new.join("settings.json")).unwrap(), b"{}");
}

#[test]
fn no_old_folder_copies_nothing_and_says_so() {
    let dir = tempfile::tempdir().unwrap();
    let new = dir.path().join(FOLDER);
    let old = dir.path().join(common::paths::FOLDER_NAME);
    let copied = copy_old_data(&new, &old).unwrap();
    assert_eq!(copied, Copied::default());
    assert!(copied.line(&old).starts_with("Preview: nothing to copy"));
    assert!(!old.exists(), "the old folder is not made");
}

#[test]
fn the_preview_has_its_own_key_folder_and_name() {
    let base = win::instance::instance_key_for("player");
    assert_eq!(instance_key(&base, false), base);
    assert_ne!(instance_key(&base, true), base);
    assert!(instance_key(&base, true).starts_with(&base) && instance_key(&base, true).ends_with(KEY_SUFFIX));
    assert_eq!(folder_name(false), common::paths::FOLDER_NAME);
    assert_ne!(folder_name(true), common::paths::FOLDER_NAME);
    assert_eq!(shown_version("0.1.0", false), "0.1.0");
    assert_eq!(format!("模仿者小工具 {}", shown_version("0.1.0", true)), format!("{NAME} 0.1.0"));
}

#[test]
fn the_preview_never_looks_for_updates() {
    struct Counts(std::rc::Rc<std::cell::Cell<u32>>);
    impl crate::wiring::stubs::UpdateCheck for Counts {
        fn check(&mut self) -> bool {
            self.0.set(self.0.get() + 1);
            true
        }
    }
    let calls = std::rc::Rc::new(std::cell::Cell::new(0));
    let mut preview = updater(Box::new(Counts(calls.clone())), true);
    preview.check();
    assert_eq!(calls.get(), 0);
    let mut normal = updater(Box::new(Counts(calls.clone())), false);
    normal.check();
    assert_eq!(calls.get(), 1);
}
