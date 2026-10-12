"""直播模式: the marks over the game, copied into one window a streaming app can capture.

A streamer who captures only the game's window (窗口捕获) gets the game without the ring, the
cards, the red glow or the flower border: those are windows of their own, drawn over it. With
直播模式 on, this window copies all of them, where they are on screen, a little over twenty
times a second. It sits under every other window, so on the streamer's own screen the game
hides it. Where nothing is shown it is clear, so it never covers the desktop.

Behind the marks it is either pure green (绿幕), for the streaming app's 抠图 (color key) to
take out, or clear (透明), for a capture that keeps transparency. Green works everywhere but
turns the soft red glow murky at its edges; clear keeps the glow as it is.

In 直播姬 or OBS: add a second 窗口捕获, pick 模仿者小工具·直播画面, put it over the game;
with 绿幕, give it a color key filter on green.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QWidget

from blacklist_detect.names import APP_NAME
from blacklist_detect.ui_alert import paint_glow

TITLE = f"{APP_NAME}·直播画面"
# The color the streaming app keys out.
KEY = QColor(0, 255, 0)
FRAME_MS = 45


class StreamMirror(QWidget):
    """One window with every mark the app shows over the game, for a streaming app to capture.

    window is the main window: it owns the marks (panel, hit_card, like_card, clear_mark), the
    red glow (alert) and the flower border (love).
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
            self.setGeometry(self._screen())
            self.show()
            self.lower()
            self._tick.start()
        else:
            self._tick.stop()
            self._active = False
            self.hide()

    def _marks(self) -> list[QWidget]:
        window = self._window
        return [mark for mark in (window.panel, window.hit_card, window.like_card, window.clear_mark) if mark.isVisible()]

    def busy(self) -> bool:
        """Whether anything is shown over the game now."""
        window = self._window
        return bool(self._marks()) or window.alert.isVisible() or window.love.playing()

    def _screen(self) -> QRect:
        panel = self._window.panel
        point = panel.cover_geometry().center() if panel.isVisible() else QPoint(0, 0)
        screen = QApplication.screenAt(point) or QApplication.primaryScreen()
        return screen.geometry() if screen is not None else QRect(0, 0, 1920, 1080)

    def _step(self) -> None:
        busy = self.busy()
        if busy:
            area = self._screen()
            if self.geometry() != area:
                self.setGeometry(area)
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
        origin = self.geometry().topLeft()
        window = self._window
        if window.alert.isVisible():
            painter.save()
            painter.translate(window.alert.geometry().topLeft() - origin)
            painter.setOpacity(window.alert.windowOpacity())
            paint_glow(painter, window.alert.width(), window.alert.height())
            painter.restore()
        if window.love.playing():
            painter.save()
            painter.translate(window.love.geometry().topLeft() - origin)
            window.love.paint_at(painter, window.love.elapsed(), window.love.width(), window.love.height())
            painter.restore()
        for mark in self._marks():
            painter.setOpacity(mark.windowOpacity())
            painter.drawPixmap(mark.geometry().topLeft() - origin, mark.grab())
        painter.end()
