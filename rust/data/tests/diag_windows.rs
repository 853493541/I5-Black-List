//! On Windows: a real report from this computer, through the same code the app runs, with every field filled.
#![cfg(windows)]

use data::diag::{self, FlowTest, Machine, Screen, Settings};
use data::logs::export::{export_logs, Account};

fn machine() -> Machine {
    let facts = win::machine::facts();
    let power = win::machine::power_status().map(|(ac, percent, saver)| diag::power_note(ac, percent, saver)).unwrap_or_default();
    Machine {
        cpu: facts.cpu,
        threads: facts.threads,
        memory_total_gb: facts.memory_total_gb,
        memory_free_gb: facts.memory_free_gb,
        gpus: facts.gpus,
        product: facts.product,
        display_version: facts.display_version,
        build: facts.build,
        version: facts.version,
        power,
    }
}

#[test]
fn a_real_report_has_every_field_filled() {
    let machine = machine();
    let line = machine.line();
    println!("{line}");
    assert!(line.starts_with("CPU ") && !line.starts_with("CPU  ("), "{line}");
    assert!(!line.contains("RAM 0.0 GB") && line.contains(" build 10.0.") && line.contains("Windows"), "{line}");
    let screens: Option<Vec<Screen>> =
        win::machine::screens().map(|all| all.into_iter().map(|(width, height, ratio)| Screen { width, height, ratio }).collect());
    let screens = diag::screens_line(screens.as_deref());
    println!("Screens: {screens}");

    let before = win::machine::system_times().map(|(idle, kernel, user)| diag::SystemTimes { idle, kernel, user });
    let (own, wall) = (win::machine::process_cpu_seconds(), std::time::Instant::now());
    let spent: u64 = (0..20_000_000u64).fold(0, |a, b| a.wrapping_add(b ^ (b >> 3)));
    assert!(spent > 0);
    let after = win::machine::system_times().map(|(idle, kernel, user)| diag::SystemTimes { idle, kernel, user });
    let numbers = diag::cpu_numbers(before, after, win::machine::process_cpu_seconds() - own, wall.elapsed().as_secs_f64(), machine.threads);
    let (busy, mine) = numbers.expect("Windows says how busy it was");
    assert!((0.0..=100.0).contains(&busy) && mine >= 0.0, "{busy} {mine}");

    let test = FlowTest { size: (1920, 1080), cpu_busy: Some(busy), cpu_own: Some(mine), runs: vec![vec![("capture".into(), 0.1)]], ..FlowTest::default() };
    let now = chrono::Local::now().naive_local();
    let summary = diag::summary_text("v1.0.1", now, &line, &screens, "cpu", &Settings { hotkey: "F8".into(), ..Settings::default() });
    let dir = tempfile::tempdir().unwrap();
    let home = std::env::var("USERPROFILE").unwrap_or_default();
    let account = Account { short: win::machine::short_name(&home), home, user: std::env::var("USERNAME").unwrap_or_default() };
    let desktop = win::machine::desktop();
    println!("desktop {desktop:?}");
    let path = export_logs(&dir.path().join("root"), &summary, &dir.path().join("desk"), &test.text(), &diag::export_stamp(now), &account).unwrap();
    let written = std::fs::read_to_string(&path).unwrap();
    println!("{written}");
    for field in ["==== 电脑和设置 ====", "模仿者小工具 v1.0.1", "导出于 ", "CPU ", "RAM ", "GPU ", "Screens: ", "Recognition on cpu", "==== 最近一次环境测试 ===="] {
        assert!(written.contains(field), "{field} missing");
    }
    assert!(written.contains("\r\n"), "the export is written with Windows line ends, as Python's text mode does");
}
