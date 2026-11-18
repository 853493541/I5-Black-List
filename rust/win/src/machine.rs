//! What the computer is, for the diagnostics report (diagnostics.machine_line, screens_line, power_note,
//! CpuWindow, desktop and _short_name). Plain values out: `data::diag` turns them into the report's words.
//! Each `unsafe` block is one Win32 call on memory this function owns.

use std::path::PathBuf;

use windows::core::{BOOL, HSTRING, PCWSTR};
use windows::Win32::Foundation::{FILETIME, LPARAM, RECT};
use windows::Win32::Graphics::Gdi::{EnumDisplayDevicesW, EnumDisplayMonitors, GetMonitorInfoW, DISPLAY_DEVICEW, HDC, HMONITOR, MONITORINFO};
use windows::Win32::Storage::FileSystem::GetShortPathNameW;
use windows::Win32::System::Power::{GetSystemPowerStatus, SYSTEM_POWER_STATUS};
use windows::Win32::System::SystemInformation::{GlobalMemoryStatusEx, MEMORYSTATUSEX};
use windows::Win32::System::Threading::{GetCurrentProcess, GetProcessTimes, GetSystemTimes};
use windows::Win32::UI::HiDpi::{GetDpiForMonitor, SetThreadDpiAwarenessContext, DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2, MDT_EFFECTIVE_DPI};

const CURRENT_VERSION: &str = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion";

/// The computer's facts, read as diagnostics.py reads them (see `data::diag::Machine` for each field's meaning).
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Facts {
    pub cpu: String,
    pub threads: usize,
    pub memory_total_gb: f64,
    pub memory_free_gb: f64,
    pub gpus: Vec<String>,
    pub product: String,
    pub display_version: String,
    pub build: u32,
    pub version: String,
}

fn registry(path: &str, name: &str) -> String {
    windows_registry::LOCAL_MACHINE.open(path).and_then(|key| key.get_string(name)).map(|v| v.trim().to_string()).unwrap_or_default()
}

fn registry_u32(path: &str, name: &str) -> Option<u32> {
    windows_registry::LOCAL_MACHINE.open(path).and_then(|key| key.get_u32(name)).ok()
}

fn text(wide: &[u16]) -> String {
    let end = wide.iter().position(|&c| c == 0).unwrap_or(wide.len());
    String::from_utf16_lossy(&wide[..end])
}

/// Everything machine_line names but the power note.
pub fn facts() -> Facts {
    let (memory_total_gb, memory_free_gb) = memory_gb();
    let build: u32 = registry(CURRENT_VERSION, "CurrentBuildNumber").parse().unwrap_or(0);
    let major = registry_u32(CURRENT_VERSION, "CurrentMajorVersionNumber").unwrap_or(10);
    let minor = registry_u32(CURRENT_VERSION, "CurrentMinorVersionNumber").unwrap_or(0);
    let cpu = registry(r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "ProcessorNameString");
    let cpu = if cpu.is_empty() { registry(r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "Identifier") } else { cpu };
    Facts {
        cpu,
        threads: std::thread::available_parallelism().map_or(1, |n| n.get()),
        memory_total_gb,
        memory_free_gb,
        gpus: gpus(),
        product: registry(CURRENT_VERSION, "ProductName"),
        display_version: registry(CURRENT_VERSION, "DisplayVersion"),
        build,
        version: format!("{major}.{minor}.{build}"),
    }
}

/// (total, free) memory in GiB, or (0, 0).
pub fn memory_gb() -> (f64, f64) {
    let mut memory = MEMORYSTATUSEX { dwLength: std::mem::size_of::<MEMORYSTATUSEX>() as u32, ..Default::default() };
    // SAFETY: memory is ours, its size set as the call asks.
    if unsafe { GlobalMemoryStatusEx(&mut memory) }.is_err() {
        return (0.0, 0.0);
    }
    let gib = (1u64 << 30) as f64;
    (memory.ullTotalPhys as f64 / gib, memory.ullAvailPhys as f64 / gib)
}

/// The display adapters' names, each once, as EnumDisplayDevices lists them (at most 16).
pub fn gpus() -> Vec<String> {
    let mut found: Vec<String> = Vec::new();
    for index in 0..16 {
        let mut device = DISPLAY_DEVICEW { cb: std::mem::size_of::<DISPLAY_DEVICEW>() as u32, ..Default::default() };
        // SAFETY: device is ours, its size set; a null device name asks for the adapters.
        if !unsafe { EnumDisplayDevicesW(PCWSTR::null(), index, &mut device, 0) }.as_bool() {
            break;
        }
        let name = text(&device.DeviceString);
        if !name.is_empty() && !found.contains(&name) {
            found.push(name);
        }
    }
    found
}

/// GetSystemPowerStatus: (ACLineStatus, BatteryLifePercent, SystemStatusFlag), for `data::diag::power_note`.
pub fn power_status() -> Option<(u8, u8, u8)> {
    let mut status = SYSTEM_POWER_STATUS::default();
    // SAFETY: status is ours.
    unsafe { GetSystemPowerStatus(&mut status) }.ok()?;
    Some((status.ACLineStatus, status.BatteryLifePercent, status.SystemStatusFlag))
}

fn ticks(time: FILETIME) -> u64 {
    (u64::from(time.dwHighDateTime) << 32) | u64::from(time.dwLowDateTime)
}

/// GetSystemTimes: (idle, kernel, user) in 100 ns ticks, kernel including idle.
pub fn system_times() -> Option<(u64, u64, u64)> {
    let (mut idle, mut kernel, mut user) = (FILETIME::default(), FILETIME::default(), FILETIME::default());
    // SAFETY: the three FILETIMEs are ours.
    unsafe { GetSystemTimes(Some(&mut idle), Some(&mut kernel), Some(&mut user)) }.ok()?;
    Some((ticks(idle), ticks(kernel), ticks(user)))
}

/// This process's CPU time so far, user and kernel, in seconds (time.process_time()).
pub fn process_cpu_seconds() -> f64 {
    let mut times = [FILETIME::default(); 4];
    let [created, exited, kernel, user] = &mut times;
    // SAFETY: the current process's pseudo handle needs no closing; the FILETIMEs are ours.
    if unsafe { GetProcessTimes(GetCurrentProcess(), created, exited, kernel, user) }.is_err() {
        return 0.0;
    }
    (ticks(*kernel) + ticks(*user)) as f64 / 1e7
}

unsafe extern "system" fn add_monitor(monitor: HMONITOR, _: HDC, _: *mut RECT, found: LPARAM) -> BOOL {
    // SAFETY: found is the Vec screens() passed, alive for the whole enumeration.
    let found = unsafe { &mut *(found.0 as *mut Vec<(f64, f64, f64)>) };
    let mut info = MONITORINFO { cbSize: std::mem::size_of::<MONITORINFO>() as u32, ..Default::default() };
    // SAFETY: info is ours, its size set.
    if unsafe { GetMonitorInfoW(monitor, &mut info) }.as_bool() {
        let (mut dpi_x, mut dpi_y) = (96u32, 96u32);
        // SAFETY: the two counts are ours.
        let _ = unsafe { GetDpiForMonitor(monitor, MDT_EFFECTIVE_DPI, &mut dpi_x, &mut dpi_y) };
        let ratio = f64::from(dpi_x.max(1)) / 96.0;
        let rect = info.rcMonitor;
        found.push((f64::from(rect.right - rect.left) / ratio, f64::from(rect.bottom - rect.top) / ratio, ratio));
    }
    true.into()
}

/// Each screen as Qt gives it: (width, height) in logical pixels and the device pixel ratio; None when
/// Windows lists none. Read per-monitor DPI aware, so the sizes are the real ones divided by the scale.
pub fn screens() -> Option<Vec<(f64, f64, f64)>> {
    let mut found: Vec<(f64, f64, f64)> = Vec::new();
    // SAFETY: changes this thread's DPI awareness for the enumeration; the old one is put back below.
    let before = unsafe { SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2) };
    // SAFETY: add_monitor writes only into found, which outlives the call.
    let listed = unsafe { EnumDisplayMonitors(None, None, Some(add_monitor), LPARAM(&mut found as *mut _ as isize)) };
    if !before.is_invalid() {
        // SAFETY: as above.
        unsafe { SetThreadDpiAwarenessContext(before) };
    }
    (listed.as_bool() && !found.is_empty()).then_some(found)
}

/// The Desktop, wherever Windows keeps it (it may be in OneDrive); None when Windows does not say.
pub fn desktop() -> Option<PathBuf> {
    let key = windows_registry::CURRENT_USER.open(r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders").ok()?;
    key.get_string("Desktop").ok().filter(|path| !path.is_empty()).map(PathBuf::from)
}

/// The 8.3 name Windows keeps for a folder (ZHANGS~1 for 张三), or "" when it has none.
pub fn short_name(folder: &str) -> String {
    let mut buffer = vec![0u16; 1024];
    // SAFETY: buffer is ours and its length is passed with it.
    let length = unsafe { GetShortPathNameW(&HSTRING::from(folder), Some(&mut buffer)) } as usize;
    if length == 0 || length > buffer.len() {
        return String::new();
    }
    let path = String::from_utf16_lossy(&buffer[..length]);
    path.rsplit(['\\', '/']).find(|part| !part.is_empty()).unwrap_or_default().to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn this_computer_is_described() {
        let facts = facts();
        println!("{facts:?} screens {:?} power {:?} desktop {:?}", screens(), power_status(), desktop());
        assert!(!facts.cpu.is_empty() && facts.threads >= 1);
        assert!(facts.memory_total_gb > 0.5 && facts.memory_free_gb > 0.0 && facts.memory_free_gb <= facts.memory_total_gb);
        assert!(facts.build >= 10240 && facts.version.starts_with("10.0."), "{facts:?}");
        assert!(!facts.product.is_empty());
        assert!(power_status().is_some());
        let (idle, kernel, user) = system_times().unwrap();
        assert!(kernel >= idle && user > 0);
        let spent: u64 = (0..3_000_000u64).fold(0, |a, b| a.wrapping_add(b * b));
        assert!(spent > 0 && process_cpu_seconds() >= 0.0);
        if let Some(screens) = screens() {
            assert!(screens.iter().all(|&(w, h, r)| w > 0.0 && h > 0.0 && r >= 1.0));
        }
        let home = std::env::var("USERPROFILE").unwrap();
        let _ = short_name(&home);
    }
}
