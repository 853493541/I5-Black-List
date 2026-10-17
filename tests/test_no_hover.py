"""No box of text on hover anywhere (ask #71): no widget, item or action carries a tooltip, and a tooltip
Qt would show by itself is eaten before it shows. What a hover used to say is read without one."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import QAbstractListModel, QEvent, QModelIndex, QObject, QPoint, Qt  # noqa: E402
from PySide6.QtGui import QAction, QHelpEvent  # noqa: E402
from PySide6.QtWidgets import QAbstractItemView, QApplication, QPushButton, QToolTip, QWidget  # noqa: E402
from test_dialog_fit import _dialogs  # noqa: E402

from blacklist_detect.model import Combo, Scenes  # noqa: E402
from blacklist_detect.pipeline import CheckResult, NameSlot  # noqa: E402
from blacklist_detect.ui import MainWindow  # noqa: E402
from blacklist_detect.ui_theme import NoHoverText  # noqa: E402


@pytest.fixture
def window(tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    QApplication.instance() or QApplication([])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    made = MainWindow()
    made._watch_timer.stop()
    made.store.add("示例坏人", tags=("炸房",), reason="开局就退")
    made.store.add("路过的捣蛋鬼", tags=("场外", "挂机"), reason="场外报点，还在频道里骂人，这是一段很长很长的原因" * 4)
    made.store.add_like("心动小鹿", nickname="小鹿")
    made.store.add_like("心动星星", scenes=Scenes(("ice", "fluffy", "claw")))
    made.store.set_combos([Combo(("心动小鹿", "心动星星"), Scenes(("angel",)))])
    made.store.add_scan([{"seat": 1, "name": "示例坏人", "unclear": False}, {"seat": 2, "name": "心动小鹿", "unclear": False}])
    made._refresh_blacklist_tab()
    made.likes_page.refresh()
    made._reload_history()
    yield made
    made.notice.hide()
    made.close()


def _no_hover(root: QWidget) -> None:
    """Nothing in root says anything on hover, and a hover Qt itself would answer shows nothing."""
    for widget in [root, *root.findChildren(QWidget)]:
        assert widget.toolTip() == "", (type(widget).__name__, widget.objectName(), widget.toolTip())
        assert widget.whatsThis() == "" and widget.statusTip() == "", widget
        spot = QPoint(1, 1)
        for kind in (QEvent.Type.ToolTip, QEvent.Type.WhatsThis):
            assert QApplication.sendEvent(widget, QHelpEvent(kind, spot, widget.mapToGlobal(spot))), (kind, widget)
        assert not QToolTip.isVisible(), widget
        if isinstance(widget, QAbstractItemView) and widget.model() is not None:
            model = widget.model()
            columns = 1 if isinstance(model, QAbstractListModel) else model.columnCount(QModelIndex())
            for row in range(model.rowCount(QModelIndex())):
                for column in range(columns):
                    assert not model.index(row, column).data(Qt.ItemDataRole.ToolTipRole), (widget.objectName(), row, column)
    for action in root.findChildren(QAction):
        # Qt makes an action's tooltip of its words; the guard keeps it from ever showing.
        assert action.toolTip() in ("", action.text().replace("&", ""), action.iconText()), action.toolTip()
        assert action.statusTip() == "" and action.whatsThis() == ""


def test_the_guard_eats_every_hover_on_every_object(window):
    app = QApplication.instance()
    guard = app.findChild(NoHoverText)
    assert guard is not None, "installed by the time the window is made"
    spot = QPoint(1, 1)
    for kind in (QEvent.Type.ToolTip, QEvent.Type.WhatsThis):
        for watched in (QObject(), QWidget(), window, app):
            assert guard.eventFilter(watched, QHelpEvent(kind, spot, spot)) is True
    assert guard.eventFilter(window, QEvent(QEvent.Type.Enter)) is False
    # A tooltip set anyway, by Qt or by a later change, never shows.
    stray = QPushButton("播放")
    stray.setToolTip("从头播放")
    stray.show()
    QApplication.sendEvent(stray, QHelpEvent(QEvent.Type.ToolTip, spot, stray.mapToGlobal(spot)))
    assert not QToolTip.isVisible()
    stray.close()


def test_no_page_section_card_or_tray_says_anything_on_hover(window):
    window.resize(900, 560)
    window.show()
    for tab in (window.history_tab, window.blacklist_tab, window.likes_tab):
        window.tabs.setCurrentIndex(tab)
        QApplication.processEvents()
        _no_hover(window)
    window.tabs.setCurrentIndex(window.settings_tab)
    for key in ("general", "help", "about"):
        window.settings_catalog.choose(key)
        QApplication.processEvents()
        _no_hover(window)
    window.check_panel.open_panel()
    QApplication.processEvents()
    _no_hover(window.check_panel)
    window.check_panel.close_panel()
    # The on-game cards, the overlay and every other window of the app.
    names = [
        NameSlot(index, (0, 0, 1, 1), name, name, False, 0.9, False)
        for index, name in enumerate(("示例坏人", "心动小鹿", "路人甲"))
    ]
    screen = QApplication.primaryScreen().availableGeometry()
    left = screen.left() + screen.width() // 2 - 90
    button = (left, screen.top() + 300, left + 180, screen.top() + 360)
    window._live_check = True
    window._on_lobby_placed(button)
    window._show_panel(CheckResult(True, "", names=names, button_box=button))
    QApplication.processEvents()
    for top in QApplication.topLevelWidgets():
        _no_hover(top)
    window._hide_panel_after_title()
    assert window.tray is None or window.tray.toolTip() == ""


def test_no_dialog_says_anything_on_hover(window, monkeypatch):
    for title, dialog in _dialogs(window, monkeypatch).items():
        dialog.show()
        QApplication.processEvents()
        try:
            _no_hover(dialog)
        except AssertionError as error:
            raise AssertionError(f"{title}: {error}") from error
        finally:
            dialog.done(0)
