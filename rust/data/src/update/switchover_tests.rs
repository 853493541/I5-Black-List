use std::path::Path;

use super::*;

fn put(root: &Path, rel: &str, text: &str) {
    let path = root.join(rel);
    std::fs::create_dir_all(path.parent().unwrap()).unwrap();
    std::fs::write(path, text).unwrap();
}

/// A folder as v1.0.1's launcher leaves it right after laying the switch-over update on.
fn switched(root: &Path) {
    put(root, "模仿者小工具.exe", "launcher");
    put(root, "使用说明.txt", "guide");
    put(root, APP_EXE, "rust app");
    put(root, MARKER, "marker");
    put(root, "blacklist_detect/onnxruntime.dll", "ort");
    put(root, "blacklist_detect/ocr/PP-OCRv5_mobile_det/inference.onnx", "det");
    put(root, FILES_LIST, &[APP_EXE, MARKER, FILES_LIST, "blacklist_detect/onnxruntime.dll", "blacklist_detect/ocr/PP-OCRv5_mobile_det/inference.onnx"].join("\n"));
    // What the Python app left.
    put(root, "runtime/python311.dll", "py");
    put(root, "runtime/Lib/site-packages/PySide6/Qt6Core.dll", "qt");
    put(root, "runtime/I5黑名单.exe", "old name");
    put(root, "blacklist_detect/ui.py", "ui");
    put(root, "blacklist_detect/models/PP-OCRv5_mobile_det/inference.pdiparams", "paddle");
    put(root, "blacklist_detect/assets/app.ico", "icon");
    put(root, "update.old/runtime/模仿者小工具.exe", "python exe");
    put(root, PENDING, "v2.0.0");
}

fn files_under(root: &Path) -> Vec<String> {
    let mut out = Vec::new();
    let mut stack = vec![root.to_path_buf()];
    while let Some(dir) = stack.pop() {
        for entry in std::fs::read_dir(dir).unwrap().flatten() {
            if entry.file_type().unwrap().is_dir() {
                stack.push(entry.path());
            } else {
                out.push(rel_of(root, &entry.path()).unwrap());
            }
        }
    }
    out.sort();
    out
}

#[test]
fn launcher_arguments_are_dropped_and_the_rest_kept() {
    let args = |list: &[&str]| list.iter().map(|item| item.to_string()).collect::<Vec<_>>();
    assert_eq!(app_args(args(&["-m", "blacklist_detect", "--background"])), args(&["--background"]));
    assert_eq!(app_args(args(&["--background"])), args(&["--background"]));
    assert_eq!(app_args(args(&["-m"])), args(&["-m"]));
    assert!(app_args(args(&["-m", "blacklist_detect"])).is_empty());
}

#[test]
fn install_root_is_the_folder_with_the_launcher() {
    let dir = tempfile::tempdir().unwrap();
    switched(dir.path());
    assert_eq!(install_root(&dir.path().join(APP_EXE)), Some(dir.path().to_path_buf()));
    assert_eq!(install_root(&dir.path().join("target/debug/app.exe")), None);
    std::fs::remove_file(dir.path().join("模仿者小工具.exe")).unwrap();
    assert_eq!(install_root(&dir.path().join(APP_EXE)), None);
}

#[test]
fn a_good_start_confirms_and_deletes_the_python_app() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path();
    switched(root);
    let done = after_good_start(root, "v2.0.0");
    assert!(done.confirmed);
    assert_eq!((done.files, done.failed), (6, 0));
    assert_eq!(
        files_under(root),
        vec![
            "blacklist_detect/__init__.py",
            "blacklist_detect/files.txt",
            "blacklist_detect/ocr/PP-OCRv5_mobile_det/inference.onnx",
            "blacklist_detect/onnxruntime.dll",
            "runtime/模仿者小工具.exe",
            "使用说明.txt",
            "模仿者小工具.exe",
        ]
    );
    assert!(!root.join("runtime/Lib").exists() && !root.join("blacklist_detect/models").exists());
    // Once clean, a start changes nothing.
    assert_eq!(after_good_start(root, "v2.0.0"), Cleaned::default());
}

#[test]
fn nothing_is_deleted_while_an_update_waits() {
    for waiting in [STAGED, PARTIAL] {
        let dir = tempfile::tempdir().unwrap();
        switched(dir.path());
        std::fs::create_dir(dir.path().join(waiting)).unwrap();
        let done = after_good_start(dir.path(), "v2.0.0");
        assert!(done.confirmed);
        assert_eq!(done.files, 0);
        assert!(dir.path().join("runtime/python311.dll").is_file());
    }
}

#[test]
fn without_a_proper_file_list_nothing_is_deleted() {
    for list in [None, Some("runtime/模仿者小工具.exe\n"), Some("")] {
        let dir = tempfile::tempdir().unwrap();
        switched(dir.path());
        match list {
            Some(text) => put(dir.path(), FILES_LIST, text),
            None => std::fs::remove_file(dir.path().join(FILES_LIST)).unwrap(),
        }
        assert_eq!(after_good_start(dir.path(), "v2.0.0").files, 0);
        assert!(dir.path().join("blacklist_detect/ui.py").is_file());
    }
}

#[test]
fn a_later_release_drops_files_the_new_list_leaves_out() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path();
    switched(root);
    after_good_start(root, "v2.0.0");
    // v2.0.1 replaces the detection model; the launcher leaves update.check, the new app confirms.
    put(root, "blacklist_detect/ocr/PP-OCRv6_det/inference.onnx", "new det");
    put(root, FILES_LIST, &[APP_EXE, MARKER, FILES_LIST, "blacklist_detect/onnxruntime.dll", "blacklist_detect/ocr/PP-OCRv6_det/inference.onnx"].join("\r\n"));
    put(root, PENDING, "v2.0.1");
    let done = after_good_start(root, "v2.0.1");
    assert!(done.confirmed);
    assert_eq!(done.files, 1);
    assert!(!root.join("blacklist_detect/ocr/PP-OCRv5_mobile_det").exists());
    assert!(root.join("blacklist_detect/ocr/PP-OCRv6_det/inference.onnx").is_file());
}

#[test]
fn the_rust_stager_takes_the_rust_release_layout() {
    let parts = |rel: &str| rel.split('/').map(str::to_string).collect::<Vec<_>>();
    for rel in [APP_EXE, MARKER, FILES_LIST, "blacklist_detect/onnxruntime.dll", "blacklist_detect/ocr/PP-OCRv5_mobile_det/inference.onnx"] {
        let owned = parts(rel);
        let refs: Vec<&str> = owned.iter().map(String::as_str).collect();
        assert!(stage::allowed(&refs), "{rel}");
    }
}
