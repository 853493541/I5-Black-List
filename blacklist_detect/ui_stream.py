"""直播模式: the 心动 marks, copied into one window a streaming app can capture.

A streamer who captures only the game's window (窗口捕获) gets the game without the marks:
those are windows of their own, drawn over it. With 直播模式 on, this window copies the 心动
ones, where they are, a little over twenty times a second: the rose ring and heart badge of a
lobby with no 黑名单 player, the 心动 card, and the flower border. Nothing about 黑名单 is
ever copied (no red ring, card or glow), so viewers never see who is on the list.

In 安全模式 the marks are made but never put on the streamer's screen (WA_DontShowOnScreen);
this window is the only place they show. The window itself sits just off the screen, to the
right of every monitor: the streamer never sees it (on screen, its green would fill any bare
desktop around a windowed game), and a window capture still reads it, being a capture of the
window and not of the screen. It is the size of the game's screen and mirrors it point for point.

Behind the marks it is pure green, for the streaming app's 色度键 (color key) to take out.

In 直播姬 or OBS: add a second 窗口捕获, pick 模仿者小工具·直播画面, put it over the game,
and give it a 色度键 filter on green.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QWidget

from blacklist_detect.names import APP_NAME

TITLE = f"{APP_NAME}·直播画面"
# The color the streaming app keys out.
KEY = QColor(0, 255, 0)
FRAME_MS = 45


class StreamMirror(QWidget):
    """One window with the 心动 marks, for a streaming app to capture.

    window is the main window: it owns the marks (panel, like_card, clear_mark) and the flower
    border (love). Its 黑名单 marks (hit_card, the red ring, alert) are left out.
    """

    def __init__(self, window) -> None:  # noqa: ANN001
        # A normal window, not a tool window: streaming apps leave tool windows out of their list.
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.Window
            | Qt.WindowStaysOnBottomHint
            | Qt.WindowDoesNotAcceptFocus
            | Qt.WindowTransparentForInput,
        )
        self.setWindowTitle(TITLE)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.NoFocus)
        self._window = window
        self._active = False
        self._mode = ""
        # The screen this window mirrors; it is shown somewhere else, off the screen.
        self._area = QRect()
        self._tick = QTimer(self)
        self._tick.setInterval(FRAME_MS)
        self._tick.timeout.connect(self._step)

    def enabled(self) -> bool:
        return self._tick.isActive()

    def mode(self) -> str:
        return self._mode

    def enable(self, mode: str | bool) -> None:
        """"key" (green behind the marks), "alpha" (clear), or "" / False to close it."""
        mode = "key" if mode is True else (mode or "")
        self._mode = mode
        self.update()
        if mode:
            self._place(self._screen())
            self.show()
            self.lower()
            self._tick.start()
        else:
            self._tick.stop()
            self._active = False
            self.hide()

    def _marks(self) -> list[QWidget]:
        """The 心动 marks showing now. The ring and badge only while no 黑名单 player is there."""
        window = self._window
        marks = [window.like_card]
        if window.panel.mode == "liked":
            marks += [window.panel, window.clear_mark]
        return [mark for mark in marks if mark.isVisible()]

    def _borders(self) -> list:
        """The flower borders playing now: the one over the game, or the one only the stream gets."""
        window = self._window
        return [border for border in (window.love, window.stream_love) if border.playing()]

    def busy(self) -> bool:
        """Whether a 心动 mark is showing now."""
        return bool(self._marks()) or bool(self._borders())

    def _place(self, area: QRect) -> None:
        """Mirror area (the game's screen), from a spot just right of every monitor."""
        self._area = QRect(area)
        right = max((screen.geometry().right() for screen in QApplication.screens()), default=area.right())
        self.setGeometry(QRect(right + 64, area.y(), area.width(), area.height()))

    def _screen(self) -> QRect:
        panel = self._window.panel
        point = panel.cover_geometry().center() if panel.isVisible() else QPoint(0, 0)
        screen = QApplication.screenAt(point) or QApplication.primaryScreen()
        return screen.geometry() if screen is not None else QRect(0, 0, 1920, 1080)

    def _step(self) -> None:
        busy = self.busy()
        if busy:
            area = self._screen()
            if area != self._area:
                self._place(area)
        # Painted while something shows, and once more after, to clear it.
        if busy or self._active:
            self._active = busy
            self.update()

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        if not self._active:
            painter.end()
            return
        painter.setRenderHint(QPainter.Antialiasing)
        if self._mode == "key":
            painter.fillRect(self.rect(), KEY)
        origin = self._area.topLeft()
        for border in self._borders():
            painter.save()
            painter.translate(border.geometry().topLeft() - origin)
            border.paint_at(painter, border.elapsed(), border.width(), border.height())
            painter.restore()
        for mark in self._marks():
            painter.setOpacity(mark.windowOpacity())
            painter.drawPixmap(mark.geometry().topLeft() - origin, mark.grab())
        painter.end()
