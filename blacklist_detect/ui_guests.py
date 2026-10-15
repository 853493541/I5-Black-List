"""嘉宾 themes: the 特效 cards a 嘉宾 or a combination picks from, and 组合, the 嘉宾 who, all in one
lobby, get a scene of their own (guests.lobby_choice).

The 嘉宾 dialogs share one layout, as 嘉宾特效 does: the picked scene playing over the sample lobby on
the left, the dialog's own fields on its right, and the 特效 as picture cards under both (ui_theme_cards).
A 嘉宾's cards start with 默认 (嘉宾特效's own choice, which it plays), as every choice lists its
default first; a combination's have only the scenes, since it exists to pick one.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from blacklist_detect import love_scenes
from blacklist_detect.guests import members
from blacklist_detect.match import fold
from blacklist_detect.model import Combo, Entry
from blacklist_detect.ui_dialogs import _danger, _field, _footer, _frame, _primary, _say_error
from blacklist_detect.ui_kit import IconButton, Modal
from blacklist_detect.ui_love_pick import ScenePreview, tune_for
from blacklist_detect.ui_theme import THEME, _pointing
from blacklist_detect.ui_theme_cards import CONTENT_W, ThemeGallery, poster, section, showcase
from blacklist_detect.ui_widgets import _FlowHost

# What a 嘉宾 with no theme of their own gets, as the cards and the list say it.
DEFAULT_NAME = "默认"
def scene_name(key: str) -> str:
    """A theme as the list says it: the scene's name, 默认 for none, and the scene that replaced a
    dropped one (one this version never had is 默认 too: it plays 嘉宾特效's choice)."""
    names = dict(love_scenes.SCENES)
    return names.get(love_scenes.shown(key), DEFAULT_NAME) if key else DEFAULT_NAME


def choice_name(key: str) -> str:
    """嘉宾特效's own choice as words: a scene's name, 随机 or 无."""
    return {"random": "随机", "off": "无"}.get(key) or scene_name(key)


class ThemeRow:
    """The 特效 cards under their heading, one picked at a time; the preview plays the one picked
    (默认: default, 嘉宾特效's choice, which its card shows)."""

    def __init__(
        self,
        layout: QVBoxLayout,
        current: str,
        with_default: bool,
        preview: ScenePreview,
        default: str = "classic",
    ) -> None:
        self.preview = preview
        self.default = default or "classic"
        items = [("", DEFAULT_NAME)] if with_default else []
        items += list(love_scenes.SCENES)
        current = love_scenes.shown(current) if current else ""
        if current not in dict(items):
            current = items[0][0]
        block = section(layout, "特效", "默认跟随嘉宾特效里的选择" if with_default else "这几位嘉宾都在大厅时放")
        self.gallery = ThemeGallery(
            items,
            current,
            CONTENT_W,
            labels={"": f"{DEFAULT_NAME} · {choice_name(self.default)}"},
            pictures={"": poster(self.default)},
        )
        if with_default:
            self.gallery.buttons[""].setToolTip("跟随嘉宾特效里选的特效")
        self.gallery.picked.connect(self.show)
        block.addWidget(self.gallery)
        self.buttons = self.gallery.buttons
        self.show(current)

    def value(self) -> str:
        return self.gallery.value()

    def show(self, key: str) -> None:
        self.preview.show_scene(key or self.default, DEFAULT_NAME if not key else "")


class ScenePlayer:
    """▶ on the preview: the picked scene from its start with the music a lobby would play with it."""

    def __init__(self, music, music_choice: str) -> None:  # noqa: ANN001
        self.music = music
        self.music_choice = music_choice
        self.preview: ScenePreview | None = None

    def __call__(self) -> None:
        preview = self.preview
        if preview is None:
            return
        preview.show_scene(preview.choice, preview.prefix)
        if self.music is not None:
            self.music.preview(tune_for(preview.scene, self.music_choice))

    def stop(self) -> None:
        if self.music is not None:
            self.music.stop()


def thumbnail(key: str, width: int, radius: float = 6) -> QPixmap:
    """A scene's picture made small, its corners rounded, sharp on this screen."""
    ratio = 2.0
    picture = poster(key)
    height = round(width * picture.height() / max(1, picture.width()))
    out = QPixmap(QSize(round(width * ratio), round(height * ratio)))
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    shape = QPainterPath()
    shape.addRoundedRect(QRectF(0, 0, out.width(), out.height()), radius * ratio, radius * ratio)
    p.setClipPath(shape)
    p.drawPixmap(QRectF(0, 0, out.width(), out.height()), picture, QRectF(picture.rect()))
    p.setClipping(False)
    p.setPen(QColor(THEME["border"]))
    p.drawPath(shape)
    p.end()
    out.setDevicePixelRatio(ratio)
    return out


class ComboDialog(Modal):
    """One combination: the 嘉宾 in it (two or more) and its scene."""

    def __init__(self, likes: list[Entry], combo: Combo | None = None, parent=None, music=None, music_choice: str = "organ") -> None:  # noqa: ANN001
        super().__init__(parent)
        self.likes = likes
        self.deleted = False
        self.combo = combo
        layout = _frame(self, "编辑组合" if combo else "添加组合")
        layout.setSpacing(16)
        self.player = ScenePlayer(music, music_choice)
        self.preview = ScenePreview(self, play=self.player)
        self.player.preview = self.preview
        side = showcase(self, layout, self.preview)
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
        # A long list scrolls beside the preview rather than making the dialog taller.
        scroll = QScrollArea()
        scroll.setObjectName("peopleScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea#peopleScroll, QScrollArea#peopleScroll > QWidget > QWidget { background: transparent; }")
        scroll.setWidget(self.people)
        scroll.setMaximumHeight(self.preview.height() - 30)
        self.people_error = _field(side, "嘉宾（选两位或更多）", scroll)
        side.addStretch(1)
        self.theme = ThemeRow(layout, combo.theme if combo else "", with_default=False, preview=self.preview)
        remove = _danger("删除", self._delete) if combo else None
        _footer(self, _primary("保存" if combo else "添加", self._accept), left=remove)
        self.finished.connect(self.player.stop)
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
    """组合: each combination as its scene's picture, its 嘉宾 and the scene's name, to edit or add. A
    嘉宾 since taken off the list shows struck out: the combination waits until they are back, or is
    deleted."""

    THUMB_W = 76

    def __init__(self, store, parent=None, music=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.store = store
        self.music = music
        layout = _frame(self, "组合特效")
        note = QLabel("这几位嘉宾都在大厅时，放这里选的特效")
        note.setObjectName("sub")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(0)
        layout.addLayout(self.rows)
        self.empty = QLabel("还没有组合")
        self.empty.setObjectName("sub")
        self.empty.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.empty)
        self.add_button = QPushButton("添加组合")
        self.add_button.setAutoDefault(False)
        self.add_button.clicked.connect(self.add)
        _footer(self, _primary("完成", self.accept), left=self.add_button)
        self.card.setFixedWidth(520)
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
        row = QFrame()
        row.setObjectName("comboRow")
        row.setStyleSheet(f"QFrame#comboRow {{ border-bottom: 1px solid {THEME['border']}; }}")
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 10, 0, 10)
        line.setSpacing(12)
        picture = QLabel()
        picture.setPixmap(thumbnail(combo.theme or love_scenes.KEYS[0], self.THUMB_W))
        line.addWidget(picture, 0, Qt.AlignVCenter)
        words = QVBoxLayout()
        words.setSpacing(2)
        parts = [name if present else f"<s>{name}</s>" for name, present in members(combo, self.store.likes)]
        who = QLabel(" + ".join(parts))
        who.setTextFormat(Qt.RichText)
        who.setWordWrap(True)
        words.addWidget(who)
        theme = QLabel(scene_name(combo.theme))
        theme.setObjectName("sub")
        words.addWidget(theme)
        line.addLayout(words, 1)
        edit = IconButton("edit", "编辑")
        edit.clicked.connect(lambda _checked=False, index=index: self.edit(index))
        line.addWidget(edit, 0, Qt.AlignVCenter)
        return row

    def _editor(self, combo: Combo | None = None) -> ComboDialog:
        return ComboDialog(self.store.likes, combo, parent=self, music=self.music, music_choice=self.store.love_music)

    def add(self) -> None:
        dialog = self._editor()
        if dialog.exec() != QDialog.Accepted or dialog.combo is None:
            return
        self.store.set_combos([*self.store.combos, dialog.combo])
        self.refresh()

    def edit(self, index: int) -> None:
        if not 0 <= index < len(self.store.combos):
            return
        dialog = self._editor(self.store.combos[index])
        if dialog.exec() != QDialog.Accepted:
            return
        combos = list(self.store.combos)
        if dialog.deleted:
            del combos[index]
        else:
            combos[index] = dialog.combo
        self.store.set_combos(combos)
        self.refresh()


__all__ = ["DEFAULT_NAME", "ComboDialog", "CombosDialog", "ScenePlayer", "ThemeRow", "choice_name", "scene_name", "thumbnail"]
