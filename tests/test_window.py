"""The window can be built without a display. OCR is not loaded."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel

from blacklist_detect.pipeline import CheckResult, Hit, NameSlot
from blacklist_detect.storage import Store
from blacklist_detect.ui import AddNameDialog, HotkeyDialog, MainWindow, WarningWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_add_remove_and_mute(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    assert window.list_hint.text() == "还没有名字，点添加"
    assert window.blacklist_table.isHidden() is True
    added = window.store.add("罪玥吉尔曼", reasons=("炸房", "贴脸"))
    assert added is not None
    window._show_list()
    assert window.blacklist_table.rowCount() == 1
    assert window.blacklist_table.item(0, 0).text() == "罪玥吉尔曼"
    assert window.blacklist_table.item(0, 1).text() == "炸房、贴脸"
    assert window.windowTitle() == "黑名单检测"
    assert window.list_hint.text() == "点击修改"
    assert window.blacklist_table.isHidden() is False
    window.mute_box.setChecked(True)
    assert window.store.muted is True
    assert window.hotkey_edit.text() == ""
    window.close()


def test_reason_boxes_allow_several_and_a_note(qapp):
    dialog = AddNameDialog()
    dialog.show()
    assert dialog.detail_edit.isVisible() is False
    box = dialog.boxes["炸房"]
    text_pos = QPointF(box.width() - 8, box.height() / 2)
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        text_pos,
        text_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        text_pos,
        text_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(box, press)
    QApplication.sendEvent(box, release)
    assert box.isChecked() is True
    dialog.boxes["其他"].setChecked(True)
    assert dialog.detail_edit.isVisible() is True
    dialog.name_edit.setText("   ")
    dialog._accept()
    assert dialog.name_error.text() == "请填写名字"
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
    assert window.watch_label.text() == "未开启"
    assert window.watch_label.toolTip() == "未开启"
    window.store.add_scan([{"seat": 1, "name": "莓有橘子甜", "unclear": False}], 0.254)
    window._reload_history()
    assert "0.25" not in window.history_list.item(0).text()
    assert window.scan_time.text() == "用时 0.25 秒"
    window.names_view.setPlainText("1号  莓有橘子甜\n12号  未看清")
    window.copy_result()
    assert QApplication.clipboard().text() == "1号  莓有橘子甜\n12号  未看清"
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
    assert window.history_table.item(0, 0).text() == "② 纪戴宁"
    action = window.history_table.cellWidget(0, 0).findChild(QLabel, "rowAction")
    assert action.text() == "加入"
    assert action.isHidden() is False
    window._paint_history_hover(0, 0, True)
    assert action.isHidden() is False
    window._paint_history_hover(0, 0, False)
    assert action.isHidden() is False
    assert window.history_table.item(0, 1).text() == "⑫ 未看清"
    assert window.history_table.item(0, 1).data(Qt.UserRole) in ("", None)
    assert window.history_table.cellWidget(0, 1).findChild(QLabel, "rowAction") is None
    window.store.add("纪戴宁")
    window._reload_history()
    assert window.history_table.item(0, 0).foreground().color().name() == "#c23b2e"
    action = window.history_table.cellWidget(0, 0).findChild(QLabel, "rowAction")
    assert action.text() == "移除"
    assert action.isHidden() is False
    monkeypatch.setattr("blacklist_detect.ui._confirm", lambda *_args: True)
    window._on_history_cell(0, 0)
    assert window.store.entries == []
    window._delete_history()
    assert len(window.store.scans) == 0
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
    assert window.watch_label.text() == "未开启"
    window.auto_box.setChecked(True)
    assert window.watch_label.text() == "正在监控"
    assert window.store.auto_capture is True
    assert window._watch_timer.isActive() is True
    window._watch_timer.stop()
    assert Store(window.store.root).auto_capture is True
    window.auto_box.setChecked(False)
    assert window.watch_label.text() == "未开启"
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
    window.store.add("无害虎皮吉尔曼", reasons=("炸房",))
    window.store.add_scan([{"seat": 1, "name": "无害虎皮", "unclear": False}])
    window._reload_history()
    text = window.history_table.item(0, 0).text()
    assert "无害虎皮吉尔曼" in text
    assert "炸房" in text
    action = window.history_table.cellWidget(0, 0).findChild(QLabel, "rowAction")
    assert action.text() == "移除"
    assert action.isHidden() is False
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


def test_theme_choice_persists(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()
    from PySide6.QtWidgets import QPushButton

    labeled = {button.text(): button for button in window.findChildren(QPushButton)}
    assert labeled["设置"].objectName() == "primary"
    assert window.theme_buttons["蓝色"].objectName() == "primary"
    assert window.theme_buttons["蓝色"].icon().isNull() is False
    dialog = HotkeyDialog()
    assert dialog.minimumWidth() == 420
    assert any(button.text() == "取消" for button in dialog.findChildren(QPushButton))
    dialog.close()
    window._set_theme("红色")
    assert window.theme_buttons["红色"].objectName() == "primary"
    assert window.theme_buttons["蓝色"].objectName() == ""
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
