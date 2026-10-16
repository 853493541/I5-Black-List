"""The red glow at the screen's edges while a lobby with 黑名单 players is shown."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from blacklist_detect.pipeline import CheckResult, Hit, NameSlot  # noqa: E402


@pytest.fixture
def window(tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    from blacklist_detect.ui import MainWindow

    QApplication.instance() or QApplication([])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    made = MainWindow()
    # The marks over the game, as before 基础模式: 完整模式 and 自动检查, agreed to once.
    made.store.consented = ["full", "auto"]
    made._on_display_mode("full")
    made._on_auto_mode("auto")
    made._watch_timer.stop()
    yield made
    made.close()


def _lobby(window):  # noqa: ANN001, ANN202
    screen = QApplication.primaryScreen().availableGeometry()
    left = screen.left() + screen.width() // 2 - 90
    button = (left, screen.top() + 300, left + 180, screen.top() + 360)
    names = [
        NameSlot(0, (0, 0, 1, 1), "坏人", "坏人", False, 0.9, False),
        NameSlot(1, (0, 0, 1, 1), "小红", "小红", False, 0.9, False),
        NameSlot(2, (0, 0, 1, 1), "小明", "小明", False, 0.9, False),
    ]
    window._live_check = True
    window._on_lobby_placed(button)
    return button, names


def test_a_hit_glows_red_at_the_edges_until_the_lobby_goes(window):
    button, names = _lobby(window)
    hit = Hit(0, "坏人", "坏人", "", False, "", ("炸房",))
    window._show_panel(CheckResult(True, "", names=names, hits=[hit], button_box=button))
    assert window.alert.showing()
    screen = QApplication.screenAt(window.panel.cover_geometry().center()) or QApplication.primaryScreen()
    assert window.alert.geometry() == screen.geometry()
    # Checked again and nobody listed: the glow goes.
    window._show_panel(CheckResult(True, "", names=names[1:], button_box=button))
    assert not window.alert.showing()
    # Back, then the lobby closes: it goes again.
    window._show_panel(CheckResult(True, "", names=names, hits=[hit], button_box=button))
    assert window.alert.showing()
    window._hide_panel_after_title()
    assert not window.alert.showing()


def test_a_hit_with_two_likes_glows_red_under_their_scene(window):
    window.store.add_like("小红")
    window.store.add_like("小明")
    button, names = _lobby(window)
    hit = Hit(0, "坏人", "坏人", "", False, "", ())
    window._show_panel(CheckResult(True, "", names=names, hits=[hit], button_box=button))
    assert window.alert.showing() and window.love.playing()
    window._hide_panel_after_title()


def test_the_glow_is_red_at_the_edge_and_clear_in_the_middle():
    from blacklist_detect.ui_alert import paint_glow

    QApplication.instance() or QApplication([])
    image = QImage(400, 300, QImage.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    paint_glow(painter, 400, 300)
    painter.end()
    edge, middle = image.pixelColor(1, 150), image.pixelColor(200, 150)
    assert edge.alpha() > 100 and edge.red() > edge.green() * 3
    assert middle.alpha() == 0
    # It fades inward, and the corners glow like the sides.
    assert image.pixelColor(1, 150).alpha() > image.pixelColor(12, 150).alpha() > image.pixelColor(30, 150).alpha()
    assert abs(image.pixelColor(1, 1).alpha() - image.pixelColor(200, 1).alpha()) < 20


def test_the_glow_fits_a_game_in_a_window(window, monkeypatch):
    from PySide6.QtCore import QRect

    from blacklist_detect import ui
    from blacklist_detect.capture import virtual_origin

    button, names = _lobby(window)
    screen = QApplication.screenAt(window.panel.cover_geometry().center()) or QApplication.primaryScreen()
    ratio = screen.devicePixelRatio()
    origin_x, origin_y = virtual_origin()
    area = screen.geometry()
    # An emulator window in the middle of the screen, the button inside it.
    game = QRect(area.x() + 100, area.y() + 120, area.width() // 2 + 200, area.height() // 2 + 150)
    asked: list[tuple[int, int]] = []

    def window_at(x, y, order=(), innermost=True):  # noqa: ANN001, ANN202
        asked.append((x, y))
        left = round(area.x() + (game.x() - area.x()) * ratio)
        top = round(area.y() + (game.y() - area.y()) * ratio)
        return left, top, left + round(game.width() * ratio), top + round(game.height() * ratio)

    monkeypatch.setattr(ui, "window_rect_at", window_at)
    hit = Hit(0, "坏人", "坏人", "", False, "", ("炸房",))
    window._show_panel(CheckResult(True, "", names=names, hits=[hit], button_box=button))
    # Asked about the middle of the button, in desktop pixels.
    left, top, right, bottom = button
    assert asked[-1] == ((left + right) // 2 + origin_x, (top + bottom) // 2 + origin_y)
    assert window.alert.geometry() == game
    window._hide_panel_after_title()
    # Nothing found, or something no bigger than the button: the whole screen, as before.
    monkeypatch.setattr(ui, "window_rect_at", lambda x, y, order=(), innermost=True: None)
    window._show_panel(CheckResult(True, "", names=names, hits=[hit], button_box=button))
    assert window.alert.geometry() == area
    window._hide_panel_after_title()
    monkeypatch.setattr(ui, "window_rect_at", lambda x, y, order=(), innermost=True: (x - 5, y - 5, x + 5, y + 5))
    window._show_panel(CheckResult(True, "", names=names, hits=[hit], button_box=button))
    assert window.alert.geometry() == area
    window._hide_panel_after_title()


def test_the_game_window_is_found_as_the_windows_stood_at_the_screenshot(window, monkeypatch):
    # By the end of a check something else may be in front of the button (the streaming app).
    from blacklist_detect import ui

    button, names = _lobby(window)
    orders: list[tuple[int, ...]] = []
    monkeypatch.setattr(ui, "window_rect_at", lambda x, y, order=(), innermost=True: orders.append(order))
    hit = Hit(0, "坏人", "坏人", "", False, "", ("炸房",))
    window._show_panel(CheckResult(True, "", names=names, hits=[hit], button_box=button, windows=(11, 22, 33)))
    assert orders and all(order == (11, 22, 33) for order in orders)
    window._hide_panel_after_title()
