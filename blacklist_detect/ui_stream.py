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
窗口区域模式) shows no frame. Viewers see it as well: it is for testing, and 直播模式's 测试框 box
takes it away (set_test_frame).

A friend's Windows 10 would not capture it off the screen: 直播姬's capture was in the scene and
live, and blank, while Windows 11 takes it. So once it is open, Windows is asked as 直播姬 asks it
(wgc). Where it refuses, the window moves to touch the rightmost screen by one pixel, then onto the
game's screen behind every window, until Windows takes it. Each answer goes to the log.

On that Windows 10 it was refused at all three. Refused everywhere, it finds out why, once
(wgc_diagnose): Windows' build, the window's styles, who runs as administrator, and Windows' answer
for the game's window, for plain windows and for windows like this one each without one property.
All of it goes to the log, with what it points at. When the window would be taken without a property
it can do without here (click-through, no-focus, stay at the bottom), it is made again without it.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QPoint, QPointF, QProcess, QProcessEnvironment, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from blacklist_detect import livehime, paths, wgc, wgc_diagnose
from blacklist_detect.names import APP_NAME
from blacklist_detect.ui_alert import paint_glow

log = logging.getLogger(__name__)

TITLE = f"{APP_NAME}·直播画面"
FRAME_MS = 45
TEST_TAG = f"{APP_NAME}·测试框"
_TEST_RED = QColor(225, 38, 52)
# Where the window sits, each tried in turn until Windows would capture it there: off every screen,
# touching the rightmost screen by one pixel, or on the game's screen behind every window.
SPOTS = ("off", "edge", "on")
_WHERE = {"off": "off the screen", "edge": "at the screen's right edge", "on": "on the screen, behind every window"}
# After the window shows or moves, before Windows is asked.
ASK_MS = 300
# The most the diagnosis may take before it is given up.
DIAGNOSE_MS = 60_000
# What the window's flags are made of, and the Qt flag behind each property it can do without.
_FLAGS = Qt.FramelessWindowHint | Qt.Window
_DROPPABLE = {
    "click-through": Qt.WindowTransparentForInput,
    "no-focus": Qt.WindowDoesNotAcceptFocus,
    "on-bottom": Qt.WindowStaysOnBottomHint,
}


class StreamMirror(QWidget):
    """One window with the marks, for a streaming app to capture.

    window is the main window: it owns the marks (panel, like_card, clear_mark), the flower
    border (love) and the red glow (alert). The card with the 黑名单 names (hit_card) is left out.
    """

    def __init__(self, window) -> None:  # noqa: ANN001
        # A normal window, not a tool window: streaming apps leave tool windows out of their list.
        # Properties the diagnosis found Windows refuses, left out (wgc_diagnose.HARMLESS).
        self.without: set[str] = set()
        super().__init__(None, self._flags())
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
        # The 测试框 while no mark shows (store.stream_test_frame).
        self.test_frame = True
        # Where it sits (SPOTS), and Windows' last answer there (wgc): None until it has answered.
        self.spot = SPOTS[0]
        self.answer: int | None = None
        self._asking: QProcess | None = None
        # The diagnosis, once each time 直播模式 opens: running, and whether it has run.
        self._diagnosing: QProcess | None = None
        self._diagnosed = False
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
            self.spot = SPOTS[0]
            self.answer = None
            self._diagnosed = False
            self._place(self._source())
            self.show()
            self.lower()
            self._tick.start()
            QTimer.singleShot(ASK_MS, self.ask_windows)
        else:
            self._stop_asking()
            self._stop_diagnosing()
            self._tick.stop()
            self._active = False
            self.hide()

    def ask_windows(self) -> None:
        """Ask Windows, from a process of its own as 直播姬 is, whether it would capture this window
        where it is. _answered takes the answer."""
        if not self.enabled() or sys.platform != "win32" or self._asking is not None:
            return
        program, arguments, folder = wgc.command(int(self.winId()))
        asking = QProcess(self)
        asking.setWorkingDirectory(folder)
        environment = QProcessEnvironment()
        for key, value in paths.child_env().items():
            environment.insert(key, value)
        asking.setProcessEnvironment(environment)
        asking.finished.connect(lambda _code, _status: self._answered(wgc.read(bytes(asking.readAllStandardOutput()).decode(errors="replace"))))
        asking.errorOccurred.connect(lambda error: self._could_not_ask(asking, error))
        self._asking = asking
        asking.start(program, arguments)

    def _could_not_ask(self, asking: QProcess, error) -> None:  # noqa: ANN001
        if error == QProcess.FailedToStart and self._asking is asking:
            log.warning("直播画面: could not ask Windows whether it captures it (%s).", asking.errorString())
            self._asking = None

    def _stop_asking(self) -> None:
        asking, self._asking = self._asking, None
        if asking is not None:
            asking.finished.disconnect()
            asking.kill()

    def _answered(self, result: int | None) -> None:
        """Windows' answer where the window is: it stays there, or tries the next of SPOTS."""
        self._asking = None
        if not self.enabled():
            return
        self.answer = result
        log.info("直播画面 %s: %s.", _WHERE[self.spot], wgc.words(result))
        if result is None or result == wgc.ACCEPTED:
            return
        later = SPOTS.index(self.spot) + 1
        if later == len(SPOTS):
            log.warning("直播画面: Windows would not capture it anywhere; a streaming app shows nothing of it.")
            if not self._diagnosed:
                self._diagnosed = True
                self.diagnose()
            return
        self.spot = SPOTS[later]
        self._place(self._area if not self._area.isEmpty() else self._source())
        QTimer.singleShot(ASK_MS, self.ask_windows)

    def _flags(self) -> Qt.WindowFlags:
        flags = _FLAGS
        for name, flag in _DROPPABLE.items():
            if name not in self.without:
                flags |= flag
        return flags

    def diagnose(self) -> None:
        """Find out why Windows refuses this window, in a process of its own (wgc_diagnose);
        diagnosed logs what it found."""
        if not self.enabled() or sys.platform != "win32" or self._diagnosing is not None:
            return
        control = 0
        watch = getattr(self._window, "_scene_watch", None)
        game = livehime.game_capture(watch.scene(), TITLE) if watch is not None else None
        if game is not None:
            control = livehime.window_of(game)
        program, arguments, folder = wgc_diagnose.command(int(self.winId()), control)
        running = QProcess(self)
        running.setWorkingDirectory(folder)
        environment = QProcessEnvironment()
        for key, value in paths.child_env().items():
            environment.insert(key, value)
        running.setProcessEnvironment(environment)
        running.finished.connect(lambda _code, _status: self._diagnosed_by(running))
        running.errorOccurred.connect(lambda error: self._could_not_diagnose(running, error))
        self._diagnosing = running
        log.info("直播画面: finding out why Windows refuses it (the game window 直播姬 captures: %s).", "open" if control else "not open")
        running.start(program, arguments)
        QTimer.singleShot(DIAGNOSE_MS, lambda: self._diagnosis_too_long(running))

    def _diagnosed_by(self, running: QProcess) -> None:
        if self._diagnosing is not running:
            return
        self._diagnosing = None
        output = bytes(running.readAllStandardOutput()).decode("utf-8", errors="replace")
        trouble = bytes(running.readAllStandardError()).decode("utf-8", errors="replace").strip()
        if "Traceback" in trouble:
            log.warning("直播画面 diagnosis failed:\n%s", trouble[-3000:])
        self.diagnosed(output)

    def diagnosed(self, output: str) -> None:
        """Log the diagnosis, and make the window again without a property Windows refuses, when it
        can do without it."""
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        found = next((line.removeprefix("verdict: ") for line in lines if line.startswith("verdict: ")), "")
        fix = next((line.removeprefix("fix: ") for line in lines if line.startswith("fix: ")), "")
        report = [line for line in lines if not line.startswith(("verdict: ", "fix: "))]
        frame = "on" if self.test_frame else "off"
        left_out = ", ".join(sorted(self.without)) or "nothing"
        report.append(f"fact: from the app: 测试框 {frame}; a mark showing {self.busy()}; left out {left_out}")
        log.info("直播画面 diagnosis:\n%s", "\n".join(report))
        log.warning("直播画面 diagnosis: %s", found or "no answer (the report above is all there is).")
        if fix in _DROPPABLE and fix not in self.without and self.enabled():
            self.without.add(fix)
            log.info("直播画面: made again without %s, which Windows took in the test; asking again from off the screen.", fix)
            if fix == "click-through":
                # Qt makes a window click-through for this as well.
                self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            self.setWindowFlags(self._flags())
            self.spot = SPOTS[0]
            self.answer = None
            self._place(self._area if not self._area.isEmpty() else self._source())
            self.show()
            self.lower()
            QTimer.singleShot(ASK_MS, self.ask_windows)

    def _could_not_diagnose(self, running: QProcess, error) -> None:  # noqa: ANN001
        if error == QProcess.FailedToStart and self._diagnosing is running:
            log.warning("直播画面: could not find out why Windows refuses it (%s).", running.errorString())
            self._diagnosing = None

    def _diagnosis_too_long(self, running: QProcess) -> None:
        if self._diagnosing is running:
            log.warning("直播画面: finding out why Windows refuses it took over %d s; given up.", DIAGNOSE_MS // 1000)
            self._stop_diagnosing()

    def _stop_diagnosing(self) -> None:
        running, self._diagnosing = self._diagnosing, None
        if running is not None:
            running.finished.disconnect()
            running.kill()

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

    def set_test_frame(self, on: bool) -> None:
        """Show the 测试框 while no mark shows, or not."""
        self.test_frame = bool(on)
        self.update()

    def set_backdrop(self, picture: QPixmap | None, where: QRect | None = None) -> None:
        """Draw picture under the marks, at where on the screen (测试效果's sample lobby); None
        takes it away."""
        self._backdrop = (picture, QRect(where)) if picture is not None and where is not None else None
        self._step()

    def _place(self, area: QRect) -> None:
        """Mirror area, from a 16:9 window as wide as its screen, where self.spot says: just right of
        every monitor, overlapping the rightmost one by a pixel, or over area's screen."""
        self._area = QRect(area)
        screen = QApplication.screenAt(area.center()) or QApplication.primaryScreen()
        home = screen.geometry() if screen is not None else QRect(0, 0, 1920, 1080)
        rightmost = max((each.geometry() for each in QApplication.screens()), key=lambda each: each.right(), default=home)
        corner = {
            "off": QPoint(rightmost.right() + 64, home.y()),
            "edge": QPoint(rightmost.right(), rightmost.y()),
            "on": home.topLeft(),
        }[self.spot]
        self.setGeometry(QRect(corner, QSize(home.width(), round(home.width() * 9 / 16))))
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
            if self.test_frame:
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
