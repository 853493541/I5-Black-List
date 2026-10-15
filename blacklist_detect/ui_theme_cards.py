"""特效 cards: each 嘉宾特效 scene shown as a picture of it, its name under it, in a gallery where one
is picked at a time; the picked card wears an accent ring and a ✓.

The pictures are the scenes at their best moment over the fake-name sample lobby, with the 嘉宾 marks
in their look (assets/posters, drawn by build/theme_posters.py). 默认 shows what 嘉宾特效 has, 随机 four
scenes at once, and 无 the bare lobby, dimmed, its name in red as everywhere else.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QAbstractButton, QButtonGroup, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from blacklist_detect import love_scenes
from blacklist_detect.love_scenes import DESIGN
from blacklist_detect.ui_icons import pixmap as line_pixmap
from blacklist_detect.ui_kit import Modal, _KeyboardRing
from blacklist_detect.ui_theme import DIALOG_PAD, THEME, chinese_font

ASSETS = Path(__file__).resolve().parent / "assets"
POSTERS = ASSETS / "posters"
SAMPLE_LOBBY = ASSETS / "sample-lobby.jpg"
# The scenes 随机's picture shows, one in each quarter.
MIXED = ("classic", "cyber", "angel", "claw")
RADIUS = 8
# Room round a picture for the ring that marks it picked.
RING = 3
NAME_GAP = 5
NAME_H = 18
# The dialogs' layout: the preview, the gap after it, the fields' column beside it; the cards under both
# are as wide as all three.
PREVIEW_W = 468
SIDE_GAP = 20
SIDE_W = 292
CONTENT_W = PREVIEW_W + SIDE_GAP + SIDE_W

_pictures: dict[str, QPixmap] = {}


def poster(key: str) -> QPixmap:
    """A scene's picture, at the size it was drawn; "random" four of them, "off" the bare lobby dimmed."""
    if key not in _pictures:
        if key == "random":
            _pictures[key] = _mixed()
        elif key == "off":
            _pictures[key] = _bare()
        else:
            path = POSTERS / f"{love_scenes.shown(key)}.jpg"
            _pictures[key] = QPixmap(str(path)) if path.is_file() else _bare()
    return _pictures[key]


def _size() -> QSize:
    first = QPixmap(str(POSTERS / f"{love_scenes.KEYS[0]}.jpg"))
    return first.size() if not first.isNull() else QSize(480, round(480 * DESIGN[1] / DESIGN[0]))


def _mixed() -> QPixmap:
    size = _size()
    out = QPixmap(size)
    out.fill(QColor("#0b0e14"))
    p = QPainter(out)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    half_w, half_h = size.width() / 2, size.height() / 2
    for index, key in enumerate(MIXED):
        place = QRectF((index % 2) * half_w, (index // 2) * half_h, half_w, half_h)
        p.drawPixmap(place, poster(key), QRectF(poster(key).rect()))
    p.fillRect(QRectF(0, 0, size.width(), size.height()), QColor(8, 10, 16, 110))
    p.setPen(QPen(QColor(255, 255, 255, 70), 2))
    p.drawLine(QPointF(half_w, 0), QPointF(half_w, size.height()))
    p.drawLine(QPointF(0, half_h), QPointF(size.width(), half_h))
    _glyph(p, QPointF(half_w, half_h), size.height() * 0.17, "reload")
    p.end()
    return out


def _bare() -> QPixmap:
    size = _size()
    lobby = QPixmap(str(SAMPLE_LOBBY))
    out = QPixmap(size)
    out.fill(QColor("#0b0e14"))
    p = QPainter(out)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setRenderHint(QPainter.Antialiasing)
    if not lobby.isNull():
        p.drawPixmap(QRectF(0, 0, size.width(), size.height()), lobby, QRectF(lobby.rect()))
    p.fillRect(QRectF(0, 0, size.width(), size.height()), QColor(8, 10, 16, 150))
    # A circle struck through: nothing plays.
    middle, r = QPointF(size.width() / 2, size.height() / 2), size.height() * 0.17
    p.setBrush(QColor(10, 12, 18, 170))
    p.setPen(QPen(QColor(255, 255, 255, 215), r * 0.13))
    p.drawEllipse(middle, r, r)
    p.drawLine(middle + QPointF(-r * 0.7, r * 0.7), middle + QPointF(r * 0.7, -r * 0.7))
    p.end()
    return out


def _glyph(p: QPainter, middle: QPointF, r: float, name: str) -> None:
    """A line icon in a dark disc, over a picture."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(255, 255, 255, 90), max(1.0, r * 0.06)))
    p.setBrush(QColor(10, 12, 18, 190))
    p.drawEllipse(middle, r, r)
    side = round(r * 1.1)
    icon = line_pixmap(name, side, "#ffffff", ratio=1.0, stroke=max(1.5, side / 12))
    p.drawPixmap(QRectF(middle.x() - side / 2, middle.y() - side / 2, side, side), icon, QRectF(icon.rect()))
    p.restore()


class ThemeCard(_KeyboardRing, QAbstractButton):
    """One 特效 as a card: its picture and its name. Checked, an accent ring goes round the picture and
    a ✓ sits in its corner; under the mouse, the picture brightens."""

    def __init__(self, key: str, name: str, picture: QPixmap, width: int, label: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key = key
        self.picture = picture
        # What the card says under its picture; the button's own text stays the choice's name.
        self.label = label or name
        self.setText(name)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(self.label)
        # 无 in red, as in every row of choices: it turns the effect off.
        self.setProperty("off", key == "off")
        self._hover = False
        inner = width - 2 * RING
        self._picture_h = round(inner * DESIGN[1] / DESIGN[0])
        self.setFixedSize(width, RING + self._picture_h + NAME_GAP + NAME_H + RING)

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
        box = QRectF(RING, RING, self.width() - 2 * RING, self._picture_h)
        shape = QPainterPath()
        shape.addRoundedRect(box, RADIUS, RADIUS)
        p.save()
        p.setClipPath(shape)
        p.drawPixmap(box, self.picture, QRectF(self.picture.rect()))
        if self._hover and not self.isChecked():
            p.fillRect(box, QColor(255, 255, 255, 26))
        p.restore()
        accent = QColor(THEME["accent_line"])
        if self.isChecked():
            p.setPen(QPen(accent, 2.5))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(box.adjusted(-1.25, -1.25, 1.25, 1.25), RADIUS + 1.5, RADIUS + 1.5)
            middle, r = QPointF(box.right() - 13, box.top() + 13), 9.5
            p.setPen(QPen(QColor(255, 255, 255, 230), 1.5))
            p.setBrush(accent)
            p.drawEllipse(middle, r, r)
            tick = line_pixmap("check", 12, "#ffffff", stroke=2.0)
            p.drawPixmap(QRectF(middle.x() - 6, middle.y() - 6, 12, 12), tick, QRectF(tick.rect()))
        else:
            line = QColor(THEME["field_line"] if self._hover else THEME["border"])
            p.setPen(QPen(line, 1))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(box.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)
        if self.show_ring():
            p.setPen(QPen(accent, 1.5, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75), RADIUS + 3, RADIUS + 3)
        font = QFont(chinese_font())
        font.setWeight(QFont.DemiBold if self.isChecked() else QFont.Normal)
        p.setFont(font)
        if self.property("off"):
            color = THEME["red"]
        elif self.isChecked():
            color = THEME["accent_line"]
        else:
            color = THEME["text"]
        p.setPen(QColor(color))
        words = QRectF(0, box.bottom() + NAME_GAP, self.width(), NAME_H)
        p.drawText(words, Qt.AlignHCenter | Qt.AlignVCenter, QFontMetrics(font).elidedText(self.label, Qt.ElideRight, self.width()))
        p.end()

    def sizeHint(self) -> QSize:
        return self.size()


class ThemeGallery(QWidget):
    """The 特效 as cards in rows, columns to a row, as wide as width; one is picked at a time, and
    picked(key) says which was clicked. buttons holds the cards by their choice."""

    picked = Signal(str)
    GAP = 12

    def __init__(
        self,
        items: list[tuple[str, str]],
        current: str,
        width: int,
        columns: int = 6,
        labels: dict[str, str] | None = None,
        pictures: dict[str, QPixmap] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(self.GAP)
        grid.setVerticalSpacing(self.GAP - 4)
        card_w = (width - (columns - 1) * self.GAP) // columns
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, ThemeCard] = {}
        known = {key for key, _name in items}
        current = current if current in known else items[0][0]
        for index, (key, name) in enumerate(items):
            picture = (pictures or {}).get(key) or poster(key)
            card = ThemeCard(key, name, picture, card_w, (labels or {}).get(key, ""), self)
            card.setChecked(key == current)
            card.clicked.connect(lambda _checked=False, key=key: self.picked.emit(key))
            self.group.addButton(card)
            grid.addWidget(card, index // columns, index % columns, Qt.AlignLeft | Qt.AlignTop)
            self.buttons[key] = card
        self.setFixedWidth(width)

    def value(self) -> str:
        return next((key for key, card in self.buttons.items() if card.isChecked()), "")


def showcase(dialog: Modal, layout: QVBoxLayout, preview: QWidget) -> QVBoxLayout:
    """The preview on the left and a column for the dialog's fields on its right, the card as wide as
    the cards under them; returns the column. The preview stops when the dialog closes."""
    row = QHBoxLayout()
    row.setSpacing(SIDE_GAP)
    row.addWidget(preview, 0, Qt.AlignTop)
    side = QVBoxLayout()
    side.setSpacing(12)
    row.addLayout(side, 1)
    layout.addLayout(row)
    dialog.card.setFixedWidth(CONTENT_W + 2 * DIALOG_PAD)
    dialog.finished.connect(preview.stop)
    return side


def section(layout: QVBoxLayout, title: str, hint: str = "") -> QVBoxLayout:
    """A part of the dialog under its heading, a quiet hint on the heading's right; returns where the
    part's own widgets go, close under the heading."""
    block = QVBoxLayout()
    block.setSpacing(8)
    row = QHBoxLayout()
    row.setSpacing(8)
    name = QLabel(title)
    name.setObjectName("field")
    row.addWidget(name)
    row.addStretch(1)
    if hint:
        note = QLabel(hint)
        note.setObjectName("sub")
        row.addWidget(note)
    block.addLayout(row)
    layout.addLayout(block)
    return block


__all__ = ["CONTENT_W", "PREVIEW_W", "ThemeCard", "ThemeGallery", "poster", "section", "showcase"]
