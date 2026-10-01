"""Main window, tray status, and the always-on-top warning."""

from __future__ import annotations

import queue
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from blacklist_detect.capture import capture_capability_message, capture_displays
from blacklist_detect.hotkey import GlobalHotkey, parse_hotkey
from blacklist_detect.match import seat_number
from blacklist_detect.ocr_engine import models_are_cached
from blacklist_detect.pipeline import CheckResult, check_frames, check_image
from blacklist_detect.sound import chime_path, play_chime
from blacklist_detect.storage import Store


def run_app() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("黑名单检测")
    app.setFont(_app_font())
    window = MainWindow()
    window.show()
    return app.exec()


def _app_font() -> QFont:
    font = QFont()
    font.setFamilies(
        [
            "Noto Sans CJK SC",
            "Noto Sans SC",
            "Source Han Sans SC",
            "WenQuanYi Micro Hei",
            "Microsoft YaHei",
            "sans-serif",
        ]
    )
    font.setPointSize(11)
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
        layout.addWidget(QLabel("按下热键。可以带 Ctrl、Alt、Shift 或 Win。Esc 取消。"))
        self.hint = QLabel("等待按键。")
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
            self.hint.setText("请用字母、数字或 F1–F12。")
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
        self.setStyleSheet(
            """
            QWidget { background: #2a120f; color: #f8efe6; }
            QLabel#warnTitle { color: #f0c36a; font-size: 16px; font-weight: 600; }
            QPlainTextEdit { background: #3a1a16; color: #f8efe6; border: 1px solid #8a4034; }
            QPushButton { background: #8c3b2a; color: #fff8f4; padding: 6px 12px; }
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
        self.resize(460, 640)
        self.store = Store()
        self.hotkey = GlobalHotkey(self.check_now)
        self.worker = CheckWorker()
        self.worker.done.connect(self._on_checked)
        self._closing = False
        self.warning = WarningWindow()
        self._build()
        self._apply_style()
        self._reload_table()
        self._restore_hotkey()
        self._set_tray(self.store.load_warning or capture_capability_message())
        if self.store.load_warning:
            self.result_label.setText(self.store.load_warning)

    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        header = QLabel("黑名单检测")
        header.setObjectName("title")
        outer.addWidget(header)
        sub = QLabel("上排 1–6 号，下排 7–12 号。按前四个字匹配。")
        sub.setObjectName("sub")
        outer.addWidget(sub)
        outer.addWidget(self._blacklist_box(), 1)
        outer.addWidget(self._check_box())
        self.names_view = QPlainTextEdit()
        self.names_view.setReadOnly(True)
        self.names_view.setPlaceholderText("检查后，十二个名字显示在这里。")
        self.names_view.setFixedHeight(160)
        outer.addWidget(self.names_view)

        self.tray = None
        if QSystemTrayIcon_available():
            from PySide6.QtWidgets import QSystemTrayIcon

            self.tray = QSystemTrayIcon(_icon(), self)
            self.tray.setToolTip("黑名单检测")
            self.tray.show()

    def _blacklist_box(self) -> QGroupBox:
        box = QGroupBox("黑名单")
        layout = QVBoxLayout(box)
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("玩家名")
        self.name_edit.returnPressed.connect(self.add_entry)
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("备注，可空")
        form.addRow("名字", self.name_edit)
        form.addRow("备注", self.note_edit)
        layout.addLayout(form)
        add = QPushButton("添加")
        add.setObjectName("primary")
        add.clicked.connect(self.add_entry)
        layout.addWidget(add)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["名字", "备注", "删除"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, self.table.horizontalHeader().ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, self.table.horizontalHeader().ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        layout.addWidget(self.table)
        self.empty_label = QLabel("还没有黑名单。把名字加在上面。")
        self.empty_label.setObjectName("empty")
        layout.addWidget(self.empty_label)
        return box

    def _check_box(self) -> QGroupBox:
        box = QGroupBox("检查")
        layout = QVBoxLayout(box)
        hot_row = QHBoxLayout()
        self.hotkey_edit = QLineEdit()
        self.hotkey_edit.setReadOnly(True)
        self.hotkey_edit.setPlaceholderText("尚未设置")
        hot_row.addWidget(self.hotkey_edit, 1)
        set_key = QPushButton("设置热键")
        set_key.clicked.connect(self.choose_hotkey)
        clear_key = QPushButton("清除")
        clear_key.clicked.connect(self.clear_hotkey)
        hot_row.addWidget(set_key)
        hot_row.addWidget(clear_key)
        layout.addLayout(hot_row)
        self.mute_box = QCheckBox("静音")
        self.mute_box.setChecked(self.store.muted)
        self.mute_box.toggled.connect(self._toggle_mute)
        layout.addWidget(self.mute_box)
        buttons = QHBoxLayout()
        self.check_button = QPushButton("立即检查")
        self.check_button.setObjectName("primary")
        self.check_button.clicked.connect(self.check_now)
        self.open_button = QPushButton("打开截图")
        self.open_button.clicked.connect(self.open_screenshot)
        buttons.addWidget(self.check_button)
        buttons.addWidget(self.open_button)
        layout.addLayout(buttons)
        self.result_label = QLabel("还没有检查。设好热键后，按热键才会截屏。")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)
        return box

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget#root { background: #1a1916; color: #f3efe6; }
            QLabel#title { font-size: 20px; font-weight: 600; color: #f3efe6; }
            QLabel#sub, QLabel#empty { color: #b7ad9e; }
            QGroupBox {
                border: 1px solid #3c372f;
                margin-top: 14px;
                padding: 10px 8px 8px 8px;
                color: #f3efe6;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #e6c27a;
            }
            QLineEdit, QPlainTextEdit, QTableWidget {
                background: #24221e;
                color: #f3efe6;
                border: 1px solid #3c372f;
                border-radius: 4px;
                padding: 4px;
            }
            QHeaderView::section {
                background: #2c2924;
                color: #e6dccb;
                border: none;
                padding: 4px;
            }
            QPushButton {
                background: #3a342c;
                color: #f3efe6;
                border: 1px solid #5c5346;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton#primary { background: #8c6a1f; border-color: #c6a15a; color: #fff8e8; }
            QCheckBox { spacing: 8px; }
            """
        )

    def _reload_table(self) -> None:
        self.table.setRowCount(len(self.store.entries))
        for row, entry in enumerate(self.store.entries):
            name = QTableWidgetItem(entry.name)
            name.setFlags(name.flags() & ~Qt.ItemIsEditable)
            note = QTableWidgetItem(entry.note)
            note.setFlags(note.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, note)
            remove = QPushButton("删除")
            remove.clicked.connect(lambda _checked=False, index=row: self._remove(index))
            self.table.setCellWidget(row, 2, remove)
        self.empty_label.setVisible(not self.store.entries)

    def add_entry(self) -> None:
        entry = self.store.add(self.name_edit.text(), self.note_edit.text())
        if entry is None:
            self.result_label.setText("名字是空的，没有加入。")
            return
        self.name_edit.clear()
        self.note_edit.clear()
        self._reload_table()

    def _remove(self, index: int) -> None:
        self.store.remove_at(index)
        self._reload_table()

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
            self.result_label.setText(f"热键已设为 {spec.display}。按下它会复制显示器并检查一次。")
        elif sys.platform != "win32":
            self.result_label.setText(
                f"热键已保存为 {spec.display}。这台系统没有全局热键，到 Windows 上才会截屏。"
            )
        else:
            self.store.hotkey = ""
            self.store.save_settings()
            self.hotkey_edit.clear()
            self.result_label.setText(self.hotkey.error or "这个热键没有注册。")

    def clear_hotkey(self) -> None:
        self.hotkey.clear()
        self.store.hotkey = ""
        self.store.save_settings()
        self.hotkey_edit.clear()
        self.result_label.setText("热键已清除。在设置新热键之前，不会因为热键截屏。")

    def _restore_hotkey(self) -> None:
        spec = parse_hotkey(self.store.hotkey)
        if spec is None:
            self.hotkey_edit.clear()
            return
        self.hotkey_edit.setText(spec.display)
        self.hotkey.apply(spec)

    def check_now(self) -> None:
        self._start(self._capture_job)

    def open_screenshot(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self,
            "打开截图",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if not path:
            return
        self._start(lambda: check_image(path, list(self.store.entries)))

    def _capture_job(self) -> CheckResult:
        frames = capture_displays()
        return check_frames(frames, list(self.store.entries))

    def _start(self, fn) -> None:
        if not self.worker.request(fn):
            self.result_label.setText("上一次检查还在进行。")
            return
        if models_are_cached():
            self.result_label.setText("正在检查…")
        else:
            self.result_label.setText("正在加载本地中文识别模型并检查。第一次需要模型文件已在本机。")
        self.check_button.setEnabled(False)
        self.open_button.setEnabled(False)

    def _on_checked(self, payload) -> None:
        self.worker.running_job = False
        if self._closing:
            return
        self.check_button.setEnabled(True)
        self.open_button.setEnabled(True)
        kind, value = payload
        if kind == "err":
            text = str(value)
            if isinstance(value, str) and "DXGI" not in text and "dxcam" not in text and "截" not in text:
                pass
            self.result_label.setText(text)
            self._set_tray(text)
            return
        result: CheckResult = value
        self.result_label.setText(result.message)
        self._set_tray(result.message)
        self._show_result(result)
        if result.header_found and result.hits:
            self.warning.present([hit.line for hit in result.hits])
            if not self.store.muted:
                try:
                    play_chime(chime_path(self.store.root))
                except Exception:
                    self.result_label.setText(result.message + " 提示音没有播放。")
        if self.store.save_debug_frames and result.preview_rgb is not None:
            self._save_debug(result)

    def _show_result(self, result: CheckResult) -> None:
        lines = []
        for slot in result.names:
            seat = seat_number(slot.index)
            if slot.unclear:
                lines.append(f"{seat}号  未看清")
            else:
                lines.append(f"{seat}号  {slot.visible}")
        self.names_view.setPlainText("\n".join(lines))

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
