//! The name a copy of the app answers on (paths.instance_key): one per Windows user.

use sha1::{Digest, Sha1};

/// Program names the app's runtime has had (names.PROCESSES).
pub use common::names::PROCESSES;

/// The user name as Python's getpass.getuser() finds it: the first set of LOGNAME, USER, LNAME, USERNAME.
pub fn user_name(var: impl Fn(&str) -> Option<String>) -> String {
    ["LOGNAME", "USER", "LNAME", "USERNAME"]
        .iter()
        .find_map(|name| var(name).filter(|v| !v.is_empty()))
        .unwrap_or_else(|| "user".to_string())
}

/// "BlackListDetect-" and the first 12 hex digits of the user name's SHA-1.
pub fn instance_key_for(user: &str) -> String {
    let digest = Sha1::digest(user.as_bytes());
    let hex: String = digest.iter().map(|b| format!("{b:02x}")).collect();
    format!("BlackListDetect-{}", &hex[..12])
}

/// This user's key.
pub fn instance_key() -> String {
    instance_key_for(&user_name(|name| std::env::var(name).ok()))
}

/// The named pipe the open copy serves under the key (Qt's QLocalServer name on Windows).
pub fn pipe_path(key: &str) -> String {
    format!(r"\\.\pipe\{key}")
}

/// The mutex held for as long as a copy lives.
pub fn mutex_name(key: &str) -> String {
    format!(r"Local\{key}")
}

/// Send b"show" or b"quit" to the open copy through its pipe. False when none is open.
pub fn message_running_copy(message: &[u8], key: &str) -> bool {
    use std::io::Write;
    if !cfg!(windows) {
        return false;
    }
    match std::fs::OpenOptions::new().write(true).open(pipe_path(key)) {
        Ok(mut pipe) => {
            // The open copy brings its window to the front: the launch the player just made may hand it the right.
            #[cfg(windows)]
            unsafe {
                use windows::Win32::UI::WindowsAndMessaging::{AllowSetForegroundWindow, ASFW_ANY};
                let _ = AllowSetForegroundWindow(ASFW_ANY);
            }
            pipe.write_all(message).is_ok()
        }
        Err(_) => false,
    }
}

/// The longest message a second launch sends (b"show", b"quit"); anything more is cut there.
#[cfg(windows)]
const LONGEST: u64 = 64;

/// Serve the pipe under the key on a thread of its own (Qt's QLocalServer in listen_for_instances): each second
/// launch's whole message goes to `heard`. An error when the pipe cannot be made (another process serves it).
#[cfg(windows)]
pub fn listen(key: &str, heard: impl Fn(Vec<u8>) + Send + 'static) -> std::io::Result<()> {
    let path = pipe_path(key);
    let mut pipe = serve(&path, true)?;
    std::thread::Builder::new().name("Instances".into()).spawn(move || {
        let mut failures = 0;
        loop {
            // One instance waits at a time; the next is made once a copy is in, so another can knock while it is read.
            let next = match wait_for_client(&pipe) {
                Ok(()) => {
                    failures = 0;
                    let next = serve_again(&pipe);
                    heard(read_all(pipe));
                    next
                }
                Err(error) => {
                    // Never silent, never the end of listening: this instance goes, a new one serves.
                    eprintln!("Instances: a launch could not connect: {error}");
                    failures += 1;
                    std::thread::sleep(std::time::Duration::from_millis(50 * failures.min(20)));
                    drop(pipe);
                    None
                }
            };
            let next = next.or_else(|| {
                std::thread::sleep(std::time::Duration::from_millis(200));
                serve(&path, false).map_err(|error| eprintln!("Instances: listening stopped: {error}")).ok()
            });
            match next {
                Some(next) => pipe = next,
                None => return,
            }
        }
    })?;
    Ok(())
}

#[cfg(windows)]
struct Pipe(std::fs::File, String);

#[cfg(windows)]
fn serve(path: &str, first: bool) -> std::io::Result<Pipe> {
    use std::os::windows::io::FromRawHandle;
    use windows::core::HSTRING;
    use windows::Win32::Foundation::INVALID_HANDLE_VALUE;
    use windows::Win32::Storage::FileSystem::{FILE_FLAG_FIRST_PIPE_INSTANCE, PIPE_ACCESS_INBOUND};
    use windows::Win32::System::Pipes::{
        CreateNamedPipeW, PIPE_READMODE_BYTE, PIPE_REJECT_REMOTE_CLIENTS, PIPE_TYPE_BYTE, PIPE_UNLIMITED_INSTANCES, PIPE_WAIT,
    };
    let open = if first { PIPE_ACCESS_INBOUND | FILE_FLAG_FIRST_PIPE_INSTANCE } else { PIPE_ACCESS_INBOUND };
    let mode = PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT | PIPE_REJECT_REMOTE_CLIENTS;
    let handle = unsafe { CreateNamedPipeW(&HSTRING::from(path), open, mode, PIPE_UNLIMITED_INSTANCES, 0, 512, 0, None) };
    if handle == INVALID_HANDLE_VALUE || handle.is_invalid() {
        return Err(std::io::Error::last_os_error());
    }
    Ok(Pipe(unsafe { std::fs::File::from_raw_handle(handle.0) }, path.to_string()))
}

#[cfg(windows)]
fn serve_again(pipe: &Pipe) -> Option<Pipe> {
    serve(&pipe.1, false).map_err(|error| eprintln!("Instances: no next pipe: {error}")).ok()
}

#[cfg(windows)]
fn wait_for_client(pipe: &Pipe) -> std::io::Result<()> {
    use std::os::windows::io::AsRawHandle;
    use windows::Win32::Foundation::{ERROR_NO_DATA, ERROR_PIPE_CONNECTED, HANDLE};
    use windows::Win32::System::Pipes::ConnectNamedPipe;
    match unsafe { ConnectNamedPipe(HANDLE(pipe.0.as_raw_handle()), None) } {
        Ok(()) => Ok(()),
        // The client came between CreateNamedPipe and ConnectNamedPipe; with NO_DATA it has written and gone already,
        // and what it wrote is still there to read.
        Err(error) if [ERROR_PIPE_CONNECTED, ERROR_NO_DATA].iter().any(|code| error.code() == code.to_hresult()) => Ok(()),
        Err(error) => Err(std::io::Error::other(error)),
    }
}

/// Up to the client closing its end (a broken pipe reads as the end).
#[cfg(windows)]
fn read_all(pipe: Pipe) -> Vec<u8> {
    use std::io::Read;
    let mut message = Vec::new();
    let _ = (&pipe.0).take(LONGEST).read_to_end(&mut message);
    message
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn key_matches_paths_instance_key() {
        // Values written by blacklist_detect.paths.instance_key (hashlib.sha1 of the user name).
        assert_eq!(instance_key_for("root"), "BlackListDetect-dc76e9f0c000");
        assert_eq!(instance_key_for("alice"), "BlackListDetect-522b276a356b");
    }

    #[test]
    fn user_name_follows_getpass_order() {
        let env = |pairs: &'static [(&'static str, &'static str)]| move |n: &str| pairs.iter().find(|p| p.0 == n).map(|p| p.1.to_string());
        assert_eq!(user_name(env(&[("USERNAME", "win"), ("USER", "unix")])), "unix");
        assert_eq!(user_name(env(&[("USERNAME", "win"), ("LOGNAME", "")])), "win");
        assert_eq!(user_name(env(&[])), "user");
    }

    #[test]
    fn names_on_the_pipe_and_mutex() {
        assert_eq!(pipe_path("K"), r"\\.\pipe\K");
        assert_eq!(mutex_name("K"), r"Local\K");
        #[cfg(not(windows))]
        assert!(!message_running_copy(b"show", "K"));
    }

    /// A second launch is answered at once, every time, and its message reaches the open copy whole.
    #[cfg(windows)]
    #[test]
    fn a_second_launch_is_answered_at_once() {
        use std::time::{Duration, Instant};
        let key = format!("BlackListDetect-test-{}", std::process::id());
        let (tx, rx) = std::sync::mpsc::channel();
        listen(&key, move |message| {
            let _ = tx.send(message);
        })
        .unwrap();
        assert!(listen(&key, |_| {}).is_err(), "only one copy serves the key");
        for message in [&b"show"[..], b"", b"quit", b"show"] {
            let start = Instant::now();
            let sent = (0..40).any(|_| message_running_copy(message, &key) || {
                std::thread::sleep(Duration::from_millis(25));
                false
            });
            assert!(sent, "{message:?} was not taken");
            assert_eq!(rx.recv_timeout(Duration::from_secs(3)).unwrap(), message);
            assert!(start.elapsed() < Duration::from_secs(3), "{:?}", start.elapsed());
        }
    }
}

