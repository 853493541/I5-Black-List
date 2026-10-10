"""The marks drawn over the game: the cover on 准备案件还原, the hit card, and the clear check."""

from __future__ import annotations

import sys

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import (
    QBitmap,
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from blacklist_detect.ui_icons import pixmap as line_pixmap
from blacklist_detect.ui_theme import (
    BODY_PT,
    OVERLAY_PT,
    SMALL_PT,
    chinese_family,
    chinese_font,
)
from blacklist_detect.ui_widgets import (
    TagPill,
    _clear_layout,
)


def native_to_logical(x: float, y: float, screens=None) -> tuple[float, float, float]:  # noqa: ANN001
    """Map a desktop pixel to window coordinates, with the scaling of the monitor it is on.

    Qt keeps each monitor's top-left corner at its pixel position and scales only
    the size, so two monitors at 100% and 150% need different factors.
    """
    listed = list(screens) if screens is not None else QApplication.screens()
    for screen in listed:
        area = screen.geometry()
        ratio = screen.devicePixelRatio() or 1.0
        if area.x() <= x < area.x() + area.width() * ratio and area.y() <= y < area.y() + area.height() * ratio:
            return area.x() + (x - area.x()) / ratio, area.y() + (y - area.y()) / ratio, ratio
    primary = QApplication.primaryScreen()
    ratio = (primary.devicePixelRatio() if primary is not None else 1.0) or 1.0
    return x / ratio, y / ratio, ratio


def _pin_topmost(widget) -> None:
    if sys.platform != "win32":
        return
    import ctypes

    hwnd = int(widget.winId())
    HWND_TOPMOST = -1
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOACTIVATE = 0x0010
    SWP_SHOWWINDOW = 0x0040
    ctypes.windll.user32.SetWindowPos(
        hwnd,
        HWND_TOPMOST,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
    )


_COVER_RING = 4
_COVER_OUTSET = 3

# The marks sit over the game, not over the app, so they keep these colors in 浅色 and 深色:
# dark glass like other game overlays, and a red and a green bright enough for a game scene.
_GLASS = QColor(18, 20, 26, 236)
_GLASS_LINE = QColor(255, 255, 255, 30)
# A dark hairline outside a ring keeps it visible on a light scene and a dark one alike.
_EDGE = QColor(0, 0, 0, 150)
RED = "#f04438"
GREEN = "#17b26a"
_RED_TEXT = "#ff8f87"
_RED_WASH = "#34f04438"  # #AARRGGBB: the red at about a fifth
_INK = "#f5f6f8"


def _fade_in(widget: QWidget, ms: int = 120) -> None:
    """Ease a mark in over the game instead of letting it pop."""
    anim = getattr(widget, "_fade_anim", None)
    if anim is None:
        anim = QPropertyAnimation(widget, b"windowOpacity", widget)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        widget._fade_anim = anim
    anim.stop()
    anim.setDuration(ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    widget.setWindowOpacity(0.0)
    anim.start()


def _cover_radius(height: int) -> int:
    """准备案件还原 is a rounded rectangle, not a pill."""
    return max(4, round(height * 0.14))


class HitCard(QWidget):
    """Who on the blacklist is in this lobby, beside the red ring. It does not cover the button.

    Dark glass, like other game overlays: 「N 人在黑名单里」 in red on top, then each name
    in large white type with its tags. Three names show; more scroll.
    """

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.Window
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.body = QWidget()
        self.body.setObjectName("hitCard")
        self.body.setAttribute(Qt.WA_StyledBackground, True)
        outer.addWidget(self.body)
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(14, 10, 14, 12)
        body_layout.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(6)
        self.icon = QLabel()
        self.icon.setObjectName("hitIcon")
        self.icon.setPixmap(line_pixmap("warning", 16, RED, stroke=1.8))
        head.addWidget(self.icon, 0, Qt.AlignVCenter)
        self.title = QLabel("")
        self.title.setObjectName("hitTitle")
        self.title.setFont(chinese_font(SMALL_PT))
        head.addWidget(self.title, 0, Qt.AlignVCenter)
        head.addStretch(1)
        body_layout.addLayout(head)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("hitScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFocusPolicy(Qt.NoFocus)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.content = QWidget()
        self.content.setObjectName("hitRows")
        self.rows = QVBoxLayout(self.content)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(6)
        self.scroll.setWidget(self.content)
        body_layout.addWidget(self.scroll)
        self._apply_style()

    def set_people(self, people: list[tuple[str, tuple[str, ...]]], height: int) -> None:
        del height  # The card keeps its own size; it is centered on the button beside it.
        self.rows.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        _clear_layout(self.rows)
        self.title.setText(f"{len(people)} 人在黑名单里")
        family = chinese_family()
        name_font = chinese_font(OVERLAY_PT)
        name_font.setWeight(QFont.Weight.DemiBold)
        name_width = 0
        if people:
            metrics = QFontMetrics(name_font)
            name_width = max(metrics.horizontalAdvance(name) for name, _tags in people)
        for name, tags in people:
            person = QWidget()
            person.setStyleSheet("background: transparent;")
            row = QHBoxLayout(person)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            row.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            label = QLabel(name)
            label.setObjectName("hitName")
            label.setFont(name_font)
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            label.setFixedWidth(name_width)
            label.setStyleSheet(
                f'color: {_INK}; background: transparent; font-family: "{family}"; font-size: {OVERLAY_PT}pt; font-weight: 600;'
            )
            row.addWidget(label, 0, Qt.AlignVCenter)
            row.addSpacing(4)
            for tag in tags[:3]:
                pill = TagPill(tag)
                pill.set_colors(_RED_WASH, _RED_TEXT)
                row.addWidget(pill, 0, Qt.AlignVCenter)
            row.addStretch(1)
            self.rows.addWidget(person)
            person.setVisible(True)
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        self.content.setMinimumSize(0, 0)
        self.content.setMaximumSize(16777215, 16777215)
        self.rows.invalidate()
        self.rows.activate()
        count = self.rows.count()
        row_heights = [self.rows.itemAt(i).widget().sizeHint().height() for i in range(count)]
        spacing = self.rows.spacing()
        full = sum(row_heights) + spacing * max(0, count - 1)
        visible_n = min(3, count)
        visible = sum(row_heights[:visible_n]) + spacing * max(0, visible_n - 1)
        content_w = max(self.rows.sizeHint().width(), 1)
        bar = 10 if count > 3 else 0
        self.content.setMinimumSize(content_w, max(full, 1))
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded if count > 3 else Qt.ScrollBarAlwaysOff)
        self.scroll.setFixedSize(content_w + bar, max(visible, 1))
        self.scroll.verticalScrollBar().setValue(0)
        self.body.layout().invalidate()
        self.body.layout().activate()
        self.setFixedSize(self.body.layout().sizeHint())

    def _apply_style(self) -> None:
        family = chinese_family()
        self.setStyleSheet(
            f"""
            QWidget#hitCard {{
                background: rgba({_GLASS.red()}, {_GLASS.green()}, {_GLASS.blue()}, {_GLASS.alpha()});
                border: 1px solid rgba(255, 255, 255, {_GLASS_LINE.alpha()});
                border-radius: 12px;
            }}
            QLabel#hitTitle {{
                color: {_RED_TEXT};
                background: transparent;
                font-family: "{family}";
                font-size: {SMALL_PT}pt;
                font-weight: 600;
            }}
            QLabel#hitIcon {{ background: transparent; }}
            QScrollArea#hitScroll, QScrollArea#hitScroll QWidget {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 2px 0 2px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255, 255, 255, 70);
                border-radius: 3px;
                min-height: 24px;
            }}
            QScrollBar::add-line, QScrollBar::sub-line,
            QScrollBar::add-page, QScrollBar::sub-page {{
                background: transparent;
                height: 0;
                width: 0;
            }}
            """
        )
        self.scroll.viewport().setAutoFillBackground(False)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _pin_topmost(self)
        _fade_in(self)


class ClearMark(QWidget):
    """Green badge with a white check, shown beside a clear accept button."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.Window
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
            | Qt.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.NoFocus)

    def set_size(self, height: int) -> None:
        side = max(16, round(int(height) * 0.6))
        self.setFixedSize(side, side)

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(_EDGE, 1))
        painter.setBrush(QColor(GREEN))
        painter.drawEllipse(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))
        pen = QPen(QColor("#ffffff"), max(2.0, self.height() * 0.07))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        width = float(self.width())
        height = float(self.height())

        def point(x: float, y: float) -> QPointF:
            scale = 0.72
            return QPointF((8 + (x - 8) * scale) / 16 * width, (8 + (y - 8) * scale) / 16 * height)

        painter.drawLine(point(3.2, 8.4), point(6.6, 11.8))
        painter.drawLine(point(6.6, 11.8), point(12.8, 4.5))
        painter.end()

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _pin_topmost(self)
        _fade_in(self)


class LobbyPanel(QWidget):
    """The cover sized to 准备案件还原. It sits on the button, not beside it.

    While a check runs, dark glass hides the button, with a turning arc and 请等待. A hit draws
    a red ring around the button and a clear lobby a green one; the button shows through.
    """

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.Window
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.mode = ""
        self._text = ""
        self._angle = 0.0
        self._spin = QVariantAnimation(self)
        self._spin.setStartValue(0.0)
        self._spin.setEndValue(360.0)
        self._spin.setDuration(900)
        self._spin.setLoopCount(-1)
        self._spin.valueChanged.connect(self._turn)
        self.setFont(chinese_font(BODY_PT))

    def text(self) -> str:
        return self._text

    def spinning(self) -> bool:
        return self._spin.state() == QVariantAnimation.State.Running

    def ring(self) -> str:
        """The ring's color, or "" when there is none."""
        return {"hit": RED, "clear": GREEN}.get(self.mode, "")

    def set_mode(self, mode: str, text: str) -> None:
        self.mode = mode
        self.setToolTip(text)
        self._text = text if mode == "checking" else ""
        if mode == "checking":
            if not self.spinning():
                self._spin.start()
        else:
            self._spin.stop()
        self.update()

    def _turn(self, value) -> None:  # noqa: ANN001
        self._angle = float(value)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        box = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = _cover_radius(self.height())
        if self.mode == "checking":
            # Nearly opaque: the button must not show through while it is being checked.
            painter.setPen(QPen(_GLASS_LINE, 1))
            painter.setBrush(QColor(_GLASS.red(), _GLASS.green(), _GLASS.blue(), 250))
            painter.drawRoundedRect(box, radius, radius)
            self._paint_waiting(painter)
            return
        color = self.ring()
        if not color:
            return
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(_EDGE, 1))
        painter.drawRoundedRect(box, radius, radius)
        inset = 1 + _COVER_RING / 2
        painter.setPen(QPen(QColor(color), _COVER_RING))
        painter.drawRoundedRect(box.adjusted(inset, inset, -inset, -inset), max(1.0, radius - inset), max(1.0, radius - inset))

    def _paint_waiting(self, painter: QPainter) -> None:
        """A turning arc and the words, centered on the cover."""
        face = chinese_font(BODY_PT)
        face.setPixelSize(max(12, min(22, round(self.height() * 0.32))))
        face.setWeight(QFont.Weight.DemiBold)
        painter.setFont(face)
        metrics = QFontMetrics(face)
        words = metrics.horizontalAdvance(self._text) if self._text else 0
        side = metrics.height() * 0.8
        gap = 8 if self._text else 0
        left = (self.width() - (side + gap + words)) / 2
        middle = self.height() / 2
        arc = QRectF(left, middle - side / 2, side, side)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 56), 2.2))
        painter.drawEllipse(arc)
        pen = QPen(QColor(_INK), 2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(arc, round(-self._angle * 16), 100 * 16)
        if self._text:
            painter.setPen(QColor(_INK))
            painter.drawText(QRectF(left + side + gap, 0, words + 2, self.height()), Qt.AlignLeft | Qt.AlignVCenter, self._text)

    def hideEvent(self, event) -> None:  # noqa: ANN001
        super().hideEvent(event)
        self._spin.stop()

    def show_over(self, left: float, top: float, width: float, height: float, mode: str, text: str) -> None:
        width = max(1, int(round(width)))
        height = max(1, int(round(height)))
        # Changing the input flags hides the window; only a cover that was not up yet fades in,
        # so 请等待 turning into the result does not blink.
        appearing = not self.isVisible()
        self.setFixedSize(width, height)
        self.move(int(round(left)), int(round(top)))
        self._apply_input(mode == "clear")
        self.set_mode(mode, text)
        self._mask_pill()
        self.show()
        _pin_topmost(self)
        if appearing:
            _fade_in(self)
        else:
            self.setWindowOpacity(1.0)

    def _apply_input(self, click_through: bool) -> None:
        flags = (
            Qt.FramelessWindowHint
            | Qt.Window
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        if click_through:
            flags |= Qt.WindowTransparentForInput
        self.hide()
        self.clearMask()
        self.setAttribute(Qt.WA_TransparentForMouseEvents, click_through)
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, click_through)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.NoFocus)

    def _mask_pill(self) -> None:
        width = self.width()
        height = self.height()
        if width < 2 or height < 2:
            return
        mask = QBitmap(width, height)
        mask.fill(Qt.color0)
        painter = QPainter(mask)
        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.color1)
        radius = _cover_radius(height)
        painter.drawRoundedRect(0, 0, width, height, radius, radius)
        painter.end()
        self.setMask(mask)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        self._mask_pill()
        _pin_topmost(self)
