use super::*;

#[test]
fn updates_first_at_one_second_then_every_half_hour() {
    let mut clock = UpdateClock::new(true);
    assert_eq!(clock.tick(500), None);
    assert_eq!(clock.tick(1_000), Some(UpdateLook::Install));
    assert_eq!(clock.tick(2_000), None);
    assert_eq!(clock.tick(UPDATE_EVERY_MS), Some(UpdateLook::Offer));
    assert_eq!(clock.tick(UPDATE_EVERY_MS + 1), None);
    clock.updating = true;
    assert_eq!(clock.tick(2 * UPDATE_EVERY_MS), None, "no look while an update installs");
}

#[test]
fn a_build_from_source_never_looks() {
    let mut clock = UpdateClock::new(false);
    assert_eq!(clock.tick(UPDATE_EVERY_MS), None);
    assert_eq!(clock.on_return(UPDATE_EVERY_MS), None);
}

#[test]
fn coming_back_looks_when_the_last_look_is_ten_minutes_old() {
    let mut clock = UpdateClock::new(true);
    assert_eq!(clock.on_return(5_000), None, "no look yet: the start's own comes first");
    clock.tick(1_000);
    assert_eq!(clock.on_return(1_000 + UPDATE_AGAIN_MS - 1), None);
    assert_eq!(clock.on_return(1_000 + UPDATE_AGAIN_MS), Some(UpdateLook::Offer));
}

#[test]
fn x_closes_to_the_tray_only_with_a_tray() {
    let mut settings = Settings { close_to_tray: true, ..Settings::default() };
    assert_eq!(on_close(&settings, true, true), Close::ToTray);
    assert_eq!(on_close(&settings, false, true), Close::Quit, "no tray icon: no way back, so X quits");
    assert_eq!(on_close(&settings, true, false), Close::Quit, "退出 always quits");
    settings.close_to_tray = false;
    assert_eq!(on_close(&settings, true, true), Close::Quit);
}

#[test]
fn tray_and_second_launch() {
    assert_eq!(on_tray(TrayAction::Quit), Do::Quit);
    assert_eq!(on_tray(TrayAction::Check), Do::CheckNow);
    assert_eq!(on_instance_message(b"show"), Some(Do::ShowWindow));
    assert_eq!(on_instance_message(b"quit"), Some(Do::Quit));
    assert_eq!(on_instance_message(b""), None, "a start with Windows only asks whether a copy is open");
}

#[test]
fn background_start_stays_in_the_tray_once_set_up() {
    let settings = Settings { disclaimer_accepted: true, env_checked: "2.0".into(), ..Settings::default() };
    assert!(start_quiet(true, true, false, &settings, "2.0"));
    assert!(!start_quiet(false, true, false, &settings, "2.0"));
    assert!(!start_quiet(true, false, false, &settings, "2.0"), "no tray: the window shows");
    assert!(!start_quiet(true, true, true, &settings, "2.0"), "first run: the window shows");
    assert!(!start_quiet(true, true, false, &settings, "2.1"), "environment check due");
}

#[test]
fn safe_mode_parks_auto_and_brings_it_back() {
    let mut settings = Settings { auto_capture: true, ..Settings::default() };
    assert!(set_safe(&mut settings, true));
    assert!(!settings.auto_capture && settings.auto_resume);
    assert!(!set_auto(&mut settings, true), "自动 is not offered in 基础模式");
    assert!(set_safe(&mut settings, false));
    assert!(settings.auto_capture && !settings.auto_resume);
    assert!(!set_safe(&mut settings, false));
}

#[test]
fn own_choice_ends_auto_resume() {
    let mut settings = Settings { safe_mode: true, auto_resume: true, ..Settings::default() };
    assert!(set_auto(&mut settings, false));
    assert!(!settings.auto_resume);
    set_safe(&mut settings, false);
    assert!(!settings.auto_capture, "手动 picked in 基础模式 stays 手动");
}

#[test]
fn stream_mode_is_on_or_empty() {
    let mut settings = Settings::default();
    assert!(set_stream(&mut settings, true));
    assert_eq!(settings.stream_mode, "on");
    assert!(mode_of(&settings).stream);
    assert!(!set_stream(&mut settings, true));
    assert!(set_stream(&mut settings, false));
    assert_eq!(settings.stream_mode, "");
}
