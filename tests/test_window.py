"""The window can be built without a display. OCR is not loaded."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

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
