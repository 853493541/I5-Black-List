"""直播模式: the marks, copied into one window a streaming app can capture, without a 黑名单 name.

A streamer who captures only the game's window (窗口捕获) gets the game without the marks:
those are windows of their own, drawn over it. With 直播模式 on, this window copies them, where
they are, a little over twenty times a second: the ring round the button and its heart badge, the
心动 card, the flower border, and the red glow. Viewers see that a 黑名单 player is there (the red
ring and glow), never who: the card with the names is not copied.

In 安全模式 the marks are made but never put on the streamer's screen (WA_DontShowOnScreen);
this window is the only place they show. The window itself sits just off the screen, to the
right of every monitor: the streamer never sees it, and a window capture still reads it, being
a capture of the window and not of the screen. It is the size of the game's screen and mirrors it
point for point.

Behind the marks it is clear, and the streaming app keeps that: 哔哩哔哩直播姬 captures the
window with its transparency, so the soft pink glow and the sheer silk look as they do over the
game. It used to be pure green for a 色度键 to take out, which took the soft parts with it.

In 直播姬: add a second 窗口捕获, pick 模仿者小工具·直播画面, and put it over the game. A 色度键
from before does no harm: there is no green left for it to take.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication, QWidget

from blacklist_detect.names import APP_NAME
from blacklist_detect.ui_alert import paint_glow

TITLE = f"{APP_NAME}·直播画面"
FRAME_MS = 45


class StreamMirror(QWidget):
    """One window with the marks, for a streaming app to capture.

    window is the main window: it owns the marks (panel, like_card, clear_mark), the flower
    border (love) and the red glow (alert). The card with the 黑名单 names (hit_card) is left out.
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
        # The game's window as a streaming app's 窗口捕捉 sees it, once a check has found it.
        self._frame = QRect()
        self._tick = QTimer(self)
        self._tick.setInterval(FRAME_MS)
        self._tick.timeout.connect(self._step)

    def enabled(self) -> bool:
        return self._tick.isActive()

    def mode(self) -> str:
        return self._mode

    def enable(self, mode: str | bool) -> None:
        """Any true value opens it (clear behind the marks); "" or False closes it."""
        mode = "on" if mode else ""
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
        """The marks showing now: the 心动 card, and the ring with a 心动 or 黑名单 player there
        (red has no names on it). Never the 黑名单 card; nothing for a lobby with no one listed."""
        window = self._window
        marks = [window.like_card]
        if window.panel.mode in ("liked", "hit", "both"):
            marks.append(window.panel)
        if window.panel.mode == "liked":
            marks.append(window.clear_mark)
        return [mark for mark in marks if mark.isVisible()]

    def _borders(self) -> list:
        """The flower border while it plays."""
        love = self._window.love
        return [love] if love.playing() else []

    def _glow(self):  # noqa: ANN202
        """The red glow while it shows."""
        alert = self._window.alert
        return alert if alert.isVisible() else None

    def busy(self) -> bool:
        """Whether a mark is showing now."""
        return bool(self._marks()) or bool(self._borders()) or self._glow() is not None

    def _place(self, area: QRect) -> None:
        """Mirror area (the game's screen), from a spot just right of every monitor."""
        self._area = QRect(area)
        right = max((screen.geometry().right() for screen in QApplication.screens()), default=area.right())
        self.setGeometry(QRect(right + 64, area.y(), area.width(), area.height()))

    def set_frame(self, frame: QRect) -> None:
        """Mirror the game's window from now on: the same size as the 窗口捕捉 of the game, so the
        two line up when both fill the canvas. A full-screen game's window is the screen."""
        self._frame = QRect(frame)
        if self.enabled() and self._frame.size() != self.size():
            self._place(self._frame)

    def _screen(self) -> QRect:
        if not self._frame.isEmpty():
            return self._frame
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
        origin = self._area.topLeft()
        for border in self._borders():
            painter.save()
            painter.translate(border.geometry().topLeft() - origin)
            border.paint_at(painter, border.elapsed(), border.width(), border.height())
            painter.restore()
        glow = self._glow()
        if glow is not None:
            painter.save()
            painter.setOpacity(glow.windowOpacity())
            painter.translate(glow.geometry().topLeft() - origin)
            paint_glow(painter, glow.width(), glow.height())
            painter.restore()
        for mark in self._marks():
            painter.setOpacity(mark.windowOpacity())
            painter.drawPixmap(mark.geometry().topLeft() - origin, mark.grab())
        painter.end()
