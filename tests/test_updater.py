"""Updates: the signed version file, the download, the unpacking, and the launcher laying it over the folder."""

import base64
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from blacklist_detect import updater
from blacklist_detect.names import LAUNCHERS
from blacklist_detect.updater import Release, UpdateError

ROOT = Path(__file__).resolve().parent.parent


def _keys() -> tuple[Ed25519PrivateKey, str]:
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return private, base64.b64encode(public).decode()


def _manifest(version: str = "v9.0.0", payload: bytes = b"zip", base: str = "v0.1.0", url: str = "") -> bytes:
    data = {
        "version": version,
        "base": base,
        "notes": ["心动列表", "更新更快"],
        "update": {
            "url": url or f"{updater.DOWNLOADS}{version}/BlackListDetect-{version}-update.zip",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
        },
    }
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


class _Response:
    def __init__(self, content: bytes, status: int = 200) -> None:
        self.content = content
        self.text = content.decode("utf-8", "replace")
        self.status_code = status

    def raise_for_status(self) -> None:
        import requests

        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def iter_content(self, size: int):  # noqa: ANN201
        for at in range(0, len(self.content), size):
            yield self.content[at : at + size]

    def __enter__(self):  # noqa: ANN204
        return self

    def __exit__(self, *_args) -> None:  # noqa: ANN002
        return None


class _Session:
    def __init__(self, pages: dict[str, _Response]) -> None:
        self.pages = pages
        self.asked: list[str] = []

    def get(self, url: str, **_kwargs) -> _Response:  # noqa: ANN003
        self.asked.append(url)
        return self.pages.get(url, _Response(b"", 404))


def test_versions_compare_by_number():
    assert updater.parse_version("v0.10.0") > updater.parse_version("v0.9.9")
    assert updater.parse_version("0.4.0") == (0, 4, 0)
    assert updater.parse_version("dev") == ()
    assert Release("v0.5.0", "u", "0" * 64, 1, base="v0.4.0").needs_full("v0.3.0")
    assert not Release("v0.5.0", "u", "0" * 64, 1, base="v0.4.0").needs_full("v0.4.0")


def test_only_the_release_key_signature_is_accepted():
    private, public = _keys()
    manifest = _manifest()
    signature = base64.b64encode(private.sign(manifest)).decode()
    assert updater.verify(manifest, signature, public)
    assert not updater.verify(manifest.replace(b"v9.0.0", b"v9.0.1"), signature, public)
    _other, someone_else = _keys()
    assert not updater.verify(manifest, signature, someone_else)
    assert not updater.verify(manifest, "not base64!", public)
    assert not updater.verify(manifest, signature, "")


def test_a_zip_from_anywhere_else_is_refused():
    with pytest.raises(UpdateError):
        updater.read_manifest(_manifest(url="https://example.com/BlackListDetect-v9.0.0-update.zip"))
    with pytest.raises(UpdateError):
        updater.read_manifest(b"{not json")
    release = updater.read_manifest(_manifest())
    assert release.version == "v9.0.0" and release.notes == ("心动列表", "更新更快") and release.base == "v0.1.0"


def test_a_newer_signed_release_is_found(monkeypatch):
    private, public = _keys()
    monkeypatch.setattr(updater, "PUBLIC_KEY", public)
    manifest = _manifest()
    signature = base64.b64encode(private.sign(manifest)).decode().encode()
    session = _Session({updater.MANIFEST_URL: _Response(manifest), updater.MANIFEST_URL + ".sig": _Response(signature)})
    release = updater.fetch_release(session, current="v0.3.0")
    assert release is not None and release.version == "v9.0.0"
    # Already on it, or no release published yet: nothing to offer.
    assert updater.fetch_release(session, current="v9.0.0") is None
    assert updater.fetch_release(_Session({}), current="v0.3.0") is None
    # Signed by someone else: refused, with a reason.
    forged = _Session({updater.MANIFEST_URL: _Response(manifest), updater.MANIFEST_URL + ".sig": _Response(base64.b64encode(_keys()[0].sign(manifest)))})
    with pytest.raises(UpdateError):
        updater.fetch_release(forged, current="v0.3.0")


def test_the_download_must_match_the_release(tmp_path):
    payload = b"x" * 200_000
    release = updater.read_manifest(_manifest(payload=payload))
    seen: list[tuple[int, int]] = []
    path = updater.download(release, tmp_path, lambda got, total: seen.append((got, total)), _Session({release.url: _Response(payload)}))
    assert path.read_bytes() == payload and seen[-1] == (len(payload), len(payload))
    with pytest.raises(UpdateError):
        updater.download(release, tmp_path, session=_Session({release.url: _Response(b"y" * len(payload))}))
    with pytest.raises(UpdateError):
        updater.download(release, tmp_path, session=_Session({release.url: _Response(payload + b"more")}))
    assert not any(tmp_path.iterdir())


def _update_zip(path: Path, extra: dict[str, bytes] | None = None) -> Path:
    files = {
        "BlackListDetect/blacklist_detect/__init__.py": b'__version__ = "v9.0.0"\n',
        "BlackListDetect/blacklist_detect/new_part.py": b"NEW = True\n",
        "BlackListDetect/模仿者小工具.exe": b"launcher",
        "BlackListDetect/使用说明.txt": "新的说明".encode(),
        **(extra or {}),
    }
    with zipfile.ZipFile(path, "w") as bundle:
        for name, data in files.items():
            bundle.writestr(name, data)
    return path


def test_unpacking_keeps_to_the_app_files(tmp_path):
    zipped = _update_zip(
        tmp_path / "u.zip",
        {
            "BlackListDetect/../evil.txt": b"no",
            "BlackListDetect/blacklist_detect/models/x.bin": b"no",
            "BlackListDetect/runtime/python312.dll": b"no",
            "Other/blacklist_detect/x.py": b"no",
            # A folder from before the rename keeps its old file names; they are updated too.
            "BlackListDetect/黑名单检测.exe": b"old launcher",
            "BlackListDetect/runtime/I5黑名单.exe": b"old app",
            "BlackListDetect/runtime/模仿者小工具.exe": b"app",
        },
    )
    root = tmp_path / "app"
    root.mkdir()
    staged = updater.stage(zipped, root, "v9.0.0")
    names = sorted(p.relative_to(staged).as_posix() for p in staged.rglob("*") if p.is_file())
    assert names == [
        ".version",
        "blacklist_detect/__init__.py",
        "blacklist_detect/new_part.py",
        "runtime/I5黑名单.exe",
        "runtime/模仿者小工具.exe",
        "使用说明.txt",
        "模仿者小工具.exe",
        "黑名单检测.exe",
    ]
    assert updater.staged_version(root) == "v9.0.0"
    assert not (tmp_path / "evil.txt").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="the launcher is a Windows program")
def test_the_launcher_lays_the_update_over_and_puts_it_back_when_it_fails(tmp_path):
    sys.path.insert(0, str(ROOT / "build"))
    from build_launcher import build

    root = tmp_path / "BlackListDetect"
    (root / "blacklist_detect" / "models").mkdir(parents=True)
    (root / "runtime").mkdir()
    launcher = build(root / LAUNCHERS[0])
    (root / "blacklist_detect" / "__init__.py").write_text('__version__ = "v0.3.0"\n', encoding="utf-8")
    (root / "blacklist_detect" / "models" / "model.bin").write_bytes(b"model")
    (root / "使用说明.txt").write_text("旧的说明", encoding="utf-8")

    def stage_new() -> None:
        updater.stage(_update_zip(tmp_path / "u.zip", {"BlackListDetect/模仿者小工具.exe": launcher.read_bytes()}), root, "v9.0.0")

    def apply() -> int:
        return subprocess.run([str(root / LAUNCHERS[0]), "--apply-only"], check=False, timeout=60).returncode

    stage_new()
    assert apply() == 0
    assert (root / "blacklist_detect" / "__init__.py").read_text(encoding="utf-8") == '__version__ = "v9.0.0"\n'
    assert (root / "blacklist_detect" / "new_part.py").exists() and (root / "blacklist_detect" / "models" / "model.bin").exists()
    assert (root / updater.PENDING).read_text(encoding="utf-8") == "v9.0.0"
    assert not (root / updater.STAGED).exists()
    # The new version never said it started: the next start puts the old one back.
    assert apply() == 2
    assert (root / "blacklist_detect" / "__init__.py").read_text(encoding="utf-8") == '__version__ = "v0.3.0"\n'
    assert (root / "使用说明.txt").read_text(encoding="utf-8") == "旧的说明"
    assert not (root / "blacklist_detect" / "new_part.py").exists()
    assert not (root / updater.PENDING).exists() and not (root / updater.BACKUP).exists()
    # This time it starts and says so: the old files go, and later starts change nothing.
    stage_new()
    assert apply() == 0
    assert updater.confirm_started(root)
    assert not (root / updater.PENDING).exists() and not (root / updater.BACKUP).exists()
    assert apply() == 0
    assert (root / "blacklist_detect" / "__init__.py").read_text(encoding="utf-8") == '__version__ = "v9.0.0"\n'


@pytest.fixture
def window(tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from blacklist_detect.ui import MainWindow

    QApplication.instance() or QApplication([])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    made = MainWindow()
    made._watch_timer.stop()
    yield made
    made.close()


def test_settings_have_no_update_controls(window):
    from PySide6.QtWidgets import QLabel, QPushButton

    texts = [label.text() for label in window.findChildren(QLabel)] + [button.text() for button in window.findChildren(QPushButton)]
    assert not any(text in ("更新", "检查更新", "有新版本", "有更新") for text in texts)


def test_a_new_version_found_at_start_is_installed_first(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication

    from blacklist_detect.ui_update import UpdateDialog

    root = tmp_path / "BlackListDetect"
    root.mkdir()
    monkeypatch.setattr(updater, "app_root", lambda: root)
    window.show()
    QApplication.processEvents()
    started: list[str] = []
    monkeypatch.setattr("blacklist_detect.ui_update.Download.start", lambda self, rel, where, folder: started.append(rel.version))
    window._on_update_found(updater.read_manifest(_manifest(base="v0.1.0")))
    dialog = window.findChild(UpdateDialog)
    assert started == ["v9.0.0"] and dialog is not None and dialog.isVisible()
    assert dialog.windowTitle() == "正在更新到 v9.0.0" and "心动列表" in dialog.notes.text()
    # Nothing closes it: no ×, and Esc or a click outside do nothing.
    assert dialog.close_button.isHidden() and dialog.band.isHidden()
    dialog.reject()
    dialog.click_outside()
    assert dialog.isVisible()
    dialog._on_progress(42, 100)
    assert dialog.bar.value() == 420 and dialog.status.text() == "下载中 42%"
    # A second answer from GitHub does not start a second update.
    window._on_update_found(updater.read_manifest(_manifest(base="v0.1.0")))
    assert started == ["v9.0.0"]
    # Done: it says so and the app restarts by itself.
    restarted: list[bool] = []
    monkeypatch.setattr(window, "_restart_for_update", lambda *_args: restarted.append(True))
    dialog.restart_requested.disconnect()
    dialog.restart_requested.connect(window._restart_for_update)
    dialog.RESTART_MS = 0
    dialog._on_done("v9.0.0")
    assert dialog.status.text() == "更新完成，正在重启…"
    QApplication.processEvents()
    assert restarted == [True]


def test_a_failed_download_offers_retry_or_skip(window, tmp_path, monkeypatch):
    from blacklist_detect.ui_update import UpdateDialog

    root = tmp_path / "BlackListDetect"
    root.mkdir()
    monkeypatch.setattr(updater, "app_root", lambda: root)
    window.show()
    started: list[str] = []
    monkeypatch.setattr("blacklist_detect.ui_update.Download.start", lambda self, rel, where, folder: started.append(rel.version))
    window._on_update_found(updater.read_manifest(_manifest(base="v0.1.0")))
    dialog = window.findChild(UpdateDialog)
    dialog._on_failed("下载失败，请检查网络后重试")
    assert not dialog.band.isHidden() and dialog.action.text() == "重试" and dialog.skip.text() == "跳过"
    assert dialog.status.text() == "下载失败，请检查网络后重试" and dialog.close_button.isHidden()
    dialog.reject()
    assert dialog.isVisible(), "only 跳过 lets it go"
    dialog.action.click()
    assert started == ["v9.0.0", "v9.0.0"] and dialog.band.isHidden()
    dialog._on_failed("下载失败，请检查网络后重试")
    dialog.skip.click()
    assert not dialog.isVisible() and not window._updating


def test_in_the_tray_the_update_happens_out_of_sight(window, tmp_path, monkeypatch):
    from blacklist_detect.ui_update import UpdateDialog

    root = tmp_path / "BlackListDetect"
    root.mkdir()
    monkeypatch.setattr(updater, "app_root", lambda: root)
    window.hide()
    started: list[str] = []
    monkeypatch.setattr("blacklist_detect.ui_update.Download.start", lambda self, rel, where, folder: started.append(rel.version))
    window._on_update_found(updater.read_manifest(_manifest(base="v0.1.0")))
    assert started == ["v9.0.0"] and window.findChild(UpdateDialog) is None
    window._quiet_update_failed("下载失败，请检查网络后重试")
    assert not window._updating


def test_a_release_needing_the_full_package_sends_to_the_download_page(window, tmp_path, monkeypatch):
    from blacklist_detect.ui_update import UpdateDialog

    root = tmp_path / "BlackListDetect"
    root.mkdir()
    monkeypatch.setattr(updater, "app_root", lambda: root)
    window.show()
    started: list[str] = []
    monkeypatch.setattr("blacklist_detect.ui_update.Download.start", lambda self, rel, where, folder: started.append(rel.version))
    opened: list[str] = []
    monkeypatch.setattr("blacklist_detect.ui_update.QDesktopServices.openUrl", lambda url: opened.append(url.toString()))
    window._on_update_found(updater.read_manifest(_manifest(base="v8.0.0")))
    dialog = window.findChild(UpdateDialog)
    assert started == [] and dialog.action.text() == "前往下载" and dialog.skip.text() == "跳过"
    assert "完整安装包" in dialog.status.text()
    dialog.action.click()
    assert opened == [updater.RELEASES_URL] and dialog.isVisible()
    dialog.skip.click()
    assert not dialog.isVisible() and not window._updating
