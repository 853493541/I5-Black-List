//! On Windows (the windows-latest CI job): a solid red window made here is found, asked about and captured with
//! Windows Graphics Capture, and the diagnosis report is written for it. Where the runner has no WGC or cannot
//! capture (no GPU, no desktop), the capture is skipped with the reason printed; the rest still runs.
#![cfg(windows)]

use std::time::Duration;

use win::livehime::desktop::{client_rect, window_of, window_rect};
use win::wgc::capture::{answer, grab, supported};
use win::wgc::diagnose::{make_window, report, settle, window_facts, Made};
use win::wgc::{words, ACCEPTED};

const TITLE: &str = "模仿者小工具·测试 solid red";

#[test]
fn a_solid_window_is_found_captured_and_diagnosed() {
    let mut made = Made::default();
    let red = make_window(&mut made, TITLE, 0x9000_0000, 0, (100, 100, 320, 180), 0x0000_00FF);
    assert_ne!(red, 0, "the test window could not be made");
    settle(Duration::from_millis(600));

    assert_eq!(window_of(TITLE, ""), red as isize);
    let client = client_rect(TITLE, "").expect("client rect");
    assert_eq!((client.2 - client.0, client.3 - client.1), (320, 180), "{client:?}");
    assert!(window_rect(red as isize).is_some());
    let facts = window_facts(red);
    assert!(facts[0].starts_with("class 模仿者小工具·测试窗口") && facts[0].contains("POPUP|VISIBLE"), "{facts:?}");

    if !supported() {
        eprintln!("skipped the capture: this Windows has no Windows.Graphics.Capture");
    } else {
        let said = answer(red as isize);
        eprintln!("Windows' answer for the red window: {}", words(said));
        if said == Some(ACCEPTED) {
            match grab(red as isize, Duration::from_secs(5)) {
                Ok(frame) => {
                    let middle = frame.pixel(frame.width / 2, frame.height / 2);
                    eprintln!("captured {}x{}, middle pixel {middle:?}", frame.width, frame.height);
                    assert!(frame.width >= 300 && frame.height >= 160, "{}x{}", frame.width, frame.height);
                    assert!(middle[0] > 200 && middle[1] < 60 && middle[2] < 60, "{middle:?}");
                }
                Err(why) => eprintln!("skipped the capture on this runner: {why}"),
            }
        } else {
            eprintln!("skipped the capture: Windows would not capture the window here");
        }
    }

    let lines = report(red, 0, &|windows| windows.iter().map(|w| answer(*w as isize)).collect());
    for line in &lines {
        eprintln!("{line}");
    }
    assert!(lines.iter().all(|l| ["fact: ", "test: ", "verdict: ", "fix: "].iter().any(|p| l.starts_with(p))));
    assert!(lines.iter().any(|l| l.starts_with("test: 直播画面 itself: ")));
    assert!(lines.iter().any(|l| l.starts_with("verdict: ")));
    assert!(lines.contains(&"fact: Qt windows could not be made here".to_string()));
}
