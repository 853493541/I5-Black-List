"""记录: a seat on neither list has ♥ (加入嘉宾) and 🚫 (加入黑名单) at its right end, shown on hover."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QWidget  # noqa: E402

from blacklist_detect.ui_theme import ROW_H, THEME  # noqa: E402
from blacklist_detect.ui_widgets import masked_name  # noqa: E402


@pytest.fixture(scope="module")
def qapp():  # noqa: ANN201
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    from blacklist_detect import ui, ui_likes

    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    def no_dialog(*_args, **_kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("no dialog opens")

    # ♥ and 🚫 add at once: neither 添加 nor 添加嘉宾 opens.
    monkeypatch.setattr(ui.AddNameDialog, "exec", no_dialog)
    monkeypatch.setattr(ui_likes.LikeDialog, "exec", no_dialog)
    made = ui.MainWindow()
    made.store.player_name = "心动星星"
    made.store.add("示例坏人")
    made.store.add_like("心动小鹿")
    made.store.add_scan([{"seat": 1, "name": "路人甲", "unclear": False}, {"seat": 2, "name": "路人乙", "unclear": False}])
    # An older record, not the one the page opens on.
    seats = [
        {"seat": 1, "name": "示例坏人", "unclear": False},
        {"seat": 2, "name": "心动小鹿", "unclear": False},
        {"seat": 3, "name": "心动星星", "unclear": False},
        {"seat": 4, "name": "", "unclear": True},
        {"seat": 5, "name": "路人丙...", "unclear": False},
        {"seat": 6, "name": "路人丁", "unclear": False},
    ]
    made.store.scans.append({"at": "2026-10-14T20:00:00+08:00", "elapsed": None, "names": seats})
    made._reload_history()
    # The record with the six seats, whichever row it is on.
    row = next(r for r in range(made.history_list.count()) if len(made.store.scans[max(0, made._scan_at(r))]["names"]) == 6)
    made.history_list.setCurrentRow(row)
    made._show_history_scan(made._scan_at(row))
    assert made.history_table.item(0, 0).text() == "示例坏人"
    yield made
    made.close()


def _buttons(window, row: int, column: int) -> QWidget | None:  # noqa: ANN001
    return window.history_table.cellWidget(row, column).findChild(QWidget, "seatActions")


def _button(window, row: int, column: int, which: str) -> QPushButton:  # noqa: ANN001
    return window.history_table.cellWidget(row, column).findChild(QPushButton, which)


def _record(window) -> tuple[int, int, int, int]:  # noqa: ANN001
    return (
        window.history_list.currentRow(),
        window._selected_scan(),
        window.history_list.verticalScrollBar().value(),
        window.tabs.currentIndex(),
    )


def test_only_a_seat_on_neither_list_has_the_buttons_and_only_on_hover(window):
    # 示例坏人 (黑名单), 心动小鹿 (嘉宾), 心动星星 (我), 未识别: none. 路人丙 and 路人丁: both, hidden.
    for row, column in ((0, 0), (0, 1), (1, 0), (1, 1)):
        assert _buttons(window, row, column) is None
    for row, column in ((2, 0), (2, 1)):
        buttons = _buttons(window, row, column)
        assert buttons is not None and buttons.isHidden()
        assert window.history_table.cellWidget(row, column).findChild(QLabel, "rowAction") is None
    like, ban = _button(window, 2, 0, "seatLike"), _button(window, 2, 0, "seatBan")
    assert (like.toolTip(), like.accessibleName()) == ("", "加入嘉宾")
    assert (ban.toolTip(), ban.accessibleName()) == ("", "加入黑名单")
    assert THEME["rose_wash"] in like.styleSheet() and THEME["red_wash"] in ban.styleSheet()
    # They fit in the seat: the row is no taller.
    assert like.height() <= ROW_H - 6 and ban.height() <= ROW_H - 6
    window._hover_history_cell(2, 0)
    assert not _buttons(window, 2, 0).isHidden()
    assert _buttons(window, 2, 1).isHidden()
    # A click on the rest of the seat does nothing, so the pointer is no hand there.
    assert window.history_table.viewport().cursor().shape() == Qt.ArrowCursor
    window._hover_history_cell(2, 1)
    assert _buttons(window, 2, 0).isHidden() and not _buttons(window, 2, 1).isHidden()
    window._hover_history_cell(0, 0)
    assert _buttons(window, 2, 1).isHidden()
    assert window.history_table.viewport().cursor().shape() == Qt.PointingHandCursor


def test_a_real_pointer_lights_a_seat_on_neither_list_and_its_buttons_keep_it_lit(window, monkeypatch):
    """Such a seat takes the mouse for its buttons, so the table never hears the pointer on it: the seat itself
    lights on Enter, and on Leave the seat now under the pointer lights, or none (tester: a real cursor never lit it)."""
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QEnterEvent

    from blacklist_detect import ui

    window.show()
    QApplication.processEvents()
    table = window.history_table
    first, second = table.cellWidget(2, 0), table.cellWidget(2, 1)
    assert first.objectName() == second.objectName() == "seatWrap"
    pointer = {"at": QPoint()}
    monkeypatch.setattr(ui.QCursor, "pos", staticmethod(lambda: pointer["at"]))

    def enter(wrap) -> None:  # noqa: ANN001
        middle = QPointF(wrap.rect().center())
        QApplication.sendEvent(wrap, QEnterEvent(middle, middle, QPointF(wrap.mapToGlobal(wrap.rect().center()))))

    def leave_to(spot: QPoint) -> None:
        pointer["at"] = spot
        QApplication.sendEvent(leaving, QEvent(QEvent.Type.Leave))

    enter(first)
    assert window._history_hover == (2, 0) and not _buttons(window, 2, 0).isHidden()
    # Onto ♥: no Leave reaches the seat (the button is inside it), so it stays lit.
    assert first.isAncestorOf(_button(window, 2, 0, "seatLike")) and window._history_hover == (2, 0)
    # Off it onto the next seat: that one lights, this one's buttons go.
    leaving = first
    leave_to(second.mapToGlobal(second.rect().center()))
    assert window._history_hover == (2, 1) and _buttons(window, 2, 0).isHidden() and not _buttons(window, 2, 1).isHidden()
    # Off it onto a listed seat the table told of before: that one lights, with no Enter from the table.
    leaving = second
    listed = table.cellWidget(0, 0)
    leave_to(listed.mapToGlobal(listed.rect().center()))
    assert window._history_hover == (0, 0) and _buttons(window, 2, 1).isHidden()
    # Off the table: none.
    enter(second)
    leave_to(window.mapToGlobal(QPoint(2, 2)))
    assert window._history_hover == (-1, -1) and _buttons(window, 2, 1).isHidden()
    window.hide()


def test_the_heart_adds_to_guests_at_once_and_the_seat_turns_rose_in_place(window):
    record = _record(window)
    likes = window.tabs.tabText(window.likes_tab)
    window._hover_history_cell(2, 0)
    _button(window, 2, 0, "seatLike").click()
    # The name as the game showed it, without the cut, on 随机.
    assert [like.name for like in window.store.likes] == ["心动小鹿", "路人丙"]
    assert window.store.likes[1].scenes.random
    assert window.store.entries[-1].name == "示例坏人"
    assert window.toast.text.text() == "已加入嘉宾「路人丙」"
    assert _record(window) == record
    assert window.tabs.tabText(window.likes_tab) != likes and window.tabs.tabText(window.likes_tab).endswith("2")
    item = window.history_table.item(2, 0)
    assert item.foreground().color().name() == THEME["rose"]
    seat = window.history_table.cellWidget(2, 0)
    assert seat.findChild(QLabel, "seatHeart") is not None
    assert seat.findChild(QWidget, "seatActions") is None
    # The 嘉宾 page has the new row.
    assert window.likes_page.table.rowCount() >= 2
    window.toast.action.click()
    assert [like.name for like in window.store.likes] == ["心动小鹿"]
    assert window.history_table.item(2, 0).foreground().color().name() == THEME["text"]
    assert _buttons(window, 2, 0) is not None
    assert _record(window) == record


def test_the_ban_adds_to_the_blacklist_at_once_and_the_seat_turns_red_in_place(window):
    record = _record(window)
    window._hover_history_cell(2, 1)
    _button(window, 2, 1, "seatBan").click()
    entry = window.store.entries[-1]
    assert (entry.name, entry.reason, tuple(entry.tags)) == ("路人丁", "", ())
    assert window.toast.text.text() == "已加入黑名单「路人丁」"
    assert _record(window) == record
    assert window.tabs.tabText(window.blacklist_tab).endswith("2")
    assert window.history_table.item(2, 1).foreground().color().name() == THEME["red"]
    assert window.history_table.cellWidget(2, 1).findChild(QLabel, "seatWarn") is not None
    assert _buttons(window, 2, 1) is None
    # The red seat now opens its edit, where 原因 and 标签 are added.
    opened: list[int] = []
    window._edit_entry = opened.append
    window._on_history_cell(2, 1)
    assert opened == [1]
    window.toast.action.click()
    assert [entry.name for entry in window.store.entries] == ["示例坏人"]
    assert _buttons(window, 2, 1) is not None
    assert _record(window) == record


def test_a_click_on_the_rest_of_the_seat_adds_nothing(window):
    window._on_history_cell(2, 0)
    assert [entry.name for entry in window.store.entries] == ["示例坏人"]
    assert [like.name for like in window.store.likes] == ["心动小鹿"]


def test_a_real_click_on_a_button_adds_and_beside_it_reaches_only_the_table(window, qapp):
    window.resize(1100, 760)
    window.show()
    window._show_records_page()
    qapp.processEvents()
    clicked: list[tuple[int, int]] = []
    window.history_table.cellClicked.connect(lambda row, column: clicked.append((row, column)))
    window._hover_history_cell(2, 0)
    qapp.processEvents()
    tile = window.history_table.cellWidget(2, 0).findChild(QFrame, "seat")
    QTest.mouseClick(tile, Qt.LeftButton, Qt.NoModifier, QPoint(20, tile.height() // 2))
    assert clicked == [(2, 0)]
    assert [like.name for like in window.store.likes] == ["心动小鹿"]
    assert [entry.name for entry in window.store.entries] == ["示例坏人"]
    like = _button(window, 2, 0, "seatLike")
    QTest.mouseClick(like, Qt.LeftButton, Qt.NoModifier, like.rect().center())
    assert [like.name for like in window.store.likes] == ["心动小鹿", "路人丙"]
    assert clicked == [(2, 0)]


def test_the_menu_does_what_the_buttons_do(window):
    menu = window._seat_menu(2, 0)
    texts = {action.text(): action for action in menu.actions() if action.text()}
    assert list(texts) == ["加入黑名单", "加入嘉宾列表", "复制名字"]
    window._on_menu_action(texts["加入嘉宾列表"])
    assert [like.name for like in window.store.likes] == ["心动小鹿", "路人丙"]
    assert window.history_table.item(2, 0).foreground().color().name() == THEME["rose"]
    menu = window._seat_menu(2, 1)
    texts = {action.text(): action for action in menu.actions() if action.text()}
    window._on_menu_action(texts["加入黑名单"])
    assert [entry.name for entry in window.store.entries] == ["示例坏人", "路人丁"]
    assert window.history_table.item(2, 1).foreground().color().name() == THEME["red"]
    # A listed seat's menu is as before.
    assert [a.text() for a in window._seat_menu(2, 1).actions() if a.text()] == ["编辑", "复制名字"]


def test_a_guest_banned_is_moved_only_when_asked(window, monkeypatch):
    from blacklist_detect import ui

    # Put on 嘉宾 elsewhere while this record still shows the seat on neither list.
    window.store.add_like("路人丁")
    answers: list[str] = []

    def ask(_parent, title, *_args, **_kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
        answers.append(title)
        return len(answers) > 1

    monkeypatch.setattr(ui.ConfirmDialog, "ask", ask)
    _button(window, 2, 1, "seatBan").click()
    assert answers == ["移到黑名单"]
    assert [entry.name for entry in window.store.entries] == ["示例坏人"]
    assert "路人丁" in [like.name for like in window.store.likes]
    _button(window, 2, 1, "seatBan").click()
    assert [entry.name for entry in window.store.entries] == ["示例坏人", "路人丁"]
    assert "路人丁" not in [like.name for like in window.store.likes]
    # 撤销 puts it back on 嘉宾.
    window.toast.action.click()
    assert [entry.name for entry in window.store.entries] == ["示例坏人"]
    assert "路人丁" in [like.name for like in window.store.likes]


def test_a_blacklisted_name_is_not_put_on_guests(window):
    window.store.add("路人丙")
    _button(window, 2, 0, "seatLike").click()
    assert [like.name for like in window.store.likes] == ["心动小鹿"]
    assert window.toast.text.text() == "已经在黑名单里了"


def test_stream_mode_masks_a_seat_just_banned(window):
    window.store.stream_mode = "on"
    window._show_history_scan(window._selected_scan())
    assert window.history_table.cellWidget(0, 0).findChild(QLabel, "rowName").text() == masked_name("示例坏人")
    assert window.history_table.cellWidget(2, 1).findChild(QLabel, "rowName").text() == "路人丁"
    _button(window, 2, 1, "seatBan").click()
    assert window.history_table.cellWidget(2, 1).findChild(QLabel, "rowName").text() == masked_name("路人丁")
