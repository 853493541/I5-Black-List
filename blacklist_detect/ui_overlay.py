"""The marks drawn over the game: the cover on 准备案件还原, the hit card, and the clear check."""

from __future__ import annotations

import sys

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRect, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import (
    QBitmap,
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
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


_COVER_OUTSET = 3
# Room around a mark, inside its window, for its glow.
_GLOW = 9
# A result ring, from the outside in: a gold rim, then the color.
_RIM = 2.4
_BAND = 4.0

# The marks sit over the game, not over the app, so they keep these colors in 浅色 and 深色.
# They come from the game's own look: antique gold like the gold names in the lobby, a deep
# crimson, and an emerald, each edged in the same gold.
_GOLD = QColor("#e4c47e")
_BRASS = ("#e4c47e", "#c9a254", "#a07c36")
_BRASS_INK = QColor("#2b1d08")
_BRASS_LINE = QColor(255, 240, 200, 150)
_EDGE = QColor(0, 0, 0, 150)
RED = "#a8262f"
GREEN = "#2f9e5e"
ROSE = "#c2306b"
_RED_GLOW = QColor(220, 60, 70, 140)
_GREEN_GLOW = QColor(52, 200, 110, 130)
_ROSE_GLOW = QColor(235, 95, 155, 140)
# The badge beside a lobby with 心动 players: the check badge's twin, pink with a heart.
_HEART_FILL = "#d6457f"
# The card beside a red ring: crimson, edged in gold, like the ring.
_CARD = ("#7a1620", "#4e0c13")
_CARD_LINE = "rgba(228, 196, 126, 220)"
_INK = "#fff3e0"
_TAG_WASH = "#2a0a0e"
_TAG_INK = "#ffcf9e"
# The 心动 card: rose, edged in the same gold.
_LIKE_CARD = ("#a3346a", "#6b1c43")
_LIKE_INK = "#fff0f6"
_LIKE_HEART = "#ffb8d2"


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


def _across(box: QRectF, colors: tuple[QColor, ...]) -> QBrush:
    """One color, or two: the first on the left half, the second on the right, blended in the middle."""
    if len(colors) == 1:
        return QBrush(colors[0])
    left, right = colors
    shade = QLinearGradient(box.topLeft(), box.topRight())
    shade.setColorAt(0.0, left)
    shade.setColorAt(0.42, left)
    shade.setColorAt(0.58, right)
    shade.setColorAt(1.0, right)
    return QBrush(shade)


def _glow(painter: QPainter, shape, color: QColor | tuple[QColor, ...], round_shape: bool = False) -> None:  # noqa: ANN001
    """A soft light around a box, fading out over _GLOW; in two colors, split like the ring."""
    box, radius = shape
    colors = color if isinstance(color, tuple) else (color,)
    for step in range(_GLOW - 1, 0, -1):
        shades = []
        for each in colors:
            shade = QColor(each)
            shade.setAlpha(round(each.alpha() * (1 - step / _GLOW) ** 1.6))
            shades.append(shade)
        grown = box.adjusted(-step, -step, step, step)
        if round_shape:
            painter.setPen(Qt.NoPen)
            painter.setBrush(_across(grown, tuple(shades)))
            painter.drawEllipse(grown)
        else:
            painter.setPen(QPen(_across(grown, tuple(shades)), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(grown, radius + step, radius + step)


def _heart_path(cx: float, cy: float, size: float) -> QPainterPath:
    """A heart about size wide, centered on (cx, cy)."""
    u = size / 17.0
    x0, y0 = cx - 8.5 * u, cy - 7.5 * u
    path = QPainterPath(QPointF(x0 + 8.5 * u, y0 + 15 * u))
    path.cubicTo(x0 + 2 * u, y0 + 10.5 * u, x0, y0 + 7 * u, x0, y0 + 4.3 * u)
    path.cubicTo(x0, y0 + 1.7 * u, x0 + 2 * u, y0, x0 + 4.3 * u, y0)
    path.cubicTo(x0 + 6.1 * u, y0, x0 + 7.6 * u, y0 + 1.1 * u, x0 + 8.5 * u, y0 + 2.7 * u)
    path.cubicTo(x0 + 9.4 * u, y0 + 1.1 * u, x0 + 10.9 * u, y0, x0 + 12.7 * u, y0)
    path.cubicTo(x0 + 15 * u, y0, x0 + 17 * u, y0 + 1.7 * u, x0 + 17 * u, y0 + 4.3 * u)
    path.cubicTo(x0 + 17 * u, y0 + 7 * u, x0 + 15 * u, y0 + 10.5 * u, x0 + 8.5 * u, y0 + 15 * u)
    path.closeSubpath()
    return path


def _paint_ring(painter: QPainter, cover: QRectF, color: tuple[QColor, ...], glow: tuple[QColor, ...]) -> None:
    """Like the check mark's edge, and nothing more: the color, a gold rim around it, a glow outside.
    Two colors split the ring down the middle."""
    radius = _cover_radius(round(cover.height()))
    _glow(painter, (cover, radius), glow)
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(_GOLD, _RIM))
    half = _RIM / 2
    painter.drawRoundedRect(cover.adjusted(half, half, -half, -half), radius, radius)
    inset = _RIM + _BAND / 2
    painter.setPen(QPen(_across(cover, color), _BAND))
    painter.drawRoundedRect(cover.adjusted(inset, inset, -inset, -inset), max(1.0, radius - inset), max(1.0, radius - inset))


class _Fade(QWidget):
    """The bottom of a card that scrolls fades out, so the next name shows there is more."""

    def __init__(self, parent: QWidget, bottom: str) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._bottom = bottom

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        fade = QLinearGradient(0, 0, 0, self.height())
        bottom = QColor(self._bottom)
        fade.setColorAt(0.0, QColor(bottom.red(), bottom.green(), bottom.blue(), 0))
        fade.setColorAt(1.0, QColor(bottom.red(), bottom.green(), bottom.blue(), 235))
        painter.fillRect(self.rect(), fade)
        painter.end()


class HitCard(QWidget):
    """Who on the blacklist is in this lobby, beside the red ring. It does not cover the button.

    Crimson edged in gold, like the ring: each name in large type with its tags, and no title,
    since the ring and the tags already say what the names are. Three names show; more scroll.
    """

    margin = 0
    _COLORS = _CARD
    _NAME_INK = _INK

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
        body_layout.setContentsMargins(12, 8, 12, 8)
        body_layout.setSpacing(0)
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
        self.rows.setSpacing(4)
        self.scroll.setWidget(self.content)
        body_layout.addWidget(self.scroll)
        self.fade = _Fade(self.scroll.viewport(), self._COLORS[1])
        self.fade.hide()
        self.scroll.verticalScrollBar().valueChanged.connect(self._sync_fade)
        self.scroll.verticalScrollBar().rangeChanged.connect(self._sync_fade)
        self._apply_style()

    def set_people(self, people: list[tuple[str, tuple[str, ...]]], height: int) -> None:
        del height  # The card keeps its own size; it is centered on the button beside it.
        self.rows.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        _clear_layout(self.rows)
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
                f'color: {self._NAME_INK}; background: transparent; font-family: "{family}"; font-size: {OVERLAY_PT}pt; font-weight: 600;'
            )
            lead = self._lead()
            if lead is not None:
                row.addWidget(lead, 0, Qt.AlignVCenter)
            row.addWidget(label, 0, Qt.AlignVCenter)
            row.addSpacing(8)
            for tag in tags[:3]:
                pill = TagPill(tag)
                pill.set_colors(_TAG_WASH, _TAG_INK)
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
        bar = 9 if count > 3 else 0
        self.content.setMinimumSize(content_w, max(full, 1))
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded if count > 3 else Qt.ScrollBarAlwaysOff)
        self.scroll.setFixedSize(content_w + bar, max(visible, 1))
        self.fade.setGeometry(0, max(visible, 1) - 16, content_w, 16)
        self.scroll.verticalScrollBar().setValue(0)
        self.body.layout().invalidate()
        self.body.layout().activate()
        self.setFixedSize(self.body.layout().sizeHint())
        self._sync_fade()

    def _sync_fade(self, *_args) -> None:  # noqa: ANN002
        """Fade the bottom only while more names wait below."""
        bar = self.scroll.verticalScrollBar()
        self.fade.setVisible(bar.maximum() > 0 and bar.value() < bar.maximum())
        self.fade.raise_()

    def _lead(self) -> QWidget | None:
        """What comes before each name. A hit needs nothing: the card is beside a red ring."""
        return None

    def _apply_style(self) -> None:
        self.setStyleSheet(
            f"""
            QWidget#hitCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {self._COLORS[0]}, stop:1 {self._COLORS[1]});
                border: 1px solid {_CARD_LINE};
                border-radius: 8px;
            }}
            QScrollArea#hitScroll, QWidget#hitRows {{
                background: transparent;
                border: none;
            }}
            QScrollArea#hitScroll QScrollBar:vertical {{
                background: rgba(228, 196, 126, 50);
                width: 3px;
                margin: 0;
                border: none;
                border-radius: 1px;
            }}
            QScrollArea#hitScroll QScrollBar::handle:vertical {{
                background: rgba(228, 196, 126, 210);
                border-radius: 1px;
                min-height: 16px;
            }}
            QScrollArea#hitScroll QScrollBar::add-line, QScrollArea#hitScroll QScrollBar::sub-line,
            QScrollArea#hitScroll QScrollBar::add-page, QScrollArea#hitScroll QScrollBar::sub-page {{
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


class LikeCard(HitCard):
    """心动 players in this lobby: the same card in rose, a heart before each name.

    set_people gets each player as (what to show, ()): the 昵称, or the full name.
    """

    _COLORS = _LIKE_CARD
    _NAME_INK = _LIKE_INK

    def __init__(self) -> None:
        super().__init__()
        self.body.setObjectName("likeCard")
        self._apply_style()

    def _lead(self) -> QWidget | None:
        heart = QLabel()
        heart.setObjectName("likeHeart")
        heart.setPixmap(line_pixmap("heart", 16, _LIKE_HEART, stroke=1.8))
        heart.setStyleSheet("background: transparent;")
        return heart

    def _apply_style(self) -> None:
        super()._apply_style()
        self.setStyleSheet(self.styleSheet().replace("QWidget#hitCard", "QWidget#likeCard"))


class ClearMark(QWidget):
    """The check beside a clear accept button: emerald with a gold rim and a soft glow, like the ring.

    With 心动 players in the lobby it is the same badge in pink, with a heart.
    """

    # The window reaches this far past the badge on each side, for the glow.
    margin = _GLOW
    # A heart instead of the check, for a lobby with 心动 players.
    heart = False

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

    def set_heart(self, heart: bool) -> None:
        """A pink heart instead of the green check: the lobby has 心动 players and no 黑名单."""
        self.heart = bool(heart)
        self.update()

    def set_size(self, height: int) -> None:
        side = max(16, round(int(height) * 0.7))
        self.setFixedSize(side + 2 * _GLOW, side + 2 * _GLOW)

    def badge(self) -> QRectF:
        return QRectF(self.rect()).adjusted(_GLOW, _GLOW, -_GLOW, -_GLOW)

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        box = self.badge()
        side = box.width()
        _glow(painter, (box, side / 2), _ROSE_GLOW if self.heart else _GREEN_GLOW, round_shape=True)
        painter.setPen(QPen(_GOLD, max(1.5, side * 0.06)))
        painter.setBrush(QColor(_HEART_FILL if self.heart else GREEN))
        painter.drawEllipse(box.adjusted(1, 1, -1, -1))
        if self.heart:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#ffffff"))
            painter.drawPath(_heart_path(box.center().x(), box.center().y() + side * 0.03, side * 0.5))
            painter.end()
            return
        pen = QPen(QColor("#ffffff"), max(2.0, side * 0.08))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        tick = QPainterPath()
        tick.moveTo(box.left() + side * 0.28, box.top() + side * 0.52)
        tick.lineTo(box.left() + side * 0.44, box.top() + side * 0.67)
        tick.lineTo(box.left() + side * 0.73, box.top() + side * 0.36)
        painter.drawPath(tick)
        painter.end()

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _pin_topmost(self)
        _fade_in(self)


class LobbyPanel(QWidget):
    """The cover sized to 准备案件还原. It sits on the button, not beside it.

    While a check runs, a block of antique gold hides the button, with 检查中 in the middle and
    a glint passing over it now and then. A hit rings the button in crimson and a clear lobby in
    emerald, each edged in gold with a soft glow, like the check mark; the button shows through.
    A clear lobby with 心动 players is ringed in rose; with 黑名单 players too, the ring is rose on the
    left, where their card is, and crimson on the right.
    The window reaches _GLOW past the cover on each side, for that glow.
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
        self._phase = 0.0
        self._shine = QVariantAnimation(self)
        self._shine.setStartValue(0.0)
        self._shine.setEndValue(1.0)
        self._shine.setDuration(1600)
        self._shine.setLoopCount(-1)
        self._shine.valueChanged.connect(self._glint)
        self.setFont(chinese_font(BODY_PT))

    def text(self) -> str:
        return self._text

    def shining(self) -> bool:
        return self._shine.state() == QVariantAnimation.State.Running

    def ring(self) -> str:
        """The ring's color, or "" when there is none."""
        return (self.rings() or ("",))[-1]

    def rings(self) -> tuple[str, ...]:
        """The ring's colors, left to right: rose then crimson when 心动 and 黑名单 players are both here."""
        return {"hit": (RED,), "clear": (GREEN,), "liked": (ROSE,), "both": (ROSE, RED)}.get(self.mode, ())

    def cover(self) -> QRectF:
        """The cover inside the window: the button and its outset, without the room for the glow."""
        return QRectF(self.rect()).adjusted(_GLOW, _GLOW, -_GLOW, -_GLOW)

    def cover_geometry(self) -> QRect:
        """Where the cover is on the screen."""
        return QRect(self.x() + _GLOW, self.y() + _GLOW, max(1, self.width() - 2 * _GLOW), max(1, self.height() - 2 * _GLOW))

    def set_mode(self, mode: str, text: str) -> None:
        self.mode = mode
        self.setToolTip(text)
        self._text = text if mode == "checking" else ""
        if mode == "checking":
            if not self.shining():
                self._shine.start()
        else:
            self._shine.stop()
            self._phase = 0.0
        self._mask_pill()
        self.update()

    def _glint(self, value) -> None:  # noqa: ANN001
        self._phase = float(value)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        cover = self.cover()
        if self.mode == "checking":
            self._paint_brass(painter, cover)
            return
        colors = self.rings()
        if colors:
            glows = {RED: _RED_GLOW, ROSE: _ROSE_GLOW, GREEN: _GREEN_GLOW}
            _paint_ring(painter, cover, tuple(QColor(c) for c in colors), tuple(glows[c] for c in colors))

    def _paint_brass(self, painter: QPainter, cover: QRectF) -> None:
        """Opaque antique gold: the button must not show through while it is being checked."""
        radius = _cover_radius(round(cover.height()))
        fill = QLinearGradient(cover.topLeft(), cover.bottomLeft())
        fill.setColorAt(0.0, QColor(_BRASS[0]))
        fill.setColorAt(0.5, QColor(_BRASS[1]))
        fill.setColorAt(1.0, QColor(_BRASS[2]))
        painter.setPen(QPen(_EDGE, 1))
        painter.setBrush(fill)
        painter.drawRoundedRect(cover.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(_BRASS_LINE, 1))
        painter.drawRoundedRect(cover.adjusted(3.5, 3.5, -3.5, -3.5), max(1, radius - 3), max(1, radius - 3))
        # A glint crosses the brass in the first part of each turn, then it rests.
        travel = self._phase / 0.65
        if travel <= 1.0:
            x = cover.left() - cover.height() + travel * (cover.width() + cover.height() * 2)
            band = QLinearGradient(QPointF(x - 30, cover.top()), QPointF(x + 30, cover.bottom()))
            band.setColorAt(0.0, QColor(255, 255, 255, 0))
            band.setColorAt(0.5, QColor(255, 250, 230, 120))
            band.setColorAt(1.0, QColor(255, 255, 255, 0))
            shape = QPainterPath()
            shape.addRoundedRect(cover, radius, radius)
            painter.save()
            painter.setClipPath(shape)
            painter.setPen(Qt.NoPen)
            painter.setBrush(band)
            painter.drawRect(cover)
            painter.restore()
        self._paint_words(painter, cover)

    def _paint_words(self, painter: QPainter, cover: QRectF) -> None:
        """The words, dead center on the cover, with nothing beside them to pull them off."""
        if not self._text:
            return
        face = chinese_font(BODY_PT)
        face.setPixelSize(max(12, min(30, round(cover.height() * 0.36))))
        face.setWeight(QFont.Weight.DemiBold)
        # Centered by the ink itself, not the font's box, which carries uneven side bearings.
        outline = QPainterPath()
        outline.addText(0, 0, face, self._text)
        ink = outline.boundingRect()
        middle = cover.center()
        painter.setFont(face)
        painter.setPen(_BRASS_INK)
        painter.drawText(QPointF(middle.x() - ink.center().x(), middle.y() - ink.center().y()), self._text)

    def hideEvent(self, event) -> None:  # noqa: ANN001
        super().hideEvent(event)
        self._shine.stop()

    def show_over(self, left: float, top: float, width: float, height: float, mode: str, text: str) -> None:
        """Cover the box at left, top (the button and its outset), with room around it for the glow."""
        width = max(1, int(round(width)))
        height = max(1, int(round(height)))
        # Changing the input flags hides the window; only a cover that was not up yet fades in,
        # so 检查中 turning into the result does not blink.
        appearing = not self.isVisible()
        self.setFixedSize(width + 2 * _GLOW, height + 2 * _GLOW)
        self.move(int(round(left)) - _GLOW, int(round(top)) - _GLOW)
        # Clear, or clear with 心动 players: a click reaches the button.
        self._apply_input(mode in ("clear", "liked"))
        self.set_mode(mode, text)
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
        """The window's shape: the cover while checking, the cover and its glow for a result."""
        width = self.width()
        height = self.height()
        if width <= 2 * _GLOW + 1 or height <= 2 * _GLOW + 1:
            return
        mask = QBitmap(width, height)
        mask.fill(Qt.color0)
        painter = QPainter(mask)
        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.color1)
        radius = _cover_radius(height - 2 * _GLOW)
        if self.mode == "checking":
            painter.drawRoundedRect(_GLOW, _GLOW, width - 2 * _GLOW, height - 2 * _GLOW, radius, radius)
        else:
            painter.drawRoundedRect(0, 0, width, height, radius + _GLOW, radius + _GLOW)
        painter.end()
        self.setMask(mask)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        self._mask_pill()
        _pin_topmost(self)
