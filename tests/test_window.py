"""The window can be built without a display. OCR is not loaded."""

import os
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from blacklist_detect.pipeline import CheckResult, Hit, NameSlot
from blacklist_detect.storage import Store
from blacklist_detect.ui import (
    AddNameDialog,
    MainWindow,
    _zh_clock,
    TagAdd,
    TagCreateDialog,
    TagEditDialog,
    TagPill,
    WarningWindow,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_add_and_remove(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    assert window.list_hint.text() == "还没有名字"
    assert window.blacklist_table.isHidden() is True
    added = window.store.add("罪玥吉尔曼", tags=("炸房", "贴脸"), reason="他做了坏事")
    assert added is not None
    window._show_list()
    assert window.blacklist_table.rowCount() == 1
    assert window.blacklist_table.item(0, 0).text() == "罪玥吉尔曼"
    assert window.blacklist_table.item(0, 1).text() == "炸房、贴脸"
    assert window.blacklist_table.item(0, 2).text() == "他做了坏事"
    assert window.blacklist_table.item(0, 0).textAlignment() & int(Qt.AlignLeft)
    window._hover_blacklist_row(0)
    assert window.blacklist_table.currentRow() == 0
    assert window.blacklist_table.horizontalHeader().highlightSections() is False
    window._clear_blacklist_hover()
    assert window.blacklist_table.currentRow() == -1
    labels = [button.text() for button in window.findChildren(QPushButton)]
    assert "批量添加" in labels
    assert "清空列表" in labels
    assert window.blacklist_table.columnCount() == 4
    assert window.blacklist_table.item(0, 3).text() == ""
    edited = AddNameDialog(
        "罪玥吉尔曼",
        window.store.entries[0].tags,
        window.store.entries[0].reason,
        added_at=window.store.entries[0].added_at,
    )
    added_on = edited.added_on.text()
    assert len(added_on) == 10 and added_on[4] == "-" and ":" not in added_on
    edited.close()
    window.store.add_scan([{"seat": 1, "name": "罪玥吉尔曼", "unclear": False}])
    seen = datetime.now().astimezone().replace(microsecond=0) - timedelta(hours=3)
    window.store.scans[0]["at"] = seen.isoformat()
    window._show_list()
    assert window.blacklist_table.item(0, 3).text() == "3小时前"
    assert window.windowTitle() == "黑名单检测"
    assert window.list_hint.isHidden() is True
    assert window.blacklist_table.isHidden() is False
    assert window.hotkey_edit.text() == "Alt+1"
    assert window.hotkey_edit.isEnabled() is False
    assert window.player_edit.maximumWidth() == window.player_edit.width()
    assert window.player_edit.width() < 200
    assert "点击修改" not in [label.text() for label in window.findChildren(QLabel)]
    created = TagCreateDialog(window.store.tag_catalog(), parent=window)
    created.name_edit.setText("红名")
    created._accept()
    assert created.created == "红名"
    assert window.store.add_custom_tag(created.created)
    window.store.save_settings()
    window._fill_tag_settings()
    created.close()
    assert window.store.tag_catalog() == ("炸房", "贴脸", "挂机", "红名")
    picked = AddNameDialog(catalog=window.store.tag_catalog())
    assert [pill._text for pill in picked.findChildren(TagPill)] == []
    assert [chip._name for chip in picked.findChildren(TagAdd)] == ["炸房", "贴脸", "挂机", "红名"]
    picked.close()
    window.store.add("甲", tags=("红名",))
    asked: list[str] = []

    def confirm(_parent, text: str) -> bool:
        asked.append(text)
        return len(asked) > 1

    monkeypatch.setattr("blacklist_detect.ui._confirm", confirm)
    window._remove_settings_tag("红名")
    assert window.store.custom_tags == ["红名"]
    window._remove_settings_tag("红名")
    assert asked == ["1 个名字使用「红名」：甲。确定删除？"] * 2
    assert window.store.custom_tags == []
    assert window.store.entries[-1].tags == ()
    window.close()


def test_renaming_a_tag_updates_the_edit_panel(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window.store.add("甲", tags=("炸房", "贴脸"))
    window._show_list()
    taken = TagEditDialog("炸房", window.store.tag_catalog())
    taken.name_edit.setText("贴脸")
    taken._accept()
    assert taken.error.text() == "已有这个标签"
    dialog = TagEditDialog("炸房", window.store.tag_catalog())
    dialog.name_edit.setText("闹房")
    dialog._accept()
    assert dialog.renamed == "闹房"
    assert window.store.rename_tag("炸房", dialog.renamed) == "renamed"
    window._refresh_tag_views()
    assert window.blacklist_table.item(0, 1).text() == "贴脸、闹房"
    edited = AddNameDialog("甲", window.store.entries[0].tags, catalog=window.store.tag_catalog())
    assert [pill._text for pill in edited.findChildren(TagPill)] == ["贴脸", "闹房"]
    edited.close()
    window.close()


def test_blacklist_columns_can_be_dragged(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    assert "拖动标题换顺序，拖边缘改宽度" not in [label.text() for label in window.findChildren(QLabel)]
    header = window.blacklist_table.horizontalHeader()
    assert header.sectionsMovable() is True
    window.show()
    edge = header.sectionViewportPosition(0) + header.sectionSize(0) - 2
    assert header._cursor_at(edge) == Qt.SplitHCursor
    assert header._cursor_at(header.sectionViewportPosition(0) + 40) == Qt.OpenHandCursor
    header.moveSection(3, 0)
    assert window._column_labels() == ["最后遇到", "名字", "标签", "原因"]
    assert window.store.column_order == [3, 0, 1, 2]
    window.close()
    again = MainWindow()
    assert again._column_labels() == ["最后遇到", "名字", "标签", "原因"]
    again.blacklist_table.horizontalHeader().resizeSection(0, 220)
    assert again.store.column_widths[0] == 220
    again.close()
    kept = MainWindow()
    assert kept.blacklist_table.columnWidth(0) == 220
    kept.close()


def test_blacklist_dates_sort_newest_first(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    older = window.store.add("甲")
    newer = window.store.add("乙")
    assert older is not None and newer is not None
    older.added_at = "2020-01-01T00:00:00+00:00"
    newer.added_at = "2024-06-01T00:00:00+00:00"
    now = datetime.now().astimezone().replace(microsecond=0)
    window.store.add_scan([{"seat": 1, "name": "甲", "unclear": False}])
    window.store.scans[0]["at"] = (now - timedelta(days=10)).isoformat()
    window.store.add_scan([{"seat": 1, "name": "乙", "unclear": False}])
    window.store.scans[0]["at"] = (now - timedelta(hours=2)).isoformat()
    window._show_list()
    window._sort_blacklist(3)
    assert [window.blacklist_table.item(row, 0).text() for row in range(2)] == ["乙", "甲"]
    window._sort_blacklist(3)
    assert [window.blacklist_table.item(row, 0).text() for row in range(2)] == ["甲", "乙"]
    window.close()


def test_reason_boxes_allow_several_and_a_note(qapp):
    dialog = AddNameDialog()
    dialog.show()
    assert dialog.detail_edit.isVisible() is True
    assert [chip._name for chip in dialog.findChildren(TagAdd)] == ["炸房", "贴脸", "挂机"]
    dialog._attach_tag("炸房")
    dialog._attach_tag("贴脸")
    assert dialog.picked == ["炸房", "贴脸"]
    dialog.name_edit.setText("   ")
    dialog._accept()
    assert dialog.name_error.text() == "请填写名字"
    dialog.name_edit.setText("甲")
    dialog.detail_edit.setText("他做了坏事")
    dialog._accept()
    assert dialog.tags == ("炸房", "贴脸")
    assert dialog.detail == "他做了坏事"
    dialog._detach_tag("贴脸")
    dialog._accept()
    assert dialog.tags == ("炸房",)
    dialog = AddNameDialog("甲", ("炸房",), "", title="修改", allow_delete=True)
    dialog.show()
    from PySide6.QtWidgets import QPushButton
    labeled = {button.text(): button for button in dialog.findChildren(QPushButton)}
    assert labeled["保存"].isDefault() is True
    assert labeled["删除"].isDefault() is False
    assert labeled["删除"].autoDefault() is False
    dialog.close()


def test_elapsed_and_copy_result(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    assert window.watch_label.text() == "正在监控"
    assert window.watch_label.toolTip() == "正在监控"
    window.store.add_scan([{"seat": 1, "name": "莓有橘子甜", "unclear": False}], 0.254)
    window._reload_history()
    assert "0.25" not in window.history_list.item(0).text()
    window.names_view.setPlainText("1号  莓有橘子甜\n12号  未看清")
    window.copy_result()
    assert QApplication.clipboard().text() == "1号  莓有橘子甜\n12号  未看清"
    window.close()


def test_on_the_hour_keeps_the_zero_minute():
    assert _zh_clock(datetime(2026, 10, 6, 21, 0)) == "下午9点0分"
    assert _zh_clock(datetime(2026, 10, 6, 9, 0)) == "上午9点0分"
    assert _zh_clock(datetime(2026, 10, 6, 21, 5)) == "下午9点05分"


def test_history_adds_a_name_to_the_blacklist(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window.store.add_scan(
        [
            {"seat": 2, "name": "纪戴宁", "unclear": False},
            {"seat": 3, "name": "庄园美女...", "unclear": False},
            {"seat": 12, "name": "", "unclear": True},
        ]
    )
    window._reload_history()
    assert window.tabs.tabText(window.history_tab).startswith("记录")
    assert window.history_list.count() == 2
    day = window.history_list.item(0)
    assert day.data(Qt.UserRole) == -1
    assert day.data(Qt.UserRole + 1) == "day"
    folder = window.history_list.itemWidget(day).findChild(QLabel, "dayFolder")
    assert folder.text().startswith("▼")
    assert "上午" in folder.text() or "下午" in folder.text()
    assert "transparent" in window.history_list.itemWidget(day).styleSheet()
    clock = window.history_list.item(1).text().strip()
    assert clock.startswith("上午") is False
    assert clock.startswith("下午") is False
    assert "点" in clock
    assert ":" not in clock
    window._on_history_clicked(day)
    assert window.history_list.item(1).isHidden()
    assert folder.text().startswith("▶")
    window._on_history_clicked(day)
    assert window.history_list.item(1).isHidden() is False
    assert folder.text().startswith("▼")
    assert window.history_list.item(1).font().bold() is True
    assert window.history_table.item(0, 0).text() == "纪戴宁"
    assert window.history_table.item(0, 1).text() == "庄园美女"
    assert "..." not in window.history_table.item(0, 1).text()
    action = window.history_table.cellWidget(0, 0).findChild(QLabel, "rowAction")
    assert action.text() == "加入"
    assert action.isHidden() is True
    window._paint_history_hover(0, 0, True)
    assert action.isHidden() is False
    assert window.history_table.cellWidget(0, 0).styleSheet() == window._history_wrap_style("#fde4e1")
    window._paint_history_hover(0, 0, False)
    assert action.isHidden() is True
    window.player_edit.setText("纪戴宁")
    window._save_player_name()
    assert window.history_table.item(0, 0).foreground().color().name() == "#1c7a3e"
    assert Store(window.store.root).player_name == "纪戴宁"
    action = window.history_table.cellWidget(0, 0).findChild(QLabel, "rowAction")
    assert action.text() == "你"
    assert action.isHidden() is False
    window._hover_history_cell(0, 0)
    assert window.history_table.cellWidget(0, 0).styleSheet() == window._history_wrap_style("#f3fbf6")
    assert window.history_table.viewport().cursor().shape() == Qt.ArrowCursor
    assert window.history_table.item(1, 0).text() == "未看清"
    assert window.history_table.item(1, 0).foreground().color().name() == "#6b7280"
    assert window.history_table.item(1, 0).data(Qt.UserRole) in ("", None)
    assert window.history_table.cellWidget(1, 0).findChild(QLabel, "rowAction") is None
    window.store.add("纪戴宁")
    window._reload_history()
    assert window.history_table.item(0, 0).foreground().color().name() == "#c23b2e"
    assert window.history_table.cellWidget(0, 0).findChild(QLabel, "rowAction") is None
    opened: list[int] = []
    monkeypatch.setattr(window, "_edit_entry", lambda index: opened.append(index))
    window._on_history_cell(0, 0)
    assert opened == [0]
    assert [entry.name for entry in window.store.entries] == ["纪戴宁"]
    window._delete_history()
    assert len(window.store.scans) == 0
    window.store.add_scan([{"seat": 1, "name": "庄园美女", "unclear": False}])
    window._reload_history()
    remove = window.history_list.itemWidget(window.history_list.item(1)).findChild(QPushButton, "rowDelete")
    assert remove.isHidden()
    remove.click()
    assert window.store.scans == []
    assert window.tabs.tabText(window.history_tab) == "记录"
    window.close()


def test_capture_mode_defaults_to_auto(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    assert window.auto_on.isChecked() is True
    assert window.auto_off.isChecked() is False
    assert window.store.auto_capture is True
    assert window._watch_timer.isActive() is True
    assert window.watch_label.text() == "正在监控"
    assert window.hotkey_edit.text() == "Alt+1"
    assert window.hotkey_edit.isEnabled() is False
    assert window.hotkey.active == ""
    monkeypatch.setattr(window.hotkey, "apply", lambda spec: setattr(window.hotkey, "active", spec.display) or True)
    window.auto_off.click()
    assert window.watch_label.text() == "未开启"
    assert window.store.auto_capture is False
    assert window._watch_timer.isActive() is False
    assert window.hotkey_edit.isEnabled() is True
    assert window.hotkey.active == "Alt+1"
    assert Store(window.store.root).auto_capture is False
    window.auto_on.click()
    assert window.watch_label.text() == "正在监控"
    assert window.store.auto_capture is True
    assert window.hotkey_edit.isEnabled() is False
    assert window.hotkey.active == ""
    window._watch_timer.stop()
    window.close()


def test_clean_lobby_shows_a_green_clear(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window._live_check = True
    button = (100, 400, 280, 460)
    window._on_lobby_placed(button)
    assert window.panel.isVisible() is True
    assert window.panel.mode == "checking"
    assert window.panel.label.text() == "正在检查"
    assert window.panel.x() > 0
    window._on_checked("ok", CheckResult(True, "", button_box=button))
    assert window.panel.mode == "clear"
    assert window.panel.label.text() == "没有黑名单"
    assert window.panel.windowFlags() & Qt.WindowStaysOnTopHint
    assert window.panel.windowFlags() & Qt.WindowDoesNotAcceptFocus
    assert window.panel.windowFlags() & Qt.FramelessWindowHint
    slot = NameSlot(0, (0, 0, 1, 1), "甲", "甲", False, 1.0, False)
    hit = Hit(0, "甲", "甲", "", False, "1号  甲")
    text, clear = window._brief(CheckResult(True, "", names=[slot], hits=[hit]))
    assert text == "1 人在名单里"
    assert clear is False
    window._show_panel(CheckResult(True, "", names=[slot], hits=[hit], button_box=button))
    assert window.panel.mode == "hit"
    assert window.panel.label.text() == "黑名单\n甲"
    window.close()


def test_panel_reopens_where_it_was_dragged(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window._live_check = True
    window.panel.show_at(30, 40, "clear", "没有黑名单")
    origin = window.panel.mapToGlobal(window.panel.rect().center())
    local = QPointF(window.panel.rect().center())
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        local,
        QPointF(origin),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    move = QMouseEvent(
        QEvent.Type.MouseMove,
        local + QPointF(80, 25),
        QPointF(origin) + QPointF(80, 25),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        local + QPointF(80, 25),
        QPointF(origin) + QPointF(80, 25),
        Qt.LeftButton,
        Qt.NoButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(window.panel, press)
    QApplication.sendEvent(window.panel, move)
    QApplication.sendEvent(window.panel, release)
    assert window.store.panel_pos == (window.panel.x(), window.panel.y())
    assert window.panel.x() != 30 or window.panel.y() != 40
    saved = window.store.panel_pos
    window._show_panel(CheckResult(True, "", button_box=(100, 400, 280, 460)))
    assert (window.panel.x(), window.panel.y()) == saved
    window._on_glanced("ok", False)
    assert window.panel.isVisible() is False
    assert window._panel_hide_timer.isActive() is False
    window._on_glanced("ok", True)
    assert window._panel_hide_timer.isActive() is False
    window.close()


def test_auto_check_does_not_leave_the_current_tab(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window.worker.request = lambda fn, kind="check": True
    assert window.tabs.tabText(0).startswith("记录")
    assert window.tabs.count() == 3
    settings = window.tabs.count() - 1
    window.tabs.setCurrentIndex(settings)
    window._start(lambda: None, live=True)
    assert window.tabs.currentIndex() == settings
    assert window.watch_label.text() == "正在检查"
    window._start(window._capture_job, live=True)
    assert window.tabs.currentIndex() == settings
    window.close()


def test_titlebar_close_hides_and_tray_can_quit(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window.show()

    class TitleBarClose:
        def spontaneous(self):
            return True

        def ignore(self):
            self.ignored = True

    event = TitleBarClose()
    window.closeEvent(event)
    assert event.ignored is True
    assert window.isHidden() is True
    assert window._closing is False
    if window.tray is not None:
        labels = [action.text() for action in window.tray.contextMenu().actions()]
        assert labels == ["打开", "退出"]
        assert window.tray.toolTip() == "已缩到托盘，右键可退出"
        again = TitleBarClose()
        window.closeEvent(again)
        assert window.tray.toolTip() == "已缩到托盘，右键可退出"
    window.close()


def test_warning_stays_on_top_without_taking_focus(qapp):
    warning = WarningWindow()
    flags = warning.windowFlags()
    assert warning.windowTitle() == "黑名单玩家"
    assert flags & Qt.WindowStaysOnTopHint
    assert flags & Qt.WindowDoesNotAcceptFocus
    assert warning.testAttribute(Qt.WA_ShowWithoutActivating)
    warning.present(["3号：读到「罪玥吉尔曼」，匹配「罪玥吉尔曼」"])
    assert "罪玥吉尔曼" in warning.body.toPlainText()
    warning.close()


def test_prefix_hit_shows_the_stored_name(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window.store.add("无害虎皮吉尔曼", tags=("炸房",))
    window.store.add_scan([{"seat": 1, "name": "无害虎皮", "unclear": False}])
    window._reload_history()
    text = window.history_table.item(0, 0).text()
    assert "无害虎皮吉尔曼" in text
    assert "炸房" not in text
    assert window.history_table.cellWidget(0, 0).findChild(QLabel, "rowAction") is None
    window.close()


def test_corner_reports_refresh_and_skip(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    seat = NameSlot(0, (0, 0, 1, 1), "纪戴宁", "纪戴宁", False, 1.0, False)
    window.store.add_scan([{"seat": 1, "name": "纪戴宁", "unclear": False}])
    window._on_checked("ok", CheckResult(True, "", names=[seat]))
    assert "这一分钟已经记过" in window.watch_label.toolTip()
    window.store.scans[0]["at"] = "2020-01-01T00:00:00+00:00"
    window._on_checked("ok", CheckResult(True, "", names=[seat]))
    assert "已更新这条记录" in window.watch_label.toolTip()
    assert window.watch_label.text() == "没有发现黑名单" or "没有发现黑名单" in window.watch_label.toolTip()
    window.close()


def test_hotkey_saves_on_the_key_press(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window.show()
    assert window.hotkey_edit.isEnabled() is False
    monkeypatch.setattr(window.hotkey, "apply", lambda _spec: True)
    window.auto_off.click()
    assert window.hotkey_edit.isEnabled() is True
    qapp.sendEvent(window.hotkey_edit, QFocusEvent(QEvent.Type.FocusIn))
    assert window.hotkey_edit.placeholderText() == "按下热键"
    assert window.hotkey_edit.text() == ""
    qapp.sendEvent(
        window.hotkey_edit,
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key_1, Qt.KeyboardModifier.AltModifier),
    )
    assert window.store.hotkey == "Alt+1"
    assert window.hotkey_edit.text() == "Alt+1"
    assert Store(window.store.root).hotkey == "Alt+1"
    qapp.sendEvent(window.hotkey_edit, QFocusEvent(QEvent.Type.FocusIn))
    qapp.sendEvent(window.hotkey_edit, QFocusEvent(QEvent.Type.FocusOut))
    assert window.hotkey_edit.text() == "Alt+1"
    assert window.store.hotkey == "Alt+1"
    window.close()


def test_theme_choice_persists(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    from PySide6.QtWidgets import QPushButton

    assert all(button.text() != "清除" for button in window.findChildren(QPushButton))
    assert all(label.text() != "热键" for label in window.findChildren(QLabel))
    assert window.theme_buttons["蓝色"]._selected is True
    assert window.theme_buttons["蓝色"]._color == "#12325a"
    assert all(button.text() not in ("蓝色", "棕色", "紫色", "绿色", "红色") for button in window.findChildren(QPushButton))
    window._set_theme("红色")
    assert window.theme_buttons["红色"]._selected is True
    assert window.theme_buttons["蓝色"]._selected is False
    assert Store(window.store.root).theme == "红色"
    window._set_result("1 人在名单里", "hit", "result")
    assert window.watch_label.objectName() == "hit"
    assert "#c23b2e" in window.styleSheet()
    window.show()
    window.resize(940, 600)
    window._remember_size()
    assert Store(window.store.root).window_size == (window.width(), window.height())
    window.warning.apply_theme()
    window.clear_notice.apply_theme()
    window.close()


def test_reset_asks_before_clearing_everything(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    assert any(button.text() == "清除全部数据" for button in window.findChildren(QPushButton))
    window.store.add("甲", tags=("炸房",))
    window.store.add_scan([{"seat": 1, "name": "甲", "unclear": False}])
    window.store.player_name = "纪戴宁"
    window.store.theme = "绿色"
    window.store.save_settings()
    window.player_edit.setText("纪戴宁")
    window._show_list()
    monkeypatch.setattr("blacklist_detect.ui._confirm", lambda *_args: False)
    window._ask_reset()
    assert [entry.name for entry in window.store.entries] == ["甲"]
    assert window.player_edit.text() == "纪戴宁"
    monkeypatch.setattr("blacklist_detect.ui._confirm", lambda *_args: True)
    window._ask_reset()
    assert window.store.entries == []
    assert window.store.scans == []
    assert window.player_edit.text() == ""
    assert window.store.player_name == ""
    assert window.store.theme == "蓝色"
    assert window.store.tag_catalog() == ("炸房", "贴脸", "挂机")
    assert window.hotkey_edit.text() == "Alt+1"
    assert window.hotkey_edit.isEnabled() is False
    assert window.auto_on.isChecked() is True
    again = Store(window.store.root)
    assert again.entries == []
    assert again.scans == []
    assert again.player_name == ""
    window._watch_timer.stop()
    window.close()
