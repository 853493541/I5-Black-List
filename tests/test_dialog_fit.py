"""Layout that held in the UI test: dialogs fit short screens, and long text is never cut where it matters.

A screen is measured by the room Windows leaves for windows: 1366×768 with its taskbar leaves 728 px,
1080p at 150% (1280×720) leaves 672. Every dialog fits the second, with its buttons in view.
"""

import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication, QDialog, QFrame, QLabel

from blacklist_detect.ui import MainWindow
from blacklist_detect.ui_dialogs import StreamGuideDialog
from blacklist_detect.ui_kit import ConfirmDialog, Modal, _height_for
from blacklist_detect.ui_widgets import TagPill

LAPTOP = 728
SHORT = 672


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window.store.add("示例坏人", tags=("炸房",), reason="开局就退")
    window.store.add("路过的捣蛋鬼", tags=("场外", "挂机"), reason="场外报点，还在频道里骂人，这是一段很长很长的原因")
    window.store.add_like("心动小鹿", nickname="小鹿")
    yield window
    window.close()


def _card_height(dialog: Modal) -> int:
    """The card with its shadow, as tall as it will be on the screen."""
    card = dialog.card
    width = max(card.minimumWidth(), min(card.maximumWidth(), card.sizeHint().width()))
    margins = dialog.layout().contentsMargins()
    return _height_for(card, width) + margins.top() + margins.bottom()


def _dialogs(window, monkeypatch) -> dict[str, Modal]:
    """Every dialog the window opens, as it builds it, without showing any."""
    opened: dict[str, Modal] = {}
    name = {"now": ""}

    def keep(dialog, *_args):  # noqa: ANN001, ANN202
        opened[name["now"]] = dialog
        return QDialog.Rejected

    for kind in (Modal, ConfirmDialog, StreamGuideDialog):
        monkeypatch.setattr(kind, "exec", keep)
        monkeypatch.setattr(kind, "open", keep)
    from blacklist_detect.diagnostics import FlowTest
    from blacklist_detect.ui_dialogs import FlowReportDialog, PictureResultDialog

    runs = [{"capture": 0.08, "find": 0.04, "read": 0.06}] * 3
    openers = {
        "添加": window._add_by_dialog,
        "批量导入": window._add_many_by_dialog,
        "编辑": lambda: window._edit_entry(1),
        "清空黑名单": window._clear_list,
        "添加心动": window.likes_page.add_one,
        "编辑心动": lambda: window.likes_page.edit(0),
        "心动特效": window._show_love_effects,
        "显示说明": window._show_display_guide,
        "直播模式说明": window._show_stream_guide,
        "使用声明": window._show_disclaimer,
        "截图检查": lambda: PictureResultDialog("截图检查", error="这张图打不开", parent=window).open(),
        "环境测试": lambda: FlowReportDialog(FlowTest(size=(1920, 1080), runs=runs, right=12), lambda: None, window).open(),
    }
    for title, opener in openers.items():
        name["now"] = title
        opener()
    assert set(opened) == set(openers)
    return opened


def test_every_dialog_fits_a_short_screen_with_its_buttons(window, monkeypatch):
    for title, dialog in _dialogs(window, monkeypatch).items():
        dialog.fit_height(SHORT)
        assert _card_height(dialog) <= SHORT - 8, title


def test_love_effects_fits_a_laptop_without_scrolling(window, monkeypatch):
    effects = _dialogs(window, monkeypatch)["心动特效"]
    if QApplication.platformName() == "windows":
        # Measured with Windows' own fonts; the offscreen platform some tests use draws a fallback
        # face a few percent taller.
        effects.fit_height(LAPTOP)
        assert effects.scroll is None
        assert _card_height(effects) <= LAPTOP - 8
    # Shorter still, the choices scroll between the title and the buttons.
    effects.fit_height(SHORT)
    assert effects.scroll is not None and effects.scroll.isAncestorOf(effects.scene_buttons["classic"])
    assert not effects.scroll.isAncestorOf(effects.play_button)


def test_love_counts_say_they_can_be_ticked_together(window, monkeypatch):
    effects = _dialogs(window, monkeypatch)["心动特效"]
    ticked = {count: not box.icon().isNull() for count, box in effects.count_boxes.items()}
    assert ticked == {count: box.isChecked() for count, box in effects.count_boxes.items()}
    effects.count_boxes[1].click()
    assert not effects.count_boxes[1].icon().isNull()
    assert any(label.text() == "可多选" for label in effects.findChildren(QLabel))


def test_a_long_hotkey_is_shown_whole(window):
    window.hotkey_edit.setText("Ctrl+Shift+Alt+F12")
    metrics = window.hotkey_edit.fontMetrics()
    assert window.hotkey_edit.width() >= metrics.horizontalAdvance("Ctrl+Shift+Alt+F12") + 16


def test_the_check_panel_rows_are_alike_and_each_info_mark_is_beside_its_choice(window):
    # 显示 and 直播模式 are each two joined choices, their ⓘ right after them; 方式 has 手动检查
    # beside its hotkey.
    window.show()
    window.check_panel.toggle()
    for _ in range(5):
        QApplication.processEvents()
    panel = window.check_panel
    assert list(window.auto_mode.buttons) == ["auto", "manual"] and list(window.stream_choice.buttons) == ["on", "off"]
    for choice, info in ((window.display_mode, window.display_guide), (window.stream_choice, window.stream_guide)):
        end = choice.mapTo(panel, QPoint(choice.width(), 0)).x()
        assert 0 <= info.mapTo(panel, QPoint(0, 0)).x() - end <= 16
    manual = window.auto_mode.buttons["manual"]
    assert window.hotkey_edit.mapTo(panel, QPoint(0, 0)).x() - manual.mapTo(panel, QPoint(manual.width(), 0)).x() <= 16
    window.check_panel.close_panel()


def test_clickable_tags_take_clicks_over_a_full_target():
    assert TagPill("炸房", clickable=True).sizeHint().height() >= TagPill.TARGET
    assert TagPill("炸房").sizeHint().height() < TagPill.TARGET


def test_a_seat_keeps_the_name_read_and_cuts_the_list_name(window):
    window.store.add("一个名字特别特别长的玩家")
    window.store.add_scan([{"seat": 1, "name": "一个名字特别长的测试", "unclear": False}])
    window._reload_history()
    seat = window.history_table.cellWidget(0, 0)
    tile = seat.findChild(QFrame, "seat")
    name, listed = seat.findChild(QLabel, "rowName"), seat.findChild(QLabel, "rowListed")
    assert listed.text() == "黑名单：一个名字特别特别长的玩家"
    tile.layout().setGeometry(QRect(0, 0, 330, 32))
    assert name.width() == name.sizeHint().width()
    assert listed.width() < listed.sizeHint().width()
