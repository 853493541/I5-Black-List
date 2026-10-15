"""选择片段: which part of a sound the player uploaded for a 场景 plays, when the file is longer than a 场景's
sound may be (5 s).

A player for the whole sound, to capture from: it plays from its start as the dialog opens (unless 静音), a
playhead running along the strip, and 截取 takes the limit_s seconds just heard. The sound is drawn as a
strip, its loudest moment per pixel in the accent colour, with a window over the part that plays: the first
limit_s seconds at first. A press or a drag on the strip moves the playhead there (the sound goes on from it
once let go); dragging either of the window's edges makes it shorter or longer (never longer than limit_s,
shorter than MIN_S or past the file's ends); ◀ ▶ and ← → move it by NUDGE_S. What lies outside it is drawn
faint. 暂停 / 播放 pauses the sound and goes on with it, through the caller's play(at), which plays the
sound from at to its end. 试听 pauses it and plays the part picked, through the caller's preview(start,
length), and turns into 停止 until it has played. Under 静音 (muted) neither can be pressed, but the playhead
still moves and 截取 still takes. 确定 keeps the part and plays nothing, × and Esc keep nothing. Why a part
cannot be heard or kept (a silent one, say), as the caller's preview or check has it, shows beside 截取 in
red until the window moves, and 确定 leaves the dialog open on it.

The dialog is made from plain values (the samples, their rate and the file's name), so it knows nothing of
how the file was read or played; the caller keeps only the part picked (selection()). Time is the caller's
now(), so tests can run it.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import numpy as np
from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from blacklist_detect.ui_dialogs import _primary
from blacklist_detect.ui_kit import Modal, _KeyboardRing
from blacklist_detect.ui_theme import THEME, _mix, _pointing, chinese_font, is_dark

# The longest part a 场景's sound keeps, the shortest the window can be made, and an arrow key's step.
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


def _grounds() -> tuple[QColor, QColor]:
    """The strip's ground inside the window and outside it, the outside plainly dimmer in either scheme (in
    the light one the accent's wash and the card's alt are all but the same, so both are its own)."""
    if is_dark():
        return QColor(THEME["accent_wash"]), QColor(THEME["surface_alt"])
    return _mix(THEME["surface"], THEME["accent_line"], 0.08), _mix(THEME["surface_alt"], THEME["muted"], 0.14)


def _glyph(kind: str, side: int, color: str) -> QIcon:
    """A solid ▶ (play), ◀ (back), ■ (stop) or ⏸ (pause), for the dialog's buttons."""
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
    elif kind == "back":
        p.drawPolygon(QPolygonF([QPointF(side * 0.8, side * 0.1), QPointF(side * 0.1, side * 0.5), QPointF(side * 0.8, side * 0.9)]))
    elif kind == "pause":
        for left in (0.2, 0.58):
            p.drawRoundedRect(QRectF(side * left, side * 0.12, side * 0.22, side * 0.76), 1.0, 1.0)
    else:
        p.drawRoundedRect(QRectF(side * 0.18, side * 0.18, side * 0.64, side * 0.64), 1.5, 1.5)
    p.end()
    image.setDevicePixelRatio(ratio)
    return QIcon(image)


class Waveform(_KeyboardRing, QWidget):
    """The whole sound as a strip, with the window over the part picked and the playhead. start and length
    are in seconds; changed(start, length) says the window moved or was resized, by the mouse or the arrow
    keys. playhead is where the sound is, in seconds; seek(at, done) asks for it to go to at, done once the
    mouse is let go. trial, while 试听 plays, is where in the sound it is."""

    changed = Signal(float, float)
    seek = Signal(float, bool)

    W = 560
    H = 104
    RADIUS = 8
    # Room left and right of the sound, so the window's edges at its very start and end can be taken.
    INSET = 8
    # How near an edge of the window a press takes that edge rather than the playhead.
    GRIP = 7

    def __init__(self, samples: np.ndarray, rate: int, limit_s: float = LIMIT_S, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.samples = np.asarray(samples, dtype=np.int16).reshape(-1)
        self.duration = len(self.samples) / rate if rate > 0 else 0.0
        self.limit = min(limit_s, self.duration)
        self.shortest = min(MIN_S, self.limit)
        self.start = 0.0
        self.length = self.limit
        self.playhead = 0.0
        self.trial: float | None = None
        self.setFixedSize(QSize(self.W, self.H))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setAccessibleName("选择片段")
        self._peaks: np.ndarray | None = None
        # What a press took: "left" or "right" (an edge of the window), or "seek" (the playhead).
        self._held = ""

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
        """What a press at x takes: an edge of the window, or else the playhead ("")."""
        left, right = self.x_of(self.start), self.x_of(self.start + self.length)
        # Each edge reaches GRIP either side of it, but no further in than the window's middle: a narrow
        # window is all grips, its left half the left edge's.
        centre = (left + right) / 2
        if left - self.GRIP <= x <= min(left + self.GRIP, centre):
            return "left"
        if max(right - self.GRIP, centre) <= x <= right + self.GRIP:
            return "right"
        return ""

    def _grab(self, part: str) -> None:
        self.setCursor(Qt.SizeHorCursor if part in ("left", "right") else Qt.PointingHandCursor)

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if event.button() != Qt.LeftButton or not self.duration:
            super().mousePressEvent(event)
            return
        x = event.position().x()
        self._held = self._part(x) or "seek"
        if self._held == "seek":
            self.seek.emit(self.time_at(x), False)
        self._grab(self._held)
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: ANN001
        x = event.position().x()
        if not self._held:
            self._grab(self._part(x))
            return
        at = self.time_at(x)
        end = self.start + self.length
        if self._held == "seek":
            self.seek.emit(at, False)
        elif self._held == "left":
            start = min(max(at, end - self.limit, 0.0), end - self.shortest)
            self.set_selection(start, end - start)
        else:
            end = min(max(at, self.start + self.shortest), self.start + self.limit, self.duration)
            self.set_selection(self.start, end - self.start)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.LeftButton and self._held:
            x = event.position().x()
            if self._held == "seek":
                self.seek.emit(self.time_at(x), True)
            self._held = ""
            self._grab(self._part(x))
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
        within, beyond = _grounds()
        p.setPen(QPen(QColor(THEME["border"]), 1))
        p.setBrush(beyond)
        p.drawPath(strip)
        p.setClipPath(strip)
        left, right = self.x_of(self.start), self.x_of(self.start + self.length)
        band = QRectF(left, box.top(), right - left, box.height())
        p.setPen(Qt.NoPen)
        p.setBrush(within)
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
        outside = _mix(beyond.name(), THEME["muted"], 0.5)
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
        # Where 试听 is in the part, in the accent; where the sound is, a thin line in the text's colour.
        if self.trial is not None:
            at = self.x_of(min(self.trial, self.start + self.length))
            p.fillRect(QRectF(at - 0.75, box.top(), 1.5, box.height()), inside)
        at = self.x_of(min(max(self.playhead, 0.0), self.duration))
        p.fillRect(QRectF(at - 0.75, box.top(), 1.5, box.height()), QColor(THEME["text"]))
        p.setClipping(False)
        if self.show_ring():
            p.setPen(QPen(QColor(THEME["accent_line"]), 1.5, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(box.adjusted(1, 1, -1, -1), self.RADIUS - 1, self.RADIUS - 1)
        p.end()


class SoundTrimDialog(Modal):
    """选择片段: the part of a sound longer than limit_s that a 场景 plays. samples: the sound, mono int16
    at rate; name: its file's name. play(at) plays the sound from at to its end, or returns why it cannot;
    preview(start, length) plays that part, or returns why it cannot; stop() stops either; check(start,
    length) is why a part cannot be kept, or "". muted: nothing would be heard, so neither can be pressed.
    now: the time in seconds (time.monotonic). selection() is (start, length) in seconds; 确定 accepts it."""

    def __init__(
        self,
        samples: np.ndarray,
        rate: int,
        name: str,
        preview: Callable[[float, float], str | None],
        stop: Callable[[], None],
        parent: QWidget | None = None,
        limit_s: float = LIMIT_S,
        muted: bool = False,
        check: Callable[[float, float], str] | None = None,
        play: Callable[[float], str | None] | None = None,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(parent)
        self.preview = preview
        self.stop = stop
        self.check = check
        self.play = play
        self.now = now
        self.muted = muted
        # 试听 plays (playing), or the sound does (running), from offset seconds in at now() began.
        self.playing = False
        self.running = False
        self.offset = 0.0
        self._began = 0.0
        self._tried = 0.0
        # A drag of the playhead paused the sound, to go on where it is let go.
        self._resume = False
        self._opened = False
        layout = self.frame("选择片段")
        self.wave = Waveform(samples, rate, limit_s)
        self.wave.changed.connect(self._changed)
        self.wave.seek.connect(self._seek)
        self._first = self.wave.selection()
        about = QVBoxLayout()
        about.setSpacing(2)
        title = chinese_font()
        title.setWeight(QFont.DemiBold)
        self.name = QLabel(QFontMetrics(title).elidedText(name, Qt.ElideMiddle, Waveform.W))
        self.name.setFont(title)
        self.name.setToolTip(name)
        about.addWidget(self.name)
        self.hint = QLabel(f"共 {clock(self.wave.duration)} · 边听边按「截取」，取下刚听到的 {self.wave.limit:g} 秒")
        self.hint.setObjectName("sub")
        about.addWidget(self.hint)
        layout.addLayout(about)
        layout.addWidget(self.wave)
        self.where = QLabel()
        self.where.setObjectName("sub")
        layout.addWidget(self.where)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.pause_button = self._button("暂停", self.toggle_song)
        row.addWidget(self.pause_button)
        self.cut_button = self._button("截取", self.cut)
        self.cut_button.setAccessibleName(f"截取刚听到的 {self.wave.limit:g} 秒")
        row.addWidget(self.cut_button)
        self.times = QLabel()
        row.addWidget(self.times)
        row.addStretch(1)
        layout.addLayout(row)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.back_button = self._button("", lambda: self.wave.nudge(-NUDGE_S), "back", "往前微调")
        self.on_button = self._button("", lambda: self.wave.nudge(NUDGE_S), "play", "往后微调")
        for button in (self.back_button, self.on_button):
            button.setAutoRepeat(True)
            row.addWidget(button)
        keys = QLabel(f"微调 {NUDGE_S:g} 秒")
        keys.setObjectName("sub")
        row.addWidget(keys)
        row.addStretch(1)
        self.play_button = self._button("试听", self.toggle_preview)
        row.addWidget(self.play_button)
        layout.addLayout(row)
        if muted:
            for button in (self.pause_button, self.play_button):
                button.setEnabled(False)
                button.setToolTip("已静音")
        self.ok_button = _primary("确定", self.accept)
        self.footer(self.ok_button)
        _pointing(self)
        for button in (self.pause_button, self.cut_button, self.back_button, self.on_button, self.play_button, self.ok_button):
            button.installEventFilter(self)
        self._show_play(False)
        self._show_song()
        self._show_head()
        self._show_times()
        self._tick = QTimer(self)
        self._tick.setInterval(33)
        self._tick.timeout.connect(self._advance)
        self.wave.setFocus()

    def _button(self, text: str, action: Callable[[], None], glyph: str = "", name: str = "") -> QPushButton:
        button = QPushButton(text)
        button.setAutoDefault(False)
        button.setIconSize(QSize(12, 12))
        if glyph:
            button.setIcon(_glyph(glyph, 12, THEME["text"]))
        if name:
            button.setAccessibleName(name)
            button.setToolTip(name)
        button.clicked.connect(action)
        return button

    def selection(self) -> tuple[float, float]:
        """The part picked: where it starts and how long it is, in seconds, to the millisecond."""
        start, length = self.wave.selection()
        return round(start, 3), round(length, 3)

    def has_changes(self) -> bool:
        return self.wave.selection() != self._first

    def head(self) -> float:
        """Where the sound is, in seconds: on with the clock while it plays."""
        if not self.running:
            return self.offset
        return min(self.offset + self.now() - self._began, self.wave.duration)

    def _show_times(self, reason: str = "") -> None:
        """Where the part picked starts and ends, or, in red, why it cannot be heard or kept."""
        start, length = self.wave.selection()
        self.times.setObjectName("error" if reason else "")
        self.times.style().unpolish(self.times)
        self.times.style().polish(self.times)
        self.times.setText(reason or f"选中 {clock(start)} – {clock(start + length)} · {length:.1f} 秒")

    def _show_head(self) -> None:
        at = self.head()
        self.wave.playhead = at
        self.wave.update()
        self.where.setText(f"{clock(at)} / {clock(self.wave.duration)}")

    def _show_play(self, playing: bool) -> None:
        self.play_button.setText("停止" if playing else "试听")
        self.play_button.setIcon(_glyph("stop" if playing else "play", 12, THEME["text"]))
        self.play_button.setAccessibleName("停止试听" if playing else "试听这一段")

    def _show_song(self) -> None:
        self.pause_button.setText("暂停" if self.running else "播放")
        self.pause_button.setIcon(_glyph("pause" if self.running else "play", 12, THEME["text"]))
        self.pause_button.setAccessibleName("暂停" if self.running else "从这里播放")

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        if not self._opened:
            # The sound plays from its start as the dialog opens: the player listens for the part.
            self._opened = True
            self._start_song()

    def _start_song(self) -> None:
        """The sound on from the playhead (from its start once it has played to its end)."""
        if self.running or not self.pause_button.isEnabled():
            return
        self._end(stop=False)
        if self.offset >= self.wave.duration:
            self.offset = 0.0
        if self.play is not None and (reason := self.play(self.offset)):
            self._show_times(reason)
            return
        self.running = True
        self._began = self.now()
        self._show_song()
        self._tick.start()

    def _halt(self) -> None:
        """The sound paused where it is."""
        if not self.running:
            return
        self.offset = self.head()
        self.running = False
        self.stop()
        if not self.playing:
            self._tick.stop()
        self._show_song()
        self._show_head()

    def toggle_song(self) -> None:
        """暂停 while the sound plays, else 播放 from the playhead."""
        if self.running:
            self._halt()
        else:
            self._start_song()

    def cut(self) -> None:
        """截取: the limit_s seconds just heard, up to the playhead (the first limit_s before it is that far in)."""
        at = self.head()
        self.wave.set_selection(at - self.wave.limit, self.wave.limit)

    def _seek(self, at: float, done: bool) -> None:
        """The playhead pressed or dragged to at: the sound waits while it is held, and goes on from there."""
        if self.running:
            self._halt()
            self._resume = True
        self.offset = at
        self._show_head()
        if done and self._resume:
            self._resume = False
            self._start_song()

    def toggle_preview(self) -> None:
        """试听: the sound paused, and the part picked from its start; while it plays, 停止."""
        if self.playing:
            self._end(stop=True)
            return
        if not self.play_button.isEnabled():
            return
        self._halt()
        start, length = self.selection()
        if reason := self.preview(start, length):
            self._show_times(reason)
            return
        self.playing = True
        self._show_play(True)
        self._tried = self.now()
        self.wave.trial = self.wave.start
        self.wave.update()
        self._tick.start()

    def _advance(self) -> None:
        """The playhead on with the sound, and 试听's mark with the part; whichever has played to its end, done."""
        if self.playing:
            played = self.now() - self._tried
            if played >= self.wave.length:
                self._end(stop=False)
            else:
                self.wave.trial = self.wave.start + played
        if self.running and self.head() >= self.wave.duration:
            self.offset = self.wave.duration
            self.running = False
            self._show_song()
        self._show_head()
        if not (self.playing or self.running):
            self._tick.stop()

    def _end(self, stop: bool) -> None:
        """试听 no longer playing; stop: cut its sound short too."""
        if not self.playing:
            return
        if stop:
            self.stop()
        self.playing = False
        if not self.running:
            self._tick.stop()
        self.wave.trial = None
        self.wave.update()
        self._show_play(False)

    def _changed(self, _start: float, _length: float) -> None:
        """The window moved: what 试听 plays is no longer what is picked, so it stops."""
        self._end(stop=True)
        self._show_times()

    def eventFilter(self, watched, event) -> bool:  # noqa: ANN001
        # ← → move the window with a button focused too: in a dialog a button would take them to move the
        # focus to the next button.
        if event.type() == QEvent.Type.KeyPress and (step := _arrow(event)) is not None:
            self.wave.nudge(step)
            return True
        return super().eventFilter(watched, event)

    def _quiet(self) -> None:
        self._end(stop=True)
        self._halt()
        self._resume = False

    def accept(self) -> None:
        """确定: the part picked, unless it cannot be kept; then why, and the dialog stays for another. Nothing
        plays: the sound and 试听 stop, and the part is not played again."""
        self._quiet()
        if self.check is not None and (reason := self.check(*self.selection())):
            self._show_times(reason)
            return
        super().accept()

    def done(self, result: int) -> None:  # noqa: A003
        self._quiet()
        super().done(result)
