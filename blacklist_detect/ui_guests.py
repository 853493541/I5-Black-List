"""嘉宾 themes: the scenes a 嘉宾 or a 组合 has as the 嘉宾 list says them, and 组合, the 嘉宾 who, all in
one lobby, get scenes of their own (guests.lobby_choice).

The 嘉宾 list says a 嘉宾's or a 组合's scenes in a word or two (scenes_said), after their dots (scene_dots);
they are ticked in the dialog that edits it, beside its fields (ui_guest_scenes.ScenePane). The 组合 head the 嘉宾 page's list
(ui_likes), each a row tagged 组合 that opens ComboDialog; 添加组合 adds one, on 不放 to begin with.
"""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QFrame, QSizePolicy, QVBoxLayout, QWidget

from blacklist_detect import love_scenes
from blacklist_detect.guests import ticked
from blacklist_detect.match import fold
from blacklist_detect.model import Combo, Entry, Scenes
from blacklist_detect.ui_dialogs import _danger, _field, _primary, _say_error
from blacklist_detect.ui_guest_scenes import OFF, ScenePane, TickBox, two_columns
from blacklist_detect.ui_kit import _SCROLL_BAR, Modal, _CardScroll
from blacklist_detect.ui_love_pick import POSTERS, poster
from blacklist_detect.ui_theme import _pointing


def scene_name(key: str) -> str:
    """A scene as the list says it: its name, the scene that replaced a dropped one, and 经典 for one
    this version does not have."""
    return dict(love_scenes.SCENES).get(love_scenes.shown(key), love_scenes.SCENES[0][1])


def scenes_said(scenes: Scenes) -> str:
    """A 嘉宾's or a 组合's scenes as the 嘉宾 list says them: nothing on 不放, 随机 (any scene), the one
    scene's name, or N个场景."""
    keys = scene_dots(scenes)
    if keys == ["random"]:
        return "随机"
    return scene_name(keys[0]) if len(keys) == 1 else f"{len(keys)}个场景" if keys else ""


def scene_dots(scenes: Scenes) -> list[str]:
    """The dots (ui_love_pick.scene_dot) before the 嘉宾 list's words for scenes: none on 不放, 随机's
    ("random") for any scene, else each scene ticked's."""
    if scenes.off:
        return []
    return list(() if scenes.random else ticked(scenes)) or ["random"]


class _PeopleScroll(_CardScroll):
    """The 嘉宾 to pick, in a box as tall as the column leaves it: however many there are, they scroll in it
    and never make the dialog taller."""

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return False

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSizeHint()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.widget().minimumSizeHint().width() + _SCROLL_BAR, ComboDialog.MIN_ROWS * TickBox.H)


class ComboDialog(Modal):
    """One combination: on the left 已添加的嘉宾, every 嘉宾 in a box, those in it (two or more) ticked, with
    its 场景 playing at the column's foot; on the right the 场景 that greet them (ScenePane). A new one is
    on 不放. 编辑组合 is laid out as 添加组合 is. others: the other 组合 saved; the same 嘉宾 as one of them
    cannot be saved again.

    The box takes the height the 场景 beside it leave, and its 嘉宾 scroll in it past that, so the dialog
    keeps its height however many 嘉宾 there are."""

    # Rows the box shows at the least, when the column is at its shortest.
    MIN_ROWS = 3
    PREVIEW_W = 424
    PAD = 4

    def __init__(self, likes: list[Entry], combo: Combo | None = None, parent=None, others: list[Combo] | None = None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.likes = likes
        self.taken = [{fold(name) for name in other.names} for other in others or []]
        self.deleted = False
        self.combo = combo
        layout = self.frame("编辑组合" if combo else "添加组合")
        left, right = two_columns(layout)
        chosen = {fold(name) for name in combo.names} if combo else set()
        self.people = QWidget()
        rows = QVBoxLayout(self.people)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(0)
        self.people_buttons: dict[str, TickBox] = {}
        on_list = {fold(like.name) for like in likes}
        # Its 嘉宾 since taken off the list stay in it, struck out as the list shows them, until unticked.
        self.gone = [name for name in combo.names if fold(name) not in on_list] if combo else []
        # Its own 嘉宾 first, so the list opens on them however far it scrolls: in the list's order, its top
        # first, then those gone; then the others in the list's order.
        listed = list(reversed(likes))
        mine = [like for like in listed if fold(like.name) in chosen]
        others = [like for like in listed if fold(like.name) not in chosen]
        for like in [*mine, *(Entry(name) for name in self.gone), *others]:
            box = TickBox(like.shown())
            box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            if like.name in self.gone:
                face = box.font()
                face.setStrikeOut(True)
                box.setFont(face)
                box.setToolTip("已不在嘉宾里")
            elif like.nickname:
                box.setToolTip(like.name)
            box.setChecked(fold(like.name) in chosen)
            box.toggled.connect(self._clear_error)
            rows.addWidget(box)
            self.people_buttons[like.name] = box
        rows.addStretch(1)
        self.people_scroll = _PeopleScroll(self.people)
        self.people.setAutoFillBackground(False)
        self.people_box = QFrame()
        self.people_box.setObjectName("section")
        inside = QVBoxLayout(self.people_box)
        inside.setContentsMargins(self.PAD, self.PAD, self.PAD, self.PAD)
        inside.addWidget(self.people_scroll)
        self.people_box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.people_error = _field(left, "已添加的嘉宾", self.people_box)
        # The box takes the column's free height, the preview at its foot.
        left.setStretch(left.count() - 1, 1)
        self.pane = ScenePane(combo.scenes if combo else OFF, self.PREVIEW_W)
        left.addWidget(self.pane.preview)
        right.addWidget(self.pane)
        remove = _danger("删除", self._delete) if combo else None
        self.footer(_primary("保存" if combo else "添加", self._accept), left=remove)
        self._before = set(self.picked())
        _pointing(self)

    def _clear_error(self, _on: bool = False) -> None:
        _say_error(self.people_error, "")

    def picked(self) -> tuple[str, ...]:
        """The 嘉宾 ticked, in the order they were saved, then those gone still ticked."""
        names = [like.name for like in self.likes] + self.gone
        return tuple(name for name in names if self.people_buttons[name].isChecked())

    def has_changes(self) -> bool:
        return set(self.picked()) != self._before or self.pane.has_changes()

    def _accept(self) -> None:
        if len(self.picked()) < 2:
            _say_error(self.people_error, "至少选两位嘉宾")
            return
        if {fold(name) for name in self.picked()} in self.taken:
            _say_error(self.people_error, "已有这几位嘉宾的组合")
            return
        self.combo = Combo(self.picked(), self.pane.value())
        self.accept()

    def _delete(self) -> None:
        self.deleted = True
        self.accept()

    def done(self, result: int) -> None:  # noqa: A003
        self.pane.stop()
        super().done(result)


__all__ = ["POSTERS", "ComboDialog", "poster", "scene_name", "scenes_said"]
