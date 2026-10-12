"""Updates in the window: a quiet check when the app opens, 检查更新, and the dialog that downloads one.

The check and the download run on their own threads and report back by signal, so the window
never waits on the network. Nothing is downloaded until the player clicks 更新.
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QProgressBar, QWidget

from blacklist_detect import __version__, updater
from blacklist_detect.ui_dialogs import _footer, _primary
from blacklist_detect.ui_kit import Modal
from blacklist_detect.ui_theme import _pointing

log = logging.getLogger(__name__)


class UpdateChecker(QObject):
    """Asks GitHub for the newest release on a thread; one answer per check."""

    found = Signal(object)
    latest = Signal()
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._busy = False

    def busy(self) -> bool:
        return self._busy

    def check(self) -> bool:
        """Start a check. False when one is already running."""
        if self._busy:
            return False
        self._busy = True
        threading.Thread(target=self._run, name="update-check", daemon=True).start()
        return True

    def _run(self) -> None:
        try:
            release = updater.fetch_release()
        except updater.UpdateError as error:
            self._busy = False
            self.failed.emit(str(error))
            return
        except Exception:  # noqa: BLE001 - a broken check must never take the app down
            log.exception("Update check failed")
            self._busy = False
            self.failed.emit("检查失败，请稍后重试")
            return
        self._busy = False
        if release is None:
            self.latest.emit()
        else:
            self.found.emit(release)


class _Download(QObject):
    progress = Signal(int, int)
    done = Signal(str)
    failed = Signal(str)

    def start(self, release: updater.Release, root: Path, folder: Path) -> None:
        threading.Thread(target=self._run, args=(release, root, folder), name="update-download", daemon=True).start()

    def _run(self, release: updater.Release, root: Path, folder: Path) -> None:
        try:
            zipped = updater.download(release, folder, self.progress.emit)
            updater.stage(zipped, root, release.version)
            zipped.unlink(missing_ok=True)
        except updater.UpdateError as error:
            self.failed.emit(str(error))
            return
        except Exception:  # noqa: BLE001
            log.exception("Update download failed")
            self.failed.emit("更新失败，请稍后重试")
            return
        self.done.emit(release.version)


def restart_into_update(root: Path) -> bool:
    """Start the launcher, which waits for this app to close, lays the update over and opens it."""
    launcher = root / updater.LAUNCHER
    if not launcher.is_file():
        return False
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([str(launcher), "--wait-pid", str(os.getpid())], cwd=str(root), creationflags=flags, close_fds=True)  # noqa: S603
    return True


class UpdateDialog(Modal):
    """发现新版本: what is new, then 立即更新 → a progress bar → 立即重启.

    restart is called when the player wants the new version now; the window quits for it.
    """

    restart_requested = Signal()

    def __init__(self, release: updater.Release, root: Path | None, data_dir: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.release = release
        self.root = root
        self.data_dir = data_dir
        self._download = _Download(self)
        self._download.progress.connect(self._on_progress)
        self._download.done.connect(self._on_done)
        self._download.failed.connect(self._on_failed)
        layout = self.frame(f"发现新版本 {release.version}")
        self.summary = QLabel(f"当前版本 {__version__}")
        self.summary.setObjectName("sub")
        layout.addWidget(self.summary)
        self.notes = QLabel("\n".join(f"· {line}" for line in release.notes) or "· 问题修复和体验优化")
        self.notes.setWordWrap(True)
        self.notes.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.notes)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.bar.hide()
        layout.addWidget(self.bar)
        self.status = QLabel("")
        self.status.setObjectName("sub")
        self.status.setWordWrap(True)
        self.status.hide()
        layout.addWidget(self.status)
        self.action = _primary("立即更新", self._act)
        _footer(self, self.action)
        self.card.setMinimumWidth(460)
        _pointing(self)
        self._state = "offer"
        if release.needs_full():
            self._state = "full"
            self._say("此版本需要下载完整安装包，名单和设置会保留")
            self.action.setText("前往下载")
        elif root is None:
            self._state = "source"
            self._say("源码运行不支持更新")
            self.action.setEnabled(False)
        elif updater.staged_version(root) == release.version:
            self._ready()
        else:
            size = release.size / 1e6
            self.summary.setText(f"当前版本 {__version__} · {max(size, 0.1):.1f} MB")

    def _say(self, text: str) -> None:
        self.status.setText(text)
        self.status.setVisible(bool(text))

    def _act(self) -> None:
        if self._state == "full":
            QDesktopServices.openUrl(QUrl(updater.RELEASES_URL))
            self.accept()
        elif self._state in ("offer", "failed"):
            self._start()
        elif self._state == "ready":
            self.restart_requested.emit()
            self.accept()

    def _start(self) -> None:
        self._state = "downloading"
        self.action.setEnabled(False)
        self.action.setText("下载中…")
        self.bar.setValue(0)
        self.bar.show()
        self._say("")
        self._download.start(self.release, self.root, self.data_dir / "updates")

    def _on_progress(self, got: int, total: int) -> None:
        self.bar.setValue(round(1000 * got / max(total, 1)))

    def _on_done(self, _version: str) -> None:
        self._ready()

    def _ready(self) -> None:
        self._state = "ready"
        self.bar.hide()
        self._say("下载完成，重启后生效")
        self.action.setEnabled(True)
        self.action.setText("立即重启")

    def _on_failed(self, message: str) -> None:
        self._state = "failed"
        self.bar.hide()
        self._say(message)
        self.action.setEnabled(True)
        self.action.setText("重试")
