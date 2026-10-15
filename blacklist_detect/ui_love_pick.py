"""嘉宾 › 嘉宾特效: the scene that plays over the game when 嘉宾 are in a lobby, and the wedding music.
It plays whenever one is there: a 组合 all there gets its own scene, else the top 嘉宾 with one of
their own, else the one chosen here (guests.lobby_choice). The scene and the music can each be one of
them, 随机 or 无; every choice is saved as it is made. The default comes first (经典花边, 婚礼进行曲 ·
管风琴), then the others, then 随机, and 无 last, in red.

A preview plays the chosen scene over the fake-name sample lobby, with the app's own marks on it.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QPoint, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QAbstractButton, QButtonGroup, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from blacklist_detect import love_scenes
from blacklist_detect.love_scenes import DESIGN, sample_stage
from blacklist_detect.ui_dialogs import _primary
from blacklist_detect.ui_kit import Modal
from blacklist_detect.ui_music import TUNE_LIST, WeddingMusic
from blacklist_detect.ui_theme import SMALL_PT, THEME, _pointing, chinese_font, is_dark
from blacklist_detect.ui_theme_cards import CONTENT_W, PREVIEW_W, ThemeGallery, section, showcase
from blacklist_detect.ui_widgets import _FlowHost

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
            QPoint(cover.x() - 16 - card.width(), cover.center().y() - card.height() // 2 + 1),
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


def _triangle(side: int) -> QIcon:
    """A solid ▶, white, for the play button over the preview (its own disc is the button)."""
    ratio = 2.0
    image = QPixmap(round(side * ratio), round(side * ratio))
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(ratio, ratio)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#ffffff"))
    p.drawPolygon(QPolygonF([QPointF(side * 0.22, side * 0.1), QPointF(side * 0.92, side * 0.5), QPointF(side * 0.22, side * 0.9)]))
    p.end()
    image.setDevicePixelRatio(ratio)
    return QIcon(image)


class ScenePreview(QWidget):
    """The sample lobby with a scene playing over it, over and over, in a rounded frame with the scene's
    name in its corner. 随机 goes through them all. With play, a ▶ in the other corner calls it (to play
    the scene from its start with its music)."""

    # Beside the dialog's own fields, with the 特效 cards under both.
    WIDTH = PREVIEW_W
    RADIUS = 10

    def __init__(self, parent: QWidget | None = None, width: int = WIDTH, play=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.setFixedSize(QSize(width, round(width * DESIGN[1] / DESIGN[0])))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        # Said before the scene's name in the corner, as 默认 is.
        self.prefix = ""
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
            button.move(self.width() - 36 - 10, self.height() - 36 - 10)
            button.clicked.connect(play)
            self.play_button = button
        self.setAccessibleName("嘉宾特效预览")
        self._lobby = QPixmap(str(SAMPLE_LOBBY))
        # The marks in each scene's look, made as each first plays.
        self._looks: dict[str, SampleMarks] = {}
        self._marks = self._marks_for("classic")
        self._stage = sample_stage()
        self.choice = "random"
        self.scene = ""
        self._paint = None
        self._turn = -1
        self._clock = QElapsedTimer()
        self._tick = QTimer(self)
        self._tick.setInterval(33)
        self._tick.timeout.connect(self.update)

    def show_scene(self, choice: str, prefix: str = "") -> None:
        """Play this choice from its start: a scene, "random" (each in turn) or "off" (the lobby only)."""
        self.choice = choice
        self.prefix = prefix
        self._turn = -1
        self._next()
        self._tick.start()

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

    def _next(self) -> None:
        if self.choice == "off":
            self.scene = ""
        elif self.choice == "random":
            self._turn = (self._turn + 1) % len(love_scenes.KEYS)
            self.scene = love_scenes.KEYS[self._turn]
        else:
            self.scene = self.choice
        self._paint = love_scenes.load(self.scene).make(self._stage) if self.scene else None
        # With 无 the marks are as they are with no scene: 经典花边's.
        self._marks = self._marks_for(self.scene or "classic")
        self._clock.start()

    def caption(self) -> str:
        """What the corner says: the scene playing, 随机 before it while they take turns, 无特效 for none."""
        names = dict(love_scenes.SCENES)
        if self.choice == "off":
            words = "无特效"
        elif self.choice == "random":
            words = f"随机 · {names.get(self.scene, '')}"
        else:
            words = names.get(self.scene, "")
        return f"{self.prefix} · {words}" if self.prefix else words

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
                self._next()
                t = 0.0
            if t <= duration:
                self._paint(painter, t)
        # Marks the scene draws moving move with it, from its start.
        for pixmap, at in self._marks.at(t):
            painter.drawPixmap(QPointF(at), pixmap)
        painter.resetTransform()
        self._paint_caption(painter)
        painter.setClipping(False)
        painter.setPen(QPen(QColor(255, 255, 255, 40) if is_dark() else QColor(THEME["border"]), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(box.adjusted(0.5, 0.5, -0.5, -0.5), self.RADIUS, self.RADIUS)
        painter.end()

    def _paint_caption(self, painter: QPainter) -> None:
        words = self.caption()
        if not words:
            return
        font = chinese_font(SMALL_PT)
        font.setWeight(QFont.DemiBold)
        metrics = QFontMetrics(font)
        pill = QRectF(10, 10, metrics.horizontalAdvance(words) + 20, metrics.height() + 8)
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
        painter.setBrush(QColor(10, 13, 20, 170))
        painter.drawRoundedRect(pill, pill.height() / 2, pill.height() / 2)
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(pill, Qt.AlignCenter, words)


def tune_for(scene: str, music_choice: str) -> str:
    """The music a scene plays with: its own (遇袭's 指挥家) unless 音乐 is 无, else 音乐's choice."""
    own = getattr(love_scenes.load(scene), "MUSIC", "") if scene else ""
    return own if own and music_choice != "off" else music_choice


class LoveEffectsDialog(Modal):
    """嘉宾特效, laid out as the 嘉宾 dialogs: the preview on the left (▶ plays the scene with its
    music), 音乐 and when it all plays on its right, and the scenes as picture cards under both, 随机
    and 无 last."""

    def __init__(self, store, music: WeddingMusic, parent: QWidget | None = None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.store = store
        self.music = music
        layout = self.frame("嘉宾特效")
        layout.setSpacing(16)
        self.preview = ScenePreview(self, play=self.play_both)
        self.play_button = self.preview.play_button
        side = showcase(self, layout, self.preview)
        tunes = [*((key, name) for key, name, _file in TUNE_LIST), ("random", "随机"), ("off", "无")]
        self.music_buttons = self._choices(side, "音乐", tunes, store.love_music, self._pick_music)
        side.addStretch(1)
        when = QLabel("有嘉宾在大厅就放：组合都在时放组合的，嘉宾自己选了特效就放自己的，其余放这里选的。")
        when.setObjectName("sub")
        when.setWordWrap(True)
        side.addWidget(when)
        block = section(layout, "特效", "点一张卡片，左边就放它")
        scenes = [*love_scenes.SCENES, ("random", "随机"), ("off", "无")]
        self.gallery = ThemeGallery(scenes, love_scenes.shown(store.love_scene), CONTENT_W)
        self.gallery.picked.connect(self._pick_scene)
        block.addWidget(self.gallery)
        self.scene_buttons = self.gallery.buttons
        self.footer(_primary("完成", self.accept))
        _pointing(self)
        self.preview.show_scene(self._current(self.scene_buttons, love_scenes.shown(store.love_scene), "classic"))

    def _choices(self, layout, label: str, items, current: str, pick) -> dict[str, QPushButton]:  # noqa: ANN001
        host = _FlowHost(gap=8)
        group = QButtonGroup(self)
        group.setExclusive(True)
        buttons: dict[str, QPushButton] = {}
        known = {key for key, _name in items}
        for key, name in items:
            button = QPushButton(name)
            button.setObjectName("segment")
            button.setProperty("place", "only")
            # 无 in red: it turns the effect off.
            button.setProperty("off", key == "off")
            button.setCheckable(True)
            button.setAutoDefault(False)
            button.setChecked(key == (current if current in known else items[0][0]))
            button.clicked.connect(lambda _checked=False, key=key: pick(key))
            group.addButton(button)
            host.addWidget(button)
            buttons[key] = button
        self._above(layout, label, host)
        return buttons

    @staticmethod
    def _above(layout, label: str, host: QWidget, aside: QWidget | None = None) -> None:  # noqa: ANN001
        """The row's name over its choices, as the fields beside the preview have them; aside on its right."""
        column = QVBoxLayout()
        column.setSpacing(6)
        top = QHBoxLayout()
        name = QLabel(label)
        name.setObjectName("field")
        top.addWidget(name)
        top.addStretch(1)
        if aside is not None:
            top.addWidget(aside)
        column.addLayout(top)
        column.addWidget(host)
        layout.addLayout(column)

    @staticmethod
    def _current(buttons: dict[str, QAbstractButton], saved: str, default: str) -> str:
        return saved if saved in buttons else default

    def _pick_scene(self, key: str) -> None:
        self.store.love_scene = key
        self.store.save_settings()
        self.preview.show_scene(key)

    def _pick_music(self, key: str) -> None:
        self.store.love_music = key
        self.store.save_settings()
        self.music.preview(key)

    def play_both(self) -> None:
        """The scene from its start and the music with it, as a lobby would get them: a scene with its
        own tune (遇袭's 指挥家) plays that, unless 音乐 is 无."""
        self.preview.show_scene(self._current(self.scene_buttons, love_scenes.shown(self.store.love_scene), "classic"))
        self.music.preview(tune_for(self.preview.scene, self.store.love_music))

    def done(self, result: int) -> None:  # noqa: A003
        self.preview.stop()
        self.music.stop()
        super().done(result)
