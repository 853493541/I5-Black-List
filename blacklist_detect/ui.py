"""Main window, tray status, and the always-on-top warning."""

from __future__ import annotations

import queue
import sys
import time
from datetime import datetime

from PySide6.QtCore import QEvent, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
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
from blacklist_detect.match import NameLabel, match_label, seat_number
from blacklist_detect.pipeline import CheckResult, check_frames, glance_title
from blacklist_detect.sound import chime_path, play_chime
from blacklist_detect.storage import Store, reason_text
from blacklist_detect.watch import GLANCE_INTERVAL_MS, LobbyWatch


def run_app() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("黑名单检测")
    app.setFont(chinese_font())
    _apply_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()


_CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫"


def _zh_clock(moment: datetime) -> str:
    period = "上午" if moment.hour < 12 else "下午"
    hour = moment.hour % 12 or 12
    if moment.minute == 0:
        return f"{period}{hour}点"
    return f"{period}{hour}点{moment.minute:02d}分"


def _circled(seat) -> str:
    try:
        number = int(seat)
    except (TypeError, ValueError):
        return ""
    if 1 <= number <= len(_CIRCLED):
        return _CIRCLED[number - 1]
    return str(number)


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

def _palette(
    page: str,
    ink: str,
    muted: str,
    wash: str,
    edge: str,
    accent: str,
    accent_line: str,
    accent_hover: str,
    accent_press: str,
    on_accent: str,
) -> dict[str, str]:
    return {
        "bg": page,
        "text": ink,
        "muted": muted,
        "surface": "#ffffff",
        "line": edge,
        "button": "#ffffff",
        "button_line": edge,
        "selected": wash,
        "head": wash,
        "head_text": ink,
        "gold": accent,
        "gold_line": accent_line,
        "on_gold": on_accent,
        "green": "#1c7a3e",
        "red": "#c23b2e",
        "add": accent,
        "danger": "#a33b2c",
        "hover": wash,
        "gold_hover": accent_hover,
        "gold_press": accent_press,
        "danger_hover": "#f8e6e1",
    }


THEMES = {
    "蓝色": _palette("#f2f6fb", "#172033", "#5d6d82", "#e4eef8", "#d3deec", "#12325a", "#2c6cb3", "#1a4578", "#0c243f", "#f4f8ff"),
    "棕色": _palette("#f7f3ee", "#2a2118", "#6f6256", "#f3ebe3", "#e6d9cc", "#6b4428", "#a67c52", "#7d5334", "#4a2e1a", "#fff8f2"),
    "紫色": _palette("#f6f4fb", "#241833", "#6a5d80", "#eee8f6", "#ddd4ec", "#4a2d73", "#7a5caf", "#5c3b8c", "#321d52", "#f8f5ff"),
    "绿色": _palette("#f3f7f4", "#17241c", "#5c6e64", "#e5f0ea", "#d2e2d8", "#1b5340", "#3d8f6e", "#24664e", "#12382b", "#f4fbf7"),
    "红色": _palette("#fbf5f4", "#2c1818", "#7a6565", "#f6e8e6", "#ead8d4", "#7a3030", "#b85c5c", "#8e3c3c", "#541f1f", "#fff6f5"),
}
THEME = THEMES["蓝色"]


def use_theme(name: str) -> None:
    global THEME
    THEME = THEMES.get(name, THEMES["蓝色"])


def _apply_theme(app: QApplication | None = None) -> None:
    """Keep every native control on the same palette, even when Windows is dark."""
    app = app or QApplication.instance()
    if app is None:
        return
    scheme = Qt.ColorScheme.Light
    app.styleHints().setColorScheme(scheme)
    t = THEME
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(t["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(t["surface"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(t["head"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(t["button"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(t["selected"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(t["surface"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(t["muted"]))
    palette.setColor(QPalette.ColorRole.Mid, QColor(t["line"]))
    app.setPalette(palette)


def _control_hover() -> str:
    t = THEME
    return f"""
            QPushButton:hover {{
                background: {t["hover"]};
                border-color: {t["gold_line"]};
            }}
            QPushButton:pressed {{ background: {t["selected"]}; }}
            QPushButton#primary:hover {{
                background: {t["gold_hover"]};
                border-color: {t["gold_line"]};
                color: {t["on_gold"]};
            }}
            QPushButton#primary:pressed {{
                background: {t["gold_press"]};
                color: {t["on_gold"]};
            }}
            QPushButton#danger:hover {{
                background: {t["danger_hover"]};
                color: {t["danger"]};
            }}
            QCheckBox:hover {{ color: {t["gold"]}; }}
            QLineEdit:hover {{ border: 1px solid {t["gold_line"]}; }}
            """


def _pointing(root) -> None:
    for widget in (*root.findChildren(QPushButton), *root.findChildren(QCheckBox)):
        widget.setCursor(Qt.PointingHandCursor)


def _menu_style(family: str) -> str:
    t = THEME
    return f"""
            QMenu {{
                font-family: "{family}";
                background: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["line"]};
                padding: 4px;
            }}
            QMenu::item {{
                font-family: "{family}";
                background: transparent;
                color: {t["text"]};
                padding: 6px 18px;
            }}
            QMenu::item:selected {{ background: {t["selected"]}; }}
            """


def _window_style(family: str) -> str:
    t = THEME
    return f"""
            QWidget#root, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QCheckBox,
            QTabWidget, QTabBar, QListWidget, QTableWidget, QHeaderView, QTableWidget QWidget {{
                font-family: "{family}";
            }}
            QMainWindow, QWidget#root, QTabWidget, QTabBar, QTabWidget::pane {{
                background: {t["bg"]};
                color: {t["text"]};
                border: none;
                padding: 0;
                margin: 0;
            }}
            QTabBar::tab {{
                font-family: "{family}";
                font-size: 14px;
                color: {t["muted"]};
                background: transparent;
                border: none;
                border-bottom: 2px solid transparent;
                padding: 8px 16px;
                margin-right: 8px;
            }}
            QTabBar::tab:selected {{
                color: {t["text"]};
                border-bottom: 2px solid {t["gold_line"]};
            }}
            QTabBar::tab:hover {{
                color: {t["text"]};
                background: {t["hover"]};
                border-radius: 4px;
            }}
            QTabBar::tab:selected:hover {{ background: transparent; }}
            QLabel#sub {{ font-family: "{family}"; color: {t["muted"]}; }}
            QLabel#clear {{
                font-family: "{family}";
                font-size: 18px;
                font-weight: 700;
                color: {t["green"]};
            }}
            QLabel#hit {{
                font-family: "{family}";
                font-size: 18px;
                font-weight: 700;
                color: {t["red"]};
            }}
            QLabel#idle {{
                font-family: "{family}";
                font-size: 18px;
                font-weight: 700;
                color: {t["muted"]};
            }}
            QLabel#status {{
                font-family: "{family}";
                font-size: 18px;
                font-weight: 700;
                color: {t["text"]};
            }}
            QLineEdit, QPlainTextEdit, QTableWidget, QListWidget {{
                background: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["line"]};
                border-radius: 4px;
                padding: 8px 12px;
            }}
            QListWidget::item {{
                font-family: "{family}";
                background: transparent;
                color: {t["text"]};
                padding: 8px 12px;
                border: none;
            }}
            QListWidget#history {{ padding: 0; }}
            QListWidget#history::item {{ padding: 0; }}
            QListWidget::item:hover {{ background: {t["hover"]}; }}
            QListWidget::item:selected, QListWidget::item:selected:hover {{
                background: {t["selected"]};
                color: {t["text"]};
            }}
            QTableWidget::item {{
                background: {t["surface"]};
                color: {t["text"]};
                border: none;
            }}
            QTableWidget::item:hover {{ background: {t["hover"]}; }}
            QTableWidget::item:selected, QTableWidget::item:selected:hover {{
                background: {t["selected"]};
                color: {t["text"]};
            }}
            QHeaderView, QTableCornerButton::section {{ background: {t["head"]}; }}
            QHeaderView::section {{
                background: {t["head"]};
                color: {t["head_text"]};
                border: none;
                padding: 8px 12px;
            }}
            QScrollBar:vertical, QScrollBar:horizontal {{
                background: {t["surface"]};
                border: none;
                margin: 0;
            }}
            QScrollBar:vertical {{ width: 10px; }}
            QScrollBar:horizontal {{ height: 10px; }}
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
                background: {t["button_line"]};
                border-radius: 4px;
                min-height: 24px;
                min-width: 24px;
            }}
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
                background: {t["gold_line"]};
            }}
            QScrollBar::add-line, QScrollBar::sub-line,
            QScrollBar::add-page, QScrollBar::sub-page {{
                background: transparent;
                height: 0;
                width: 0;
            }}
            QWidget#tableHead {{ background: {t["head"]}; }}
            QWidget#tableHead QLabel {{
                font-family: "{family}";
                color: {t["head_text"]};
                background: transparent;
            }}
            QPushButton {{
                background: {t["button"]};
                color: {t["text"]};
                border: 1px solid {t["button_line"]};
                border-radius: 4px;
                padding: 8px 16px;
            }}
            QPushButton#primary {{
                background: {t["gold"]};
                border-color: {t["gold_line"]};
                color: {t["on_gold"]};
            }}
            QCheckBox {{ spacing: 8px; color: {t["text"]}; background: transparent; }}
            """ + _control_hover() + _menu_style(family)


def _dialog_style(family: str) -> str:
    t = THEME
    return f"""
            QDialog, QMessageBox, QLabel, QLineEdit, QPushButton, QCheckBox {{
                font-family: "{family}";
                background: {t["bg"]};
                color: {t["text"]};
            }}
            QLineEdit {{
                background: {t["surface"]};
                border: 1px solid {t["line"]};
                border-radius: 4px;
                padding: 6px;
            }}
            QCheckBox {{ background: transparent; spacing: 8px; }}
            QPushButton {{
                background: {t["button"]};
                color: {t["text"]};
                border: 1px solid {t["button_line"]};
                border-radius: 4px;
                padding: 6px 12px;
            }}
            QPushButton#primary {{
                background: {t["gold"]};
                border-color: {t["gold_line"]};
                color: {t["on_gold"]};
            }}
            QPushButton#danger {{ color: {t["danger"]}; }}
            """ + _control_hover() + f"""
            QCheckBox {{
                spacing: 8px;
                padding: 6px 8px;
                border-radius: 4px;
            }}
            QCheckBox:hover {{
                background: {t["hover"]};
                color: {t["text"]};
            }}
            QLabel#error {{
                color: {t["red"]};
                background: transparent;
            }}
            """


def _colorref(value: str):
    import ctypes

    color = QColor(value)
    return ctypes.c_uint((color.blue() << 16) | (color.green() << 8) | color.red())


def _caption_color(widget) -> None:
    """Match the window caption to the chrome. Windows only."""
    if sys.platform != "win32":
        return
    import ctypes

    hwnd = int(widget.winId())
    dark = ctypes.c_int(0)
    dwm = ctypes.windll.dwmapi
    values = (
        (20, dark),
        (19, dark),
        (34, _colorref(THEME["line"])),
        (35, _colorref(THEME["bg"])),
        (36, _colorref(THEME["text"])),
    )
    for attribute, value in values:
        dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))


def _page(layout) -> None:
    layout.setContentsMargins(0, GAP, 0, 0)
    layout.setSpacing(GAP)


def _watch_mark(color: str) -> QPixmap:
    ratio = 2
    size = 16 * ratio
    pixmap = QPixmap(size, size)
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    painter.setOpacity(0.22)
    painter.drawEllipse(0, 0, size, size)
    painter.setOpacity(1)
    inset = 4 * ratio
    painter.drawEllipse(inset, inset, size - inset * 2, size - inset * 2)
    painter.end()
    return pixmap


def _swatch(color: str) -> QIcon:
    pixmap = QPixmap(14, 14)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(1, 1, 12, 12)
    painter.end()
    return QIcon(pixmap)


def _confirm(parent, text: str) -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle("黑名单检测")
    box.setText(text)
    box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    box.setDefaultButton(QMessageBox.No)
    yes = box.button(QMessageBox.Yes)
    no = box.button(QMessageBox.No)
    if yes is not None:
        yes.setText("确定")
    if no is not None:
        no.setText("取消")
    box.setFont(chinese_font())
    box.setStyleSheet(_dialog_style(chinese_family()))
    _caption_color(box)
    return box.exec() == QMessageBox.Yes


def _icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(THEME["gold"]))
    painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
    painter.setBrush(QColor(THEME["on_gold"]))
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
        self.setStyleSheet(_dialog_style(chinese_family()))
        _caption_color(self)
        layout.addWidget(self.hint)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)
        self.setMinimumWidth(420)
        _pointing(self)

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

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)


class ReasonCheck(QCheckBox):
    """The words count as the control. A stylesheet otherwise keeps only the square clickable."""

    def hitButton(self, pos) -> bool:  # noqa: ANN001
        return self.rect().contains(pos)


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
        self.setStyleSheet(_dialog_style(chinese_family()))
        _caption_color(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAD, PAD, PAD, PAD)
        layout.setSpacing(GAP)
        layout.addWidget(QLabel("名字"))
        self.name_edit = QLineEdit(name)
        layout.addWidget(self.name_edit)
        self.name_error = QLabel("")
        self.name_error.setObjectName("error")
        layout.addWidget(self.name_error)
        self.name_edit.textChanged.connect(lambda _text: self.name_error.setText(""))
        layout.addWidget(QLabel("原因"))
        from blacklist_detect.storage import REASON_TAGS

        self.boxes: dict[str, QCheckBox] = {}
        for tag in REASON_TAGS:
            box = ReasonCheck(tag)
            box.setChecked(tag in reasons)
            box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
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
        _pointing(self)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)

    def _chosen(self) -> tuple[str, ...]:
        from blacklist_detect.storage import REASON_TAGS

        return tuple(tag for tag in REASON_TAGS if self.boxes[tag].isChecked())

    def _accept(self) -> None:
        if not self.name_edit.text().strip():
            self.name_error.setText("请填写名字")
            return
        self.name_error.setText("")
        self.name = self.name_edit.text()
        self.reasons = self._chosen()
        self.detail = self.detail_edit.text() if "其他" in self.reasons else ""
        self.deleted = False
        self.accept()

    def _delete(self) -> None:
        if not _confirm(self, "删除这一名？"):
            return
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
        self.setFont(chinese_font())
        self.body.setFont(chinese_font(12))
        self.apply_theme()
        _pointing(self)

    def apply_theme(self) -> None:
        family = chinese_family()
        t = THEME
        self.setStyleSheet(
            f"""
            QWidget {{ background: {t["bg"]}; color: {t["text"]}; font-family: "{family}"; }}
            QLabel#warnTitle {{ color: {t["red"]}; font-family: "{family}"; font-size: 16px; font-weight: 600; background: transparent; }}
            QPlainTextEdit {{
                background: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["line"]};
                border-radius: 4px;
                font-family: "{family}";
                font-size: 14px;
            }}
            QPushButton {{
                background: {t["button"]};
                color: {t["text"]};
                border: 1px solid {t["button_line"]};
                border-radius: 4px;
                padding: 6px 12px;
                font-family: "{family}";
            }}
            QPushButton:hover {{
                background: {t["hover"]};
                border-color: {t["gold_line"]};
            }}
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
        _caption_color(self)
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
        self.setFont(chinese_font())
        self.apply_theme()
        _pointing(self)

    def apply_theme(self) -> None:
        family = chinese_family()
        t = THEME
        self.setStyleSheet(
            f"""
            QWidget {{ background: {t["bg"]}; color: {t["text"]}; font-family: "{family}"; }}
            QLabel#clearTitle {{ color: {t["green"]}; font-family: "{family}"; font-size: 18px; font-weight: 600; background: transparent; }}
            QLabel#clearDetail {{ color: {t["text"]}; font-family: "{family}"; font-size: 15px; background: transparent; }}
            QPushButton {{
                background: {t["button"]};
                color: {t["text"]};
                border: 1px solid {t["button_line"]};
                border-radius: 4px;
                padding: 8px 16px;
                font-family: "{family}";
            }}
            QPushButton:hover {{
                background: {t["hover"]};
                border-color: {t["gold_line"]};
            }}
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
        _caption_color(self)
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
            LobbyPanel, QWidget {{ background: transparent; }}
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
        self.store = Store()
        use_theme(self.store.theme)
        self.setMinimumSize(900, 560)
        saved = self.store.window_size or (900, 560)
        self.resize(saved[0], saved[1])
        self.setWindowIcon(_icon())
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
        self._history_hover = (-1, -1)
        self._closed_days: set[str] = set()
        self._check_started: float | None = None
        self._release_foreground = False
        self._told_tray = False
        self._status_kind = "idle"
        self._watch_tone = "idle"
        self._watch_full = "未开启"
        self._build()
        self._apply_style()
        _caption_color(self)
        self._show_list()
        self._reload_history()
        self._restore_hotkey()
        if self.store.auto_capture:
            self._watch_timer.start()
        self._sync_watch_idle()
        notice = self.store.load_warning or capture_capability_message()
        if notice:
            self._set_result(notice, "hit", "error")

    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(PAD, PAD, PAD, PAD)
        outer.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.history_tab = self.tabs.addTab(self._history_page(), "记录")
        self.blacklist_tab = self.tabs.addTab(self._list_page(), "黑名单")
        self.tabs.addTab(self._settings_page(), "设置")
        corner = QWidget()
        corner_row = QHBoxLayout(corner)
        corner_row.setContentsMargins(0, 0, 0, 0)
        corner_row.setSpacing(8)
        self.watch_mark = QLabel()
        self.watch_mark.setPixmap(_watch_mark(THEME["muted"]))
        self.watch_label = QLabel("未开启")
        self.watch_label.setObjectName("idle")
        self.watch_label.setMaximumWidth(200)
        watch_font = chinese_font(18)
        watch_font.setBold(True)
        self.watch_label.setFont(watch_font)
        corner_row.addWidget(self.watch_mark)
        corner_row.addWidget(self.watch_label)
        self.tabs.setCornerWidget(corner, Qt.TopRightCorner)
        outer.addWidget(self.tabs)

        self.names_view = QPlainTextEdit()
        self.names_view.hide()

        self.tray = None
        if QSystemTrayIcon_available():
            from PySide6.QtWidgets import QSystemTrayIcon

            self.tray = QSystemTrayIcon(_icon(), self)
            self.tray.setToolTip("黑名单检测")
            self.tray_menu = QMenu()
            self.tray_menu.setFont(chinese_font())
            self.tray_menu.setStyleSheet(_menu_style(chinese_family()))
            self.tray_menu.addAction("打开", self._show_from_tray)
            self.tray_menu.addAction("退出", self.close)
            self.tray.setContextMenu(self.tray_menu)
            self.tray.activated.connect(self._on_tray)
            self.tray.show()

    def _list_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        _page(layout)
        add = QPushButton("添加")
        add.setObjectName("primary")
        add.clicked.connect(self._add_by_dialog)
        layout.addWidget(add, 0, Qt.AlignLeft)
        self.list_hint = QLabel("还没有名字，点添加")
        self.list_hint.setObjectName("sub")
        self.list_hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.list_hint)
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
        self.blacklist_table.setMouseTracking(True)
        self.blacklist_table.setCursor(Qt.PointingHandCursor)
        self.blacklist_table.cellClicked.connect(self._edit_row)
        layout.addWidget(self.blacklist_table, 1)
        return page

    def _history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        _page(layout)
        body = QHBoxLayout()
        body.setSpacing(GAP)
        side = QWidget()
        side.setFixedWidth(168)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(GAP)
        self.history_list = QListWidget()
        self.history_list.setObjectName("history")
        self.history_list.setCursor(Qt.PointingHandCursor)
        self.history_list.currentRowChanged.connect(self._on_history_picked)
        self.history_list.itemClicked.connect(self._on_history_clicked)
        side_layout.addWidget(self.history_list, 1)
        self.clear_history_button = QPushButton("清空记录")
        self.clear_history_button.clicked.connect(self._ask_clear_history)
        side_layout.addWidget(self.clear_history_button)
        body.addWidget(side)
        names = QVBoxLayout()
        names.setSpacing(0)
        head_bar = QWidget()
        head_bar.setObjectName("tableHead")
        head = QHBoxLayout(head_bar)
        head.setContentsMargins(12, 8, 12, 8)
        head.setSpacing(GAP)
        catalog = QLabel("模仿者游戏")
        catalog.setFont(chinese_font())
        self.scan_time = QLabel("")
        self.scan_time.setFont(chinese_font())
        self.scan_time.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.delete_scan_button = QPushButton("删除这条")
        self.delete_scan_button.clicked.connect(self._delete_history)
        head.addWidget(catalog)
        head.addStretch(1)
        head.addWidget(self.scan_time)
        head.addWidget(self.delete_scan_button)
        names.addWidget(head_bar)
        self.history_table = QTableWidget(0, 3)
        self.history_table.horizontalHeader().setVisible(False)
        header = self.history_table.horizontalHeader()
        header.setStretchLastSection(True)
        for column in range(3):
            header.setSectionResizeMode(column, header.ResizeMode.Stretch)
        self.history_table.setCursor(Qt.PointingHandCursor)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.verticalHeader().setDefaultSectionSize(40)
        self.history_table.setSelectionMode(QTableWidget.NoSelection)
        self.history_table.setShowGrid(False)
        self.history_table.setMouseTracking(True)
        self.history_table.viewport().setMouseTracking(True)
        self.history_table.viewport().installEventFilter(self)
        self.history_table.cellEntered.connect(self._hover_history_cell)
        self.history_table.cellClicked.connect(self._on_history_cell)
        names.addWidget(self.history_table, 1)
        body.addLayout(names, 1)
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
        set_key.setObjectName("primary")
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
        mute_hint = QLabel("有黑名单时不播放提示音")
        mute_hint.setObjectName("sub")
        layout.addWidget(mute_hint)
        self.auto_box = QCheckBox("看到推演成功时自动检查")
        self.auto_box.setChecked(self.store.auto_capture)
        self.auto_box.toggled.connect(self._toggle_auto)
        layout.addWidget(self.auto_box)
        layout.addWidget(QLabel("主题"))
        themes = QHBoxLayout()
        themes.setSpacing(GAP)
        self.theme_buttons: dict[str, QPushButton] = {}
        for name in THEMES:
            button = QPushButton(name)
            button.setIcon(_swatch(THEMES[name]["gold"]))
            button.setIconSize(QSize(14, 14))
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, picked=name: self._set_theme(picked))
            self.theme_buttons[name] = button
            themes.addWidget(button)
        themes.addStretch(1)
        layout.addLayout(themes)
        self.settings_label = QLabel("")
        self.settings_label.setObjectName("sub")
        self.settings_label.setWordWrap(True)
        layout.addWidget(self.settings_label)
        layout.addStretch(1)
        return page

    def _apply_style(self) -> None:
        _apply_theme()
        self.setFont(chinese_font())
        self.setStyleSheet(_window_style(chinese_family()))
        _pointing(self)
        self._mark_theme_buttons()
        if hasattr(self, "watch_label"):
            self._set_result(self._watch_full, self._watch_tone, self._status_kind)
        if hasattr(self, "warning"):
            self.warning.apply_theme()
            self.clear_notice.apply_theme()

    def _mark_theme_buttons(self) -> None:
        for name, button in self.theme_buttons.items():
            button.setObjectName("primary" if name == self.store.theme else "")
            button.setChecked(name == self.store.theme)
            button.style().unpolish(button)
            button.style().polish(button)

    def _set_theme(self, name: str) -> None:
        if name not in THEMES or name == self.store.theme:
            self._mark_theme_buttons()
            return
        self.store.theme = name
        self.store.save_settings()
        use_theme(name)
        icon = _icon()
        self.setWindowIcon(icon)
        if self.tray is not None:
            self.tray.setIcon(icon)
        self._apply_style()
        _caption_color(self)
        self.warning.apply_theme()
        self.clear_notice.apply_theme()
        self._reload_history(max(0, self._selected_scan()))
        self._show_list()

    def eventFilter(self, watched, event) -> bool:  # noqa: ANN001
        table = getattr(self, "history_table", None)
        if table is not None and watched is table.viewport() and event.type() == QEvent.Type.Leave:
            self._clear_history_hover()
        return super().eventFilter(watched, event)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)
        self._remember_size()

    def _show_list(self) -> None:
        self.blacklist_table.setRowCount(len(self.store.entries))
        for index, entry in enumerate(self.store.entries):
            name = QTableWidgetItem(entry.name)
            name.setFlags(name.flags() & ~Qt.ItemIsEditable)
            name.setFont(chinese_font())
            name.setForeground(QColor(THEME["text"]))
            reason = QTableWidgetItem(reason_text(entry))
            reason.setFlags(reason.flags() & ~Qt.ItemIsEditable)
            reason.setFont(chinese_font())
            reason.setForeground(QColor(THEME["text"]))
            self.blacklist_table.setItem(index, 0, name)
            self.blacklist_table.setItem(index, 1, reason)
            self.blacklist_table.setRowHeight(index, 40)
        self._refresh_blacklist_tab()
        count = len(self.store.entries)
        if count:
            self.list_hint.setText("点击修改")
            self.list_hint.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.blacklist_table.setVisible(True)
        else:
            self.list_hint.setText("还没有名字，点添加")
            self.list_hint.setAlignment(Qt.AlignCenter)
            self.blacklist_table.setVisible(False)

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
        self._show_history_scan(self._selected_scan())

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
        self._show_history_scan(self._selected_scan())

    def _reload_history(self, select: int = 0) -> None:
        self.history_list.blockSignals(True)
        self.history_list.clear()
        folders: list[tuple[str, list[tuple[int, str]]]] = []
        seen: dict[str, int] = {}
        for index, scan in enumerate(self.store.scans):
            day, clock = self._day_and_clock(str(scan.get("at", "")))
            period = "上午" if clock.startswith("上午") else "下午" if clock.startswith("下午") else ""
            key = f"{day} {period}".strip() if day else clock
            if key not in seen:
                seen[key] = len(folders)
                folders.append((key, []))
            folders[seen[key]][1].append((index, clock))
        for key, rows in folders:
            closed = key in self._closed_days
            self._add_day_folder(key, closed)
            for index, clock in rows:
                shown = clock[2:] if clock.startswith(("上午", "下午")) else clock
                self._add_history_time(key, index, f"  {shown}", closed)
        count = len(self.store.scans)
        self.history_list.setVisible(count > 0)
        self.history_table.setVisible(count > 0)
        self.history_empty.setVisible(count == 0)
        self.delete_scan_button.setVisible(count > 0)
        self.clear_history_button.setVisible(count > 0)
        self.tabs.setTabText(self.history_tab, f"记录  {count}" if count else "记录")
        chosen = -1
        if count:
            chosen = max(0, min(select, count - 1))
            for list_row in range(self.history_list.count()):
                if self.history_list.item(list_row).data(Qt.UserRole) == chosen:
                    self.history_list.setCurrentRow(list_row)
                    break
        self.history_list.blockSignals(False)
        self._show_history_scan(chosen)

    def _add_day_folder(self, day: str, closed: bool) -> None:
        item = QListWidgetItem("")
        item.setData(Qt.UserRole, -1)
        item.setData(Qt.UserRole + 1, "day")
        item.setData(Qt.UserRole + 2, day)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        item.setSizeHint(QSize(0, 36))
        wrap = QWidget()
        wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        wrap.setStyleSheet("background: transparent;")
        line = QHBoxLayout(wrap)
        line.setContentsMargins(8, 4, 8, 4)
        line.setSpacing(0)
        label = QLabel(f"{'▶' if closed else '▼'}  {day}")
        label.setObjectName("dayFolder")
        label.setFont(chinese_font())
        label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        label.setStyleSheet(f"color: {THEME['text']}; background: transparent;")
        line.addWidget(label)
        self.history_list.addItem(item)
        self.history_list.setItemWidget(item, wrap)

    def _add_history_time(self, day: str, index: int, text: str, closed: bool) -> None:
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, index)
        item.setData(Qt.UserRole + 1, "time")
        item.setData(Qt.UserRole + 2, day)
        item.setForeground(QColor(THEME["text"]))
        item.setFont(chinese_font())
        self.history_list.addItem(item)
        item.setHidden(closed)

    def _on_history_clicked(self, item: QListWidgetItem) -> None:
        if item.data(Qt.UserRole + 1) != "day":
            return
        day = str(item.data(Qt.UserRole + 2) or "")
        if day in self._closed_days:
            self._closed_days.discard(day)
        else:
            self._closed_days.add(day)
        self._sync_day_folders()

    def _sync_day_folders(self) -> None:
        self.history_list.blockSignals(True)
        selected = self._selected_scan()
        for row in range(self.history_list.count()):
            item = self.history_list.item(row)
            day = str(item.data(Qt.UserRole + 2) or "")
            closed = day in self._closed_days
            kind = item.data(Qt.UserRole + 1)
            if kind == "day":
                wrap = self.history_list.itemWidget(item)
                label = wrap.findChild(QLabel, "dayFolder") if wrap is not None else None
                if label is not None:
                    label.setText(f"{'▶' if closed else '▼'}  {day}")
            else:
                item.setHidden(closed)
        if selected >= 0:
            for row in range(self.history_list.count()):
                item = self.history_list.item(row)
                if item.data(Qt.UserRole) == selected and not item.isHidden():
                    self.history_list.setCurrentRow(row)
                    break
        self.history_list.blockSignals(False)

    def _on_history_picked(self, list_row: int) -> None:
        index = self._scan_at(list_row)
        if index < 0:
            return
        self._show_history_scan(index)

    def _selected_scan(self) -> int:
        return self._scan_at(self.history_list.currentRow())

    def _scan_at(self, list_row: int) -> int:
        if list_row < 0:
            return -1
        item = self.history_list.item(list_row)
        if item is None:
            return -1
        value = item.data(Qt.UserRole)
        try:
            index = int(value)
        except (TypeError, ValueError):
            return -1
        if index < 0:
            return -1
        return index

    def _delete_history(self) -> None:
        row = self._selected_scan()
        self.store.remove_scan(row)
        self._reload_history(row)

    def _ask_clear_history(self) -> None:
        if not _confirm(self, "清空记录？"):
            return
        self._clear_history()

    def _clear_history(self) -> None:
        self.store.clear_scans()
        self._reload_history()

    def _day_and_clock(self, stamp: str) -> tuple[str, str]:
        try:
            moment = datetime.fromisoformat(stamp)
        except ValueError:
            return "", stamp
        return moment.strftime("%m-%d"), _zh_clock(moment)

    def _scan_parts(self, stamp: str, elapsed) -> tuple[str, str]:
        day, clock = self._day_and_clock(stamp)
        when = f"{day} {clock}".strip()
        try:
            seconds = float(elapsed)
        except (TypeError, ValueError):
            return when, ""
        shown = f"{seconds:.2f}" if seconds < 10 else f"{seconds:.1f}"
        return when, f"用时 {shown} 秒"

    def _show_history_scan(self, row: int) -> None:
        self._history_hover = (-1, -1)
        self.history_table.setRowCount(0)
        if row < 0 or row >= len(self.store.scans):
            self.scan_time.setText("")
            return
        scan = self.store.scans[row]
        _when, spent = self._scan_parts(str(scan.get("at", "")), scan.get("elapsed"))
        self.scan_time.setText(spent)
        names = self.store.scans[row].get("names", [])
        self.history_table.setRowCount((len(names) + 2) // 3)
        for index, seat in enumerate(names):
            self._set_history_seat(index // 3, index % 3, seat)
            self.history_table.setRowHeight(index // 3, 40)

    def _history_match(self, shown: str):
        label = NameLabel(raw=shown, visible=shown, truncated=False)
        found = match_label(label, list(self.store.entries))
        return found[0] if found else None

    def _set_history_seat(self, row: int, column: int, seat: dict) -> None:
        unclear = bool(seat.get("unclear")) or not str(seat.get("name") or "")
        shown = "未看清" if unclear else str(seat.get("name"))
        match = None if unclear else self._history_match(shown)
        stored = match.entry.name if match is not None else ""
        reason = reason_text(match.entry) if match is not None else ""
        action = "移除" if match is not None else ("" if unclear else "加入")
        title = stored if match is not None else shown
        if reason:
            title = f"{title}  {reason}"
        label = f"{_circled(seat.get('seat'))} {title}"
        name_item = QTableWidgetItem(label)
        name_item.setData(Qt.UserRole, "" if unclear else shown)
        name_item.setData(Qt.UserRole + 1, action)
        name_item.setData(Qt.UserRole + 2, stored)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        name_item.setFont(chinese_font())
        name_item.setForeground(QColor(THEME["red"] if match is not None else THEME["text"]))
        self.history_table.setItem(row, column, name_item)
        wrap = QWidget()
        wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        wrap.setStyleSheet(self._history_wrap_style(False))
        line = QHBoxLayout(wrap)
        line.setContentsMargins(4, 0, 8, 0)
        line.setSpacing(GAP)
        name_label = QLabel(label)
        name_label.setFont(chinese_font())
        name_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        name_color = THEME["red"] if match is not None else THEME["text"]
        name_label.setStyleSheet(f"color: {name_color}; background: transparent;")
        line.addWidget(name_label)
        line.addStretch(1)
        if action:
            action_label = QLabel(action)
            action_label.setObjectName("rowAction")
            action_label.setFont(chinese_font())
            action_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            color = THEME["red"] if match is not None else THEME["add"]
            action_label.setStyleSheet(f"color: {color}; background: transparent;")
            line.addWidget(action_label)
        self.history_table.setCellWidget(row, column, wrap)

    def _history_wrap_style(self, hot: bool) -> str:
        color = THEME["hover"] if hot else THEME["surface"]
        return f"background: {color};"

    def _hover_history_cell(self, row: int, column: int) -> None:
        if self._history_hover == (row, column):
            return
        self._paint_history_hover(*self._history_hover, False)
        self._history_hover = (row, column)
        self._paint_history_hover(row, column, True)

    def _clear_history_hover(self) -> None:
        self._paint_history_hover(*self._history_hover, False)
        self._history_hover = (-1, -1)

    def _paint_history_hover(self, row: int, column: int, hot: bool) -> None:
        if row < 0 or column < 0:
            return
        item = self.history_table.item(row, column)
        wrap = self.history_table.cellWidget(row, column)
        if item is None or wrap is None:
            return
        if hot and not str(item.data(Qt.UserRole) or ""):
            return
        wrap.setStyleSheet(self._history_wrap_style(hot))

    def _on_history_cell(self, row: int, column: int) -> None:
        item = self.history_table.item(row, column)
        if item is None:
            return
        shown = str(item.data(Qt.UserRole) or "")
        if not shown:
            return
        stored = str(item.data(Qt.UserRole + 2) or "")
        if stored:
            if not _confirm(self, "从黑名单移除这一名？"):
                return
            self.store.remove_name(stored)
            self._show_list()
            self._show_history_scan(self._selected_scan())
            return
        dialog = AddNameDialog(shown, title="添加", parent=self)
        if dialog.exec() != QDialog.Accepted or dialog.deleted:
            return
        if self.store.add(dialog.name, dialog.detail, reasons=dialog.reasons) is None:
            return
        self._show_list()
        self._show_history_scan(self._selected_scan())

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
        if self._status_kind in ("idle", "watch"):
            self._sync_watch_idle()

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
            self.settings_label.setText("")
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
        self.settings_label.setText("")

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
        if not self.worker.request(fn):
            self._set_result("正在检查", "status", "check")
            self._unlock_foreground()
            return False
        self._check_started = time.perf_counter()
        self._set_result("正在检查", "status", "check")
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
                self._set_result(text, "hit", "error")
            return
        was_error = self._status_kind == "error"
        self._glance_error = ""
        if was_error:
            self._sync_watch_idle()
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
        elapsed = None
        if self._check_started is not None:
            elapsed = time.perf_counter() - self._check_started
            self._check_started = None
        if status == "err":
            self._note_watch(False)
            self._hide_panel_after_title()
            text = str(value)
            self._set_result(text, "hit", "error")
            return
        result: CheckResult = value
        self._note_watch(bool(result.header_found))
        brief, clear = self._brief(result)
        if result.header_found and result.names:
            outcome = self.store.add_scan(
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
            if outcome == "refreshed":
                brief = f"{brief}，已更新这条记录"
            elif outcome == "skipped":
                brief = f"{brief}，这一分钟已经记过"
        self._set_result(brief, "clear" if clear else "hit", "result")
        self._show_result(result)
        self._show_panel(result)
        if result.header_found and result.hits and not self.store.muted:
            try:
                play_chime(chime_path(self.store.root))
            except Exception:
                self._set_result("提示音没响。", "hit", "error")
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
        lines = []
        for slot in result.names:
            seat = seat_number(slot.index)
            text = "未看清" if slot.unclear else slot.visible
            lines.append(f"{seat}号  {text}")
        self.names_view.setPlainText("\n".join(lines))

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

    def _sync_watch_idle(self) -> None:
        if self.store.auto_capture:
            self._set_result("正在监控", "clear", "watch")
        else:
            self._set_result("未开启", "idle", "idle")

    def _set_result(self, text: str, tone: str = "status", kind: str = "result") -> None:
        self._status_kind = kind
        self._watch_tone = tone
        self._watch_full = text
        colors = {
            "clear": THEME["green"],
            "hit": THEME["red"],
            "idle": THEME["muted"],
            "status": THEME["text"],
        }
        self.watch_label.setObjectName(tone)
        self.watch_label.setToolTip(text)
        width = max(1, self.watch_label.maximumWidth())
        self.watch_label.setText(self.watch_label.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, width))
        self.watch_label.style().unpolish(self.watch_label)
        self.watch_label.style().polish(self.watch_label)
        self.watch_mark.setPixmap(_watch_mark(colors.get(tone, THEME["muted"])))
        self._set_tray(text)

    def _remember_size(self) -> None:
        if not hasattr(self, "store"):
            return
        width, height = self.width(), self.height()
        if width < 900 or height < 560:
            return
        if self.store.window_size == (width, height):
            return
        self.store.window_size = (width, height)
        self.store.save_settings()

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._remember_size()

    def copy_result(self) -> None:
        text = self.names_view.toPlainText().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)

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

    def _show_from_tray(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_tray(self, reason) -> None:
        from PySide6.QtWidgets import QSystemTrayIcon

        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._show_from_tray()

    def closeEvent(self, event) -> None:  # noqa: ANN001
        if event.spontaneous():
            event.ignore()
            self.hide()
            if not self._told_tray:
                self._told_tray = True
                self._set_tray("已缩到托盘，右键可退出")
            return
        self._remember_size()
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
