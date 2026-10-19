"""日志: one text file a friend can send, with no names, and why a check was slow."""

import os

import pytest

from blacklist_detect import diagnostics
from blacklist_detect.diagnostics import CpuWindow, export_logs, summary_text
from blacklist_detect.storage import Store


def test_the_cpu_window_says_how_busy_the_computer_was():
    window = CpuWindow()
    sum(range(200_000))
    text = window.stop()
    assert text == "" or (text.startswith("CPU ") and "this app" in text)


def test_the_export_is_one_text_file_with_no_names(tmp_path):
    store = Store(tmp_path)
    store.add("坏人甲", "炸房")
    store.add_like("心动小鹿")
    store.player_name = "我的名字"
    logs = tmp_path / "logs"
    logs.mkdir()
    home = os.path.expanduser("~")
    (logs / "app.log.1").write_text("2026 INFO older\n", encoding="utf-8")
    (logs / "app.log").write_text(f"2026 INFO newer\n2026 WARNING could not read {home}\\x.json\n", encoding="utf-8")
    (logs / "crash.log").write_text("", encoding="utf-8")
    target = export_logs(tmp_path, summary_text(store, "cpu"), tmp_path / "out")
    assert target.name.startswith("模仿者小工具_日志_") and target.suffix == ".txt"
    assert list((tmp_path / "out").iterdir()) == [target]
    text = target.read_text(encoding="utf-8")
    assert text.index("电脑和设置") < text.index("older") < text.index("newer")
    assert "黑名单 1 people, 嘉宾 1 people" in text
    for name in ("坏人甲", "心动小鹿", "我的名字"):
        assert name not in text
    assert home not in text and "~\\x.json" in text
    assert "crash.log" not in text, "an empty file is left out"


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


def test_export_puts_one_file_where_it_says(window, tmp_path, monkeypatch):
    from blacklist_detect import ui

    real = diagnostics.export_logs
    monkeypatch.setattr(ui, "export_logs", lambda root, summary, report="": real(root, summary, tmp_path / "desk", report=report))
    opened = []
    import subprocess

    # Popen is a stand-in here: Paddle, looking for the GPU, would run `where` through it, and run first
    # the app's quiet Popen would be built on it.
    monkeypatch.setattr(ui, "inference_device", lambda: "cpu")
    monkeypatch.setattr(subprocess, "Popen", lambda args, **_: opened.append(args))
    said = []
    monkeypatch.setattr(window, "_say", lambda text, undo=None: said.append(text))
    window._export_logs()
    made = list((tmp_path / "desk").glob("*.txt"))
    assert len(made) == 1 and said == [f"已存到桌面：{made[0].name}"]
    assert "电脑和设置" in made[0].read_text(encoding="utf-8")
    assert opened and opened[0][0] == "explorer"


def test_a_slow_check_says_why_in_the_log(window):
    from blacklist_detect.pipeline import CheckResult

    result = CheckResult(True, "")
    result.timings.update({"capture": 0.1, "find": 2.0, "read": 1.0, "wait": 1.5, "idle": 600})
    window._cpu = CpuWindow()
    note = window._timing_note(result)
    assert "started 1.50 s after it" in note and "recognition idle 10 min before" in note


def test_the_export_carries_the_dumps_of_stuck_copies(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "app.log").write_text("2026 WARNING A copy was open but its pipe did not answer\n", encoding="utf-8")
    raw = b"MDMP" + bytes(range(256)) * 40
    (logs / "stuck-4242.dmp").write_bytes(raw)
    target = export_logs(tmp_path, "cpu", tmp_path / "out")
    assert list((tmp_path / "out").iterdir()) == [target], "still one file to send"
    text = target.read_text(encoding="utf-8")
    assert text.index("pipe did not answer") < text.index("==== stuck-4242.dmp")
    assert diagnostics.dumps_in(text) == {"stuck-4242.dmp": raw}
