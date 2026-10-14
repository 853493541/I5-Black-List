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

That found it (v0.9.4): Windows 10 (22H2, build 19045) will not capture a window that never takes
focus (WS_EX_NOACTIVATE), and took 直播画面 at once without it. So on Windows 10 it is made without it
from the start. Windows 11 takes it either way and keeps it as it was.

What Windows 10 wants is a window on the taskbar: it refused the window that never takes focus (no
button), the taskbar itself, and, in v0.9.5, 直播画面 with its button taken off (ITaskbarList), while it
took a copy that kept its button. So there 直播画面 has a taskbar button, the price of being captured.

Taken is not enough on Windows 10: there the desktop stops redrawing what a capture gets from a
window that is wholly off the screen, so 直播姬 holds one still picture of it, empty, and the marks
never show. It must touch a screen by at least a pixel. So on Windows 10 it never sits off the
screen: it starts at the rightmost screen's edge, a clear column one pixel wide behind every window.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QPoint, QPointF, QProcess, QProcessEnvironment, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from blacklist_detect import livehime, livehime_layout, paths, wgc, wgc_diagnose
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
# Windows 10 refuses to capture a window that never takes focus, and keeps a capture of one up to date
# only while it touches a screen; 11 does both either way.
WINDOWS_10 = sys.platform == "win32" and sys.getwindowsversion().build < 22000


def _spots() -> tuple[str, ...]:
    """The SPOTS to try, in turn: on Windows 10 never off the screen."""
    return SPOTS[1:] if WINDOWS_10 else SPOTS
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
        # Properties Windows refuses, left out: no-focus on Windows 10, and what the diagnosis finds
        # (wgc_diagnose.HARMLESS).
        self.without: set[str] = {"no-focus"} if WINDOWS_10 else set()
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
        self.spot = _spots()[0]
        self.answer: int | None = None
        self._asking: QProcess | None = None
        # The diagnosis, once each time 直播模式 opens: running, and whether it has run.
        self._diagnosing: QProcess | None = None
        self._diagnosed = False
        # The layout last written to the log (note_layout), so the same one is not written again, and
        # what 直播姬's log says of its canvas, read on as it grows.
        self._layout_said: list[str] = []
        self._studio = livehime_layout.StudioWatch()
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
            self.spot = _spots()[0]
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
            self.note_layout("直播模式 on")
            return
        spots = _spots()
        later = spots.index(self.spot) + 1 if self.spot in spots else 0
        if later == len(spots):
            log.warning("直播画面: Windows would not capture it anywhere; a streaming app shows nothing of it.")
            if not self._diagnosed:
                self._diagnosed = True
                self.diagnose()
            return
        self.spot = spots[later]
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
        program, arguments, folder = wgc_diagnose.command(int(self.winId()), control, sorted(self.without))
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
            log.info("直播画面: made again without %s, which Windows took in the test; asking again from where it starts.", fix)
            if fix == "click-through":
                # Qt makes a window click-through for this as well.
                self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            self.setWindowFlags(self._flags())
            self.spot = _spots()[0]
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

    def note_layout(self, why: str) -> None:
        """Write to the log where everything is and how 直播姬 lines the game and this window up,
        when that changed since it was last written. Never in the way of the app: a failure is a
        line in the log."""
        if not self.enabled():
            return
        try:
            lines = self.layout_lines()
        except Exception as error:  # noqa: BLE001 - a report must never take 直播模式 down
            lines = [f"could not be worked out: {error!r}"]
        if lines != self._layout_said:
            self._layout_said = lines
            log.info("直播画面 layout (%s):\n%s", why, "\n".join(lines))

    def layout_lines(self) -> list[str]:
        """Our side in desktop pixels (the screen, this window, the game's window and where it is drawn
        here), then for each 直播姬 scene with this window: where the game's capture lands on its
        canvas, where this window draws that same picture, and the difference; then 直播姬's canvas
        and two-canvas mode."""
        screen = QApplication.screenAt(self._area.center()) or QApplication.primaryScreen()
        ratio = (screen.devicePixelRatio() if screen is not None else 1.0) or 1.0
        home = screen.geometry() if screen is not None else QRect(0, 0, 1920, 1080)

        def pixels(rect: QRect) -> tuple[int, int, int, int]:
            """A rect in Qt's units on this screen as (x, y, w, h) in desktop pixels."""
            return (
                round(home.x() + (rect.x() - home.x()) * ratio),
                round(home.y() + (rect.y() - home.y()) * ratio),
                round(rect.width() * ratio),
                round(rect.height() * ratio),
            )

        mine = livehime_layout.window_rect(int(self.winId()))
        if mine is None:
            x, y, w, h = pixels(self.geometry())
            mine = (x, y, x + w, y + h)
        mw, mh = mine[2] - mine[0], mine[3] - mine[1]
        # This window's pixels per Qt unit, as Windows made it.
        here = mw / max(1, self.width())
        scale, offset = self._fit()
        ax, ay, aw, ah = pixels(self._area)
        lines = [
            f"screen {round(home.width() * ratio)}x{round(home.height() * ratio)} px at ({home.x()}, {home.y()}), {ratio * 100:.0f}%; "
            f"直播画面 {mw}x{mh} px at ({mine[0]}, {mine[1]}), {_WHERE.get(self.spot, self.spot)}",
            f"mirrors ({ax}, {ay}) {aw}x{ah} px (the game's window as its 窗口捕获 takes it), drawn in 直播画面 at "
            f"({offset.x() * here:.0f}, {offset.y() * here:.0f}) {self._area.width() * scale * here:.0f}x{self._area.height() * scale * here:.0f} px",
        ]
        picture = self._picture(screen)
        if picture is not None:
            px, py, pw, ph = pixels(picture)
            lines.append(f"the game's picture, where the 心动 border plays: ({px}, {py}) {pw}x{ph} px")
        path = livehime_layout.collection_path()
        if path is None:
            lines.append("直播姬's scene file: not found")
        else:
            current, placed = livehime_layout.placements(path)
            for scene in dict.fromkeys(item.scene for item in placed if item.title == TITLE):
                lines.append(self._scene_line(scene, current, [item for item in placed if item.scene == scene], mw, mh, here))
        studio = self._studio.studio()
        canvas = f"{studio.canvas[0]}x{studio.canvas[1]}" if studio.canvas else "?"

        def said(value: bool | None) -> str:
            return "?" if value is None else "on" if value else "off"

        lines.append(
            f"直播姬: canvas {canvas}; 横竖双屏 {said(studio.double_screen)}; two canvases (预览 and 直播 apart) {said(studio.two_canvas)}; "
            f"last 同步至直播 {studio.synced or 'not seen'}; last source added or removed {studio.edited or 'not seen'}"
            + ("; CHANGED SINCE THE LAST 同步至直播: viewers do not see it yet" if studio.unsynced() else "")
        )
        return lines

    def _scene_line(self, scene: str, current: str, items: list, mw: int, mh: int, here: float) -> str:  # noqa: ANN001
        """One 直播姬 scene: this window's capture and the game's under it, and how they line up."""
        from blacklist_detect.ui_overlay import native_to_logical

        ours = next((item for item in reversed(items) if item.title == TITLE and item.visible), None) or next(
            item for item in reversed(items) if item.title == TITLE
        )
        head = f"直播姬「{scene}」{' (shown now)' if scene == current else ''}: "
        x, y, w, h = ours.on_canvas(mw, mh)
        flags = "".join(
            note
            for on, note in (
                (not ours.visible, ", hidden"),
                (ours.whole_screen, ", 窗口区域模式"),
                (not ours.client_area, ", whole window"),
                (bool(ours.rotation), f", turned {ours.rotation:g}°"),
                (any(ours.crop), f", cropped {ours.crop}"),
            )
            if on
        )
        mine = f"直播画面 at ({x:.0f}, {y:.0f}) {w:.0f}x{h:.0f}{flags}"
        under = items[: items.index(ours)]
        game = next((item for item in reversed(under) if item.visible and item.title and item.title != TITLE), None)
        if game is None:
            return head + mine + "; no game capture under it"
        frame = livehime_layout.captured_rect(game)
        if frame is None:
            return head + mine + f"; the game's 「{game.title}」 is not open"
        gx, gy, gw, gh = game.on_canvas(frame[2] - frame[0], frame[3] - frame[1])
        # Where this window draws that same picture: its corners, through the mirror, onto the canvas.
        left, top, _ratio = native_to_logical(frame[0], frame[1])
        right, bottom, _ratio = native_to_logical(frame[2], frame[3])
        corner = self.to_window(QPoint(round(left), round(top)))
        far = self.to_window(QPoint(round(right), round(bottom)))
        kx, ky = w / mw, h / mh
        ox, oy = x + corner.x() * here * kx, y + corner.y() * here * ky
        ow, oh = (far.x() - corner.x()) * here * kx, (far.y() - corner.y()) * here * ky
        took = "client area" if game.client_area else "whole window"
        border = ""
        picture = self._picture(QApplication.screenAt(self._area.center()) or QApplication.primaryScreen())
        if picture is not None:
            start, end = self.to_window(picture.topLeft()), self.to_window(picture.bottomRight() + QPoint(1, 1))
            bx, by = x + start.x() * here * kx, y + start.y() * here * ky
            bw, bh = (end.x() - start.x()) * here * kx, (end.y() - start.y()) * here * ky
            border = f"; the 心动 border plays over ({bx:.0f}, {by:.0f}) {bw:.0f}x{bh:.0f} of the canvas"
        return (
            head + mine + f"; game 「{game.title}」 ({took} {frame[2] - frame[0]}x{frame[3] - frame[1]} px at ({frame[0]}, {frame[1]})) "
            f"lands at ({gx:.0f}, {gy:.0f}) {gw:.0f}x{gh:.0f}; 直播画面 draws it at ({ox:.0f}, {oy:.0f}) {ow:.0f}x{oh:.0f}: "
            f"off by ({round(ox - gx):+d}, {round(oy - gy):+d}), size ×{ow / max(1.0, gw):.3f}" + border
        )

    def _picture(self, screen) -> QRect | None:  # noqa: ANN001
        """The game's picture on the screen, where the 心动 border plays (the main window works it out)."""
        find = getattr(self._window, "_game_area", None)
        return find(screen) if find is not None and screen is not None else None

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
