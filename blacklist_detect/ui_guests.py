"""嘉宾 themes: the scenes a 嘉宾 or a 组合 has as the 嘉宾 list says them, and 组合, the 嘉宾 who, all in
one lobby, get scenes of their own (guests.lobby_choice).

The 嘉宾 list says a 嘉宾's or a 组合's scenes in a word or two (scenes_said); they are ticked in 嘉宾场景
(ui_guest_scenes). The 组合 head the 嘉宾 page's list (ui_likes), each a row tagged 组合 that opens
ComboDialog; 添加 › 添加组合 adds one, on 随机 to begin with.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QPushButton, QWidget

from blacklist_detect import love_scenes
from blacklist_detect.guests import ticked
from blacklist_detect.match import fold
from blacklist_detect.model import ANY_SCENE, Combo, Entry, Scenes
from blacklist_detect.ui_dialogs import _danger, _field, _primary, _say_error
from blacklist_detect.ui_icons import icon as line_icon
from blacklist_detect.ui_kit import Modal, _CardScroll, _height_for
from blacklist_detect.ui_theme import THEME, _pointing
from blacklist_detect.ui_widgets import _FlowHost

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


def scene_name(key: str) -> str:
    """A scene as the list says it: its name, the scene that replaced a dropped one, and 经典 for one
    this version does not have."""
    return dict(love_scenes.SCENES).get(love_scenes.shown(key), love_scenes.SCENES[0][1])


def scenes_said(scenes: Scenes) -> str:
    """A 嘉宾's or a 组合's scenes as the 嘉宾 list says them: 不放, 随机 (any scene), the one scene's name,
    or N个场景."""
    if scenes.off:
        return "不放"
    keys = () if scenes.random else ticked(scenes)
    if not keys:
        return "随机"
    return scene_name(keys[0]) if len(keys) == 1 else f"{len(keys)}个场景"


class _PeopleScroll(_CardScroll):
    """The 嘉宾 a 组合 picks from: as tall as their rows up to its maximum height, then scrolling."""

    def __init__(self, content: QWidget) -> None:
        super().__init__(content)
        # A scroll area fills its content's background; the pills sit on the card's.
        content.setAutoFillBackground(False)

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        # Measured at the whole width: the scroll bar only comes once they are taller than it lets them be.
        return min(_height_for(self.widget(), width), self.maximumHeight())

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        width = super().minimumSizeHint().width()
        return QSize(width, self.heightForWidth(max(self.width(), width)))


class ComboDialog(Modal):
    """One combination: the 嘉宾 in it (two or more). Its scenes are ticked in 嘉宾场景; a new one is on 随机.

    The 嘉宾 to pick scroll past ROWS rows and half the next, so a long list shows it goes on and the
    dialog keeps its height however many 嘉宾 there are."""

    ROWS = 4

    def __init__(self, likes: list[Entry], combo: Combo | None = None, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.likes = likes
        self.deleted = False
        self.combo = combo
        layout = self.frame("编辑组合" if combo else "添加组合")
        self.card.setFixedWidth(520)
        chosen = {fold(name) for name in combo.names} if combo else set()
        gap = 8
        self.people = _FlowHost(gap=gap)
        self.people_buttons: dict[str, QPushButton] = {}
        on_list = {fold(like.name) for like in likes}
        # Its 嘉宾 since taken off the list stay in it, struck out as the list shows them, until unticked.
        self.gone = [name for name in combo.names if fold(name) not in on_list] if combo else []
        # Its own 嘉宾 first, so the list opens on them however far it scrolls: in the list's order, its top
        # first, then those gone; then the others in the list's order.
        listed = list(reversed(likes))
        mine = [like for like in listed if fold(like.name) in chosen]
        others = [like for like in listed if fold(like.name) not in chosen]
        for like in [*mine, *(Entry(name) for name in self.gone), *others]:
            button = QPushButton(like.shown())
            if like.name in self.gone:
                face = button.font()
                face.setStrikeOut(True)
                button.setFont(face)
                button.setToolTip("已不在嘉宾里")
            button.setObjectName("segment")
            button.setProperty("place", "only")
            button.setCheckable(True)
            button.setAutoDefault(False)
            button.setChecked(fold(like.name) in chosen)
            button.toggled.connect(self._clear_error)
            # A ✓ while chosen.
            button.toggled.connect(lambda on, button=button: button.setIcon(line_icon("check", 14, THEME["on_accent"]) if on else QIcon()))
            button.setIcon(line_icon("check", 14, THEME["on_accent"]) if button.isChecked() else QIcon())
            self.people.addWidget(button)
            self.people_buttons[like.name] = button
        self.people_scroll = _PeopleScroll(self.people)
        self.people_error = _field(layout, "嘉宾", self.people_scroll)
        if self.people_buttons:
            # Measured once in the dialog, wearing its style.
            first = next(iter(self.people_buttons.values()))
            first.ensurePolished()
            pill = first.sizeHint().height()
            self.people_scroll.setMaximumHeight(self.ROWS * (pill + gap) + pill // 2)
        remove = _danger("删除", self._delete) if combo else None
        self.footer(_primary("保存" if combo else "添加", self._accept), left=remove)
        _pointing(self)

    def _clear_error(self, _on: bool = False) -> None:
        _say_error(self.people_error, "")

    def picked(self) -> tuple[str, ...]:
        """The 嘉宾 ticked, in the order they were saved, then those gone still ticked."""
        names = [like.name for like in self.likes] + self.gone
        return tuple(name for name in names if self.people_buttons[name].isChecked())

    def _accept(self) -> None:
        if len(self.picked()) < 2:
            _say_error(self.people_error, "至少选两位嘉宾")
            return
        # A new one starts as a new 嘉宾 does: any scene.
        self.combo = Combo(self.picked(), self.combo.scenes if self.combo else ANY_SCENE)
        self.accept()

    def _delete(self) -> None:
        self.deleted = True
        self.accept()


__all__ = ["ComboDialog", "poster", "scene_name", "scenes_said"]
