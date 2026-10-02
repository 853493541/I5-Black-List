"""The window can be built without a display. OCR is not loaded."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from blacklist_detect.storage import Store
from blacklist_detect.ui import MainWindow, WarningWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_add_remove_and_mute(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    window.name_edit.setText("罪玥吉尔曼")
    window.note_edit.setText("备注")
    window.add_entry()
    assert window.table.rowCount() == 1
    assert window.table.columnCount() == 3
    assert window.store.entries[0].name == "罪玥吉尔曼"
    assert window.store.entries[0].note == "备注"
    assert window.windowTitle() == "黑名单检测"
    window.mute_box.setChecked(True)
    assert window.store.muted is True
    window._remove(0)
    assert window.table.rowCount() == 0
    assert window.hotkey_edit.text() == ""
    window.close()


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
