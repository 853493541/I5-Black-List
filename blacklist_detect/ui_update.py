"""Updates in the window: a check when the app opens, and the update itself.

A new version found when the app opens is downloaded straight away, in a dialog that stays until
it is done, and the app restarts into it. The check and the download run on their own threads
and report back by signal, so the window never waits on the network.
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QProgressBar, QPushButton, QWidget

from blacklist_detect import __version__, updater
from blacklist_detect.names import launcher_in
from blacklist_detect.ui_dialogs import _primary
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
            self.failed.emit("无法检查更新，请稍后再试")
            return
        self._busy = False
        if release is None:
            self.latest.emit()
        else:
            self.found.emit(release)


class Download(QObject):
    """Fetches the update zip on a thread and unpacks it into update.new."""

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
            cause = f" ({error.__cause__})" if error.__cause__ else ""
            log.warning("Update to %s failed: %s%s", release.version, error, cause)
            self.failed.emit(str(error))
            return
        except Exception:  # noqa: BLE001
            log.exception("Update download failed")
            self.failed.emit("无法更新，请稍后再试")
            return
        self.done.emit(release.version)


def restart_into_update(root: Path, background: bool = False) -> bool:
    """Start the launcher, which waits for this app to close, lays the update over and opens it.

    background: the app was in the tray, so the new version starts there too.
    """
    launcher = launcher_in(root)
    if launcher is None:
        return False
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    command = [str(launcher), "--wait-pid", str(os.getpid())] + (["--background"] if background else [])
    subprocess.Popen(command, cwd=str(root), creationflags=flags, close_fds=True)  # noqa: S603
    return True


class UpdateDialog(Modal):
    """正在更新: what is new and a progress bar; when the download is done the app restarts.

    The new version comes first: no ×, no Esc and no click outside close it. If the download
    fails, 重试 tries again and 跳过 goes on with this version; the next start tries again. A
    release that needs the full package says so, with 前往下载 and 跳过.
    """

    restart_requested = Signal()
    # How long 更新完成，正在重启… shows before the app closes.
    RESTART_MS = 900

    def __init__(self, release: updater.Release, root: Path | None, data_dir: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.release = release
        self.root = root
        self.data_dir = data_dir
        self._download = Download(self)
        self._download.progress.connect(self._on_progress)
        self._download.done.connect(self._on_done)
        self._download.failed.connect(self._on_failed)
        full = release.needs_full() or root is None
        layout = self.frame(f"发现新版本 {release.version}" if full else f"正在更新到 {release.version}")
        size = max(release.size / 1e6, 0.1)
        self.summary = QLabel(f"当前版本 {__version__}" if full else f"当前版本 {__version__} · {size:.1f} MB")
        self.summary.setObjectName("sub")
        layout.addWidget(self.summary)
        self.notes = QLabel("\n".join(f"· {line}" for line in release.notes))
        self.notes.setWordWrap(True)
        self.notes.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # No notes: nothing, rather than a line that says nothing.
        self.notes.setVisible(bool(release.notes))
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
        self.skip = QPushButton("跳过")
        self.skip.setAutoDefault(False)
        self.skip.clicked.connect(self._skip)
        self.action = _primary("重试", self._act)
        row = self.footer(self.skip, self.action)
        self.band = row.parentWidget()
        self.card.setMinimumWidth(460)
        _pointing(self)
        self._state = "idle"
        self.close_button.hide()
        if root is None:
            log.info("Update %s found, but this copy runs from source.", release.version)
            self.close_button.show()
            self._state = "source"
            self._say("源码运行时不能更新")
            self.skip.hide()
            self.action.setText("知道了")
        elif release.needs_full():
            log.info("Update %s needs the full package; the player is sent to download it.", release.version)
            self._state = "full"
            self._say("这个版本要下载完整安装包，名单和设置都会保留")
            self.action.setText("前往下载")
        else:
            self.band.hide()

    def start(self) -> None:
        """Download now. Already downloaded (and not yet restarted into): restart now."""
        if self._state in ("source", "full", "downloading", "restarting"):
            return
        if updater.staged_version(self.root) == self.release.version:
            self._on_done(self.release.version)
            return
        self._state = "downloading"
        self.close_button.hide()
        self.band.hide()
        self.bar.setValue(0)
        self.bar.show()
        self._say("下载中 0%")
        self._download.start(self.release, self.root, self.data_dir / "updates")

    def busy(self) -> bool:
        return self._state in ("downloading", "restarting")

    def reject(self) -> None:
        # The new version comes first: ×, Esc and a click outside do nothing; only 跳过 lets it go.
        if self._state == "source":
            super().reject()

    def _skip(self) -> None:
        if self._state in ("failed", "full"):
            super().reject()

    def click_outside(self) -> None:
        if self._state == "source":
            super().click_outside()
            return
        self._nudge()

    def _say(self, text: str) -> None:
        self.status.setText(text)
        self.status.setVisible(bool(text))

    def _act(self) -> None:
        if self._state == "full":
            QDesktopServices.openUrl(QUrl(updater.RELEASES_URL))
        elif self._state == "failed":
            self.start()
        else:
            self.accept()

    def _on_progress(self, got: int, total: int) -> None:
        share = got / max(total, 1)
        self.bar.setValue(round(1000 * share))
        self._say(f"下载中 {round(100 * share)}%")

    def _on_done(self, _version: str) -> None:
        self._state = "restarting"
        self.close_button.hide()
        self.band.hide()
        self.bar.setValue(1000)
        self.bar.show()
        self._say("更新完成，正在重启…")
        QTimer.singleShot(self.RESTART_MS, self._restart)

    def _restart(self) -> None:
        self.restart_requested.emit()

    def _on_failed(self, message: str) -> None:
        self._state = "failed"
        self.bar.hide()
        self._say(message)
        self.band.show()
        self.action.setText("重试")
