//! Windows Graphics Capture of one window (wgc.py), and why Windows would not capture 直播画面 (wgc_diagnose.py).
//!
//! 直播姬 (and OBS) capture a window with Windows.Graphics.Capture: IGraphicsCaptureItemInterop's CreateForWindow.
//! On a friend's Windows 10 that call refused 直播模式's window every time with E_INVALIDARG (0x80070057), the
//! answer Windows gives for a window that is not showing. The same call says beforehand whether a window will be
//! captured; the app asks it from a process of its own, as 直播姬 asks it (`<app>.exe --wgc <hwnd> ...` prints
//! each HRESULT on a line, see [`answer_lines`]).
//!
//! How the app captures: the lobby is always read from a GDI copy of the whole desktop (capture.rs, as
//! capture.py does); WGC is used only for 直播模式's window, to ask whether 直播姬 can capture it and, here, to
//! take one frame of a single window ([`capture::grab`]).
//!
//! This file is platform-free (the answers, the verdict and the report's wording); [`capture`] and [`diagnose`]
//! call Windows.

#[cfg(windows)]
pub mod capture;
#[cfg(windows)]
pub mod diagnose;

pub const ACCEPTED: u32 = 0;
/// What Windows answers for a window it will not capture (and for a hidden one).
pub const REFUSED: u32 = 0x8007_0057;

/// The answer printed by the asking process: an HRESULT, or None (Python's `int(text, 16)`).
pub fn read(output: &str) -> Option<u32> {
    let text = output.trim();
    let (negative, digits) = match text.strip_prefix('-') {
        Some(rest) => (true, rest),
        None => (false, text.strip_prefix('+').unwrap_or(text)),
    };
    let digits = digits.strip_prefix("0x").or_else(|| digits.strip_prefix("0X")).unwrap_or(digits).replace('_', "");
    let value = i64::from_str_radix(&digits, 16).ok()?;
    let value = if negative { -value } else { value };
    u32::try_from(value).ok()
}

/// The answer for the log.
pub fn words(result: Option<u32>) -> String {
    match result {
        None => "no Windows.Graphics.Capture to ask".into(),
        Some(ACCEPTED) => "captured".into(),
        Some(code) => format!("refused (0x{code:08X})"),
    }
}

/// What the asking process prints for one answer.
pub fn answer_line(result: Option<u32>) -> String {
    result.map_or_else(|| "none".into(), |code| format!("0x{code:08X}"))
}

/// The asking process's output for these windows, one line each (wgc.py's `__main__`), with `answer` being
/// [`capture::answer`] on Windows.
pub fn answer_lines(arguments: &[String], answer: &dyn Fn(isize) -> Option<u32>) -> Vec<String> {
    arguments.iter().map(|argument| answer_line(argument.parse().ok().and_then(answer))).collect()
}

/// One window asked about: Windows' answer from another process (`there`) and from where it was made (`here`).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Test {
    pub name: String,
    pub hwnd: i64,
    pub there: Option<u32>,
    pub here: Option<u32>,
}

impl Test {
    pub fn new(name: &str, hwnd: i64) -> Test {
        Test { name: name.into(), hwnd, there: None, here: None }
    }
}

/// Plain windows made by the diagnosis: (name, style, extended style, how it is filled, off the screen).
pub const WIN32: [(&str, u32, u32, &str, bool); 10] = [
    ("plain window", 0x8000_0000, 0, "paint", false),
    ("titled window", 0x00CF_0000, 0, "paint", false),
    ("plain window, DPI unaware", 0x8000_0000, 0, "paint", false),
    ("plain window, off the screen", 0x8000_0000, 0, "paint", true),
    ("layered, one alpha", 0x8000_0000, 0x0008_0000, "alpha", false),
    ("layered per pixel, half see-through", 0x8000_0000, 0x0008_0000, "half", false),
    ("layered per pixel, all clear", 0x8000_0000, 0x0008_0000, "clear", false),
    ("click-through (layered + transparent)", 0x8000_0000, 0x0008_0020, "alpha", false),
    ("no-activate", 0x8000_0000, 0x0800_0000, "paint", false),
    ("styled like 直播画面 (no-activate + layered + transparent, per pixel)", 0x8000_0000, 0x0808_0020, "half", false),
];

/// Windows like 直播画面, each without one of its properties (made with Qt by the Python app).
pub const QT: [(&str, &[&str]); 10] = [
    ("Qt, like 直播画面", &[]),
    ("Qt, like 直播画面, nothing drawn", &["drawn"]),
    ("Qt, without see-through background", &["see-through"]),
    ("Qt, without click-through", &["click-through"]),
    ("Qt, without no-focus", &["no-focus"]),
    ("Qt, without on-bottom", &["on-bottom"]),
    ("Qt, not layered (no see-through, no click-through)", &["see-through", "click-through"]),
    ("Qt, plain window", &["see-through", "click-through", "no-focus", "on-bottom"]),
    ("Qt, like 直播画面, its taskbar button taken off", &["taskbar"]),
    ("Qt, like 直播画面, owned by a hidden window (no taskbar button)", &["owner"]),
];
/// What a copy can be made without, as against how it is set apart (taskbar, owner).
pub const PROPERTIES: [&str; 5] = ["drawn", "see-through", "click-through", "no-focus", "on-bottom"];
/// Properties of 直播画面 that can go without changing what viewers see.
pub const HARMLESS: [&str; 3] = ["click-through", "no-focus", "on-bottom"];
pub const BY_PYTHONW: &str = "plain window made by pythonw.exe";
pub const TASKBAR: &str = "control: the taskbar (Explorer's)";
pub const ITSELF: &str = "直播画面 itself";
pub const CONTROL: &str = "control: the game window 直播姬 captures";

/// Extended window styles and styles, by the names the report uses.
pub const EX_STYLES: [(u32, &str); 7] = [
    (0x0000_0008, "TOPMOST"),
    (0x0000_0020, "TRANSPARENT"),
    (0x0000_0080, "TOOLWINDOW"),
    (0x0004_0000, "APPWINDOW"),
    (0x0008_0000, "LAYERED"),
    (0x0020_0000, "NOREDIRECTIONBITMAP"),
    (0x0800_0000, "NOACTIVATE"),
];
pub const STYLES: [(u32, &str); 5] =
    [(0x8000_0000, "POPUP"), (0x1000_0000, "VISIBLE"), (0x0800_0000, "DISABLED"), (0x00C0_0000, "CAPTION"), (0x4000_0000, "CHILD")];

/// The names of the bits set in `value`, joined by "|"; "none" when none is.
pub fn flags(value: u32, names: &[(u32, &str)]) -> String {
    let found: Vec<&str> = names.iter().filter(|(bit, _)| value & bit == *bit).map(|(_, name)| *name).collect();
    if found.is_empty() {
        "none".into()
    } else {
        found.join("|")
    }
}

/// What the answers point at, and a harmless property to leave out ("" when none would help).
pub fn verdict(tests: &[Test]) -> (String, String) {
    let mut taken: Vec<(&str, bool)> = Vec::new();
    for test in tests {
        if let Some(there) = test.there {
            match taken.iter_mut().find(|(name, _)| *name == test.name) {
                Some(slot) => slot.1 = there == ACCEPTED,
                None => taken.push((&test.name, there == ACCEPTED)),
            }
        }
    }
    let get = |name: &str| taken.iter().find(|(n, _)| *n == name).map(|(_, on)| *on);
    let say = |text: &str| (text.to_string(), String::new());
    if taken.is_empty() {
        return say("Windows could not be asked (no Windows.Graphics.Capture, or the asking process failed).");
    }
    if get(ITSELF) == Some(true) {
        return say("Windows takes 直播画面 now.");
    }
    let controls: Vec<&str> = tests.iter().filter(|t| t.name.starts_with("control") && t.there.is_some()).map(|t| t.name.as_str()).collect();
    if !controls.is_empty() && !controls.iter().any(|name| get(name) == Some(true)) {
        return say("Windows refuses even the control windows: the asking is blocked on this PC, not 直播画面.");
    }
    if get("plain window") == Some(false) && get("titled window") == Some(false) {
        if get(BY_PYTHONW) == Some(true) {
            return say(
                "Windows takes a plain window made by pythonw.exe and none made by 模仿者小工具.exe: it is about the app's program \
                 file (its name or what it says of itself), not how the window is made.",
            );
        }
        return say(
            "Windows takes other programs' windows but no window made by this app: it is about the app's programs, not how \
             the window is made.",
        );
    }
    let refused: Vec<&str> = tests
        .iter()
        .filter(|t| WIN32.iter().any(|(name, ..)| *name == t.name) && get(&t.name) == Some(false))
        .map(|t| t.name.as_str())
        .collect();
    let plain = if refused.is_empty() { String::new() } else { format!(" Windows also refuses these plain windows: {}.", refused.join(", ")) };
    if get("Qt, like 直播画面") == Some(true) {
        let found = "A fresh window like 直播画面 is taken: something about the running 直播画面 differs (its state or what it shows).";
        return (format!("{found}{plain}"), String::new());
    }
    let flips: Vec<&[&str]> = QT[2..]
        .iter()
        .filter(|(name, without)| get(name) == Some(true) && without.iter().all(|p| PROPERTIES.contains(p)))
        .map(|(_, without)| *without)
        .collect();
    let Some(smallest) = flips.iter().fold(None::<&[&str]>, |best, &f| match best {
        Some(b) if b.len() <= f.len() => Some(b),
        _ => Some(f),
    }) else {
        return (format!("No single difference from 直播画面 made Windows take it.{plain}"), String::new());
    };
    let named = smallest.join(" and ");
    let fix = flips.iter().find(|single| single.len() == 1 && HARMLESS.contains(&single[0])).map_or("", |single| single[0]);
    (format!("Without {named} Windows takes it: {named} is what Windows refuses here.{plain}"), fix.to_string())
}

/// One "test: " line of the report; `owned` is whether the window has an owner, for the windows with no taskbar
/// button.
pub fn test_line(test: &Test, owned: Option<bool>) -> String {
    let mut shown = if test.hwnd != 0 { words(test.there) } else { "could not be made".into() };
    if test.hwnd > 0 && test.here != test.there {
        shown += &format!(" (asked from where it was made: {})", words(test.here));
    }
    if test.hwnd > 0 && test.name.ends_with("(no taskbar button)") {
        shown += &format!("; owned {}", if owned.unwrap_or(false) { "True" } else { "False" });
    }
    format!("test: {}: {shown}", test.name)
}

/// The end of the report: a line per test, the verdict, and the fix when there is one.
pub fn closing_lines(tests: &[Test], owned: &dyn Fn(&Test) -> Option<bool>) -> Vec<String> {
    let mut lines: Vec<String> = tests.iter().map(|test| test_line(test, owned(test))).collect();
    let (found, fix) = verdict(tests);
    lines.push(format!("verdict: {found}"));
    if !fix.is_empty() {
        lines.push(format!("fix: {fix}"));
    }
    lines
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn answers_read_and_say_as_python_does() {
        assert_eq!(read(" 0x80070057\n"), Some(REFUSED));
        assert_eq!(read("none"), None);
        assert_eq!(words(Some(0)), "captured");
        assert_eq!(words(Some(REFUSED)), "refused (0x80070057)");
        assert_eq!(answer_lines(&["5".into(), "x".into()], &|h| (h == 5).then_some(0)), vec!["0x00000000", "none"]);
        assert_eq!(flags(0x0808_0020, &EX_STYLES), "TRANSPARENT|LAYERED|NOACTIVATE");
    }
}
