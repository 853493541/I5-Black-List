"""天使 trial 3: a stand-in for a 心动 theme being tried out, to be replaced whole.

A soft glow in the top left corner, and the 心动 marks drawn plainly in the theme's colors through
love_scenes' hooks: a rim round the button, a dot for the badge, a plain card edged in one line and a
dot before each name, the rim and the badge pulsing (MARKS_ANIMATED).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient

from blacklist_detect.love_scenes.draw import col, ease_in, win

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
LOOK = {
    "glow": (255, 226, 150),
    "rim": "#f3d58a",
    "band": ("#fff3c4", "#f6d68a"),
    "card": ("#fffdf6", "#fbefd2"),
    "edge": "#e2c27a",
    "ink": "#7a5a1a",
    "flowers": (("#ffffff", "#fff1cc", "#e9c46a"), ("#fffaf0", "#f3e6ff", "#cdb8f0")),
    "disc": ("#fffdf6", "#f6e3b0"),
    "heart": ("#ffe7a3", "#d9a441"),
    "deep": "#c9962a",
    "deep_glow": (245, 205, 110),
}
MARKS_ANIMATED = True
# No ornament on the card.
CARD_TOP = 0


def make(stage: Stage):  # noqa: ANN201
    reach = 420 * stage.unit()

    def paint(p: QPainter, t: float) -> None:
        a = win(t, 0.0, 0.6) * (1 - ease_in(win(t, DURATION - 0.8, DURATION)))
        if a <= 0:
            return
        glow = QRadialGradient(QPointF(0, 0), reach)
        glow.setColorAt(0, col(LOOK["rim"], 0.55 * a))
        glow.setColorAt(1, col(LOOK["rim"], 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QPointF(0, 0), reach, reach)

    return paint


def _pulse(t: float) -> float:
    return 0.7 + 0.3 * math.cos(t * 3.0)


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    radius = cover.height() * 0.14
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(col(LOOK["rim"], _pulse(t)), 3))
    p.drawRoundedRect(cover.adjusted(1.5, 1.5, -1.5, -1.5), radius, radius)


def badge(p: QPainter, box: QRectF, t: float) -> None:
    r = box.width() * 0.3
    p.setPen(QPen(col(LOOK["rim"]), 2))
    p.setBrush(col(LOOK["deep"], _pulse(t)))
    p.drawEllipse(box.center(), r, r)


def card(p: QPainter, rect: QRectF, t: float) -> None:
    body = rect.adjusted(0.5, CARD_TOP + 0.5, -0.5, -0.5)
    fill = QLinearGradient(body.topLeft(), body.bottomLeft())
    fill.setColorAt(0, col(LOOK["card"][0]))
    fill.setColorAt(1, col(LOOK["card"][1]))
    p.setPen(QPen(col(LOOK["edge"]), 1))
    p.setBrush(fill)
    p.drawRoundedRect(body, 6, 6)


def lead(size: float, index: int) -> QPixmap:
    ratio = 2.0
    image = QPixmap(round(size * ratio), round(size * ratio))
    image.setDevicePixelRatio(ratio)
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(col(LOOK["flowers"][index % 2][2]))
    p.drawEllipse(QPointF(size / 2, size / 2), size * 0.22, size * 0.22)
    p.end()
    return image
