"""测试效果: the sample lobby shown as the game for a moment, framed by the 嘉宾 effects, on the screen
and in 直播画面, so a streamer sees what viewers get without waiting for a lobby."""

import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QRect  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from blacklist_detect import livehime  # noqa: E402


@pytest.fixture
def window(tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    from blacklist_detect import ui
    from blacklist_detect.ui import MainWindow

    QApplication.instance() or QApplication([])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(ui, "DEMO_MS", 400)
    made = MainWindow()
    made._watch_timer.stop()
    made.store.disclaimer_accepted = True
    made.store.consented = ["full"]
    made._on_display_mode("full")
    played: list[str] = []
    monkeypatch.setattr(made.music, "preview", lambda choice: played.append(choice) or choice)
    made.played = played
    # What earlier tests' windows left waiting is handled now, not inside 测试效果's 400 ms: late in a
    # full run it took about as long, and the sample lobby was over before the marks went up.
    QApplication.processEvents()
    yield made
    made._end_stream_test()
    made.notice.hide()
    made.close()


def _wait(ms: int) -> None:
    end = time.time() + ms / 1000
    while time.time() < end:
        QApplication.processEvents()
        time.sleep(0.01)


def test_the_button_is_there_with_stream_mode(window):
    assert window.stream_test.isHidden() and window.stream_test.text() == "测试效果"
    window._set_stream_mode(True)
    assert not window.stream_test.isHidden()
    window._set_stream_mode(False)
    assert window.stream_test.isHidden()


def test_the_sample_lobby_shows_with_the_love_effects_and_everything_goes_back(window):
    window._set_stream_mode(True)
    assert window.start_stream_test()
    picture = window.demo_lobby.geometry()
    assert window.demo_lobby.isVisible() and abs(picture.width() / picture.height() - 16 / 9) < 0.01
    # Viewers get the picture too, under the marks.
    assert window.stream._backdrop is not None and window.stream._backdrop[1] == picture
    _wait(150)
    # 嘉宾 only: the rose ring and the heart on 准备案件还原, the card, the border, the music. No 黑名单.
    assert window.panel.isVisible() and window.panel.mode == "liked" and window.clear_mark.isVisible()
    assert window.like_card.isVisible() and not window.hit_card.isVisible() and not window.alert.isVisible()
    assert window.love.playing() and window.played == [window.store.love_music]
    assert picture.contains(window.panel.cover_geometry().center())
    # Pressed again while it runs: once is enough.
    assert not window.start_stream_test()
    _wait(400)
    # Done: the picture and the marks gone, nothing saved, the last lobby as it was.
    assert not window.demo_lobby.isVisible() and window.stream._backdrop is None
    assert not window.panel.isVisible() and not window.like_card.isVisible() and not window.love.playing()
    assert window._demo_likes is None and window._game_box is None and window.store.scans == []
    assert window._glance_pause_until == 0.0


def test_a_real_lobby_takes_over(window, monkeypatch):
    assert window.start_stream_test()
    monkeypatch.setattr(window.worker, "request", lambda fn, kind="check": True)
    window._start(window._capture_job, live=True)
    assert window._demo_likes is None and not window.demo_lobby.isVisible()


def test_the_sample_lobby_goes_over_the_game_or_in_the_middle(window, monkeypatch):
    from blacklist_detect.ui import DEMO_SHARE

    # No game known: in the middle of this window's screen.
    picture, where = window._demo_place()
    screen = window.screen().geometry()
    assert picture.center() == screen.center() and abs(picture.width() - screen.width() * DEMO_SHARE) <= 2
    assert where == "the middle of this window's screen"
    # With 直播模式: over the window 直播姬's scene shows the game with, 16:9 inside it.
    window._set_stream_mode(True)
    game_window = livehime.Capture("MuMu安卓设备", "Qt5QWindowIcon", "MuMuNxDevice.exe", True)
    ratio = window.screen().devicePixelRatio()
    native = (screen.x() + round(100 * ratio), screen.y() + round(80 * ratio), screen.x() + round(900 * ratio), screen.y() + round(530 * ratio))
    monkeypatch.setattr(livehime, "game_capture", lambda scene, title: game_window)
    monkeypatch.setattr(livehime, "client_rect", lambda capture: native)
    picture, where = window._demo_place()
    assert QRect(screen.x() + 100, screen.y() + 80, 800, 450).contains(picture) and picture.width() == 800
    assert "MuMuNxDevice.exe" in where
    # Its 准备案件还原 is where the sample screen has it.
    button, game = window._demo_boxes(picture)
    assert game[0] < button[0] < button[2] < game[2] and game[1] + 0.7 * (game[3] - game[1]) < button[1]


def test_the_sample_screen_is_the_lobby_in_a_whole_16_9_screen():
    from blacklist_detect.ui_demo import sample_screen

    QApplication.instance() or QApplication([])
    picture = sample_screen()
    assert abs(picture.width() / picture.height() - 16 / 9) < 0.01 and picture is sample_screen()


def test_the_game_capture_is_the_one_under_the_stream_window():
    stream = livehime.Capture("模仿者小工具·直播画面", "Qt", "模仿者小工具.exe", True)
    game = livehime.Capture("MuMu安卓设备", "Qt5QWindowIcon", "MuMuNxDevice.exe", True)
    hidden = livehime.Capture("照片", "WinUI", "Photos.exe", False)
    over = livehime.Capture("微信", "WeChat", "WeChat.exe", True)
    title = stream.title
    assert livehime.game_capture([game, hidden, stream, over], title) is game
    assert livehime.game_capture([hidden, game], title) is game
    assert livehime.game_capture([stream], title) is None
    assert livehime.game_capture(None, title) is None
