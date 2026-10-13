"""The scene that greets two or more 心动 players in a lobby, over the game.

Which scene plays is the player's choice in 设置 › 心动特效: one of love_scenes.SCENES, 随机 (any
but the one just played), or 关闭. It plays once, about five seconds, then goes. The bottom of the
scene parts around the accept button and its marks, and clicks pass through the whole window to
the game.
"""

from __future__ import annotations

import random

from PySide6.QtCore import QElapsedTimer, QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QWidget

from blacklist_detect import love_scenes
from blacklist_detect.love_scenes import Stage
from blacklist_detect.ui_overlay import _pin_topmost


class LoveBorder(QWidget):
    """A click-through window over the game's screen that plays one scene once."""

    def __init__(self, rng: random.Random | None = None) -> None:
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
        # 设置's choice: a scene's key, "random" or "off".
        self.choice = "random"
        self.scene = "classic"
        self._last = ""
        self._rng = rng or random.Random()
        self._gap = QRectF()
        self._badge: QPointF | None = None
        self._cards: tuple[QPointF, ...] = ()
        self._made: dict[tuple, object] = {}
        self._buffers: dict[tuple, QImage] = {}
        self._clock = QElapsedTimer()
        self._tick = QTimer(self)
        self._tick.setInterval(33)
        self._tick.timeout.connect(self._step)

    def play(self, area: QRect, keep_clear: QRect, badge: QPoint | None = None, cards: tuple[QPoint, ...] = ()) -> bool:
        """Cover area (the game's screen) and play, leaving keep_clear (the button and its marks) bare.

        badge is the 心动 heart and cards the middle of each 心动 player's card, on the screen.
        Returns False when 设置 says 关闭.
        """
        scene = love_scenes.choose(self.choice, self._last, len(cards), self._rng)
        if not scene:
            return False
        self.scene = self._last = scene
        self.setGeometry(area)
        clear = QRectF(keep_clear.translated(-area.topLeft()))
        self._gap = QRectF(clear.left() - 28, clear.top() - 30, clear.width() + 56, area.height() - clear.top() + 30)
        origin = QPointF(area.topLeft())
        self._badge = QPointF(badge) - origin if badge is not None else None
        self._cards = tuple(QPointF(card) - origin for card in cards)
        self._made = {}
        self._clock.start()
        self._tick.start()
        self.show()
        _pin_topmost(self)
        self.update()
        return True

    def playing(self) -> bool:
        return self._tick.isActive()

    def stop(self) -> None:
        self._tick.stop()
        self.hide()

    def elapsed(self) -> float:
        return self._clock.elapsed() / 1000 if self._clock.isValid() else 0.0

    def duration(self) -> float:
        return float(love_scenes.load(self.scene).DURATION)

    def _step(self) -> None:
        if self.elapsed() >= self.duration():
            self.stop()
            return
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.paint_at(painter, self.elapsed(), self.width(), self.height())
        painter.end()

    def paint_at(self, painter: QPainter, t: float, width: float, height: float, gap: QRectF | None = None) -> None:
        """The scene at t seconds into its play, on a width by height area (this window, or 直播模式's)."""
        stage = Stage(width, height, gap if gap is not None else self._gap, self._badge, self._cards)
        paint, limit = self._made_for(stage)
        ratio = painter.device().devicePixelRatioF() if painter.device() is not None else 1.0
        if limit is None or ratio <= limit + 0.01:
            paint(painter, t)
            return
        # A heavy scene on a sharp screen: drawn at fewer pixels, then laid on.
        buffer = self._buffer(width, height, limit)
        inner = QPainter(buffer)
        inner.setRenderHint(QPainter.Antialiasing)
        paint(inner, t)
        inner.end()
        painter.save()
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawImage(QRectF(0, 0, width, height), buffer)
        painter.restore()

    def _made_for(self, stage: Stage):  # noqa: ANN202
        gap = stage.gap
        badge = (stage.badge.x(), stage.badge.y()) if stage.badge is not None else None
        key = (self.scene, round(stage.width), round(stage.height), gap.x(), gap.y(), gap.width(), gap.height(), badge,
               tuple((card.x(), card.y()) for card in stage.cards))
        if key not in self._made:
            module = love_scenes.load(self.scene)
            self._made[key] = (module.make(stage), getattr(module, "MAX_RATIO", None))
        return self._made[key]

    def _buffer(self, width: float, height: float, ratio: float) -> QImage:
        key = (round(width), round(height), ratio)
        image = self._buffers.get(key)
        if image is None:
            self._buffers = {}
            image = QImage(max(1, round(width * ratio)), max(1, round(height * ratio)), QImage.Format_ARGB32_Premultiplied)
            image.setDevicePixelRatio(ratio)
            self._buffers[key] = image
        image.fill(Qt.transparent)
        return image
