"""The window can be built without a display. OCR is not loaded."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from blacklist_detect.pipeline import CheckResult, Hit, NameSlot
from blacklist_detect.storage import Store
from blacklist_detect.ui import AddNameDialog, MainWindow, WarningWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_add_remove_and_mute(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    added = window.store.add("罪玥吉尔曼", reasons=("炸房", "贴脸"))
    assert added is not None
    window._show_list()
    assert window.blacklist_table.rowCount() == 1
    assert window.blacklist_table.item(0, 0).text() == "罪玥吉尔曼"
    assert window.blacklist_table.item(0, 1).text() == "炸房、贴脸"
    assert window.windowTitle() == "黑名单检测"
    window.mute_box.setChecked(True)
    assert window.store.muted is True
    assert window.hotkey_edit.text() == ""
    window.close()


def test_reason_boxes_allow_several_and_a_note(qapp):
    dialog = AddNameDialog()
    dialog.show()
    assert dialog.detail_edit.isVisible() is False
    dialog.boxes["炸房"].setChecked(True)
    dialog.boxes["其他"].setChecked(True)
    assert dialog.detail_edit.isVisible() is True
    dialog.name_edit.setText("甲")
    dialog.detail_edit.setText("挂机")
    dialog._accept()
    assert dialog.reasons == ("炸房", "其他")
    assert dialog.detail == "挂机"
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
    assert window.time_label.text() == "—"
    assert window.copy_button.isEnabled() is False
    window._show_elapsed(0.254)
    assert window.time_label.text() == "0.25 秒"
    window.names_view.setPlainText("1号  莓有橘子甜\n12号  未看清")
    window.copy_button.setEnabled(True)
    window.copy_result()
    assert QApplication.clipboard().text() == "1号  莓有橘子甜\n12号  未看清"
    assert window.result_label.text() == "已复制。"
    window.close()


def test_history_adds_a_name_to_the_blacklist(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window.store.add_scan(
        [
            {"seat": 2, "name": "纪戴宁", "unclear": False},
            {"seat": 12, "name": "", "unclear": True},
        ]
    )
    window._reload_history()
    assert window.tabs.tabText(window.history_tab).startswith("记录")
    assert window.history_list.count() == 1
    assert window.history_table.item(0, 2).text() == "加入"
    assert window.history_table.item(1, 2).text() == ""
    window._on_history_cell(0, 2)
    assert window.store.entries[0].name == "纪戴宁"
    assert window.history_table.item(0, 2).text() == "已在名单"
    window._on_history_cell(0, 2)
    assert len(window.store.entries) == 1
    window._delete_history()
    assert len(window.store.scans) == 0
    assert window.history_clear.isVisible() is False
    window.store.add_scan([{"seat": 1, "name": "庄园美女", "unclear": False}])
    window.store.add_scan([{"seat": 1, "name": "纪戴宁", "unclear": False}])
    window._reload_history()
    window._clear_history()
    assert window.store.scans == []
    assert window.tabs.tabText(window.history_tab) == "记录"
    window.close()


def test_auto_capture_switch_is_off_until_checked(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    assert window.auto_box.isChecked() is False
    assert window._watch_timer.isActive() is False
    window._watch_timer.setInterval(60_000)
    window.auto_box.setChecked(True)
    assert window.store.auto_capture is True
    assert window._watch_timer.isActive() is True
    window._watch_timer.stop()
    assert Store(window.store.root).auto_capture is True
    window.auto_box.setChecked(False)
    assert window.store.auto_capture is False
    assert Store(window.store.root).auto_capture is False
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
    assert window.result_label.text() == "没有发现黑名单"
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
    assert "1号  甲" in window.panel.label.text()
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
    assert window.panel.isVisible() is True
    assert window._panel_hide_timer.isActive() is True
    assert window._panel_hide_timer.interval() == 1000
    window._on_glanced("ok", True)
    assert window._panel_hide_timer.isActive() is False
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
