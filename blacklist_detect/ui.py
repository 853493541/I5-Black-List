"""Main window, tray status, and the always-on-top warning."""

from __future__ import annotations

import queue
import sys
import time
from datetime import datetime

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLayoutItem,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
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
from blacklist_detect.match import NameLabel, format_hit, match_label, seat_number, split_ellipsis
from blacklist_detect.model import Entry
from blacklist_detect.pipeline import CheckResult, Hit, NameSlot, check_frames, glance_title
from blacklist_detect.storage import Store, describe_entry, tag_text
from blacklist_detect.watch import GLANCE_INTERVAL_MS, LobbyWatch


def run_app() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("黑名单检测")
    app.setFont(chinese_font())
    _apply_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()


def _zh_clock(moment: datetime) -> str:
    period = "上午" if moment.hour < 12 else "下午"
    hour = moment.hour % 12 or 12
    if moment.minute == 0:
        return f"{period}{hour}点0分"
    return f"{period}{hour}点{moment.minute:02d}分"


def _local_moment(stamp: str) -> datetime | None:
    try:
        moment = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    now = datetime.now().astimezone()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=now.tzinfo)
    return moment.astimezone(now.tzinfo)


def _zh_date(stamp: str) -> str:
    moment = _local_moment(stamp)
    if moment is None:
        return ""
    return f"{moment.year}-{moment.month:02d}-{moment.day:02d}"


def _zh_ago(stamp: str) -> str:
    moment = _local_moment(stamp)
    if moment is None:
        return ""
    seconds = (datetime.now().astimezone() - moment).total_seconds()
    if seconds < 60:
        return "刚刚"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}分钟前"
    hours = int(seconds // 3600)
    if hours < 24:
        return f"{hours}小时前"
    days = int(seconds // 86400)
    if days < 30:
        return f"{days}天前"
    months = days // 30
    if months < 12:
        return f"{months}个月前"
    return f"{days // 365}年前"


def chinese_family() -> str:
    """A face that actually contains simplified Chinese. Qt does not fall back by itself."""
    from PySide6.QtGui import QFontDatabase

    installed = set(QFontDatabase.families())
    for name in (
        "Microsoft YaHei",
        "微软雅黑",
        "Microsoft YaHei UI",
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


class _FlowLayout(QLayout):
    """Pills sit on a row and wrap onto the next line."""

    def __init__(self, parent=None, gap: int = 8) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._gap = gap
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:  # noqa: ANN001
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: ANN201
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):  # noqa: ANN201
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):  # noqa: ANN201
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._arrange(width)

    def setGeometry(self, rect) -> None:  # noqa: ANN001
        super().setGeometry(rect)
        self._arrange(rect.width(), rect.topLeft())

    def sizeHint(self) -> QSize:
        width = 0
        height = 0
        for item in self._items:
            hint = item.sizeHint()
            width += hint.width()
            height = max(height, hint.height())
        if self._items:
            width += self._gap * (len(self._items) - 1)
        margins = self.contentsMargins()
        return QSize(width + margins.left() + margins.right(), height + margins.top() + margins.bottom())

    def minimumSize(self) -> QSize:
        return self.sizeHint()

    def _arrange(self, width: int, origin: QPoint | None = None) -> int:
        margins = self.contentsMargins()
        x = margins.left()
        y = margins.top()
        line_height = 0
        limit = max(0, width - margins.right())
        for item in self._items:
            hint = item.sizeHint()
            if x > margins.left() and x + hint.width() > limit:
                x = margins.left()
                y += line_height + self._gap
                line_height = 0
            if origin is not None:
                item.setGeometry(QRect(origin + QPoint(x, y), hint))
            x += hint.width() + self._gap
            line_height = max(line_height, hint.height())
        return y + line_height + margins.bottom()


class _FlowHost(QWidget):
    """Gives a wrapping pill row a real height so the next control is not covered."""

    def __init__(self) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        layout = self.layout()
        if layout is None:
            return 0
        return layout.heightForWidth(width)

    def sizeHint(self) -> QSize:
        layout = self.layout()
        if layout is None:
            return super().sizeHint()
        hint = layout.sizeHint()
        return QSize(max(hint.width(), 1), self.heightForWidth(max(hint.width(), 1)))


class _ColumnHeader(QHeaderView):
    """Arrow on a title means drag to reorder. A left-right arrow on the edge means resize."""

    def __init__(self, parent=None) -> None:
        super().__init__(Qt.Horizontal, parent)
        self.setMouseTracking(True)

    def _cursor_at(self, pos: int) -> Qt.CursorShape:
        logical = self.logicalIndexAt(pos)
        if logical < 0:
            return Qt.ArrowCursor
        left = self.sectionViewportPosition(logical)
        right = left + self.sectionSize(logical)
        if pos - left <= 8 or right - pos <= 8:
            return Qt.SplitHCursor
        return Qt.OpenHandCursor

    def mouseMoveEvent(self, event) -> None:  # noqa: ANN001
        super().mouseMoveEvent(event)
        pos = int(event.position().x())
        if event.buttons() & Qt.LeftButton and self._cursor_at(pos) != Qt.SplitHCursor:
            self.setCursor(Qt.ClosedHandCursor)
            return
        self.setCursor(self._cursor_at(pos))

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        self.unsetCursor()
        super().leaveEvent(event)

    def paintSection(self, painter, rect, logicalIndex) -> None:  # noqa: ANN001
        super().paintSection(painter, rect, logicalIndex)
        if self.visualIndex(logicalIndex) == self.count() - 1:
            return
        painter.save()
        painter.setPen(QColor(THEME["line"]))
        painter.drawLine(rect.right(), rect.top() + 6, rect.right(), rect.bottom() - 6)
        painter.restore()


class TagPill(QWidget):
    """A painted capsule. Stylesheets were painting flat color over the words."""

    def __init__(self, text: str, on_remove=None, *, on_click=None) -> None:
        super().__init__()
        self._text = text
        self._on_remove = on_remove
        self._on_click = on_click
        self._wash = THEME["red_wash"]
        self._ink = THEME["red"]
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        face = chinese_font(9)
        face.setWeight(QFont.Weight.DemiBold)
        self.setFont(face)
        if on_remove is None and on_click is None:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        else:
            self.setMouseTracking(True)
            self.setCursor(Qt.PointingHandCursor)

    def sizeHint(self) -> QSize:
        metrics = QFontMetrics(self.font())
        pad = 8
        close = 16 if self._on_remove is not None else 0
        width = metrics.horizontalAdvance(self._text) + pad * 2 + close
        return QSize(width, metrics.height() + 6)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def _close_box(self) -> QRect:
        rect = self.rect()
        return QRect(rect.right() - 16, rect.top(), 16, rect.height())

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        body = QRect(self.rect())
        body.adjust(0, 1, -1, -1)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._wash))
        radius = body.height() / 2
        painter.drawRoundedRect(body, radius, radius)
        painter.setPen(QColor(self._ink))
        painter.setFont(self.font())
        text_box = QRect(body)
        if self._on_remove is not None:
            text_box.adjust(8, 0, -16, 0)
            painter.drawText(text_box, Qt.AlignVCenter | Qt.AlignLeft, self._text)
            painter.drawText(self._close_box(), Qt.AlignCenter, "×")
        else:
            text_box.adjust(8, 0, -8, 0)
            painter.drawText(text_box, Qt.AlignCenter, self._text)

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        if self._on_click is not None:
            self._on_click()
            return
        if self._on_remove is not None and self._close_box().contains(event.position().toPoint()):
            self._on_remove()
            return
        super().mousePressEvent(event)


class TagAdd(QWidget):
    """A tag that is not on this person. Plain text, so it does not look applied."""

    def __init__(self, text: str, on_click) -> None:
        super().__init__()
        self._name = text
        self._on_click = on_click
        self._hover = False
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        face = chinese_font(9)
        self.setFont(face)

    def sizeHint(self) -> QSize:
        metrics = QFontMetrics(self.font())
        return QSize(metrics.horizontalAdvance(f"＋{self._name}") + 4, metrics.height() + 6)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def enterEvent(self, event) -> None:  # noqa: ANN001
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(QColor(THEME["text"] if self._hover else THEME["muted"]))
        painter.drawText(self.rect(), Qt.AlignVCenter | Qt.AlignLeft, f"＋{self._name}")

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.LeftButton:
            self._on_click()
            return
        super().mousePressEvent(event)


class NewTagButton(QPushButton):
    """Sits after the tag pills and opens the new-tag dialog."""

    def __init__(self) -> None:
        super().__init__("新标签")
        self.setObjectName("tagNew")
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFont(self._face())
        self._hover = False

    @staticmethod
    def _face() -> QFont:
        face = chinese_font(9)
        face.setWeight(QFont.Weight.DemiBold)
        return face

    def sizeHint(self) -> QSize:
        metrics = QFontMetrics(self._face())
        return QSize(metrics.horizontalAdvance(self.text()) + 16, metrics.height() + 6)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def enterEvent(self, event) -> None:  # noqa: ANN001
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        face = self._face()
        painter.setFont(face)
        body = QRect(self.rect())
        body.adjust(0, 1, -1, -1)
        painter.setPen(QColor(THEME["button_line"]))
        painter.setBrush(QColor(THEME["hover"] if self._hover else THEME["button"]))
        painter.drawRoundedRect(body, body.height() / 2, body.height() / 2)
        painter.setPen(QColor(THEME["text"]))
        text_box = QRect(body)
        text_box.adjust(8, 0, -8, 0)
        painter.drawText(text_box, Qt.AlignCenter, self.text())


def _clear_layout(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


def chinese_font(point_size: int = 11) -> QFont:
    font = QFont(chinese_family())
    font.setPointSize(point_size)
    font.setWeight(QFont.Weight.Normal)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.NoSubpixelAntialias)
    return font


def ui_font() -> QFont:
    """The same Chinese face as the page, at full weight so the strokes stay together."""
    font = chinese_font()
    font.setWeight(QFont.Weight.Bold)
    return font


# One inset for the whole window. Pages share the same gap so the tabs line up.
PAD = 16
GAP = 12

def _palette(
    accent: str,
    accent_line: str,
    accent_hover: str,
    accent_press: str,
    on_accent: str,
) -> dict[str, str]:
    # Shared paper, ink, and borders. The theme swatch only changes the accent.
    return {
        "bg": "#faf6ec",
        "text": "#33291a",
        "muted": "#6f6350",
        "surface": "#fffdf7",
        "line": "#e7dcc7",
        "button": "#fffdf7",
        "button_line": "#e7dcc7",
        "selected": "#f4ead9",
        "head": "#f4ead9",
        "head_text": "#33291a",
        "gold": accent,
        "gold_line": accent_line,
        "on_gold": on_accent,
        "green": "#1c7a3e",
        "green_wash": "#f3fbf6",
        "green_hover": "#e3f6eb",
        "red": "#c23b2e",
        "red_wash": "#fff6f6",
        "red_hover": "#fde4e1",
        "gray": "#6b7280",
        "gray_wash": "#f3f4f6",
        "gray_hover": "#e6e8ec",
        "add": accent,
        "danger": "#a33b2c",
        "hover": "#f4ead9",
        "gold_hover": accent_hover,
        "gold_press": accent_press,
        "danger_hover": "#f8e6e1",
    }


THEMES = {
    "蓝色": _palette("#12325a", "#2c6cb3", "#1a4578", "#0c243f", "#f4f8ff"),
    "棕色": _palette("#6b4428", "#a67c52", "#7d5334", "#4a2e1a", "#fff8f2"),
    "紫色": _palette("#4a2d73", "#7a5caf", "#5c3b8c", "#321d52", "#f8f5ff"),
    "绿色": _palette("#1b5340", "#3d8f6e", "#24664e", "#12382b", "#f4fbf7"),
    "红色": _palette("#a24f28", "#c46a3e", "#92471f", "#6e3416", "#fdf6ec"),
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
            QWidget#root, QLabel, QLineEdit, QPlainTextEdit, QCheckBox,
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
            QTabBar {{ height: 0; max-height: 0; }}
            QWidget#tabHeader {{
                background: transparent;
                border: none;
                border-bottom: 1px solid {t["line"]};
            }}
            QWidget#tabHeader QLabel {{ background: transparent; }}
            QLabel#sub {{ font-family: "{family}"; color: {t["muted"]}; }}
            QLabel#clear {{
                font-family: "{family}";
                font-size: 14px;
                font-weight: 500;
                color: {t["green"]};
                background: transparent;
            }}
            QLabel#hit {{
                font-family: "{family}";
                font-size: 14px;
                font-weight: 500;
                color: {t["red"]};
                background: transparent;
            }}
            QLabel#idle {{
                font-family: "{family}";
                font-size: 14px;
                font-weight: 500;
                color: {t["muted"]};
                background: transparent;
            }}
            QLabel#status {{
                font-family: "{family}";
                font-size: 14px;
                font-weight: 500;
                color: {t["text"]};
                background: transparent;
            }}
            QLineEdit {{
                background: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["line"]};
                border-radius: 8px;
                padding: 4px 12px;
                min-height: 28px;
            }}
            QLineEdit:focus {{
                border: 1px solid {t["gold"]};
            }}
            QLineEdit:disabled {{
                color: {t["muted"]};
                background: {t["head"]};
                border: 1px solid {t["line"]};
            }}
            QPlainTextEdit, QTableWidget, QListWidget {{
                background: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["line"]};
                border-radius: 8px;
                padding: 8px 12px;
            }}
            QListWidget::item {{
                font-family: "{family}";
                background: transparent;
                color: {t["text"]};
                padding: 8px 12px;
                border: none;
            }}
            QListWidget#history {{ padding: 0; outline: none; }}
            QListWidget#history:focus {{
                border: 1px solid {t["line"]};
                outline: none;
            }}
            QListWidget#history::item {{ padding: 0; border: none; outline: none; }}
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
            QTableWidget#recordNames::item,
            QTableWidget#recordNames::item:hover,
            QTableWidget#recordNames::item:selected {{
                background: transparent;
            }}
            QTableWidget#blacklist {{
                background: {t["surface"]};
                padding: 0;
                outline: none;
            }}
            QTableWidget#blacklist:focus {{
                border: 1px solid {t["line"]};
                outline: none;
            }}
            QTableWidget#blacklist::item {{
                background: {t["surface"]};
                padding: 10px 14px;
                border: none;
                outline: none;
            }}
            QTableWidget#blacklist::item:hover {{
                background: {t["surface"]};
                color: {t["text"]};
            }}
            QTableWidget#blacklist::item:selected,
            QTableWidget#blacklist::item:selected:hover {{
                background: {t["hover"]};
                color: {t["text"]};
            }}
            QHeaderView {{ background: {t["surface"]}; }}
            QHeaderView::section, QTableCornerButton::section {{
                background: {t["head"]};
                color: {t["head_text"]};
                border: none;
                padding: 8px 14px;
                font-weight: 500;
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
            QWidget#settingsCard {{
                background: {t["surface"]};
                border: 1px solid {t["line"]};
                border-radius: 12px;
            }}
            QWidget#settingsRow {{
                background: transparent;
                border: none;
                border-bottom: 1px solid {t["line"]};
            }}
            QWidget#settingsRowLast {{
                background: transparent;
                border: none;
            }}
            QPushButton {{
                background: {t["button"]};
                color: {t["text"]};
                border: 1px solid {t["button_line"]};
                border-radius: 8px;
                padding: 6px 14px;
                min-height: 28px;
            }}
            QPushButton#primary {{
                background: {t["gold"]};
                border-color: {t["gold_line"]};
                color: {t["on_gold"]};
            }}
            QPushButton#danger {{
                color: {t["danger"]};
                border-color: {t["danger"]};
            }}
            QPushButton#rowDelete {{
                background: transparent;
                color: {t["danger"]};
                border: none;
                border-radius: 4px;
                padding: 0;
                min-height: 28px;
                font-size: 22px;
                font-weight: 700;
            }}
            QPushButton#rowDelete:hover {{
                background: {t["danger_hover"]};
                color: {t["danger"]};
            }}
            QCheckBox {{
                spacing: 8px;
                min-height: 28px;
                color: {t["text"]};
                background: transparent;
            }}
            """ + _control_hover() + _menu_style(family) + f"""
            QPushButton#tab {{
                color: {t["muted"]};
                background: transparent;
                border: none;
                border-radius: 8px;
                padding: 6px 14px;
                margin: 0 2px;
                min-height: 28px;
            }}
            QPushButton#tab:hover {{
                color: {t["text"]};
                background: {t["hover"]};
                border: none;
            }}
            QPushButton#tab:checked,
            QPushButton#tab:checked:hover,
            QPushButton#tab:checked:pressed {{
                color: {t["gold"]};
                background: {t["selected"]};
                border: none;
            }}
            QPushButton#tab:pressed {{
                background: {t["hover"]};
                border: none;
            }}
            QPushButton#mode:checked,
            QPushButton#mode:checked:hover {{
                background: {t["gold"]};
                border-color: {t["gold_line"]};
                color: {t["on_gold"]};
            }}
            QPushButton#tagNew {{
                background: transparent;
                border: none;
                padding: 0;
                margin: 0;
                min-width: 0;
                min-height: 0;
            }}
            """


def _dialog_style(family: str) -> str:
    t = THEME
    return f"""
            QDialog, QMessageBox, QLabel, QLineEdit, QPushButton, QCheckBox {{
                font-family: "{family}";
                background: {t["bg"]};
                color: {t["text"]};
            }}
            QLabel#sub {{ font-family: "{family}"; color: {t["muted"]}; background: transparent; }}
            QLineEdit {{
                background: {t["surface"]};
                border: 1px solid {t["line"]};
                border-radius: 8px;
                padding: 4px 10px;
                min-height: 28px;
            }}
            QLineEdit:focus {{ border: 1px solid {t["gold"]}; }}
            QCheckBox {{
                background: transparent;
                spacing: 8px;
                min-height: 28px;
                padding: 2px 4px;
                border-radius: 4px;
            }}
            QPushButton {{
                background: {t["button"]};
                color: {t["text"]};
                border: 1px solid {t["button_line"]};
                border-radius: 8px;
                padding: 6px 14px;
                min-height: 28px;
            }}
            QPushButton#primary {{
                background: {t["gold"]};
                border-color: {t["gold_line"]};
                color: {t["on_gold"]};
            }}
            QPushButton#danger {{ color: {t["danger"]}; }}
            """ + _control_hover() + f"""
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
    size = 8 * ratio
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
    inset = 2 * ratio
    painter.drawEllipse(inset, inset, size - inset * 2, size - inset * 2)
    painter.end()
    return pixmap


class ThemeSwatch(QWidget):
    """One theme, shown as its color only."""

    _square = 28
    _badge = 16

    def __init__(self, name: str, color: str, on_click) -> None:
        super().__init__()
        self._name = name
        self._color = color
        self._on_click = on_click
        self._selected = False
        hang = self._badge // 2
        self.setFixedSize(self._square + hang, self._square + hang)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip(name)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        hang = self._badge // 2
        painter.fillRect(0, hang, self._square, self._square, QColor(self._color))
        if not self._selected:
            return
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#1c9a4b"))
        painter.drawEllipse(self._square - hang, 0, self._badge, self._badge)
        center_x = self._square
        center_y = hang
        pen = QPen(QColor("#ffffff"), 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(center_x - 4, center_y, center_x - 1, center_y + 3)
        painter.drawLine(center_x - 1, center_y + 3, center_x + 4, center_y - 3)

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.LeftButton:
            self._on_click()
            return
        super().mousePressEvent(event)


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


class TagEditDialog(QDialog):
    """Rename one tag, or delete it from the list and from every name."""

    def __init__(self, tag: str, catalog: tuple[str, ...], parent=None) -> None:
        super().__init__(parent)
        self.original = tag
        self.catalog = catalog
        self.renamed = tag
        self.deleted = False
        self.setWindowTitle("修改标签")
        self.setFont(chinese_font())
        self.setStyleSheet(_dialog_style(chinese_family()))
        _caption_color(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAD, PAD, PAD, PAD)
        layout.setSpacing(GAP)
        layout.addWidget(QLabel("标签"))
        self.name_edit = QLineEdit(tag)
        layout.addWidget(self.name_edit)
        self.error = QLabel("")
        self.error.setObjectName("error")
        layout.addWidget(self.error)
        self.name_edit.textChanged.connect(lambda _text: self.error.setText(""))
        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
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
        save = QPushButton("保存")
        save.setObjectName("primary")
        save.setAutoDefault(True)
        save.setDefault(True)
        save.clicked.connect(self._accept)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)
        self.setMinimumWidth(360)
        self.name_edit.returnPressed.connect(self._accept)
        _pointing(self)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)

    def _accept(self) -> None:
        from blacklist_detect.storage import clean_tag

        renamed = clean_tag(self.name_edit.text())
        if not renamed:
            self.error.setText("请填写标签")
            return
        if renamed != self.original and renamed in self.catalog:
            self.error.setText("已有这个标签")
            return
        self.error.setText("")
        self.renamed = renamed
        self.deleted = False
        self.accept()

    def _delete(self) -> None:
        names = []
        parent = self.parent()
        entries = getattr(getattr(parent, "store", None), "entries", ())
        for entry in entries:
            if self.original in entry.tags:
                names.append(entry.name)
        if not names:
            text = f"没有名字使用「{self.original}」。确定删除？"
        else:
            shown = "、".join(names[:6])
            if len(names) > 6:
                shown += "等"
            text = f"{len(names)} 个名字使用「{self.original}」：{shown}。确定删除？"
        if not _confirm(self, text):
            return
        self.deleted = True
        self.accept()


class TagCreateDialog(QDialog):
    """Name a tag that is not in the list yet."""

    def __init__(self, catalog: tuple[str, ...], parent=None) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.created = ""
        self.setWindowTitle("新标签")
        self.setFont(chinese_font())
        self.setStyleSheet(_dialog_style(chinese_family()))
        _caption_color(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAD, PAD, PAD, PAD)
        layout.setSpacing(GAP)
        layout.addWidget(QLabel("标签"))
        self.name_edit = QLineEdit()
        layout.addWidget(self.name_edit)
        self.error = QLabel("")
        self.error.setObjectName("error")
        layout.addWidget(self.error)
        self.name_edit.textChanged.connect(lambda _text: self.error.setText(""))
        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        buttons.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setAutoDefault(False)
        cancel.setDefault(False)
        cancel.clicked.connect(self.reject)
        add = QPushButton("添加")
        add.setObjectName("primary")
        add.setAutoDefault(True)
        add.setDefault(True)
        add.clicked.connect(self._accept)
        buttons.addWidget(cancel)
        buttons.addWidget(add)
        layout.addLayout(buttons)
        self.setMinimumWidth(360)
        self.name_edit.returnPressed.connect(self._accept)
        _pointing(self)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)

    def _accept(self) -> None:
        from blacklist_detect.storage import clean_tag

        tag = clean_tag(self.name_edit.text())
        if not tag:
            self.error.setText("请填写标签")
            return
        if tag in self.catalog:
            self.error.setText("已有这个标签")
            return
        self.error.setText("")
        self.created = tag
        self.accept()


class AddNameDialog(QDialog):
    """One player. Click a tag from 设置 to put it on this record."""

    def __init__(
        self,
        name: str = "",
        tags: tuple[str, ...] = (),
        detail: str = "",
        title: str = "添加",
        allow_delete: bool = False,
        catalog: tuple[str, ...] = (),
        added_at: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        from blacklist_detect.storage import TAGS

        self.setWindowTitle(title)
        self.name = name
        self.tags: tuple[str, ...] = tuple(tags)
        self.detail = detail
        self.catalog = list(catalog or TAGS)
        self.picked = [tag for tag in self.catalog if tag in tags]
        self.picked.extend(tag for tag in tags if tag not in self.picked)
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
        layout.addWidget(QLabel("标签"))
        self.tag_host = _FlowHost()
        self.tag_rows = _FlowLayout(self.tag_host, gap=6)
        layout.addWidget(self.tag_host)
        self.tag_empty = QLabel("还没有")
        self.tag_empty.setObjectName("sub")
        layout.addWidget(self.tag_empty)
        self.add_label = QLabel("可加")
        layout.addWidget(self.add_label)
        self.add_host = _FlowHost()
        self.add_rows = _FlowLayout(self.add_host, gap=10)
        layout.addWidget(self.add_host)
        self._refresh_tags()
        layout.addWidget(QLabel("原因"))
        self.detail_edit = QLineEdit(detail)
        layout.addWidget(self.detail_edit)
        added_on = _zh_date(added_at)
        if added_on:
            layout.addWidget(QLabel("添加时间"))
            self.added_on = QLabel(added_on)
            self.added_on.setObjectName("sub")
            layout.addWidget(self.added_on)
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

    def _refresh_tags(self) -> None:
        _clear_layout(self.tag_rows)
        for tag in self.picked:
            self.tag_rows.addWidget(TagPill(tag, lambda picked=tag: self._detach_tag(picked)))
        self.tag_host.updateGeometry()
        self.tag_host.setVisible(bool(self.picked))
        self.tag_empty.setVisible(not self.picked)
        _clear_layout(self.add_rows)
        spare = [tag for tag in self.catalog if tag not in self.picked]
        for tag in spare:
            self.add_rows.addWidget(TagAdd(tag, lambda picked=tag: self._attach_tag(picked)))
        self.add_host.updateGeometry()
        self.add_label.setVisible(bool(spare))
        self.add_host.setVisible(bool(spare))

    def _toggle_tag(self, tag: str) -> None:
        if tag in self.picked:
            self._detach_tag(tag)
            return
        self._attach_tag(tag)

    def _attach_tag(self, tag: str | None = None) -> None:
        chosen = tag or ""
        if not chosen or chosen in self.picked or chosen not in self.catalog:
            return
        self.picked.append(chosen)
        self._refresh_tags()

    def _detach_tag(self, tag: str) -> None:
        self.picked = [item for item in self.picked if item != tag]
        self._refresh_tags()

    def _chosen(self) -> tuple[str, ...]:
        ordered = [tag for tag in self.catalog if tag in self.picked]
        ordered.extend(tag for tag in self.picked if tag not in ordered)
        return tuple(ordered)

    def _accept(self) -> None:
        if not self.name_edit.text().strip():
            self.name_error.setText("请填写名字")
            return
        self.name_error.setText("")
        self.name = self.name_edit.text()
        self.tags = self._chosen()
        self.detail = self.detail_edit.text()
        self.deleted = False
        self.accept()

    def _delete(self) -> None:
        if not _confirm(self, "删除这一名？"):
            return
        self.deleted = True
        self.accept()


class BatchAddDialog(QDialog):
    """Many names from one paste. Spaces separate names, or each person is 名字（说明）."""

    def __init__(self, catalog: tuple[str, ...] = (), parent=None) -> None:
        super().__init__(parent)
        from blacklist_detect.storage import TAGS

        self.setWindowTitle("批量添加")
        self.names: list[str] = []
        self.annotated: list[tuple[str, tuple[str, ...], str]] | None = None
        self.catalog = catalog or TAGS
        self.setFont(chinese_font())
        self.setStyleSheet(_dialog_style(chinese_family()))
        _caption_color(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAD, PAD, PAD, PAD)
        layout.setSpacing(GAP)
        layout.addWidget(QLabel("一行一个：名字，炸房，贴脸，原因"))
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("把名字粘在这里")
        self.edit.setMinimumHeight(180)
        layout.addWidget(self.edit)
        self.error = QLabel("")
        self.error.setObjectName("error")
        layout.addWidget(self.error)
        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        buttons.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setAutoDefault(False)
        cancel.setDefault(False)
        cancel.clicked.connect(self.reject)
        confirm = QPushButton("添加")
        confirm.setObjectName("primary")
        confirm.setAutoDefault(True)
        confirm.setDefault(True)
        confirm.clicked.connect(self._accept)
        buttons.addWidget(cancel)
        buttons.addWidget(confirm)
        layout.addLayout(buttons)
        self.setMinimumWidth(420)
        _pointing(self)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)

    def _accept(self) -> None:
        from blacklist_detect.storage import annotated_from_block, names_from_block, parse_blacklist

        text = self.edit.toPlainText()
        self.annotated = annotated_from_block(text, self.catalog)
        if self.annotated is None and ("," in text or "，" in text):
            self.annotated = parse_blacklist(text, self.catalog) or None
        if self.annotated is None:
            self.names = names_from_block(text)
        else:
            self.names = [name for name, _tags, _reason in self.annotated]
        if not self.names:
            self.error.setText("没有名字")
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
                border-radius: 8px;
                font-family: "{family}";
                font-size: 14px;
            }}
            QPushButton {{
                background: {t["button"]};
                color: {t["text"]};
                border: 1px solid {t["button_line"]};
                border-radius: 8px;
                padding: 6px 14px;
                min-height: 28px;
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
                border-radius: 8px;
                padding: 6px 14px;
                min-height: 28px;
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


class _PlainItemDelegate(QStyledItemDelegate):
    """Selection stays a wash. A click does not draw the black focus box."""

    def paint(self, painter, option, index) -> None:  # noqa: ANN001
        view = self.parent()
        if isinstance(view, QTableWidget) and view.objectName() == "blacklist" and index.column() == 1:
            drawn = QStyleOptionViewItem(option)
            self.initStyleOption(drawn, index)
            drawn.state = drawn.state & ~QStyle.State_HasFocus
            drawn.text = ""
            view.style().drawControl(QStyle.CE_ItemViewItem, drawn, painter, view)
            return
        option.state = option.state & ~QStyle.State_HasFocus
        super().paint(painter, option, index)


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
        self._rescan_active = False
        self._history_hover = (-1, -1)
        self._closed_days: set[str] = set()
        self._check_started: float | None = None
        self._release_foreground = False
        self._told_tray = False
        self._status_kind = "idle"
        self._watch_tone = "idle"
        self._watch_full = "未开启"
        self._blacklist_sort: tuple[int, bool] | None = None
        self._blacklist_hover = -1
        self._build()
        self._apply_style()
        _caption_color(self)
        self._show_list()
        self._reload_history()
        self._restore_hotkey()
        if self.store.auto_capture:
            app = QApplication.instance()
            if app is not None and app.platformName() == "offscreen":
                self._watch_timer.setInterval(60_000)
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
        self.tabs.tabBar().hide()
        self.tabs.currentChanged.connect(self._sync_tab_buttons)
        header = QWidget()
        header.setObjectName("tabHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(0, 0, 0, 8)
        header_row.setSpacing(6)
        self._tab_buttons: list[QPushButton] = []
        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        for index in range(self.tabs.count()):
            button = QPushButton(self.tabs.tabText(index))
            button.setObjectName("tab")
            button.setFont(ui_font())
            button.setCheckable(True)
            button.setFocusPolicy(Qt.NoFocus)
            button.setCursor(Qt.PointingHandCursor)
            self._tab_group.addButton(button, index)
            self._tab_buttons.append(button)
            header_row.addWidget(button, 0, Qt.AlignVCenter)
        self._tab_group.idClicked.connect(self.tabs.setCurrentIndex)
        header_row.addStretch(1)
        self.watch_mark = QLabel()
        self.watch_mark.setPixmap(_watch_mark(THEME["muted"]))
        self.watch_label = QLabel("未开启")
        self.watch_label.setObjectName("idle")
        self.watch_label.setMaximumWidth(200)
        self.watch_label.setFont(chinese_font(14))
        header_row.addWidget(self.watch_mark, 0, Qt.AlignVCenter)
        header_row.addWidget(self.watch_label, 0, Qt.AlignVCenter)
        self._sync_tab_buttons(self.tabs.currentIndex())
        outer.addWidget(header)
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
        add_row = QHBoxLayout()
        add_row.setSpacing(GAP)
        self.list_hint = QLabel("还没有名字")
        self.list_hint.setObjectName("sub")
        add_row.addWidget(self.list_hint, 0, Qt.AlignVCenter)
        add_row.addStretch(1)
        clear = QPushButton("清空列表")
        clear.clicked.connect(self._ask_clear_list)
        add_row.addWidget(clear)
        batch = QPushButton("批量添加")
        batch.clicked.connect(self._add_many_by_dialog)
        add = QPushButton("添加")
        add.setObjectName("primary")
        add.clicked.connect(self._add_by_dialog)
        add_row.addWidget(batch)
        add_row.addWidget(add)
        self.blacklist_table = QTableWidget(0, 4)
        self.blacklist_table.setObjectName("blacklist")
        self.blacklist_table.setHorizontalHeader(_ColumnHeader(self.blacklist_table))
        self.blacklist_table.setHorizontalHeaderLabels(["名字", "标签", "原因", "最后遇到"])
        for column in range(4):
            item = self.blacklist_table.horizontalHeaderItem(column)
            if item is not None:
                item.setToolTip("拖动换顺序，拖边缘改宽度")
        header = self.blacklist_table.horizontalHeader()
        header.setStretchLastSection(False)
        for column in range(4):
            header.setSectionResizeMode(column, header.ResizeMode.Interactive)
        header.setMinimumSectionSize(72)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionsClickable(True)
        header.setSectionsMovable(True)
        header.setHighlightSections(False)
        header.setSortIndicatorShown(False)
        header.sectionClicked.connect(self._sort_blacklist)
        header.sectionMoved.connect(self._save_column_order)
        header.sectionResized.connect(self._save_column_width)
        self._apply_column_widths()
        self._apply_column_order()
        self.blacklist_table.verticalHeader().setVisible(False)
        self.blacklist_table.verticalHeader().setDefaultSectionSize(44)
        self.blacklist_table.setSelectionMode(QTableWidget.SingleSelection)
        self.blacklist_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.blacklist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.blacklist_table.setShowGrid(False)
        self.blacklist_table.setAutoScroll(False)
        self.blacklist_table.setFocusPolicy(Qt.NoFocus)
        self.blacklist_table.setItemDelegate(_PlainItemDelegate(self.blacklist_table))
        self.blacklist_table.setMouseTracking(True)
        self.blacklist_table.viewport().setMouseTracking(True)
        self.blacklist_table.viewport().installEventFilter(self)
        self.blacklist_table.setCursor(Qt.PointingHandCursor)
        self.blacklist_table.cellEntered.connect(self._hover_blacklist_row)
        self.blacklist_table.cellClicked.connect(self._edit_row)
        layout.addWidget(self.blacklist_table, 1)
        layout.addLayout(add_row)
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
        self.history_list.setFocusPolicy(Qt.NoFocus)
        self.history_list.setItemDelegate(_PlainItemDelegate(self.history_list))
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
        catalog = QLabel("模仿者游戏（12人狂欢场）")
        catalog.setFont(chinese_font())
        head.addWidget(catalog)
        head.addStretch(1)
        names.addWidget(head_bar)
        self.history_table = QTableWidget(0, 2)
        self.history_table.setObjectName("recordNames")
        self.history_table.horizontalHeader().setVisible(False)
        header = self.history_table.horizontalHeader()
        header.setStretchLastSection(True)
        for column in range(2):
            header.setSectionResizeMode(column, header.ResizeMode.Stretch)
        self.history_table.setCursor(Qt.PointingHandCursor)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.verticalHeader().setDefaultSectionSize(40)
        self.history_table.setSelectionMode(QTableWidget.NoSelection)
        self.history_table.setFocusPolicy(Qt.NoFocus)
        self.history_table.setItemDelegate(_PlainItemDelegate(self.history_table))
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
        metrics = QFontMetrics(chinese_font())
        label_width = metrics.horizontalAdvance("我的角色名称")
        name_width = metrics.horizontalAdvance("中" * 7) + 28
        card = QWidget()
        card.setObjectName("settingsCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        def add_row(label: str, body, *, top: bool = False, last: bool = False) -> None:
            host = QWidget()
            host.setObjectName("settingsRowLast" if last else "settingsRow")
            host.setAttribute(Qt.WA_StyledBackground, True)
            line = QHBoxLayout(host)
            line.setContentsMargins(16, 14, 16, 14)
            line.setSpacing(24)
            text = QLabel(label)
            text.setMinimumWidth(label_width)
            align = Qt.AlignTop if top else Qt.AlignVCenter
            line.addWidget(text, 0, align)
            if isinstance(body, QLayout):
                line.addLayout(body, 1)
            else:
                line.addWidget(body, 0, align)
                line.addStretch(1)
            card_layout.addWidget(host)

        self.player_edit = QLineEdit(self.store.player_name)
        self.player_edit.setPlaceholderText("游戏里的名字")
        self.player_edit.editingFinished.connect(self._save_player_name)
        self.player_edit.setFixedWidth(name_width)
        add_row("我的角色名称", self.player_edit)
        self.tag_settings = QVBoxLayout()
        self.tag_settings.setSpacing(0)
        self.tag_settings.setContentsMargins(0, 2, 0, 0)
        self._fill_tag_settings()
        add_row("我的标签", self.tag_settings, top=True)
        modes = QHBoxLayout()
        modes.setSpacing(GAP)
        self.auto_on = QPushButton("自动检查")
        self.auto_off = QPushButton("手动截图")
        self.auto_group = QButtonGroup(self)
        self.auto_group.setExclusive(True)
        mode_width = metrics.horizontalAdvance("手动截图") + 32
        for button in (self.auto_on, self.auto_off):
            button.setObjectName("mode")
            button.setCheckable(True)
            button.setFixedWidth(mode_width)
            button.setFocusPolicy(Qt.NoFocus)
            button.setCursor(Qt.PointingHandCursor)
            button.setAutoDefault(False)
            self.auto_group.addButton(button)
            modes.addWidget(button)
        self.hotkey_edit = QLineEdit()
        self.hotkey_edit.setReadOnly(True)
        self.hotkey_edit.setPlaceholderText("无")
        self.hotkey_edit.setFixedWidth(name_width)
        self.hotkey_edit.setCursor(Qt.PointingHandCursor)
        self.hotkey_edit.installEventFilter(self)
        modes.addWidget(self.hotkey_edit)
        modes.addStretch(1)
        self.auto_on.setChecked(self.store.auto_capture)
        self.auto_off.setChecked(not self.store.auto_capture)
        self.auto_on.clicked.connect(lambda: self._toggle_auto(True))
        self.auto_off.clicked.connect(lambda: self._toggle_auto(False))
        add_row("", modes)
        themes = QHBoxLayout()
        themes.setSpacing(8)
        self.theme_buttons: dict[str, ThemeSwatch] = {}
        for name in THEMES:
            swatch = ThemeSwatch(name, THEMES[name]["gold"], lambda picked=name: self._set_theme(picked))
            self.theme_buttons[name] = swatch
            themes.addWidget(swatch)
        themes.addStretch(1)
        add_row("主题", themes)
        reset = QPushButton("清除全部数据")
        reset.setObjectName("danger")
        reset.setFont(ui_font())
        self.reset_button = reset
        reset.setAutoDefault(False)
        reset.setCursor(Qt.PointingHandCursor)
        reset.clicked.connect(self._ask_reset)
        add_row("", reset, last=True)
        layout.addWidget(card)
        self.settings_label = QLabel("")
        self.settings_label.setObjectName("sub")
        self.settings_label.setWordWrap(True)
        self.settings_label.hide()
        layout.addWidget(self.settings_label)
        layout.addStretch(1)
        return page

    def _fill_tag_settings(self) -> None:
        while self.tag_settings.count():
            item = self.tag_settings.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        host = _FlowHost()
        host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        flow = _FlowLayout(host, gap=6)
        for tag in self.store.tag_catalog():
            flow.addWidget(TagPill(tag, on_click=lambda picked=tag: self._edit_settings_tag(picked)))
        create = NewTagButton()
        create.clicked.connect(self._create_settings_tag)
        flow.addWidget(create)
        self.tag_settings.addWidget(host)

    def _create_settings_tag(self) -> None:
        dialog = TagCreateDialog(self.store.tag_catalog(), parent=self)
        if dialog.exec() != QDialog.Accepted or not dialog.created:
            return
        if not self.store.add_custom_tag(dialog.created):
            return
        self.store.save_settings()
        self._fill_tag_settings()

    def _edit_settings_tag(self, tag: str) -> None:
        dialog = TagEditDialog(tag, self.store.tag_catalog(), parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        if dialog.deleted:
            if self.store.remove_custom_tag(tag):
                self._refresh_tag_views()
            return
        if dialog.renamed == tag:
            return
        if self.store.rename_tag(tag, dialog.renamed) == "renamed":
            self._refresh_tag_views()

    def _refresh_tag_views(self) -> None:
        self._fill_tag_settings()
        self._show_list()
        self._show_history_scan(self._selected_scan())

    def _remove_settings_tag(self, tag: str) -> None:
        names = [entry.name for entry in self.store.entries if tag in entry.tags]
        if not names:
            text = f"没有名字使用「{tag}」。确定删除？"
        else:
            shown = "、".join(names[:6])
            if len(names) > 6:
                shown += "等"
            text = f"{len(names)} 个名字使用「{tag}」：{shown}。确定删除？"
        if not _confirm(self, text):
            return
        if not self.store.remove_custom_tag(tag):
            return
        self._refresh_tag_views()

    def _set_settings_note(self, text: str) -> None:
        self.settings_label.setText(text)
        self.settings_label.setVisible(bool(text))

    def _ask_reset(self) -> None:
        if not _confirm(self, "清除全部数据会清空我的角色名称、记录、黑名单和设置。确定清除？"):
            return
        self.store.reset()
        self.hotkey.clear()
        self.player_edit.setText("")
        self.hotkey_edit.clearFocus()
        self._show_hotkey()
        self._sync_hotkey_mode()
        self._set_settings_note("")
        self.auto_on.setChecked(True)
        self.auto_off.setChecked(False)
        if not self._watch_timer.isActive():
            self.watch = LobbyWatch()
            self._watch_timer.start()
        self._sync_watch_idle()
        use_theme(self.store.theme)
        icon = _icon()
        self.setWindowIcon(icon)
        if self.tray is not None:
            self.tray.setIcon(icon)
        self._apply_style()
        _caption_color(self)
        self.warning.apply_theme()
        self.clear_notice.apply_theme()
        self._apply_column_widths()
        self._apply_column_order()
        self._panel_hide_timer.stop()
        self.panel.hide()
        self._reload_history()

    def _save_player_name(self) -> None:
        name = self.player_edit.text().strip()
        if name == self.store.player_name:
            return
        self.store.player_name = name
        self.store.save_settings()
        self._show_history_scan(self._selected_scan())

    def _is_my_name(self, shown: str) -> bool:
        mine = self.store.player_name
        if not mine or not shown:
            return False
        return bool(match_label(NameLabel(raw=shown, visible=shown, truncated=False), [Entry(mine)]))

    def _apply_style(self) -> None:
        _apply_theme()
        self.setFont(chinese_font())
        self.setStyleSheet(_window_style(chinese_family()))
        self.setFont(chinese_font())
        for button in getattr(self, "_tab_buttons", []):
            button.setFont(ui_font())
        if getattr(self, "reset_button", None) is not None:
            self.reset_button.setFont(ui_font())
        _pointing(self)
        self._mark_theme_buttons()
        if hasattr(self, "tag_settings"):
            self._fill_tag_settings()
        if hasattr(self, "watch_label"):
            self._set_result(self._watch_full, self._watch_tone, self._status_kind)
        if hasattr(self, "warning"):
            self.warning.apply_theme()
            self.clear_notice.apply_theme()

    def _mark_theme_buttons(self) -> None:
        for name, swatch in self.theme_buttons.items():
            swatch.set_selected(name == self.store.theme)

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
        edit = getattr(self, "hotkey_edit", None)
        if edit is not None and watched is edit:
            kind = event.type()
            if kind == QEvent.Type.FocusIn:
                if not self.store.auto_capture:
                    self._begin_hotkey()
            elif kind == QEvent.Type.FocusOut:
                self._end_hotkey()
            elif kind == QEvent.Type.KeyPress and event.key() not in (Qt.Key_Tab, Qt.Key_Backtab):
                if not self.store.auto_capture:
                    self._take_hotkey(event)
                return True
        table = getattr(self, "history_table", None)
        if table is not None and watched is table.viewport() and event.type() == QEvent.Type.Leave:
            self._clear_history_hover()
        names = getattr(self, "blacklist_table", None)
        if names is not None and watched is names.viewport() and event.type() == QEvent.Type.Leave:
            self._clear_blacklist_hover()
        if watched.property("scanRow") is not None:
            button = watched.findChild(QPushButton, "rowDelete")
            kind = event.type()
            if button is not None and kind == QEvent.Type.Enter:
                button.show()
            elif button is not None and kind == QEvent.Type.Leave:
                button.hide()
            elif kind == QEvent.Type.MouseButtonPress and event.button() == Qt.LeftButton:
                scan = int(watched.property("scanRow"))
                for row in range(self.history_list.count()):
                    item = self.history_list.item(row)
                    if item.data(Qt.UserRole) == scan and not item.isHidden():
                        self.history_list.setCurrentRow(row)
                        break
        return super().eventFilter(watched, event)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)
        self._remember_size()

    def _tag_cell(self, tags: tuple[str, ...] | list[str]) -> QWidget:
        host = QWidget()
        host.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        row = QHBoxLayout(host)
        row.setContentsMargins(4, 0, 4, 0)
        row.setSpacing(6)
        for tag in tags:
            row.addWidget(TagPill(tag))
        row.addStretch(1)
        return host

    def _list_cell(self, text: str, store_index: int | None = None) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setFont(chinese_font())
        item.setForeground(QColor(THEME["text"]))
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        if store_index is not None:
            item.setData(Qt.UserRole, store_index)
        return item

    def _sort_stamp(self, entry: Entry, column: int) -> float | None:
        if column != 3:
            return None
        for scan in self.store.scans:
            for seat in scan.get("names", []):
                if seat.get("unclear") or not str(seat.get("name") or ""):
                    continue
                shown = str(seat["name"])
                if match_label(NameLabel(raw=shown, visible=shown, truncated=False), [entry]):
                    moment = _local_moment(str(scan.get("at", "")))
                    return None if moment is None else moment.timestamp()
        return None

    def _ordered_entries(self) -> list[tuple[int, Entry]]:
        rows = list(enumerate(self.store.entries))
        if self._blacklist_sort is None:
            return rows
        column, newest = self._blacklist_sort

        def key(pair: tuple[int, Entry]) -> tuple[bool, float, int]:
            index, entry = pair
            stamp = self._sort_stamp(entry, column)
            if stamp is None:
                return (True, 0.0, index)
            return (False, -stamp if newest else stamp, index)

        return sorted(rows, key=key)

    def _column_labels(self) -> list[str]:
        header = self.blacklist_table.horizontalHeader()
        return [
            self.blacklist_table.horizontalHeaderItem(header.logicalIndex(visual)).text()
            for visual in range(header.count())
        ]

    def _apply_column_widths(self) -> None:
        header = self.blacklist_table.horizontalHeader()
        widths = self.store.column_widths
        if len(widths) != header.count():
            return
        header.blockSignals(True)
        for logical, width in enumerate(widths):
            self.blacklist_table.setColumnWidth(logical, width)
        header.blockSignals(False)

    def _save_column_width(self, logical: int, _old: int, new: int) -> None:
        if not 0 <= logical < len(self.store.column_widths) or self.store.column_widths[logical] == new:
            return
        self.store.column_widths[logical] = new
        self.store.save_settings()

    def _apply_column_order(self) -> None:
        header = self.blacklist_table.horizontalHeader()
        order = self.store.column_order
        if sorted(order) != list(range(header.count())):
            return
        header.blockSignals(True)
        for visual, logical in enumerate(order):
            current = header.visualIndex(logical)
            if current != visual:
                header.moveSection(current, visual)
        header.blockSignals(False)

    def _save_column_order(self, _logical: int = 0, _old: int = 0, _new: int = 0) -> None:
        header = self.blacklist_table.horizontalHeader()
        order = [header.logicalIndex(visual) for visual in range(header.count())]
        if order == self.store.column_order:
            return
        self.store.column_order = order
        self.store.save_settings()

    def _sort_blacklist(self, column: int) -> None:
        if column != 3:
            return
        newest = self._blacklist_sort != (column, True)
        self._blacklist_sort = (column, newest)
        header = self.blacklist_table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(column, Qt.DescendingOrder if newest else Qt.AscendingOrder)
        self._show_list()

    def _last_met(self, entry: Entry) -> str:
        for scan in self.store.scans:
            for seat in scan.get("names", []):
                if seat.get("unclear") or not str(seat.get("name") or ""):
                    continue
                shown = str(seat["name"])
                if match_label(NameLabel(raw=shown, visible=shown, truncated=False), [entry]):
                    return _zh_ago(str(scan.get("at", "")))
        return ""

    def _show_list(self) -> None:
        rows = self._ordered_entries()
        bar = self.blacklist_table.verticalScrollBar()
        position = bar.value()
        self.blacklist_table.setRowCount(len(rows))
        for row, (index, entry) in enumerate(rows):
            self.blacklist_table.setItem(row, 0, self._list_cell(entry.name, index))
            self.blacklist_table.setItem(row, 1, self._list_cell(tag_text(entry)))
            self.blacklist_table.setCellWidget(row, 1, self._tag_cell(entry.tags))
            self.blacklist_table.setItem(row, 2, self._list_cell(entry.reason))
            self.blacklist_table.setItem(row, 3, self._list_cell(self._last_met(entry)))
            self.blacklist_table.setRowHeight(row, 44)
        self._blacklist_hover = -1
        self.blacklist_table.setCurrentCell(-1, -1)
        bar.setValue(position)
        self._refresh_blacklist_tab()
        count = len(self.store.entries)
        if count:
            self.list_hint.hide()
            self.blacklist_table.setVisible(True)
        else:
            self.list_hint.setText("还没有名字")
            self.list_hint.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.list_hint.show()
            self.blacklist_table.setVisible(False)

    def _hover_blacklist_row(self, row: int, _column: int = 0) -> None:
        if row < 0:
            return
        if row == self._blacklist_hover:
            return
        bar = self.blacklist_table.verticalScrollBar()
        position = bar.value()
        self._blacklist_hover = row
        self.blacklist_table.selectRow(row)
        bar.setValue(position)

    def _clear_blacklist_hover(self) -> None:
        bar = self.blacklist_table.verticalScrollBar()
        position = bar.value()
        self._blacklist_hover = -1
        self.blacklist_table.clearSelection()
        self.blacklist_table.setCurrentCell(-1, -1)
        bar.setValue(position)

    def _set_tab_title(self, index: int, text: str) -> None:
        self.tabs.setTabText(index, text)
        if 0 <= index < len(self._tab_buttons):
            self._tab_buttons[index].setText(text)

    def _sync_tab_buttons(self, index: int) -> None:
        for button_index, button in enumerate(self._tab_buttons):
            button.setChecked(button_index == index)

    def _refresh_blacklist_tab(self) -> None:
        count = len(self.store.entries)
        self._set_tab_title(self.blacklist_tab, f"黑名单  {count}" if count else "黑名单")

    def _ask_clear_list(self) -> None:
        if not _confirm(self, "清空列表？"):
            return
        self.store.clear_entries()
        self._show_list()
        self._show_history_scan(self._selected_scan())

    def _add_by_dialog(self) -> None:
        dialog = AddNameDialog(catalog=self.store.tag_catalog(), parent=self)
        if dialog.exec() != QDialog.Accepted or dialog.deleted:
            return
        if self.store.add(dialog.name, dialog.detail, tags=dialog.tags) is None:
            return
        self._show_list()
        self._show_history_scan(self._selected_scan())

    def _add_many_by_dialog(self) -> None:
        dialog = BatchAddDialog(self.store.tag_catalog(), parent=self)
        if dialog.exec() != QDialog.Accepted or not dialog.names:
            return
        if dialog.annotated is None:
            added = self.store.add_names(dialog.names)
        else:
            added = self.store.add_annotated(dialog.annotated)
        if added == 0:
            return
        self._show_list()
        self._show_history_scan(self._selected_scan())

    def _edit_row(self, row: int, _column: int = 0) -> None:
        item = self.blacklist_table.item(row, 0)
        if item is None or item.data(Qt.UserRole) is None:
            return
        self._edit_entry(int(item.data(Qt.UserRole)))

    def _edit_entry(self, index: int) -> None:
        if not 0 <= index < len(self.store.entries):
            return
        entry = self.store.entries[index]
        dialog = AddNameDialog(
            entry.name,
            entry.tags,
            entry.reason,
            title="修改",
            allow_delete=True,
            catalog=self.store.tag_catalog(),
            added_at=entry.added_at,
            parent=self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        if dialog.deleted:
            self.store.remove_at(index)
        else:
            self.store.update_at(index, dialog.name, dialog.tags, dialog.detail)
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
        self.clear_history_button.setVisible(count > 0)
        self._set_tab_title(self.history_tab, f"记录  {count}" if count else "记录")
        chosen = -1
        if count:
            chosen = max(0, min(select, count - 1))
            for list_row in range(self.history_list.count()):
                if self.history_list.item(list_row).data(Qt.UserRole) == chosen:
                    self.history_list.setCurrentRow(list_row)
                    break
        self.history_list.blockSignals(False)
        self._mark_selected_record()
        self._show_history_scan(chosen)
        self._show_list()

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
        item.setSizeHint(QSize(0, 40))
        self.history_list.addItem(item)
        item.setHidden(closed)
        wrap = QWidget()
        wrap.setProperty("scanRow", index)
        wrap.setStyleSheet("background: transparent;")
        wrap.installEventFilter(self)
        line = QHBoxLayout(wrap)
        line.setContentsMargins(0, 0, 4, 0)
        line.setSpacing(0)
        line.addStretch(1)
        remove = QPushButton("×")
        remove.setObjectName("rowDelete")
        remove.setFixedSize(32, 32)
        mark = chinese_font(16)
        mark.setBold(True)
        remove.setFont(mark)
        remove.setCursor(Qt.PointingHandCursor)
        remove.setFocusPolicy(Qt.NoFocus)
        remove.hide()
        remove.clicked.connect(lambda _checked=False, scan=index: self._delete_scan(scan))
        line.addWidget(remove)
        self.history_list.setItemWidget(item, wrap)

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

    def _delete_scan(self, index: int) -> None:
        self.store.remove_scan(index)
        self._reload_history(index)

    def _delete_history(self) -> None:
        self._delete_scan(self._selected_scan())

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

    def _show_history_scan(self, row: int) -> None:
        self._history_hover = (-1, -1)
        self._mark_selected_record()
        self.history_table.setRowCount(0)
        if row < 0 or row >= len(self.store.scans):
            return
        names = self.store.scans[row].get("names", [])
        self.history_table.setRowCount((len(names) + 1) // 2)
        for index, seat in enumerate(names):
            self._set_history_seat(index // 2, index % 2, seat)
            self.history_table.setRowHeight(index // 2, 40)

    def _mark_selected_record(self) -> None:
        chosen = self._selected_scan()
        for row in range(self.history_list.count()):
            item = self.history_list.item(row)
            if item.data(Qt.UserRole + 1) != "time":
                continue
            font = chinese_font()
            font.setBold(item.data(Qt.UserRole) == chosen)
            item.setFont(font)

    def _history_match(self, shown: str):
        label = NameLabel(raw=shown, visible=shown, truncated=False)
        found = match_label(label, list(self.store.entries))
        return found[0] if found else None

    def _set_history_seat(self, row: int, column: int, seat: dict) -> None:
        unclear = bool(seat.get("unclear")) or not str(seat.get("name") or "")
        shown = "未看清" if unclear else str(seat.get("name"))
        match = None if unclear else self._history_match(shown)
        stored = match.entry.name if match is not None else ""
        mine = not unclear and match is None and self._is_my_name(shown)
        if mine:
            action = "你"
        elif unclear or match is not None:
            action = ""
        else:
            action = "加入"
        title = stored if match is not None else shown
        if not unclear:
            title = split_ellipsis(title)[0] or title
        # Lobby order is not the player's number. Show the name until a later stage.
        label = title
        name_item = QTableWidgetItem(label)
        name_item.setData(Qt.UserRole, "" if unclear else shown)
        name_item.setData(Qt.UserRole + 1, action)
        name_item.setData(Qt.UserRole + 2, stored)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        name_font = chinese_font()
        name_item.setFont(name_font)
        if unclear:
            tone = THEME["gray"]
            wash = THEME["gray_wash"]
            hover = THEME["gray_hover"]
        elif match is not None:
            tone = THEME["red"]
            wash = THEME["red_wash"]
            hover = THEME["red_hover"]
        elif self._is_my_name(shown):
            tone = THEME["green"]
            wash = THEME["green_wash"]
            hover = ""
        else:
            tone = THEME["text"]
            wash = ""
            hover = THEME["red_hover"]
        name_item.setForeground(QColor(tone))
        self.history_table.setItem(row, column, name_item)
        wrap = QWidget()
        wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        wrap.setProperty("toneWash", wash)
        wrap.setProperty("toneHover", hover)
        wrap.setStyleSheet(self._history_wrap_style(wash))
        line = QHBoxLayout(wrap)
        line.setContentsMargins(4, 0, 8, 0)
        line.setSpacing(GAP)
        name_label = QLabel(label)
        name_label.setFont(name_font)
        name_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        name_color = tone
        name_label.setStyleSheet(f"color: {name_color}; background: transparent;")
        line.addWidget(name_label)
        line.addStretch(1)
        if action:
            action_label = QLabel(action)
            action_label.setObjectName("rowAction")
            action_label.setFont(chinese_font())
            action_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            if action == "你":
                color = THEME["green"]
            else:
                color = THEME["red"]
            action_label.setStyleSheet(f"color: {color}; background: transparent;")
            if action == "加入":
                action_label.hide()
            line.addWidget(action_label)
        self.history_table.setCellWidget(row, column, wrap)

    def _history_wrap_style(self, wash: str = "") -> str:
        return f"background: {wash or THEME['surface']};"

    def _history_cell_is_mine(self, row: int, column: int) -> bool:
        item = self.history_table.item(row, column)
        return item is not None and str(item.data(Qt.UserRole + 1) or "") == "你"

    def _hover_history_cell(self, row: int, column: int) -> None:
        if self._history_cell_is_mine(row, column):
            self._clear_history_hover()
            self.history_table.viewport().setCursor(Qt.ArrowCursor)
            return
        self.history_table.viewport().setCursor(Qt.PointingHandCursor)
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
        if hot and str(item.data(Qt.UserRole + 1) or "") == "你":
            hot = False
        hover = str(wrap.property("toneHover") or "")
        wash = hover if hot and hover else str(wrap.property("toneWash") or "")
        if hot and not hover:
            wash = THEME["red_hover"]
        wrap.setStyleSheet(self._history_wrap_style(wash))
        action_label = wrap.findChild(QLabel, "rowAction")
        if action_label is not None and action_label.text() == "加入":
            action_label.setVisible(hot)

    def _on_history_cell(self, row: int, column: int) -> None:
        item = self.history_table.item(row, column)
        if item is None:
            return
        shown = str(item.data(Qt.UserRole) or "")
        if not shown or str(item.data(Qt.UserRole + 1) or "") == "你":
            return
        stored = str(item.data(Qt.UserRole + 2) or "")
        if stored:
            for index, entry in enumerate(self.store.entries):
                if entry.name == stored:
                    self._edit_entry(index)
                    return
            return
        dialog = AddNameDialog(shown, title="添加", catalog=self.store.tag_catalog(), parent=self)
        if dialog.exec() != QDialog.Accepted or dialog.deleted:
            return
        if self.store.add(dialog.name, dialog.detail, tags=dialog.tags) is None:
            return
        self._show_list()
        self._show_history_scan(self._selected_scan())

    def _toggle_auto(self, checked: bool) -> None:
        self.store.auto_capture = bool(checked)
        self.store.save_settings()
        if self.store.auto_capture:
            self.watch = LobbyWatch()
            self._watch_timer.start()
        elif not self.panel.isVisible():
            self._watch_timer.stop()
        self._sync_hotkey_mode()
        if self._status_kind in ("idle", "watch"):
            self._sync_watch_idle()

    def _begin_hotkey(self) -> None:
        self._set_settings_note("")
        self.hotkey.clear()
        self.hotkey_edit.clear()
        self.hotkey_edit.setPlaceholderText("按下热键")

    def _end_hotkey(self) -> None:
        self.hotkey_edit.setPlaceholderText("无")
        self._show_hotkey()
        self._sync_hotkey_mode()

    def _sync_hotkey_mode(self) -> None:
        """Auto check and the hotkey do not run together."""
        manual = not self.store.auto_capture
        self.hotkey_edit.setEnabled(manual)
        self.hotkey_edit.setCursor(Qt.PointingHandCursor if manual else Qt.ArrowCursor)
        if not manual:
            self.hotkey.clear()
            return
        spec = parse_hotkey(self.store.hotkey)
        if spec is not None and self.hotkey.active != spec.display:
            self.hotkey.apply(spec)

    def _take_hotkey(self, event) -> None:
        if event.isAutoRepeat():
            return
        if event.key() == Qt.Key_Escape:
            self.hotkey_edit.clearFocus()
            return
        if event.key() in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta):
            return
        key = _qt_key_name(event.key())
        if key is None:
            self._set_settings_note("请按字母、数字，或 F1 到 F12。")
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
        spec = parse_hotkey("+".join([*modifiers, key]))
        if spec is None:
            self._set_settings_note("这个组合不能用。")
            return
        registered = self.hotkey.apply(spec)
        self.store.hotkey = spec.display
        self.store.save_settings()
        self.hotkey_edit.setText(spec.display)
        if registered:
            self._set_settings_note("")
        elif sys.platform != "win32":
            self._set_settings_note("这台电脑不能用热键。")
        else:
            self.store.hotkey = ""
            self.store.save_settings()
            self.hotkey_edit.clear()
            self._set_settings_note("换一个热键。")
        self.hotkey_edit.clearFocus()

    def _show_hotkey(self) -> None:
        spec = parse_hotkey(self.store.hotkey)
        if spec is None:
            self.hotkey_edit.clear()
            return
        self.hotkey_edit.setText(spec.display)

    def _restore_hotkey(self) -> None:
        self._show_hotkey()
        self._sync_hotkey_mode()

    def check_now(self) -> None:
        self._release_foreground = True
        self._rescan_active = False
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
        quiet = self._rescan_active
        if live and self.panel.isVisible() and not quiet:
            self._panel_hide_timer.stop()
            self.panel.set_mode("checking", "正在检查")
        if not self.worker.request(fn):
            if not quiet:
                self._set_result("正在检查", "status", "check")
            self._unlock_foreground()
            return False
        self._check_started = time.perf_counter()
        if not quiet:
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
            if self.panel.isVisible():
                self._hide_panel_after_title()
        else:
            self._panel_hide_timer.stop()
        if not self.store.auto_capture:
            return
        now = time.perf_counter()
        if not self.watch.wants_check(bool(value), now):
            return
        self.watch.arm(now)
        self._rescan_active = False
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
        rescan = self._rescan_active
        self._rescan_active = False
        elapsed = None
        if self._check_started is not None:
            elapsed = time.perf_counter() - self._check_started
            self._check_started = None
        if status == "err":
            self._set_result(str(value), "hit", "error")
            if not rescan and self._live_check and self._rescan_now():
                return
            if self.store.auto_capture:
                self.watch.retry_after(time.perf_counter())
            self._hide_panel_after_title()
            return
        result: CheckResult = value
        if not result.header_found:
            brief, _clear = self._brief(result)
            self._set_result(brief, "hit", "result")
            if not rescan and self._live_check and self._rescan_now():
                return
            if self.store.auto_capture:
                self.watch.retry_after(time.perf_counter())
            self._hide_panel_after_title()
            return
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
            if outcome == "filled":
                self._apply_filled(result)
                brief, clear = self._brief(result)
            self._reload_history()
            if outcome == "filled":
                brief = f"{brief}，补上了没看清的名字"
            elif outcome == "refreshed":
                brief = f"{brief}，已更新这条记录"
            elif outcome == "skipped" and not rescan:
                brief = f"{brief}，这一分钟已经记过"
            unclear = any(slot.unclear for slot in result.names)
            if self._live_check and unclear and not rescan and outcome != "skipped":
                self._rescan_now()
        self._set_result(brief, "clear" if clear else "hit", "result")
        self._show_result(result)
        self._show_panel(result)
        if self.store.save_debug_frames and result.preview_rgb is not None:
            self._save_debug(result)

    def _rescan_now(self) -> bool:
        if self._closing:
            return False
        self._rescan_active = True
        if self.store.auto_capture:
            self.watch.arm(time.perf_counter())
        if self._start(self._capture_job, live=True):
            return True
        self._rescan_active = False
        return False

    def _apply_filled(self, result: CheckResult) -> None:
        if not self.store.scans:
            return
        saved = {int(item["seat"]): item for item in self.store.scans[0]["names"]}
        slots: list[NameSlot] = []
        for slot in result.names:
            item = saved.get(seat_number(slot.index))
            if item is None or item.get("unclear") or not str(item.get("name") or ""):
                slots.append(slot)
                continue
            name = str(item["name"])
            slots.append(
                NameSlot(
                    index=slot.index,
                    box=slot.box,
                    raw=name,
                    visible=name,
                    truncated=name.endswith("..."),
                    confidence=slot.confidence,
                    unclear=False,
                )
            )
        result.names = slots
        hits: list[Hit] = []
        for slot in slots:
            if slot.unclear or not slot.visible:
                continue
            label = NameLabel(raw=slot.visible, visible=slot.visible, truncated=slot.truncated, unclear=False)
            for found in match_label(label, self.store.entries):
                note = describe_entry(found.entry)
                hits.append(
                    Hit(
                        index=slot.index,
                        read_text=slot.visible,
                        entry_name=found.entry.name,
                        note=note,
                        truncated=slot.truncated,
                        line=format_hit(slot.index, slot.visible, slot.truncated, found.entry.name, note),
                    )
                )
        result.hits = hits

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
                line = hit.entry_name
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
            text = "未看清" if slot.unclear else slot.visible
            lines.append(text)
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
