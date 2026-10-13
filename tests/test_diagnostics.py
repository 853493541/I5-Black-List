"""自检 and 日志: a whole check a friend can run with a report, and one text file to send, with no names."""

import os

import pytest

from blacklist_detect import diagnostics
from blacklist_detect.diagnostics import SAMPLE_NAMES, SPEED_FINE, SPEED_SLOW, CpuWindow, SelfTest, export_logs, summary_text
from blacklist_detect.storage import Store


def _test(**changes) -> SelfTest:  # noqa: ANN003
    made = SelfTest(capture=0.1, runs=[9.0, 1.0, 1.2], read=list(SAMPLE_NAMES), lobby_found=True, hotkey="Alt+1")
    for name, value in changes.items():
        setattr(made, name, value)
    return made


def test_a_working_pc_reports_all_fine():
    test = _test()
    # The first read loads the model and is left out; the screen copy is added.
    assert test.typical() == pytest.approx(1.3)
    assert test.headline() == "一切正常"
    assert [item for _tone, item, _text in test.rows()] == ["截屏", "识别", "速度", "快捷键"]
    assert ("ok", "识别", "示例大厅的 12 个名字都读对了") in test.rows()
    assert ("ok", "速度", "检查一次约 1.3 秒，正常") in test.rows()


def test_each_problem_shows_in_the_report():
    slow = _test(runs=[9.0, SPEED_SLOW + 1, SPEED_SLOW + 1], cpu_busy=95.0, cpu_own=20.0)
    assert slow.headline() == "有问题要处理"
    assert ("warn", "电脑", "其他程序占用了较多 CPU，关掉一些再试会更快") in slow.rows()
    assert _test(runs=[9.0, SPEED_FINE + 0.5, SPEED_FINE + 0.5]).headline() == "能用，但有可以改进的地方"
    misread = _test(read=["小林同学", *[""] * 11])
    assert ("warn", "识别", "示例大厅的 12 个名字读对了 1 个") in misread.rows()
    assert ("bad", "截屏", "无法截屏：黑屏") in _test(capture_error="黑屏").rows()
    assert ("bad", "快捷键", "Alt+1 没有生效") in _test(hotkey_error="Alt+1 没有生效").rows()
    assert ("ok", "方式", "自动检查：进大厅会自己检查") in _test(auto=True).rows()
    text = slow.text()
    assert text.startswith("自检：有问题要处理") and "✗ 速度" in text and "CPU 95% (this app 20%)" in text


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
    target = export_logs(tmp_path, summary_text(store, "cpu"), _test().text(), tmp_path / "out")
    assert target.name.startswith("模仿者小工具_日志_") and target.suffix == ".txt"
    assert list((tmp_path / "out").iterdir()) == [target]
    text = target.read_text(encoding="utf-8")
    assert text.index("电脑和设置") < text.index("最近一次自检") < text.index("older") < text.index("newer")
    assert "黑名单 1 people, 心动 1 people" in text and "CPU " in text and "自检：一切正常" in text
    for name in ("坏人甲", "心动小鹿", "我的名字"):
        assert name not in text
    assert home not in text and "~\\x.json" in text
    assert "crash.log" not in text, "an empty file is left out"


@pytest.fixture
def window(tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from blacklist_detect.ui import MainWindow
    from blacklist_detect.ui_dialogs import SelfTestDialog

    QApplication.instance() or QApplication([])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    shown = []
    monkeypatch.setattr(SelfTestDialog, "exec", lambda dialog: shown.append(dialog) or 0)
    made = MainWindow()
    made._watch_timer.stop()
    made.shown_reports = shown
    yield made
    made.close()


def test_the_self_test_ends_in_a_report(window, monkeypatch):
    monkeypatch.setattr(window.hotkey, "active", "Alt+1")
    window._on_self_test("ok", _test(hotkey=""))
    assert window.test_button.isEnabled() and window.test_status.text() == ""
    report = window.shown_reports[-1]
    assert report.headline.text() == "一切正常" and ("ok", "快捷键", "Alt+1 可以用") in report.items
    assert window._self_test is not None
    # A hotkey another program holds is the report's to say.
    monkeypatch.setattr(window.hotkey, "active", "")
    window._on_self_test("ok", _test(hotkey=""))
    assert window.shown_reports[-1].items[-1][0] == "bad"
    # A test that could not run still reports.
    window._on_self_test("err", RuntimeError("坏了"))
    assert window.shown_reports[-1].headline.text() == "有问题要处理"


def test_export_puts_one_file_where_it_says(window, tmp_path, monkeypatch):
    from blacklist_detect import ui

    real = diagnostics.export_logs
    monkeypatch.setattr(ui, "export_logs", lambda root, summary, report: real(root, summary, report, tmp_path / "desk"))
    opened = []
    import subprocess

    monkeypatch.setattr(subprocess, "Popen", lambda args, **_: opened.append(args))
    said = []
    monkeypatch.setattr(window, "_say", lambda text, undo=None: said.append(text))
    window._self_test = _test()
    window._export_logs()
    made = list((tmp_path / "desk").glob("*.txt"))
    assert len(made) == 1 and said == [f"已存到桌面：{made[0].name}"]
    assert "自检：一切正常" in made[0].read_text(encoding="utf-8")
    assert opened and opened[0][0] == "explorer"


def test_a_slow_check_says_why_in_the_log(window):
    from blacklist_detect.pipeline import CheckResult

    result = CheckResult(True, "")
    result.timings.update({"capture": 0.1, "find": 2.0, "read": 1.0, "wait": 1.5, "idle": 600})
    window._cpu = CpuWindow()
    note = window._timing_note(result)
    assert "started 1.50 s after it" in note and "recognition idle 10 min before" in note
