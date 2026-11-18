//! The Rust updater gives what updater.py gives on the golden cases (tools/rust_golden_update.py).

mod common;

use data::update::{self, fetch, mirrors, stage, MIRROR_FILE};
use serde_json::Value;

fn strings(value: &Value) -> Vec<String> {
    value.as_array().unwrap().iter().map(|item| item.as_str().unwrap().to_string()).collect()
}

#[test]
fn versions_compare_as_in_python() {
    for (text, want) in common::golden()["versions"].as_object().unwrap() {
        let want: Vec<i64> = want.as_array().unwrap().iter().map(|n| n.as_i64().unwrap()).collect();
        assert_eq!(update::parse_version(text), want, "{text:?}");
    }
}

#[test]
fn proxies_are_kept_as_in_python() {
    for (text, want) in common::golden()["good_mirror"].as_object().unwrap() {
        assert_eq!(update::good_mirror(text), want.as_bool().unwrap(), "{text:?}");
    }
}

#[test]
fn the_route_is_chosen_as_in_python() {
    let folder = tempfile::tempdir().unwrap();
    let path = folder.path().join(MIRROR_FILE);
    for case in common::golden()["mirrors"].as_array().unwrap() {
        let _ = std::fs::remove_file(&path);
        if let Some(text) = case["file"].as_str() {
            std::fs::write(&path, text).unwrap();
        }
        assert_eq!(mirrors::mirrors(folder.path()), strings(&case["order"]), "{:?}", case["file"]);
    }
}

#[test]
fn the_route_is_remembered_as_in_python() {
    let folder = tempfile::tempdir().unwrap();
    let path = folder.path().join(MIRROR_FILE);
    for case in common::golden()["remember"].as_array().unwrap() {
        let _ = std::fs::remove_file(&path);
        if let Some(text) = case["before"].as_str() {
            std::fs::write(&path, text).unwrap();
        }
        mirrors::remember(folder.path(), case["preferred"].as_str().unwrap(), &strings(&case["listed"]));
        assert_eq!(std::fs::read_to_string(&path).unwrap(), case["after"].as_str().unwrap(), "{:?}", case["before"]);
    }
}

#[test]
fn version_json_is_read_as_in_python() {
    for case in common::golden()["manifests"].as_array().unwrap() {
        let text = case["text"].as_str().unwrap();
        match update::read_manifest(text.as_bytes()) {
            Ok(release) => {
                let want = &case["release"];
                assert!(want.is_object(), "{text} was refused in Python");
                assert_eq!(release.version, want["version"].as_str().unwrap(), "{text}");
                assert_eq!(release.url, want["url"].as_str().unwrap());
                assert_eq!(release.sha256, want["sha256"].as_str().unwrap());
                assert_eq!(release.size, want["size"].as_i64().unwrap());
                assert_eq!(release.base, want["base"].as_str().unwrap(), "{text}");
                assert_eq!(release.notes, strings(&want["notes"]), "{text}");
                assert_eq!(release.mirrors, strings(&want["mirrors"]), "{text}");
            }
            Err(error) => assert_eq!(Some(error.message()), case["error"].as_str(), "{text}"),
        }
    }
}

#[test]
fn the_signature_check_accepts_what_python_accepts() {
    let golden = common::golden();
    for case in golden["verify"].as_array().unwrap() {
        let (manifest, signature) = (case["manifest"].as_str().unwrap(), case["signature"].as_str().unwrap());
        let ok = update::verify(manifest.as_bytes(), signature, case["key"].as_str());
        assert_eq!(ok, case["ok"].as_bool().unwrap(), "{signature:?} key {:?}", case["key"]);
    }
}

#[test]
fn the_published_v1_0_1_is_signed_by_the_release_key() {
    let folder = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/golden/update/");
    let manifest = std::fs::read(format!("{folder}version.json")).unwrap();
    let signature = std::fs::read_to_string(format!("{folder}version.json.sig")).unwrap();
    assert!(update::verify(&manifest, &signature, None));
    let release = update::read_manifest(&manifest).unwrap();
    assert_eq!((release.version.as_str(), release.size), ("v1.0.1", 9_101_938));
    // Any byte changed in either file is refused.
    for at in [0, manifest.len() / 2, manifest.len() - 1] {
        let mut tampered = manifest.clone();
        tampered[at] ^= 1;
        assert!(!update::verify(&tampered, &signature, None), "byte {at}");
    }
    let bytes = update::py::b64decode(&signature).unwrap();
    for at in [0, 31, 32, 63] {
        let mut forged = bytes.clone();
        forged[at] ^= 0x80;
        assert!(!update::verify(&manifest, &update::b64encode(&forged), None), "signature byte {at}");
    }
}

#[test]
fn a_whole_fetch_goes_as_in_python() {
    let golden = common::golden();
    let key = golden["public"].as_str().unwrap();
    for case in golden["fetch"].as_array().unwrap() {
        let folder = tempfile::tempdir().unwrap();
        if let Some(text) = case["before"].as_str() {
            std::fs::write(folder.path().join(MIRROR_FILE), text).unwrap();
        }
        let mut pages = common::Pages::from_golden(&case["pages"]);
        let got = fetch::fetch_release(&mut pages, case["current"].as_str().unwrap(), folder.path(), Some(key));
        let name = case["name"].as_str().unwrap();
        match got {
            Ok(Some(release)) => {
                assert_eq!(release.version, case["release"]["version"].as_str().unwrap(), "{name}");
                assert_eq!(release.mirror, case["release"]["mirror"].as_str().unwrap(), "{name}");
                assert_eq!(release.mirrors, strings(&case["release"]["mirrors"]), "{name}");
            }
            Ok(None) => assert!(case["release"].is_null() && case["error"].is_null(), "{name}"),
            Err(error) => assert_eq!(Some(error.message()), case["error"].as_str(), "{name}"),
        }
        assert_eq!(pages.asked, strings(&case["asked"]), "{name}");
        let after = std::fs::read_to_string(folder.path().join(MIRROR_FILE)).ok();
        assert_eq!(after.as_deref(), case["after"].as_str(), "{name}");
    }
}

#[test]
fn restarts_are_counted_as_in_python() {
    let folder = tempfile::tempdir().unwrap();
    for case in common::golden()["restarts"].as_array().unwrap() {
        let ok = stage::note_restart(Some(folder.path()), case["version"].as_str().unwrap(), case["now"].as_f64().unwrap());
        assert_eq!(ok, case["ok"].as_bool().unwrap(), "{case}");
        let file = std::fs::read_to_string(folder.path().join(stage::TRIES)).unwrap();
        assert_eq!(file, case["file"].as_str().unwrap());
    }
}
