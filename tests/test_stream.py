"""直播模式: the marks over the game copied into one window a streaming app can capture."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint  # noqa: E402
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
    yield made
    made.close()


def _hit(window) -> None:  # noqa: ANN001
    screen = QApplication.primaryScreen().availableGeometry()
    left = screen.left() + screen.width() // 2 - 90
    button = (left, screen.top() + 300, left + 180, screen.top() + 360)
    names = [NameSlot(0, (0, 0, 1, 1), "坏人", "坏人", False, 0.9, False)]
    window._live_check = True
    window._on_lobby_placed(button)
    window._show_panel(CheckResult(True, "", names=names, hits=[Hit(0, "坏人", "坏人", "", False, "", ("炸房",))], button_box=button))
    # Fades are not waited for: the copy shows the marks as they are once they have faded in.
    for mark in (window.panel, window.hit_card):
        mark.setWindowOpacity(1.0)
    window.alert._fade.stop()
    window.alert.setWindowOpacity(1.0)
    window.stream._step()


def _pixel(window, point):  # noqa: ANN001, ANN202
    image = window.stream.grab().toImage()
    ratio = image.devicePixelRatio()
    local = point - window.stream.geometry().topLeft()
    return image.pixelColor(round(local.x() * ratio), round(local.y() * ratio))


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


def test_a_hit_is_copied_where_it_shows_on_green(window):
    window._set_stream_mode("key")
    _hit(window)
    assert window.stream.busy()
    stream = window.stream.geometry()
    assert _pixel(window, stream.center()).name() == "#00ff00", "green where nothing is shown, for the color key"
    inside = _pixel(window, window.hit_card.geometry().center())
    assert inside.name() != "#00ff00" and inside.red() > inside.green(), "the crimson card is copied where it is"
    edge = _pixel(window, stream.topLeft() + QPoint(1, stream.height() // 2))
    assert edge.red() > edge.green(), "the red glow at the edge"
    # The lobby goes: the copy is cleared.
    window._hide_panel_after_title()
    window.alert.stop()
    window.stream._step()
    window.stream._step()
    assert not window.stream.busy() and not window.stream._active


def test_clear_keeps_the_glow_see_through(window):
    window._set_stream_mode("alpha")
    _hit(window)
    stream = window.stream.geometry()
    assert _pixel(window, stream.center()).alpha() == 0, "nothing behind the marks"
    edge = _pixel(window, stream.topLeft() + QPoint(1, stream.height() // 2))
    assert 0 < edge.alpha() < 255 and edge.red() > edge.green(), "the glow keeps its own transparency"
    window._hide_panel_after_title()


def test_preview_shows_sample_marks_for_a_while(window):
    window._set_stream_mode("key")
    window._preview_marks()
    assert window.panel.isVisible() and window.hit_card.isVisible() and window.alert.showing()
    assert window._panel_hide_timer.isActive()
    # A glance that finds no lobby does not take the sample away early.
    window._on_glanced("ok", False)
    assert window.panel.isVisible()
    window._hide_panel_after_title()
