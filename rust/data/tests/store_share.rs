//! 分享 and the data folder, against what the Python app gives for the same input (tools/rust_golden_store.py's
//! module, run by hand on 2026-11-18).

use data::store::files::app_dir_for;
use data::store::share::{describe_entry, is_shared, parse_shared, share_text};
use data::store::Entry;
use std::path::{Path, PathBuf};

fn entry(name: &str, reason: &str, tags: &[&str]) -> Entry {
    Entry { name: name.into(), reason: reason.into(), tags: tags.iter().map(|t| t.to_string()).collect(), added_at: String::new() }
}

#[test]
fn share_text_and_back_as_python() {
    let list = [entry("示例坏人", "开局 就走\n真的", &["贴脸", "炸房", "演员"]), entry("心动星星", "", &[]), entry("Bad", "", &["场外"])];
    assert_eq!(share_text(&list), "#模仿者小工具 黑名单 3人\n示例坏人，炸房，贴脸，演员，原因：开局 就走 真的\n心动星星\nBad，场外");
    let described: Vec<String> = list.iter().map(describe_entry).collect();
    assert_eq!(described, ["炸房、贴脸、演员。原因：开局 就走\n真的", "", "场外"]);
    let text = "#模仿者小工具 黑名单 3人\n示例坏人，炸房，贴脸,  原因：开局，就走\n示例坏人...，挂机\n\n# x\n心动星星,其他,a:b,原因：\nBad";
    let s = |v: &[&str]| v.iter().map(|t| t.to_string()).collect::<Vec<_>>();
    assert_eq!(
        parse_shared(text),
        vec![
            ("示例坏人".to_string(), s(&["炸房", "贴脸"]), "开局，就走".to_string()),
            ("心动星星".to_string(), s(&["ab"]), String::new()),
            ("Bad".to_string(), vec![], String::new()),
        ]
    );
    assert!(is_shared(text) && is_shared(" #黑名单检测 名单\nx") && !is_shared("x"));
}

#[test]
fn the_data_folder_as_paths_py() {
    let home = Path::new("/home/p");
    let env = |pairs: &'static [(&'static str, &'static str)]| move |k: &str| pairs.iter().find(|p| p.0 == k).map(|p| p.1.to_string());
    assert_eq!(app_dir_for(true, env(&[("APPDATA", "C:\\A")]), home), PathBuf::from("C:\\A").join("BlackListDetect"));
    assert_eq!(app_dir_for(true, env(&[]), home), home.join("AppData").join("Roaming").join("BlackListDetect"));
    assert_eq!(app_dir_for(false, env(&[("XDG_CONFIG_HOME", "")]), home), home.join(".config").join("BlackListDetect"));
    assert_eq!(app_dir_for(false, env(&[("XDG_CONFIG_HOME", "/x")]), home), PathBuf::from("/x/BlackListDetect"));
}
