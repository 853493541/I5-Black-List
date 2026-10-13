"""What the log must say: how each update went, what the launcher did, and the player's changes
that explain a problem later. Never a player's name."""

import logging

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from blacklist_detect import updater  # noqa: E402


@pytest.fixture
def window(tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    from blacklist_detect.ui import MainWindow

    QApplication.instance() or QApplication([])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    made = MainWindow()
    made._watch_timer.stop()
    yield made
    made.close()


def _said(caplog) -> str:  # noqa: ANN001
    return "\n".join(record.getMessage() for record in caplog.records)


def test_the_update_checks_outcome_is_logged(window, caplog):
    caplog.set_level(logging.INFO, logger="blacklist_detect")
    window.updates.latest.emit()
    window.updates.failed.emit("无法连接更新服务器，请稍后再试")
    said = _said(caplog)
    assert "is the newest" in said and "Update check failed: 无法连接更新服务器" in said


def test_a_failed_download_is_logged_with_its_cause(tmp_path, monkeypatch, caplog):
    from blacklist_detect.ui_update import Download

    QApplication.instance() or QApplication([])
    caplog.set_level(logging.INFO, logger="blacklist_detect")
    release = updater.Release(version="v9.9.9", url="u.zip", sha256="0" * 64, size=10, base="v0.6.0")

    def broken(*_args, **_kwargs):  # noqa: ANN002, ANN003, ANN202
        raise updater.UpdateError("下载的更新包坏了，请重试") from OSError("disk full")

    monkeypatch.setattr(updater, "download", broken)
    Download()._run(release, tmp_path, tmp_path)
    assert "Update to v9.9.9 failed: 下载的更新包坏了，请重试 (disk full)" in _said(caplog)


def test_what_the_launcher_did_is_read_once(tmp_path):
    assert updater.launcher_result(tmp_path) == ""
    (tmp_path / updater.RESULT).write_text("2026-10-12 18:00:00 新版本启动失败，已恢复到之前的版本", encoding="utf-8")
    assert "已恢复到之前的版本" in updater.launcher_result(tmp_path)
    assert updater.launcher_result(tmp_path) == "" and not (tmp_path / updater.RESULT).exists()


def test_the_players_changes_are_logged(window, caplog):
    caplog.set_level(logging.INFO, logger="blacklist_detect")
    window.store.consented = ["full", "auto"]
    window.full_on.click()
    window.auto_on.click()
    window.auto_off.click()
    window.safe_on.click()
    window._set_stream_mode(True)
    said = _said(caplog)
    for line in ("显示: 完整模式.", "方式: 自动检查.", "方式: 手动检查.", "显示: 安全模式.", "直播模式 on."):
        assert line in said, line


def test_a_hotkey_that_does_not_register_is_logged(window, monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="blacklist_detect")
    monkeypatch.setattr(window.hotkey, "apply", lambda spec: False)
    monkeypatch.setattr(window.hotkey, "active", "")
    window._sync_hotkey_mode()
    assert "did not register" in _said(caplog)
