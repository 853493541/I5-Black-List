//! The network side of updater.py: fetch_release() and download(), behind a trait so tests run offline.

use std::io::Write as _;
use std::path::{Path, PathBuf};

use sha2::Digest as _;

use super::mirrors::{mirrors, remember};
use super::{hex, parse_version, read_manifest, verify, Release, UpdateError, MANIFEST_URL};

/// One answer: the status after redirects, and the body.
pub struct Response {
    pub status: u16,
    pub body: Vec<u8>,
}

/// A request that failed (requests.RequestException): no connection, a timeout, a cut transfer, or a
/// status of 400 or more where the updater calls raise_for_status().
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HttpError(pub String);

/// Plain downloads of public files. The app's User-Agent is `BlackListDetect/<version>`, and its timeouts
/// are 5 s to connect and 15 s between bytes (updater.TIMEOUT).
pub trait Http {
    /// The whole answer, whatever its status.
    fn get(&mut self, url: &str) -> Result<Response, HttpError>;
    /// The body in chunks (about 64 KiB), after a status check; `chunk` returns false to stop reading.
    fn stream(&mut self, url: &str, chunk: &mut dyn FnMut(&[u8]) -> bool) -> Result<(), HttpError>;
}

fn checked(response: Result<Response, HttpError>) -> Result<Response, HttpError> {
    let response = response?;
    if response.status >= 400 {
        return Err(HttpError(response.status.to_string()));
    }
    Ok(response)
}

/// The newest release when it is newer than current and properly signed; None when there is none.
/// `key` None is the release key; `folder` holds mirrors.json.
pub fn fetch_release(http: &mut dyn Http, current: &str, folder: &Path, key: Option<&str>) -> Result<Option<Release>, UpdateError> {
    let (mut missing, mut forged) = (0, 0);
    let tried = mirrors(folder);
    for prefix in &tried {
        let manifest = match http.get(&format!("{prefix}{MANIFEST_URL}")) {
            Ok(response) if response.status == 404 => {
                missing += 1;
                continue;
            }
            response => match checked(response) {
                Ok(response) => response.body,
                Err(_) => continue,
            },
        };
        let Ok(signature) = checked(http.get(&format!("{prefix}{MANIFEST_URL}.sig"))) else { continue };
        // requests' .text: the signature is ASCII or it is no signature.
        if !verify(&manifest, &String::from_utf8_lossy(&signature.body), key) {
            forged += 1;
            continue;
        }
        let release = Release { mirror: prefix.clone(), ..read_manifest(&manifest)? };
        remember(folder, prefix, &release.mirrors);
        return Ok((parse_version(&release.version) > parse_version(current)).then_some(release));
    }
    if forged > 0 {
        return Err(UpdateError::Unreadable);
    }
    if missing == tried.len() {
        return Ok(None);
    }
    Err(UpdateError::NoConnection)
}

/// The zip's file name in folder, as updater.download names it.
pub fn zip_path(release: &Release, folder: &Path) -> PathBuf {
    folder.join(format!("BlackListDetect-{}-update.zip", release.version))
}

/// Fetch the update zip into folder and check it is the one the release named. `progress(got, total)`
/// after each chunk; `mirror_folder` holds mirrors.json.
pub fn download(
    release: &Release,
    folder: &Path,
    mut progress: Option<&mut dyn FnMut(i64, i64)>,
    http: &mut dyn Http,
    mirror_folder: &Path,
) -> Result<PathBuf, UpdateError> {
    std::fs::create_dir_all(folder).map_err(|error| UpdateError::Io(error.to_string()))?;
    let target = zip_path(release, folder);
    let mut order = vec![release.mirror.clone()];
    order.extend(mirrors(mirror_folder).into_iter().filter(|prefix| *prefix != release.mirror));
    let mut failure = UpdateError::DownloadFailed;
    for prefix in order {
        let mut out = std::fs::File::create(&target).map_err(|error| UpdateError::Io(error.to_string()))?;
        let (mut digest, mut got, mut written) = (sha2::Sha256::new(), 0i64, Ok(()));
        let fetched = http.stream(&format!("{prefix}{}", release.url), &mut |chunk| {
            got += chunk.len() as i64;
            if got > release.size {
                return false;
            }
            digest.update(chunk);
            written = out.write_all(chunk);
            if written.is_err() {
                return false;
            }
            if let Some(progress) = progress.as_mut() {
                progress(got, release.size);
            }
            true
        });
        drop(out);
        written.map_err(|error| UpdateError::Io(error.to_string()))?;
        if fetched.is_err() {
            let _ = std::fs::remove_file(&target);
            continue;
        }
        if got == release.size && hex(&digest.finalize()) == release.sha256 {
            if prefix != release.mirror {
                remember(mirror_folder, &prefix, &[]);
            }
            return Ok(target);
        }
        // Not the zip the release named: another address may pass the right one.
        let _ = std::fs::remove_file(&target);
        failure = UpdateError::BadDownload;
    }
    Err(failure)
}
