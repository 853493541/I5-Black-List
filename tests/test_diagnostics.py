"""检查速度 and 日志: a speed test a friend can run, and one zip of the logs to send, with no names."""

import os
import zipfile

import pytest

from blacklist_detect import diagnostics
from blacklist_detect.diagnostics import SPEED_FINE, SPEED_SLOW, CpuWindow, SpeedResult, export_logs, summary_text
from blacklist_detect.storage import Store


def test_the_verdict_follows_a_warm_check():
    # The first read loads the model and is left out; the screen copy is added.
    assert SpeedResult(0.1, [9.0, 1.0, 1.2], 12).typical() == pytest.approx(1.3)
    assert SpeedResult(0.1, [9.0, 1.0, 1.2], 12).verdict() == "速度正常"
    assert SpeedResult(0.2, [9.0, SPEED_FINE, SPEED_FINE], 12).verdict() == "有点慢"
    assert SpeedResult(0.2, [9.0, SPEED_SLOW, SPEED_SLOW], 12).verdict() == "很慢"


def test_the_cpu_window_says_how_busy_the_computer_was():
    window = CpuWindow()
    sum(range(200_000))
    text = window.stop()
    assert text == "" or (text.startswith("CPU ") and "this app" in text)


def test_the_zip_has_the_logs_and_the_computer_but_no_names(tmp_path):
    store = Store(tmp_path)
    store.add("坏人甲", "炸房")
    store.add_like("心动小鹿")
    store.player_name = "我的名字"
    logs = tmp_path / "logs"
    logs.mkdir()
    home = os.path.expanduser("~")
    (logs / "app.log").write_text(f"2026 INFO Start\n2026 WARNING could not read {home}\\x.json\n", encoding="utf-8")
    (logs / "crash.log").write_text("", encoding="utf-8")
    speed = SpeedResult(0.1, [3.0, 1.0, 1.1], 12)
    target = export_logs(tmp_path, summary_text(store, speed, "cpu"), tmp_path / "out")
    assert target.name.startswith("模仿者小工具_日志_") and target.suffix == ".zip"
    with zipfile.ZipFile(target) as archive:
        assert sorted(archive.namelist()) == ["logs/app.log", "logs/crash.log", "电脑信息.txt"]
        summary = archive.read("电脑信息.txt").decode("utf-8")
        log_text = archive.read("logs/app.log").decode("utf-8")
    assert "黑名单 1 people, 心动 1 people" in summary and "Speed test" in summary and "CPU " in summary
    for name in ("坏人甲", "心动小鹿", "我的名字"):
        assert name not in summary and name not in log_text
    assert home not in log_text and "~\\x.json" in log_text


@pytest.fixture
def window(tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from blacklist_detect.ui import MainWindow

    QApplication.instance() or QApplication([])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    made = MainWindow()
    made._watch_timer.stop()
    yield made
    made.close()


def test_the_speed_test_says_it_in_one_line(window):
    window._on_speed_test("ok", SpeedResult(0.2, [4.0, 1.4, 1.6], 12))
    assert window.speed_result.text() == "检查一次约 1.8 秒，速度正常"
    assert window.speed_button.isEnabled()
    window._on_speed_test("err", RuntimeError("x"))
    assert window.speed_result.text() and window.speed_button.isEnabled()


def test_export_puts_the_zip_where_it_says(window, tmp_path, monkeypatch):
    from blacklist_detect import ui

    real = diagnostics.export_logs
    monkeypatch.setattr(ui, "export_logs", lambda root, summary: real(root, summary, tmp_path / "desk"))
    opened = []
    import subprocess

    monkeypatch.setattr(subprocess, "Popen", lambda args, **_: opened.append(args))
    said = []
    monkeypatch.setattr(window, "_say", lambda text, undo=None: said.append(text))
    window._export_logs()
    made = list((tmp_path / "desk").glob("*.zip"))
    assert len(made) == 1 and said == [f"已存到桌面：{made[0].name}"]
    assert opened and opened[0][0] == "explorer"


def test_a_slow_check_says_why_in_the_log(window):
    from blacklist_detect.pipeline import CheckResult

    result = CheckResult(True, "")
    result.timings.update({"capture": 0.1, "find": 2.0, "read": 1.0, "wait": 1.5, "idle": 600})
    window._cpu = CpuWindow()
    note = window._timing_note(result)
    assert "started 1.50 s after it" in note and "recognition idle 10 min before" in note
