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
    from blacklist_detect.ui_dialogs import StreamGuideDialog
    from blacklist_detect.ui_stream import TITLE

    assert not window.stream.enabled()
    # One switch; the window is clear behind the marks, so no 色度键 is needed.
    window.stream_switch.click()
    assert window.stream.enabled() and window.stream.isVisible() and window.stream.mode() == "on"
    assert window.stream.windowTitle() == TITLE == "模仿者小工具·直播画面"
    assert Store(window.store.root).stream_mode == "on"
    # The first time, the guide opens with it; after that, from the ⓘ beside the switch.
    assert len(StreamGuideDialog.shown) == 1 and Store(window.store.root).stream_guided is True
    window.stream_switch.click()
    assert not window.stream.enabled() and not window.stream.isVisible()
    assert Store(window.store.root).stream_mode == ""
    window.stream_switch.click()
    assert len(StreamGuideDialog.shown) == 1
    window.stream_guide.click()
    assert len(StreamGuideDialog.shown) == 2
    window.stream_switch.click()


def test_the_guide_shows_what_changes_then_how(window):
    from blacklist_detect.ui_dialogs import GUIDE_PICTURES, STREAM_DIFF, STREAM_SETUP, StreamGuideDialog

    # Two pages of at most three rows, each row with its picture.
    assert 0 < len(STREAM_DIFF) <= 3 and 0 < len(STREAM_SETUP) <= 3
    for picture, _title, _words in STREAM_DIFF + STREAM_SETUP:
        assert (GUIDE_PICTURES / picture).is_file(), picture
    guide = StreamGuideDialog(window)
    assert len(guide.pictures) == len(STREAM_DIFF) + len(STREAM_SETUP)
    assert all(label.pixmap() is not None and not label.pixmap().isNull() for label in guide.pictures)
    assert guide.page == 0 and "直播模式下" in guide.page_label.text()
    assert guide.back_button.isHidden() and guide.next_button.text() == "怎么设置"
    guide.next_button.click()
    assert guide.page == 1 and "怎么设置" in guide.page_label.text()
    assert not guide.back_button.isHidden() and guide.next_button.text() == "知道了"
    guide.back_button.click()
    assert guide.page == 0
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
    window._show_history_scan(0)
    _lobby(window, hit=False)
    assert not window.like_card.isVisible() and not window.love.playing()
    assert window.notice.kind == "liked"


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


def test_display_has_its_own_picture_guide(window):
    from blacklist_detect.ui_dialogs import DISPLAY_DIFF, GUIDE_PICTURES, DisplayGuideDialog, StreamGuideDialog

    assert 0 < len(DISPLAY_DIFF) <= 3
    assert all((GUIDE_PICTURES / picture).is_file() for picture, _title, _words in DISPLAY_DIFF)
    guide = DisplayGuideDialog(window)
    assert len(guide.pictures) == len(DISPLAY_DIFF) and guide.next_button.text() == "知道了"
    assert guide.back_button.isHidden()
    guide.close()
    shown = []
    window.display_guide.clicked.disconnect()
    window.display_guide.clicked.connect(lambda: shown.append(1))
    window.display_guide.click()
    assert shown == [1] and StreamGuideDialog.shown == []


def test_in_stream_mode_no_page_shows_a_blacklist_name(window):
    from blacklist_detect.ui_dialogs import PictureResultDialog

    window.store.add("坏人")
    window.store.add_scan([{"name": "坏人"}, {"name": "小红"}])
    window._set_stream_mode(True)
    window._show_history_scan(0)
    seats = [window.history_table.cellWidget(0, c) for c in range(2)]
    record = [label.text() for seat in seats if seat for label in seat.findChildren(type(window.history_empty.hint))]
    assert "坏人" not in record and "坏*" in record and "小红" in record
    window._set_stream_mode("")
    window._show_history_scan(0)
    seats = [window.history_table.cellWidget(0, c) for c in range(2)]
    assert "坏人" in [label.text() for seat in seats if seat for label in seat.findChildren(type(window.history_empty.hint))]
    names = [NameSlot(0, (0, 0, 1, 1), "坏人", "坏人", False, 0.9, False), NameSlot(1, (0, 0, 1, 1), "小红", "小红", False, 0.9, False)]
    result = CheckResult(True, "", names=names, hits=[Hit(0, "坏人", "坏人", "", False, "", ())])
    shown = PictureResultDialog("截图检查", result=result, parent=window, hide_hits=True)
    texts = [label.text() for label in shown.findChildren(type(shown.summary))]
    assert "坏人" not in texts and "坏*" in texts and "小红" in texts
    shown.close()


def test_the_stream_window_is_the_game_window_a_capture_sees(window, monkeypatch):
    """A windowed emulator: 直播姬 captures its whole window and stretches it over the canvas, so
    直播模式's window must be that window, size for size, or the marks land off the game."""
    from PySide6.QtCore import QRect

    from blacklist_detect import ui
    from blacklist_detect.storage import Store

    screen = QApplication.primaryScreen()
    ratio = screen.devicePixelRatio()
    geo = screen.geometry()
    outer = QRect(geo.x() + 40, geo.y() + 30, geo.width() // 2 + 200, geo.height() // 2 + 160)
    inner = outer.adjusted(0, 36, -48, 0)  # the game surface, inside the emulator's frame

    def native(rect):  # noqa: ANN001, ANN202
        return (round(rect.left() * ratio), round(rect.top() * ratio), round((rect.right() + 1) * ratio), round((rect.bottom() + 1) * ratio))

    monkeypatch.setattr(ui, "window_rect_at", lambda _x, _y, _order=(), innermost=True: native(inner if innermost else outer))
    window._set_stream_mode(True)
    screen_box = QApplication.primaryScreen().availableGeometry()
    left = int((inner.center().x()) * ratio) - 90
    top = int((inner.center().y()) * ratio)
    button = (left, top, left + 180, top + 60)
    names = [NameSlot(1, (0, 0, 1, 1), "小红", "小红", False, 0.9, False), NameSlot(2, (0, 0, 1, 1), "小明", "小明", False, 0.9, False)]
    window._live_check = True
    window._on_lobby_placed(button)
    window._show_panel(CheckResult(True, "", names=names, button_box=button))
    window.stream._step()
    assert window.stream._area == outer and window.stream.size() == outer.size()
    assert window.love.geometry() == inner, "the border still fits the game surface"
    assert Store(window.store.root).stream_size == (outer.width(), outer.height())
    # Next start: the same size before any check.
    from blacklist_detect.ui import MainWindow

    again = MainWindow()
    again._watch_timer.stop()
    again._set_stream_mode(True)
    assert again.stream.size() == outer.size()
    again.close()
    window._hide_panel_after_title()
