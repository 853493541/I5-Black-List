use super::*;
use std::time::SystemTime;

/// A copy of a folder, file by file.
fn copy_dir(from: &Path, to: &Path) {
    std::fs::create_dir_all(to).unwrap();
    for entry in std::fs::read_dir(from).unwrap().flatten() {
        let path = entry.path();
        if path.is_dir() {
            copy_dir(&path, &to.join(entry.file_name()));
        } else {
            std::fs::copy(&path, to.join(entry.file_name())).unwrap();
        }
    }
}

/// v1.0.1's folder as the Python app writes it (rust/data's store golden, made by blacklist_detect/storage.py: the
/// 黑名单 with tags and notes, 嘉宾, 组合, 我, records, 设置 with hotkeys and theme, backups, custom sounds), plus a made-up
/// picture and video among the sounds, and what the preview must leave: logs, the tune cache, update staging, the
/// mirror list, debug captures and a half-written file.
fn old_folder_with_data(dir: &Path) -> PathBuf {
    let old = dir.join(common::paths::FOLDER_NAME);
    copy_dir(&Path::new(env!("CARGO_MANIFEST_DIR")).join("../data/tests/golden/store/migrate/output"), &old);
    std::fs::write(old.join("custom_sounds").join("poster.png"), b"\x89PNG made-up").unwrap();
    std::fs::write(old.join("custom_sounds").join("clip.mp4"), b"made-up video").unwrap();
    for skipped in ["logs", "sounds", "updates", "debug"] {
        std::fs::create_dir_all(old.join(skipped)).unwrap();
        std::fs::write(old.join(skipped).join("x.bin"), b"leave me").unwrap();
    }
    std::fs::write(old.join("mirrors.json"), b"[]").unwrap();
    std::fs::write(old.join("likes.json.tmp"), b"half").unwrap();
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
fn the_first_run_copies_everything_of_the_players_and_leaves_the_old_folder_as_it_was() {
    let dir = tempfile::tempdir().unwrap();
    let old = old_folder_with_data(dir.path());
    let new = dir.path().join(FOLDER);
    // The preview's own log is already there when the copy runs.
    std::fs::create_dir_all(new.join("logs")).unwrap();
    let pristine = dir.path().join("pristine");
    copy_dir(&old, &pristine);
    let before = snapshot(&old);
    std::thread::sleep(std::time::Duration::from_millis(20));

    let copied = copy_old_data(&new, &old).unwrap();
    assert_eq!(copied.skipped, None);
    for name in [
        "blacklist.json", "likes.json", "settings.json", "history.json", "backups/blacklist-2026-11-18.json",
        "backups/likes-2026-11-18.json", "custom_sounds/angel-1.wav", "custom_sounds/angel-2.wav", "custom_sounds/ice-1.wav",
        "custom_sounds/ice-x.wav", "custom_sounds/poster.png", "custom_sounds/clip.mp4",
    ] {
        assert!(copied.files.contains(&name.to_string()), "{name} not in {:?}", copied.files);
        assert_eq!(std::fs::read(new.join(name)).unwrap(), std::fs::read(old.join(name)).unwrap(), "{name}");
    }
    assert_eq!(copied.files.len(), 12, "{:?}", copied.files);
    for left in ["sounds", "updates", "debug", "mirrors.json", "likes.json.tmp", "logs/x.bin"] {
        assert!(!new.join(left).exists(), "{left} is not the player's and stays behind");
    }
    assert!(new.join(COPIED_MARK).is_file());
    assert_eq!(snapshot(&old), before, "the old folder's files are byte-identical with the same mtimes");

    // Read through the data crate, the copy holds everything the old folder held.
    let clock = || data::store::Clock::default();
    let (mine, theirs) = (data::store::Store::open(Some(new.clone()), clock()), data::store::Store::open(Some(pristine), clock()));
    assert_eq!(mine.load_warning, "");
    assert!(!mine.entries.is_empty() && !mine.likes.is_empty() && !mine.combos.is_empty() && !mine.scans.is_empty());
    assert_eq!(mine.entries, theirs.entries, "黑名单 rows, tags and notes");
    assert_eq!(mine.likes, theirs.likes, "嘉宾");
    assert_eq!(mine.combos, theirs.combos, "组合");
    assert_eq!(mine.me, theirs.me, "我");
    assert_eq!(mine.scans, theirs.scans, "records");
    assert_eq!(mine.settings, theirs.settings, "设置");
    assert_eq!(mine.settings.hotkey, "Ctrl+F9");
    assert_eq!(mine.settings.theme, "绿色");
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
