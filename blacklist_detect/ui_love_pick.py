"""设置 › 心动特效: which scene plays over the game, and which wedding music, for two or more 心动
players in a lobby. Each can be one of them, 随机 or 关闭; the choice is saved as it is made.

A preview plays the chosen scene over the fake-name sample lobby, with the app's own marks on it.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QPoint, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QButtonGroup, QLabel, QPushButton, QSizePolicy, QWidget

from blacklist_detect import love_scenes
from blacklist_detect.love_scenes import DESIGN, sample_stage
from blacklist_detect.ui_dialogs import _field, _primary
from blacklist_detect.ui_kit import Modal
from blacklist_detect.ui_music import TUNE_LIST, WeddingMusic
from blacklist_detect.ui_theme import DIALOG_PAD, _pointing
from blacklist_detect.ui_widgets import _FlowHost

SAMPLE_LOBBY = Path(__file__).resolve().parent / "assets" / "sample-lobby.jpg"
# A moment of the bare lobby between one play of the scene and the next.
PAUSE_S = 0.7


def _sample_marks() -> list[tuple[QPixmap, QPoint]]:
    """The app's 心动 marks by the sample lobby's button, as the game would show them: the rose ring,
    the heart and the card with the two 心动 players."""
    from blacklist_detect.ui_overlay import _COVER_OUTSET, _GLOW, ClearMark, LikeCard, LobbyPanel

    button = QRectF(749, 759, 256, 74).toRect()
    cover = button.adjusted(-_COVER_OUTSET, -_COVER_OUTSET, _COVER_OUTSET, _COVER_OUTSET)
    panel = LobbyPanel()
    panel.setFixedSize(cover.width() + 2 * _GLOW, cover.height() + 2 * _GLOW)
    panel.set_mode("liked", "没有黑名单")
    panel._shine.stop()
    panel._glint(0.3)
    marks = [(panel.grab(), cover.topLeft() - QPoint(_GLOW, _GLOW))]
    heart = ClearMark()
    heart.set_size(button.height() + _COVER_OUTSET * 2)
    heart.set_heart(True)
    mark = heart.grab()
    mark_h = round(mark.height() / mark.devicePixelRatio())
    marks.append((mark, QPoint(cover.right() + 17 - heart.margin, cover.center().y() - mark_h // 2 + 1)))
    card = LikeCard()
    card.set_people([("心动小鹿", ()), ("心动星星", ())], button.height())
    card.layout().activate()
    shot = card.grab()
    card_w = round(shot.width() / shot.devicePixelRatio())
    card_h = round(shot.height() / shot.devicePixelRatio())
    marks.append((shot, QPoint(cover.x() - 16 - card_w, cover.center().y() - card_h // 2 + 1)))
    for widget in (panel, heart, card):
        widget.deleteLater()
    return marks


class ScenePreview(QWidget):
    """The sample lobby with a scene playing over it, over and over. 随机 goes through them all."""

    WIDTH = 600

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        height = round(self.WIDTH * DESIGN[1] / DESIGN[0])
        self.setFixedSize(QSize(self.WIDTH, height))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAccessibleName("心动特效预览")
        self._lobby = QPixmap(str(SAMPLE_LOBBY))
        self._marks = _sample_marks()
        self._stage = sample_stage()
        self.choice = "random"
        self.scene = ""
        self._paint = None
        self._turn = -1
        self._clock = QElapsedTimer()
        self._tick = QTimer(self)
        self._tick.setInterval(33)
        self._tick.timeout.connect(self.update)

    def show_scene(self, choice: str) -> None:
        """Play this choice from its start: a scene, "random" (each in turn) or "off" (the lobby only)."""
        self.choice = choice
        self._turn = -1
        self._next()
        self._tick.start()

    def stop(self) -> None:
        self._tick.stop()

    def _next(self) -> None:
        if self.choice == "off":
            self.scene = ""
        elif self.choice == "random":
            self._turn = (self._turn + 1) % len(love_scenes.KEYS)
            self.scene = love_scenes.KEYS[self._turn]
        else:
            self.scene = self.choice
        self._paint = love_scenes.load(self.scene).make(self._stage) if self.scene else None
        self._clock.start()

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        box = QRectF(self.rect())
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
        for pixmap, at in self._marks:
            painter.drawPixmap(QPointF(at), pixmap)
        painter.end()


class LoveEffectsDialog(Modal):
    """心动特效: the scene and the music, each a row of choices, with the preview above them."""

    def __init__(self, store, music: WeddingMusic, parent: QWidget | None = None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.store = store
        self.music = music
        layout = self.frame("心动特效")
        note = QLabel("同一局遇到两名以上心动玩家时播放")
        note.setObjectName("sub")
        layout.addWidget(note)
        self.preview = ScenePreview()
        layout.addWidget(self.preview, 0, Qt.AlignHCenter)
        scenes = [("random", "随机"), *love_scenes.SCENES, ("off", "关闭")]
        tunes = [("random", "随机"), *((key, name) for key, name, _file in TUNE_LIST), ("off", "关闭")]
        self.scene_buttons = self._choices(layout, "特效", scenes, store.love_scene, self._pick_scene)
        self.music_buttons = self._choices(layout, "音乐", tunes, store.love_music, self._pick_music)
        self.play_button = QPushButton("一起预览")
        self.play_button.setAutoDefault(False)
        self.play_button.clicked.connect(self.play_both)
        self.footer(self.play_button, _primary("完成", self.accept))
        # As wide as the preview: the choices wrap under it, and it fits the smallest window.
        self.card.setFixedWidth(ScenePreview.WIDTH + 2 * DIALOG_PAD)
        _pointing(self)
        self.preview.show_scene(self._current(self.scene_buttons, store.love_scene, "random"))

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
            button.setCheckable(True)
            button.setAutoDefault(False)
            button.setChecked(key == (current if current in known else items[0][0]))
            button.clicked.connect(lambda _checked=False, key=key: pick(key))
            group.addButton(button)
            host.addWidget(button)
            buttons[key] = button
        _field(layout, label, host)
        return buttons

    @staticmethod
    def _current(buttons: dict[str, QPushButton], saved: str, default: str) -> str:
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
        """The scene from its start and the music with it, as a lobby would get them."""
        self.preview.show_scene(self._current(self.scene_buttons, self.store.love_scene, "random"))
        self.music.preview(self.store.love_music)

    def done(self, result: int) -> None:  # noqa: A003
        self.preview.stop()
        self.music.stop()
        super().done(result)
