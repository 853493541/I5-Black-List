"""The right end of the window's header: what checking is doing, and whose app this is.

StatusChip is a pill with a dot and a few words, on the card's own color or tinted by its tone. A
click opens CheckPanel under it, the 检查 settings (显示, 方式, 直播模式).

ProfileChip shows 角色名称 the way an app shows its account, at the far right, with a pen.
A click turns it into a box for the name, in the same place (see MainWindow._edit_player_name).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QApplication, QFrame, QSizePolicy, QVBoxLayout, QWidget

from blacklist_detect.ui_icons import pixmap as line_pixmap
from blacklist_detect.ui_kit import _KeyboardRing, activates
from blacklist_detect.ui_theme import BODY_PT, CARD_RADIUS, SMALL_PT, THEME, _mix, chinese_font

_CHIP_H = 30


def _accent_ink() -> str:
    """The accent as words and marks on a pill: the deep one on light, the bright one on dark."""
    return THEME["accent_line"] if THEME.get("scheme") == "dark" else THEME["accent"]


def _surface_fill(edge: str, pressed: bool) -> tuple[QColor, QColor]:
    """A pill on the card's color, and its edge: under the pointer the accent's light wash, as a row's."""
    if pressed:
        return QColor(THEME["hover"]), QColor(THEME["accent_line"])
    return QColor(THEME["surface"]), QColor(edge)


def _ring(painter: QPainter, rect: QRectF) -> None:
    """The keyboard focus ring of a pill, just inside its edge."""
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(QColor(THEME["accent_line"]), 1.4))
    inner = rect.adjusted(1.5, 1.5, -1.5, -1.5)
    painter.drawRoundedRect(inner, inner.height() / 2, inner.height() / 2)


class StatusChip(_KeyboardRing, QAbstractButton):
    """自动检查中, 手动检查 with its hotkey, or what went wrong, in a pill colored by its tone.

    手动检查 (waiting for the hotkey) and 正在准备识别 sit on the card's color with its edge, as the
    page's cards do; 自动检查中 is tinted with the accent, a problem in red."""

    _PAD_L = 10
    _PAD_R = 10
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
        """「· Alt+1」 after the words, in gray: the hotkey, without a box of its own."""
        return QFontMetrics(self._key_font()).horizontalAdvance(f"·  {self._key}") if self._key else 0

    def sizeHint(self) -> QSize:
        width = self._PAD_L + self._MARK + self._GAP + QFontMetrics(self._font()).horizontalAdvance(self._shown_text())
        if self._key:
            width += self._KEY_GAP + self._key_width()
        return QSize(width + self._PAD_R, _CHIP_H)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def _colors(self) -> tuple[str, str, str | None, str]:
        """The pill's wash, its words, its dot (None draws a hollow ring in the accent), and its edge."""
        t = THEME
        if self._tone == "watchOn":
            accent = _accent_ink()
            return t["accent_wash"], accent, accent, _mix(t["accent_wash"], accent, 0.28).name()
        if self._tone == "hit":
            return t["red_wash"], t["red"], t["red"], _mix(t["red_wash"], t["red"], 0.2).name()
        if self._tone == "watchOff":
            return t["surface"], t["text"], None, t["border"]
        return t["surface"], t["muted"], t["muted"], t["border"]

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
        wash, ink, dot, edge = self._colors()
        body = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        pressed = self._hover or self.isDown()
        if wash == THEME["surface"]:
            fill, line = _surface_fill(edge, pressed)
        else:
            fill, line = (_mix(wash, ink, 0.12) if pressed else QColor(wash)), QColor(edge)
        painter.setPen(QPen(line, 1))
        painter.setBrush(fill)
        painter.drawRoundedRect(body, body.height() / 2, body.height() / 2)
        middle = self.height() / 2
        x = self._PAD_L
        # The dot says the state; under the pointer only the pill's wash deepens.
        center = QRectF(x + self._MARK / 2 - 4, middle - 4, 8, 8)
        if dot is None:
            painter.setPen(QPen(QColor(_accent_ink()), 1.4))
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
            key = QRectF(x + text_width + self._KEY_GAP, 0, self._key_width() + 2, self.height())
            painter.setFont(self._key_font())
            painter.setPen(QColor(THEME["muted"]))
            painter.drawText(key, Qt.AlignLeft | Qt.AlignVCenter, f"·  {self._key}")
        if self.show_ring():
            _ring(painter, body)


class CheckPanel(QFrame):
    """检查's settings in a card under the status pill: 显示, 方式 and 直播模式, with 直播姬's state while it is on.

    It lies over the window the way a menu does. Esc, a click anywhere else in the window, a page
    change or the pill again closes it. A question or a guide it opens comes over the window as a
    dialog and leaves it open, so the answer shows in it.
    """

    _SHADOW = 16
    _DROP = 4
    _GAP = 6

    def __init__(self, card: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("checkPanel")
        self.card = card
        layout = QVBoxLayout(self)
        layout.setContentsMargins(self._SHADOW, self._SHADOW - self._DROP, self._SHADOW, self._SHADOW + self._DROP)
        layout.addWidget(card)
        self.anchor: QWidget | None = None
        self.hide()

    def attach(self, host: QWidget, anchor: QWidget) -> None:
        """Lie over host, under anchor (the pill)."""
        self.setParent(host)
        self.anchor = anchor
        host.installEventFilter(self)
        self.hide()

    def toggle(self) -> None:
        if self.isVisible():
            self.close_panel()
        else:
            self.open_panel()

    def open_panel(self, focus: bool = True) -> None:
        """Show it under its pill. focus=False for a card that opens by itself: it must not take
        the keys from a box the player is typing in."""
        if self.anchor is None or self.parentWidget() is None:
            return
        self._place()
        self.show()
        self.raise_()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        if focus:
            self.card.setFocus(Qt.PopupFocusReason)

    def close_panel(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self.hide()

    def _place(self) -> None:
        """Its card's right edge under the pill's, kept inside the window, as tall as its rows are now: a row
        or a line just shown or hidden (a hotkey's problem) counts at once, not only after Qt's next layout pass."""
        for widget in reversed(self.findChildren(QWidget)):
            if widget.layout() is not None:
                widget.layout().activate()
        self.layout().activate()
        self.adjustSize()
        host = self.parentWidget()
        corner = self.anchor.mapTo(host, QPoint(self.anchor.width(), self.anchor.height()))
        x = corner.x() + self._SHADOW - self.width()
        y = corner.y() + self._GAP - (self._SHADOW - self._DROP)
        self.move(max(0, min(x, host.width() - self.width())), max(0, y))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        kind = event.type()
        if watched is self.parentWidget() and kind == QEvent.Type.Resize and self.isVisible():
            self._place()
        elif kind == QEvent.Type.MouseButtonPress and self.isVisible() and isinstance(watched, QWidget):
            # Only a click in this window counts: a dialog this opened is a window of its own.
            inside = watched is self or self.isAncestorOf(watched)
            on_pill = self.anchor is not None and (watched is self.anchor or self.anchor.isAncestorOf(watched))
            if not inside and not on_pill and watched.window() is self.window():
                self.close_panel()
        return False

    def keyPressEvent(self, event) -> None:  # noqa: ANN001
        if event.key() == Qt.Key_Escape:
            self.close_panel()
            if self.anchor is not None:
                self.anchor.setFocus(Qt.OtherFocusReason)
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        # A soft shadow under the card, as under a dialog: rounded layers, each adding a little shade.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 8 if THEME.get("scheme") == "dark" else 4))
        box = QRectF(self.card.geometry())
        steps = 10
        for step in range(steps, 0, -1):
            grow = step * self._SHADOW / steps
            rect = box.adjusted(-grow, -grow + self._DROP, grow, grow + self._DROP)
            painter.drawRoundedRect(rect, CARD_RADIUS + grow, CARD_RADIUS + grow)


def _initial(name: str) -> str:
    name = name.strip()
    return name[:1].upper() if name else ""


class ProfileChip(_KeyboardRing, QAbstractButton):
    """角色名称 with a round initial, and a pen that says a click edits it."""

    _AVATAR = 24
    _PAD_L = 3
    _PAD_R = 10
    _GAP = 8
    _NAME_MAX = 120
    # Everything but the name: the initial, the gaps and the pen.
    _BESIDE = _PAD_L + _AVATAR + _GAP + 6 + 12 + _PAD_R

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("profileChip")
        self.setFocusPolicy(Qt.TabFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFixedHeight(_CHIP_H)
        # It may be narrower than it asks for (minimumSizeHint).
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setAccessibleName("游戏名")
        self._name = ""
        self._hover = False

    def name(self) -> str:
        return self._name

    def set_name(self, name: str) -> None:
        self._name = name.strip()
        self.updateGeometry()
        self.update()

    @staticmethod
    def _font() -> QFont:
        return chinese_font(BODY_PT)

    def _shown(self, room: int | None = None) -> str:
        """The name as it fits in room (at most _NAME_MAX), cut with …; "" when not even its first letter
        and … would."""
        metrics = QFontMetrics(self._font())
        name = self._name or "游戏名"
        room = self._NAME_MAX if room is None else min(room, self._NAME_MAX)
        if room < metrics.horizontalAdvance(name[:1] + "…") and metrics.horizontalAdvance(name) > room:
            return ""
        return metrics.elidedText(name, Qt.ElideRight, room)

    def sizeHint(self) -> QSize:
        text = QFontMetrics(self._font()).horizontalAdvance(self._shown())
        return QSize(self._BESIDE + text, _CHIP_H)

    def minimumSizeHint(self) -> QSize:
        """In a header with no room left (the window at its narrowest, with everything in it), the name gives
        way first, down to the round initial alone."""
        return QSize(self._PAD_L * 2 + self._AVATAR, _CHIP_H)

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
        text = self._shown(self.width() - self._BESIDE)
        if text:
            x = avatar.right() + self._GAP
            painter.setFont(self._font())
            painter.setPen(QColor(THEME["text"] if self._name else THEME["muted"]))
            width = QFontMetrics(self._font()).horizontalAdvance(text)
            painter.drawText(QRectF(x, 0, width + 2, self.height()), Qt.AlignLeft | Qt.AlignVCenter, text)
            painter.drawPixmap(QPoint(round(x + width + 6), round(middle - 6)), line_pixmap("edit", 12, THEME["muted"]))
        if self.show_ring():
            _ring(painter, body)
