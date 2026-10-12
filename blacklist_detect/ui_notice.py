"""安全模式's result: a small solid box at the bottom right of the screen, and the warning sound.

Nothing is drawn over the game itself. The box is a plain opaque window (not layered, no
fades), it never takes the focus, and it goes away on its own after a few seconds or on a click.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QScreen
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from blacklist_detect.ui_overlay import _pin_topmost
from blacklist_detect.ui_theme import BODY_PT, TITLE_PT, chinese_family, chinese_font

# How long a result stays up.
NOTICE_MS = 8_000
# 检查中 waits for the result, but never forever.
CHECKING_MS = 20_000
# Names listed before the rest are counted.
_MAX_LINES = 5
_MARGIN = 20

# The box sits over the game, so it keeps these colors in 浅色 and 深色. Each result is a
# solid block of its own color, white text on it, to be seen from the corner of the eye.
_TITLE = "#ffffff"
_TEXT = "rgba(255, 255, 255, 235)"
_EDGE = "rgba(255, 255, 255, 70)"
_FILLS = {
    "hit": ("#e0323e", "#b81f2b"),
    "clear": ("#2f9e5e", "#237a48"),
    "liked": ("#e0558f", "#c03b74"),
    "checking": ("#3a3740", "#2a272f"),
    "missing": ("#55505c", "#423e48"),
    "error": ("#c9822a", "#a5681c"),
}


def play_hit_sound() -> None:
    """The Windows warning sound. It follows the system volume and sound scheme."""
    if sys.platform == "win32":
        try:
            import winsound

            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            return
        except Exception:
            pass
    QApplication.beep()


def result_text(
    hits: list[tuple[str, tuple[str, ...]]], likes: list[str], unclear: int
) -> tuple[str, str, list[str]]:
    """(kind, title, lines) for one checked lobby. hits are (name, tags), each person once."""
    lines: list[str] = []
    if hits:
        kind, title = "hit", f"发现 {len(hits)} 名黑名单玩家"
        shown = hits if len(hits) <= _MAX_LINES else hits[: _MAX_LINES - 1]
        for name, tags in shown:
            lines.append(f"{name}　{'、'.join(tags)}" if tags else name)
        if len(shown) < len(hits):
            lines.append(f"还有 {len(hits) - len(shown)} 人")
    else:
        kind, title = ("liked" if likes else "clear"), "未发现黑名单"
    if likes:
        lines.append(f"心动：{'、'.join(likes)}")
    if unclear:
        lines.append(f"{unclear} 人未识别")
    return kind, title, lines


def _round_corners(widget: QWidget) -> None:
    """Windows 11 rounds the plain window itself; older Windows keeps square corners."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_ROUND = 2
        value = ctypes.c_int(DWMWCP_ROUND)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            int(widget.winId()), DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(value), ctypes.sizeof(value)
        )
    except Exception:
        pass


class CornerNotice(QWidget):
    """One message at a time on a block of color: a large title and a few short lines."""

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
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setObjectName("cornerNotice")
        self.setCursor(Qt.PointingHandCursor)
        self.kind = ""
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        body = QWidget()
        body.setObjectName("noticeBody")
        column = QVBoxLayout(body)
        column.setContentsMargins(20, 14, 22, 16)
        column.setSpacing(6)
        self.title = QLabel("")
        self.title.setObjectName("noticeTitle")
        title_font = chinese_font(TITLE_PT)
        title_font.setWeight(QFont.Weight.DemiBold)
        self.title.setFont(title_font)
        column.addWidget(self.title)
        self.lines = QLabel("")
        self.lines.setObjectName("noticeLines")
        self.lines.setFont(chinese_font(BODY_PT))
        self.lines.setTextFormat(Qt.PlainText)
        column.addWidget(self.lines)
        row.addWidget(body, 1)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self._style("checking")

    def _style(self, kind: str) -> None:
        family = chinese_family()
        top, bottom = _FILLS.get(kind, _FILLS["missing"])
        self.setStyleSheet(
            f"""
            QWidget#cornerNotice {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {top}, stop:1 {bottom});
                border: 1px solid {_EDGE};
            }}
            QWidget#noticeBody {{ background: transparent; }}
            QLabel#noticeTitle {{ color: {_TITLE}; background: transparent; font-family: "{family}"; }}
            QLabel#noticeLines {{ color: {_TEXT}; background: transparent; font-family: "{family}"; }}
            """
        )

    def show_message(self, kind: str, title: str, lines: list[str], screen: QScreen | None, ms: int = NOTICE_MS) -> None:
        self.kind = kind
        self._style(kind)
        self.title.setText(title)
        self.lines.setText("\n".join(lines))
        self.lines.setVisible(bool(lines))
        self.setMinimumWidth(300)
        self.layout().activate()
        self.adjustSize()
        width = min(max(self.sizeHint().width(), 300), 460)
        self.resize(width, self.sizeHint().height())
        screen = screen or QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.move(area.right() - self.width() - _MARGIN + 1, area.bottom() - self.height() - _MARGIN + 1)
        self.show()
        _round_corners(self)
        _pin_topmost(self)
        self._timer.start(ms)

    def show_checking(self, screen: QScreen | None) -> None:
        self.show_message("checking", "检查中…", [], screen, CHECKING_MS)

    def show_result(
        self,
        hits: list[tuple[str, tuple[str, ...]]],
        likes: list[str],
        unclear: int,
        screen: QScreen | None,
    ) -> None:
        kind, title, lines = result_text(hits, likes, unclear)
        self.show_message(kind, title, lines, screen)

    def show_missing(self, screen: QScreen | None) -> None:
        self.show_message("missing", "没有找到大厅", ["进入「推演成功」大厅后再按快捷键"], screen)

    def show_error(self, detail: str, screen: QScreen | None) -> None:
        self.show_message("error", "检查失败", [detail] if detail else [], screen)

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        self._timer.stop()
        self.hide()
        event.accept()
