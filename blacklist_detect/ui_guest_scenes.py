"""The 场景 of one 嘉宾, 组合 or 我: ScenePane, the right side of 添加嘉宾 / 编辑嘉宾 (ui_likes.LikeDialog),
添加组合 / 编辑组合 (ui_guests.ComboDialog) and 我的场景 (ui_likes.MeDialog).

On top 放场景, a box: off, 不放 (the list's boxes greyed, their ticks kept while the dialog is open); on with
none ticked, 随机 (any scene); on with ticks, those (several: one of them at random each time). While it is
on, a hint beside it says that none ticked plays any. A new 嘉宾 or 组合 starts off. Under it every scene, one per row, each with its box; past ROWS rows the list scrolls
inside the pane. A click on a name highlights it and plays it over the sample lobby, silent, in the pane's
preview (ScenePreview), which the dialog puts in its left column; ▶ plays it again from its start.

One saved on scenes this version all lacks opens as 随机, as it plays. Opened and saved without its 场景
touched, any one keeps exactly what it had: value() is what was saved until the boxes say otherwise.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from blacklist_detect import love_scenes
from blacklist_detect.guests import ticked
from blacklist_detect.love_scenes import DESIGN
from blacklist_detect.model import ANY_SCENE, Scenes
from blacklist_detect.ui_kit import _SCROLL_BAR, _CardScroll, _KeyboardRing
from blacklist_detect.ui_love_pick import SceneChoice, SceneList, ScenePreview, paint_box
from blacklist_detect.ui_theme import THEME, chinese_font

OFF = Scenes()


class TickBox(_KeyboardRing, QCheckBox):
    """A checkbox drawn as the scene list's boxes are (filled with a ✓ when ticked), the whole row taking
    the click: 放场景, and each 嘉宾 a 组合 picks from."""

    BOX = SceneChoice.BOX
    H = 32
    PAD = 6
    GAP = 8
    RADIUS = 6

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)

    def sizeHint(self) -> QSize:
        return QSize(self.PAD + self.BOX + self.GAP + QFontMetrics(self.font()).horizontalAdvance(self.text()) + self.PAD, self.H)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def hitButton(self, pos: QPoint) -> bool:  # noqa: N802
        return self.rect().contains(pos)

    def paintEvent(self, _event) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        band = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if self.underMouse():
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(THEME["hover"]))
            p.drawRoundedRect(band, self.RADIUS, self.RADIUS)
        if self.show_ring():
            p.setPen(QPen(QColor(THEME["accent_line"]), 1.5, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(band, self.RADIUS, self.RADIUS)
        paint_box(p, QRectF(self.PAD, (self.height() - self.BOX) / 2, self.BOX, self.BOX), self.isChecked())
        p.setFont(self.font())
        p.setPen(QColor(THEME["text"]))
        words = QRect(self.PAD + self.BOX + self.GAP, 0, self.width() - (self.PAD + self.BOX + self.GAP), self.height())
        p.drawText(words, Qt.AlignLeft | Qt.AlignVCenter, QFontMetrics(self.font()).elidedText(self.text(), Qt.ElideRight, words.width()))
        p.end()


def two_columns(layout: QVBoxLayout) -> tuple[QVBoxLayout, QVBoxLayout]:
    """A dialog's content side by side: the left column (its fields and the scene preview) and the right
    (the ScenePane)."""
    row = QHBoxLayout()
    row.setSpacing(24)
    left, right = QVBoxLayout(), QVBoxLayout()
    left.setSpacing(12)
    right.setSpacing(0)
    row.addLayout(left)
    row.addLayout(right)
    layout.addLayout(row)
    return left, right


# Beside 放场景 while it is on, whatever is ticked; nothing while it is off.
HINT = "不勾选场景则随机播放"


class ScenePane(QWidget):
    """放场景 over every scene, one per row, for one 嘉宾, 组合 or 我 saved on scenes. value() is their
    场景 as the boxes say them; preview is the pane's ScenePreview, for the dialog to place."""

    # Rows of scenes shown before the list scrolls: today's ten, so a scene added later scrolls the list
    # rather than making every dialog it is in taller.
    ROWS = 10
    PREVIEW_W = 448

    def __init__(self, scenes: Scenes, preview_width: int = PREVIEW_W, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.saved = scenes
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.play_box = TickBox("放场景")
        self.play_box.setToolTip("不勾：不放；勾上不选场景：随机放一个")
        self.play_box.toggled.connect(self._edited)
        top.addWidget(self.play_box)
        self.hint = QLabel()
        self.hint.setObjectName("sub")
        top.addWidget(self.hint)
        top.addStretch(1)
        column.addLayout(top)
        self.scenes = SceneList(chosen=(), columns=1, width=self.list_width())
        self.scenes.picked.connect(self.show_scene)
        self.scenes.chose.connect(self._edited)
        self.buttons = self.scenes.buttons
        self.scroll = _CardScroll(self.scenes)
        self.scenes.setAutoFillBackground(False)
        self.scroll.setFixedHeight(min(len(self.buttons), self.ROWS) * (SceneChoice.H + SceneList.GAP) - SceneList.GAP)
        # The list's own width and room for the scroll bar beside it, which shows once there are more rows.
        self.scroll.setFixedWidth(self.scenes.width() + _SCROLL_BAR)
        column.addWidget(self.scroll)
        column.addStretch(1)
        self.preview = ScenePreview(None, preview_width, play=self.replay)
        self.play_button = self.preview.play_button
        self.play_button.setToolTip("从头播放")
        # As it opened: 放场景 on or off and the scenes ticked, those this version has.
        on = not scenes.off
        keys = () if scenes.random else ticked(scenes)
        self.play_box.setChecked(on)
        self.scenes.set_chosen(keys)
        self._opened = self._shown()
        self._edited()
        # The first ticked in the list plays; with none, 经典.
        self.key = (*self.scenes.chosen(), self.scenes.key)[0]
        self.show_scene(self.key)

    @staticmethod
    def list_width() -> int:
        """Wide enough for every scene's name whole, highlighted (bold) too, with its box clear of it."""
        font = chinese_font()
        font.setWeight(QFont.DemiBold)
        widest = max(QFontMetrics(font).horizontalAdvance(title) for _key, title in love_scenes.SCENES)
        return max(SceneList.W, SceneChoice.TEXT_X + widest + SceneChoice.BOX_END + 12)

    @staticmethod
    def preview_height(width: int) -> int:
        return round(width * DESIGN[1] / DESIGN[0])

    def _shown(self) -> tuple[bool, frozenset[str]]:
        """放场景 and the ticks that count: none while it is off."""
        on = self.play_box.isChecked()
        return on, frozenset(self.scenes.chosen() if on else ())

    def value(self) -> Scenes:
        """Their 场景 as the boxes say them; as saved while the boxes say what they opened on."""
        on, keys = self._shown()
        if (on, keys) == self._opened:
            return self.saved
        if not on:
            return OFF
        return Scenes(self.scenes.chosen()) if keys else ANY_SCENE

    def has_changes(self) -> bool:
        return self._shown() != self._opened

    def _edited(self, _on: bool = False) -> None:
        """放场景 or a box ticked: off greys the boxes, their ticks kept, and takes the hint away."""
        on = self.play_box.isChecked()
        self.scenes.set_boxes_enabled(on)
        self.hint.setText(HINT if on else "")

    def show_scene(self, key: str) -> None:
        """Highlight this scene and play it over the sample lobby, silent."""
        self.scenes.select(key)
        self.key = self.scenes.key
        self.preview.show_scene(self.key)

    def replay(self) -> None:
        """▶: the highlighted scene again from its start, silent still."""
        self.preview.show_scene(self.key)

    def stop(self) -> None:
        self.preview.stop()


__all__ = ["HINT", "OFF", "ScenePane", "TickBox", "two_columns"]
