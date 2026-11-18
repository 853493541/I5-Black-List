use super::*;
use crate::settle::{settle, WAIT_OTHER_OWNS};

/// A process whose program is root\runtime\模仿者小工具.exe, as the app's is: Windows' ping, renamed.
fn copy_running_from(root: &Path) -> std::process::Child {
    let runtime = root.join("runtime");
    std::fs::create_dir_all(&runtime).unwrap();
    let exe = runtime.join("模仿者小工具.exe");
    let system = std::env::var("SystemRoot").unwrap_or_else(|_| r"C:\Windows".into());
    std::fs::copy(Path::new(&system).join(r"System32\PING.EXE"), &exe).unwrap();
    let child = std::process::Command::new(&exe).args(["-n", "60", "127.0.0.1"]).stdout(std::process::Stdio::null()).spawn().unwrap();
    std::thread::sleep(Duration::from_millis(500));
    child
}

fn scratch(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("win-test-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    dir
}

#[test]
fn only_the_first_start_owns_the_mutex() {
    let key = format!("BlackListDetect-test-{}", std::process::id());
    let first = claim(&key);
    assert!(first.first);
    assert!(!claim(&key).first, "a second instance is detected");
    drop(first);
}

#[test]
fn processes_include_this_one() {
    let me = std::process::id();
    assert!(processes().iter().any(|(pid, _)| *pid == me));
    assert!(!running("no-such-program-here.exe"));
}

#[test]
fn a_copy_from_this_folder_is_found_and_nothing_else() {
    let dir = scratch("found");
    let mut child = copy_running_from(&dir.join("app"));
    assert_eq!(copies_in(&dir.join("app")), vec![child.id()]);
    assert_eq!(copies_in(&dir.join("elsewhere")), Vec::<u32>::new());
    child.kill().unwrap();
    child.wait().unwrap();
}

#[test]
fn a_copy_that_never_answers_is_dumped_and_ended() {
    let dir = scratch("stuck");
    let mut child = copy_running_from(&dir.join("app"));
    let pid = child.id();
    let mut host = SystemHost { root: Some(dir.join("app")), logs: dir.join("logs"), answers: || false, start: Instant::now() };
    assert!(!settle(&mut host, true, WAIT_OTHER_OWNS));
    assert!(child.wait().is_ok());
    assert!(copies_in(&dir.join("app")).is_empty());
    let dump = std::fs::read(dir.join("logs").join(format!("stuck-{pid}.dmp"))).unwrap();
    assert_eq!(&dump[..4], b"MDMP");
}

#[test]
fn a_copy_that_answers_is_left_alone() {
    let dir = scratch("answers");
    let mut child = copy_running_from(&dir.join("app"));
    let mut host = SystemHost { root: Some(dir.join("app")), logs: dir.join("logs"), answers: || true, start: Instant::now() };
    assert!(settle(&mut host, false, WAIT_OTHER_OWNS));
    assert!(child.try_wait().unwrap().is_none());
    child.kill().unwrap();
    child.wait().unwrap();
}

#[test]
fn only_the_newest_dumps_are_kept() {
    let dir = scratch("dumps");
    let mut child = copy_running_from(&dir.join("app"));
    for name in ["stuck-1.dmp", "stuck-2.dmp", "stuck-3.dmp"] {
        std::fs::create_dir_all(dir.join("logs")).unwrap();
        std::fs::write(dir.join("logs").join(name), b"old").unwrap();
        std::thread::sleep(Duration::from_millis(20));
    }
    let path = write_dump(child.id(), &dir.join("logs"), DUMPS_KEPT).unwrap();
    assert!(path.exists());
    assert!(!dir.join("logs").join("stuck-1.dmp").exists());
    assert_eq!(std::fs::read_dir(dir.join("logs")).unwrap().count(), DUMPS_KEPT);
    child.kill().unwrap();
    child.wait().unwrap();
}
