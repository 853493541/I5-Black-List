//! 导出日志: the logs in one text file, with the Windows account's name hidden (a port of
//! diagnostics.export_logs, _without_user, _dump_without_user, _dumps_text and dumps_in).

use std::io::{Read as _, Write as _};
use std::path::{Path, PathBuf};

use base64::Engine as _;

use super::log_dir;
use crate::update::py;

pub const DUMP_LINE: usize = 100;
pub const DUMP_MAX: usize = 8_000_000;

/// Who the account is: the home folder (os.path.expanduser("~")), USERNAME, and the home folder's
/// 8.3 short name ("" when it has none; the win crate reads it).
#[derive(Debug, Clone, Default)]
pub struct Account {
    pub home: String,
    pub user: String,
    pub short: String,
}

/// Paths in error messages name the Windows account: the export says ~ instead (and <user> for the name).
pub fn without_user(text: &str, account: &Account) -> String {
    let mut text = text.to_string();
    let home_slashed = account.home.replace('\\', "/");
    for (value, mark) in [(account.home.as_str(), "~"), (home_slashed.as_str(), "~"), (account.user.as_str(), "<user>")] {
        if value.chars().count() > 2 {
            text = text.replace(value, mark);
        }
    }
    text
}

/// A dump's paths name the account too: "Users\<name>" becomes "Users\" and x's of the same length, so
/// the dump keeps its size, in UTF-16 and UTF-8, either slash, any ASCII case. (Python also tries the
/// ANSI code page, "mbcs", which only exists on Windows: not done here.)
pub fn dump_without_user(data: &[u8], account: &Account) -> Vec<u8> {
    let home_name = Path::new(&account.home.replace('\\', "/")).file_name().map(|name| name.to_string_lossy().into_owned());
    let mut names: Vec<String> = [Some(account.user.clone()), home_name, Some(account.short.clone())].into_iter().flatten().collect();
    names.retain(|name| !name.is_empty());
    names.dedup();
    let mut data = data.to_vec();
    for name in &names {
        for sep in ['\\', '/'] {
            let found = format!("Users{sep}{name}");
            let utf16 = |text: &str| text.encode_utf16().flat_map(u16::to_le_bytes).collect::<Vec<u8>>();
            let wide_pad: Vec<u8> = utf16(&"x".repeat(name.chars().count()));
            let (wide, wide_keep) = (utf16(&found), utf16(&format!("Users{sep}")).len());
            data = replace_ascii_nocase(&data, &wide, wide_keep, &wide_pad);
            let narrow = found.as_bytes();
            let narrow_pad = vec![b'x'; narrow.len() - 6];
            data = replace_ascii_nocase(&data, narrow, 6, &narrow_pad);
        }
    }
    data
}

/// re.sub(re.escape(found), keep + pad, data, flags=re.IGNORECASE) on bytes: ASCII letters fold.
fn replace_ascii_nocase(data: &[u8], found: &[u8], keep: usize, pad: &[u8]) -> Vec<u8> {
    let mut out = Vec::with_capacity(data.len());
    let mut at = 0;
    while at < data.len() {
        if data.len() - at >= found.len() && data[at..at + found.len()].eq_ignore_ascii_case(found) {
            out.extend_from_slice(&data[at..at + keep]);
            out.extend_from_slice(pad);
            at += found.len();
        } else {
            out.push(data[at]);
            at += 1;
        }
    }
    out
}

/// Stuck copies' dumps (logs/stuck-*.dmp), oldest first, zlib-compressed and in base64 lines.
pub fn dumps_text(logs: &Path, account: &Account) -> String {
    let mut dumps: Vec<(std::time::SystemTime, PathBuf)> = std::fs::read_dir(logs)
        .map(|entries| {
            entries
                .flatten()
                .map(|entry| entry.path())
                .filter(|path| path.file_name().and_then(|n| n.to_str()).is_some_and(|n| n.starts_with("stuck-") && n.ends_with(".dmp")))
                .filter_map(|path| Some((std::fs::metadata(&path).ok()?.modified().ok()?, path)))
                .collect()
        })
        .unwrap_or_default();
    dumps.sort();
    let mut parts: Vec<String> = Vec::new();
    for (_, path) in dumps {
        let Ok(data) = std::fs::read(&path) else { continue };
        let name = path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
        let mut packer = flate2::write::ZlibEncoder::new(Vec::new(), flate2::Compression::best());
        let packed = packer.write_all(&dump_without_user(&data, account)).and_then(|()| packer.finish()).unwrap_or_default();
        let coded = base64::engine::general_purpose::STANDARD.encode(packed);
        if coded.len() > DUMP_MAX {
            parts.extend([format!("==== {name} ===="), format!("(left out: {} characters)", thousands(coded.len())), String::new()]);
            continue;
        }
        parts.push(format!("==== {name} (zlib, base64) ===="));
        parts.extend(coded.as_bytes().chunks(DUMP_LINE).map(|line| String::from_utf8_lossy(line).into_owned()));
        parts.push(String::new());
    }
    parts.join("\n")
}

fn thousands(number: usize) -> String {
    let digits = number.to_string();
    let mut out = String::new();
    for (at, c) in digits.chars().enumerate() {
        if at > 0 && (digits.len() - at) % 3 == 0 {
            out.push(',');
        }
        out.push(c);
    }
    out
}

/// The dumps an export carries, by file name, as they were written.
pub fn dumps_in(text: &str) -> Vec<(String, Vec<u8>)> {
    let mut found = Vec::new();
    let mut lines = text.split('\n').peekable();
    while let Some(line) = lines.next() {
        let Some(name) = line.strip_prefix("==== ").and_then(|rest| rest.strip_suffix(" (zlib, base64) ====")) else { continue };
        let digits = name.strip_prefix("stuck-").and_then(|rest| rest.strip_suffix(".dmp"));
        if !digits.is_some_and(|d| !d.is_empty() && d.bytes().all(|b| b.is_ascii_digit())) {
            continue;
        }
        let mut coded = String::new();
        while let Some(next) = lines.peek().filter(|l| !l.is_empty() && l.bytes().all(|b| b.is_ascii_alphanumeric() || b"+/=".contains(&b))) {
            coded.push_str(next);
            lines.next();
        }
        let mut data = Vec::new();
        let packed = py::b64decode(&coded).unwrap_or_default();
        if flate2::read::ZlibDecoder::new(packed.as_slice()).read_to_end(&mut data).is_ok() {
            found.push((name.to_string(), data));
        }
    }
    found
}

/// One text file in folder: the computer and settings (summary), the last 环境测试 (report), the logs
/// oldest first, then the dumps. `stamp` is the local time, as "%Y%m%d-%H%M". Returns its path.
pub fn export_logs(root: &Path, summary: &str, folder: &Path, report: &str, stamp: &str, account: &Account) -> std::io::Result<PathBuf> {
    std::fs::create_dir_all(folder)?;
    let target = folder.join(format!("模仿者小工具_日志_{stamp}.txt"));
    let mut parts: Vec<String> = vec!["==== 电脑和设置 ====".into(), summary.into()];
    if !report.is_empty() {
        parts.extend(["==== 最近一次环境测试 ====".into(), report.into(), String::new()]);
    }
    let logs = log_dir(root);
    let mut files: Vec<(u64, PathBuf)> = std::fs::read_dir(&logs)
        .map(|entries| {
            entries
                .flatten()
                .filter_map(|entry| {
                    let name = entry.file_name().to_string_lossy().into_owned();
                    let at = name.strip_prefix("app.log.")?;
                    (!at.is_empty() && at.chars().all(|c| c.is_ascii_digit())).then(|| (at.parse().unwrap_or(u64::MAX), entry.path()))
                })
                .collect()
        })
        .unwrap_or_default();
    files.sort_by(|a, b| b.0.cmp(&a.0));
    let mut files: Vec<PathBuf> = files.into_iter().map(|(_, path)| path).collect();
    files.extend(["app.log", "crash.log"].map(|name| logs.join(name)).into_iter().filter(|path| path.is_file()));
    for path in files {
        let Ok(data) = std::fs::read(&path) else { continue };
        let text = String::from_utf8_lossy(&data);
        let text = py::strip(&text);
        if !text.is_empty() {
            let name = path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
            parts.extend([format!("==== {name} ===="), text.to_string(), String::new()]);
        }
    }
    let body = format!("{}\n{}", without_user(&parts.join("\n"), account), dumps_text(&logs, account));
    std::fs::File::create(&target)?.write_all(body.replace('\n', super::NEWLINE).as_bytes())?;
    Ok(target)
}
