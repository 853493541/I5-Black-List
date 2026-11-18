//! 导出日志 (diagnostics.export_logs from ui.py): the computer and the 设置 in a few lines, the last 环境测试, and
//! every log, in one text file on the Desktop with the account's name hidden.

use data::diag::{self, Machine, Screen};
use data::logs::export::{export_logs, Account};
use std::path::{Path, PathBuf};

/// This computer as machine_line names it (the registry, memory, GPUs on Windows; Python's fallback elsewhere).
pub fn machine() -> Machine {
    #[cfg(windows)]
    {
        let facts = win::machine::facts();
        Machine {
            cpu: facts.cpu,
            threads: facts.threads,
            memory_total_gb: facts.memory_total_gb,
            memory_free_gb: facts.memory_free_gb,
            gpus: facts.gpus,
            product: facts.product,
            display_version: facts.display_version,
            build: facts.build,
            version: facts.version,
            power: String::new(),
        }
    }
    #[cfg(not(windows))]
    Machine::fallback()
}

fn screens() -> String {
    #[cfg(windows)]
    let found = win::machine::screens().map(|list| list.into_iter().map(|(width, height, ratio)| Screen { width, height, ratio }).collect::<Vec<_>>());
    #[cfg(not(windows))]
    let found: Option<Vec<Screen>> = None;
    diag::screens_line(found.as_deref())
}

/// The account the paths name, to hide it.
pub fn account() -> Account {
    let var = |name: &str| std::env::var(name).unwrap_or_default();
    let home = if cfg!(windows) { var("USERPROFILE") } else { var("HOME") };
    let user = if cfg!(windows) { var("USERNAME") } else { var("USER") };
    #[cfg(windows)]
    let short = win::machine::short_name(&home);
    #[cfg(not(windows))]
    let short = String::new();
    Account { home, user, short }
}

/// The Desktop (where Windows keeps it), else ~/Desktop.
pub fn desktop(account: &Account) -> PathBuf {
    #[cfg(windows)]
    if let Some(found) = win::machine::desktop() {
        return found;
    }
    diag::desktop_fallback(Path::new(&account.home))
}

/// Writes the export for the data folder `root` into `folder`; `report` is the last 环境测试 ("" for none).
pub fn export_into(root: &Path, store: &data::store::Store, version: &str, report: &str, folder: &Path, account: &Account) -> std::io::Result<PathBuf> {
    let now = chrono::Local::now().naive_local();
    let summary = diag::summary_text(version, now, &machine().line(), &screens(), "cpu", &diag::Settings::from_store(store));
    export_logs(root, &summary, folder, report, &diag::export_stamp(now), account)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_export_holds_the_summary_and_the_logs_with_the_account_hidden() {
        let dir = tempfile::tempdir().unwrap();
        let root = dir.path().join("root");
        let logs = data::logs::log_dir(&root);
        std::fs::create_dir_all(&logs).unwrap();
        std::fs::write(logs.join("app.log"), "checked at /home/xiaolu/x\n").unwrap();
        let store = data::store::Store::open(Some(root.clone()), data::store::Clock::default());
        let account = Account { home: "/home/xiaolu".into(), user: "xiaolu".into(), short: String::new() };
        let path = export_into(&root, &store, "v9.9.9", "", &dir.path().join("desk"), &account).unwrap();
        let text = std::fs::read_to_string(path).unwrap();
        assert!(text.starts_with("==== 电脑和设置 ====\n模仿者小工具 v9.9.9\n"));
        assert!(text.contains("==== app.log ====\nchecked at ~/x"));
        assert!(!text.contains("xiaolu"));
    }
}
