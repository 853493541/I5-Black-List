//! Why Windows will not capture 直播画面: facts and experiments for the log (wgc_diagnose.py).
//!
//! Facts (Windows' build, the window's styles and state, its DPI mode, who runs as administrator), controls (the
//! game window 直播姬 captures, the taskbar), then plain windows made here, each asked about from one more process
//! (as 直播姬 asks from its own) and from here. Lines start with "fact: ", "test: ", "verdict: " or "fix: ", worded
//! as the Python report. The Python app also made windows with Qt; there is no Qt here, so the report says
//! "fact: Qt windows could not be made here", as the Python report does without Qt, and the pythonw.exe control
//! has no counterpart.

use std::ffi::c_void;
use std::path::Path;
use std::time::{Duration, Instant};

use windows::core::{w, HSTRING, PCWSTR};
use windows::Win32::Foundation::{CloseHandle, COLORREF, HANDLE, HWND, LPARAM, LRESULT, POINT, RECT, SIZE, WPARAM};
use windows::Win32::Graphics::Dwm::{DwmGetWindowAttribute, DwmIsCompositionEnabled, DWMWA_CLOAKED, DWMWA_EXTENDED_FRAME_BOUNDS};
use windows::Win32::Graphics::Gdi::{
    CreateCompatibleDC, CreateDIBSection, CreateSolidBrush, DeleteDC, DeleteObject, GetDC, ReleaseDC, SelectObject, AC_SRC_ALPHA,
    AC_SRC_OVER, BITMAPINFO, BITMAPINFOHEADER, BLENDFUNCTION, DIB_RGB_COLORS, HBRUSH,
};
use windows::Win32::Security::{GetTokenInformation, TokenElevation, TOKEN_ELEVATION, TOKEN_QUERY};
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::System::Threading::{GetCurrentProcessId, OpenProcess, OpenProcessToken, PROCESS_QUERY_LIMITED_INFORMATION};
use windows::Win32::UI::HiDpi::{
    GetAwarenessFromDpiAwarenessContext, GetDpiForWindow, GetWindowDpiAwarenessContext, SetThreadDpiAwarenessContext,
    DPI_AWARENESS_CONTEXT_UNAWARE,
};
use windows::Win32::UI::WindowsAndMessaging::*;

use super::{closing_lines, flags, Test, EX_STYLES, ITSELF, CONTROL, STYLES, TASKBAR, WIN32};

fn py(on: bool) -> &'static str {
    if on {
        "True"
    } else {
        "False"
    }
}

fn hwnd(value: i64) -> HWND {
    HWND(value as isize as *mut c_void)
}

/// The file name of a process's program, or "?".
pub fn program(pid: u32) -> String {
    crate::process::image_path(pid).and_then(|path| path.replace('\\', "/").rsplit('/').next().map(str::to_string)).unwrap_or_else(|| "?".into())
}

/// "administrator", "not administrator", or why it cannot be told.
pub fn elevated(pid: u32) -> String {
    // SAFETY: opening a process for a query; the handle is closed below.
    let process = match unsafe { OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, pid) } {
        Ok(process) => process,
        Err(error) => return format!("unknown (cannot open it: {})", error.code().0 & 0xFFFF),
    };
    let mut token = HANDLE::default();
    // SAFETY: token is a local the call fills in, closed below; value is a local TOKEN_ELEVATION.
    let said = unsafe {
        if OpenProcessToken(process, TOKEN_QUERY, &mut token).is_err() {
            // A program run as administrator keeps its token from one that is not.
            "unknown (its token is closed to this app: likely administrator)".to_string()
        } else {
            let mut value = TOKEN_ELEVATION::default();
            let mut size = 0u32;
            let size_of = std::mem::size_of::<TOKEN_ELEVATION>() as u32;
            match GetTokenInformation(token, TokenElevation, Some(&mut value as *mut _ as *mut c_void), size_of, &mut size) {
                Err(_) => "unknown".into(),
                Ok(()) if value.TokenIsElevated != 0 => "administrator".into(),
                Ok(()) => "not administrator".into(),
            }
        }
    };
    // SAFETY: handles opened above.
    unsafe {
        if !token.is_invalid() {
            let _ = CloseHandle(token);
        }
        let _ = CloseHandle(process);
    }
    said
}

/// What Windows says of a window: its class, styles, state, place, DPI mode and process.
pub fn window_facts(window: i64) -> Vec<String> {
    let h = hwnd(window);
    // SAFETY: every call below only reads a window's state into locals; a gone window gives zeros or errors.
    unsafe {
        if !IsWindow(Some(h)).as_bool() {
            return vec![format!("window {window}: no such window")];
        }
        let mut name = [0u16; 256];
        let len = GetClassNameW(h, &mut name).max(0) as usize;
        let style = GetWindowLongW(h, GWL_STYLE) as u32;
        let ex = GetWindowLongW(h, GWL_EXSTYLE) as u32;
        let mut rect = RECT::default();
        let _ = GetWindowRect(h, &mut rect);
        let owned = GetWindow(h, GW_OWNER).is_ok_and(|o| !o.is_invalid());
        let mut out = vec![
            format!("class {}; style 0x{style:08X} ({}); extended 0x{ex:08X} ({})", String::from_utf16_lossy(&name[..len]), flags(style, &STYLES), flags(ex, &EX_STYLES)),
            format!(
                "visible {}, minimized {}, top-level {}, owned {}; at ({}, {}) {}x{}",
                py(IsWindowVisible(h).as_bool()),
                py(IsIconic(h).as_bool()),
                py(GetAncestor(h, GA_ROOT) == h),
                py(owned),
                rect.left,
                rect.top,
                rect.right - rect.left,
                rect.bottom - rect.top
            ),
        ];
        let mut cloaked = 0u32;
        let mut bounds = RECT::default();
        let cloak = DwmGetWindowAttribute(h, DWMWA_CLOAKED, &mut cloaked as *mut _ as *mut c_void, 4);
        let framed = DwmGetWindowAttribute(h, DWMWA_EXTENDED_FRAME_BOUNDS, &mut bounds as *mut _ as *mut c_void, 16);
        let awareness = GetAwarenessFromDpiAwarenessContext(GetWindowDpiAwarenessContext(h)).0;
        let mode = match awareness {
            0 => "unaware".to_string(),
            1 => "system".to_string(),
            2 => "per monitor".to_string(),
            other => other.to_string(),
        };
        let cloak = match cloak {
            Ok(()) => cloaked.to_string(),
            Err(error) => format!("? (0x{:08X})", error.code().0 as u32),
        };
        let bounds = match framed {
            Ok(()) => format!("({}, {}) {}x{}", bounds.left, bounds.top, bounds.right - bounds.left, bounds.bottom - bounds.top),
            Err(_) => "?".into(),
        };
        out.push(format!("cloaked {cloak}; DWM bounds {bounds}; DPI {} ({mode})", GetDpiForWindow(h)));
        if ex & 0x0008_0000 != 0 {
            let (mut key, mut alpha, mut how) = (COLORREF(0), 0u8, LAYERED_WINDOW_ATTRIBUTES_FLAGS(0));
            if GetLayeredWindowAttributes(h, Some(&mut key), Some(&mut alpha), Some(&mut how)).is_ok() {
                out.push(format!("layered with one alpha {alpha} (flags {})", how.0));
            } else {
                out.push("layered per pixel (UpdateLayeredWindow)".into());
            }
        }
        let mut affinity = 0u32;
        if GetWindowDisplayAffinity(h, &mut affinity).is_ok() {
            out.push(format!("display affinity {affinity}{}", if affinity != 0 { " (kept out of captures)" } else { "" }));
        }
        let mut pid = 0u32;
        GetWindowThreadProcessId(h, Some(&mut pid));
        out.push(format!("process {pid} {}, {}", program(pid), elevated(pid)));
        out
    }
}

/// Windows' version and update, the desktop composition, and 直播姬's processes.
pub fn system_facts() -> Vec<String> {
    let version = match windows_registry::LOCAL_MACHINE.open(r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") {
        Ok(key) => {
            let value = |name: &str| key.get_string(name).or_else(|_| key.get_u32(name).map(|v| v.to_string())).unwrap_or_else(|_| "?".into());
            // ProductName says Windows 10 on Windows 11 too: the build (22000 and up is 11) tells them apart.
            format!("{} {}, build {}.{}", value("ProductName"), value("DisplayVersion"), value("CurrentBuild"), value("UBR"))
        }
        Err(_) => "?".into(),
    };
    // SAFETY: plain queries with no pointers.
    let (composed, remote) = unsafe { (DwmIsCompositionEnabled().map(|b| b.as_bool()).unwrap_or(false), GetSystemMetrics(SM_REMOTESESSION) != 0) };
    let live: Vec<String> = crate::process::processes()
        .into_iter()
        .filter(|(_, name)| name.eq_ignore_ascii_case(crate::livehime::PROCESS))
        .map(|(pid, _)| format!("process {pid}, {}", elevated(pid)))
        .collect();
    vec![
        format!("{version}; desktop composition {}; remote session {}", py(composed), py(remote)),
        format!("直播姬: {}", if live.is_empty() { "not running".to_string() } else { live.join("; ") }),
    ]
}

extern "system" fn procedure(window: HWND, message: u32, w: WPARAM, l: LPARAM) -> LRESULT {
    // SAFETY: Windows' default handling of a message sent to a window made here.
    unsafe { DefWindowProcW(window, message, w, l) }
}

/// Windows made here, destroyed when this is dropped.
#[derive(Debug, Default)]
pub struct Made(pub Vec<HWND>);

impl Drop for Made {
    fn drop(&mut self) {
        for window in &self.0 {
            // SAFETY: windows made by this thread.
            let _ = unsafe { DestroyWindow(*window) };
        }
    }
}

/// A top-level window filled with one colour (0x00BBGGRR), shown behind every window without taking focus.
/// Returns 0 when it could not be made.
pub fn make_window(made: &mut Made, title: &str, style: u32, ex: u32, at: (i32, i32, i32, i32), colour: u32) -> i64 {
    let class = HSTRING::from(format!("模仿者小工具·测试窗口{colour:06X}"));
    // SAFETY: the class and window are made with handles from this process; strings outlive the calls.
    unsafe {
        let instance = GetModuleHandleW(None).unwrap_or_default();
        let klass = WNDCLASSEXW {
            cbSize: std::mem::size_of::<WNDCLASSEXW>() as u32,
            lpfnWndProc: Some(procedure),
            hInstance: instance.into(),
            hbrBackground: HBRUSH(CreateSolidBrush(COLORREF(colour)).0),
            lpszClassName: PCWSTR(class.as_ptr()),
            ..Default::default()
        };
        RegisterClassExW(&klass);
        let (x, y, w, h) = at;
        let title = HSTRING::from(title);
        let Ok(window) = CreateWindowExW(WINDOW_EX_STYLE(ex), &class, &title, WINDOW_STYLE(style), x, y, w, h, None, None, Some(instance.into()), None) else {
            return 0;
        };
        made.0.push(window);
        window.0 as i64
    }
}

/// Fill a layered window by UpdateLayeredWindow with one premultiplied BGRA pixel, as Qt fills a see-through window.
fn per_pixel(window: HWND, at: (i32, i32, i32, i32), pixel: [u8; 4]) {
    let (x, y, w, h) = at;
    // SAFETY: a DIB section of w*h 32-bit pixels is made, filled within its size, used, and freed here.
    unsafe {
        let header = BITMAPINFOHEADER { biSize: 40, biWidth: w, biHeight: -h, biPlanes: 1, biBitCount: 32, ..Default::default() };
        let info = BITMAPINFO { bmiHeader: header, ..Default::default() };
        let screen = GetDC(None);
        let memory = CreateCompatibleDC(Some(screen));
        let mut bits: *mut c_void = std::ptr::null_mut();
        let Ok(bitmap) = CreateDIBSection(Some(memory), &info, DIB_RGB_COLORS, &mut bits, None, 0) else {
            let _ = DeleteDC(memory);
            ReleaseDC(None, screen);
            return;
        };
        let old = SelectObject(memory, bitmap.into());
        std::slice::from_raw_parts_mut(bits as *mut u8, (w * h * 4) as usize).chunks_exact_mut(4).for_each(|p| p.copy_from_slice(&pixel));
        let blend = BLENDFUNCTION { BlendOp: AC_SRC_OVER as u8, BlendFlags: 0, SourceConstantAlpha: 255, AlphaFormat: AC_SRC_ALPHA as u8 };
        let (place, size, origin) = (POINT { x, y }, SIZE { cx: w, cy: h }, POINT::default());
        let _ = UpdateLayeredWindow(window, Some(screen), Some(&place), Some(&size), Some(memory), Some(&origin), COLORREF(0), Some(&blend), ULW_ALPHA);
        SelectObject(memory, old);
        let _ = DeleteObject(bitmap.into());
        let _ = DeleteDC(memory);
        ReleaseDC(None, screen);
    }
}

/// The plain windows (those named in `only`, when given), shown behind every window in the main screen's
/// bottom right corner.
pub fn make_win32(made: &mut Made, only: &[&str]) -> Vec<Test> {
    // SAFETY: plain metrics queries.
    let (width, height, beyond) = unsafe {
        (GetSystemMetrics(SM_CXSCREEN), GetSystemMetrics(SM_CYSCREEN), GetSystemMetrics(SM_XVIRTUALSCREEN) + GetSystemMetrics(SM_CXVIRTUALSCREEN) + 200)
    };
    let (x, y, w, h) = ((width - 260).max(0), (height - 200).max(0), 240, 135);
    let mut tests = Vec::new();
    for (name, style, ex, fill, off) in WIN32 {
        if !only.is_empty() && !only.contains(&name) {
            continue;
        }
        let left = if off { beyond } else { x };
        let unaware = name.contains("unaware");
        // SAFETY: the thread's DPI awareness is set for one window and put back.
        let before = unaware.then(|| unsafe { SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_UNAWARE) });
        let window = make_window(made, &format!("模仿者小工具·测试 {name}"), style, ex, (left, y, w, h), 0x00D0_D0D0);
        if let Some(before) = before {
            // SAFETY: as above.
            unsafe { SetThreadDpiAwarenessContext(before) };
        }
        if window == 0 {
            tests.push(Test::new(name, 0));
            continue;
        }
        let h_ = hwnd(window);
        match fill {
            // SAFETY: a window made above.
            "alpha" => unsafe {
                let _ = SetLayeredWindowAttributes(h_, COLORREF(0), 255, LWA_ALPHA);
            },
            "half" => per_pixel(h_, (left, y, w, h), [0, 0, 112, 128]),
            "clear" => per_pixel(h_, (left, y, w, h), [0; 4]),
            _ => {}
        }
        // SAFETY: a window made above.
        let _ = unsafe { SetWindowPos(h_, Some(HWND_BOTTOM), left, y, w, h, SWP_NOACTIVATE | SWP_SHOWWINDOW) };
        tests.push(Test::new(name, window));
    }
    tests
}

/// Let the windows made here be shown and drawn.
pub fn settle(time: Duration) {
    let end = Instant::now() + time;
    let mut message = MSG::default();
    while Instant::now() < end {
        // SAFETY: this thread's own message queue.
        unsafe {
            while PeekMessageW(&mut message, None, 0, 0, PM_REMOVE).as_bool() {
                let _ = TranslateMessage(&message);
                DispatchMessageW(&message);
            }
        }
        std::thread::sleep(Duration::from_millis(20));
    }
}

/// Windows' answer for each window, asked from one more process (`program --wgc <hwnd>...`), as 直播姬 asks from
/// its own; None for each where it could not be asked.
pub fn ask_in_child(program: &Path, windows: &[i64]) -> Vec<Option<u32>> {
    use std::os::windows::process::CommandExt;
    let mut command = std::process::Command::new(program);
    command.arg("--wgc").args(windows.iter().map(i64::to_string)).creation_flags(0x0800_0000);
    let answers: Vec<Option<u32>> = match command.output() {
        Ok(done) => String::from_utf8_lossy(&done.stdout).lines().map(super::read).collect(),
        Err(_) => Vec::new(),
    };
    (0..windows.len()).map(|i| answers.get(i).copied().flatten()).collect()
}

/// The report: facts, then a test line for each window, then the verdict. `ask_elsewhere` asks Windows from another
/// process ([`ask_in_child`] in the app).
pub fn report(window: i64, control: i64, ask_elsewhere: &dyn Fn(&[i64]) -> Vec<Option<u32>>) -> Vec<String> {
    let mut lines: Vec<String> = system_facts().into_iter().map(|line| format!("fact: {line}")).collect();
    let exe = std::env::current_exe().ok().and_then(|p| p.file_name().map(|n| n.to_string_lossy().into_owned())).unwrap_or_else(|| "?".into());
    // SAFETY: a plain query.
    lines.push(format!("fact: the windows below are made by {exe}, administrator: {}", elevated(unsafe { GetCurrentProcessId() })));
    lines.extend(window_facts(window).into_iter().map(|line| format!("fact: 直播画面: {line}")));
    let mut tests = vec![Test::new(ITSELF, window)];
    if control != 0 {
        lines.extend(window_facts(control).into_iter().map(|line| format!("fact: control (the game window 直播姬 captures): {line}")));
        tests.push(Test::new(CONTROL, control));
    }
    // SAFETY: a lookup by class name.
    if let Ok(taskbar) = unsafe { FindWindowW(w!("Shell_TrayWnd"), PCWSTR::null()) } {
        if !taskbar.is_invalid() {
            tests.push(Test::new(TASKBAR, taskbar.0 as i64));
        }
    }
    let mut made = Made::default();
    tests.extend(make_win32(&mut made, &[]));
    lines.push("fact: Qt windows could not be made here".into());
    settle(Duration::from_millis(400));
    let asked: Vec<i64> = tests.iter().filter(|t| t.hwnd > 0).map(|t| t.hwnd).collect();
    let mut answers = ask_elsewhere(&asked).into_iter();
    for test in tests.iter_mut().filter(|t| t.hwnd > 0) {
        test.there = answers.next().flatten();
        test.here = super::capture::answer(test.hwnd as isize);
    }
    // SAFETY: reads a window's owner.
    let owned = |t: &Test| Some(unsafe { GetWindow(hwnd(t.hwnd), GW_OWNER) }.is_ok_and(|o| !o.is_invalid()));
    lines.extend(closing_lines(&tests, &owned));
    lines
}
