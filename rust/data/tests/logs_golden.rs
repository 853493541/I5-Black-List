//! The Rust log gives what logs.py and diagnostics.py give on the golden cases.

mod common;

use data::logs::export::{self, Account};
use data::logs::{self, watch::Watchdog, RotatingLog};

fn hex(text: &str) -> Vec<u8> {
    (0..text.len()).step_by(2).map(|at| u8::from_str_radix(&text[at..at + 2], 16).unwrap()).collect()
}

#[test]
fn lines_are_written_as_in_python() {
    for case in common::golden()["logs"]["lines"].as_array().unwrap() {
        let time = chrono::DateTime::from_timestamp(case["created"].as_i64().unwrap(), case["msecs"].as_u64().unwrap() as u32 * 1_000_000)
            .unwrap()
            .naive_utc();
        let got = logs::format_line(time, case["level"].as_str().unwrap(), case["thread"].as_str().unwrap(), case["message"].as_str().unwrap());
        assert_eq!(got, case["line"].as_str().unwrap());
    }
}

#[test]
fn names_are_masked_as_in_python() {
    for (name, want) in common::golden()["logs"]["masked"].as_object().unwrap() {
        assert_eq!(logs::masked(name), want.as_str().unwrap());
    }
}

#[test]
fn the_log_rolls_over_as_in_python() {
    let golden = common::golden();
    let rotation = &golden["logs"]["rotation"];
    let folder = tempfile::tempdir().unwrap();
    let log = RotatingLog {
        path: folder.path().join("app.log"),
        max_bytes: rotation["max_bytes"].as_u64().unwrap(),
        backups: rotation["backups"].as_u64().unwrap() as u32,
    };
    for line in rotation["written"].as_array().unwrap() {
        log.write(line.as_str().unwrap()).unwrap();
    }
    let files = rotation["files"].as_object().unwrap();
    assert_eq!(std::fs::read_dir(folder.path()).unwrap().count(), files.len());
    for (name, want) in files {
        let got = std::fs::read_to_string(folder.path().join(name)).unwrap();
        assert_eq!(got.replace("\r\n", "\n"), want.as_str().unwrap(), "{name}");
    }
}

#[test]
fn the_account_is_hidden_as_in_python() {
    let golden = common::golden();
    for case in golden["logs"]["hidden"].as_array().unwrap() {
        let account = Account { home: case["home"].as_str().unwrap().into(), user: case["user"].as_str().unwrap().into(), short: String::new() };
        assert_eq!(export::without_user(case["text"].as_str().unwrap(), &account), case["out"].as_str().unwrap(), "{case}");
    }
    for case in golden["logs"]["dumps"].as_array().unwrap() {
        let account = Account { home: case["home"].as_str().unwrap().into(), user: case["user"].as_str().unwrap().into(), short: String::new() };
        let got = export::dump_without_user(&hex(case["data"].as_str().unwrap()), &account);
        assert_eq!(got, hex(case["out"].as_str().unwrap()), "{case}");
    }
}

#[test]
fn the_export_holds_the_logs_oldest_first_without_the_account() {
    let root = tempfile::tempdir().unwrap();
    let logs_dir = logs::log_dir(root.path());
    std::fs::create_dir_all(&logs_dir).unwrap();
    for (name, text) in [("app.log", "newest C:\\Users\\Zhangsan\\x"), ("app.log.1", "older"), ("app.log.3", "oldest"), ("crash.log", "  \n"), ("app.log.x", "no")] {
        std::fs::write(logs_dir.join(name), text).unwrap();
    }
    std::fs::write(logs_dir.join("stuck-12.dmp"), b"MDMP C:\\Users\\Zhangsan\\a.dll").unwrap();
    let account = Account { home: "C:\\Users\\Zhangsan".into(), user: "Zhangsan".into(), short: String::new() };
    let out = tempfile::tempdir().unwrap();
    let path = export::export_logs(root.path(), "summary", out.path(), "", "20261118-1200", &account).unwrap();
    assert!(path.ends_with("模仿者小工具_日志_20261118-1200.txt"));
    let text = std::fs::read_to_string(&path).unwrap().replace("\r\n", "\n");
    assert!(text.starts_with("==== 电脑和设置 ====\nsummary\n==== app.log.3 ====\noldest\n\n==== app.log.1 ====\nolder\n\n==== app.log ====\nnewest ~\\x\n"));
    assert!(!text.contains("crash.log") && !text.contains("Zhangsan") && !text.contains("app.log.x"));
    let dumps = export::dumps_in(&text);
    assert_eq!(dumps, vec![("stuck-12.dmp".to_string(), b"MDMP C:\\Users\\xxxxxxxx\\a.dll".to_vec())]);
}

#[test]
fn crash_log_keeps_its_end_and_a_crash_is_noticed() {
    let folder = tempfile::tempdir().unwrap();
    let path = folder.path().join("crash.log");
    let text: String = (0..100).map(|n| format!("line {n}\n")).collect();
    std::fs::write(&path, &text).unwrap();
    logs::trim(&path, 500, 100);
    let kept = std::fs::read_to_string(&path).unwrap();
    assert!(kept.starts_with("(older lines removed)\nline 8") && kept.ends_with("line 99\n") && kept.len() < 130);
    assert!(!logs::mark_running(folder.path()));
    assert!(logs::mark_running(folder.path()));
    logs::mark_closed(folder.path());
    assert!(!logs::mark_running(folder.path()));
}

#[test]
fn a_pc_that_slept_is_no_freeze() {
    // tests/test_logs.py's case, step for step.
    let mut now = 100.0;
    let mut dog = Watchdog::new(now, 30.0, 10.0, 20.0);
    let mut said = Vec::new();
    let mut tick = |dog: &mut Watchdog, now: &mut f64, seconds: f64| {
        *now += seconds;
        said.extend(dog.tick(*now, |_| "12:00:00".into()));
    };
    dog.beat(now);
    for seconds in [2.0, 3600.0, 2.0, 2.0] {
        tick(&mut dog, &mut now, seconds);
    }
    for _ in 0..8 {
        tick(&mut dog, &mut now, 2.0);
    }
    dog.beat(now);
    tick(&mut dog, &mut now, 2.0);
    assert_eq!(said.len(), 2);
    assert!(said[0].starts_with("Main thread not answering for 1"), "{}", said[0]);
    assert_eq!(said[1], "Main thread answering again after 20 s.");
}
