"""New versions, from the project's GitHub releases.

Each release carries the small update zip (the app code, not the runtime or the models) and
version.json, which names the version, what is new, the zip's address, size and SHA-256, and
the oldest version the zip can be laid over. version.json.sig is an Ed25519 signature of
version.json, made with a key that never leaves the publisher's PC; the app holds the public
half, so a release that key did not sign is ignored even if the download page was taken over.

The app only asks: it checks once when it opens, and a friend
clicks 更新 to download. The zip is unpacked into update.new beside the app; the launcher
lays it over the folder on the next start, keeping
what it replaced in update.old, and puts that back if the new version never says it started.
Nothing about the player is sent: the requests are plain downloads of public files.

From mainland China github.com is often slow or cut off, so after GitHub the app goes through
public download proxies (MIRRORS), in the order that worked best from inside China: each takes a
GitHub address after its own and passes the same file through. They are trusted with nothing: version.json must carry the release key's signature and
the zip must match its SHA-256, so a proxy can at worst fail or be slow. The one that worked is
tried first next time, and a signed version.json may name newer proxies for when these go away.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import shutil
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath

from blacklist_detect import __version__
from blacklist_detect.names import LAUNCHERS, PROCESSES, launcher_in

log = logging.getLogger(__name__)

REPO = "853493541/I5-Black-List"
MANIFEST_URL = f"https://github.com/{REPO}/releases/latest/download/version.json"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"
DOWNLOADS = f"https://github.com/{REPO}/releases/download/"
# Where to fetch from: GitHub itself (""), then public proxies that put a GitHub address after their own.
# GitHub comes first, being the source; from mainland China it is often cut off, and then the route
# that worked is remembered and tried first from then on (mirrors()). The proxies are from the list
# kept in XIU2's 「GitHub 增强 - 高速下载」 (github.com/XIU2/UserScript), from four operators so that
# one going down leaves the rest. Each passed `release.py check --each` (signature and zip) on
# 2026-10-12, and they are in the order they did that day fetching version.json from 12 Globalping
# probes inside mainland China (Unicom, Mobile, Telecom, Tencent, Alibaba):
#   GitHub 6/12 · gh-proxy.org 12/12 · ghproxy.net 11/12 · cdn.gh-proxy.org 10/10 online ·
#   edgeone.gh-proxy.org 10/11 · ghfast.top 8/12 · wget.la 10/10 but about 4 s.
# gh.ddlc.top answered 429 (too many requests). They come and go; a signed version.json can name new ones.
MIRRORS = (
    "",
    "https://gh-proxy.org/",
    "https://ghproxy.net/",
    "https://cdn.gh-proxy.org/",
    "https://edgeone.gh-proxy.org/",
    "https://ghfast.top/",
    "https://wget.la/",
)
# The proxy that worked last and any a release named, kept beside the settings.
MIRROR_FILE = "mirrors.json"
_MIRROR = re.compile(r"https://[A-Za-z0-9.-]+(?::[0-9]+)?/(?:[A-Za-z0-9._~-]+/)*")
# The public half of the release key, made by `python build/release.py keygen`.
PUBLIC_KEY = "N4neQZQZcRKxH5DP/85SZr1cCq3s2sMaZFzG3lCiO14="

FOLDER = "BlackListDetect"
STAGED = "update.new"
BACKUP = "update.old"
PENDING = "update.check"
VERSION_FILE = ".version"
# What an update may put in the folder: the app, the launcher, the app's exe, the instructions.
_ALLOWED_FILES = {*LAUNCHERS, *(f"runtime/{name}" for name in PROCESSES), "使用说明.txt"}
_ALLOWED_DIR = "blacklist_detect"
MAX_SIZE = 100_000_000
# Seconds to connect, then between bytes: a cut-off address is given up on soon, a slow one is not.
TIMEOUT = (5, 15)


class UpdateError(Exception):
    """Something went wrong; the message is for the player."""


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    sha256: str
    size: int
    base: str
    notes: tuple[str, ...] = field(default_factory=tuple)
    # The address prefix version.json came through ("" for GitHub), tried first for the zip.
    mirror: str = ""
    # Proxies the release names, for later checks.
    mirrors: tuple[str, ...] = field(default_factory=tuple)

    def needs_full(self, current: str = __version__) -> bool:
        """The update zip only completes a folder at least as new as base."""
        return parse_version(current) < parse_version(self.base)


def parse_version(text: str) -> tuple[int, ...]:
    """v0.4.0 -> (0, 4, 0). Anything unreadable sorts first."""
    parts = text.strip().lstrip("vV").split(".")
    try:
        return tuple(int(part) for part in parts)
    except ValueError:
        return ()


def app_root() -> Path | None:
    """The folder the app runs from, when it is a release folder. None when run from the source."""
    root = Path(__file__).resolve().parent.parent
    if (root / "runtime").is_dir() and launcher_in(root) is not None:
        return root
    return None


def verify(manifest: bytes, signature: str, key: str | None = None) -> bool:
    """True when signature (base64) is the release key's signature of manifest."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    key = PUBLIC_KEY if key is None else key
    if not key:
        return False
    try:
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(key))
        public.verify(base64.b64decode(signature.strip()), manifest)
    except (InvalidSignature, ValueError):
        return False
    return True


def read_manifest(manifest: bytes) -> Release:
    """version.json as a Release. Only zips from this project's releases are accepted."""
    try:
        data = json.loads(manifest.decode("utf-8"))
        update = data["update"]
        release = Release(
            version=str(data["version"]),
            url=str(update["url"]),
            sha256=str(update["sha256"]).lower(),
            size=int(update["size"]),
            base=str(data.get("base", data["version"])),
            notes=tuple(str(line) for line in data.get("notes", ())),
            mirrors=tuple(str(item) for item in data.get("mirrors", ()) if _good_mirror(str(item))),
        )
    except (ValueError, KeyError, TypeError) as error:
        raise UpdateError("读不到更新信息，等会儿再试") from error
    if not release.url.startswith(DOWNLOADS) or not parse_version(release.version):
        raise UpdateError("读不到更新信息，等会儿再试")
    if not 0 < release.size <= MAX_SIZE or len(release.sha256) != 64:
        raise UpdateError("读不到更新信息，等会儿再试")
    return release


def _good_mirror(prefix: str) -> bool:
    """An https address ending in /, nothing else: a GitHub address is put right after it."""
    return prefix == "" or (len(prefix) <= 200 and _MIRROR.fullmatch(prefix) is not None)


def _mirror_file() -> Path:
    from blacklist_detect.paths import app_dir

    return app_dir() / MIRROR_FILE


def mirrors() -> list[str]:
    """Where to try, in order: the one that worked last, MIRRORS as listed, then any a release named."""
    order = list(MIRRORS)
    # None until something has worked: "" would mean GitHub, and put it ahead of the list.
    preferred: str | None = None
    try:
        saved = json.loads(_mirror_file().read_text(encoding="utf-8"))
        if "preferred" in saved:
            preferred = str(saved["preferred"])
        listed = [str(item) for item in saved.get("listed", [])]
    except (OSError, ValueError, AttributeError, TypeError):
        listed = []
    for prefix in listed:
        if _good_mirror(prefix) and prefix not in order:
            order.append(prefix)
    if preferred is not None and _good_mirror(preferred) and preferred in order:
        order.remove(preferred)
        order.insert(0, preferred)
    return order


def _remember(preferred: str, listed: tuple[str, ...] = ()) -> None:
    path = _mirror_file()
    try:
        if not listed:
            listed = tuple(json.loads(path.read_text(encoding="utf-8")).get("listed", []))
    except (OSError, ValueError, AttributeError, TypeError):
        listed = ()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"preferred": preferred, "listed": [item for item in listed if _good_mirror(item)]}
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError:
        log.info("Could not remember the update address", exc_info=True)


def _session():  # noqa: ANN202
    import requests

    session = requests.Session()
    session.headers["User-Agent"] = f"BlackListDetect/{__version__}"
    return session


def fetch_release(session=None, current: str = __version__) -> Release | None:  # noqa: ANN001
    """The newest release when it is newer than current and properly signed; None when there is none."""
    import requests

    session = session or _session()
    missing = forged = 0
    tried = mirrors()
    for prefix in tried:
        try:
            manifest = session.get(prefix + MANIFEST_URL, timeout=TIMEOUT)
            if manifest.status_code == 404:
                missing += 1
                continue
            manifest.raise_for_status()
            signature = session.get(prefix + MANIFEST_URL + ".sig", timeout=TIMEOUT)
            signature.raise_for_status()
        except requests.RequestException as error:
            log.info("Update check through %s failed: %s", prefix or "GitHub", error)
            continue
        if not verify(manifest.content, signature.text):
            # A proxy that changed the file, or a release someone else signed: either way, not this one.
            log.warning("Update manifest through %s has a bad signature", prefix or "GitHub")
            forged += 1
            continue
        release = replace(read_manifest(manifest.content), mirror=prefix)
        _remember(prefix, release.mirrors)
        if prefix:
            log.info("Update check went through %s", prefix)
        return release if parse_version(release.version) > parse_version(current) else None
    if forged:
        raise UpdateError("读不到更新信息，等会儿再试")
    if missing == len(tried):
        # Nowhere has a version.json: nothing published yet.
        return None
    raise UpdateError("连不上更新服务器，等会儿再试")


def download(release: Release, folder: Path, progress: Callable[[int, int], None] | None = None, session=None) -> Path:  # noqa: ANN001
    """Fetch the update zip into folder and check it is the one the release named."""
    import requests

    session = session or _session()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{FOLDER}-{release.version}-update.zip"
    order = [release.mirror, *(prefix for prefix in mirrors() if prefix != release.mirror)]
    failure = UpdateError("下载失败，看看网络再试")
    for prefix in order:
        digest = hashlib.sha256()
        got = 0
        try:
            with session.get(prefix + release.url, stream=True, timeout=TIMEOUT) as response:
                response.raise_for_status()
                with open(target, "wb") as out:
                    for chunk in response.iter_content(64 * 1024):
                        got += len(chunk)
                        if got > release.size:
                            break
                        digest.update(chunk)
                        out.write(chunk)
                        if progress is not None:
                            progress(got, release.size)
        except requests.RequestException as error:
            log.info("Update download through %s failed: %s", prefix or "GitHub", error)
            target.unlink(missing_ok=True)
            continue
        if got == release.size and digest.hexdigest() == release.sha256:
            if prefix != release.mirror:
                _remember(prefix)
            return target
        # Not the zip the release named: another address may pass the right one.
        log.warning("Update download through %s did not match the release", prefix or "GitHub")
        target.unlink(missing_ok=True)
        failure = UpdateError("更新包有问题，这次先不更新")
    raise failure


def _allowed(rel: PurePosixPath) -> bool:
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        return False
    if rel.parts[0] == _ALLOWED_DIR:
        return "models" not in rel.parts and "__pycache__" not in rel.parts
    return rel.as_posix() in _ALLOWED_FILES


def stage(zip_path: Path, root: Path, version: str) -> Path:
    """Unpack the update zip into root/update.new, for the launcher to lay over the folder."""
    staged = root / STAGED
    if staged.exists():
        shutil.rmtree(staged)
    staged.mkdir()
    try:
        with zipfile.ZipFile(zip_path) as bundle:
            for item in bundle.infolist():
                if item.is_dir():
                    continue
                parts = PurePosixPath(item.filename).parts
                if not parts or parts[0] != FOLDER:
                    continue
                rel = PurePosixPath(*parts[1:]) if len(parts) > 1 else PurePosixPath()
                if not _allowed(rel):
                    log.warning("Update zip entry left out: %s", item.filename)
                    continue
                target = staged.joinpath(*rel.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(item) as source, open(target, "wb") as out:
                    shutil.copyfileobj(source, out)
    except (zipfile.BadZipFile, OSError) as error:
        shutil.rmtree(staged, ignore_errors=True)
        raise UpdateError("更新包坏了，再试一次") from error
    if not (staged / _ALLOWED_DIR / "__init__.py").is_file():
        shutil.rmtree(staged, ignore_errors=True)
        raise UpdateError("更新包不完整，再试一次")
    (staged / VERSION_FILE).write_text(version, encoding="utf-8")
    return staged


def staged_version(root: Path | None) -> str:
    """The version waiting in update.new, or ""."""
    if root is None:
        return ""
    marker = root / STAGED / VERSION_FILE
    try:
        return marker.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


RESULT = "update.result"


def launcher_result(root: Path | None) -> str:
    """What the launcher did at the last start, if it did anything, once: it writes it here."""
    if root is None:
        return ""
    path = root / RESULT
    try:
        said = path.read_text(encoding="utf-8").strip()
        path.unlink()
    except OSError:
        return ""
    return said


def confirm_started(root: Path | None) -> bool:
    """The new version is running: the launcher need not put the old one back. True if it had to be told."""
    if root is None or not (root / PENDING).exists():
        return False
    (root / PENDING).unlink(missing_ok=True)
    shutil.rmtree(root / BACKUP, ignore_errors=True)
    log.info("Update to %s confirmed", __version__)
    return True
