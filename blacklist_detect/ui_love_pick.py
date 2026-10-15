"""选择特效: the scene a 嘉宾 or a 组合 is greeted with, picked from every one in love_scenes.SCENES.

The scenes are listed by name, each with a dot in its colour (SceneList); the one highlighted plays on
the right over the fake-name sample lobby, with the app's own marks on it (ScenePreview), and ▶ plays it
from its start with its music (unless 设置 › 音乐 is 无). 用这个 gives its key; closing changes nothing.
The 特效 page (ui_effects) is made of the same list and preview.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QPoint, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QAbstractButton, QButtonGroup, QHBoxLayout, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from blacklist_detect import love_scenes
from blacklist_detect.love_scenes import DESIGN, sample_stage
from blacklist_detect.ui_dialogs import _primary
from blacklist_detect.ui_icons import pixmap as line_pixmap
from blacklist_detect.ui_kit import Modal, _KeyboardRing
from blacklist_detect.ui_theme import THEME, _pointing, chinese_font, is_dark

SAMPLE_LOBBY = Path(__file__).resolve().parent / "assets" / "sample-lobby.jpg"


# A moment of the bare lobby between one play of the scene and the next.
PAUSE_S = 0.7


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
    """The sample lobby with a scene playing over it, over and over, in a rounded frame. With play, a ▶
    in its corner calls it (to play the scene from its start with its music)."""

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
        self.setAccessibleName("嘉宾特效预览")
        self._lobby = QPixmap(str(SAMPLE_LOBBY))
        # The marks in each scene's look, made as each first plays.
        self._looks: dict[str, SampleMarks] = {}
        self._marks = self._marks_for("classic")
        self._stage = sample_stage()
        self.scene = ""
        self._paint = None
        self._clock = QElapsedTimer()
        self._tick = QTimer(self)
        self._tick.setInterval(33)
        self._tick.timeout.connect(self.update)
        self._place_play()

    def set_width(self, width: int) -> None:
        """As wide as this, the lobby's shape kept, ▶ staying in its corner."""
        self.setFixedSize(QSize(width, round(width * DESIGN[1] / DESIGN[0])))
        self._place_play()

    def _place_play(self) -> None:
        if self.play_button is not None:
            self.play_button.move(self.width() - 36 - 10, self.height() - 36 - 10)

    def show_scene(self, scene: str) -> None:
        """Play this scene from its start; one this version no longer has plays what replaced it, or 经典."""
        scene = love_scenes.shown(scene)
        self.scene = scene if scene in love_scenes.KEYS else love_scenes.KEYS[0]
        self._paint = love_scenes.load(self.scene).make(self._stage)
        self._marks = self._marks_for(self.scene)
        self._clock.start()
        self._tick.start()

    def pause(self) -> None:
        """Stop playing until show_scene, while it is out of sight."""
        self._tick.stop()

    def stop(self) -> None:
        self._tick.stop()
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

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        box = QRectF(self.rect())
        frame = QPainterPath()
        frame.addRoundedRect(box, self.RADIUS, self.RADIUS)
        painter.setClipPath(frame)
        painter.drawPixmap(box, self._lobby, QRectF(self._lobby.rect()))
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
        for pixmap, at in self._marks.at(t):
            painter.drawPixmap(QPointF(at), pixmap)
        painter.resetTransform()
        painter.setClipping(False)
        painter.setPen(QPen(QColor(255, 255, 255, 40) if is_dark() else QColor(THEME["border"]), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(box.adjusted(0.5, 0.5, -0.5, -0.5), self.RADIUS, self.RADIUS)
        painter.end()


def tune_for(scene: str, music_choice: str) -> str:
    """The music a scene plays with: its own sound, unless 音乐 is 无."""
    return scene if music_choice != "off" else ""


class SceneChoice(_KeyboardRing, QAbstractButton):
    """One scene in 选择特效's list: a dot in its colour and its name. Picked, it sits in a ringed band
    with a ✓ at its end; under the mouse, the band shows faintly."""

    H = 34
    RADIUS = 8
    DOT = 6
    # Where the name starts, after the dot.
    TEXT_X = 16 + 2 * DOT + 12

    def __init__(self, key: str, name: str, parent: QWidget | None = None) -> None:
        from blacklist_detect.ui_overlay import love_look

        super().__init__(parent)
        self.key = key
        self.setText(name)
        self.setAccessibleName(name)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.dot = QColor(*love_look(key).glow)
        self._hover = False

    def sizeHint(self) -> QSize:
        font = chinese_font()
        font.setWeight(QFont.DemiBold)
        return QSize(self.TEXT_X + QFontMetrics(font).horizontalAdvance(self.text()) + 44, self.H)

    def enterEvent(self, event) -> None:  # noqa: ANN001
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
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
        p.setBrush(self.dot)
        p.drawEllipse(QPointF(16 + self.DOT, self.height() / 2), self.DOT, self.DOT)
        font = chinese_font()
        font.setWeight(QFont.DemiBold if self.isChecked() else QFont.Normal)
        p.setFont(font)
        p.setPen(QColor(THEME["text"]))
        words = QRectF(self.TEXT_X, 0, self.width() - self.TEXT_X - 36, self.height())
        p.drawText(words, Qt.AlignLeft | Qt.AlignVCenter, QFontMetrics(font).elidedText(self.text(), Qt.ElideRight, int(words.width())))
        if self.isChecked():
            tick = line_pixmap("check", 16, THEME["accent_line"], stroke=2.0)
            p.drawPixmap(QRectF(self.width() - 32, (self.height() - 16) / 2, 16, 16), tick, QRectF(tick.rect()))
        p.end()


class SceneList(QWidget):
    """Every scene in love_scenes.SCENES by name, one highlighted: 选择特效's list, and the 特效 page's.
    key is the one highlighted, 经典 for one this version does not have; picked(key) says a click
    highlighted one."""

    picked = Signal(str)
    W = 200

    def __init__(self, current: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(self.W)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(2)
        group = QButtonGroup(self)
        group.setExclusive(True)
        self.buttons: dict[str, SceneChoice] = {}
        for key, title in love_scenes.SCENES:
            button = SceneChoice(key, title)
            button.clicked.connect(lambda _checked=False, key=key: self._click(key))
            group.addButton(button)
            column.addWidget(button)
            self.buttons[key] = button
        column.addStretch(1)
        self.key = ""
        self.select(current)

    def select(self, key: str) -> None:
        """Highlight this scene: one replaced is its replacement, one this version does not have 经典."""
        key = love_scenes.shown(key)
        self.key = key if key in self.buttons else love_scenes.KEYS[0]
        self.buttons[self.key].setChecked(True)

    def _click(self, key: str) -> None:
        self.select(key)
        self.picked.emit(key)


class ScenePicker(Modal):
    """选择特效: the scenes by name on the left, the highlighted one playing on the right. key is the
    one highlighted; 用这个 accepts it."""

    def __init__(
        self,
        current: str = "",
        name: str = "",
        music=None,  # noqa: ANN001
        music_choice: str = "theme",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.music = music
        self.music_choice = music_choice
        layout = self.frame(f"选择特效 · {name}" if name else "选择特效")
        row = QHBoxLayout()
        row.setSpacing(20)
        self.scenes = SceneList(current)
        self.scenes.picked.connect(self.show_scene)
        self.buttons = self.scenes.buttons
        row.addWidget(self.scenes)
        self.preview = ScenePreview(self, play=self.play)
        self.play_button = self.preview.play_button
        row.addWidget(self.preview, 0, Qt.AlignVCenter)
        layout.addLayout(row)
        self.footer(_primary("用这个", self.accept))
        _pointing(self)
        self.key = self.scenes.key
        self.preview.show_scene(self.key)

    def show_scene(self, key: str) -> None:
        """Highlight this scene and play it, quietly: the music of the one before stops."""
        self.scenes.select(key)
        self.key = self.scenes.key
        self.preview.show_scene(self.key)
        if self.music is not None:
            self.music.stop()

    def play(self) -> None:
        """The highlighted scene from its start with its music, as a lobby would get them."""
        self.preview.show_scene(self.key)
        if self.music is not None:
            self.music.preview(tune_for(self.key, self.music_choice))

    def done(self, result: int) -> None:  # noqa: A003
        self.preview.stop()
        if self.music is not None:
            self.music.stop()
        super().done(result)
