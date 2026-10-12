"""直播模式: the 心动 marks, never the 黑名单 ones, copied into one window a streaming app can capture."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from blacklist_detect.pipeline import CheckResult, Hit, NameSlot  # noqa: E402


@pytest.fixture
def window(tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    from blacklist_detect.ui import MainWindow

    QApplication.instance() or QApplication([])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    made = MainWindow()
    made._watch_timer.stop()
    made.store.add_like("小红")
    made.store.add_like("小明")
    yield made
    made.notice.hide()
    made.close()


def _full(window) -> None:  # noqa: ANN001
    window.store.consented = ["full"]
    window._on_display_mode("full")


def _lobby(window, hit: bool) -> None:  # noqa: ANN001
    screen = QApplication.primaryScreen().availableGeometry()
    left = screen.left() + screen.width() // 2 - 90
    button = (left, screen.top() + 300, left + 180, screen.top() + 360)
    names = [
        NameSlot(0, (0, 0, 1, 1), "坏人", "坏人", False, 0.9, False),
        NameSlot(1, (0, 0, 1, 1), "小红", "小红", False, 0.9, False),
        NameSlot(2, (0, 0, 1, 1), "小明", "小明", False, 0.9, False),
    ]
    hits = [Hit(0, "坏人", "坏人", "", False, "", ("炸房",))] if hit else []
    window._live_check = True
    window._love_played = False
    window._on_lobby_placed(button)
    window._show_panel(CheckResult(True, "", names=names, hits=hits, button_box=button))
    # Fades are not waited for: the copy shows the marks as they are once they have faded in.
    for mark in (window.panel, window.hit_card, window.like_card, window.clear_mark):
        mark.setWindowOpacity(1.0)
    window.alert._fade.stop()
    window.alert.setWindowOpacity(1.0)
    window.stream._step()


def _pixel(window, point):  # noqa: ANN001, ANN202
    image = window.stream.grab().toImage()
    ratio = image.devicePixelRatio()
    local = point - window.stream.geometry().topLeft()
    return image.pixelColor(round(local.x() * ratio), round(local.y() * ratio))


def _on_screen(widget) -> bool:  # noqa: ANN001
    """What the player sees: shown, and not a mark made only for the stream."""
    return widget.isVisible() and not widget.testAttribute(Qt.WA_DontShowOnScreen)


def test_the_choice_is_remembered_and_opens_the_window(window):
    from blacklist_detect.storage import Store
    from blacklist_detect.ui_stream import TITLE

    assert not window.stream.enabled() and not window.stream_preview.isEnabled()
    window.stream_control.buttons["key"].click()
    assert window.stream.enabled() and window.stream.isVisible() and window.stream.mode() == "key"
    assert window.stream.windowTitle() == TITLE == "模仿者小工具·直播画面"
    assert Store(window.store.root).stream_mode == "key" and window.stream_preview.isEnabled()
    window.stream_control.buttons["alpha"].click()
    assert window.stream.mode() == "alpha" and Store(window.store.root).stream_mode == "alpha"
    window.stream_control.buttons["off"].click()
    assert not window.stream.enabled() and not window.stream.isVisible() and not window.stream_preview.isEnabled()


def test_likes_are_copied_on_green_and_the_border_plays(window):
    _full(window)
    window._set_stream_mode("key")
    _lobby(window, hit=False)
    assert window.panel.mode == "liked" and window.love.playing()
    assert window.stream.busy()
    inside = _pixel(window, window.like_card.geometry().center())
    assert inside.name() != "#00ff00", "the 心动 card is copied where it is"
    # The lobby goes: the copy is cleared.
    window._hide_panel_after_title()
    window.stream._step()
    window.stream._step()
    assert not window.stream.busy() and not window.stream._active


def test_nothing_about_the_blacklist_reaches_the_stream(window):
    _full(window)
    window._set_stream_mode("key")
    _lobby(window, hit=True)
    # The player sees the red ring, the card and the glow over the game ...
    assert window.panel.mode == "both" and _on_screen(window.hit_card) and window.alert.showing()
    # ... viewers see only the 心动 card.
    assert window.stream._marks() == [window.like_card]
    stream = window.stream.geometry()
    assert _pixel(window, window.hit_card.geometry().center()).name() == "#00ff00", "no 黑名单 card"
    assert _pixel(window, window.panel.cover_geometry().center()).name() == "#00ff00", "no red ring"
    assert _pixel(window, stream.topLeft() + QPoint(1, stream.height() // 2)).name() == "#00ff00", "no red glow"
    assert _pixel(window, window.like_card.geometry().center()).name() != "#00ff00"
    window._hide_panel_after_title()


def test_in_safe_mode_only_the_stream_shows_the_marks(window):
    window._set_stream_mode("alpha")
    _lobby(window, hit=False)
    # Made, and in the stream's copy ...
    assert window.like_card.isVisible() and window.love.playing()
    assert window.stream.busy()
    assert _pixel(window, window.like_card.geometry().center()).alpha() > 0
    # ... but never on the player's screen, where the corner box says it instead.
    for mark in (window.panel, window.like_card, window.clear_mark, window.love):
        assert not _on_screen(mark)
    assert window.notice.kind == "liked"
    # 直播模式 off: nothing is made at all.
    window._set_stream_mode("")
    _lobby(window, hit=False)
    assert not window.like_card.isVisible() and not window.love.playing()
    assert window.notice.kind == "liked"


def test_preview_shows_sample_likes_for_a_while(window):
    window._set_stream_mode("key")
    window._preview_marks()
    assert window.like_card.isVisible() and window.love.playing() and window.panel.mode == "liked"
    assert not _on_screen(window.like_card), "安全模式: only in the stream"
    assert window._panel_hide_timer.isActive()
    # A glance that finds no lobby does not take the sample away early.
    window._on_glanced("ok", False)
    assert window.panel.isVisible()
    window._hide_panel_after_title()
