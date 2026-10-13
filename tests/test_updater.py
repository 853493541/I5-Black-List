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


@pytest.fixture(autouse=True)
def _own_settings_folder(tmp_path, monkeypatch):  # noqa: ANN001, ANN202
    """The remembered update address goes beside the settings: never the real ones."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "appdata"))


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


def test_update_can_be_checked_from_settings(window, tmp_path, monkeypatch):
    """设置 › 帮助 › 关于: the version and 检查更新. The answer shows beside the button; a new version
    installs as it would at start. There is still no 有新版本 pill in the header."""
    from PySide6.QtWidgets import QPushButton

    from blacklist_detect import __version__

    assert window.version_label.text() == __version__
    assert not any(button.text() in ("有新版本", "有更新") for button in window.findChildren(QPushButton))
    # Run from source: nothing to update.
    monkeypatch.setattr(updater, "app_root", lambda: None)
    window.update_button.click()
    assert window.update_note.text() == "源码运行时不能更新"
    root = tmp_path / "BlackListDetect"
    root.mkdir()
    monkeypatch.setattr(updater, "app_root", lambda: root)
    asked: list[int] = []
    monkeypatch.setattr(window.updates, "check", lambda: asked.append(1) or True)
    window.update_button.click()
    assert asked == [1] and not window.update_button.isEnabled() and window.update_button.text() == "检查中…"
    window.updates.latest.emit()
    assert window.update_button.isEnabled() and window.update_button.text() == "检查更新"
    assert window.update_note.text() == "已是最新版本"
    window.update_button.click()
    window.updates.failed.emit("网络不可用")
    assert window.update_note.text() == "网络不可用"
    # The check at start answers only in the log.
    window.update_note.setText("")
    window.updates.latest.emit()
    assert window.update_note.text() == ""


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
    dialog._on_failed("下载失败，看看网络再试")
    assert not dialog.band.isHidden() and dialog.action.text() == "重试" and dialog.skip.text() == "跳过"
    assert dialog.status.text() == "下载失败，看看网络再试" and dialog.close_button.isHidden()
    dialog.reject()
    assert dialog.isVisible(), "only 跳过 lets it go"
    dialog.action.click()
    assert started == ["v9.0.0", "v9.0.0"] and dialog.band.isHidden()
    dialog._on_failed("下载失败，看看网络再试")
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
    window._quiet_update_failed("下载失败，看看网络再试")
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


def test_the_app_ends_its_process_when_the_window_is_gone(monkeypatch):
    # PaddleOCR's threads would keep Python waiting at exit: the window gone, the process left.
    from blacklist_detect import __main__ as entry

    ended: list[int] = []
    monkeypatch.setattr("blacklist_detect.ui.run_app", lambda background=False: 0)
    monkeypatch.setattr("blacklist_detect.single.exit_now", ended.append)
    assert entry.main([]) == 0
    assert ended == [0]


def test_an_update_that_does_not_go_in_is_restarted_twice_then_left(tmp_path):
    assert updater.note_restart(tmp_path, "v9.0.0", now=1000) is True
    assert updater.note_restart(tmp_path, "v9.0.0", now=1010) is True
    # A third restart into the same version would only loop.
    assert updater.note_restart(tmp_path, "v9.0.0", now=1020) is False
    # Another version, or the same one much later, is tried again.
    assert updater.note_restart(tmp_path, "v9.0.1", now=1030) is True
    assert updater.note_restart(tmp_path, "v9.0.0", now=1030 + updater.TRIES_FORGET_S) is True
    # The new version running clears the count.
    updater.confirm_started(tmp_path)
    assert not (tmp_path / updater.TRIES).exists()


class _CutOff(_Session):
    """GitHub as from mainland China: every direct request fails to connect."""

    def get(self, url: str, **kwargs) -> _Response:  # noqa: ANN003
        if url.startswith("https://github.com/"):
            import requests

            self.asked.append(url)
            raise requests.ConnectionError("reset")
        return super().get(url, **kwargs)


def _signed(monkeypatch, **manifest_args) -> tuple[bytes, bytes]:  # noqa: ANN001, ANN003
    private, public = _keys()
    monkeypatch.setattr(updater, "PUBLIC_KEY", public)
    manifest = _manifest(**manifest_args)
    return manifest, base64.b64encode(private.sign(manifest))


def test_github_cut_off_goes_through_a_proxy_and_remembers_it(monkeypatch, tmp_path):
    payload = b"z" * 5000
    manifest, signature = _signed(monkeypatch, payload=payload)
    proxy = updater.MIRRORS[2]
    release_url = updater.read_manifest(manifest).url
    session = _CutOff({
        proxy + updater.MANIFEST_URL: _Response(manifest),
        proxy + updater.MANIFEST_URL + ".sig": _Response(signature),
        proxy + release_url: _Response(payload),
    })  # fmt: skip
    release = updater.fetch_release(session, current="v0.3.0")
    assert release is not None and release.mirror == proxy
    # The zip comes through the same proxy, without trying GitHub again.
    session.asked.clear()
    assert updater.download(release, tmp_path / "zip", session=session).read_bytes() == payload
    assert session.asked == [proxy + release_url]
    # Next time that proxy is tried first.
    assert updater.mirrors()[0] == proxy
    session.asked.clear()
    updater.fetch_release(session, current="v0.3.0")
    assert session.asked[0] == proxy + updater.MANIFEST_URL


def test_a_proxy_that_changes_the_file_is_passed_over(monkeypatch):
    manifest, signature = _signed(monkeypatch)
    bad, good = updater.MIRRORS[1], updater.MIRRORS[2]
    session = _CutOff({
        bad + updater.MANIFEST_URL: _Response(manifest.replace(b"v0.1.0", b"v0.0.1")),
        bad + updater.MANIFEST_URL + ".sig": _Response(signature),
        good + updater.MANIFEST_URL: _Response(manifest),
        good + updater.MANIFEST_URL + ".sig": _Response(signature),
    })  # fmt: skip
    release = updater.fetch_release(session, current="v0.3.0")
    assert release is not None and release.mirror == good and release.base == "v0.1.0"
    # Every way blocked: the player is told it could not connect.
    with pytest.raises(UpdateError, match="连不上"):
        updater.fetch_release(_Blocked({}), current="v0.3.0")


class _Blocked(_Session):
    def get(self, url: str, **_kwargs) -> _Response:  # noqa: ANN003
        import requests

        raise requests.ConnectionError("no network")


def test_a_release_can_name_new_proxies(monkeypatch):
    data = json.loads(_manifest())
    data["mirrors"] = ["https://new-proxy.example/", "http://plain.example/", "https://x.example/a b/", "javascript:alert(1)//"]
    manifest = json.dumps(data).encode("utf-8")
    private, public = _keys()
    monkeypatch.setattr(updater, "PUBLIC_KEY", public)
    signature = base64.b64encode(private.sign(manifest))
    session = _Session({updater.MANIFEST_URL: _Response(manifest), updater.MANIFEST_URL + ".sig": _Response(signature)})
    release = updater.fetch_release(session, current="v0.3.0")
    # Only https addresses ending in / are kept.
    assert release.mirrors == ("https://new-proxy.example/",)
    assert updater.mirrors()[-1] == "https://new-proxy.example/"
    assert "http://plain.example/" not in updater.mirrors()


def test_a_download_that_does_not_match_tries_another_address(monkeypatch, tmp_path):
    payload = b"q" * 3000
    release = updater.read_manifest(_manifest(payload=payload))
    second = updater.MIRRORS[1]
    session = _Session({release.url: _Response(b"w" * len(payload)), second + release.url: _Response(payload)})
    assert updater.download(release, tmp_path, session=session).read_bytes() == payload
    assert updater.mirrors()[0] == second


def test_a_new_install_keeps_the_listed_order():
    # Nothing has worked yet: the list's own order, not GitHub first.
    assert updater.mirrors() == list(updater.MIRRORS)
    updater._remember("")
    assert updater.mirrors()[0] == ""
    updater._remember(updater.MIRRORS[1])
    assert updater.mirrors()[0] == updater.MIRRORS[1]


def test_the_next_copy_does_not_inherit_one_thread(monkeypatch, tmp_path):
    """Paddle sets OMP_NUM_THREADS=1 in the app's process. Handed to the copy the app restarts into
    for an update, it left the OCR one core: names read 3 to 5 times slower until a fresh start."""
    import subprocess
    import sys

    from blacklist_detect import paths, ui_update

    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    monkeypatch.setenv("__KMP_REGISTERED_LIB_6428", "00007FF88960C554-cafed84f-libiomp5md.dll")
    monkeypatch.setenv("BLACKLIST_TEST_KEPT", "yes")
    env = paths.child_env()
    assert "OMP_NUM_THREADS" not in env and not any(key.startswith("__KMP_REGISTERED_LIB_") for key in env)
    assert env["BLACKLIST_TEST_KEPT"] == "yes" and env.get("PATH") == __import__("os").environ.get("PATH")
    # The update restart starts the launcher with it.
    started = []
    with monkeypatch.context() as patch:
        patch.setattr(ui_update, "launcher_in", lambda _root: tmp_path / "模仿者小工具.exe")
        patch.setattr(ui_update.subprocess, "Popen", lambda *args, **kwargs: started.append(kwargs))
        assert ui_update.restart_into_update(tmp_path)
    assert "OMP_NUM_THREADS" not in started[0]["env"] and started[0]["env"]["BLACKLIST_TEST_KEPT"] == "yes"
    # A copy started with it anyway (by v0.8.4 or older) drops it before Paddle loads.
    probe = (
        "import os; import blacklist_detect.__main__; from blacklist_detect import paths; "
        "print(os.environ.get('OMP_NUM_THREADS'), paths.inherited_threads)"
    )
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, env={**__import__("os").environ, "OMP_NUM_THREADS": "1"}, check=True)
    assert out.stdout.split() == ["None", "1"]
