"""直播模式: the marks, never a 黑名单 name, copied into one window a streaming app can capture."""

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
    # The window mirrors the game's screen (_area), shown off the screen.
    local = point - window.stream._area.topLeft()
    return image.pixelColor(round(local.x() * ratio), round(local.y() * ratio))


def _on_screen(widget) -> bool:  # noqa: ANN001
    """What the player sees: shown, and not a mark made only for the stream."""
    return widget.isVisible() and not widget.testAttribute(Qt.WA_DontShowOnScreen)


def test_the_choice_is_remembered_and_opens_the_window(window):
    from blacklist_detect.storage import Store
    from blacklist_detect.ui_stream import TITLE

    from blacklist_detect.ui_dialogs import STREAM_GUIDE, StreamGuideDialog

    assert not window.stream.enabled() and not window.stream_preview.isEnabled()
    # One switch; the window is clear behind the marks, so no 色度键 is needed.
    window.stream_switch.click()
    assert window.stream.enabled() and window.stream.isVisible() and window.stream.mode() == "on"
    assert window.stream.windowTitle() == TITLE == "模仿者小工具·直播画面"
    assert Store(window.store.root).stream_mode == "on" and window.stream_preview.isEnabled()
    # The first time, how to set it up opens with it; after that, from 设置方法.
    assert len(StreamGuideDialog.shown) == 1 and Store(window.store.root).stream_guided is True
    window.stream_switch.click()
    assert not window.stream.enabled() and not window.stream.isVisible() and not window.stream_preview.isEnabled()
    assert Store(window.store.root).stream_mode == ""
    window.stream_switch.click()
    assert len(StreamGuideDialog.shown) == 1
    window.stream_guide.click()
    assert len(StreamGuideDialog.shown) == 2
    window.stream_switch.click()


def test_the_guide_goes_step_by_step(window):
    from blacklist_detect.ui_dialogs import GUIDE_PICTURES, STREAM_GUIDE, StreamGuideDialog

    guide = StreamGuideDialog(window)
    assert guide.step == 0 and guide.back_button.isHidden() and guide.next_button.text() == "下一步"
    assert "第 1 步" in guide.step_label.text() and "窗口捕捉" in guide.caption.text()
    for picture, _text in STREAM_GUIDE:
        assert (GUIDE_PICTURES / picture).is_file(), picture
    assert guide.picture.pixmap() is not None and not guide.picture.pixmap().isNull()
    for _ in range(len(STREAM_GUIDE) - 1):
        guide.next_button.click()
    assert guide.step == len(STREAM_GUIDE) - 1 and guide.next_button.text() == "完成"
    assert not guide.back_button.isHidden()
    guide.back_button.click()
    assert guide.step == len(STREAM_GUIDE) - 2
    guide.close()


def test_likes_are_copied_clear_around_and_the_border_plays(window):
    _full(window)
    window._set_stream_mode(True)
    _lobby(window, hit=False)
    assert window.panel.mode == "liked" and window.love.playing()
    assert window.stream.busy()
    inside = _pixel(window, window.like_card.geometry().center())
    assert inside.alpha() > 200, "the 心动 card is copied where it is"
    # Clear where nothing is drawn: no green, nothing for a 色度键 to take.
    area = window.stream._area
    assert _pixel(window, area.center()).alpha() == 0
    image = window.stream.grab().toImage()
    assert all(image.pixelColor(x, y).name() != "#00ff00" for x in range(0, image.width(), 97) for y in range(0, image.height(), 97))
    # The lobby goes: the copy is cleared.
    window._hide_panel_after_title()
    window.stream._step()
    window.stream._step()
    assert not window.stream.busy() and not window.stream._active


@pytest.mark.parametrize("safe", [False, True])
def test_viewers_see_the_red_but_never_a_blacklist_name(window, safe):
    if not safe:
        _full(window)
    window._set_stream_mode(True)
    _lobby(window, hit=True)
    assert window.panel.mode == "both" and window.alert.showing() and not window.love.playing()
    # The stream gets the red ring, the red glow and the 心动 card; never the card with the names.
    assert window.stream._marks() == [window.like_card, window.panel]
    assert window.stream._glow() is window.alert and window.stream._borders() == []
    stream = window.stream._area
    edge = _pixel(window, stream.topLeft() + QPoint(1, stream.height() // 2))
    assert edge.alpha() > 0 and edge.red() > edge.green() + 60, "the red glow"
    assert _pixel(window, window.like_card.geometry().center()).alpha() > 200
    card = window.hit_card.geometry()
    ring = window.panel.geometry()
    # Inside the name card, away from the ring's own soft outer edge: nothing copied.
    inside = card.center() if not card.intersects(ring) else QPoint(card.right() - 8, card.center().y())
    assert _pixel(window, inside).alpha() == 0, "no 黑名单 name card"
    assert _on_screen(window.hit_card) is (not safe)
    window._hide_panel_after_title()


def test_in_safe_mode_only_the_stream_shows_the_marks(window):
    window._set_stream_mode(True)
    _lobby(window, hit=False)
    # Made, and in the stream's copy ...
    assert window.like_card.isVisible() and window.love.playing()
    assert window.stream.busy()
    assert _pixel(window, window.like_card.geometry().center()).alpha() > 200
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
    window._set_stream_mode(True)
    window._preview_marks()
    assert window.like_card.isVisible() and window.love.playing() and window.panel.mode == "liked"
    assert not _on_screen(window.like_card), "安全模式: only in the stream"
    assert window._panel_hide_timer.isActive()
    # A glance that finds no lobby does not take the sample away early.
    window._on_glanced("ok", False)
    assert window.panel.isVisible()
    window._hide_panel_after_title()


def test_the_stream_window_is_off_every_screen(window):
    """On screen its green would fill any bare desktop round a windowed game; a window capture
    reads it wherever it is."""
    window._set_stream_mode(True)
    _lobby(window, hit=False)
    window.stream._step()
    shown = window.stream.geometry()
    assert all(not screen.geometry().intersects(shown) for screen in QApplication.screens())
    # It mirrors the game's screen, size for size.
    assert window.stream._area == (QApplication.screenAt(window.panel.cover_geometry().center()) or QApplication.primaryScreen()).geometry()
    assert shown.size() == window.stream._area.size()
    window._hide_panel_after_title()
