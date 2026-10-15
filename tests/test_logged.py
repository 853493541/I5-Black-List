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
    window.updates.failed.emit("连不上更新服务器，等会儿再试")
    said = _said(caplog)
    assert "is the newest" in said and "Update check failed: 连不上更新服务器" in said


def test_a_failed_download_is_logged_with_its_cause(tmp_path, monkeypatch, caplog):
    from blacklist_detect.ui_update import Download

    QApplication.instance() or QApplication([])
    caplog.set_level(logging.INFO, logger="blacklist_detect")
    release = updater.Release(version="v9.9.9", url="u.zip", sha256="0" * 64, size=10, base="v0.6.0")

    def broken(*_args, **_kwargs):  # noqa: ANN002, ANN003, ANN202
        raise updater.UpdateError("更新包坏了，再试一次") from OSError("disk full")

    monkeypatch.setattr(updater, "download", broken)
    Download()._run(release, tmp_path, tmp_path)
    assert "Update to v9.9.9 failed: 更新包坏了，再试一次 (disk full)" in _said(caplog)


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


def test_each_check_is_logged_seat_by_seat_with_masked_names(window, caplog):
    import numpy as np

    from blacklist_detect.pipeline import CheckResult, Hit, NameSlot

    caplog.set_level(logging.INFO, logger="blacklist_detect")
    window.store.add_like("心动小鹿")

    def seat(index: int, name: str, confidence: float, unclear: bool = False) -> NameSlot:
        return NameSlot(index, (0, 0, 1, 1), name, name, False, confidence, unclear)

    result = CheckResult(
        header_found=True,
        message="",
        names=[seat(0, "示例坏人", 0.99), seat(1, "心动小鹿", 1.0), seat(2, "", 0.31, unclear=True), seat(3, "路过的猫", 0.97)],
        hits=[Hit(index=0, read_text="示例坏人", entry_name="示例坏人", note="", truncated=False, line="")],
        preview_rgb=np.zeros((1080, 1920, 3), dtype=np.uint8),
        button_box=(800, 900, 1056, 974),
        game_box=(0.0, 0.0, 1920.0, 1080.0),
    )
    window._check_number = 7
    window._log_check("hotkey", result, 0.42)
    said = _said(caplog)
    assert "Check 7 (hotkey): lobby found, 1 on the list, 1 嘉宾, 1 unclear, 0.42 s" in said
    assert "Check 7 seats: 1 示*** 0.99 黑名单 | 2 心*** 1.00 嘉宾 | 3 ? 0.31 | 4 路*** 0.97" in said
    assert "Check 7 lobby: button (800, 900, 1056, 974), game screen (0, 0, 1920, 1080), in a 1920x1080 screen copy" in said
    for name in ("示例坏人", "心动小鹿", "路过的猫"):
        assert name not in said


def test_list_changes_are_logged_as_counts(window, caplog):
    caplog.set_level(logging.INFO, logger="blacklist_detect")
    store = window.store
    store.add("示例坏人")
    store.import_rows([("路过的捣蛋鬼", (), "", -1), ("夜猫子", (), "", -1)])
    before = store.snapshot_entries()
    store.remove_at(0)
    store.restore_entries(before)
    store.clear_entries()
    store.add_like("心动小鹿")
    store.clear_likes()
    said = _said(caplog)
    for line in (
        "黑名单: 1 added, 1 in all.",
        "黑名单: 2 imported, 0 merged, 3 in all.",
        "黑名单: 1 deleted, 2 left.",
        "黑名单: put back as it was (撤销), 3 in all.",
        "黑名单: cleared.",
        "嘉宾: 1 added, 1 in all.",
        "嘉宾: cleared.",
    ):
        assert line in said, line
    for name in ("示例坏人", "路过的捣蛋鬼", "夜猫子", "心动小鹿"):
        assert name not in said


def test_the_settings_are_logged_at_start(window):
    line = window.settings_line()
    for part in ("显示 ", "方式 手动检查 (", "直播模式 关", "嘉宾场景 开; 声音 100%;", "黑名单 0, 嘉宾 0, 记录 0"):
        assert part in line, part


def test_a_log_line_has_its_time_level_and_thread_and_a_report_stays_under_it():
    import io
    import re
    import threading

    from blacklist_detect.logs import _Format

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(_Format())
    logger = logging.getLogger("blacklist_detect.format_test")
    logger.addHandler(handler)
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.info("环境测试：正常\n  手动检查 0.2 s")
    worker = threading.Thread(target=lambda: logger.warning("from the check"), name="check")
    worker.start()
    worker.join()
    first, second, third = stream.getvalue().splitlines()
    assert re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3} INFO    ui     环境测试：正常", first)
    assert second == "      手动检查 0.2 s"
    assert re.fullmatch(r"\S+ \S+ WARNING check  from the check", third)


def test_crash_log_keeps_only_its_end(tmp_path):
    from blacklist_detect.logs import _trim, masked

    crash = tmp_path / "crash.log"
    crash.write_bytes(b"".join(f"line {number}\n".encode() for number in range(1000)))
    _trim(crash, limit=2000, keep=100)
    text = crash.read_text(encoding="utf-8")
    assert text.startswith("(older lines removed)\nline ") and text.endswith("line 999\n") and len(text) < 140
    _trim(crash, limit=2000, keep=100)
    assert crash.read_text(encoding="utf-8") == text
    assert masked("示例坏人") == "示***" and masked("A") == "A" and masked("") == ""


def test_debug_pictures_keep_the_newest_only(window):
    import numpy as np

    from blacklist_detect.pipeline import CheckResult
    from blacklist_detect.ui import DEBUG_KEEP

    folder = window.store.root / "debug"
    folder.mkdir(parents=True)
    for number in range(DEBUG_KEEP + 5):
        (folder / f"20200101-0000{number:02d}.png").write_bytes(b"")
    window._save_debug(CheckResult(header_found=True, message="", preview_rgb=np.zeros((4, 4, 3), dtype=np.uint8)))
    kept = sorted(path.name for path in folder.glob("*.png"))
    assert len(kept) == DEBUG_KEEP and not kept[-1].startswith("2020")


def test_auto_check_comes_back_after_safe_mode(window):
    from blacklist_detect.storage import Store

    window.store.consented = ["full"]
    window.display_mode.buttons["full"].click()
    window.auto_mode.buttons["auto"].click()
    assert window.store.auto_capture
    # 安全模式 checks on the hotkey only…
    window.display_mode.buttons["safe"].click()
    assert not window.store.auto_capture and window.auto_mode.current() == "manual"
    # …and remembers, through a restart too.
    assert Store(window.store.root).auto_resume is True
    window.display_mode.buttons["full"].click()
    assert window.store.auto_capture and window.auto_mode.current() == "auto"
    # 手动检查 picked by hand stays, through 安全模式 and back.
    window.auto_mode.buttons["manual"].click()
    window.display_mode.buttons["safe"].click()
    window.display_mode.buttons["full"].click()
    assert not window.store.auto_capture and window.auto_mode.current() == "manual"
