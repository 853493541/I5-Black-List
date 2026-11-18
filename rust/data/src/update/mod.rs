//! New versions, from the project's GitHub releases: a port of blacklist_detect/updater.py.
//!
//! version.json names the version, what is new, the update zip's address, size and SHA-256, and the
//! oldest version the zip can be laid over; version.json.sig is its Ed25519 signature, checked against
//! the same public key. After GitHub come the same public download proxies (MIRRORS); they are trusted
//! with nothing, as the signature and the zip's SHA-256 are checked whatever the route.

pub mod fetch;
pub mod mirrors;
pub mod net;
pub mod py;
pub mod stage;
pub mod switchover;

use base64::Engine as _;
use ed25519_dalek::{Signature, VerifyingKey};
use serde_json::Value;

pub const REPO: &str = "853493541/I5-Black-List";
pub const MANIFEST_URL: &str = "https://github.com/853493541/I5-Black-List/releases/latest/download/version.json";
pub const RELEASES_URL: &str = "https://github.com/853493541/I5-Black-List/releases/latest";
pub const DOWNLOADS: &str = "https://github.com/853493541/I5-Black-List/releases/download/";
/// GitHub itself (""), then the proxies, in updater.py's order.
pub const MIRRORS: [&str; 7] = [
    "",
    "https://gh-proxy.org/",
    "https://ghproxy.net/",
    "https://cdn.gh-proxy.org/",
    "https://edgeone.gh-proxy.org/",
    "https://ghfast.top/",
    "https://wget.la/",
];
pub const MIRROR_FILE: &str = "mirrors.json";
/// The public half of the release key (updater.PUBLIC_KEY).
pub const PUBLIC_KEY: &str = "N4neQZQZcRKxH5DP/85SZr1cCq3s2sMaZFzG3lCiO14=";
pub const MAX_SIZE: i64 = 100_000_000;

/// Something went wrong; the message is for the player, word for word as updater.py says it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum UpdateError {
    /// 读不到更新信息，等会儿再试
    Unreadable,
    /// 连不上更新服务器，等会儿再试
    NoConnection,
    /// 下载失败，看看网络再试
    DownloadFailed,
    /// 更新包有问题，这次先不更新
    BadDownload,
    /// 更新包不完整，再试一次
    Incomplete,
    /// 更新包坏了，再试一次
    Broken,
    /// A file error Python would not have caught (it raises OSError out of the updater).
    Io(String),
}

impl UpdateError {
    pub fn message(&self) -> &str {
        match self {
            Self::Unreadable => "读不到更新信息，等会儿再试",
            Self::NoConnection => "连不上更新服务器，等会儿再试",
            Self::DownloadFailed => "下载失败，看看网络再试",
            Self::BadDownload => "更新包有问题，这次先不更新",
            Self::Incomplete => "更新包不完整，再试一次",
            Self::Broken => "更新包坏了，再试一次",
            Self::Io(text) => text,
        }
    }
}

impl std::fmt::Display for UpdateError {
    fn fmt(&self, out: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        out.write_str(self.message())
    }
}

impl std::error::Error for UpdateError {}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Release {
    pub version: String,
    pub url: String,
    pub sha256: String,
    pub size: i64,
    pub base: String,
    pub notes: Vec<String>,
    /// The address prefix version.json came through ("" for GitHub), tried first for the zip.
    pub mirror: String,
    /// Proxies the release names, for later checks.
    pub mirrors: Vec<String>,
}

impl Release {
    /// The update zip only completes a folder at least as new as base.
    pub fn needs_full(&self, current: &str) -> bool {
        parse_version(current) < parse_version(&self.base)
    }
}

/// v0.4.0 -> [0, 4, 0]. Anything unreadable is empty, and sorts first.
pub fn parse_version(text: &str) -> Vec<i64> {
    py::strip(text)
        .trim_start_matches(['v', 'V'])
        .split('.')
        .map(py::parse_int)
        .collect::<Option<Vec<_>>>()
        .unwrap_or_default()
}

/// True when signature (base64) is the release key's signature of manifest; key None means PUBLIC_KEY.
pub fn verify(manifest: &[u8], signature: &str, key: Option<&str>) -> bool {
    let key = key.unwrap_or(PUBLIC_KEY);
    if key.is_empty() {
        return false;
    }
    let (Some(key), Some(signature)) = (py::b64decode(key), py::b64decode(py::strip(signature))) else {
        return false;
    };
    let (Ok(key), Ok(signature)) = (<[u8; 32]>::try_from(key), Signature::from_slice(&signature)) else {
        return false;
    };
    // Cofactorless, canonical S: the check OpenSSL makes for Python's cryptography.
    use ed25519_dalek::Verifier as _;
    VerifyingKey::from_bytes(&key).is_ok_and(|key| key.verify(manifest, &signature).is_ok())
}

/// version.json as a Release. Only zips from this project's releases are accepted.
pub fn read_manifest(manifest: &[u8]) -> Result<Release, UpdateError> {
    let release = parse_manifest(manifest).ok_or(UpdateError::Unreadable)?;
    if !release.url.starts_with(DOWNLOADS) || parse_version(&release.version).is_empty() {
        return Err(UpdateError::Unreadable);
    }
    if !(0 < release.size && release.size <= MAX_SIZE) || release.sha256.chars().count() != 64 {
        return Err(UpdateError::Unreadable);
    }
    Ok(release)
}

fn parse_manifest(manifest: &[u8]) -> Option<Release> {
    let data: Value = serde_json::from_str(std::str::from_utf8(manifest).ok()?).ok()?;
    let data = data.as_object()?;
    let update = data.get("update")?.as_object()?;
    let version = py::str_of(data.get("version")?)?;
    let strings = |key: &str| -> Option<Vec<String>> {
        data.get(key).map_or(Some(Vec::new()), |value| py::iter_of(value)?.iter().map(py::str_of).collect())
    };
    Some(Release {
        url: py::str_of(update.get("url")?)?,
        sha256: py::str_of(update.get("sha256")?)?.to_lowercase(),
        size: py::int_of(update.get("size")?)?,
        base: py::str_of(data.get("base").unwrap_or(data.get("version")?))?,
        notes: strings("notes")?,
        mirrors: strings("mirrors")?.into_iter().filter(|item| good_mirror(item)).collect(),
        version,
        mirror: String::new(),
    })
}

/// An https address ending in /, nothing else (updater._MIRROR): a GitHub address is put right after it.
pub fn good_mirror(prefix: &str) -> bool {
    if prefix.is_empty() {
        return true;
    }
    if prefix.chars().count() > 200 {
        return false;
    }
    let Some(rest) = prefix.strip_prefix("https://") else { return false };
    let Some((host, path)) = rest.split_once('/') else { return false };
    let (name, port) = host.split_once(':').unwrap_or((host, ""));
    let host_ok = !name.is_empty() && name.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'.' || b == b'-');
    let port_ok = !host.contains(':') || (!port.is_empty() && port.bytes().all(|b| b.is_ascii_digit()));
    let path_ok = path.is_empty()
        || (path.ends_with('/')
            && path[..path.len() - 1]
                .split('/')
                .all(|part| !part.is_empty() && part.bytes().all(|b| b.is_ascii_alphanumeric() || b"._~-".contains(&b))));
    host_ok && port_ok && path_ok
}

/// The SHA-256 of bytes, as lowercase hex.
pub fn sha256_hex(data: &[u8]) -> String {
    use sha2::Digest as _;
    hex(&sha2::Sha256::digest(data))
}

pub(crate) fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

/// base64 for tests and tools: the standard alphabet with padding, as Python's b64encode.
pub fn b64encode(data: &[u8]) -> String {
    base64::engine::general_purpose::STANDARD.encode(data)
}
