"""嘉宾 themes: the row of scenes a 嘉宾 or a combination picks from, and 组合, the 嘉宾 who, all in one
lobby, get a scene of their own (guests.lobby_choice).

A 嘉宾's row starts with 默认 (嘉宾特效's own choice), as every choice lists its default first; a
combination's has only the scenes, since it exists to pick one. Above the row, the picked scene plays
over the sample lobby, as in 嘉宾特效: 默认 plays what 嘉宾特效 has.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from blacklist_detect import love_scenes
from blacklist_detect.guests import members
from blacklist_detect.match import fold
from blacklist_detect.model import Combo, Entry
from blacklist_detect.ui_dialogs import _danger, _field, _footer, _frame, _primary, _say_error
from blacklist_detect.ui_kit import IconButton, Modal
from blacklist_detect.ui_love_pick import ScenePreview
from blacklist_detect.ui_theme import DIALOG_PAD, _pointing
from blacklist_detect.ui_widgets import _FlowHost

# What a 嘉宾 with no theme of their own gets, as the row and the list say it.
DEFAULT_NAME = "默认"


def scene_name(key: str) -> str:
    """A theme as the list says it: the scene's name, 默认 for none, and the scene that replaced a
    dropped one (one this version never had is 默认 too: it plays 嘉宾特效's choice)."""
    names = dict(love_scenes.SCENES)
    return names.get(love_scenes.shown(key), DEFAULT_NAME) if key else DEFAULT_NAME


class ThemeRow:
    """A row of scene buttons, one checked at a time, under a label like the dialog's other fields; the
    preview, when there is one, plays the one checked (默认: default, 嘉宾特效's choice)."""

    def __init__(
        self,
        layout: QVBoxLayout,
        label: str,
        current: str,
        with_default: bool,
        parent: QWidget,
        preview: ScenePreview | None = None,
        default: str = "classic",
    ) -> None:
        self.preview = preview
        self.default = default
        self.host = _FlowHost(gap=8)
        self.group = QButtonGroup(parent)
        self.group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}
        items = [("", DEFAULT_NAME)] if with_default else []
        items += list(love_scenes.SCENES)
        current = love_scenes.shown(current)
        if current not in dict(items):
            current = items[0][0]
        for key, name in items:
            button = QPushButton(name)
            button.setObjectName("segment")
            button.setProperty("place", "only")
            button.setCheckable(True)
            button.setAutoDefault(False)
            button.setChecked(key == current)
            if not key:
                button.setToolTip("跟随嘉宾特效里选的特效")
            button.clicked.connect(lambda _checked=False, key=key: self.show(key))
            self.group.addButton(button)
            self.host.addWidget(button)
            self.buttons[key] = button
        self.error = _field(layout, label, self.host)
        self.show(current)

    def value(self) -> str:
        return next((key for key, button in self.buttons.items() if button.isChecked()), "")

    def show(self, key: str) -> None:
        if self.preview is not None:
            self.preview.show_scene(key or self.default)


def preview_on_top(dialog: Modal, layout: QVBoxLayout) -> ScenePreview:
    """The scene preview at the top of a dialog, the card as wide as it, as 嘉宾特效 is; it stops when the
    dialog closes."""
    preview = ScenePreview(dialog)
    layout.addWidget(preview, 0, Qt.AlignHCenter)
    dialog.card.setFixedWidth(ScenePreview.WIDTH + 2 * DIALOG_PAD)
    dialog.finished.connect(preview.stop)
    return preview


class ComboDialog(Modal):
    """One combination: the 嘉宾 in it (two or more) and its scene."""

    def __init__(self, likes: list[Entry], combo: Combo | None = None, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.likes = likes
        self.deleted = False
        self.combo = combo
        layout = _frame(self, "编辑组合" if combo else "添加组合")
        self.preview = preview_on_top(self, layout)
        chosen = {fold(name) for name in combo.names} if combo else set()
        self.people = _FlowHost(gap=8)
        self.people_buttons: dict[str, QPushButton] = {}
        # The list's own order, its top first.
        for like in reversed(likes):
            button = QPushButton(like.shown())
            button.setObjectName("segment")
            button.setProperty("place", "only")
            button.setCheckable(True)
            button.setAutoDefault(False)
            button.setChecked(fold(like.name) in chosen)
            button.toggled.connect(self._clear_error)
            self.people.addWidget(button)
            self.people_buttons[like.name] = button
        self.people_error = _field(layout, "嘉宾（选两位或更多）", self.people)
        theme = combo.theme if combo else ""
        self.theme = ThemeRow(layout, "特效", theme, with_default=False, parent=self, preview=self.preview)
        remove = _danger("删除", self._delete) if combo else None
        _footer(self, _primary("保存" if combo else "添加", self._accept), left=remove)
        _pointing(self)

    def _clear_error(self, _on: bool = False) -> None:
        _say_error(self.people_error, "")

    def picked(self) -> tuple[str, ...]:
        """The 嘉宾 ticked, in the order they were saved."""
        return tuple(like.name for like in self.likes if self.people_buttons[like.name].isChecked())

    def _accept(self) -> None:
        if len(self.picked()) < 2:
            _say_error(self.people_error, "至少选两位嘉宾")
            return
        self.combo = Combo(self.picked(), self.theme.value())
        self.accept()

    def _delete(self) -> None:
        self.deleted = True
        self.accept()


class CombosDialog(Modal):
    """组合: each combination as its 嘉宾 and its scene, to edit or add. A 嘉宾 since taken off the list
    shows struck out: the combination waits until they are back, or is deleted."""

    def __init__(self, store, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.store = store
        layout = _frame(self, "组合特效")
        note = QLabel("这几位嘉宾都在大厅时，放这里选的特效")
        note.setObjectName("sub")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(6)
        layout.addLayout(self.rows)
        self.empty = QLabel("还没有组合")
        self.empty.setObjectName("sub")
        self.empty.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.empty)
        self.add_button = QPushButton("添加组合")
        self.add_button.setAutoDefault(False)
        self.add_button.clicked.connect(self.add)
        _footer(self, _primary("完成", self.accept), left=self.add_button)
        self.card.setMinimumWidth(480)
        self.refresh()
        _pointing(self)

    def refresh(self) -> None:
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        for index, combo in enumerate(self.store.combos):
            self.rows.addWidget(self._row(index, combo))
        self.empty.setVisible(not self.store.combos)
        # A combination needs two 嘉宾 to pick from.
        enough = len(self.store.likes) >= 2
        self.add_button.setEnabled(enough)
        self.add_button.setToolTip("" if enough else "先添加至少两位嘉宾")

    def _row(self, index: int, combo: Combo) -> QWidget:
        row = QWidget()
        row.setObjectName("comboRow")
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(8)
        parts = [name if present else f"<s>{name}</s>" for name, present in members(combo, self.store.likes)]
        who = QLabel(" + ".join(parts))
        who.setTextFormat(Qt.RichText)
        who.setWordWrap(True)
        line.addWidget(who, 1)
        theme = QLabel(f"→ {scene_name(combo.theme)}")
        theme.setObjectName("field")
        line.addWidget(theme)
        edit = IconButton("edit", "编辑")
        edit.clicked.connect(lambda _checked=False, index=index: self.edit(index))
        line.addWidget(edit)
        return row

    def add(self) -> None:
        dialog = ComboDialog(self.store.likes, parent=self)
        if dialog.exec() != QDialog.Accepted or dialog.combo is None:
            return
        self.store.set_combos([*self.store.combos, dialog.combo])
        self.refresh()

    def edit(self, index: int) -> None:
        if not 0 <= index < len(self.store.combos):
            return
        dialog = ComboDialog(self.store.likes, self.store.combos[index], parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        combos = list(self.store.combos)
        if dialog.deleted:
            del combos[index]
        else:
            combos[index] = dialog.combo
        self.store.set_combos(combos)
        self.refresh()


__all__ = ["DEFAULT_NAME", "ComboDialog", "CombosDialog", "ThemeRow", "preview_on_top", "scene_name"]
