"""测试效果: a lobby's marks with no lobby and no check, so a streamer sees what viewers will get."""

import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QRect  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from blacklist_detect import livehime  # noqa: E402


@pytest.fixture
def window(tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    from blacklist_detect import ui
    from blacklist_detect.ui import MainWindow

    QApplication.instance() or QApplication([])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(ui, "DEMO_HIT_MS", 150)
    monkeypatch.setattr(ui, "DEMO_LOVE_MS", 250)
    made = MainWindow()
    made._watch_timer.stop()
    made.store.disclaimer_accepted = True
    made.store.consented = ["full"]
    made._on_display_mode("full")
    played: list[str] = []
    monkeypatch.setattr(made.music, "preview", lambda choice: played.append(choice) or choice)
    made.played = played
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


def test_it_shows_the_black_list_then_the_love_effect_and_puts_everything_back(window):
    window._set_stream_mode(True)
    assert window.start_stream_test()
    # The 黑名单 part: the red ring, its card with a made-up name, the 心动 card and the glow.
    assert window.panel.isVisible() and window.panel.mode == "both"
    assert window.hit_card.isVisible() and window.like_card.isVisible() and window.alert.isVisible()
    shown = " ".join(label.text() for label in window.hit_card.findChildren(QLabel))
    assert "示例坏人" in shown or window.hit_card.people == [("示例坏人", ("炸房",))]
    assert window.stream.busy() and window.played == []
    # 直播画面 never gets the 黑名单 card.
    assert window.hit_card not in window.stream._marks()
    # Pressed again while it runs: once is enough.
    assert not window.start_stream_test()
    _wait(200)
    # 心动 alone: its ring, the heart, the card, the border and the music.
    assert window.panel.mode == "liked" and not window.hit_card.isVisible() and window.clear_mark.isVisible()
    assert window.love.playing() and window.played == [window.store.love_music]
    _wait(300)
    # Done: nothing left on the screen or in 直播画面, nothing saved, the last lobby as it was.
    assert not window.panel.isVisible() and not window.like_card.isVisible() and not window.love.playing()
    assert window._demo_likes is None and window._game_box is None and window.store.scans == []
    assert window._glance_pause_until == 0.0


def test_a_real_lobby_takes_over(window, monkeypatch):
    assert window.start_stream_test()
    monkeypatch.setattr(window.worker, "request", lambda fn, kind="check": True)
    window._start(window._capture_job, live=True)
    assert window._demo_likes is None and not window.hit_card.isVisible()


def test_it_shows_over_the_last_lobby_or_what_livehime_captures(window, monkeypatch):
    # No lobby yet and no 直播姬: this window's screen, the ring where 准备案件还原 would be.
    area, box, game, where = window._demo_place()
    screen = window.screen().geometry()
    assert area == screen and where == "this window's screen"
    assert game[0] <= box[0] < box[2] <= game[2] and game[1] <= box[1] < box[3] <= game[3]
    # With 直播模式: over the window 直播姬's scene shows the game with.
    window._set_stream_mode(True)
    game_window = livehime.Capture("MuMu安卓设备", "Qt5QWindowIcon", "MuMuNxDevice.exe", True)
    monkeypatch.setattr(livehime, "game_capture", lambda scene, title: game_window)
    # In desktop pixels, which this screen's scale turns into the window's own units.
    ratio = window.screen().devicePixelRatio()
    native = (screen.x() + round(100 * ratio), screen.y() + round(80 * ratio), screen.x() + round(740 * ratio), screen.y() + round(440 * ratio))
    monkeypatch.setattr(livehime, "client_rect", lambda capture: native)
    area, box, game, where = window._demo_place()
    assert area == QRect(screen.x() + 100, screen.y() + 80, 640, 360) and "MuMuNxDevice.exe" in where
    assert box[0] - game[0] == round(0.430 * 640 * ratio)
    # A lobby seen before: right there again.
    window._game_box, window._game_screen = (10, 20, 30, 40), (0, 0, 100, 60)
    assert window._demo_place() == (None, (10, 20, 30, 40), (0, 0, 100, 60), "the last lobby's game")


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
