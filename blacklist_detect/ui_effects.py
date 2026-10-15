"""特效: the 特效 the 特效 hotkey plays, and that hotkey.

Every scene in love_scenes.SCENES is listed by name with its dot, as in 选择特效 (ui_love_pick.SceneList);
the one picked plays beside them over the fake-name sample lobby, as big as the page allows, and ▶ plays
it from its start with its music. Under it, the hotkey, set the way 检查's is (the window's hotkey box),
and 播放, which does what the hotkey does: the 特效 at once over the game, with no check
(MainWindow.play_quick_scene). The preview plays only while it can be seen, its window not minimized,
and the app is in front: behind the game it would paint 30 times a second for nothing.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from blacklist_detect.love_scenes import DESIGN
from blacklist_detect.ui_love_pick import SceneList, ScenePreview, tune_for
from blacklist_detect.ui_theme import GAP, _page


class _Fitted(QWidget):
    """The preview as big as it fits, the lobby's shape kept, at the top left, and what goes under it
    (below) right under it. The preview keeps the most room below has needed, so it does not jump
    as a note under the hotkey comes and goes."""

    MIN_W = 320

    def __init__(self, preview: ScenePreview, below: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.preview = preview
        self.below = below
        preview.setParent(self)
        below.setParent(self)
        # Its box and 播放 grow once they are styled, after the first place: placed again then.
        below.installEventFilter(self)
        self._under = 0
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(QSize(self.MIN_W, self._tall(self.MIN_W)))

    def _tall(self, width: int) -> int:
        return round(width * DESIGN[1] / DESIGN[0]) + GAP + self.below.sizeHint().height()

    def sizeHint(self) -> QSize:
        return QSize(ScenePreview.WIDTH, self._tall(ScenePreview.WIDTH))

    def place(self) -> None:
        under = self.below.sizeHint().height()
        self._under = max(self._under, under)
        room = max(1, self.height() - self._under - GAP)
        self.preview.set_width(max(1, min(self.width(), int(room * DESIGN[0] / DESIGN[1]))))
        self.preview.move(0, 0)
        self.below.setGeometry(0, self.preview.height() + GAP, self.width(), under)

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self.place()

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        self.place()

    def eventFilter(self, watched, event) -> bool:  # noqa: ANN001
        if watched is self.below and event.type() == QEvent.Type.LayoutRequest:
            self.place()
        return super().eventFilter(watched, event)


class EffectsPage(QWidget):
    """The 特效 page. Picking a scene saves it as store.quick_scene and says so with picked(key);
    hotkey_box is the window's box for the 特效 hotkey, and play what 播放 does. sounding: the music
    playing is the one ▶ started, which stops as the page goes out of sight."""

    picked = Signal(str)

    def __init__(self, store, music, hotkey_box: QLineEdit, play, parent: QWidget | None = None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.store = store
        self.music = music
        self.sounding = False
        outer = QVBoxLayout(self)
        _page(outer)
        body = QHBoxLayout()
        body.setSpacing(20)
        outer.addLayout(body, 1)
        self.scenes = SceneList(store.quick_scene)
        self.scenes.picked.connect(self._pick)
        body.addWidget(self.scenes, 0, Qt.AlignTop)
        self.preview = ScenePreview(play=self.play_preview)
        # The hotkey and 播放, in one row right under the preview.
        below = QWidget()
        under = QVBoxLayout(below)
        under.setContentsMargins(0, 0, 0, 0)
        under.setSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(10)
        label = QLabel("快捷键")
        label.setObjectName("rowLabel")
        row.addWidget(label)
        row.addWidget(hotkey_box)
        self.play_button = QPushButton("播放")
        self.play_button.setObjectName("primary")
        self.play_button.setAutoDefault(False)
        self.play_button.setCursor(Qt.PointingHandCursor)
        self.play_button.clicked.connect(lambda: play())
        row.addWidget(self.play_button)
        row.addStretch(1)
        under.addLayout(row)
        # What is wrong with a key pressed for the hotkey, as 检查 says it, or why 播放 played nothing,
        # under them. Its room is kept while it is hidden.
        self.note = QLabel("")
        self.note.setObjectName("rowHint")
        self.note.setWordWrap(True)
        policy = self.note.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        self.note.setSizePolicy(policy)
        self.note.hide()
        under.addWidget(self.note)
        self.stage = _Fitted(self.preview, below)
        body.addWidget(self.stage, 1)
        QGuiApplication.instance().applicationStateChanged.connect(self._app_state)

    def select(self, key: str) -> None:
        """Show this scene as the one picked (after 清空数据), without saving."""
        self.scenes.select(key)
        if self.isVisible():
            self.preview.show_scene(self.scenes.key)

    def _pick(self, key: str) -> None:
        """A click on a scene: it is the hotkey's now, and plays quietly, the music ▶ started stopped.
        A play over the game keeps its music."""
        self.store.quick_scene = self.scenes.key
        self.store.save_settings()
        self.preview.show_scene(self.scenes.key)
        if self.sounding and self.music is not None:
            self.music.stop()
        self.sounding = False
        self.picked.emit(self.scenes.key)

    def play_preview(self) -> None:
        """▶: the scene from its start in the preview, with its music, which takes over from a play's
        over the game."""
        self.preview.show_scene(self.scenes.key)
        if self.music is not None:
            self.music.preview(tune_for(self.scenes.key, self.store.love_music))
            self.sounding = True

    def say(self, text: str) -> None:
        self.note.setText(text)
        self.note.setVisible(bool(text))
        self.stage.below.layout().activate()
        self.stage.place()

    def _seen(self) -> bool:
        """On screen: this page the one shown, in a window that is not minimized."""
        return self.isVisible() and not self.window().isMinimized()

    def _show(self) -> None:
        """The picked scene from its start; made again only when it changed (演说家遇袭 takes over a second).
        While ▶'s music plays on, it goes on where the music is instead."""
        if self.preview.scene == self.scenes.key:
            self.preview.resume(from_start=not self.sounding)
        else:
            self.preview.show_scene(self.scenes.key)

    def _app_state(self, state) -> None:  # noqa: ANN001
        """With the game in front, the preview rests; it plays again as the app comes back."""
        if state != Qt.ApplicationState.ApplicationActive:
            self.preview.pause()
        elif self._seen():
            self._show()

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        if self._seen():
            self._show()

    def hideEvent(self, event) -> None:  # noqa: ANN001
        self.preview.pause()
        if self.sounding and self.music is not None:
            self.music.stop()
        self.sounding = False
        super().hideEvent(event)
