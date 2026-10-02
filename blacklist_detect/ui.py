"""Main window, tray status, and the always-on-top warning."""

from __future__ import annotations

import queue
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
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
    capture_top_band,
    lock_foreground,
    virtual_origin,
)
from blacklist_detect.hotkey import GlobalHotkey, parse_hotkey
from blacklist_detect.match import seat_number
from blacklist_detect.pipeline import CheckResult, check_frames, check_image, glance_title
from blacklist_detect.sound import chime_path, play_chime
from blacklist_detect.storage import Store, reason_text
from blacklist_detect.watch import GLANCE_INTERVAL_MS, LobbyWatch


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


# One inset for the whole window. Pages share the same gap so the tabs line up.
PAD = 16
GAP = 12


def _page(layout) -> None:
    layout.setContentsMargins(0, GAP, 0, 0)
    layout.setSpacing(GAP)


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
        layout.setContentsMargins(PAD, PAD, PAD, PAD)
        layout.setSpacing(GAP)
        layout.addWidget(QLabel("按下要使用的热键。可以加上 Ctrl、Alt 或 Shift。"))
        self.hint = QLabel("等待按键。")
        self.setFont(chinese_font())
        layout.addWidget(self.hint)

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


class AddNameDialog(QDialog):
    """One player. Reasons are 炸房, 贴脸, and 其他, and more than one can be checked."""

    def __init__(
        self,
        name: str = "",
        reasons: tuple[str, ...] = (),
        detail: str = "",
        title: str = "添加",
        allow_delete: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.name = name
        self.reasons: tuple[str, ...] = tuple(reasons)
        self.detail = detail
        self.deleted = False
        self.setFont(chinese_font())
        family = chinese_family()
        self.setStyleSheet(
            f"""
            QDialog, QLabel, QLineEdit, QPushButton, QCheckBox {{
                font-family: "{family}";
                background: #1a1916;
                color: #f3efe6;
            }}
            QLineEdit {{
                background: #24221e;
                border: 1px solid #3c372f;
                border-radius: 4px;
                padding: 6px;
            }}
            QCheckBox {{ background: transparent; spacing: 8px; }}
            QPushButton {{
                background: #3a342c;
                border: 1px solid #5c5346;
                border-radius: 4px;
                padding: 6px 12px;
            }}
            QPushButton#primary {{ background: #8c6a1f; border-color: #c6a15a; color: #fff8e8; }}
            QPushButton#danger {{ color: #e7b2a6; }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAD, PAD, PAD, PAD)
        layout.setSpacing(GAP)
        layout.addWidget(QLabel("名字"))
        self.name_edit = QLineEdit(name)
        layout.addWidget(self.name_edit)
        layout.addWidget(QLabel("原因"))
        from blacklist_detect.storage import REASON_TAGS

        self.boxes: dict[str, QCheckBox] = {}
        for tag in REASON_TAGS:
            box = QCheckBox(tag)
            box.setChecked(tag in reasons)
            self.boxes[tag] = box
            layout.addWidget(box)
        self.detail_edit = QLineEdit(detail)
        self.detail_edit.setPlaceholderText("补充说明")
        layout.addWidget(self.detail_edit)
        self.boxes["其他"].toggled.connect(self.detail_edit.setVisible)
        self.detail_edit.setVisible("其他" in reasons)
        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        remove = None
        if allow_delete:
            remove = QPushButton("删除")
            remove.setObjectName("danger")
            remove.setAutoDefault(False)
            remove.setDefault(False)
            remove.clicked.connect(self._delete)
            buttons.addWidget(remove)
        buttons.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setAutoDefault(False)
        cancel.setDefault(False)
        cancel.clicked.connect(self.reject)
        confirm = QPushButton("保存" if allow_delete else "添加")
        confirm.setObjectName("primary")
        confirm.setAutoDefault(True)
        confirm.setDefault(True)
        confirm.clicked.connect(self._accept)
        buttons.addWidget(cancel)
        buttons.addWidget(confirm)
        layout.addLayout(buttons)
        self.setMinimumWidth(420)
        self.name_edit.returnPressed.connect(self._accept)
        self.detail_edit.returnPressed.connect(self._accept)

    def _chosen(self) -> tuple[str, ...]:
        from blacklist_detect.storage import REASON_TAGS

        return tuple(tag for tag in REASON_TAGS if self.boxes[tag].isChecked())

    def _accept(self) -> None:
        if not self.name_edit.text().strip():
            return
        self.name = self.name_edit.text()
        self.reasons = self._chosen()
        self.detail = self.detail_edit.text() if "其他" in self.reasons else ""
        self.deleted = False
        self.accept()

    def _delete(self) -> None:
        self.deleted = True
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
    placed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._queue: queue.Queue = queue.Queue()
        self.running_job = False

    def request(self, fn, kind: str = "check") -> bool:
        if self.running_job:
            return False
        self.running_job = True
        self._queue.put((kind, fn))
        if not self.isRunning():
            self.start()
        return True

    def run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            kind, fn = item
            try:
                self.done.emit((kind, "ok", fn()))
            except Exception as exc:
                self.done.emit((kind, "err", str(exc)))

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
        layout.setContentsMargins(PAD, PAD, PAD, PAD)
        layout.setSpacing(GAP)
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
        _pin_topmost(self)


def _pin_topmost(widget) -> None:
    if sys.platform != "win32":
        return
    import ctypes

    hwnd = int(widget.winId())
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


class ClearWindow(QWidget):
    """Topmost green notice when the lobby has nobody on the blacklist."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.Window
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setWindowTitle("没有发现黑名单")
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAD, PAD, PAD, PAD)
        layout.setSpacing(GAP)
        title = QLabel("没有发现黑名单")
        title.setObjectName("clearTitle")
        layout.addWidget(title)
        self.detail = QLabel("本局没有黑名单玩家。")
        self.detail.setObjectName("clearDetail")
        self.detail.setWordWrap(True)
        self.detail.setMinimumWidth(360)
        layout.addWidget(self.detail)
        close = QPushButton("关闭")
        close.setFocusPolicy(Qt.NoFocus)
        close.clicked.connect(self.close)
        layout.addWidget(close, 0, Qt.AlignLeft)
        family = chinese_family()
        self.setFont(chinese_font())
        self.setStyleSheet(
            f"""
            QWidget {{ background: #102218; color: #e7f6ec; font-family: "{family}"; }}
            QLabel#clearTitle {{ color: #7dce8a; font-family: "{family}"; font-size: 18px; font-weight: 600; }}
            QLabel#clearDetail {{ color: #e7f6ec; font-family: "{family}"; font-size: 15px; }}
            QPushButton {{ background: #2f6b45; color: #f4fff6; padding: 8px 16px; font-family: "{family}"; }}
            """
        )

    def present(self, detail: str) -> None:
        self.detail.setText(detail)
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
        _pin_topmost(self)


class LobbyPanel(QWidget):
    """Draggable color block. The first open sits beside 准备案件还原."""

    moved = Signal(int, int)

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.Window
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.OpenHandCursor)
        self.mode = ""
        self._drag_offset = None
        self._drag_moved = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel("")
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setMinimumWidth(168)
        self.label.setMaximumWidth(320)
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.label)
        self.setFont(chinese_font(14))
        self.label.setFont(chinese_font(14))

    def set_mode(self, mode: str, text: str) -> None:
        tones = {
            "checking": ("#d06a14", "#fff8f0"),
            "clear": ("#1e8a4a", "#f4fff7"),
            "hit": ("#b33a2e", "#fff6f4"),
        }
        background, color = tones[mode]
        self.mode = mode
        self.label.setText(text)
        self.label.setAlignment(Qt.AlignVCenter | (Qt.AlignLeft if mode == "hit" else Qt.AlignCenter))
        family = chinese_family()
        self.setStyleSheet(
            f"""
            QLabel {{
                background: {background};
                color: {color};
                font-family: "{family}";
                font-size: 15px;
                padding: 12px 16px;
                border-radius: 8px;
            }}
            """
        )
        self.adjustSize()

    def show_at(self, x: int, y: int, mode: str, text: str) -> None:
        self.set_mode(mode, text)
        self.move(int(x), int(y))
        self.show()
        _pin_topmost(self)

    def show_beside(
        self,
        right: float,
        top: float,
        bottom: float,
        mode: str,
        text: str,
    ) -> None:
        self.set_mode(mode, text)
        gap = 16
        x = int(round(right + gap))
        y = int(round(top + ((bottom - top) - self.height()) / 2))
        screen = QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            if y + self.height() > area.bottom() - 8:
                y = area.bottom() - self.height() - 8
            if x + self.width() > area.right() - 8:
                x = max(area.left() + 8, area.right() - self.width() - 8)
            y = max(area.top() + 8, y)
        self.move(x, y)
        self.show()
        _pin_topmost(self)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _pin_topmost(self)

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
            self._drag_moved = False
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: ANN001
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            self._drag_moved = True
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.LeftButton and self._drag_offset is not None:
            self._drag_offset = None
            self.setCursor(Qt.OpenHandCursor)
            if self._drag_moved:
                self._drag_moved = False
                self.moved.emit(self.x(), self.y())
            event.accept()
            return
        super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("黑名单检测")
        self.setWindowIcon(_icon())
        self.setFixedSize(900, 560)
        self.store = Store()
        self.hotkey = GlobalHotkey(self.check_now)
        self.worker = CheckWorker()
        self.worker.done.connect(self._on_worker)
        self.worker.placed.connect(self._on_lobby_placed)
        self.watch = LobbyWatch()
        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(GLANCE_INTERVAL_MS)
        self._watch_timer.timeout.connect(self._auto_tick)
        self._closing = False
        self.warning = WarningWindow()
        self.clear_notice = ClearWindow()
        self.panel = LobbyPanel()
        self.panel.moved.connect(self._save_panel_pos)
        self._panel_hide_timer = QTimer(self)
        self._panel_hide_timer.setSingleShot(True)
        self._panel_hide_timer.timeout.connect(self._hide_panel_after_title)
        self._live_check = False
        self._check_started: float | None = None
        self._release_foreground = False
        self._build()
        self._apply_style()
        self._show_list()
        self._reload_history()
        self._restore_hotkey()
        if self.store.auto_capture:
            self._watch_timer.start()
        self._set_tray("黑名单检测")
        notice = self.store.load_warning or capture_capability_message()
        if notice:
            self._set_result(notice)

    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(PAD, PAD, PAD, PAD)
        outer.setSpacing(0)

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
        layout.setContentsMargins(GAP, GAP, GAP, GAP)
        layout.setSpacing(8)
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
        _page(layout)

        board = QWidget()
        board.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        grid = QGridLayout(board)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(GAP)
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
        bar.setSpacing(GAP)
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
        _page(layout)
        add = QPushButton("添加")
        add.setObjectName("primary")
        add.clicked.connect(self._add_by_dialog)
        layout.addWidget(add, 0, Qt.AlignLeft)
        self.blacklist_table = QTableWidget(0, 2)
        self.blacklist_table.setHorizontalHeaderLabels(["名字", "原因"])
        self.blacklist_table.horizontalHeader().setStretchLastSection(True)
        self.blacklist_table.horizontalHeader().setSectionResizeMode(0, self.blacklist_table.horizontalHeader().ResizeMode.Stretch)
        self.blacklist_table.horizontalHeader().setSectionResizeMode(1, self.blacklist_table.horizontalHeader().ResizeMode.Stretch)
        self.blacklist_table.verticalHeader().setVisible(False)
        self.blacklist_table.verticalHeader().setDefaultSectionSize(40)
        self.blacklist_table.setSelectionMode(QTableWidget.SingleSelection)
        self.blacklist_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.blacklist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.blacklist_table.setShowGrid(False)
        self.blacklist_table.setCursor(Qt.PointingHandCursor)
        self.blacklist_table.cellClicked.connect(self._edit_row)
        layout.addWidget(self.blacklist_table, 1)
        return page

    def _history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        _page(layout)
        actions = QHBoxLayout()
        actions.setSpacing(GAP)
        actions.addStretch(1)
        self.history_delete = QPushButton("删除")
        self.history_delete.clicked.connect(self._delete_history)
        self.history_clear = QPushButton("清空")
        self.history_clear.clicked.connect(self._clear_history)
        actions.addWidget(self.history_delete)
        actions.addWidget(self.history_clear)
        layout.addLayout(actions)
        body = QHBoxLayout()
        body.setSpacing(GAP)
        self.history_list = QListWidget()
        self.history_list.setFixedWidth(168)
        self.history_list.currentRowChanged.connect(self._show_history_scan)
        body.addWidget(self.history_list)
        self.history_table = QTableWidget(0, 3)
        self.history_table.setHorizontalHeaderLabels(["座位", "名字", ""])
        self.history_table.horizontalHeader().setStretchLastSection(False)
        self.history_table.horizontalHeader().setSectionResizeMode(0, self.history_table.horizontalHeader().ResizeMode.Fixed)
        self.history_table.horizontalHeader().setSectionResizeMode(1, self.history_table.horizontalHeader().ResizeMode.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(2, self.history_table.horizontalHeader().ResizeMode.Fixed)
        self.history_table.setColumnWidth(0, 64)
        self.history_table.setColumnWidth(2, 96)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.verticalHeader().setDefaultSectionSize(40)
        self.history_table.setSelectionMode(QTableWidget.NoSelection)
        self.history_table.setShowGrid(False)
        self.history_table.cellClicked.connect(self._on_history_cell)
        body.addWidget(self.history_table, 1)
        self.history_empty = QLabel("没有记录")
        self.history_empty.setObjectName("sub")
        self.history_empty.setAlignment(Qt.AlignCenter)
        body.addWidget(self.history_empty, 1)
        layout.addLayout(body, 1)
        return page

    def _settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        _page(layout)
        layout.addWidget(QLabel("热键"))
        row = QHBoxLayout()
        row.setSpacing(GAP)
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
        self.auto_box = QCheckBox("看到推演成功时自动检查")
        self.auto_box.setChecked(self.store.auto_capture)
        self.auto_box.toggled.connect(self._toggle_auto)
        layout.addWidget(self.auto_box)
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
            QWidget#root, QTabWidget::pane {{ background: #1a1916; color: #f3efe6; border: none; padding: 0; margin: 0; }}
            QTabBar::tab {{
                font-family: "{family}";
                font-size: 14px;
                color: #9c9386;
                background: transparent;
                border: none;
                border-bottom: 2px solid transparent;
                padding: 8px 16px;
                margin-right: 8px;
            }}
            QTabBar::tab:selected {{
                color: #f6f1e6;
                border-bottom: 2px solid #c6a15a;
            }}
            QTabBar::tab:hover {{ color: #f6f1e6; }}
            QLabel#sub {{ font-family: "{family}"; color: #b7ad9e; }}
            QLabel#clear {{ font-family: "{family}"; font-size: 16px; color: #7dce8a; }}
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
                padding: 8px 12px;
            }}
            QListWidget::item {{
                font-family: "{family}";
                padding: 8px 12px;
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
                padding: 8px 12px;
            }}
            QPushButton {{
                background: #3a342c;
                color: #f3efe6;
                border: 1px solid #5c5346;
                border-radius: 4px;
                padding: 8px 16px;
            }}
            QPushButton#primary {{ background: #8c6a1f; border-color: #c6a15a; color: #fff8e8; }}
            QCheckBox {{ spacing: 8px; }}
            """
        )

    def _show_list(self) -> None:
        self.blacklist_table.setRowCount(len(self.store.entries))
        for index, entry in enumerate(self.store.entries):
            name = QTableWidgetItem(entry.name)
            name.setFlags(name.flags() & ~Qt.ItemIsEditable)
            name.setFont(chinese_font())
            reason = QTableWidgetItem(reason_text(entry))
            reason.setFlags(reason.flags() & ~Qt.ItemIsEditable)
            reason.setFont(chinese_font())
            self.blacklist_table.setItem(index, 0, name)
            self.blacklist_table.setItem(index, 1, reason)
            self.blacklist_table.setRowHeight(index, 40)
        self._refresh_blacklist_tab()

    def _refresh_blacklist_tab(self) -> None:
        count = len(self.store.entries)
        self.tabs.setTabText(self.blacklist_tab, f"黑名单  {count}" if count else "黑名单")

    def _add_by_dialog(self) -> None:
        dialog = AddNameDialog(parent=self)
        if dialog.exec() != QDialog.Accepted or dialog.deleted:
            return
        if self.store.add(dialog.name, dialog.detail, reasons=dialog.reasons) is None:
            return
        self._show_list()
        self._show_history_scan(self.history_list.currentRow())

    def _edit_row(self, row: int, _column: int = 0) -> None:
        if not 0 <= row < len(self.store.entries):
            return
        entry = self.store.entries[row]
        dialog = AddNameDialog(entry.name, entry.reasons, entry.note, title="修改", allow_delete=True, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        if dialog.deleted:
            self.store.remove_at(row)
        else:
            self.store.update_at(row, dialog.name, dialog.reasons, dialog.detail)
        self._show_list()
        self._show_history_scan(self.history_list.currentRow())

    def _reload_history(self, select: int = 0) -> None:
        self.history_list.blockSignals(True)
        self.history_list.clear()
        for scan in self.store.scans:
            self.history_list.addItem(self._scan_title(str(scan.get("at", ""))))
        count = len(self.store.scans)
        self.history_list.setVisible(count > 0)
        self.history_table.setVisible(count > 0)
        self.history_delete.setVisible(count > 0)
        self.history_clear.setVisible(count > 0)
        self.history_empty.setVisible(count == 0)
        self.tabs.setTabText(self.history_tab, f"记录  {count}" if count else "记录")
        chosen = -1
        if count:
            chosen = max(0, min(select, count - 1))
            self.history_list.setCurrentRow(chosen)
        self.history_list.blockSignals(False)
        self._show_history_scan(chosen)

    def _delete_history(self) -> None:
        row = self.history_list.currentRow()
        self.store.remove_scan(row)
        self._reload_history(row)

    def _clear_history(self) -> None:
        self.store.clear_scans()
        self._reload_history()

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
            self.history_table.setRowHeight(index, 40)

    def _on_history_cell(self, row: int, column: int) -> None:
        if column != 2:
            return
        action = self.history_table.item(row, 2)
        name = self.history_table.item(row, 1)
        if action is None or name is None or action.text() != "加入":
            return
        if self.store.add(name.text()) is None:
            return
        self._show_list()
        self._show_history_scan(self.history_list.currentRow())

    def _toggle_mute(self, checked: bool) -> None:
        self.store.muted = bool(checked)
        self.store.save_settings()

    def _toggle_auto(self, checked: bool) -> None:
        self.store.auto_capture = bool(checked)
        self.store.save_settings()
        if self.store.auto_capture:
            self.watch = LobbyWatch()
            self._watch_timer.start()
        elif not self.panel.isVisible():
            self._watch_timer.stop()

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
        self._start(self._capture_job, live=True)

    def open_screenshot(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            str(Path.home()),
            "图片 (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if not path:
            return
        self._start(lambda: check_image(path, list(self.store.entries)), live=False)

    def _capture_job(self) -> CheckResult:
        frames = capture_displays()
        return check_frames(frames, list(self.store.entries), on_lobby=self.worker.placed.emit)

    def _glance_job(self) -> bool:
        return glance_title(capture_top_band())

    def _auto_tick(self) -> None:
        if self._closing:
            return
        if not self.store.auto_capture and not self.panel.isVisible():
            self._watch_timer.stop()
            return
        self.worker.request(self._glance_job, kind="glance")

    def _start(self, fn, live: bool = False) -> bool:
        self._live_check = live
        if live and self.panel.isVisible():
            self._panel_hide_timer.stop()
            self.panel.set_mode("checking", "正在检查")
        self.tabs.setCurrentIndex(0)
        if not self.worker.request(fn):
            self._set_result("正在检查。")
            self._unlock_foreground()
            return False
        self._check_started = time.perf_counter()
        self._set_result("正在检查。")
        self.check_button.setEnabled(False)
        self.open_button.setEnabled(False)
        return True

    def _unlock_foreground(self) -> None:
        if not self._release_foreground:
            return
        self._release_foreground = False
        lock_foreground(False)

    def _on_worker(self, payload) -> None:
        job, status, value = payload
        self.worker.running_job = False
        if self._closing:
            return
        if job == "glance":
            self._on_glanced(status, value)
            return
        self._on_checked(status, value)

    def _on_glanced(self, status: str, value) -> None:
        if status != "ok":
            text = str(value)
            if text and text != getattr(self, "_glance_error", ""):
                self._glance_error = text
                self._set_result(text)
            return
        self._glance_error = ""
        if not value:
            if self.panel.isVisible() and not self._panel_hide_timer.isActive():
                self._panel_hide_timer.start(1000)
        else:
            self._panel_hide_timer.stop()
        if not self.store.auto_capture:
            return
        now = time.perf_counter()
        if not self.watch.wants_check(bool(value), now):
            return
        self.watch.arm(now)
        if not self._start(self._capture_job, live=True):
            self.watch.retry_after(now)

    def _note_watch(self, found: bool) -> None:
        if not self.store.auto_capture:
            return
        if found:
            self.watch.hold()
        else:
            self.watch.retry_after(time.perf_counter())

    def _on_checked(self, status: str, value) -> None:
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
        if status == "err":
            self._note_watch(False)
            self._hide_panel_after_title()
            text = str(value)
            self._set_result(text)
            self._set_tray(text)
            return
        result: CheckResult = value
        self._note_watch(bool(result.header_found))
        brief, clear = self._brief(result)
        self._set_result(brief, clear)
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
        self._show_panel(result)
        if result.header_found and result.hits and not self.store.muted:
            try:
                play_chime(chime_path(self.store.root))
            except Exception:
                self._set_result("提示音没响。")
        if self.store.save_debug_frames and result.preview_rgb is not None:
            self._save_debug(result)

    def _save_panel_pos(self, x: int, y: int) -> None:
        self.store.panel_pos = (int(x), int(y))
        self.store.save_settings()

    def _hide_panel_after_title(self) -> None:
        self._panel_hide_timer.stop()
        self.panel.hide()
        if not self.store.auto_capture:
            self._watch_timer.stop()

    def _on_lobby_placed(self, box) -> None:
        if self._closing or not self._live_check:
            return
        self._open_panel("checking", "正在检查", box)

    def _show_panel(self, result: CheckResult) -> None:
        if not self._live_check or not result.header_found:
            self._hide_panel_after_title()
            return
        if self.store.panel_pos is None and result.button_box is None:
            self._hide_panel_after_title()
            return
        if result.hits:
            lines = ["黑名单"]
            for hit in result.hits:
                line = f"{seat_number(hit.index)}号  {hit.entry_name}"
                if hit.note.strip():
                    line += f"  {hit.note.strip()}"
                lines.append(line)
            self._open_panel("hit", "\n".join(lines), result.button_box)
            return
        text = "没有黑名单"
        unclear = sum(1 for slot in result.names if slot.unclear)
        if unclear:
            text += f"\n{unclear} 人没看清"
        self._open_panel("clear", text, result.button_box)

    def _open_panel(self, mode: str, text: str, box) -> None:
        self._panel_hide_timer.stop()
        if self.store.panel_pos is not None:
            self.panel.show_at(self.store.panel_pos[0], self.store.panel_pos[1], mode, text)
        elif box is not None:
            self._show_panel_at(box, mode, text)
        else:
            return
        if not self._watch_timer.isActive():
            self._watch_timer.start()

    def _show_panel_at(self, box, mode: str, text: str) -> None:
        origin_x, origin_y = virtual_origin()
        screen = QApplication.primaryScreen()
        ratio = screen.devicePixelRatio() if screen is not None else 1.0
        if ratio <= 0:
            ratio = 1.0
        _left, top, right, bottom = box
        self.panel.show_beside(
            (right + origin_x) / ratio,
            (top + origin_y) / ratio,
            (bottom + origin_y) / ratio,
            mode,
            text,
        )

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

    def _brief(self, result: CheckResult) -> tuple[str, bool]:
        if not result.header_found:
            return result.message, False
        parts: list[str] = []
        clear = not result.hits
        if result.hits:
            parts.append(f"{len(result.hits)} 人在名单里")
        else:
            parts.append("没有发现黑名单")
        unclear = sum(1 for slot in result.names if slot.unclear)
        if unclear:
            parts.append(f"{unclear} 人没看清")
        return "，".join(parts), clear

    def _set_result(self, text: str, clear: bool = False) -> None:
        self.result_label.setObjectName("clear" if clear else "sub")
        self.result_label.setText(text)
        self.result_label.style().unpolish(self.result_label)
        self.result_label.style().polish(self.result_label)

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
        self._set_result("已复制。")

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
        self._panel_hide_timer.stop()
        self._watch_timer.stop()
        self.warning.close()
        self.clear_notice.close()
        self.panel.close()
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
