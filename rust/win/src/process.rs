//! One copy of the app at a time (single.py): the mutex, finding this folder's other copies, dumping and
//! ending a stuck one, and exit_now. Only processes whose program is this folder's runtime are ended.

use crate::instance::{mutex_name, PROCESSES};
use crate::settle::Host;
use std::os::windows::io::AsRawHandle;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};
use windows::core::{HSTRING, PWSTR};
use windows::Win32::Foundation::{CloseHandle, GetLastError, ERROR_ALREADY_EXISTS, HANDLE};
use windows::Win32::System::Diagnostics::Debug::{MiniDumpNormal, MiniDumpWithThreadInfo, MiniDumpWriteDump};
use windows::Win32::System::Diagnostics::ToolHelp::{
    CreateToolhelp32Snapshot, Process32FirstW, Process32NextW, PROCESSENTRY32W, TH32CS_SNAPPROCESS,
};
use windows::Win32::System::Threading::{
    CreateMutexW, GetCurrentProcess, OpenProcess, QueryFullProcessImageNameW, TerminateProcess, WaitForSingleObject,
    PROCESS_NAME_WIN32, PROCESS_QUERY_INFORMATION, PROCESS_QUERY_LIMITED_INFORMATION, PROCESS_SYNCHRONIZE,
    PROCESS_TERMINATE, PROCESS_VM_READ,
};

/// A kernel handle, closed on drop.
pub struct Owned(HANDLE);

impl Drop for Owned {
    fn drop(&mut self) {
        // SAFETY: the handle came from a successful open/create call and is closed once.
        let _ = unsafe { CloseHandle(self.0) };
    }
}

fn open(pid: u32, access: windows::Win32::System::Threading::PROCESS_ACCESS_RIGHTS) -> Option<Owned> {
    // SAFETY: no pointers; a failed open returns an error, a good one is owned by Owned.
    unsafe { OpenProcess(access, false, pid) }.ok().map(Owned)
}

/// The app's mutex, held while this value lives (keep it for the life of the process).
pub struct Claim {
    _handle: Option<Owned>,
    /// Whether this is the only copy that holds it (the first to start).
    pub first: bool,
}

pub fn claim(key: &str) -> Claim {
    let name = HSTRING::from(mutex_name(key));
    // SAFETY: name outlives the call; the last error is read right after it, on the same thread.
    let (handle, error) = unsafe {
        let handle = CreateMutexW(None, false, &name);
        (handle, GetLastError())
    };
    Claim { first: error != ERROR_ALREADY_EXISTS, _handle: handle.ok().map(Owned) }
}

/// Every process: its id and its program's file name.
pub fn processes() -> Vec<(u32, String)> {
    let mut found = Vec::new();
    // SAFETY: the snapshot is owned and closed by Owned; entry is ours with dwSize set as the API asks.
    unsafe {
        let Ok(snapshot) = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0) else { return found };
        let snapshot = Owned(snapshot);
        let mut entry = PROCESSENTRY32W { dwSize: size_of::<PROCESSENTRY32W>() as u32, ..Default::default() };
        let mut more = Process32FirstW(snapshot.0, &mut entry).is_ok();
        while more {
            let end = entry.szExeFile.iter().position(|&c| c == 0).unwrap_or(entry.szExeFile.len());
            found.push((entry.th32ProcessID, String::from_utf16_lossy(&entry.szExeFile[..end])));
            more = Process32NextW(snapshot.0, &mut entry).is_ok();
        }
    }
    found
}

/// Whether a program by this file name is running, such as livehime.exe.
pub fn running(program: &str) -> bool {
    processes().iter().any(|(_, name)| name.eq_ignore_ascii_case(program) || name.to_lowercase() == program.to_lowercase())
}

/// A process's full program path.
pub fn image_path(pid: u32) -> Option<String> {
    let process = open(pid, PROCESS_QUERY_LIMITED_INFORMATION)?;
    let mut buffer = vec![0u16; 1024];
    let mut size = buffer.len() as u32;
    // SAFETY: buffer holds `size` u16s and outlives the call, which writes at most that many.
    unsafe { QueryFullProcessImageNameW(process.0, PROCESS_NAME_WIN32, PWSTR(buffer.as_mut_ptr()), &mut size) }.ok()?;
    Some(String::from_utf16_lossy(&buffer[..size as usize]))
}

fn normcase(path: &Path) -> String {
    std::path::absolute(path).unwrap_or_else(|_| path.to_path_buf()).to_string_lossy().replace('/', "\\").to_lowercase()
}

/// Other processes running this folder's copy of the app (root\runtime\模仿者小工具.exe).
pub fn copies_in(root: &Path) -> Vec<u32> {
    let wanted: Vec<String> = PROCESSES.iter().map(|name| normcase(&root.join("runtime").join(name))).collect();
    let names: Vec<String> = PROCESSES.iter().map(|name| name.to_lowercase()).collect();
    let me = std::process::id();
    processes()
        .into_iter()
        .filter(|(pid, name)| *pid != me && names.contains(&name.to_lowercase()))
        .filter(|(pid, _)| image_path(*pid).is_some_and(|path| wanted.contains(&normcase(Path::new(&path)))))
        .map(|(pid, _)| pid)
        .collect()
}

/// End these processes, waiting up to 3 s for each; the ones ended.
pub fn end(pids: &[u32]) -> Vec<u32> {
    pids.iter()
        .copied()
        .filter(|&pid| {
            let Some(process) = open(pid, PROCESS_TERMINATE | PROCESS_SYNCHRONIZE) else { return false };
            // SAFETY: process is a live handle with terminate and synchronize rights.
            unsafe { TerminateProcess(process.0, 1).is_ok() && { WaitForSingleObject(process.0, 3000); true } }
        })
        .collect()
}

pub const DUMPS_KEPT: usize = 3;

/// A small minidump (folder/stuck-<pid>.dmp): threads and stacks, none of its other memory. Only the
/// newest `keep` dumps stay.
pub fn write_dump(pid: u32, folder: &Path, keep: usize) -> std::io::Result<PathBuf> {
    std::fs::create_dir_all(folder)?;
    let target = folder.join(format!("stuck-{pid}.dmp"));
    let process = open(pid, PROCESS_QUERY_INFORMATION | PROCESS_VM_READ).ok_or_else(std::io::Error::last_os_error)?;
    let file = std::fs::File::create(&target)?;
    // SAFETY: process and file are live handles for the call; the optional streams are none.
    let written = unsafe {
        MiniDumpWriteDump(process.0, pid, HANDLE(file.as_raw_handle()), MiniDumpNormal | MiniDumpWithThreadInfo, None, None, None)
    };
    drop(file);
    if let Err(error) = written {
        let _ = std::fs::remove_file(&target);
        return Err(std::io::Error::other(error.message()));
    }
    let mut old: Vec<(std::time::SystemTime, PathBuf)> = std::fs::read_dir(folder)?
        .filter_map(Result::ok)
        .map(|e| e.path())
        .filter(|p| p.file_name().and_then(|n| n.to_str()).is_some_and(|n| n.starts_with("stuck-") && n.ends_with(".dmp")))
        .filter_map(|p| Some((p.metadata().ok()?.modified().ok()?, p)))
        .collect();
    old.sort();
    for (_, path) in old.iter().take(old.len().saturating_sub(keep)) {
        let _ = std::fs::remove_file(path);
    }
    Ok(target)
}

/// End this process at once, without unloading its libraries.
pub fn exit_now(code: u32) -> ! {
    // SAFETY: the pseudo-handle of this process needs no closing.
    let _ = unsafe { TerminateProcess(GetCurrentProcess(), code) };
    std::process::exit(code as i32)
}

/// settle's Host on the real system: this folder's copies, dumps into `logs`.
pub struct SystemHost<F: FnMut() -> bool> {
    pub root: Option<PathBuf>,
    pub logs: PathBuf,
    pub answers: F,
    pub start: Instant,
}

impl<F: FnMut() -> bool> Host for SystemHost<F> {
    fn answers(&mut self) -> bool {
        (self.answers)()
    }
    fn copies(&mut self) -> Vec<u32> {
        self.root.as_deref().map(copies_in).unwrap_or_default()
    }
    fn dump(&mut self, pid: u32) -> Result<String, String> {
        write_dump(pid, &self.logs, DUMPS_KEPT).map(|p| p.file_name().unwrap_or_default().to_string_lossy().into_owned()).map_err(|e| e.to_string())
    }
    fn end(&mut self, pids: &[u32]) -> Vec<u32> {
        end(pids)
    }
    fn now(&mut self) -> Duration {
        self.start.elapsed()
    }
    fn sleep(&mut self, time: Duration) {
        std::thread::sleep(time);
    }
    fn warn(&mut self, message: &str) {
        eprintln!("{message}");
    }
}

#[cfg(test)]
#[path = "process_tests.rs"]
mod tests;
