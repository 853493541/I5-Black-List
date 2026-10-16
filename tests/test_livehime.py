"""直播姬 and 直播模式: whether its current scene shows 直播画面, read from 直播姬's own log."""

import json

import pytest

from blacklist_detect import livehime
from blacklist_detect.livehime import BEHIND, CLOSED, HIDDEN, MISSING, OK, Capture, SceneWatch, parse_scene, status

TITLE = "模仿者小工具·直播画面"
GAME = "MuMu安卓设备:Qt5156QWindowIcon:MuMuNxDevice.exe"
OURS = TITLE + ":Qt6120QWindowIcon:模仿者小工具.exe"


def _scene_line(*windows: tuple[str, bool]) -> str:
    """A line as 直播姬 writes it when its current scene changes: the window captures, bottom to top."""
    items = [
        {"allow_aero": True, "client_area": True, "is_open": True, "is_visible": visible, "method_name": 0,
         "process_info": spec, "process_name": spec.rsplit(":", 1)[-1], "source_type": "window"}
        for spec, visible in windows
    ]  # fmt: skip
    return (
        "[25084:1013/073314.823:INFO:bililive\\bililive\\livehime\\event_report\\business_action_report.cpp:139] "
        "game_and_widnow_info : " + json.dumps(items, ensure_ascii=False, separators=(",", ":")) + "\n"
    )


START = "[5448:0801/004342.152:INFO:bililive\\app\\bililive_main.cc:38] --- Application Startup ---\n"
NOISE = "[25084:1013/073224.582:INFO:obs\\obs_proxy\\core_proxy\\obs_logging_hook.cpp:53] adding 42 milliseconds of audio buffering\n"


def test_a_scene_line_reads_as_its_captures_bottom_to_top():
    line = _scene_line((GAME, True), (OURS, True), ("a#3Ab#22c:Chrome_WidgetWin_1:chrome.exe", False))
    assert parse_scene(line) == [
        Capture("MuMu安卓设备", "Qt5156QWindowIcon", "MuMuNxDevice.exe", True),
        Capture(TITLE, "Qt6120QWindowIcon", "模仿者小工具.exe", True),
        Capture("a:b#c", "Chrome_WidgetWin_1", "chrome.exe", False),
    ]
    assert parse_scene(_scene_line()) == []
    assert parse_scene(NOISE) is None
    assert parse_scene("game_and_widnow_info : [{broken") is None


def test_the_last_scene_since_the_last_start_is_found_from_the_end(tmp_path, monkeypatch):
    # Small blocks, so the line it looks for lies across several of them.
    monkeypatch.setattr(livehime, "BLOCK", 97)
    path = tmp_path / "bililive_debug.log"
    path.write_text(START + _scene_line((GAME, True)) + START + _scene_line((GAME, True), (OURS, True)) + NOISE * 40, encoding="utf-8")
    watch = SceneWatch(path)
    assert [capture.title for capture in watch.scene()] == ["MuMu安卓设备", TITLE]
    # 直播姬 started again and has not said what it shows yet: not known.
    path.write_text(path.read_text(encoding="utf-8") + START + NOISE, encoding="utf-8")
    assert SceneWatch(path).scene() is None
    assert SceneWatch(tmp_path / "none.log").scene() is None


def test_after_the_first_look_only_what_was_added_is_read(tmp_path):
    path = tmp_path / "bililive_debug.log"
    path.write_text(START + _scene_line((GAME, True)) + NOISE, encoding="utf-8")
    watch = SceneWatch(path)
    assert [capture.title for capture in watch.scene()] == ["MuMu安卓设备"]
    line = _scene_line((GAME, True), (OURS, True))
    with open(path, "a", encoding="utf-8") as log:
        # Half a line, still being written: it waits.
        log.write(line[:60])
    assert [capture.title for capture in watch.scene()] == ["MuMu安卓设备"]
    with open(path, "a", encoding="utf-8") as log:
        log.write(line[60:] + NOISE)
    assert [capture.title for capture in watch.scene()] == ["MuMu安卓设备", TITLE]
    # The source hidden with the eye in 直播姬's list.
    with open(path, "a", encoding="utf-8") as log:
        log.write(_scene_line((GAME, True), (OURS, False)))
    assert watch.scene()[-1].visible is False
    # A new log, shorter than the old one: read again from the end.
    path.write_text(START + _scene_line((OURS, True)), encoding="utf-8")
    assert [capture.title for capture in watch.scene()] == [TITLE]


def test_the_status_of_each_setup():
    game = Capture("MuMu安卓设备", "Qt5156QWindowIcon", "MuMuNxDevice.exe", True)
    chat = Capture("弹幕姬", "Qt5QWindowIcon", "danmaku.exe", True)
    ours = Capture(TITLE, "Qt6120QWindowIcon", "模仿者小工具.exe", True)
    hidden = Capture(TITLE, "Qt6120QWindowIcon", "模仿者小工具.exe", False)
    is_game = lambda capture: capture.title == game.title  # noqa: E731
    assert status(TITLE, False, [game, ours], is_game) == CLOSED
    assert status(TITLE, True, None, is_game) == ""
    assert status(TITLE, True, [game], is_game) == MISSING
    assert status(TITLE, True, [game, hidden], is_game) == HIDDEN
    assert status(TITLE, True, [game, ours], is_game) == OK
    # Under the game: viewers get the game over the marks.
    assert status(TITLE, True, [ours, game], is_game) == BEHIND
    # Another window over it, not the game's: fine. Without the game known, the order is not judged.
    assert status(TITLE, True, [game, ours, chat], is_game) == OK
    assert status(TITLE, True, [ours, game], None) == OK
    # A hidden game capture over it covers nothing; a second, shown copy of ours on top is enough.
    assert status(TITLE, True, [ours, Capture(game.title, game.window_class, game.exe, False)], is_game) == OK
    assert status(TITLE, True, [hidden, game, ours], is_game) == OK
    assert all(livehime.WORDS[state] for state in (OK, MISSING, HIDDEN, BEHIND, CLOSED))


@pytest.fixture
def window(tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from blacklist_detect import single
    from blacklist_detect.ui import MainWindow

    QApplication.instance() or QApplication([])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    log = tmp_path / "bililive_debug.log"
    monkeypatch.setattr(livehime, "log_path", lambda: log)
    running = {"on": True}
    monkeypatch.setattr(single, "running", lambda _name: running["on"])
    made = MainWindow()
    made._watch_timer.stop()
    made.log, made.running = log, running
    yield made
    made.close()


def test_the_stream_row_says_whether_livehime_shows_the_window(window):
    label = window.stream_status
    # No 直播姬 on this PC: nothing is said.
    window._set_stream_mode(True)
    assert window._stream_watch.isActive() and label.isHidden()
    window.log.write_text(START + _scene_line((GAME, True)), encoding="utf-8")
    window._check_stream_setup()
    assert not label.isHidden() and label.text() == livehime.WORDS[MISSING] and label.property("tone") == "warn"
    assert label.font().underline(), "a warning is underlined"
    with open(window.log, "a", encoding="utf-8") as log:
        log.write(_scene_line((GAME, True), (OURS, True)))
    window._check_stream_setup()
    assert label.text().startswith("✓") and label.property("tone") == "ok" and not label.font().underline()
    window.running["on"] = False
    window._check_stream_setup()
    assert label.text() == livehime.WORDS[CLOSED] and label.property("tone") == "warn" and label.font().underline()
    # 直播模式 off: nothing to say, and no more looking.
    window._set_stream_mode(False)
    assert label.isHidden() and not window._stream_watch.isActive()
