"""场景管理's signs that a sound plays: a few bars rising and falling at the right of its row (SoundWave), and the
⏸ its ▶ becomes meanwhile (pause_icon), drawn as ui_icons draws ▶, a ring with the sign in it."""

from __future__ import annotations

import math

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from blacklist_detect.ui_theme import THEME


def pause_icon(size: int = 16, color: str | None = None) -> QIcon:
    """⏸ in a ring, at size × size logical pixels, its lines as thick as ui_icons' ▶ beside it."""
    ratio = 2.0
    image = QPixmap(round(size * ratio), round(size * ratio))
    image.setDevicePixelRatio(ratio)
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 24.0, size / 24.0)
    pen = QPen(QColor(color or THEME["muted"]), (1.4 if size <= 20 else 2.0) * 24.0 / size)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawEllipse(QPointF(12, 12), 8.5, 8.5)
    for x in (10.2, 13.8):
        p.drawLine(QPointF(x, 9.0), QPointF(x, 15.0))
    p.end()
    return QIcon(image)


class SoundWave(QWidget):
    """Bars rising and falling in the theme's accent while a sound plays (run(True)); hidden and still
    otherwise (its row keeps its room). Its timer runs only while it plays and is seen."""

    BARS = 5
    W = 30
    H = 18
    BAR_W = 3.6
    # A frame each this many ms: smooth enough for bars this small.
    FRAME_MS = 40

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(QSize(self.W, self.H))
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAccessibleName("正在播放")
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(self.FRAME_MS)
        self._timer.timeout.connect(self.update)
        self.hide()

    @property
    def running(self) -> bool:
        return self._timer.isActive()

    def run(self, on: bool) -> None:  # noqa: FBT001
        """Shown and moving while on; hidden and still otherwise."""
        if on:
            if not self.running:
                self._clock.start()
                self._timer.start()
            self.show()
        else:
            self._timer.stop()
            self.hide()

    def levels(self, t: float) -> list[float]:
        """Each bar's height at t seconds, 0.2 to 1 of the room: two slow waves on each, out of step with the
        bars beside it, so they read as music, not a pulse."""
        out = []
        for bar in range(self.BARS):
            wave = 0.55 * math.sin(t * (7.0 + 1.3 * bar) + bar * 1.9) + 0.45 * math.sin(t * (11.0 - 0.9 * bar) + bar * 0.7)
            out.append(0.2 + 0.8 * (0.5 + 0.5 * wave))
        return out

    def hideEvent(self, event) -> None:  # noqa: ANN001
        # Out of sight, with its dialog too: nothing to paint for.
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(THEME["accent"]))
        t = self._clock.elapsed() / 1000 if self._clock.isValid() else 0.0
        gap = (self.W - self.BARS * self.BAR_W) / (self.BARS - 1)
        for bar, level in enumerate(self.levels(t)):
            height = max(self.BAR_W, level * self.H)
            box = QRectF(bar * (self.BAR_W + gap), (self.H - height) / 2, self.BAR_W, height)
            p.drawRoundedRect(box, self.BAR_W / 2, self.BAR_W / 2)
        p.end()
