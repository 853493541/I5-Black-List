"""The window can be built without a display. OCR is not loaded."""

import os
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QEnterEvent, QFocusEvent, QFontMetrics, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QPushButton

from blacklist_detect.pipeline import CheckResult, Hit, NameSlot
from blacklist_detect.storage import Store
from blacklist_detect.ui import (
    AddNameDialog,
    DayFolderIcon,
    MainWindow,
    masked_name,
    _zh_clock,
    TagCreateDialog,
    TagEditDialog,
    TagPill,
    WarningWindow,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_recheck_button_applies_a_later_tag(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window.store.add("甲", tags=("炸房",), reason="这人场外说话")
    window._show_list()
    assert window.blacklist_table.item(0, 1).text() == "炸房"
    button = next(item for item in window.findChildren(QPushButton) if item.text() == "按原因补标签")
    button.click()
    assert window.blacklist_table.item(0, 1).text() == "炸房、场外"
    window.close()


def test_the_name_eye_hides_list_names(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert masked_name("怪物名字啊") == "怪****"
    assert masked_name("甲") == "甲"
    window = MainWindow()
    window.store.add("怪物名字啊")
    window._show_list()
    assert window.blacklist_table.item(0, 0).text() == "怪物名字啊"
    window._toggle_name_hiding(True)
    assert window.blacklist_table.item(0, 0).text() == "怪****"
    assert window.store.names_hidden is True
    assert Store(window.store.root).names_hidden is True
    window._toggle_name_hiding(False)
    assert window.blacklist_table.item(0, 0).text() == "怪物名字啊"
    window.close()


def test_add_and_remove(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    assert window.list_hint.text() == "还没有名字"
    assert window.list_empty.isHidden() is False
    assert window.clear_list_button.isHidden() is True
    assert window.blacklist_table.isHidden() is True
    assert window.history_hint.text() == "还没有记录"
    assert window.history_empty.isHidden() is False
    assert window.history_side.isHidden() is True
    assert window.record_card.isHidden() is True
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
    assert window.windowTitle() == "黑名单检测 v0.1.3"
    assert window.list_empty.isHidden() is True
    assert window.clear_list_button.isHidden() is False
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
    assert window.store.tag_catalog() == ("炸房", "贴脸", "挂机", "场外", "不尊重底牌", "红名")
    picked = AddNameDialog(catalog=window.store.tag_catalog())
    assert [(pill._text, pill._active) for pill in picked.findChildren(TagPill)] == [
        ("炸房", False),
        ("贴脸", False),
        ("挂机", False),
        ("场外", False),
        ("不尊重底牌", False),
        ("红名", False),
    ]
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
    assert [(pill._text, pill._active) for pill in edited.findChildren(TagPill)] == [
        ("贴脸", True),
        ("闹房", True),
        ("挂机", False),
        ("场外", False),
        ("不尊重底牌", False),
    ]
    edited._detach_tag("贴脸")
    assert [(pill._text, pill._active) for pill in edited.findChildren(TagPill)] == [
        ("贴脸", False),
        ("闹房", True),
        ("挂机", False),
        ("场外", False),
        ("不尊重底牌", False),
    ]
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
    kept.resize(900, 560)
    kept.show()
    qapp.processEvents()
    table = kept.blacklist_table
    header = table.horizontalHeader()
    available = table.viewport().width()
    last = header.logicalIndex(header.count() - 1)
    before_last = header.sectionSize(last)
    first = header.logicalIndex(0)
    header.resizeSection(first, header.sectionSize(first) + 160)
    qapp.processEvents()
    sizes = [header.sectionSize(header.logicalIndex(visual)) for visual in range(header.count())]
    assert sum(sizes) <= available + 1
    right = header.sectionViewportPosition(last) + header.sectionSize(last)
    assert right <= available + 1
    assert header.sectionSize(last) <= before_last
    kept.close()


def test_blacklist_detail_elides_and_explains_on_hover(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    reason = "第一行说明\n第二行还在" + "很长" * 30
    assert window.store.add("甲", reason=reason) is not None
    assert window.store.add("乙") is not None
    window._show_list()
    stored = window.store.entries[0].reason
    cell = window.blacklist_table.item(0, 2)
    assert cell is not None
    assert "\n" not in cell.text()
    assert cell.text() == " ".join(stored.split())
    assert window.blacklist_table.horizontalHeaderItem(2).text() == "原因"
    assert window.blacklist_table.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert window.blacklist_table.textElideMode() == Qt.TextElideMode.ElideRight
    window.resize(900, 560)
    window.show()
    qapp.processEvents()
    saved = list(window.store.column_widths)
    window._fit_blacklist_columns()
    assert window.store.column_widths == saved
    header = window.blacklist_table.horizontalHeader()
    total = sum(header.sectionSize(index) for index in range(header.count()))
    assert total <= window.blacklist_table.viewport().width() + 1
    inner = max(1, window.blacklist_table.columnWidth(2) - 28)
    elided = QFontMetrics(cell.font()).elidedText(cell.text(), Qt.TextElideMode.ElideRight, inner)
    assert len(elided) < len(cell.text())
    assert elided.endswith("…") or elided.endswith("...")
    dialog = AddNameDialog("甲", (), stored, parent=window)
    assert dialog.detail_edit.toPlainText() == stored
    assert "\n" in dialog.detail_edit.toPlainText()
    dialog.close()
    assert window._reason_for_row(0) == stored
    window._hover_blacklist_row(0, 2)
    assert window.detail_tip.isVisible() is True
    assert window.detail_tip.label.text() == stored
    window._hover_blacklist_row(1, 2)
    assert window.detail_tip.isVisible() is False
    window.close()


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
    assert [(pill._text, pill._active) for pill in dialog.findChildren(TagPill)] == [
        ("炸房", False),
        ("贴脸", False),
        ("挂机", False),
        ("场外", False),
        ("不尊重底牌", False),
    ]
    dialog._attach_tag("炸房")
    dialog._attach_tag("贴脸")
    assert dialog.picked == ["炸房", "贴脸"]
    dialog.name_edit.setText("   ")
    dialog._accept()
    assert dialog.name_error.text() == "请填写名字"
    dialog.name_edit.setText("甲")
    height = dialog.detail_edit.height()
    assert height >= QFontMetrics(dialog.font()).lineSpacing() * 3
    dialog.detail_edit.setPlainText("他做了坏事\n第二行\n第三行\n第四行")
    assert dialog.detail_edit.height() == height
    assert dialog.detail_edit.verticalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    dialog.detail_edit.setPlainText("他做了坏事")
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
    row = None
    root = dialog.layout()
    for index in range(root.count()):
        nested = root.itemAt(index).layout()
        if nested is not None and nested.indexOf(labeled["保存"]) >= 0:
            row = nested
            break
    assert row is not None
    assert row.indexOf(labeled["删除"]) == row.indexOf(labeled["保存"]) - 1
    dialog._delete()
    assert dialog.deleted is True
    assert dialog.result() == QDialog.Accepted
    dialog.close()


def test_elapsed_and_copy_result(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    assert window.watch_label.text() == "自动捕捉中"
    assert window.watch_label.toolTip() == "自动捕捉中"
    window.store.add_scan([{"seat": 1, "name": "莓有橘子甜", "unclear": False}], 0.254)
    window._reload_history()
    assert "0.25" not in window.history_list.item(0).text()
    window.names_view.setPlainText("1号  莓有橘子甜\n12号  未看清")
    window.copy_result()
    assert QApplication.clipboard().text() == "1号  莓有橘子甜\n12号  未看清"
    window.close()


def test_on_the_hour_keeps_the_zero_minute():
    assert _zh_clock(datetime(2026, 10, 6, 13, 20)) == "13:20"
    assert _zh_clock(datetime(2026, 10, 6, 9, 0)) == "09:00"
    assert _zh_clock(datetime(2026, 10, 6, 21, 5)) == "21:05"


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
    mark = window.history_list.itemWidget(day).findChild(DayFolderIcon, "dayMark")
    assert "▼" not in folder.text()
    assert "▶" not in folder.text()
    assert mark._opened is True
    assert "上午" not in folder.text()
    assert "下午" not in folder.text()
    moment = datetime.fromisoformat(str(window.store.scans[0]["at"]))
    assert folder.text() == f"{moment.month}月{moment.day}日"
    assert "transparent" in window.history_list.itemWidget(day).styleSheet()
    clock_label = window.history_list.itemWidget(window.history_list.item(1)).findChild(QLabel, "recordTime")
    clock = clock_label.text()
    assert "#6b7280" not in clock_label.styleSheet()
    assert "#6b7280" not in folder.styleSheet()
    assert ":" in clock
    assert "点" not in clock
    assert "上午" not in clock
    assert "下午" not in clock
    window._on_history_clicked(day)
    assert window.history_list.item(1).isHidden()
    assert mark._opened is False
    window._on_history_clicked(day)
    assert window.history_list.item(1).isHidden() is False
    assert mark._opened is True
    assert window.history_list.item(1).font().bold() is False
    assert window.history_table.item(0, 0).text() == "纪戴宁"
    assert window.history_table.item(0, 1).text() == "庄园美女"
    assert "..." not in window.history_table.item(0, 1).text()
    assert "..." not in str(window.history_table.item(0, 1).data(Qt.UserRole))
    action = window.history_table.cellWidget(0, 0).findChild(QLabel, "rowAction")
    assert action.text() == "添加"
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
    assert "#6b7280" in action.styleSheet()
    assert action.font().bold() is True
    assert action.font().italic() is True
    assert action.isHidden() is False
    window._hover_history_cell(0, 0)
    assert window.history_table.cellWidget(0, 0).styleSheet() == window._history_wrap_style("#f3fbf6")
    assert window.history_table.viewport().cursor().shape() == Qt.ArrowCursor
    assert window.history_table.item(1, 0).text() == "未看清"
    missed = window.history_table.cellWidget(1, 0).findChild(QLabel)
    assert missed.text() == "未知"
    assert missed.font().italic() is True
    assert "italic" in missed.styleSheet()
    assert window.history_table.cellWidget(1, 0).styleSheet() == window._history_wrap_style("")
    window._hover_history_cell(1, 0)
    assert window.history_table.cellWidget(1, 0).styleSheet() == window._history_wrap_style("")
    assert window.history_table.viewport().cursor().shape() == Qt.ArrowCursor
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
    assert window.watch_label.text() == "自动捕捉中"
    assert window.watch_mark.text() == ""
    assert window.hotkey_edit.text() == "Alt+1"
    assert window.hotkey_edit.isEnabled() is False
    assert window.hotkey.active == ""
    monkeypatch.setattr(window.hotkey, "apply", lambda spec: setattr(window.hotkey, "active", spec.display) or True)
    window.auto_off.click()
    assert window.watch_label.text() == "手动捕捉"
    assert window.watch_mark.text() == "[Alt+1]"
    assert window.watch_mark.objectName() == "hotkey"
    assert window.store.auto_capture is False
    assert window._watch_timer.isActive() is False
    assert window.hotkey_edit.isEnabled() is True
    assert window.hotkey.active == "Alt+1"
    assert Store(window.store.root).auto_capture is False
    window.auto_on.click()
    assert window.watch_label.text() == "自动捕捉中"
    assert window.store.auto_capture is True
    assert window.hotkey_edit.isEnabled() is False
    assert window.hotkey.active == ""
    window._watch_timer.stop()
    window.close()


def test_header_cycle_switches_capture_mode(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window.show()
    cycle = window.mode_cycle
    assert cycle is not None
    assert cycle.objectName() == "modeCycle"
    assert cycle.width() == 16
    assert cycle.cursor().shape() == Qt.PointingHandCursor
    assert cycle.isHidden()
    assert cycle.toolTip() == "切换为手动捕捉"
    assert window.watch_label.text() == "自动捕捉中"
    assert cycle.parentWidget() is window.mode_cluster
    assert window.watch_mark.parentWidget() is window.mode_cluster
    assert window.watch_label.parentWidget() is window.mode_cluster
    qapp.sendEvent(window.watch_label, QEnterEvent(QPointF(2, 2), QPointF(2, 2), QPointF(2, 2)))
    qapp.processEvents()
    assert cycle.isHidden() is False
    assert cycle.isVisible()
    assert cycle.x() < window.watch_label.x() < window.watch_mark.x()

    def fake_apply(spec):
        window.hotkey.active = spec.display
        return True

    monkeypatch.setattr(window.hotkey, "apply", fake_apply)

    def click(widget) -> None:
        local = QPointF(widget.rect().center())
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            local,
            QPointF(widget.mapToGlobal(widget.rect().center())),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        qapp.sendEvent(widget, press)

    click(window.watch_label)
    assert window.store.auto_capture is False
    assert window.watch_label.text() == "手动捕捉"
    assert window.watch_mark.text() == "[Alt+1]"
    assert window.auto_off.isChecked() is True
    assert window.auto_on.isChecked() is False
    assert window.hotkey_edit.isEnabled() is True
    assert window.hotkey.active == "Alt+1"
    assert Store(window.store.root).auto_capture is False
    assert cycle.toolTip() == "切换为自动捕捉"
    assert window.tabs.currentIndex() == 0
    click(window.watch_mark)
    assert window.store.auto_capture is True
    assert window.watch_label.text() == "自动捕捉中"
    assert window.auto_on.isChecked() is True
    assert window.hotkey_edit.isEnabled() is False
    assert window.hotkey.active == ""
    assert Store(window.store.root).auto_capture is True
    assert cycle.toolTip() == "切换为手动捕捉"
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
    assert window.panel.label.text() == "请等待"
    assert "#e8892d" in window.panel.styleSheet()
    assert "border: none" in window.panel.styleSheet()
    assert not (window.panel.windowFlags() & Qt.WindowTransparentForInput)
    assert window.hit_card.isVisible() is False
    assert window.clear_mark.isVisible() is False
    assert window.panel.x() > 0
    window._on_checked("ok", CheckResult(True, "", button_box=button))
    assert window.panel.mode == "clear"
    assert window.panel.label.text() == ""
    assert window.panel.toolTip() == "没有黑名单"
    assert window.clear_mark.isVisible() is True
    assert window.clear_mark.height() == max(16, round(window.panel.height() * 0.6))
    assert window.clear_mark.width() == window.clear_mark.height()
    centered = window.panel.y() + (window.panel.height() - window.clear_mark.height()) // 2
    assert window.clear_mark.y() == centered
    mark_right = window.clear_mark.x() + window.clear_mark.width()
    mark_beside = window.clear_mark.x() >= window.panel.x() + window.panel.width() or mark_right <= window.panel.x()
    assert mark_beside
    assert window.panel.windowFlags() & Qt.WindowTransparentForInput
    assert window.panel.windowFlags() & Qt.WindowStaysOnTopHint
    assert window.panel.windowFlags() & Qt.WindowDoesNotAcceptFocus
    assert window.panel.windowFlags() & Qt.FramelessWindowHint
    slot = NameSlot(0, (0, 0, 1, 1), "甲", "甲", False, 1.0, False)
    hit = Hit(0, "甲", "甲", "", False, "1号  甲", ("炸房", "贴脸"))
    text, clear = window._brief(CheckResult(True, "", names=[slot], hits=[hit]))
    assert text == "1 人在名单里"
    assert clear is False
    window._show_panel(CheckResult(True, "", names=[slot], hits=[hit], button_box=button))
    assert window.panel.mode == "hit"
    assert window.panel.label.text() == ""
    assert "6px solid #c23b2e" in window.panel.styleSheet()
    assert not (window.panel.windowFlags() & Qt.WindowTransparentForInput)
    assert window.hit_card.isVisible() is True
    assert window.clear_mark.isVisible() is False
    centered = window.panel.y() + (window.panel.height() - window.hit_card.height()) // 2
    assert window.hit_card.y() == centered
    assert "border: none" in window.hit_card.styleSheet()
    assert window.hit_card.findChild(QLabel, "hitBullet").text() == "•"
    name = window.hit_card.findChild(QLabel, "hitName")
    assert name.text() == "甲"
    assert isinstance(name.parentWidget().layout(), QHBoxLayout)
    assert [pill._text for pill in window.hit_card.findChildren(TagPill)] == ["炸房", "贴脸"]
    assert window.hit_card.findChild(QLabel, "hitMore") is None
    listed = window._tag_cell(("炸房", "贴脸", "挂机", "场外"))
    assert [pill._text for pill in listed.findChildren(TagPill)] == ["炸房", "贴脸", "挂机"]
    assert listed.findChildren(TagPill)[0].font().pointSize() == 11
    window.hit_card.set_people(
        [
            ("国服园丁", ("123",)),
            ("紫花地丁o", ("炸房", "贴脸", "挂机", "第四")),
            ("亿萌", ("贴脸", "挂机")),
        ],
        window.panel.height(),
    )
    names = [label.text() for label in window.hit_card.findChildren(QLabel, "hitName")]
    assert names == ["国服园丁", "紫花地丁o", "亿萌"]
    assert [pill._text for pill in window.hit_card.findChildren(TagPill)] == [
        "123",
        "炸房",
        "贴脸",
        "挂机",
        "贴脸",
        "挂机",
    ]
    assert window.hit_card.findChildren(TagPill)[0].font().pointSize() == 11
    assert "13pt" in window.hit_card.findChild(QLabel, "hitName").styleSheet()
    assert window.hit_card.findChild(QLabel, "hitMore") is None
    assert window.hit_card.findChild(QLabel, "hitExtra") is None
    assert window.hit_card.scroll.verticalScrollBar().maximum() == 0
    assert window.hit_card.height() > window.panel.height()
    three_height = window.hit_card.height()
    window.hit_card.set_people(
        [
            ("国服园丁", ("123",)),
            ("紫花地丁o", ("炸房", "贴脸", "挂机", "第四")),
            ("亿萌", ("贴脸", "挂机")),
            ("第四人", ("挂机",)),
        ],
        window.panel.height(),
    )
    names = [label.text() for label in window.hit_card.findChildren(QLabel, "hitName")]
    assert names == ["国服园丁", "紫花地丁o", "亿萌", "第四人"]
    assert window.hit_card.findChild(QLabel, "hitExtra") is None
    assert window.hit_card.height() == three_height
    assert window.hit_card.scroll.verticalScrollBar().maximum() > 0
    card_right = window.hit_card.x() + window.hit_card.width()
    beside = window.hit_card.x() >= window.panel.x() + window.panel.width() or card_right <= window.panel.x()
    assert beside
    window._show_panel(CheckResult(True, "", button_box=button))
    assert window.panel.mode == "clear"
    assert window.hit_card.isVisible() is False
    assert window.clear_mark.isVisible() is True
    window.close()


def test_panel_covers_the_accept_button(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window._live_check = True
    window.store.panel_pos = (12, 12)
    button = (100, 400, 280, 460)
    window._on_lobby_placed(button)
    screen = QApplication.primaryScreen()
    ratio = screen.devicePixelRatio() if screen is not None else 1.0
    if ratio <= 0:
        ratio = 1.0
    from blacklist_detect.capture import virtual_origin

    origin_x, origin_y = virtual_origin()
    from blacklist_detect.ui import _COVER_OUTSET, _cover_radius

    outset = _COVER_OUTSET
    assert window.panel.x() == round((100 + origin_x) / ratio) - outset
    assert window.panel.y() == round((400 + origin_y) / ratio) - outset
    assert window.panel.width() == round(180 / ratio) + outset * 2
    assert window.panel.height() == round(60 / ratio) + outset * 2
    radius = _cover_radius(window.panel.height())
    assert radius < window.panel.height() // 2
    assert f"border-radius: {radius}px" in window.panel.styleSheet()
    assert window.panel.mask().contains(QPoint(window.panel.height() // 4, 2))
    assert "#e8892d" in window.panel.styleSheet()
    window._show_panel(CheckResult(True, "", button_box=button))
    assert window.panel.mode == "clear"
    assert window.panel.x() == round((100 + origin_x) / ratio) - outset
    assert window.panel.y() == round((400 + origin_y) / ratio) - outset
    window._on_glanced("ok", False)
    assert window.panel.isVisible() is False
    assert window._panel_hide_timer.isActive() is False
    window._on_glanced("ok", True)
    assert window._panel_hide_timer.isActive() is False
    window.close()


def test_a_finished_lobby_is_not_checked_again(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window._watch_timer.stop()
    window._live_check = True
    calls = []
    window.worker.request = lambda *args, **kwargs: calls.append(args) or True
    button = (100, 400, 280, 460)
    names = [
        NameSlot(0, (0, 0, 1, 1), "甲", "甲", False, 0.9, False),
        NameSlot(1, (0, 0, 1, 1), "", "", False, 0.1, True),
    ]
    window._on_checked("ok", CheckResult(True, "", names=names, button_box=button))
    assert calls == []
    assert window.panel.mode == "clear"
    assert window._rescan_active is False
    window._on_lobby_placed(button)
    assert window.panel.mode == "clear"
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
    assert window.watch_label.text() == "自动捕捉中"
    window._start(window._capture_job, live=True)
    assert window.tabs.currentIndex() == settings
    window.close()


def test_titlebar_close_hides_to_the_tray_and_says_so_once(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window.show()
    if window.tray is not None:
        labels = [action.text() for action in window.tray.contextMenu().actions()]
        assert labels == ["打开", "退出"]

    class Tray:
        def __init__(self):
            self.messages = []

        def isVisible(self):
            return True

        def showMessage(self, title, text, *args):
            self.messages.append(title)

        def setToolTip(self, text):
            pass

        def hide(self):
            pass

    class TitleBarClose:
        def spontaneous(self):
            return True

        def ignore(self):
            self.ignored = True

    real_tray, window.tray = window.tray, Tray()
    event = TitleBarClose()
    window.closeEvent(event)
    assert event.ignored is True
    assert window.isHidden() is True
    assert window._closing is False
    assert window.tray.messages == ["黑名单检测仍在运行"]
    window.closeEvent(TitleBarClose())
    assert window.tray.messages == ["黑名单检测仍在运行"]
    window.tray = real_tray
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


def test_prefix_hit_shows_the_read_name_and_the_stored_name(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window.store.add("无害虎皮吉尔曼", tags=("炸房",))
    window.store.add_scan([{"seat": 1, "name": "无害虎皮", "unclear": False}])
    window._reload_history()
    assert window.history_table.item(0, 0).text() == "无害虎皮"
    listed = window.history_table.cellWidget(0, 0).findChild(QLabel, "rowListed")
    assert listed.text() == "名单：无害虎皮吉尔曼"
    assert "炸房" not in listed.text()
    assert window.history_table.cellWidget(0, 0).findChild(QLabel, "rowAction") is None
    window.close()


def test_corner_reports_refresh_and_skip(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    seat = NameSlot(0, (0, 0, 1, 1), "纪戴宁", "纪戴宁", False, 1.0, False)
    window.store.add_scan([{"seat": 1, "name": "纪戴宁", "unclear": False}])
    window._on_checked("ok", CheckResult(True, "", names=[seat]))
    assert window.watch_label.text() == "自动捕捉中"
    window.store.scans[0]["at"] = "2020-01-01T00:00:00+00:00"
    window._on_checked("ok", CheckResult(True, "", names=[seat]))
    assert window.watch_label.text() == "自动捕捉中"
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
    assert any(button.text() == "清除数据且复原" for button in window.findChildren(QPushButton))
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
    assert window.store.tag_catalog() == ("炸房", "贴脸", "挂机", "场外", "不尊重底牌")
    assert window.hotkey_edit.text() == "Alt+1"
    assert window.hotkey_edit.isEnabled() is False
    assert window.auto_on.isChecked() is True
    again = Store(window.store.root)
    assert again.entries == []
    assert again.scans == []
    assert again.player_name == ""
    window._watch_timer.stop()
    window.close()


def test_clear_buttons_split_into_cancel_and_confirm(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    asked: list[str] = []
    monkeypatch.setattr("blacklist_detect.ui._confirm", lambda _parent, text: asked.append(text) or False)
    window.store.add("甲")
    window._show_list()
    window.store.add_scan([{"seat": 1, "name": "甲", "unclear": False}])
    window._reload_history()
    window.clear_list_button.click()
    assert window.clear_list_button.isHidden()
    assert window.clear_list_pair.isHidden() is False
    cancel, confirm = window.clear_list_pair.findChildren(QPushButton)
    assert cancel.text() == "取消"
    assert confirm.text() == "确认清空"
    cancel.click()
    assert window.clear_list_button.isHidden() is False
    assert window.store.entries
    window.clear_list_button.click()
    window.clear_list_pair.findChildren(QPushButton)[1].click()
    assert window.store.entries == []
    assert window.clear_list_button.isHidden() is True
    assert window.list_empty.isHidden() is False
    window.clear_history_button.click()
    assert window.clear_history_button.isHidden()
    history_buttons = window.clear_history_pair.findChildren(QPushButton)
    assert [button.text() for button in history_buttons] == ["取消", "确认清空"]
    history_buttons[0].click()
    assert window.store.scans
    window.clear_history_button.click()
    window.clear_history_pair.findChildren(QPushButton)[1].click()
    assert window.store.scans == []
    assert asked == []
    window.close()


def test_the_add_dialog_refuses_a_name_already_on_the_list(qapp):
    dialog = AddNameDialog(taken=frozenset({"霁玥吉尔曼", "gffdsd"}))
    dialog.name_edit.setText(" GFFDSD ")
    dialog._accept()
    assert dialog.result() != QDialog.Accepted
    assert dialog.name_error.text() == "黑名单里已经有这个名字"
    dialog.name_edit.setText("★☆★")
    dialog._accept()
    assert dialog.name_error.text() == "名字里要有文字或数字"
    dialog.name_edit.setText("新名字")
    dialog._accept()
    assert dialog.result() == QDialog.Accepted
    dialog.close()


def test_editing_a_name_may_keep_its_own_spelling(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window.store.add("甲")
    window.store.add("乙")
    assert window._taken_names(skip=0) == frozenset({"乙"})
    assert window._taken_names() == frozenset({"甲", "乙"})
    window.close()


def test_history_shows_the_name_as_read_beside_the_list_spelling(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window.store.add("小猫爆锤大王")
    window.store.add("纪戴宁")
    window.store.add_scan(
        [
            {"seat": 1, "name": "小猫爆锤...", "unclear": False},
            {"seat": 2, "name": "纪戴宁", "unclear": False},
        ]
    )
    window._reload_history()
    assert window.history_table.item(0, 0).text() == "小猫爆锤"
    listed = window.history_table.cellWidget(0, 0).findChild(QLabel, "rowListed")
    assert listed.text() == "名单：小猫爆锤大王"
    assert window.history_table.item(0, 0).foreground().color().name() == "#c23b2e"
    assert window.history_table.cellWidget(0, 1).findChild(QLabel, "rowListed") is None
    opened: list[int] = []
    monkeypatch.setattr(window, "_edit_entry", lambda index: opened.append(index))
    window._on_history_cell(0, 0)
    assert opened == [0]
    window.close()


def test_a_failed_check_is_shown_and_clears_when_checks_work(qapp, tmp_path, monkeypatch):
    from blacklist_detect.ocr_engine import OcrUnavailable

    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window._watch_timer.stop()
    window._on_worker(("glance", "err", OcrUnavailable("本地 PaddleOCR 中文模型没有就绪。")))
    assert window.watch_label.text() == "识别模型没有就绪"
    assert "PaddleOCR" in window.watch_label.toolTip()
    assert "app.log" in window.watch_label.toolTip()
    assert window._glance_pause_until > 0
    window._on_worker(("check", "err", RuntimeError("坏了")))
    assert window.watch_label.text() == "检查出错"
    window._on_worker(("glance", "ok", False))
    assert window.watch_label.text() == "自动捕捉中"
    window.close()


def test_the_model_load_is_shown_until_it_finishes(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window._watch_timer.stop()
    window.worker.request = lambda *args, **kwargs: True
    window.start_warmup()
    assert window.watch_label.text() == "正在加载识别模型"
    window._on_worker(("warmup", "ok", None))
    assert window.watch_label.text() == "自动捕捉中"
    window.close()


def test_closing_without_a_tray_icon_quits(qapp, tmp_path, monkeypatch):
    from PySide6.QtGui import QCloseEvent

    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window.tray = None
    event = QCloseEvent()
    monkeypatch.setattr(event, "spontaneous", lambda: True)
    window.closeEvent(event)
    assert window._closing is True
    assert event.isAccepted()


def test_a_second_copy_reaches_the_first(qapp):
    from blacklist_detect.ui import instance_key, listen_for_instances, notify_running_instance

    key = instance_key() + "-test"
    assert notify_running_instance(key) is False
    shown: list[bool] = []
    server = listen_for_instances(key, lambda: shown.append(True))
    assert notify_running_instance(key) is True
    for _ in range(50):
        qapp.processEvents()
        if shown:
            break
    assert shown == [True]
    server.close()
