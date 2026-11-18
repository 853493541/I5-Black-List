//! The download, the unpacking and the restart files, as tests/test_updater.py checks them.

mod common;

use std::io::Write as _;
use std::path::Path;

use data::update::{self, fetch, mirrors, stage, Release, UpdateError, MIRRORS};

fn release(payload: &[u8]) -> Release {
    Release {
        version: "v9.0.0".into(),
        url: format!("{}v9.0.0/BlackListDetect-v9.0.0-update.zip", update::DOWNLOADS),
        sha256: update::sha256_hex(payload),
        size: payload.len() as i64,
        base: "v0.1.0".into(),
        ..Release::default()
    }
}

#[test]
fn the_download_must_match_the_release() {
    let (zips, routes) = (tempfile::tempdir().unwrap(), tempfile::tempdir().unwrap());
    let payload = vec![b'x'; 200_000];
    let wanted = release(&payload);
    let mut seen = Vec::new();
    let mut pages = common::Pages::default().with(&wanted.url, Some((200, payload.clone())));
    let path = fetch::download(&wanted, zips.path(), Some(&mut |got, total| seen.push((got, total))), &mut pages, routes.path()).unwrap();
    assert_eq!(std::fs::read(&path).unwrap(), payload);
    assert_eq!(seen.last(), Some(&(200_000, 200_000)));
    for wrong in [vec![b'y'; 200_000], [payload.as_slice(), b"more"].concat()] {
        let mut pages = common::Pages::default().with(&wanted.url, Some((200, wrong)));
        assert_eq!(fetch::download(&wanted, zips.path(), None, &mut pages, routes.path()), Err(UpdateError::BadDownload));
    }
    assert_eq!(std::fs::read_dir(zips.path()).unwrap().count(), 0);
    // Nothing reachable: said as a failed download.
    let mut pages = common::Pages::default().with(&wanted.url, None);
    assert_eq!(fetch::download(&wanted, zips.path(), None, &mut pages, routes.path()), Err(UpdateError::DownloadFailed));
}

#[test]
fn a_download_that_does_not_match_tries_another_address_and_remembers_it() {
    let (zips, routes) = (tempfile::tempdir().unwrap(), tempfile::tempdir().unwrap());
    let payload = vec![b'q'; 3000];
    let wanted = release(&payload);
    let second = format!("{}{}", MIRRORS[1], wanted.url);
    let mut pages = common::Pages::default().with(&wanted.url, Some((200, vec![b'w'; 3000]))).with(&second, Some((200, payload.clone())));
    let path = fetch::download(&wanted, zips.path(), None, &mut pages, routes.path()).unwrap();
    assert_eq!(std::fs::read(path).unwrap(), payload);
    assert_eq!(mirrors::mirrors(routes.path())[0], MIRRORS[1]);
}

fn update_zip(path: &Path, extra: &[(&str, &[u8])]) {
    let mut bundle = zip::ZipWriter::new(std::fs::File::create(path).unwrap());
    let options = zip::write::SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);
    let files: &[(&str, &[u8])] = &[
        ("BlackListDetect/blacklist_detect/__init__.py", b"__version__ = \"v9.0.0\"\n"),
        ("BlackListDetect/blacklist_detect/new_part.py", b"NEW = True\n"),
        ("BlackListDetect/模仿者小工具.exe", b"launcher"),
        ("BlackListDetect/使用说明.txt", "新的说明".as_bytes()),
    ];
    for (name, data) in files.iter().chain(extra) {
        bundle.start_file(*name, options).unwrap();
        bundle.write_all(data).unwrap();
    }
    bundle.finish().unwrap();
}

#[test]
fn unpacking_keeps_to_the_app_files() {
    let folder = tempfile::tempdir().unwrap();
    let zipped = folder.path().join("u.zip");
    update_zip(
        &zipped,
        &[
            ("BlackListDetect/../evil.txt", b"no"),
            ("BlackListDetect/blacklist_detect/models/x.bin", b"no"),
            ("BlackListDetect/blacklist_detect/__pycache__/x.pyc", b"no"),
            ("BlackListDetect/runtime/python312.dll", b"no"),
            ("Other/blacklist_detect/x.py", b"no"),
            ("BlackListDetect/黑名单检测.exe", b"old launcher"),
            ("BlackListDetect/runtime/I5黑名单.exe", b"old app"),
            ("BlackListDetect/runtime/模仿者小工具.exe", b"app"),
            ("BlackListDetect/blacklist_detect/C:/x.py", b"no"),
        ],
    );
    let root = folder.path().join("app");
    std::fs::create_dir(&root).unwrap();
    let staged = stage::stage(&zipped, &root, "v9.0.0").unwrap();
    let mut names = Vec::new();
    let mut stack = vec![staged.clone()];
    while let Some(dir) = stack.pop() {
        for entry in std::fs::read_dir(dir).unwrap().flatten() {
            if entry.path().is_dir() {
                stack.push(entry.path());
            } else {
                names.push(entry.path().strip_prefix(&staged).unwrap().to_string_lossy().replace('\\', "/"));
            }
        }
    }
    names.sort();
    let want = [".version", "blacklist_detect/__init__.py", "blacklist_detect/new_part.py", "runtime/I5黑名单.exe", "runtime/模仿者小工具.exe", "使用说明.txt", "模仿者小工具.exe", "黑名单检测.exe"];
    assert_eq!(names, want);
    assert_eq!(stage::staged_version(Some(&root)), "v9.0.0");
    assert!(!folder.path().join("evil.txt").exists() && !root.join(stage::PARTIAL).exists());
}

#[test]
fn a_zip_without_the_app_or_a_broken_one_leaves_nothing_to_lay_over() {
    let folder = tempfile::tempdir().unwrap();
    let root = folder.path().join("app");
    std::fs::create_dir(&root).unwrap();
    let empty = folder.path().join("empty.zip");
    zip::ZipWriter::new(std::fs::File::create(&empty).unwrap()).finish().unwrap();
    assert_eq!(stage::stage(&empty, &root, "v9.0.0"), Err(UpdateError::Incomplete));
    let broken = folder.path().join("broken.zip");
    std::fs::write(&broken, b"PK not a zip").unwrap();
    assert_eq!(stage::stage(&broken, &root, "v9.0.0"), Err(UpdateError::Broken));
    assert!(!root.join(stage::STAGED).exists() && !root.join(stage::PARTIAL).exists());
    assert_eq!(stage::staged_version(Some(&root)), "");
}

#[test]
fn an_update_the_launcher_never_lays_over_stops_after_three_restarts() {
    let folder = tempfile::tempdir().unwrap();
    let root = Some(folder.path());
    let tried: Vec<bool> = [1000.0, 1010.0, 1020.0]
        .into_iter()
        .map(|at| {
            stage::confirm_started(root, "v1.0.0");
            stage::note_restart(root, "v1.0.1", at)
        })
        .collect();
    assert_eq!(tried, [true, true, false]);
    // The new version running clears the count; a file that cannot be read goes too.
    stage::confirm_started(root, "v1.0.1");
    assert!(!folder.path().join(stage::TRIES).exists());
    std::fs::write(folder.path().join(stage::TRIES), "{").unwrap();
    stage::confirm_started(root, "v1.0.0");
    assert!(!folder.path().join(stage::TRIES).exists());
    // The launcher's note is read once; update.check and update.old go once the new version runs.
    std::fs::write(folder.path().join(stage::RESULT), " 已更新 \n").unwrap();
    assert_eq!((stage::launcher_result(root), stage::launcher_result(root)), ("已更新".into(), String::new()));
    std::fs::write(folder.path().join(stage::PENDING), "").unwrap();
    std::fs::create_dir(folder.path().join(stage::BACKUP)).unwrap();
    assert!(stage::confirm_started(root, "v1.0.1"));
    assert!(!folder.path().join(stage::BACKUP).exists() && !stage::confirm_started(root, "v1.0.1"));
}

#[test]
fn needs_full_compares_with_the_base() {
    let wanted = Release { base: "v0.4.0".into(), ..release(b"x") };
    assert!(wanted.needs_full("v0.3.0") && !wanted.needs_full("v0.4.0"));
}
