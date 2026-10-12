"""The border that greets two or more 心动 players in a lobby.

Sheer silk swags drop in across the top from knots of flowers; a thin rose-gold frame with curls
draws itself out from the middle of each edge; roses bloom in the two bottom corners; glints
blink and drift down; the sides glow pink. It plays once, about four and a half seconds, then
goes. The bottom of the frame parts around the accept button and its marks, which sit close to
the bottom of the game, and clicks pass through the whole window to the game.
"""

from __future__ import annotations

import math
import random

from PySide6.QtCore import QElapsedTimer, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QWidget

from blacklist_detect.ui_overlay import _alpha, _knot, _pin_topmost, _sparkle

DURATION = 4.6
# By then the frame, the roses and the knots have settled; from there they are drawn from a picture
# kept of them, and only the silk and the glints are painted again each frame.
_SETTLED = 1.6
# The frames were drawn for a game about this big, in window coordinates.
_DESIGN = (1635.0, 848.0)
_SILK = (
    # sag, width, color, alpha
    (150, 30, (255, 214, 236), 0.20),
    (132, 16, (255, 236, 246), 0.30),
    (166, 11, (230, 220, 255), 0.24),
    (122, 2.4, (255, 255, 255), 0.80),
    (156, 1.8, (255, 250, 255), 0.65),
)
_ROSES = ((60, 60, 46, 10), (140, 34, 32, 40), (36, 150, 30, 70), (120, 120, 22, 20))


def _ease_out(k: float) -> float:
    k = max(0.0, min(1.0, k))
    return 1 - (1 - k) ** 3


def _ease_back(k: float) -> float:
    """Overshoots a little and settles, like cloth dropping."""
    k = max(0.0, min(1.0, k))
    return 1 + 2.9 * (k - 1) ** 3 + 1.9 * (k - 1) ** 2


def _life(t: float) -> float:
    """In over the first half second, out over the last second."""
    return min(1.0, t / 0.5) * min(1.0, max(0.0, (DURATION - t) / 0.9))


class LoveBorder(QWidget):
    """A click-through window over the game's screen that plays the border once."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.Window
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
            | Qt.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.NoFocus)
        self._gap = QRectF()
        self._still: dict[str, QPixmap] = {}
        self._still_key: tuple = ()
        self._clock = QElapsedTimer()
        self._tick = QTimer(self)
        self._tick.setInterval(33)
        self._tick.timeout.connect(self._step)

    def play(self, area: QRect, keep_clear: QRect) -> None:
        """Cover area (the game's screen) and play, leaving keep_clear (the button and its marks) bare."""
        self.setGeometry(area)
        clear = QRectF(keep_clear.translated(-area.topLeft()))
        self._gap = QRectF(clear.left() - 28, clear.top() - 30, clear.width() + 56, area.height() - clear.top() + 30)
        self._still = {}
        self._clock.start()
        self._tick.start()
        self.show()
        _pin_topmost(self)
        self.update()

    def playing(self) -> bool:
        return self._tick.isActive()

    def stop(self) -> None:
        self._tick.stop()
        self.hide()

    def elapsed(self) -> float:
        return self._clock.elapsed() / 1000 if self._clock.isValid() else 0.0

    def _step(self) -> None:
        if self.elapsed() >= DURATION:
            self.stop()
            return
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.paint_at(painter, self.elapsed(), self.width(), self.height())
        painter.end()

    def paint_at(self, painter: QPainter, t: float, width: float, height: float, gap: QRectF | None = None) -> None:
        """The border at t seconds into its play, on a width by height area."""
        life = _life(t)
        if life <= 0:
            return
        unit = min(width / _DESIGN[0], height / _DESIGN[1])
        gap = gap if gap is not None else self._gap
        painter.save()
        painter.setOpacity(life)
        painter.setPen(Qt.NoPen)
        if t >= _SETTLED:
            still = self._settled(painter, width, height, unit, gap)
            painter.drawPixmap(0, 0, still["under"])
            self._swags(painter, t, width, unit)
            painter.drawPixmap(0, 0, still["over"])
        else:
            self._under(painter, t, width, height, unit, gap)
            self._swags(painter, t, width, unit)
            self._over(painter, t, width, unit)
        self._glints(painter, t, width, height, unit)
        painter.restore()

    def _under(self, painter: QPainter, t: float, width: float, height: float, unit: float, gap: QRectF) -> None:
        """What lies under the silk: the glowing sides, the frame parted around the button, the roses."""
        self._glow_sides(painter, width, height)
        keep = QPainterPath()
        keep.addRect(QRectF(0, 0, width, height))
        hole = QPainterPath()
        hole.addRoundedRect(gap, 14, 14)
        painter.save()
        painter.setClipPath(keep.subtracted(hole))
        self._frame(painter, t, width, height, unit)
        painter.restore()
        self._roses(painter, min(t, _SETTLED), width, height, unit)

    def _over(self, painter: QPainter, t: float, width: float, unit: float) -> None:
        """The knots of flowers the silk hangs from."""
        for i in range(5):
            x = width * i / 4
            _knot(painter, x, 6 * unit + 20 * unit, 38 * unit * _ease_back((t - 0.15 - 0.06 * i) / 0.7))

    def _settled(self, painter: QPainter, width: float, height: float, unit: float, gap: QRectF) -> dict[str, QPixmap]:
        ratio = painter.device().devicePixelRatioF() if painter.device() is not None else 1.0
        key = (round(width), round(height), round(ratio * 100), gap.x(), gap.y(), gap.width(), gap.height())
        if key != self._still_key or not self._still:
            self._still = {}
            for name in ("under", "over"):
                picture = QPixmap(max(1, round(width * ratio)), max(1, round(height * ratio)))
                picture.setDevicePixelRatio(ratio)
                picture.fill(Qt.transparent)
                inner = QPainter(picture)
                inner.setRenderHint(QPainter.Antialiasing)
                inner.setPen(Qt.NoPen)
                if name == "under":
                    self._under(inner, _SETTLED, width, height, unit, gap)
                else:
                    self._over(inner, _SETTLED, width, unit)
                inner.end()
                self._still[name] = picture
            self._still_key = key
        return self._still

    @staticmethod
    def _glow_sides(painter: QPainter, width: float, height: float) -> None:
        """Pink-lavender light at the left and right edges, a little along the top."""
        reach = width * 0.14
        for x0, x1 in ((0.0, reach), (width, width - reach)):
            light = QLinearGradient(QPointF(x0, 0), QPointF(x1, 0))
            light.setColorAt(0, QColor(255, 170, 215, 102))
            light.setColorAt(0.5, QColor(205, 180, 255, 36))
            light.setColorAt(1, QColor(255, 170, 215, 0))
            painter.fillRect(QRectF(min(x0, x1), 0, reach, height), light)
        top = QLinearGradient(QPointF(0, 0), QPointF(0, height * 0.18))
        top.setColorAt(0, QColor(255, 200, 230, 71))
        top.setColorAt(1, QColor(255, 200, 230, 0))
        painter.fillRect(QRectF(0, 0, width, height * 0.18), top)

    @staticmethod
    def _swags(painter: QPainter, t: float, width: float, unit: float) -> list[QPointF]:
        """Sheer silk hanging between five points along the top, dropping in and swaying."""
        anchors = [QPointF(width * k / 4, 6 * unit) for k in range(5)]
        painter.setBrush(Qt.NoBrush)
        for i in range(4):
            a, b = anchors[i], anchors[i + 1]
            drop = _ease_back((t - 0.08 * abs(i - 1.5)) / 1.1)
            for layer, (sag, thick, rgb, alpha) in enumerate(_SILK):
                depth = (sag + 5 * math.sin(t * 1.6 + i * 0.9 + layer)) * unit * drop
                path = QPainterPath(a)
                path.quadTo(QPointF((a.x() + b.x()) / 2, a.y() + 2 * depth), b)
                pen = QPen(QColor(*rgb, round(255 * alpha)), thick * unit)
                pen.setCapStyle(Qt.RoundCap)
                painter.setPen(pen)
                painter.drawPath(path)
        painter.setPen(Qt.NoPen)
        return anchors

    @staticmethod
    def _frame(painter: QPainter, t: float, width: float, height: float, unit: float) -> None:
        """A thin rose-gold frame, drawn out from the middle of each edge, curls along top and bottom."""
        grow = _ease_out(t / 1.2)
        inset = 16 * unit
        half_w, half_h = (width / 2 - inset) * grow, (height / 2 - inset) * grow
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(_alpha("#ffd9e6", 0.9), 2 * unit))
        for y in (inset, height - inset):
            painter.drawLine(QPointF(width / 2 - half_w, y), QPointF(width / 2 + half_w, y))
        for x in (inset, width - inset):
            painter.drawLine(QPointF(x, height / 2 - half_h), QPointF(x, height / 2 + half_h))
        painter.setPen(QPen(_alpha("#f7c4d6", 0.55), max(1.0, unit)))
        for y in (inset + 7 * unit, height - inset - 7 * unit):
            painter.drawLine(QPointF(width / 2 - half_w, y), QPointF(width / 2 + half_w, y))
        painter.setPen(QPen(_alpha("#ffe3ec", 0.85), 1.6 * unit))
        step = 46 * unit
        for y, flip in ((inset + 22 * unit, 1), (height - inset - 22 * unit, -1)):
            reach = 0.0
            while reach < half_w - step:
                for x in (width / 2 + reach, width / 2 - reach):
                    curl = QPainterPath(QPointF(x - step / 2, y))
                    curl.cubicTo(QPointF(x - step / 4, y - 10 * unit * flip), QPointF(x, y - 10 * unit * flip), QPointF(x, y))
                    curl.cubicTo(QPointF(x, y + 6 * unit * flip), QPointF(x + step / 6, y + 6 * unit * flip), QPointF(x + step / 6, y + unit * flip))
                    curl.moveTo(QPointF(x, y))
                    curl.cubicTo(QPointF(x + step / 4, y + 9 * unit * flip), QPointF(x + step / 2, y + 4 * unit * flip), QPointF(x + step / 2, y))
                    painter.drawPath(curl)
                reach += step
        painter.setPen(Qt.NoPen)

    @staticmethod
    def _roses(painter: QPainter, t: float, width: float, height: float, unit: float) -> None:
        """Pale roses, with leaves, blooming in the two bottom corners."""
        for side, (cx, dirx) in enumerate(((0.0, 1), (width, -1))):
            blooms = [_ease_back((t - 0.3 - 0.12 * j - 0.1 * side) / 0.8) for j in range(len(_ROSES))]
            for j, (dx, dy, r, _turn) in enumerate(_ROSES):
                if blooms[j] > 0:
                    _leaf(painter, cx + dirx * (dx + r * 0.8) * unit, height - (dy - r * 0.2) * unit, r * 1.3 * unit * blooms[j], 30 * dirx + j * 25)
            for j, (dx, dy, r, turn) in enumerate(_ROSES):
                if blooms[j] > 0:
                    _rose(painter, cx + dirx * dx * unit, height - dy * unit, r * unit * blooms[j], turn + 6 * t)

    @staticmethod
    def _glints(painter: QPainter, t: float, width: float, height: float, unit: float) -> None:
        """Glints drifting slowly down from the swags, each blinking on and off."""
        rnd = random.Random(3)
        for _ in range(26):
            x = rnd.uniform(0.02, 0.98) * width
            y = rnd.uniform(0.0, 0.42) * height
            speed = rnd.uniform(8, 26) * unit
            period = rnd.uniform(0.9, 1.8)
            phase = rnd.uniform(0, period)
            r = rnd.uniform(4, 11) * unit
            blink = max(0.0, math.sin(((t + phase) % period) / period * math.pi)) ** 2
            _sparkle(painter, x, y + speed * t, r, blink)


def _rose(painter: QPainter, x: float, y: float, r: float, turn: float) -> None:
    """A pale rose seen from above: rings of rounded petals, deeper toward a closed bud."""
    if r < 0.5:
        return
    painter.save()
    painter.translate(x, y)
    painter.rotate(turn)
    glow = QRadialGradient(QPointF(0, 0), r * 1.9)
    glow.setColorAt(0, _alpha("#ffb6cf", 0.35))
    glow.setColorAt(1, _alpha("#ffb6cf", 0))
    painter.setPen(Qt.NoPen)
    painter.setBrush(glow)
    painter.drawEllipse(QPointF(0, 0), r * 1.9, r * 1.9)
    rings = (
        (5, 1.0, 0.62, "#ffe4ee", "#f7a9c4", 0),
        (5, 0.74, 0.5, "#ffd0e0", "#ee8fb2", 36),
        (4, 0.5, 0.42, "#ffbcd3", "#e07aa0", 15),
        (3, 0.3, 0.36, "#f9a5c3", "#cf6690", 60),
    )
    for count, reach, width, tip, base, offset in rings:
        for i in range(count):
            painter.save()
            painter.rotate(offset + i * 360 / count)
            shade = QLinearGradient(QPointF(0, 0), QPointF(0, -r * reach))
            shade.setColorAt(0, QColor(base))
            shade.setColorAt(1, QColor(tip))
            painter.setBrush(shade)
            painter.setPen(QPen(_alpha("#fff6f9", 0.75), max(0.7, r * 0.035)))
            petal = QPainterPath(QPointF(0, 0))
            petal.cubicTo(QPointF(-r * width, -r * reach * 0.35), QPointF(-r * width * 0.9, -r * reach), QPointF(0, -r * reach))
            petal.cubicTo(QPointF(r * width * 0.9, -r * reach), QPointF(r * width, -r * reach * 0.35), QPointF(0, 0))
            painter.drawPath(petal)
            painter.restore()
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#c85d86"))
    painter.drawEllipse(QPointF(0, 0), r * 0.1, r * 0.1)
    painter.restore()


def _leaf(painter: QPainter, x: float, y: float, length: float, angle: float) -> None:
    painter.save()
    painter.translate(x, y)
    painter.rotate(angle)
    leaf = QPainterPath(QPointF(0, 0))
    leaf.quadTo(QPointF(length * 0.5, -length * 0.32), QPointF(length, 0))
    leaf.quadTo(QPointF(length * 0.5, length * 0.32), QPointF(0, 0))
    painter.setPen(QPen(_alpha("#fff1e0", 0.7), 1))
    painter.setBrush(_alpha("#f6d6c4", 0.6))
    painter.drawPath(leaf)
    painter.restore()
