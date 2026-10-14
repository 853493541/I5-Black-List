"""直播模式: the marks, copied into one window a streaming app can capture, without a 黑名单 name.

A streamer who captures only the game's window (窗口捕获) gets the game without the marks:
those are windows of their own, drawn over it. With 直播模式 on, this window copies them, where
they are, a little over twenty times a second: the ring round the button and its heart badge, the
心动 card, the flower border, and the red glow. Viewers see that a 黑名单 player is there (the red
ring and glow), never who: the card with the names is not copied.

In 安全模式 the marks are made but never put on the streamer's screen (WA_DontShowOnScreen);
this window is the only place they show. The window itself sits just off the screen, to the
right of every monitor: the streamer never sees it, and a window capture still reads it, being
a capture of the window and not of the screen.

Its size never changes: 16:9, as wide as the game's screen. 直播姬 fixes a 窗口捕捉's scale when
it is added, fitting the window into the canvas as it is then, so a window that changed size
later would leave the marks too small or too big. Inside it, the game's window (once a check has
found it; its screen before that) is drawn the way 直播姬 fits the game's own 窗口捕捉 into a
16:9 canvas: as big as fits, centered. The two captures line up without touching either.

Behind the marks it is clear, and the streaming app keeps that: 哔哩哔哩直播姬 captures the
window with its transparency, so the soft pink glow and the sheer silk look as they do over the
game. It used to be pure green for a 色度键 to take out, which took the soft parts with it.

In 直播姬: add a second 窗口捕获, pick 模仿者小工具·直播画面, and put it over the game. A 色度键
from before does no harm: there is no green left for it to take.

While no mark shows, a red frame (the 测试框) runs round the game, where the marks are drawn: a
streamer who sees it in the stream knows the marks will be there too, and that they line up. A
capture that reads nothing of this window (in 直播姬: the 预览 side not yet 同步至直播, BitBlt,
窗口区域模式) shows no frame. Viewers see it as well: it is for testing.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from blacklist_detect.names import APP_NAME
from blacklist_detect.ui_alert import paint_glow

TITLE = f"{APP_NAME}·直播画面"
FRAME_MS = 45
# The 测试框 while no mark shows. False takes it away.
TEST_FRAME = True
TEST_TAG = f"{APP_NAME}·测试框"
_TEST_RED = QColor(225, 38, 52)


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
        # What this window mirrors, in screen coordinates: the game's window, or its screen.
        self._area = QRect()
        # The game's window as a streaming app's 窗口捕捉 sees it, once a check has found it.
        self._frame = QRect()
        # 测试效果: a picture under the marks, where it is on the screen, so viewers see it too.
        self._backdrop: tuple[QPixmap, QRect] | None = None
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
            self._place(self._source())
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
        return self._backdrop is not None or bool(self._marks()) or bool(self._borders()) or self._glow() is not None

    def set_backdrop(self, picture: QPixmap | None, where: QRect | None = None) -> None:
        """Draw picture under the marks, at where on the screen (测试效果's sample lobby); None
        takes it away."""
        self._backdrop = (picture, QRect(where)) if picture is not None and where is not None else None
        self._step()

    def _place(self, area: QRect) -> None:
        """Mirror area, from a 16:9 window as wide as its screen, just right of every monitor."""
        self._area = QRect(area)
        screen = QApplication.screenAt(area.center()) or QApplication.primaryScreen()
        width = screen.geometry().width() if screen is not None else 1920
        top = screen.geometry().y() if screen is not None else 0
        right = max((each.geometry().right() for each in QApplication.screens()), default=area.right())
        self.setGeometry(QRect(QPoint(right + 64, top), QSize(width, round(width * 9 / 16))))
        # The 测试框 goes round the new area.
        self.update()

    def set_frame(self, frame: QRect) -> None:
        """Mirror the game's window from now on: what the game's 窗口捕捉 shows. A full-screen
        game's window is the screen."""
        self._frame = QRect(frame)
        if self.enabled() and self._frame != self._area:
            self._place(self._frame)

    def _source(self) -> QRect:
        """What to mirror: the game's window once a check has found it, else the game's screen."""
        if not self._frame.isEmpty():
            return self._frame
        panel = self._window.panel
        point = panel.cover_geometry().center() if panel.isVisible() else QPoint(0, 0)
        screen = QApplication.screenAt(point) or QApplication.primaryScreen()
        return screen.geometry() if screen is not None else QRect(0, 0, 1920, 1080)

    def _fit(self) -> tuple[float, QPointF]:
        """The scale and offset that put the mirrored area in this window as 直播姬 puts a
        window it captures in a 16:9 canvas when it is added: as big as fits, centered."""
        area = self._area
        if area.isEmpty():
            return 1.0, QPointF(0, 0)
        scale = min(self.width() / area.width(), self.height() / area.height())
        return scale, QPointF((self.width() - area.width() * scale) / 2, (self.height() - area.height() * scale) / 2)

    def to_window(self, point: QPoint) -> QPointF:
        """Where a point on the screen is drawn in this window."""
        scale, offset = self._fit()
        return offset + QPointF(point - self._area.topLeft()) * scale

    def _step(self) -> None:
        busy = self.busy()
        if busy:
            area = self._source()
            if area != self._area:
                self._place(area)
        # Painted while something shows, and once more after, back to the 测试框.
        if busy or self._active:
            self._active = busy
            self.update()

    def _paint_test_frame(self, painter: QPainter) -> None:
        """The 测试框: a red line round the mirrored game, its name in a red tag at the top left."""
        scale, offset = self._fit()
        if self._area.isEmpty():
            box = QRectF(self.rect())
        else:
            box = QRectF(offset.x(), offset.y(), self._area.width() * scale, self._area.height() * scale)
        line = max(4.0, self.width() / 240)
        pen = QPen(_TEST_RED, line)
        pen.setJoinStyle(Qt.MiterJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(box.adjusted(line / 2, line / 2, -line / 2, -line / 2))
        font = QFont(self.font())
        font.setPixelSize(max(12, round(self.width() / 80)))
        font.setBold(True)
        metrics = QFontMetricsF(font)
        pad = font.pixelSize() * 0.5
        tag = QRectF(box.left(), box.top(), metrics.horizontalAdvance(TEST_TAG) + pad * 2, metrics.height() + pad)
        painter.fillRect(tag, _TEST_RED)
        painter.setFont(font)
        painter.setPen(QColor("white"))
        painter.drawText(tag, Qt.AlignCenter, TEST_TAG)

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        if not self._active:
            if TEST_FRAME:
                self._paint_test_frame(painter)
            painter.end()
            return
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        # From here on, screen coordinates: each mark is drawn where it is on the screen.
        scale, offset = self._fit()
        painter.translate(offset)
        painter.scale(scale, scale)
        painter.translate(-QPointF(self._area.topLeft()))
        if self._backdrop is not None:
            picture, where = self._backdrop
            painter.drawPixmap(QRectF(where), picture, QRectF(picture.rect()))
        for border in self._borders():
            painter.save()
            painter.translate(border.geometry().topLeft())
            border.paint_at(painter, border.elapsed(), border.width(), border.height())
            painter.restore()
        glow = self._glow()
        if glow is not None:
            painter.save()
            painter.setOpacity(glow.windowOpacity())
            painter.translate(glow.geometry().topLeft())
            paint_glow(painter, glow.width(), glow.height())
            painter.restore()
        for mark in self._marks():
            painter.setOpacity(mark.windowOpacity())
            painter.drawPixmap(mark.geometry().topLeft(), mark.grab())
        painter.end()
