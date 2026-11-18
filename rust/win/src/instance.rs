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
        Ok(mut pipe) => pipe.write_all(message).is_ok(),
        Err(_) => false,
    }
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
}
