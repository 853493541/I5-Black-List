"""嘉宾 themes: the 场景 row a 嘉宾 or a 组合 ticks its scenes with, and 组合, the 嘉宾 who, all in one
lobby, get scenes of their own (guests.lobby_choice).

The 场景 row shows the scene as a small picture and its name, several as their pictures stacked and
N个场景 · 随机, none ticked as 全部场景 · 随机 (any scene), and 不放 as 不放场景; ▶ and 更换 › open
选择场景 (ui_love_pick). The 嘉宾 list says the same in a word or two (scenes_said).
The 组合 head the 嘉宾 page's list (ui_likes), each a row tagged 组合 that opens ComboDialog; 添加 ›
添加组合 adds one.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QWidget

from blacklist_detect import love_scenes
from blacklist_detect.guests import ticked
from blacklist_detect.love_scenes import DESIGN
from blacklist_detect.match import fold
from blacklist_detect.model import ANY_SCENE, Combo, Entry, Scenes
from blacklist_detect.ui_dialogs import _danger, _field, _primary, _say_error
from blacklist_detect.ui_icons import icon as line_icon
from blacklist_detect.ui_kit import Modal, _CardScroll, _height_for
from blacklist_detect.ui_love_pick import ScenePicker, _triangle
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
    """A 嘉宾's or a 组合's scenes as the 嘉宾 list says them: 不放, the one scene's name, N个场景, or
    全部随机 for none ticked (any scene)."""
    if scenes.off:
        return "不放"
    keys = ticked(scenes)
    if not keys:
        return "全部随机"
    return scene_name(keys[0]) if len(keys) == 1 else f"{len(keys)}个场景"


def _height(width: int) -> int:
    """A picture's height at this width, the posters' shape kept."""
    picture = poster(love_scenes.KEYS[0])
    return round(width * DESIGN[1] / DESIGN[0]) if picture.isNull() else round(width * picture.height() / max(1, picture.width()))


def _card(p: QPainter, box: QRectF, key: str, radius: float, ratio: float) -> None:
    """One scene's picture in box, its corners rounded, with a thin edge."""
    picture = poster(key)
    shape = QPainterPath()
    shape.addRoundedRect(box, radius * ratio, radius * ratio)
    p.save()
    p.setClipPath(shape)
    p.fillPath(shape, QColor("#0b0e14"))
    p.drawPixmap(box, picture, QRectF(picture.rect()))
    p.restore()
    p.setPen(QColor(THEME["border"]))
    p.setBrush(Qt.NoBrush)
    p.drawPath(shape)


def _canvas(width: int) -> tuple[QPixmap, float]:
    ratio = 2.0
    out = QPixmap(QSize(round(width * ratio), round(_height(width) * ratio)))
    out.fill(Qt.transparent)
    return out, ratio


def thumbnail(key: str, width: int, radius: float = 6) -> QPixmap:
    """A scene's picture made small, its corners rounded, sharp on this screen."""
    out, ratio = _canvas(width)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    _card(p, QRectF(0, 0, out.width(), out.height()), key, radius, ratio)
    p.end()
    out.setDevicePixelRatio(ratio)
    return out


def stack(keys: tuple[str, ...], width: int, radius: float = 5) -> QPixmap:
    """Up to three scenes' pictures stacked, the first in front, the others stepping up and right behind
    it: as big in all as one thumbnail, so the row does not change size."""
    out, ratio = _canvas(width)
    keys = keys[:3]
    step = 5 * ratio
    shown = len(keys) - 1
    height = out.height() - step * shown
    card_w = min(out.width() - step * shown * 2, height * out.width() / max(1, out.height()))
    span = (out.width() - card_w) / max(1, shown)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    for index in range(shown, -1, -1):
        box = QRectF(index * span, (shown - index) * step, card_w, height)
        _card(p, box, keys[index], radius, ratio)
        if index:
            # Those behind a little darker, so the one in front reads first.
            shade = QPainterPath()
            shade.addRoundedRect(box, radius * ratio, radius * ratio)
            p.fillPath(shade, QColor(0, 0, 0, 70))
    p.end()
    out.setDevicePixelRatio(ratio)
    return out


def no_scene(width: int, radius: float = 6) -> QPixmap:
    """不放场景's picture: an empty tile with a dashed edge and a ⊘."""
    out, ratio = _canvas(width)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    box = QRectF(out.rect()).adjusted(ratio, ratio, -ratio, -ratio)
    p.setPen(QPen(QColor(THEME["border"]), ratio, Qt.DashLine))
    p.setBrush(QColor(THEME["surface_alt"]))
    p.drawRoundedRect(box, radius * ratio, radius * ratio)
    size = min(box.width(), box.height()) * 0.42
    ring = QRectF(box.center().x() - size / 2, box.center().y() - size / 2, size, size)
    p.setPen(QPen(QColor(THEME["muted"]), 1.6 * ratio))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(ring)
    reach = size / 2 * 0.7071
    p.drawLine(QPointF(ring.center().x() - reach, ring.center().y() + reach), QPointF(ring.center().x() + reach, ring.center().y() - reach))
    p.end()
    out.setDevicePixelRatio(ratio)
    return out


class ThemeField(QWidget):
    """The 场景 row of a 嘉宾's or a 组合's dialog: the scenes' pictures, what they are in words, ▶ and
    更换 ›. A click on the row or on 更换 › opens 选择场景; ▶ opens it playing the first ticked (经典 for
    none) with its music.

    value() is the scenes to save: as they came until 选择场景 changes them."""

    THUMB_W = 96
    RADIUS = 10

    def __init__(self, scenes: Scenes, who: str = "", music=None, music_choice: str = "theme", parent: QWidget | None = None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.who = who
        self.music = music
        self.music_choice = music_choice
        self._scenes = scenes
        self._hover = False
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 10, 12, 10)
        row.setSpacing(12)
        self.picture = QLabel()
        # As big for one picture, a stack or none, so the row keeps its height.
        self.picture.setFixedSize(self.THUMB_W, _height(self.THUMB_W))
        row.addWidget(self.picture, 0, Qt.AlignVCenter)
        self.name = QLabel()
        row.addSpacing(4)
        row.addWidget(self.name, 1, Qt.AlignVCenter)
        self.play_button = QPushButton()
        self.play_button.setObjectName("themePlay")
        self.play_button.setAccessibleName("播放")
        self.play_button.setToolTip("从头播放，带音乐")
        self.play_button.setAutoDefault(False)
        self.play_button.setIcon(_triangle(12, THEME["text"]))
        self.play_button.setIconSize(QSize(12, 12))
        self.play_button.setFixedSize(34, 34)
        self.play_button.setStyleSheet(
            f"QPushButton#themePlay {{ background: {THEME['surface']}; border: 1px solid {THEME['border']};"
            " border-radius: 16px; padding: 0 0 0 2px; min-height: 32px; }"
            f" QPushButton#themePlay:hover {{ background: {THEME['hover']}; border-color: {THEME['field_line']}; }}"
        )
        self.play_button.clicked.connect(lambda: self.change(play=True))
        row.addWidget(self.play_button, 0, Qt.AlignVCenter)
        self.change_button = QPushButton("更换 ›")
        self.change_button.setAutoDefault(False)
        self.change_button.clicked.connect(lambda: self.change())
        row.addWidget(self.change_button, 0, Qt.AlignVCenter)
        self._show()

    def value(self) -> Scenes:
        return self._scenes

    def _show(self) -> None:
        keys = ticked(self._scenes)
        if self._scenes.off:
            picture, words = no_scene(self.THUMB_W), "不放场景"
        elif not keys:
            picture, words = stack(love_scenes.KEYS, self.THUMB_W), "全部场景 · 随机"
        elif len(keys) == 1:
            picture, words = thumbnail(keys[0], self.THUMB_W), scene_name(keys[0])
        else:
            picture, words = stack(keys, self.THUMB_W), f"{len(keys)}个场景 · 随机"
        self.picture.setPixmap(picture)
        self.name.setText(words)
        self.setAccessibleName(f"场景：{words}")
        # Several: which, in full.
        self.setToolTip("、".join(scene_name(key) for key in keys) if len(keys) > 1 and not self._scenes.off else "")

    def change(self, play: bool = False) -> None:
        """选择场景, starting on the scenes as they are; with play, the first plays with its music at once."""
        picker = ScenePicker(self._scenes, self.who, self.music, self.music_choice, parent=self.window())
        if play:
            picker.play()
        if picker.exec() == QDialog.Accepted and picker.has_changes():
            self._scenes = picker.value()
            self._show()

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.change()
            return
        super().mouseReleaseEvent(event)

    def event(self, event) -> bool:  # noqa: ANN001
        if event.type() in (event.Type.HoverEnter, event.Type.HoverLeave):
            self._hover = event.type() == event.Type.HoverEnter
            self.update()
        return super().event(event)

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(THEME["field_line" if self._hover else "border"]), 1))
        p.setBrush(QColor(THEME["surface"]))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), self.RADIUS, self.RADIUS)
        p.end()


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
    """One combination: the 嘉宾 in it (two or more) and its scenes.

    The 嘉宾 to pick scroll past ROWS rows and half the next, so a long list shows it goes on and the
    dialog keeps its height however many 嘉宾 there are."""

    ROWS = 4

    def __init__(self, likes: list[Entry], combo: Combo | None = None, parent=None, music=None, music_choice: str = "theme") -> None:  # noqa: ANN001
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
            # A ✓ while chosen, as 设置's 提醒 shows it.
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
        # A new one starts as a new 嘉宾 does: any scene.
        self.theme = ThemeField(combo.scenes if combo else ANY_SCENE, "组合", music, music_choice)
        _field(layout, "场景", self.theme)
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
        self.combo = Combo(self.picked(), self.theme.value())
        self.accept()

    def _delete(self) -> None:
        self.deleted = True
        self.accept()


__all__ = ["ComboDialog", "ThemeField", "no_scene", "poster", "scene_name", "scenes_said", "stack", "thumbnail"]
