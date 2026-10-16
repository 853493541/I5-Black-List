"""The scene that greets 嘉宾 players in a lobby, over the game.

Which scene plays is the lobby's (guests.lobby_choice): one of love_scenes.SCENES, ticked by its 组合
or its 嘉宾, one of several at random but never the one just played twice in a row, any for none ticked;
none for 不放. The 场景 hotkey plays the one picked on 场景管理, with no lobby, 不放 or not. It plays
once, about five seconds, then goes. The bottom of the scene parts around the accept button and its
marks, and clicks pass through the whole window to the game.
"""

from __future__ import annotations

import random
import threading

from PySide6.QtCore import QElapsedTimer, QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication, QWidget

from blacklist_detect import love_scenes
from blacklist_detect.love_scenes import Stage
from blacklist_detect.ui_overlay import _pin_topmost

# How long play waits for a scene's pictures made already (found made, or nearly): this soon, it starts at once.
READY_S = 0.02


class LoveBorder(QWidget):
    """A click-through window over the game's screen that plays one scene once. started: its clock started, its
    first frame shows now (its music hangs on it); a scene stopped or played again before that never sends it.
    dropped: stopped while its pictures were being made, before it started: it never showed."""

    started = Signal()
    dropped = Signal()

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
        # 嘉宾场景's choice: a scene's key, keys to pick one of, "random" (any) or "off".
        self.choice = "random"
        self.scene = "classic"
        self._last = ""
        # (choice, scene): the scene pick() settled for this lobby's play, and the choice it was for.
        self._picked: tuple[str, str] | None = None
        self._rng = rng or random.Random()
        self._gap = QRectF()
        self._badge: QPointF | None = None
        # The players' names in this window, where the check read them.
        self._seats: tuple[QRectF, ...] = ()
        self._made: dict[tuple, object] = {}
        self._buffers: dict[tuple, QImage] = {}
        self._clock = QElapsedTimer()
        # A scene's pictures being made before it starts (its paint's warm), off the screen's thread.
        self._warming: threading.Thread | None = None
        # A scene's pictures made ahead (warm_ahead), before a lobby asks for it.
        self._ahead: threading.Thread | None = None
        self._tick = QTimer(self)
        self._tick.setInterval(33)
        self._tick.timeout.connect(self._step)

    def play(self, area: QRect, keep_clear: QRect, badge: QPoint | None = None, seats: tuple[QRectF, ...] = ()) -> bool:
        """Cover area (the game's screen) and play, leaving keep_clear (the button and its marks) bare.

        badge is the 嘉宾 heart and seats the players' names, on the screen. Returns False when
        the choice plays none (不放).
        """
        scene = self.pick()
        if not scene:
            return False
        self.scene = self._last = scene
        self.setGeometry(area)
        clear = QRectF(keep_clear.translated(-area.topLeft()))
        self._gap = QRectF(clear.left() - 28, clear.top() - 30, clear.width() + 56, area.height() - clear.top() + 30)
        origin = QPointF(area.topLeft())
        self._badge = QPointF(badge) - origin if badge is not None else None
        self._seats = tuple(seat.translated(-origin) for seat in seats)
        # The same scene again (the 场景 hotkey pressed again) keeps the last two made for it, on the
        # screen and in 直播画面: over the same place it starts at once. 演说家遇袭's and 竖琴清风's pictures take a while to make.
        paint, _limit = self._made_for(Stage(area.width(), area.height(), self._gap, self._badge, self._seats))
        self._made = dict([(key, made) for key, made in self._made.items() if key[0] == scene][-2:])
        self._clock.invalidate()
        self._tick.start()
        # A scene whose pictures take a while (演说家遇袭, 竖琴清风) has them made first, several at a time, and starts
        # once they are, so its entrance plays from its first frame; made for this place, the next play
        # starts at once.
        warm = getattr(paint, "warm", None)
        self._warming = None
        if warm is not None:
            screen = QApplication.screenAt(area.center()) or QApplication.primaryScreen()
            ratio = screen.devicePixelRatio() if screen is not None else 1.0
            self._warming = threading.Thread(target=warm, args=(ratio,), name="scene-warm", daemon=True)
            self._warming.start()
            # Made already (warm_ahead, or the last play here): it starts now, its music with it.
            self._warming.join(READY_S)
            if not self._warming.is_alive():
                self._begin()
        else:
            self._begin()
        return True

    def waiting(self) -> bool:
        """Its scene's pictures are being made: it starts (started) once they are."""
        return self._warming is not None and self._tick.isActive()

    def warm_ahead(self, scene: str, width: float, height: float, ratio: float) -> bool:
        """Make a scene's pictures for a game screen this size ahead, off the screen's thread, so a lobby that
        plays it there starts at once: only a scene whose pictures take a while (warm in love_scenes), one at a
        time. Whether it started making them."""
        module = love_scenes.load(scene)
        warm = getattr(module, "warm", None)
        if warm is None or width < 1 or height < 1 or (self._ahead is not None and self._ahead.is_alive()):
            return False
        self._ahead = threading.Thread(target=warm, args=(width, height, round(ratio, 2)), name="scene-ahead", daemon=True)
        self._ahead.start()
        return True

    def _begin(self) -> None:
        self._warming = None
        self._clock.start()
        self.show()
        _pin_topmost(self)
        self.update()
        self.started.emit()

    def pick(self) -> str:
        """The scene this lobby's play() plays ("" for 无), settled now, 随机 too, so the 嘉宾 marks can
        be dressed for it before it starts; once it played, still that one, so checking the lobby again
        plays its music, not another's."""
        if self._picked is None or self._picked[0] != self.choice:
            self._picked = (self.choice, love_scenes.choose(self.choice, self._last, self._rng))
        return self._picked[1]

    def draw_again(self) -> None:
        """A new lobby: the next pick() draws its own scene, one of several or any, not the last lobby's."""
        self._picked = None

    def heard(self, scene: str) -> None:
        """scene's sound greeted a lobby, its scene shown or not (基础模式): the next one is another."""
        self._last = scene

    def playing(self) -> bool:
        return self._tick.isActive()

    def stop(self) -> None:
        never_shown = self.waiting()
        self._tick.stop()
        self._warming = None
        self.hide()
        if never_shown:
            self.dropped.emit()

    def elapsed(self) -> float:
        return self._clock.elapsed() / 1000 if self._clock.isValid() else 0.0

    def duration(self) -> float:
        return float(love_scenes.load(self.scene).DURATION)

    def _step(self) -> None:
        if self._warming is not None:
            if not self._warming.is_alive():
                self._begin()
            return
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
        """The scene at t seconds into its play, on a width by height area (this window, or 直播模式's);
        nothing while its pictures are being made."""
        if self._warming is not None:
            return
        stage = Stage(width, height, gap if gap is not None else self._gap, self._badge, self._seats)
        paint, limit = self._made_for(stage)
        ratio = painter.device().devicePixelRatioF() if painter.device() is not None else 1.0
        if limit is None or ratio <= limit + 0.01:
            paint(painter, t)
            return
        # A heavy scene on a sharp screen: drawn at fewer pixels, then laid on; a part that must
        # stay crisp is drawn on top at the screen's own.
        crisp = getattr(paint, "sharp", None)
        buffer = self._buffer(width, height, limit)
        inner = QPainter(buffer)
        inner.setRenderHint(QPainter.Antialiasing)
        if crisp is None:
            paint(inner, t)
        else:
            paint(inner, t, sharp=False)
        inner.end()
        painter.save()
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawImage(QRectF(0, 0, width, height), buffer)
        painter.restore()
        if crisp is not None:
            crisp(painter, t)

    def _made_for(self, stage: Stage):  # noqa: ANN202
        gap = stage.gap
        badge = (stage.badge.x(), stage.badge.y()) if stage.badge is not None else None
        seats = tuple((seat.x(), seat.y(), seat.width(), seat.height()) for seat in stage.seats)
        key = (self.scene, round(stage.width), round(stage.height), gap.x(), gap.y(), gap.width(), gap.height(), badge, seats)
        made = self._made.pop(key, None)
        if made is None:
            module = love_scenes.load(self.scene)
            made = (module.make(stage), getattr(module, "MAX_RATIO", None))
        # The last one used last: play() keeps the last two.
        self._made[key] = made
        return made

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
