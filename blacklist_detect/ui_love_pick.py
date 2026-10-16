"""The scenes listed to pick from, and one playing over the sample lobby.

Every scene in love_scenes.SCENES by name, each with a dot in its colour (SceneList); beside a 嘉宾's,
a 组合's or 我's fields (ui_guest_scenes.ScenePane) one per row, each with a box to tick. A click on a name highlights it, and it plays
over the fake-name sample lobby, with the app's own marks on it (ScenePreview).
The 场景管理 page (ui_effects) is made of the same list, with no boxes, and preview, each scene in its list with a
round spot at its end, ✓ on the 场景 the hotkey plays, a click on another's (or Space) giving it the hotkey apart
from the one shown, and with ♪ each 场景 that plays one of the player's songs.
"""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QEvent, QPoint, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QAbstractButton, QButtonGroup, QGridLayout, QPushButton, QSizePolicy, QToolTip, QWidget

from blacklist_detect import love_scenes
from blacklist_detect.love_scenes import DESIGN, sample_stage
from blacklist_detect.ui_icons import pixmap as line_pixmap
from blacklist_detect.ui_kit import _KeyboardRing
from blacklist_detect.ui_theme import THEME, chinese_font, is_dark

# 随机's dot, where the 场景 are listed with theirs: a colour none of them has.
RANDOM_DOT = (160, 210, 60)

SAMPLE_LOBBY = Path(__file__).resolve().parent / "assets" / "sample-lobby.jpg"
# Each scene at its best moment over the fake-name sample lobby, with the 嘉宾 marks in its look,
# drawn by build/theme_posters.py.
POSTERS = Path(__file__).resolve().parent / "assets" / "posters"

_pictures: dict[str, QPixmap] = {}


def poster(key: str) -> QPixmap:
    """A scene's picture, at the size it was drawn; 经典's for one this version does not have."""
    key = love_scenes.shown(key)
    if key not in love_scenes.KEYS:
        key = love_scenes.KEYS[0]
    if key not in _pictures:
        _pictures[key] = QPixmap(str(POSTERS / f"{key}.jpg"))
    return _pictures[key]


# A moment of the bare lobby between one play of the scene and the next.
PAUSE_S = 0.7
# How long a scene whose pictures take a while (竖琴清风) is waited for, made already or nearly: this soon, it plays at
# once; else its still shows while they are made off the screen's thread.
READY_S = 0.02


def scene_dot(key: str) -> QColor:
    """A 场景's dot in the lists, its look's glow; "random" is 随机's."""
    from blacklist_detect.ui_overlay import love_look

    return QColor(*RANDOM_DOT) if key == "random" else QColor(*love_look(key).glow)


class SampleMarks:
    """The app's 嘉宾 marks by the sample lobby's button, as the game would show them with this scene:
    the ring, the badge and the card with the two 嘉宾 players, in the scene's look, on a lobby scale
    times DESIGN. Marks the scene draws moving (moving) are grabbed again for each moment, the others
    once; close lets their windows go."""

    def __init__(self, scene: str = "classic", scale: float = 1.0) -> None:
        from blacklist_detect.ui_overlay import _COVER_OUTSET, _GLOW, ClearMark, LikeCard, LobbyPanel, _theme, love_look

        look = love_look(scene)
        self.moving = bool(_theme(look, "MARKS_ANIMATED", False))
        button = QRectF(749 * scale, 759 * scale, 256 * scale, 74 * scale).toRect()
        cover = self.cover = button.adjusted(-_COVER_OUTSET, -_COVER_OUTSET, _COVER_OUTSET, _COVER_OUTSET)
        panel = LobbyPanel()
        panel.setFixedSize(cover.width() + 2 * _GLOW, cover.height() + 2 * _GLOW)
        panel.set_look(look)
        panel.set_mode("liked", "未发现黑名单")
        panel._shine.stop()
        panel._glint(0.3)
        heart = ClearMark()
        heart.set_size(button.height() + _COVER_OUTSET * 2)
        heart.set_heart(True)
        heart.set_look(look)
        card = LikeCard()
        card.set_look(look)
        card.set_people([("心动小鹿", ()), ("心动星星", ())], cover.height())
        card.layout().activate()
        self.widgets = (panel, heart, card)
        # Where each window's top left is on the lobby: the badge right of the cover, the card left of it.
        self.places = (
            cover.topLeft() - QPoint(_GLOW, _GLOW),
            QPoint(cover.right() + 17 - heart.margin, cover.center().y() - heart.height() // 2 + 1),
            QPoint(cover.x() - 16 - card.width(), cover.y() - card.top),
        )
        self._shots: list[tuple[QPixmap, QPoint]] = []

    def at(self, t: float) -> list[tuple[QPixmap, QPoint]]:
        """The marks t seconds after they showed, each with its place."""
        if self.widgets and (self.moving or not self._shots):
            for widget in self.widgets:
                widget.set_time(t if self.moving else 0.0)
            self._shots = [(widget.grab(), place) for widget, place in zip(self.widgets, self.places, strict=True)]
        return self._shots

    def close(self) -> None:
        """Let the windows go; the marks stay as last grabbed."""
        for widget in self.widgets:
            widget.deleteLater()
        self.widgets = ()


def _sample_marks(scene: str = "classic") -> list[tuple[QPixmap, QPoint]]:
    """The app's 嘉宾 marks by the sample lobby's button with this scene, as they first show."""
    marks = SampleMarks(scene)
    shots = marks.at(0.0)
    marks.close()
    return shots


def _triangle(side: int, color: str = "#ffffff") -> QIcon:
    """A solid ▶, white over the preview, for a play button (its own disc is the button)."""
    ratio = 2.0
    image = QPixmap(round(side * ratio), round(side * ratio))
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(ratio, ratio)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawPolygon(QPolygonF([QPointF(side * 0.22, side * 0.1), QPointF(side * 0.92, side * 0.5), QPointF(side * 0.22, side * 0.9)]))
    p.end()
    image.setDevicePixelRatio(ratio)
    return QIcon(image)


class ScenePreview(QWidget):
    """The sample lobby with a scene playing over it, over and over, in a rounded frame, or the scene still at
    its best moment (show_still, its poster), which takes no time to show: a dialog opens on that, and a scene
    is made to play only when the player asks (a scene takes up to a second to make). One asked for by a click
    shows the bare lobby for a frame and is made just after, so the click is seen at once; one whose pictures take
    a while (竖琴清风) shows its still while they are made off the screen's thread, so the dialog never stalls. With
    play, a ▶ in its corner calls it (to play the scene from its start with its music). started: a scene started
    from its start, its first frame showing now (▶ 播放's music hangs on it)."""

    started = Signal()
    WIDTH = 600
    RADIUS = 10

    def __init__(self, parent: QWidget | None = None, width: int = WIDTH, play=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.setFixedSize(QSize(width, round(width * DESIGN[1] / DESIGN[0])))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.play_button: QPushButton | None = None
        if play is not None:
            button = QPushButton(self)
            button.setObjectName("previewPlay")
            button.setToolTip("从头播放，带音乐")
            button.setAccessibleName("播放")
            button.setCursor(Qt.PointingHandCursor)
            button.setAutoDefault(False)
            button.setFocusPolicy(Qt.TabFocus)
            button.setIcon(_triangle(14))
            button.setIconSize(QSize(14, 14))
            button.setFixedSize(36, 36)
            button.setStyleSheet(
                "QPushButton#previewPlay { background: rgba(10, 13, 20, 160); border: 1px solid rgba(255, 255, 255, 90);"
                " border-radius: 18px; padding: 0 0 0 2px; }"
                " QPushButton#previewPlay:hover { background: rgba(10, 13, 20, 215); border-color: rgba(255, 255, 255, 170); }"
            )
            button.clicked.connect(play)
            self.play_button = button
        self.setAccessibleName("嘉宾场景预览")
        self._lobby = QPixmap(str(SAMPLE_LOBBY))
        # The marks in each scene's look, made as each first plays.
        self._looks: dict[str, SampleMarks] = {}
        self._marks: SampleMarks | None = None
        self._stage = sample_stage()
        self.scene = ""
        self._paint = None
        # Each scene made while it is open, played again at once; rest keeps the one shown.
        self._made: dict = {}
        # A scene asked for and not made yet: made after the frame that shows the click.
        self._waiting = False
        self._still: QPixmap | None = None
        # The pictures of the scene asked for being made, off the screen's thread: it starts once they are.
        self._warming: threading.Thread | None = None
        self._clock = QElapsedTimer()
        self._tick = QTimer(self)
        self._tick.setInterval(33)
        self._tick.timeout.connect(self._step)
        self._place_play()

    @property
    def is_still(self) -> bool:
        """Showing a scene's still, nothing playing."""
        return self._still is not None

    def set_width(self, width: int) -> None:
        """As wide as this, the lobby's shape kept, ▶ staying in its corner."""
        self.setFixedSize(QSize(width, round(width * DESIGN[1] / DESIGN[0])))
        self._place_play()

    def _place_play(self) -> None:
        if self.play_button is not None:
            self.play_button.move(self.width() - 36 - 10, self.height() - 36 - 10)

    def show_scene(self, scene: str, now: bool = False) -> None:
        """Play this scene from its start; one this version no longer has plays what replaced it, or 经典. One not
        made yet is made after the frame that shows it was asked for, or now (for ▶, its music starting with it)."""
        self.scene = self._known(scene)
        self._still = None
        self._warming = None
        self._paint = self._made.get(self.scene)
        self._waiting = self._paint is None
        if not self._waiting:
            self._ready()
        elif now:
            self._make()
        else:
            self._tick.stop()
            self.update()

    def show_still(self, scene: str) -> None:
        """This scene still, at its best moment; nothing plays until show_scene."""
        self.scene = self._known(scene)
        self._still = poster(self.scene)
        self._paint = None
        self._waiting = False
        self._warming = None
        self._tick.stop()
        self.update()

    @staticmethod
    def _known(scene: str) -> str:
        scene = love_scenes.shown(scene)
        return scene if scene in love_scenes.KEYS else love_scenes.KEYS[0]

    def _make(self) -> None:
        """The scene asked for, made (演说家遇袭 takes nearly a second) and played from its start."""
        if not self._waiting:
            return
        self._waiting = False
        if self.scene not in self._made:
            self._made[self.scene] = love_scenes.load(self.scene).make(self._stage)
        self._paint = self._made[self.scene]
        self._ready()

    def _ready(self) -> None:
        """The scene made: it starts now, or, its pictures taking a while, once they are made off the screen's
        thread, its still showing meanwhile."""
        warm = getattr(self._paint, "warm", None)
        if warm is not None:
            sharp = round(self.devicePixelRatioF() * self.width() / DESIGN[0], 2)
            thread = threading.Thread(target=warm, args=(sharp,), name="preview-warm", daemon=True)
            thread.start()
            thread.join(READY_S)
            if thread.is_alive():
                self._warming = thread
                self._tick.start()
                self.update()
                return
        self._start()

    def _step(self) -> None:
        if self._warming is not None and not self._warming.is_alive():
            self._warming = None
            self._start()
        self.update()

    def _start(self) -> None:
        self._marks = self._marks_for(self.scene)
        self._clock.start()
        self._tick.start()
        self.update()
        self.started.emit()

    def pause(self) -> None:
        """Stop playing until show_scene or resume, while it is out of sight."""
        self._tick.stop()

    def resume(self, from_start: bool = True) -> None:
        """The scene played before pause, from its start again, without making it again. from_start=False:
        where it would be had it played on, in step with its music still playing. A still stays still."""
        if self._paint is None:
            return
        if self._warming is not None:
            # Still being made: it starts from its start once it is.
            self._tick.start()
            return
        if from_start or not self._clock.isValid():
            self._clock.start()
        self._tick.start()

    def rest(self) -> None:
        """Out of sight for a while: nothing plays, and of the scenes made only the one shown is kept."""
        self._tick.stop()
        self._waiting = False
        self._warming = None
        self._made = {key: paint for key, paint in self._made.items() if key == self.scene}

    def stop(self) -> None:
        self._tick.stop()
        self._waiting = False
        self._warming = None
        self._made.clear()
        for marks in self._looks.values():
            marks.close()

    def _marks_for(self, scene: str) -> SampleMarks:
        if scene not in self._looks:
            marks = SampleMarks(scene)
            marks.at(0.0)
            if not marks.moving:
                marks.close()
            self._looks[scene] = marks
        return self._looks[scene]

    def _paint_scene(self, painter: QPainter, box: QRectF) -> None:
        painter.drawPixmap(box, self._lobby, QRectF(self._lobby.rect()))
        if self._waiting:
            # This frame shows the click; the scene is made just after it.
            QTimer.singleShot(0, self._make)
            return
        painter.scale(self.width() / DESIGN[0], self.height() / DESIGN[1])
        t = self._clock.elapsed() / 1000 if self._clock.isValid() else 0.0
        if self._paint is not None:
            duration = love_scenes.load(self.scene).DURATION
            if t > duration + PAUSE_S:
                self._clock.start()
                t = 0.0
            if t <= duration:
                self._paint(painter, t)
        # Marks the scene draws moving move with it, from its start.
        for pixmap, at in self._marks.at(t) if self._marks is not None else ():
            painter.drawPixmap(QPointF(at), pixmap)

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        box = QRectF(self.rect())
        frame = QPainterPath()
        frame.addRoundedRect(box, self.RADIUS, self.RADIUS)
        painter.setClipPath(frame)
        if self._still is not None or self._warming is not None:
            # Its still, or while its pictures are being made, the scene's.
            still = self._still or poster(self.scene)
            painter.drawPixmap(box, still, QRectF(still.rect()))
        else:
            self._paint_scene(painter, box)
        painter.resetTransform()
        painter.setClipping(False)
        painter.setPen(QPen(QColor(255, 255, 255, 40) if is_dark() else QColor(THEME["border"]), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(box.adjusted(0.5, 0.5, -0.5, -0.5), self.RADIUS, self.RADIUS)
        painter.end()


def _draw_note(p: QPainter, centre: QPointF, color: str) -> None:
    """A small ♪, 14 px tall, drawn rather than typed so every font shows it alike."""
    p.save()
    p.translate(centre - QPointF(7, 7))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.save()
    p.translate(5.2, 11)
    p.rotate(-20)
    p.drawEllipse(QPointF(0, 0), 3.0, 2.2)
    p.restore()
    p.drawRect(QRectF(7.3, 1.5, 1.4, 9.5))
    flag = QPainterPath(QPointF(8.7, 1.5))
    flag.cubicTo(9.5, 4.0, 12.5, 4.2, 11.8, 7.8)
    flag.cubicTo(11.4, 5.8, 10.0, 5.2, 8.7, 4.9)
    flag.closeSubpath()
    p.drawPath(flag)
    p.restore()


def _faded_gray(share: float) -> QColor:
    """A true gray, no tint of the theme's: as light as this share of the theme's gray over the surface."""
    gray, surface = QColor(THEME["gray"]), QColor(THEME["surface"])
    level = share * gray.lightnessF() + (1 - share) * surface.lightnessF()
    return QColor.fromRgbF(level, level, level)


def paint_box(p: QPainter, box: QRectF, on: bool, enabled: bool = True) -> None:
    """A 场景 box: filled, with a ✓, when ticked; an empty square when not. Not enabled (播放场景 off), all
    of it gray, its tick kept."""
    p.save()
    if on:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(THEME["accent"]) if enabled else _faded_gray(0.55))
        p.drawRoundedRect(box, 4, 4)
        tick = line_pixmap("check", 12, THEME["on_accent"] if enabled else _faded_gray(0).name(), stroke=2.0)
        p.drawPixmap(box.adjusted(2, 2, -2, -2), tick, QRectF(tick.rect()))
    else:
        p.setPen(QPen(QColor(THEME["field_line"]) if enabled else _faded_gray(0.45), 1.2))
        p.setBrush(QColor(THEME["surface"]) if enabled else _faded_gray(0.08))
        p.drawRoundedRect(box.adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
    p.restore()


class SceneChoice(_KeyboardRing, QAbstractButton):
    """One scene in a list: a dot in its colour and its name. Highlighted, it sits in a ringed band; under
    the mouse, the band shows faintly. In ScenePane (chosen not None) a box at its end is ticked or not, by a
    click on it or Space, apart from the band, and chose says so; 播放场景 off (set_box_enabled(False)) the box
    and the dot are gray and the box does not tick, and the name still highlights. On the 场景管理 page (tick not None) a round
    spot there is apart from the band too: ✓ when the hotkey plays it (tick), empty when not, and a click on an
    empty one or Space says ticked, for the hotkey to play it; own puts a ♪ before it (it plays one of the
    player's songs). With neither, the ✓ goes with the band."""

    chose = Signal(bool)
    ticked = Signal()

    H = 34
    RADIUS = 8
    DOT = 6
    BOX = 16
    SPOT = 18
    # Where the name starts, after the dot.
    TEXT_X = 16 + 2 * DOT + 12
    # Kept clear at the row's end: for the ✓, and for ScenePane's box with a gap before it.
    END = 36
    BOX_END = 32 + 12

    def __init__(self, key: str, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key = key
        self.setText(name)
        self.setAccessibleName(name)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.dot = scene_dot(key)
        self._hover = False
        # None: the ✓ goes with the band.
        self.tick: bool | None = None
        self.own = False
        # ScenePane's box: None for none, else whether it is ticked.
        self.chosen: bool | None = None
        self.box_enabled = True
        self._box_press = False
        # The mouse on the 场景管理 page's spot.
        self._spot_hover = False

    def set_marks(self, tick: bool, own: bool) -> None:
        self.tick, self.own = tick, own
        said = ["快捷键播放这个"] * tick + ["自定义配乐"] * own
        self.setAccessibleDescription("，".join(said))
        self.setMouseTracking(True)
        self.update()

    def set_chosen(self, on: bool) -> None:
        """Give this scene ScenePane's box, ticked or not."""
        self.chosen = on
        self.setAccessibleDescription("已勾选" if on else "未勾选")
        self.update()

    def set_box_enabled(self, on: bool) -> None:
        """Whether the box can be ticked: not with 播放场景 off, where it and the dot are gray, its tick kept."""
        self.box_enabled = on
        self.update()

    def _ticks(self) -> bool:
        """Whether the row's end takes a click of its own: ScenePane's box, or the page's spot."""
        return (self.chosen is not None and self.box_enabled) or self.tick is not None

    def _toggle_chosen(self) -> None:
        if self.chosen is None:
            # The page's spot: one at a time, like a radio button, so a ✓ is not taken off.
            if not self.tick:
                self.ticked.emit()
            return
        self.set_chosen(not self.chosen)
        self.chose.emit(self.chosen)

    def _at_end(self, x: float) -> bool:
        return x >= self.width() - 40

    def _on_box(self, event) -> bool:  # noqa: ANN001
        """Whether the mouse is on the box or the spot: the end of the row, where it sits."""
        return self._ticks() and self._at_end(event.position().x())

    def mouseMoveEvent(self, event) -> None:  # noqa: ANN001
        over = self.tick is not None and self._at_end(event.position().x())
        if over != self._spot_hover:
            self._spot_hover = over
            self.update()
        super().mouseMoveEvent(event)

    def event(self, event) -> bool:  # noqa: ANN001
        # The spot says what it does when the mouse rests on it.
        if event.type() == QEvent.Type.ToolTip and self.tick is not None and self._at_end(event.pos().x()):
            QToolTip.showText(event.globalPos(), "按快捷键时播放这个" if self.tick else "点一下，按快捷键时播放这个", self)
            return True
        return super().event(event)

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        # A press on the box ticks it and leaves the highlight where it is.
        self._box_press = event.button() == Qt.LeftButton and self._on_box(event)
        if self._box_press:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
        if self._box_press:
            self._box_press = False
            if self._on_box(event) and self.rect().contains(event.position().toPoint()):
                self._toggle_chosen()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: ANN001
        if self._ticks() and event.key() == Qt.Key_Space:
            if not event.isAutoRepeat():
                self._toggle_chosen()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:  # noqa: ANN001
        if self._ticks() and event.key() == Qt.Key_Space:
            event.accept()
            return
        super().keyReleaseEvent(event)

    def sizeHint(self) -> QSize:
        font = chinese_font()
        font.setWeight(QFont.DemiBold)
        return QSize(self.TEXT_X + QFontMetrics(font).horizontalAdvance(self.text()) + 44 + 20 * self.own, self.H)

    def shown_name(self, bold: bool) -> str:
        """The name as drawn, cut with … only when the row is too narrow for it."""
        font = chinese_font()
        font.setWeight(QFont.DemiBold if bold else QFont.Normal)
        room = self.width() - self.TEXT_X - (self.END if self.chosen is None else self.BOX_END) - 20 * self.own
        return QFontMetrics(font).elidedText(self.text(), Qt.ElideRight, room)

    def enterEvent(self, event) -> None:  # noqa: ANN001
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        self._hover = self._spot_hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.4)
        box = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if self.isChecked():
            p.setPen(QPen(QColor(THEME["accent_line"]), 1.5))
            p.setBrush(QColor(THEME["selected"]))
            p.drawRoundedRect(box, self.RADIUS, self.RADIUS)
        elif self._hover:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(THEME["hover"]))
            p.drawRoundedRect(box, self.RADIUS, self.RADIUS)
        if self.show_ring():
            p.setPen(QPen(QColor(THEME["accent_line"]), 1.5, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(box, self.RADIUS, self.RADIUS)
        p.setPen(Qt.NoPen)
        # 播放场景 off: the dot gray with the boxes, the name as ever.
        p.setBrush(self.dot if self.box_enabled or self.chosen is None else _faded_gray(0.5))
        p.drawEllipse(QPointF(16 + self.DOT, self.height() / 2), self.DOT, self.DOT)
        font = chinese_font()
        font.setWeight(QFont.DemiBold if self.isChecked() else QFont.Normal)
        p.setFont(font)
        p.setPen(QColor(THEME["text"]))
        words = QRectF(self.TEXT_X, 0, self.width() - self.TEXT_X, self.height())
        p.drawText(words, Qt.AlignLeft | Qt.AlignVCenter, self.shown_name(self.isChecked()))
        if self.own:
            _draw_note(p, QPointF(self.width() - 45, self.height() / 2), THEME["muted"])
        if self.chosen is not None:
            self._paint_box(p)
            p.end()
            return
        if self.tick is not None:
            self._paint_spot(p)
        elif self.isChecked():
            tick = line_pixmap("check", 16, THEME["accent_line"], stroke=2.0)
            p.drawPixmap(QRectF(self.width() - 32, (self.height() - 16) / 2, 16, 16), tick, QRectF(tick.rect()))
        p.end()

    def _paint_spot(self, p: QPainter) -> None:
        """The page's spot at the row's end: filled, with a ✓, for the hotkey's; an empty ring for the others,
        stronger under the mouse."""
        spot = QRectF(self.width() - 33, (self.height() - self.SPOT) / 2, self.SPOT, self.SPOT)
        p.save()
        if self.tick:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(THEME["accent"]))
            p.drawEllipse(spot)
            tick = line_pixmap("check", 12, THEME["on_accent"], stroke=2.0)
            p.drawPixmap(spot.adjusted(3, 3, -3, -3), tick, QRectF(tick.rect()))
        else:
            p.setPen(QPen(QColor(THEME["accent_line" if self._spot_hover else "field_line"]), 1.4))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(spot.adjusted(1, 1, -1, -1))
        p.restore()

    def _paint_box(self, p: QPainter) -> None:
        """ScenePane's box at the row's end; with 播放场景 off gray, its tick kept."""
        paint_box(p, QRectF(self.width() - 32, (self.height() - self.BOX) / 2, self.BOX, self.BOX), bool(self.chosen), self.box_enabled)


class SceneList(QWidget):
    """Every scene in love_scenes.SCENES by name, one highlighted: ScenePane's list, and the 场景管理 page's
    list. key is the one highlighted, 经典 for one this version does not have; picked(key) says a click
    highlighted one. In ScenePane (chosen: the keys ticked) each has a box to tick, and chose says one was
    ticked or unticked. On the page (marks) each has a spot, and ticked(key) says a click on one's (or Space)
    asked for the hotkey to play it; set_marks puts the ✓ on the hotkey's and a ♪ on each that plays one of the
    player's songs. In columns, row by row, the whole width shared alike among them."""

    picked = Signal(str)
    chose = Signal()
    ticked = Signal(str)
    W = 200
    GAP = 2

    def __init__(
        self,
        current: str = "",
        parent: QWidget | None = None,
        marks: bool = False,
        chosen: tuple[str, ...] | None = None,
        columns: int = 1,
        width: int = W,
    ) -> None:
        super().__init__(parent)
        self.setFixedWidth(width)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(self.GAP)
        cell = (width - 4 * (columns - 1)) // columns
        group = QButtonGroup(self)
        group.setExclusive(True)
        self.buttons: dict[str, SceneChoice] = {}
        for place, (key, title) in enumerate(love_scenes.SCENES):
            button = SceneChoice(key, title)
            if columns > 1:
                # Alike, wide enough for every name whole; the name again when the mouse rests on it.
                button.setFixedWidth(cell)
                button.setToolTip(title)
            button.clicked.connect(lambda _checked=False, key=key: self._click(key))
            button.chose.connect(lambda _on: self.chose.emit())
            button.ticked.connect(lambda key=key: self.ticked.emit(key))
            group.addButton(button)
            grid.addWidget(button, *divmod(place, columns))
            self.buttons[key] = button
        grid.setRowStretch(grid.rowCount(), 1)
        self.key = ""
        self.select(current)
        if marks:
            self.set_marks(self.key, ())
        if chosen is not None:
            self.set_chosen(chosen)

    def set_marks(self, ticked: str, own) -> None:  # noqa: ANN001
        """The ✓ on ticked alone (one replaced is its replacement), the ♪ on each key in own."""
        ticked = love_scenes.shown(ticked)
        for key, button in self.buttons.items():
            button.set_marks(key == ticked, key in own)

    def set_chosen(self, keys) -> None:  # noqa: ANN001
        """Tick these scenes (one replaced is its replacement) and no others."""
        keys = {love_scenes.shown(key) for key in keys}
        for key, button in self.buttons.items():
            button.set_chosen(key in keys)

    def set_boxes_enabled(self, on: bool) -> None:
        """Whether the boxes can be ticked (not with 播放场景 off); the names highlight either way."""
        for button in self.buttons.values():
            button.set_box_enabled(on)

    def chosen(self) -> tuple[str, ...]:
        """The scenes ticked, in the list's order."""
        return tuple(key for key, button in self.buttons.items() if button.chosen)

    def select(self, key: str) -> None:
        """Highlight this scene: one replaced is its replacement, one this version does not have 经典."""
        key = love_scenes.shown(key)
        self.key = key if key in self.buttons else love_scenes.KEYS[0]
        self.buttons[self.key].setChecked(True)

    def _click(self, key: str) -> None:
        self.select(key)
        self.picked.emit(key)
