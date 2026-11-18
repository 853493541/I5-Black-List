//! The computer in one line (diagnostics.machine_line, screens_line, power_note, CpuWindow), from facts
//! `win::machine` reads on Windows.

/// What the computer is, as the log says it at each start. On Windows each field is read as Python reads it:
/// `cpu` HKLM ProcessorNameString (else the processor's identifier), `threads` the logical CPUs, the memory
/// from GlobalMemoryStatusEx in GiB, `gpus` EnumDisplayDevices' names without repeats, `product` and
/// `display_version` from HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion, `build` the build number and
/// `version` "major.minor.build" (platform.version()), `power` [`power_note`]'s words.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Machine {
    pub cpu: String,
    pub threads: usize,
    pub memory_total_gb: f64,
    pub memory_free_gb: f64,
    pub gpus: Vec<String>,
    pub product: String,
    pub display_version: String,
    pub build: u32,
    pub version: String,
    pub power: String,
}

impl Machine {
    /// What Python says off Windows: no registry, no memory, no GPUs, the logical CPU count.
    pub fn fallback() -> Machine {
        Machine {
            threads: std::thread::available_parallelism().map_or(1, |n| n.get()),
            cpu: std::env::consts::ARCH.into(),
            ..Machine::default()
        }
    }

    /// The computer in one line, for the log at each start and the export's summary.
    pub fn line(&self) -> String {
        let product =
            if self.build >= 22000 { self.product.replace("Windows 10", "Windows 11") } else { self.product.clone() };
        let build = format!("build {}", self.version);
        let windows: Vec<&str> =
            [product.as_str(), self.display_version.as_str(), build.as_str()].into_iter().filter(|p| !p.is_empty()).collect();
        let gpus = if self.gpus.is_empty() { "?".to_string() } else { self.gpus.join(" / ") };
        let mut parts = vec![
            format!("CPU {} ({} threads)", self.cpu, self.threads),
            format!("RAM {:.1} GB ({:.1} GB free)", self.memory_total_gb, self.memory_free_gb),
            format!("GPU {gpus}"),
            windows.join(" "),
        ];
        if !self.power.is_empty() {
            parts.push(self.power.clone());
        }
        parts.join("; ")
    }
}

/// power_note from GetSystemPowerStatus's ACLineStatus, BatteryLifePercent and SystemStatusFlag:
/// "on battery 57%", "battery saver", both, or "" when plugged in or a desktop.
pub fn power_note(ac_line_status: u8, battery_percent: u8, system_status_flag: u8) -> String {
    let mut notes = Vec::new();
    if ac_line_status == 0 {
        notes.push(format!("on battery {battery_percent}%"));
    }
    if system_status_flag == 1 {
        notes.push("battery saver".to_string());
    }
    notes.join(", ")
}

/// One screen as Qt gives it: its size in logical pixels and its device pixel ratio (1.5 at 150%).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Screen {
    pub width: f64,
    pub height: f64,
    pub ratio: f64,
}

/// "1920x1080 at 150%, 2560x1440 at 100%" in real pixels; "?" when the screens could not be read.
pub fn screens_line(screens: Option<&[Screen]>) -> String {
    let Some(screens) = screens else { return "?".into() };
    let one = |s: &Screen| format!("{:.0}x{:.0} at {:.0}%", s.width * s.ratio, s.height * s.ratio, s.ratio * 100.0);
    screens.iter().map(one).collect::<Vec<_>>().join(", ")
}

/// GetSystemTimes in 100 ns ticks: idle, kernel (which includes idle), user.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct SystemTimes {
    pub idle: u64,
    pub kernel: u64,
    pub user: u64,
}

/// CpuWindow.numbers: (whole computer, this app) busy percent between two readings, or None when Windows
/// does not say. `own_seconds` is this process's CPU time spent between them, `wall_seconds` the time between.
pub fn cpu_numbers(before: Option<SystemTimes>, after: Option<SystemTimes>, own_seconds: f64, wall_seconds: f64, cpus: usize) -> Option<(f64, f64)> {
    let (before, after) = (before?, after?);
    let idle = after.idle as i128 - before.idle as i128;
    let total = (after.kernel as i128 - before.kernel as i128) + (after.user as i128 - before.user as i128);
    if total <= 0 {
        return None;
    }
    let own = 100.0 * own_seconds / wall_seconds.max(1e-6) / cpus.max(1) as f64;
    Some((100.0 * (total - idle) as f64 / total as f64, own))
}

/// CpuWindow.stop: "CPU 85% (this app 20%)", or "" when Windows does not say.
pub fn cpu_text(numbers: Option<(f64, f64)>) -> String {
    numbers.map_or_else(String::new, |(busy, own)| format!("CPU {busy:.0}% (this app {own:.0}%)"))
}
