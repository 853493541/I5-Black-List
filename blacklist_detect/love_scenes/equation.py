"""PLACEHOLDER: a soft glow where the heart goes, until the scene itself is built."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter

from blacklist_detect.love_scenes.draw import ease_in, soft_dot, win

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0


def make(stage: Stage):  # noqa: ANN201
    u = stage.unit()
    at = QPointF(stage.width * 0.118, stage.height * 0.19)

    def paint(p: QPainter, t: float) -> None:
        soft_dot(p, at.x(), at.y(), 140 * u, "#ffffff", 0.6 * win(t, 0.0, 0.5) * (1 - ease_in(win(t, 4.2, 5.0))))

    return paint
