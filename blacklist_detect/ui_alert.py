"""The red glow around the screen while a lobby with 黑名单 players is shown.

A soft red light comes in from every edge of the game's screen, a little over a twentieth of its
height deep, and breathes slowly while the result is up. It is meant to be seen from the
corner of an eye, not to shout: the ring and the card beside the button say who. Clicks pass
through it to the game.

The glow is painted once; the breathing only changes the window's opacity, which Windows
blends without the picture being sent again, so it costs next to nothing while it stays up.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from blacklist_detect.ui_overlay import _pin_topmost

# The glow at the screen's edge, and how far in it reaches, as a share of the shorter side.
_RED = (225, 38, 52)
_EDGE_ALPHA = 150
_DEPTH = 0.055
# The slow breath: from this opacity to full and back, over this long.
_LOW = 0.68
_BREATH_MS = 2800
_FADE_MS = 260


class AlertGlow(QWidget):
    """A click-through window over the game's screen with a red glow at its edges."""

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
        self._breath = QPropertyAnimation(self, b"windowOpacity", self)
        self._breath.setDuration(_BREATH_MS)
        self._breath.setKeyValueAt(0.0, 1.0)
        self._breath.setKeyValueAt(0.5, _LOW)
        self._breath.setKeyValueAt(1.0, 1.0)
        self._breath.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._breath.setLoopCount(-1)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(_FADE_MS)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(self._after_fade)
        self._leaving = False

    def showing(self) -> bool:
        return self.isVisible() and not self._leaving

    def show_on(self, area: QRect) -> None:
        """Glow around area, the game's screen. Already up there: nothing changes."""
        if self.showing() and self.geometry() == area:
            return
        self._leaving = False
        self._fade.stop()
        self._breath.stop()
        self.setGeometry(area)
        self.setWindowOpacity(0.0)
        self.show()
        _pin_topmost(self)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()

    def leave(self) -> None:
        """Fade out and hide."""
        if not self.isVisible() or self._leaving:
            return
        self._leaving = True
        self._breath.stop()
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        self._fade.start()

    def stop(self) -> None:
        """Hide at once."""
        self._leaving = False
        self._breath.stop()
        self._fade.stop()
        self.hide()

    def _after_fade(self) -> None:
        if self._leaving:
            self._leaving = False
            self.hide()
            return
        self._breath.start()

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        paint_glow(painter, self.width(), self.height())
        painter.end()


def paint_glow(painter: QPainter, width: float, height: float) -> None:
    """The red light at the edges of a width by height area, fading inward."""
    depth = max(24.0, min(width, height) * _DEPTH)
    steps = max(12, round(depth / 2))
    painter.setBrush(Qt.NoBrush)
    for step in range(steps):
        inset = depth * step / steps
        fade = (1 - step / steps) ** 2.2
        painter.setPen(QPen(QColor(*_RED, round(_EDGE_ALPHA * fade)), depth / steps + 0.6))
        painter.drawRect(QRectF(inset, inset, width - 2 * inset, height - 2 * inset))
