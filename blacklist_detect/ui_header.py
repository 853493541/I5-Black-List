"""The right end of the window's header: what checking is doing, and whose app this is.

StatusChip is a tinted pill with a dot and a few words. A click flips 自动检查 and 手动检查;
under the pointer the dot turns into the flip arrows to say so.

ProfileChip shows 角色名称 the way an app shows its account, at the far right. A click opens
NamePopover, a small box to change it.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QFrame, QGraphicsDropShadowEffect, QLabel, QLineEdit, QVBoxLayout, QWidget

from blacklist_detect.ui_icons import pixmap as line_pixmap
from blacklist_detect.ui_kit import _KeyboardRing, activates
from blacklist_detect.ui_theme import BODY_PT, SMALL_PT, THEME, _mix, chinese_font

_CHIP_H = 30


def _ring(painter: QPainter, rect: QRectF) -> None:
    """The keyboard focus ring of a pill, just inside its edge."""
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(QColor(THEME["accent_line"]), 1.4))
    inner = rect.adjusted(1.5, 1.5, -1.5, -1.5)
    painter.drawRoundedRect(inner, inner.height() / 2, inner.height() / 2)


class StatusChip(_KeyboardRing, QAbstractButton):
    """自动检查中, 手动检查 with its hotkey, or what went wrong, in a pill tinted by its tone."""

    _PAD_L = 10
    _PAD_R = 12
    _MARK = 16
    _GAP = 6
    _KEY_GAP = 8
    _TEXT_MAX = 200

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusChip")
        self.setFocusPolicy(Qt.TabFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFixedHeight(_CHIP_H)
        self._tone = "idle"
        self._key = ""
        self._hover = False

    def set_state(self, text: str, tone: str, key: str = "") -> None:
        self.setText(text)
        self.setAccessibleName(f"{text} {key}".strip())
        self._tone = tone
        self._key = key
        self.updateGeometry()
        self.update()

    def tone(self) -> str:
        return self._tone

    def key_text(self) -> str:
        return self._key

    def hovered(self) -> bool:
        return self._hover

    @staticmethod
    def _font() -> QFont:
        return chinese_font(BODY_PT)

    @staticmethod
    def _key_font() -> QFont:
        return chinese_font(SMALL_PT)

    def _shown_text(self) -> str:
        return QFontMetrics(self._font()).elidedText(self.text(), Qt.ElideRight, self._TEXT_MAX)

    def _key_width(self) -> int:
        return QFontMetrics(self._key_font()).horizontalAdvance(self._key) + 12 if self._key else 0

    def sizeHint(self) -> QSize:
        width = self._PAD_L + self._MARK + self._GAP + QFontMetrics(self._font()).horizontalAdvance(self._shown_text())
        if self._key:
            width += self._KEY_GAP + self._key_width()
        return QSize(width + self._PAD_R, _CHIP_H)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def _colors(self) -> tuple[str, str, str | None]:
        """The pill's wash, its words, and its dot (None draws a hollow dot)."""
        t = THEME
        if self._tone == "watchOn":
            return t["green_wash"], t["green"], t["green"]
        if self._tone == "hit":
            return t["red_wash"], t["red"], t["red"]
        if self._tone == "watchOff":
            return t["chip_bg"], t["text"], None
        return t["chip_bg"], t["muted"], t["muted"]

    def enterEvent(self, event) -> None:  # noqa: ANN001
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: ANN001
        if activates(event):
            self.click()
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        wash, ink, dot = self._colors()
        body = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        fill = _mix(wash, ink, 0.12) if (self._hover or self.isDown()) else QColor(wash)
        painter.setPen(QPen(_mix(wash, ink, 0.16), 1))
        painter.setBrush(fill)
        painter.drawRoundedRect(body, body.height() / 2, body.height() / 2)
        middle = self.height() / 2
        x = self._PAD_L
        if self._hover or self.show_ring():
            # Under the pointer the dot becomes the flip arrows: a click changes the mode.
            painter.drawPixmap(QPoint(x, round(middle - self._MARK / 2)), line_pixmap("reload", self._MARK, ink))
        else:
            center = QRectF(x + self._MARK / 2 - 4, middle - 4, 8, 8)
            if dot is None:
                painter.setPen(QPen(QColor(THEME["muted"]), 1.4))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(center.adjusted(0.7, 0.7, -0.7, -0.7))
            else:
                halo = QColor(dot)
                halo.setAlphaF(0.22)
                painter.setPen(Qt.NoPen)
                painter.setBrush(halo)
                painter.drawEllipse(center.adjusted(-2, -2, 2, 2))
                painter.setBrush(QColor(dot))
                painter.drawEllipse(center)
        x += self._MARK + self._GAP
        painter.setFont(self._font())
        painter.setPen(QColor(ink))
        text = self._shown_text()
        text_width = QFontMetrics(self._font()).horizontalAdvance(text)
        painter.drawText(QRectF(x, 0, text_width + 2, self.height()), Qt.AlignLeft | Qt.AlignVCenter, text)
        if self._key:
            # The hotkey as a key cap, the way shortcuts are shown in menus and docs.
            key = QRectF(x + text_width + self._KEY_GAP, middle - 10, self._key_width(), 20)
            painter.setPen(QPen(QColor(THEME["border"]), 1))
            painter.setBrush(QColor(THEME["surface"]))
            painter.drawRoundedRect(key.adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
            painter.setFont(self._key_font())
            painter.setPen(QColor(THEME["muted"]))
            painter.drawText(key, Qt.AlignCenter, self._key)
        if self.show_ring():
            _ring(painter, body)


def _initial(name: str) -> str:
    name = name.strip()
    return name[:1].upper() if name else ""


class ProfileChip(_KeyboardRing, QAbstractButton):
    """角色名称 with a round initial, and a chevron that says a click opens it for a change."""

    _AVATAR = 24
    _PAD_L = 3
    _PAD_R = 10
    _GAP = 8
    _NAME_MAX = 120

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("profileChip")
        self.setFocusPolicy(Qt.TabFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFixedHeight(_CHIP_H)
        self.setAccessibleName("角色名称")
        self._name = ""
        self._hover = False

    def name(self) -> str:
        return self._name

    def set_name(self, name: str) -> None:
        self._name = name.strip()
        self.setToolTip(self._name or "角色名称")
        self.updateGeometry()
        self.update()

    @staticmethod
    def _font() -> QFont:
        return chinese_font(BODY_PT)

    def _shown(self) -> str:
        return QFontMetrics(self._font()).elidedText(self._name or "角色名称", Qt.ElideRight, self._NAME_MAX)

    def sizeHint(self) -> QSize:
        text = QFontMetrics(self._font()).horizontalAdvance(self._shown())
        return QSize(self._PAD_L + self._AVATAR + self._GAP + text + 6 + 12 + self._PAD_R, _CHIP_H)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def enterEvent(self, event) -> None:  # noqa: ANN001
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: ANN001
        if activates(event):
            self.click()
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        body = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self._hover or self.isDown():
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(THEME["hover"]))
            painter.drawRoundedRect(body, body.height() / 2, body.height() / 2)
        middle = self.height() / 2
        avatar = QRectF(self._PAD_L, middle - self._AVATAR / 2, self._AVATAR, self._AVATAR)
        dark = THEME.get("scheme") == "dark"
        accent = THEME["accent_line"] if dark else THEME["accent"]
        if self._name:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(THEME["accent_wash"]))
            painter.drawEllipse(avatar)
            face = chinese_font(SMALL_PT)
            face.setWeight(QFont.Weight.DemiBold)
            painter.setFont(face)
            painter.setPen(QColor(accent))
            painter.drawText(avatar, Qt.AlignCenter, _initial(self._name))
        else:
            # No name yet: an outlined circle with a plus, asking for one.
            painter.setPen(QPen(QColor(THEME["border"]), 1.2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(avatar.adjusted(0.6, 0.6, -0.6, -0.6))
            painter.drawPixmap(QPoint(round(avatar.center().x() - 7), round(middle - 7)), line_pixmap("add", 14, THEME["muted"]))
        x = avatar.right() + self._GAP
        painter.setFont(self._font())
        painter.setPen(QColor(THEME["text"] if self._name else THEME["muted"]))
        text = self._shown()
        width = QFontMetrics(self._font()).horizontalAdvance(text)
        painter.drawText(QRectF(x, 0, width + 2, self.height()), Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.drawPixmap(QPoint(round(x + width + 6), round(middle - 6)), line_pixmap("chevron_down", 12, THEME["muted"]))
        if self.show_ring():
            _ring(painter, body)


class NamePopover(QWidget):
    """The small box under ProfileChip. Enter or a click elsewhere keeps the name; Esc puts it back."""

    closed = Signal()
    # Room around the card for its shadow: left, top, right, bottom.
    _SHADOW = (14, 8, 14, 20)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(*self._SHADOW)
        card = QFrame()
        card.setObjectName("popover")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 56))
        card.setGraphicsEffect(shadow)
        self.card = card
        outer.addWidget(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(8)
        title = QLabel("角色名称")
        title.setObjectName("popoverTitle")
        layout.addWidget(title)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("游戏里的名字")
        self.edit.setAccessibleName("角色名称")
        self.edit.returnPressed.connect(self.close)
        layout.addWidget(self.edit)
        hint = QLabel("记录里会标出你自己。")
        hint.setObjectName("rowHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.setFixedWidth(280 + self._SHADOW[0] + self._SHADOW[2])
        self._before = ""

    def open_below(self, anchor: QWidget) -> None:
        """Open under the anchor, the card's right edge on the anchor's, inside the screen."""
        self._before = self.edit.text()
        self.adjustSize()
        left, top, right, _bottom = self._SHADOW
        corner = anchor.mapToGlobal(QPoint(anchor.width(), anchor.height() + 6))
        place = QPoint(corner.x() - self.width() + right, corner.y() - top)
        screen = QGuiApplication.screenAt(corner) or QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            place.setX(max(area.left() - left, min(place.x(), area.right() - self.width() + right)))
            place.setY(max(area.top() - top, min(place.y(), area.bottom() - self.height())))
        self.move(place)
        self.show()
        self.edit.setFocus(Qt.PopupFocusReason)
        self.edit.selectAll()

    def keyPressEvent(self, event) -> None:  # noqa: ANN001
        if event.key() == Qt.Key_Escape:
            self.edit.setText(self._before)
            self.close()
            return
        super().keyPressEvent(event)

    def hideEvent(self, event) -> None:  # noqa: ANN001
        super().hideEvent(event)
        self.closed.emit()

