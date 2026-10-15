"""选择片段: which part of a sound the player uploaded for a 特效 plays, when the file is longer than a 特效's
sound may be (5 s).

The whole sound is drawn as a strip, its loudest moment per pixel in the accent colour, with a window over
the part that plays: the first limit_s seconds at first. Dragging the window moves it, dragging either of its
edges makes it shorter or longer (never longer than limit_s, shorter than MIN_S or past the file's ends), and
← → move it by NUDGE_S. What lies outside it is drawn faint. 试听 plays the part picked, through the caller's
preview(start, length), and turns into 停止 until it has played; 确定 keeps it, × and Esc keep nothing.

The dialog is made from plain values (the samples, their rate and the file's name), so it knows nothing of
how the file was read; the caller keeps only the part picked (selection()).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from PySide6.QtCore import QElapsedTimer, QEvent, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from blacklist_detect.ui_dialogs import _primary
from blacklist_detect.ui_kit import Modal, _KeyboardRing
from blacklist_detect.ui_theme import THEME, _mix, _pointing, chinese_font

# The longest part a 特效's sound keeps, the shortest the window can be made, and an arrow key's step.
LIMIT_S = 5.0
MIN_S = 0.5
NUDGE_S = 0.1


def clock(seconds: float) -> str:
    """A moment of the sound as minutes and seconds to a tenth: 0:12.3."""
    tenths = max(0, round(seconds * 10))
    return f"{tenths // 600}:{tenths % 600 / 10:04.1f}"


def peaks(samples: np.ndarray, columns: int) -> np.ndarray:
    """The loudest sample in each of columns equal stretches of the sound, 0 to 32768."""
    count = len(samples)
    if count == 0 or columns <= 0:
        return np.zeros(max(columns, 0))
    starts = np.minimum(np.arange(columns) * count // columns, count - 1)
    # Highest and lowest apart: abs() of a whole int16 sound would copy it at twice its size first.
    high = np.maximum.reduceat(samples, starts).astype(np.int32)
    low = np.minimum.reduceat(samples, starts).astype(np.int32)
    return np.maximum(high, -low).astype(np.float64)


def _arrow(event) -> float | None:  # noqa: ANN001
    """How far ← or → moves the window, in seconds; None for any other key."""
    if event.modifiers() & ~Qt.KeypadModifier:
        return None
    return {Qt.Key_Left: -NUDGE_S, Qt.Key_Right: NUDGE_S}.get(event.key())


def _glyph(kind: str, side: int, color: str) -> QIcon:
    """A solid ▶ (play) or ■ (stop), for 试听."""
    ratio = 2.0
    image = QPixmap(round(side * ratio), round(side * ratio))
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(ratio, ratio)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    if kind == "play":
        p.drawPolygon(QPolygonF([QPointF(side * 0.2, side * 0.1), QPointF(side * 0.9, side * 0.5), QPointF(side * 0.2, side * 0.9)]))
    else:
        p.drawRoundedRect(QRectF(side * 0.18, side * 0.18, side * 0.64, side * 0.64), 1.5, 1.5)
    p.end()
    image.setDevicePixelRatio(ratio)
    return QIcon(image)


class Waveform(_KeyboardRing, QWidget):
    """The whole sound as a strip, with the window over the part picked. start and length are in seconds;
    changed(start, length) says the window moved or was resized, by the mouse or the arrow keys.
    playhead, while 试听 plays, is how far into the window it is, in seconds."""

    changed = Signal(float, float)

    W = 560
    H = 104
    RADIUS = 8
    # Room left and right of the sound, so the window's edges at its very start and end can be taken.
    INSET = 8
    # How near an edge of the window a press takes that edge rather than the window (inside it, at most a
    # quarter of the window).
    GRIP = 7

    def __init__(self, samples: np.ndarray, rate: int, limit_s: float = LIMIT_S, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.samples = np.asarray(samples, dtype=np.int16).reshape(-1)
        self.duration = len(self.samples) / rate if rate > 0 else 0.0
        self.limit = min(limit_s, self.duration)
        self.shortest = min(MIN_S, self.limit)
        self.start = 0.0
        self.length = self.limit
        self.playhead: float | None = None
        self.setFixedSize(QSize(self.W, self.H))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setAccessibleName("选择片段")
        self._peaks: np.ndarray | None = None
        # What a press took: "move" (the window, held offset seconds from its start), "left" or "right".
        self._held = ""
        self._offset = 0.0

    def selection(self) -> tuple[float, float]:
        return self.start, self.length

    def set_selection(self, start: float, length: float) -> None:
        """The window from start, length long, kept within limit, the shortest and the sound's ends."""
        length = min(max(length, self.shortest), self.limit)
        start = min(max(start, 0.0), self.duration - length)
        if (start, length) == (self.start, self.length):
            return
        self.start, self.length = start, length
        self.update()
        self.changed.emit(start, length)

    def nudge(self, seconds: float) -> None:
        self.set_selection(self.start + seconds, self.length)

    # Where moments of the sound are on the strip, and back.
    def _span(self) -> tuple[float, float]:
        return float(self.INSET), float(self.width() - 2 * self.INSET)

    def x_of(self, seconds: float) -> float:
        left, wide = self._span()
        return left + (seconds / self.duration * wide if self.duration else 0.0)

    def time_at(self, x: float) -> float:
        left, wide = self._span()
        return min(max((x - left) / wide * self.duration, 0.0), self.duration)

    def _part(self, x: float) -> str:
        """What a press at x takes: an edge of the window, the window, or the strip outside it."""
        left, right = self.x_of(self.start), self.x_of(self.start + self.length)
        # Inside the window an edge reaches a quarter of it at most, so the middle half of a narrow one (5 s of
        # a long song is a dozen pixels) still moves it; outside, each edge reaches GRIP.
        reach = min(self.GRIP, (right - left) / 4)
        if left + reach < x < right - reach:
            return "move"
        near_left, near_right = left - self.GRIP <= x <= left + reach, right - reach <= x <= right + self.GRIP
        if near_left and near_right:
            return "left" if x < (left + right) / 2 else "right"
        if near_left:
            return "left"
        if near_right:
            return "right"
        return ""

    def _grab(self, part: str) -> None:
        cursors = {"left": Qt.SizeHorCursor, "right": Qt.SizeHorCursor, "move": Qt.OpenHandCursor, "": Qt.PointingHandCursor}
        self.setCursor(Qt.ClosedHandCursor if self._held == "move" else cursors[part])

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if event.button() != Qt.LeftButton or not self.duration:
            super().mousePressEvent(event)
            return
        x = event.position().x()
        part = self._part(x)
        if not part:
            # A press beside the window brings it there, centred on the press, to be dragged on.
            self.set_selection(self.time_at(x) - self.length / 2, self.length)
            part = "move"
        self._held = part
        self._offset = self.time_at(x) - self.start
        self._grab(part)
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: ANN001
        x = event.position().x()
        if not self._held:
            self._grab(self._part(x))
            return
        at = self.time_at(x)
        end = self.start + self.length
        if self._held == "move":
            self.set_selection(at - self._offset, self.length)
        elif self._held == "left":
            start = min(max(at, end - self.limit, 0.0), end - self.shortest)
            self.set_selection(start, end - start)
        else:
            end = min(max(at, self.start + self.shortest), self.start + self.limit, self.duration)
            self.set_selection(self.start, end - self.start)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.LeftButton and self._held:
            self._held = ""
            self._grab(self._part(event.position().x()))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: ANN001
        step = _arrow(event)
        if step is None:
            super().keyPressEvent(event)
            return
        self.nudge(step)
        event.accept()

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        self._peaks = None
        super().resizeEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        box = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        strip = QPainterPath()
        strip.addRoundedRect(box, self.RADIUS, self.RADIUS)
        p.setPen(QPen(QColor(THEME["border"]), 1))
        p.setBrush(QColor(THEME["surface_alt"]))
        p.drawPath(strip)
        p.setClipPath(strip)
        left, right = self.x_of(self.start), self.x_of(self.start + self.length)
        band = QRectF(left, box.top(), right - left, box.height())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(THEME["accent_wash"]))
        p.drawRect(band)
        # The sound, one bar per pixel as tall as its loudest sample there: the accent in the window,
        # faint outside it. A quiet file is drawn as big as a loud one.
        first, wide = self._span()
        columns = max(1, round(wide))
        if self._peaks is None or len(self._peaks) != columns:
            found = peaks(self.samples, columns)
            self._peaks = found / max(float(found.max(initial=0.0)), 1000.0)
        middle = self.height() / 2
        reach = middle - 10
        inside = QColor(THEME["accent_line"])
        outside = _mix(THEME["surface_alt"], THEME["muted"], 0.5)
        for column, loud in enumerate(self._peaks):
            x = first + column
            half = max(0.5, loud * reach)
            p.fillRect(QRectF(x, middle - half, 1.0, 2 * half), inside if left <= x + 0.5 <= right else outside)
        # The window's edges, each with a grip to take, light on the sound.
        p.setPen(QPen(inside, 1.5))
        p.setBrush(QColor(THEME["surface"]))
        for x in (left, right):
            p.fillRect(QRectF(x - 1, box.top(), 2, box.height()), inside)
            p.drawRoundedRect(QRectF(x - 3.5, middle - 13, 7, 26), 3.5, 3.5)
        if self.playhead is not None:
            at = self.x_of(self.start + min(self.playhead, self.length))
            p.fillRect(QRectF(at - 0.75, box.top(), 1.5, box.height()), QColor(THEME["text"]))
        p.setClipping(False)
        if self.show_ring():
            p.setPen(QPen(QColor(THEME["accent_line"]), 1.5, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(box.adjusted(1, 1, -1, -1), self.RADIUS - 1, self.RADIUS - 1)
        p.end()


class SoundTrimDialog(Modal):
    """选择片段: the part of a sound longer than limit_s that a 特效 plays. samples: the sound, mono int16
    at rate; name: its file's name. preview(start, length) plays that part, stop() stops it. selection()
    is (start, length) in seconds; 确定 accepts it."""

    def __init__(
        self,
        samples: np.ndarray,
        rate: int,
        name: str,
        preview: Callable[[float, float], None],
        stop: Callable[[], None],
        parent: QWidget | None = None,
        limit_s: float = LIMIT_S,
    ) -> None:
        super().__init__(parent)
        self.preview = preview
        self.stop = stop
        self.playing = False
        layout = self.frame("选择片段")
        self.wave = Waveform(samples, rate, limit_s)
        self.wave.changed.connect(self._changed)
        self._first = self.wave.selection()
        about = QVBoxLayout()
        about.setSpacing(2)
        title = chinese_font()
        title.setWeight(QFont.DemiBold)
        self.name = QLabel(QFontMetrics(title).elidedText(name, Qt.ElideMiddle, Waveform.W))
        self.name.setFont(title)
        self.name.setToolTip(name)
        about.addWidget(self.name)
        self.hint = QLabel(f"共 {clock(self.wave.duration)} · 拖动选框选一段，最长 {limit_s:g} 秒")
        self.hint.setObjectName("sub")
        about.addWidget(self.hint)
        layout.addLayout(about)
        layout.addWidget(self.wave)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.play_button = QPushButton("试听")
        self.play_button.setAutoDefault(False)
        self.play_button.setIconSize(QSize(12, 12))
        self.play_button.clicked.connect(self.toggle_preview)
        row.addWidget(self.play_button)
        self.times = QLabel()
        row.addWidget(self.times)
        row.addStretch(1)
        keys = QLabel("← → 微调")
        keys.setObjectName("sub")
        row.addWidget(keys)
        layout.addLayout(row)
        self.ok_button = _primary("确定", self.accept)
        self.footer(self.ok_button)
        _pointing(self)
        for button in (self.play_button, self.ok_button):
            button.installEventFilter(self)
        self._show_play(False)
        self._show_times()
        self._clock = QElapsedTimer()
        self._tick = QTimer(self)
        self._tick.setInterval(33)
        self._tick.timeout.connect(self._advance)
        self.wave.setFocus()

    def selection(self) -> tuple[float, float]:
        """The part picked: where it starts and how long it is, in seconds, to the millisecond."""
        start, length = self.wave.selection()
        return round(start, 3), round(length, 3)

    def has_changes(self) -> bool:
        return self.wave.selection() != self._first

    def _show_times(self) -> None:
        start, length = self.wave.selection()
        self.times.setText(f"{clock(start)} – {clock(start + length)} · {length:.1f} 秒")

    def _show_play(self, playing: bool) -> None:
        self.play_button.setText("停止" if playing else "试听")
        self.play_button.setIcon(_glyph("stop" if playing else "play", 12, THEME["text"]))
        self.play_button.setAccessibleName("停止试听" if playing else "试听这一段")

    def toggle_preview(self) -> None:
        """试听: the part picked, from its start; while it plays, 停止."""
        if self.playing:
            self._end(stop=True)
            return
        start, length = self.selection()
        self.preview(start, length)
        self.playing = True
        self._show_play(True)
        self._clock.start()
        self.wave.playhead = 0.0
        self._tick.start()

    def _advance(self) -> None:
        """The playhead on with the sound; once the part has played, 试听 again."""
        played = self._clock.elapsed() / 1000
        if played >= self.wave.length:
            self._end(stop=False)
            return
        self.wave.playhead = played
        self.wave.update()

    def _end(self, stop: bool) -> None:
        """No longer playing; stop: cut the sound short too."""
        if not self.playing:
            return
        if stop:
            self.stop()
        self.playing = False
        self._tick.stop()
        self.wave.playhead = None
        self.wave.update()
        self._show_play(False)

    def _changed(self, _start: float, _length: float) -> None:
        """The window moved: what plays is no longer what is picked, so it stops."""
        self._end(stop=True)
        self._show_times()

    def eventFilter(self, watched, event) -> bool:  # noqa: ANN001
        # ← → move the window with 试听 or 确定 focused too: in a dialog a button would take them to move
        # the focus to the next button.
        if event.type() == QEvent.Type.KeyPress and (step := _arrow(event)) is not None:
            self.wave.nudge(step)
            return True
        return super().eventFilter(watched, event)

    def done(self, result: int) -> None:  # noqa: A003
        self._end(stop=True)
        super().done(result)
