"""Main window, tray status, and the always-on-top warning."""

from __future__ import annotations

import queue
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from blacklist_detect.capture import (
    capture_capability_message,
    capture_displays,
    lock_foreground,
)
from blacklist_detect.hotkey import GlobalHotkey, parse_hotkey
from blacklist_detect.match import seat_number
from blacklist_detect.pipeline import CheckResult, check_frames, check_image
from blacklist_detect.sound import chime_path, play_chime
from blacklist_detect.storage import Store


def run_app() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("黑名单检测")
    app.setFont(chinese_font())
    window = MainWindow()
    window.show()
    return app.exec()


def chinese_family() -> str:
    """A face that actually contains simplified Chinese. Qt does not fall back by itself."""
    from PySide6.QtGui import QFontDatabase

    installed = set(QFontDatabase.families())
    for name in (
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "微软雅黑",
        "Sarasa Gothic SC",
        "Noto Sans CJK SC",
        "Noto Sans SC",
        "Source Han Sans SC",
        "思源黑体",
        "PingFang SC",
        "SimHei",
        "黑体",
    ):
        if name in installed:
            return name
    return "Microsoft YaHei"


def chinese_font(point_size: int = 11) -> QFont:
    font = QFont(chinese_family())
    font.setPointSize(point_size)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


def _icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#8c6a1f"))
    painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
    painter.setBrush(QColor("#f6f1e6"))
    painter.drawRoundedRect(16, 16, 32, 6, 2, 2)
    painter.drawRoundedRect(16, 29, 32, 6, 2, 2)
    painter.drawRoundedRect(16, 42, 20, 6, 2, 2)
    painter.end()
    return QIcon(pixmap)


class HotkeyDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置热键")
        self.spec = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("按下要使用的按键，可以加上 Ctrl、Alt 或 Shift。按 Esc 取消。"))
        self.hint = QLabel("等待按键。")
        self.setFont(chinese_font())
        layout.addWidget(self.hint)
        self.resize(360, 120)

    def keyPressEvent(self, event) -> None:  # noqa: ANN001
        if event.isAutoRepeat():
            return
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        if event.key() in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta):
            return
        key = _qt_key_name(event.key())
        if key is None:
            self.hint.setText("请按字母、数字，或 F1 到 F12。")
            return
        modifiers = []
        flags = event.modifiers()
        if flags & Qt.ControlModifier:
            modifiers.append("Ctrl")
        if flags & Qt.AltModifier:
            modifiers.append("Alt")
        if flags & Qt.ShiftModifier:
            modifiers.append("Shift")
        if flags & Qt.MetaModifier:
            modifiers.append("Win")
        self.spec = parse_hotkey("+".join([*modifiers, key]))
        if self.spec is None:
            self.hint.setText("这个组合不能用。")
            return
        self.accept()


def _qt_key_name(key: int) -> str | None:
    if Qt.Key_A <= key <= Qt.Key_Z or Qt.Key_0 <= key <= Qt.Key_9:
        return chr(key)
    if Qt.Key_F1 <= key <= Qt.Key_F12:
        return f"F{key - Qt.Key_F1 + 1}"
    return None


class CheckWorker(QThread):
    """Owns the OCR engine. Paddle is loaded on this thread and reused here."""

    done = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._queue: queue.Queue = queue.Queue()
        self.running_job = False

    def request(self, fn) -> bool:
        if self.running_job:
            return False
        self.running_job = True
        self._queue.put(fn)
        if not self.isRunning():
            self.start()
        return True

    def run(self) -> None:
        while True:
            fn = self._queue.get()
            if fn is None:
                return
            try:
                self.done.emit(("ok", fn()))
            except Exception as exc:
                self.done.emit(("err", str(exc)))

    def stop(self) -> None:
        self._queue.put(None)


class WarningWindow(QWidget):
    """Small topmost notice. It does not take keyboard focus."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.Window
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setWindowTitle("黑名单玩家")
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)
        layout = QVBoxLayout(self)
        title = QLabel("黑名单玩家")
        title.setObjectName("warnTitle")
        layout.addWidget(title)
        self.body = QPlainTextEdit()
        self.body.setReadOnly(True)
        self.body.setFocusPolicy(Qt.NoFocus)
        self.body.setMinimumWidth(420)
        layout.addWidget(self.body)
        close = QPushButton("关闭")
        close.setFocusPolicy(Qt.NoFocus)
        close.clicked.connect(self.close)
        layout.addWidget(close)
        family = chinese_family()
        self.setFont(chinese_font())
        self.body.setFont(chinese_font(12))
        self.setStyleSheet(
            f"""
            QWidget {{ background: #2a120f; color: #f8efe6; font-family: "{family}"; }}
            QLabel#warnTitle {{ color: #f0c36a; font-family: "{family}"; font-size: 16px; font-weight: 600; }}
            QPlainTextEdit {{ background: #3a1a16; color: #f8efe6; border: 1px solid #8a4034; font-family: "{family}"; font-size: 14px; }}
            QPushButton {{ background: #8c3b2a; color: #fff8f4; padding: 6px 12px; font-family: "{family}"; }}
            """
        )

    def present(self, lines: list[str]) -> None:
        self.body.setPlainText("\n".join(lines))
        self.adjustSize()
        screen = QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.move(area.right() - self.width() - 28, area.top() + 28)
        self.show()
        self._pin_without_focus()

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        self._pin_without_focus()

    def _pin_without_focus(self) -> None:
        if sys.platform != "win32":
            return
        import ctypes

        hwnd = int(self.winId())
        HWND_TOPMOST = -1
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOACTIVATE = 0x0010
        SWP_SHOWWINDOW = 0x0040
        ctypes.windll.user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("黑名单检测")
        self.setWindowIcon(_icon())
        self.resize(880, 520)
        self.store = Store()
        self.hotkey = GlobalHotkey(self.check_now)
        self.worker = CheckWorker()
        self.worker.done.connect(self._on_checked)
        self._closing = False
        self.warning = WarningWindow()
        self._check_started: float | None = None
        self._release_foreground = False
        self._build()
        self._apply_style()
        self._reload_table()
        self._reload_history()
        self._restore_hotkey()
        self._set_tray("黑名单检测")
        notice = self.store.load_warning or capture_capability_message()
        if notice:
            self.result_label.setText(notice)

    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(12, 8, 12, 12)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._match_page(), "本局")
        self.history_tab = self.tabs.addTab(self._history_page(), "记录")
        self.blacklist_tab = self.tabs.addTab(self._list_page(), "黑名单")
        self.tabs.addTab(self._settings_page(), "设置")
        outer.addWidget(self.tabs)

        self.names_view = QPlainTextEdit()
        self.names_view.hide()

        self.tray = None
        if QSystemTrayIcon_available():
            from PySide6.QtWidgets import QSystemTrayIcon

            self.tray = QSystemTrayIcon(_icon(), self)
            self.tray.setToolTip("黑名单检测")
            self.tray.show()

    def _seat(self, number: int) -> QFrame:
        frame = QFrame()
        frame.setObjectName("seat")
        frame.setMinimumHeight(84)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        layout.addStretch(1)
        number_label = QLabel(str(number))
        number_label.setObjectName("seatNo")
        number_label.setAlignment(Qt.AlignCenter)
        name = QLabel("—")
        name.setObjectName("seatName")
        name.setAlignment(Qt.AlignCenter)
        name.setWordWrap(True)
        name.setFont(chinese_font(13))
        layout.addWidget(number_label)
        layout.addWidget(name)
        layout.addStretch(1)
        frame.seat_name = name  # type: ignore[attr-defined]
        return frame

    def _match_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 12, 4, 4)
        layout.setSpacing(12)

        board = QWidget()
        board.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        grid = QGridLayout(board)
        grid.setSpacing(8)
        self.seats: list[QFrame] = []
        for index in range(12):
            tile = self._seat(index + 1)
            self.seats.append(tile)
            grid.addWidget(tile, 0 if index < 6 else 1, index % 6)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        layout.addWidget(board, 1)

        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        self.result_label.setObjectName("sub")
        layout.addWidget(self.result_label)

        bar = QHBoxLayout()
        self.time_label = QLabel("—")
        self.time_label.setObjectName("sub")
        self.copy_button = QPushButton("复制")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_result)
        self.open_button = QPushButton("图片")
        self.open_button.clicked.connect(self.open_screenshot)
        self.check_button = QPushButton("检查本局")
        self.check_button.setObjectName("primary")
        self.check_button.clicked.connect(self.check_now)
        bar.addWidget(self.time_label)
        bar.addStretch(1)
        bar.addWidget(self.copy_button)
        bar.addWidget(self.open_button)
        bar.addWidget(self.check_button)
        layout.addLayout(bar)
        return page

    def _list_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 12, 4, 4)
        layout.setSpacing(10)
        row = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("玩家名字")
        self.name_edit.returnPressed.connect(self.add_entry)
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("备注")
        self.note_edit.returnPressed.connect(self.add_entry)
        add = QPushButton("添加")
        add.setObjectName("primary")
        add.clicked.connect(self.add_entry)
        row.addWidget(self.name_edit, 2)
        row.addWidget(self.note_edit, 1)
        row.addWidget(add)
        layout.addLayout(row)
        self.list_label = QLabel("")
        self.list_label.setObjectName("sub")
        self.list_label.hide()
        layout.addWidget(self.list_label)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["名字", "备注", "删除"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, self.table.horizontalHeader().ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, self.table.horizontalHeader().ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, self.table.horizontalHeader().ResizeMode.Fixed)
        self.table.setColumnWidth(2, 88)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setShowGrid(False)
        self.table.cellClicked.connect(self._on_list_cell)
        layout.addWidget(self.table, 1)
        self.empty_label = QLabel("没有名字")
        self.empty_label.setObjectName("sub")
        self.empty_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.empty_label, 1)
        return page

    def _history_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(4, 12, 4, 4)
        layout.setSpacing(10)
        self.history_list = QListWidget()
        self.history_list.setFixedWidth(168)
        self.history_list.currentRowChanged.connect(self._show_history_scan)
        layout.addWidget(self.history_list)
        names = QVBoxLayout()
        self.history_table = QTableWidget(0, 3)
        self.history_table.setHorizontalHeaderLabels(["座位", "名字", ""])
        self.history_table.horizontalHeader().setStretchLastSection(False)
        self.history_table.horizontalHeader().setSectionResizeMode(0, self.history_table.horizontalHeader().ResizeMode.Fixed)
        self.history_table.horizontalHeader().setSectionResizeMode(1, self.history_table.horizontalHeader().ResizeMode.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(2, self.history_table.horizontalHeader().ResizeMode.Fixed)
        self.history_table.setColumnWidth(0, 64)
        self.history_table.setColumnWidth(2, 96)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.verticalHeader().setDefaultSectionSize(36)
        self.history_table.setSelectionMode(QTableWidget.NoSelection)
        self.history_table.setShowGrid(False)
        self.history_table.cellClicked.connect(self._on_history_cell)
        names.addWidget(self.history_table, 1)
        layout.addLayout(names, 1)
        self.history_empty = QLabel("没有记录")
        self.history_empty.setObjectName("sub")
        self.history_empty.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.history_empty, 1)
        return page

    def _settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 16, 4, 4)
        layout.setSpacing(12)
        layout.addWidget(QLabel("热键"))
        row = QHBoxLayout()
        self.hotkey_edit = QLineEdit()
        self.hotkey_edit.setReadOnly(True)
        self.hotkey_edit.setPlaceholderText("无")
        set_key = QPushButton("设置")
        set_key.clicked.connect(self.choose_hotkey)
        clear_key = QPushButton("清除")
        clear_key.clicked.connect(self.clear_hotkey)
        row.addWidget(self.hotkey_edit, 1)
        row.addWidget(set_key)
        row.addWidget(clear_key)
        layout.addLayout(row)
        self.mute_box = QCheckBox("静音")
        self.mute_box.setChecked(self.store.muted)
        self.mute_box.toggled.connect(self._toggle_mute)
        layout.addWidget(self.mute_box)
        self.settings_label = QLabel("")
        self.settings_label.setObjectName("sub")
        self.settings_label.setWordWrap(True)
        layout.addWidget(self.settings_label)
        layout.addStretch(1)
        return page

    def _apply_style(self) -> None:
        family = chinese_family()
        self.setFont(chinese_font())
        self.setStyleSheet(
            f"""
            QWidget#root, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QCheckBox,
            QTabWidget, QTabBar, QListWidget, QTableWidget, QHeaderView, QTableWidget QWidget {{
                font-family: "{family}";
            }}
            QWidget#root, QTabWidget::pane {{ background: #1a1916; color: #f3efe6; border: none; }}
            QTabBar::tab {{
                font-family: "{family}";
                font-size: 14px;
                color: #9c9386;
                background: transparent;
                border: none;
                border-bottom: 2px solid transparent;
                padding: 8px 18px;
                margin-right: 4px;
            }}
            QTabBar::tab:selected {{
                color: #f6f1e6;
                border-bottom: 2px solid #c6a15a;
            }}
            QTabBar::tab:hover {{ color: #f6f1e6; }}
            QLabel#sub {{ font-family: "{family}"; color: #b7ad9e; }}
            QFrame#seat, QFrame#hit {{
                background: #24221e;
                border: 1px solid #3c372f;
                border-radius: 8px;
                min-height: 64px;
            }}
            QFrame#hit {{
                background: #3a1a16;
                border: 1px solid #d2644a;
            }}
            QLabel#seatNo {{ font-family: "{family}"; font-size: 12px; color: #9c9386; }}
            QLabel#seatName {{ font-family: "{family}"; font-size: 15px; color: #f6f1e6; }}
            QFrame#hit QLabel#seatName {{ font-family: "{family}"; color: #ffd7cc; }}
            QLineEdit, QPlainTextEdit, QTableWidget, QListWidget {{
                background: #24221e;
                color: #f3efe6;
                border: 1px solid #3c372f;
                border-radius: 4px;
                padding: 4px;
            }}
            QListWidget::item {{
                font-family: "{family}";
                padding: 8px 6px;
                border: none;
            }}
            QListWidget::item:selected {{
                background: #3a342c;
                color: #f6f1e6;
            }}
            QHeaderView::section {{
                background: #2c2924;
                color: #e6dccb;
                border: none;
                padding: 4px;
            }}
            QPushButton {{
                background: #3a342c;
                color: #f3efe6;
                border: 1px solid #5c5346;
                border-radius: 4px;
                padding: 6px 12px;
            }}
            QPushButton#primary {{ background: #8c6a1f; border-color: #c6a15a; color: #fff8e8; }}
            QCheckBox {{ spacing: 8px; }}
            """
        )

    def _reload_table(self) -> None:
        self.table.setRowCount(len(self.store.entries))
        for row, entry in enumerate(self.store.entries):
            name = QTableWidgetItem(entry.name)
            name.setFlags(name.flags() & ~Qt.ItemIsEditable)
            name.setFont(chinese_font())
            note = QTableWidgetItem(entry.note)
            note.setFlags(note.flags() & ~Qt.ItemIsEditable)
            note.setFont(chinese_font())
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, note)
            remove = QTableWidgetItem("删除")
            remove.setFlags(remove.flags() & ~Qt.ItemIsEditable)
            remove.setTextAlignment(Qt.AlignCenter)
            remove.setForeground(QColor("#e7b2a6"))
            remove.setFont(chinese_font())
            self.table.setItem(row, 2, remove)
            self.table.setRowHeight(row, 36)
        count = len(self.store.entries)
        self.table.setVisible(count > 0)
        self.empty_label.setVisible(count == 0)
        self.tabs.setTabText(self.blacklist_tab, f"黑名单  {count}" if count else "黑名单")

    def _reload_history(self) -> None:
        self.history_list.blockSignals(True)
        self.history_list.clear()
        for scan in self.store.scans:
            self.history_list.addItem(self._scan_title(str(scan.get("at", ""))))
        count = len(self.store.scans)
        self.history_list.setVisible(count > 0)
        self.history_table.setVisible(count > 0)
        self.history_empty.setVisible(count == 0)
        self.tabs.setTabText(self.history_tab, f"记录  {count}" if count else "记录")
        if count:
            self.history_list.setCurrentRow(0)
        self.history_list.blockSignals(False)
        self._show_history_scan(0 if count else -1)

    def _scan_title(self, stamp: str) -> str:
        try:
            moment = datetime.fromisoformat(stamp)
        except ValueError:
            return stamp
        return moment.strftime("%m-%d %H:%M:%S")

    def _show_history_scan(self, row: int) -> None:
        self.history_table.setRowCount(0)
        if row < 0 or row >= len(self.store.scans):
            return
        names = self.store.scans[row].get("names", [])
        self.history_table.setRowCount(len(names))
        for index, seat in enumerate(names):
            unclear = bool(seat.get("unclear")) or not str(seat.get("name") or "")
            shown = "未看清" if unclear else str(seat.get("name"))
            seat_item = QTableWidgetItem(f"{seat.get('seat')}号")
            seat_item.setFlags(seat_item.flags() & ~Qt.ItemIsEditable)
            seat_item.setFont(chinese_font())
            name_item = QTableWidgetItem(shown)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            name_item.setFont(chinese_font())
            if unclear:
                action = ""
            elif self.store.contains_name(shown):
                action = "已在名单"
            else:
                action = "加入"
            action_item = QTableWidgetItem(action)
            action_item.setFlags(action_item.flags() & ~Qt.ItemIsEditable)
            action_item.setTextAlignment(Qt.AlignCenter)
            action_item.setFont(chinese_font())
            action_item.setForeground(QColor("#e6c27a" if action == "加入" else "#9c9386"))
            self.history_table.setItem(index, 0, seat_item)
            self.history_table.setItem(index, 1, name_item)
            self.history_table.setItem(index, 2, action_item)
            self.history_table.setRowHeight(index, 36)

    def _on_history_cell(self, row: int, column: int) -> None:
        if column != 2:
            return
        action = self.history_table.item(row, 2)
        name = self.history_table.item(row, 1)
        if action is None or name is None or action.text() != "加入":
            return
        if self.store.add(name.text()) is None:
            return
        self._reload_table()
        self._show_history_scan(self.history_list.currentRow())

    def add_entry(self) -> None:
        entry = self.store.add(self.name_edit.text(), self.note_edit.text())
        if entry is None:
            self.list_label.setText("请填写名字。")
            self.list_label.show()
            return
        self.list_label.hide()
        self.list_label.clear()
        self.name_edit.clear()
        self.note_edit.clear()
        self._reload_table()
        self._show_history_scan(self.history_list.currentRow())

    def _on_list_cell(self, row: int, column: int) -> None:
        if column == 2:
            self._remove(row)

    def _remove(self, index: int) -> None:
        self.store.remove_at(index)
        self._reload_table()
        self._show_history_scan(self.history_list.currentRow())

    def _toggle_mute(self, checked: bool) -> None:
        self.store.muted = bool(checked)
        self.store.save_settings()

    def choose_hotkey(self) -> None:
        dialog = HotkeyDialog(self)
        if dialog.exec() != QDialog.Accepted or dialog.spec is None:
            return
        spec = dialog.spec
        registered = self.hotkey.apply(spec)
        self.store.hotkey = spec.display
        self.store.save_settings()
        self.hotkey_edit.setText(spec.display)
        if registered:
            self.settings_label.setText(spec.display)
        elif sys.platform != "win32":
            self.settings_label.setText("这台电脑不能用热键。")
        else:
            self.store.hotkey = ""
            self.store.save_settings()
            self.hotkey_edit.clear()
            self.settings_label.setText("换一个热键。")

    def clear_hotkey(self) -> None:
        self.hotkey.clear()
        self.store.hotkey = ""
        self.store.save_settings()
        self.hotkey_edit.clear()
        self.settings_label.setText("已清除。")

    def _restore_hotkey(self) -> None:
        spec = parse_hotkey(self.store.hotkey)
        if spec is None:
            self.hotkey_edit.clear()
            return
        self.hotkey_edit.setText(spec.display)
        self.hotkey.apply(spec)

    def check_now(self) -> None:
        self._release_foreground = True
        lock_foreground(True)
        self._start(self._capture_job)

    def open_screenshot(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            str(Path.home()),
            "图片 (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if not path:
            return
        self._start(lambda: check_image(path, list(self.store.entries)))

    def _capture_job(self) -> CheckResult:
        frames = capture_displays()
        return check_frames(frames, list(self.store.entries))

    def _start(self, fn) -> None:
        self.tabs.setCurrentIndex(0)
        if not self.worker.request(fn):
            self.result_label.setText("正在检查。")
            self._unlock_foreground()
            return
        self._check_started = time.perf_counter()
        self.result_label.setText("正在检查。")
        self.check_button.setEnabled(False)
        self.open_button.setEnabled(False)

    def _unlock_foreground(self) -> None:
        if not self._release_foreground:
            return
        self._release_foreground = False
        lock_foreground(False)

    def _on_checked(self, payload) -> None:
        self.worker.running_job = False
        self._unlock_foreground()
        if self._closing:
            return
        self.check_button.setEnabled(True)
        self.open_button.setEnabled(True)
        elapsed = None
        if self._check_started is not None:
            elapsed = time.perf_counter() - self._check_started
            self._check_started = None
        self._show_elapsed(elapsed)
        kind, value = payload
        if kind == "err":
            text = str(value)
            if isinstance(value, str) and "DXGI" not in text and "dxcam" not in text and "截" not in text:
                pass
            self.result_label.setText(text)
            self._set_tray(text)
            return
        result: CheckResult = value
        brief = self._brief(result)
        self.result_label.setText(brief)
        self._set_tray(brief or "黑名单检测")
        self._show_result(result)
        if result.header_found and result.names:
            self.store.add_scan(
                [
                    {
                        "seat": seat_number(slot.index),
                        "name": "" if slot.unclear else slot.visible,
                        "unclear": slot.unclear,
                    }
                    for slot in result.names
                ],
                elapsed,
            )
            self._reload_history()
        if result.header_found and result.hits:
            self.warning.present([hit.line for hit in result.hits])
            if not self.store.muted:
                try:
                    play_chime(chime_path(self.store.root))
                except Exception:
                    self.result_label.setText("提示音没响。")
        if self.store.save_debug_frames and result.preview_rgb is not None:
            self._save_debug(result)

    def _show_result(self, result: CheckResult) -> None:
        hits = {hit.index for hit in result.hits}
        lines = []
        for tile in self.seats:
            tile.seat_name.setText("—")  # type: ignore[attr-defined]
            self._mark_seat(tile, False)
        for slot in result.names:
            seat = seat_number(slot.index)
            text = "未看清" if slot.unclear else slot.visible
            lines.append(f"{seat}号  {text}")
            tile = self.seats[slot.index]
            tile.seat_name.setText(text)  # type: ignore[attr-defined]
            self._mark_seat(tile, slot.index in hits)
        self.names_view.setPlainText("\n".join(lines))
        self.copy_button.setEnabled(bool(lines))

    def _brief(self, result: CheckResult) -> str:
        if not result.header_found:
            return result.message
        parts: list[str] = []
        if result.hits:
            parts.append(f"{len(result.hits)} 人在名单里")
        unclear = sum(1 for slot in result.names if slot.unclear)
        if unclear:
            parts.append(f"{unclear} 人没看清")
        return "，".join(parts)

    def _mark_seat(self, tile: QFrame, hit: bool) -> None:
        tile.setObjectName("hit" if hit else "seat")
        tile.style().unpolish(tile)
        tile.style().polish(tile)

    def _show_elapsed(self, elapsed: float | None) -> None:
        if elapsed is None:
            self.time_label.setText("—")
            return
        shown = f"{elapsed:.2f}" if elapsed < 10 else f"{elapsed:.1f}"
        self.time_label.setText(f"{shown} 秒")

    def copy_result(self) -> None:
        text = self.names_view.toPlainText().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
        self.result_label.setText("已复制。")

    def _save_debug(self, result: CheckResult) -> None:
        directory = self.store.root / "debug"
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = directory / f"{stamp}.png"
        from PIL import Image

        image = Image.fromarray(result.preview_rgb)
        image.save(path)

    def _set_tray(self, text: str) -> None:
        if self.tray is not None:
            self.tray.setToolTip(text[:120])

    def closeEvent(self, event) -> None:  # noqa: ANN001
        self._closing = True
        self.warning.close()
        self.hotkey.clear()
        self.worker.stop()
        self.worker.wait(1500)
        super().closeEvent(event)


def QSystemTrayIcon_available() -> bool:
    try:
        from PySide6.QtWidgets import QSystemTrayIcon

        return QSystemTrayIcon.isSystemTrayAvailable()
    except Exception:
        return False
