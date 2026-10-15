"""嘉宾 themes: the 特效 row a 嘉宾 or a 组合 picks its scene with, and 组合, the 嘉宾 who, all in one
lobby, get a scene of their own (guests.lobby_choice).

The 特效 row shows the scene as a small picture and its name; ▶ and 更换 › open 选择特效
(ui_love_pick). A 嘉宾 with no 特效 of their own is greeted with 经典, and the row and the list say so.
The 组合 show on the 嘉宾 page as a strip of chips over the list, each its scene's picture, its 嘉宾
and the scene's name; a click edits one, and + 新组合 adds one.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QAbstractButton, QDialog, QHBoxLayout, QLabel, QPushButton, QWidget

from blacklist_detect import love_scenes
from blacklist_detect.guests import members
from blacklist_detect.love_scenes import DESIGN
from blacklist_detect.match import fold
from blacklist_detect.model import Combo, Entry
from blacklist_detect.ui_dialogs import _danger, _field, _primary, _say_error
from blacklist_detect.ui_icons import icon as line_icon
from blacklist_detect.ui_kit import Modal, _KeyboardRing
from blacklist_detect.ui_love_pick import ScenePicker, _triangle
from blacklist_detect.ui_theme import SMALL_PT, THEME, _pointing, chinese_font
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
    """A theme as the list says it: the scene's name, and 经典 for none of their own or one this
    version does not have (what plays for it), the scene that replaced a dropped one."""
    return dict(love_scenes.SCENES).get(love_scenes.shown(key), love_scenes.SCENES[0][1])


def thumbnail(key: str, width: int, radius: float = 6) -> QPixmap:
    """A scene's picture made small, its corners rounded, sharp on this screen."""
    ratio = 2.0
    picture = poster(key)
    height = round(width * DESIGN[1] / DESIGN[0]) if picture.isNull() else round(width * picture.height() / max(1, picture.width()))
    out = QPixmap(QSize(round(width * ratio), round(height * ratio)))
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    shape = QPainterPath()
    shape.addRoundedRect(QRectF(0, 0, out.width(), out.height()), radius * ratio, radius * ratio)
    p.setClipPath(shape)
    p.fillPath(shape, QColor("#0b0e14"))
    p.drawPixmap(QRectF(0, 0, out.width(), out.height()), picture, QRectF(picture.rect()))
    p.setClipping(False)
    p.setPen(QColor(THEME["border"]))
    p.drawPath(shape)
    p.end()
    out.setDevicePixelRatio(ratio)
    return out


class ThemeField(QWidget):
    """The 特效 row of a 嘉宾's or a 组合's dialog: the scene's picture, its name, ▶ and 更换 ›. A click
    on the row or on 更换 › opens 选择特效; ▶ opens it playing the scene with its music.

    value() is the theme to save: as it came while the scene shown is not changed (a 嘉宾's "" stays
    none of their own, which plays 经典), else the key picked."""

    THUMB_W = 96
    RADIUS = 10

    def __init__(self, key: str, who: str = "", music=None, music_choice: str = "theme", parent: QWidget | None = None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.who = who
        self.music = music
        self.music_choice = music_choice
        self._key = key
        self._hover = False
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 10, 12, 10)
        row.setSpacing(12)
        self.picture = QLabel()
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

    def scene(self) -> str:
        """The scene shown: the theme's, 经典 for none."""
        key = love_scenes.shown(self._key)
        return key if key in love_scenes.KEYS else love_scenes.KEYS[0]

    def value(self) -> str:
        return self._key

    def _show(self) -> None:
        self.picture.setPixmap(thumbnail(self.scene(), self.THUMB_W))
        self.name.setText(scene_name(self.scene()))

    def change(self, play: bool = False) -> None:
        """选择特效, starting on the scene shown; with play, it plays with its music at once."""
        picker = ScenePicker(self.scene(), self.who, self.music, self.music_choice, parent=self.window())
        if play:
            picker.play()
        if picker.exec() == QDialog.Accepted and picker.key != self.scene():
            self._key = picker.key
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


class ComboDialog(Modal):
    """One combination: the 嘉宾 in it (two or more) and its scene."""

    def __init__(self, likes: list[Entry], combo: Combo | None = None, parent=None, music=None, music_choice: str = "theme") -> None:  # noqa: ANN001
        super().__init__(parent)
        self.likes = likes
        self.deleted = False
        self.combo = combo
        layout = self.frame("编辑组合" if combo else "添加组合")
        self.card.setFixedWidth(520)
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
            # A ✓ while chosen, as 设置's 提醒 shows it.
            button.toggled.connect(lambda on, button=button: button.setIcon(line_icon("check", 14, THEME["on_accent"]) if on else QIcon()))
            button.setIcon(line_icon("check", 14, THEME["on_accent"]) if button.isChecked() else QIcon())
            self.people.addWidget(button)
            self.people_buttons[like.name] = button
        self.people_error = _field(layout, "嘉宾", self.people)
        # A combination exists to pick a scene: a new one starts on 经典.
        self.theme = ThemeField(combo.theme if combo else love_scenes.KEYS[0], "组合", music, music_choice)
        _field(layout, "特效", self.theme)
        remove = _danger("删除", self._delete) if combo else None
        self.footer(_primary("保存" if combo else "添加", self._accept), left=remove)
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


class ComboChip(_KeyboardRing, QAbstractButton):
    """One 组合 on the strip: its scene's picture, its 嘉宾 joined by +, and the scene's name under them.
    A 嘉宾 since taken off the list shows struck out: the combination waits until they are back, or is
    deleted. With no combination it is + 新组合, in a dashed outline."""

    THUMB_W = 56
    H = 46
    PAD = 8
    RADIUS = 8
    # The names cut off past this, with the whole of them in the tooltip.
    WORDS_MAX = 240

    def __init__(self, combo: Combo | None = None, likes: list[Entry] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.combo = combo
        self.people = members(combo, likes or []) if combo else []
        self.picture = thumbnail(combo.theme, self.THUMB_W, 4) if combo else None
        self.theme_name = scene_name(combo.theme) if combo else ""
        who = " + ".join(name for name, _present in self.people)
        self.setText(who or "+ 新组合")
        self.setAccessibleName(f"{who} · {self.theme_name}" if combo else "新组合")
        if combo:
            self.setToolTip(f"{who}\n{self.theme_name}")
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self._hover = False

    @staticmethod
    def _fonts() -> tuple[QFont, QFont]:
        names = chinese_font(SMALL_PT)
        names.setWeight(QFont.DemiBold)
        return names, chinese_font(SMALL_PT)

    def _words_w(self) -> int:
        names, theme = self._fonts()
        wide = max(QFontMetrics(names).horizontalAdvance(self.text()), QFontMetrics(theme).horizontalAdvance(self.theme_name))
        return min(self.WORDS_MAX, wide)

    def sizeHint(self) -> QSize:
        if self.combo is None:
            return QSize(QFontMetrics(self._fonts()[0]).horizontalAdvance(self.text()) + 36, self.H)
        return QSize(self.PAD + self.THUMB_W + 10 + self._words_w() + 14, self.H)

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
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        box = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        enabled = self.isEnabled()
        line = QColor(THEME["field_line" if self._hover and enabled else "border"])
        names, theme = self._fonts()
        if self.combo is None:
            p.setPen(QPen(line, 1.2, Qt.DashLine))
            p.setBrush(QColor(THEME["hover"] if self._hover and enabled else THEME["surface"]))
            p.drawRoundedRect(box, self.RADIUS, self.RADIUS)
            p.setFont(names)
            p.setPen(QColor(THEME["text"] if enabled else THEME["muted"]))
            p.drawText(box, Qt.AlignCenter, self.text())
        else:
            p.setPen(QPen(line, 1))
            p.setBrush(QColor(THEME["hover"] if self._hover else THEME["surface"]))
            p.drawRoundedRect(box, self.RADIUS, self.RADIUS)
            top = (self.height() - self.picture.height() / self.picture.devicePixelRatio()) / 2
            p.drawPixmap(round(self.PAD), round(top), self.picture)
            left = self.PAD + self.THUMB_W + 10
            limit = left + self._words_w()
            line_h = QFontMetrics(names).height()
            y = (self.height() - 2 * line_h - 1) / 2
            self._draw_names(p, names, left, y, limit, line_h)
            p.setFont(theme)
            p.setPen(QColor(THEME["muted"]))
            words = QFontMetrics(theme).elidedText(self.theme_name, Qt.ElideRight, limit - left)
            p.drawText(QRectF(left, y + line_h + 1, limit - left, line_h), Qt.AlignLeft | Qt.AlignVCenter, words)
        if self.show_ring():
            p.setPen(QPen(QColor(THEME["accent_line"]), 1.5, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5), self.RADIUS, self.RADIUS)
        p.end()

    def _draw_names(self, p: QPainter, font: QFont, x: float, y: float, limit: float, line_h: int) -> None:
        """The 嘉宾 one after another, + between them, one gone from the list struck out in gray; cut with …
        where they run past limit."""
        parts: list[tuple[str, bool]] = []
        for index, (name, present) in enumerate(self.people):
            if index:
                parts.append((" + ", True))
            parts.append((name, present))
        for text, present in parts:
            face = QFont(font)
            face.setStrikeOut(not present)
            p.setPen(QColor(THEME["text" if present else "muted"]))
            metrics = QFontMetrics(face)
            wide = metrics.horizontalAdvance(text)
            if x + wide > limit:
                p.setFont(face)
                p.drawText(QRectF(x, y, limit - x, line_h), Qt.AlignLeft | Qt.AlignVCenter, metrics.elidedText(text, Qt.ElideRight, round(limit - x)))
                return
            p.setFont(face)
            p.drawText(QRectF(x, y, wide + 1, line_h), Qt.AlignLeft | Qt.AlignVCenter, text)
            x += wide


class ComboStrip(QWidget):
    """组合 on the 嘉宾 page, between its toolbar and the list: the label, a chip for each combination,
    and + 新组合 at the end, wrapping onto more lines when there are many. It changes only the store;
    changed() tells the page. Hidden while there is nothing to combine and nothing combined."""

    changed = Signal()

    def __init__(self, store, music=None, parent: QWidget | None = None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.store = store
        self.music = music
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        label = QLabel("组合")
        label.setFixedHeight(ComboChip.H)
        row.addWidget(label, 0, Qt.AlignTop)
        self.chips = _FlowHost(gap=8)
        row.addWidget(self.chips, 1)
        self.add_chip: ComboChip | None = None
        self._drawn: tuple | None = None
        self.refresh()

    def refresh(self, force: bool = False) -> None:
        """Redraw from the store, when the combinations or the 嘉宾 they show changed."""
        likes = self.store.likes
        drawn = (tuple(self.store.combos), tuple((like.name, like.shown()) for like in likes))
        if drawn == self._drawn and not force:
            return
        self._drawn = drawn
        self.chips.clear()
        for index, combo in enumerate(self.store.combos):
            chip = ComboChip(combo, likes)
            chip.clicked.connect(lambda _checked=False, index=index: self.edit(index))
            self.chips.addWidget(chip)
        self.add_chip = ComboChip()
        # A combination needs two 嘉宾 to pick from.
        enough = len(likes) >= 2
        self.add_chip.setEnabled(enough)
        self.add_chip.setToolTip("" if enough else "先添加至少两位嘉宾")
        self.add_chip.clicked.connect(self.add)
        self.chips.addWidget(self.add_chip)
        self.setVisible(enough or bool(self.store.combos))

    def _editor(self, combo: Combo | None = None) -> ComboDialog:
        return ComboDialog(self.store.likes, combo, parent=self.window(), music=self.music, music_choice=self.store.love_music)

    def add(self) -> None:
        dialog = self._editor()
        if dialog.exec() != QDialog.Accepted or dialog.combo is None:
            return
        self.store.set_combos([*self.store.combos, dialog.combo])
        self.refresh()
        self.changed.emit()

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
        self.changed.emit()


__all__ = ["ComboChip", "ComboDialog", "ComboStrip", "ThemeField", "poster", "scene_name", "thumbnail"]
