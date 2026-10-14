"""The marks drawn over the game: the cover on 准备案件还原, the hit card, and the clear check."""

from __future__ import annotations

import functools
import importlib.util
import sys
from dataclasses import dataclass, replace
from types import ModuleType

from PySide6.QtCore import QEasingCurve, QElapsedTimer, QPointF, QPropertyAnimation, QRect, QRectF, Qt, QTimer, QVariantAnimation
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
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from blacklist_detect import love_scenes
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
    # A mark made only for 直播模式's window is never put on the screen.
    if sys.platform != "win32" or widget.testAttribute(Qt.WA_DontShowOnScreen):
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
# The cover's height round 准备案件还原 on a full-screen game 1080 px high (logical): the cards
# beside it are their own size there, and smaller with a smaller game (a window, a video of it),
# down to CARD_MIN_PT, so they stay in scale with the lobby.
FULL_COVER = 82
CARD_MIN_PT = 9.0
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
# The card beside a red ring: crimson, edged in gold, like the ring.
_CARD = ("#7a1620", "#4e0c13")
_CARD_LINE = "rgba(228, 196, 126, 220)"
_INK = "#fff3e0"
_TAG_WASH = "#2a0a0e"
_TAG_INK = "#ffcf9e"
_FLOWER_TONES = {"pink": ("#fff0f6", "#ff9cc4", "#ff6fa6"), "blue": ("#f2f9ff", "#a8d6ff", "#6fb4ff")}


@dataclass(frozen=True)
class LoveLook:
    """The 心动 marks dressed for the 心动特效 scene that greets them: the ring on 准备案件还原, the
    heart badge beside it and the card of names. Colors are "#rrggbb"; glows are (r, g, b)."""

    glow: tuple[int, int, int]
    # The fine outer rim of the ring and of the badge.
    rim: str
    # The ring's band: at its two ends, and in its middle.
    band: tuple[str, str]
    # The card, top to bottom; its edge (and scroll bar); the names on it.
    card: tuple[str, str]
    edge: str
    ink: str
    # The two flowers of the knots and before the names, each (tip, middle, heart).
    flowers: tuple[tuple[str, str, str], tuple[str, str, str]]
    # The badge, middle to edge, and the heart on it, top to bottom.
    disc: tuple[str, str]
    heart: tuple[str, str]
    # The 心动 half of a ring shared with 黑名单 players, and its glow.
    deep: str
    deep_glow: tuple[int, int, int]
    # The scene that draws the marks itself (its ring, badge, card and lead: see love_scenes), or ""
    # when the look only colors them.
    marks: str = ""


# 经典花边, and wherever no scene says otherwise: pale pink and lavender edged in rose-gold, with
# knots of small pink and blue flowers, like the silk and flowers of its border.
CLASSIC_LOOK = LoveLook(
    glow=(255, 150, 200),
    rim="#f3c1d0",
    band=("#ff9cc4", "#d7c6ff"),
    card=("#fff4f9", "#fadcec"),
    edge="#e8a7bd",
    ink="#8a2d55",
    flowers=(_FLOWER_TONES["pink"], _FLOWER_TONES["blue"]),
    disc=("#fff3f8", "#f7b3cb"),
    heart=("#ff7fb0", "#d92f6b"),
    deep="#c2306b",
    deep_glow=(235, 95, 155),
)
# The scenes that only color the marks. The others (赛博, 天使, 数学 and the rest) draw them as themes
# of their own, in their own LOOK.
LOOKS: dict[str, LoveLook] = {
    "classic": CLASSIC_LOOK,
    # 冰蓝极光: ice and sapphire, the heart blue.
    "ice": LoveLook(
        glow=(110, 190, 255),
        rim="#cfe8ff",
        band=("#7fd0ff", "#b9b0ff"),
        card=("#f4fbff", "#dcefff"),
        edge="#9cc9ec",
        ink="#1f4f7a",
        flowers=(("#f2f9ff", "#a8d6ff", "#5aa8f0"), ("#f6f2ff", "#c9b8ff", "#8f74f0")),
        disc=("#f4fbff", "#b9defb"),
        heart=("#8fd0ff", "#2f6fd9"),
        deep="#2f6fd9",
        deep_glow=(90, 160, 255),
    ),
    # 星河许愿: the night sky, starlight lilac and gold, the heart gold.
    "stars": LoveLook(
        glow=(185, 163, 255),
        rim="#f6d68a",
        band=("#b9a3ff", "#f6d68a"),
        card=("#2e2758", "#1b1838"),
        edge="#c9a95a",
        ink="#f8e7b4",
        flowers=(("#fff8e0", "#f6d68a", "#e0a93a"), ("#f3eeff", "#b9a3ff", "#8a6fe0")),
        disc=("#3a3274", "#1d1a40"),
        heart=("#ffe39a", "#e0a93a"),
        deep="#7a5fe0",
        deep_glow=(150, 120, 255),
    ),
}


def love_look(scene: str) -> LoveLook:
    """The look for a 心动特效 scene, or the one that replaced it (香槟's is 天使's); 经典花边's for
    anything else (随机 not yet settled, 无, a scene that is gone). A scene not in LOOKS brings its own
    (LOOK), and one that draws its marks itself says so (marks)."""
    return _scene_look(love_scenes.shown(scene))


# What a scene module can draw of the marks itself.
_HOOKS = ("ring", "badge", "card", "lead")


@functools.cache
def _scene_look(key: str) -> LoveLook:
    module = _scene(key)
    look = LOOKS.get(key)
    if look is None:
        look = LoveLook(**module.LOOK) if hasattr(module, "LOOK") else CLASSIC_LOOK
    if any(hasattr(module, hook) for hook in _HOOKS):
        look = replace(look, marks=key)
    return look


def _scene(key: str) -> ModuleType | None:
    """The scene module for a key, in SCENES or not; None for a key with none (随机, 无, one that is gone)."""
    if not key.isidentifier() or importlib.util.find_spec(f"{love_scenes.__name__}.{key}") is None:
        return None
    module = love_scenes.load(key)
    return module if hasattr(module, "make") else None


def _theme(look: LoveLook, name: str, default=None):  # noqa: ANN001, ANN202
    """What the scene that draws these marks itself has for name (one of _HOOKS, or CARD_TOP and the
    like), or default: the mark is drawn as the look colors it."""
    return getattr(love_scenes.load(look.marks), name, default) if look.marks else default


class _MarkClock:
    """The moment a mark a scene draws moving (MARKS_ANIMATED) is at: the seconds since it showed,
    with a repaint about 30 times a second while it shows and moves; else 0, or the moment held for a
    still picture of it."""

    def __init__(self, widget: QWidget) -> None:
        self.widget = widget
        self.held: float | None = None
        self._since = QElapsedTimer()
        self._tick = QTimer(widget)
        self._tick.setInterval(33)
        self._tick.timeout.connect(widget.update)

    def t(self) -> float:
        if self.held is not None:
            return self.held
        return self._since.elapsed() / 1000 if self._tick.isActive() else 0.0

    def sync(self, moving: bool) -> None:
        """Run while the mark shows and moves, from 0 each time it starts."""
        if moving and self.held is None and self.widget.isVisible():
            if not self._tick.isActive():
                self._since.start()
                self._tick.start()
        else:
            self._tick.stop()

    def running(self) -> bool:
        return self._tick.isActive()


def _rgba(color: str, alpha: int) -> str:
    shade = QColor(color)
    return f"rgba({shade.red()}, {shade.green()}, {shade.blue()}, {alpha})"


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
    if len(colors) == 3:
        shade = QLinearGradient(box.topLeft(), box.topRight())
        for at, each in zip((0.0, 0.5, 1.0), colors, strict=True):
            shade.setColorAt(at, each)
        return QBrush(shade)
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


def _alpha(color: str | QColor, alpha: float) -> QColor:
    shade = QColor(color)
    shade.setAlphaF(max(0.0, min(1.0, alpha)))
    return shade


def _flower(
    painter: QPainter, x: float, y: float, r: float, tone: str | tuple[str, str, str] = "pink", turn: float = 0.0, halo: float = 2.2
) -> None:
    """Five soft petals, deep at the heart and pale at the tips, in a faint glow of their own.
    tone: "pink", "blue", or (tip, middle, heart)."""
    if r < 0.5:
        return
    light, mid, deep = _FLOWER_TONES[tone] if isinstance(tone, str) else tone
    painter.save()
    painter.translate(x, y)
    painter.rotate(turn)
    painter.setPen(Qt.NoPen)
    if halo > 0:
        glow = QRadialGradient(QPointF(0, 0), r * halo)
        glow.setColorAt(0, _alpha(mid, 0.45))
        glow.setColorAt(1, _alpha(mid, 0))
        painter.setBrush(glow)
        painter.drawEllipse(QPointF(0, 0), r * halo, r * halo)
    for i in range(5):
        painter.save()
        painter.rotate(i * 72)
        petal = QLinearGradient(QPointF(0, 0), QPointF(0, -r * 1.05))
        petal.setColorAt(0, QColor(deep))
        petal.setColorAt(0.55, QColor(mid))
        petal.setColorAt(1, QColor(light))
        painter.setBrush(petal)
        painter.setPen(QPen(_alpha("#ffffff", 0.55), max(0.6, r * 0.05)))
        painter.drawEllipse(QRectF(-r * 0.36, -r * 1.05, r * 0.72, r * 0.82))
        painter.restore()
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#fff6d8"))
    painter.drawEllipse(QPointF(0, 0), r * 0.2, r * 0.2)
    painter.restore()


def _knot(painter: QPainter, x: float, y: float, size: float, halo: float = 2.2, look: LoveLook = CLASSIC_LOOK) -> None:
    """A knot of flowers, overlapping: two of the look's first flower and two of its second (pink
    and blue in 经典花边)."""
    for dx, dy, scale, which, turn in ((-0.55, 0.15, 0.62, 0, 12), (0.5, 0.05, 0.55, 1, 40), (0.0, -0.35, 0.75, 0, 64), (0.1, 0.55, 0.38, 1, 25)):
        _flower(painter, x + dx * size, y + dy * size, scale * size, look.flowers[which], turn, halo)


def _sparkle(painter: QPainter, x: float, y: float, r: float, alpha: float = 1.0) -> None:
    """A four-point glint with a small halo."""
    if alpha <= 0.01 or r < 0.5:
        return
    halo = QRadialGradient(QPointF(x, y), r * 1.6)
    halo.setColorAt(0, QColor(255, 240, 250, round(140 * alpha)))
    halo.setColorAt(1, QColor(255, 200, 230, 0))
    painter.setPen(Qt.NoPen)
    painter.setBrush(halo)
    painter.drawEllipse(QPointF(x, y), r * 1.6, r * 1.6)
    star = QPainterPath(QPointF(x, y - r))
    for px, py in ((r * 0.16, -r * 0.16), (r, 0), (r * 0.16, r * 0.16), (0, r), (-r * 0.16, r * 0.16), (-r, 0), (-r * 0.16, -r * 0.16)):
        star.lineTo(x + px, y + py)
    star.closeSubpath()
    painter.setBrush(_alpha("#ffffff", alpha))
    painter.drawPath(star)


def flower_pixmap(radius: float, tone: str | tuple[str, str, str], ratio: float = 2.0, turn: float | None = None) -> QPixmap:
    """One flower, for the start of a name on the 心动 card. tone as for _flower."""
    side = round(radius * 2.4)
    image = QPixmap(round(side * ratio), round(side * ratio))
    image.setDevicePixelRatio(ratio)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    if turn is None:
        turn = 18 if tone == "pink" else 40
    _flower(painter, side / 2, side / 2 + radius * 0.05, radius, tone, turn, halo=1.15)
    painter.end()
    return image


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

    def set_bottom(self, bottom: str) -> None:
        self._bottom = bottom
        self.update()

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
        """height: the cover's round the button the card is beside; the names are sized to it."""
        self.rows.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        _clear_layout(self.rows)
        family = chinese_family()
        face = self._face()
        point = round(max(CARD_MIN_PT, OVERLAY_PT * min(1.0, height / FULL_COVER)), 1)
        self.scale = point / OVERLAY_PT
        left, top, right, bottom = (round(each * self.scale) for each in self._pad())
        self.body.layout().setContentsMargins(left, top, right, bottom)
        self.rows.setSpacing(max(2, round(4 * self.scale)))
        name_font = chinese_font(point)
        if face is not None:
            # The Chinese face after it, for what the card's own face has no glyph for.
            name_font.setFamilies([face, family])
        name_font.setWeight(QFont.Weight.DemiBold)
        # A face of the card's own is the label's font; the style sheet would put the Chinese one over it.
        font_family = f'font-family: "{family}"; ' if face is None else ""
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
                f"color: {self._NAME_INK}; background: transparent; {font_family}font-size: {point}pt; font-weight: 600;"
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

    def _pad(self) -> tuple[int, int, int, int]:
        """The body's margins round the names at full size: left, top, right, bottom."""
        return (12, 8, 12, 8)

    def _face(self) -> str | None:
        """The names' font family, or None for the app's Chinese face."""
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
    """心动 players in this lobby: a card in the look of the 心动特效 scene (经典花边's pale pink
    edged in rose-gold to begin with), a flower before each name and a knot of flowers on its top
    edge. A scene that draws the card itself (love_scenes: card, lead) puts its own under and before
    the names instead, and may give them its own face.

    set_people gets each player as (what to show, ()): the 昵称, or the full name.
    """

    look = CLASSIC_LOOK
    # Room above the card for the knot on its edge, or for the scene's own ornament (CARD_TOP).
    top = 12

    @property
    def _COLORS(self) -> tuple[str, str]:  # noqa: N802
        return self.look.card

    @property
    def _NAME_INK(self) -> str:  # noqa: N802
        return self.look.ink

    def __init__(self) -> None:
        super().__init__()
        self.body.setObjectName("likeCard")
        self.layout().setContentsMargins(0, self.top, 0, 0)
        self._leads = 0
        self.knot = _CardKnot(self)
        self._clock = _MarkClock(self)
        self._apply_style()

    def set_people(self, people: list[tuple[str, tuple[str, ...]]], height: int) -> None:
        self._leads = 0
        super().set_people(people, height)
        body = self.body.layout().sizeHint()
        self.setFixedSize(body.width(), body.height() + self.top)
        self.knot.move((self.width() - self.knot.width()) // 2, 0)
        self.knot.raise_()

    def set_look(self, look: LoveLook) -> None:
        """Dress the card for a 心动特效 scene. Before set_people: the names take its ink then."""
        if look == self.look:
            return
        self.look = look
        self.top = _theme(look, "CARD_TOP", LikeCard.top)
        self.layout().setContentsMargins(0, self.top, 0, 0)
        self.knot.setVisible(_theme(look, "card") is None)
        self.fade.set_bottom(look.card[1])
        self._apply_style()
        self.knot.update()
        self._clock.sync(self._moving())

    def set_time(self, t: float | None) -> None:
        """Hold a card the scene draws moving at t seconds, for a still picture; None runs it again."""
        self._clock.held = t
        self._clock.sync(self._moving())
        self.update()

    def _moving(self) -> bool:
        return bool(_theme(self.look, "MARKS_ANIMATED", False))

    def _lead(self) -> QWidget | None:
        index = self._leads
        self._leads += 1
        lead = _theme(self.look, "lead")
        if lead is not None:
            picture = lead(18 * getattr(self, "scale", 1.0), index)
            if picture is None:
                return None
            mark = QLabel()
            mark.setObjectName("likeLead")
            mark.setPixmap(picture)
            mark.setStyleSheet("background: transparent;")
            return mark
        # The look's two flowers in turn, "pink" and "blue" in 经典花边.
        which = index % 2
        bloom = QLabel()
        bloom.setObjectName("likeFlower")
        bloom.setProperty("tone", ("pink", "blue")[which])
        ratio = max(2.0, self.devicePixelRatioF())
        bloom.setPixmap(flower_pixmap(7.5 * getattr(self, "scale", 1.0), self.look.flowers[which], ratio, (18, 40)[which]))
        bloom.setStyleSheet("background: transparent;")
        return bloom

    def _apply_style(self) -> None:
        super()._apply_style()
        edge = self.look.edge
        self.setStyleSheet(
            self.styleSheet()
            .replace("QWidget#hitCard", "QWidget#likeCard")
            .replace(f"border: 1px solid {_CARD_LINE};", f"border: 1px solid {edge};")
            .replace("border-radius: 8px;", "border-radius: 10px;", 1)
            .replace("rgba(228, 196, 126, 50)", _rgba(edge, 60))
            .replace("rgba(228, 196, 126, 210)", _rgba(edge, 220))
        )
        if _theme(self.look, "card") is not None:
            # The scene draws the card (paintEvent), and the body is clear over it.
            self.setStyleSheet(self.styleSheet() + "QWidget#likeCard { background: transparent; border: none; }")

    def _pad(self) -> tuple[int, int, int, int]:
        return _theme(self.look, "CARD_PAD", super()._pad())

    def _face(self) -> str | None:
        return _theme(self.look, "CARD_FONT")

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        card = _theme(self.look, "card")
        if card is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        card(painter, QRectF(self.rect()), self._clock.t())
        painter.end()

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        self._clock.sync(self._moving())

    def hideEvent(self, event) -> None:  # noqa: ANN001
        super().hideEvent(event)
        self._clock.sync(False)


class _CardKnot(QWidget):
    """The knot of flowers on the 心动 card's top edge."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFixedSize(40, 28)

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        _knot(painter, self.width() / 2, 12, 10, halo=1.3, look=self.parent().look)
        painter.end()


class ClearMark(QWidget):
    """The check beside a clear accept button: emerald with a gold rim and a soft glow, like the ring.

    With 心动 players in the lobby it is the same badge with a heart, in the look of the 心动特效
    scene (经典花边's pink to begin with), or the scene's own badge (love_scenes: badge).
    """

    # The window reaches this far past the badge on each side, for the glow.
    margin = _GLOW
    # A heart instead of the check, for a lobby with 心动 players.
    heart = False
    look = CLASSIC_LOOK

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
        self._clock = _MarkClock(self)

    def set_heart(self, heart: bool) -> None:
        """A heart instead of the green check: the lobby has 心动 players and no 黑名单."""
        self.heart = bool(heart)
        self._clock.sync(self._moving())
        self.update()

    def set_look(self, look: LoveLook) -> None:
        self.look = look
        self._clock.sync(self._moving())
        self.update()

    def set_time(self, t: float | None) -> None:
        """Hold a badge the scene draws moving at t seconds, for a still picture; None runs it again."""
        self._clock.held = t
        self._clock.sync(self._moving())
        self.update()

    def _moving(self) -> bool:
        return self.heart and bool(_theme(self.look, "MARKS_ANIMATED", False))

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
        if self.heart:
            self._paint_heart(painter, box)
            painter.end()
            return
        _glow(painter, (box, side / 2), _GREEN_GLOW, round_shape=True)
        painter.setPen(QPen(_GOLD, max(1.5, side * 0.06)))
        painter.setBrush(QColor(GREEN))
        painter.drawEllipse(box.adjusted(1, 1, -1, -1))
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

    def _paint_heart(self, painter: QPainter, box: QRectF) -> None:
        """A disc in a fine rim, a heart on it, a glint at its shoulder: in 经典花边, a pale pink
        disc in rose-gold and a deep pink heart."""
        look = self.look
        badge = _theme(look, "badge")
        if badge is not None:
            painter.save()
            badge(painter, box, self._clock.t())
            painter.restore()
            return
        side = box.width()
        center = box.center()
        _glow(painter, (box, side / 2), QColor(*look.glow, 120), round_shape=True)
        fill = QRadialGradient(center, side / 2)
        fill.setColorAt(0, QColor(look.disc[0]))
        fill.setColorAt(1, QColor(look.disc[1]))
        painter.setPen(QPen(QColor(look.rim), max(1.5, side * 0.04)))
        painter.setBrush(fill)
        painter.drawEllipse(box.adjusted(1, 1, -1, -1))
        painter.setPen(QPen(_alpha("#ffffff", 0.7), 1))
        painter.setBrush(Qt.NoBrush)
        inner = max(3.0, side * 0.08)
        painter.drawEllipse(box.adjusted(inner, inner, -inner, -inner))
        heart = QLinearGradient(QPointF(center.x(), center.y() - side * 0.25), QPointF(center.x(), center.y() + side * 0.25))
        heart.setColorAt(0, QColor(look.heart[0]))
        heart.setColorAt(1, QColor(look.heart[1]))
        painter.setPen(Qt.NoPen)
        painter.setBrush(heart)
        painter.drawPath(_heart_path(center.x(), center.y() + side * 0.03, side * 0.48))
        painter.setBrush(_alpha("#ffffff", 0.7))
        painter.drawEllipse(QPointF(center.x() - side * 0.11, center.y() - side * 0.07), side * 0.05, side * 0.035)
        _sparkle(painter, box.right() - side * 0.08, box.top() + side * 0.1, max(3.0, side * 0.09))

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _pin_topmost(self)
        _fade_in(self)
        self._clock.sync(self._moving())

    def hideEvent(self, event) -> None:  # noqa: ANN001
        super().hideEvent(event)
        self._clock.sync(False)


class LobbyPanel(QWidget):
    """The cover sized to 准备案件还原. It sits on the button, not beside it.

    While a check runs, a block of antique gold hides the button, with 检查中 in the middle and
    a glint passing over it now and then. A hit rings the button in crimson and a clear lobby in
    emerald, each edged in gold with a soft glow, like the check mark; the button shows through.
    A clear lobby with 心动 players is ringed in rose; with 黑名单 players too, the ring is rose on the
    left, where their card is, and crimson on the right.
    The window reaches _GLOW past the cover on each side, for that glow. The rose is the look of the
    心动特效 scene (look), 经典花边's to begin with; a scene can draw the 心动 ring itself (love_scenes: ring).
    """

    look = CLASSIC_LOOK

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
        self._clock = _MarkClock(self)
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
        self._clock.sync(self._moving())
        self.update()

    def set_look(self, look: LoveLook) -> None:
        self.look = look
        self._clock.sync(self._moving())
        self.update()

    def set_time(self, t: float | None) -> None:
        """Hold a ring the scene draws moving at t seconds, for a still picture; None runs it again."""
        self._clock.held = t
        self._clock.sync(self._moving())
        self.update()

    def _moving(self) -> bool:
        return self.mode == "liked" and bool(_theme(self.look, "MARKS_ANIMATED", False))

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
        if self.mode == "liked":
            self._paint_liked(painter, cover)
            return
        colors = self.rings()
        if colors:
            glows = {RED: _RED_GLOW, ROSE: QColor(*self.look.deep_glow, 140), GREEN: _GREEN_GLOW}
            shown = {ROSE: self.look.deep}
            _paint_ring(painter, cover, tuple(QColor(shown.get(c, c)) for c in colors), tuple(glows[c] for c in colors))

    def _paint_liked(self, painter: QPainter, cover: QRectF) -> None:
        """心动 and no 黑名单: a glow, a fine rim, a band and flowers on two corners, in the look; in
        经典花边, pink with a rose-gold rim and a pink-lavender band."""
        look = self.look
        ring = _theme(look, "ring")
        if ring is not None:
            painter.save()
            ring(painter, cover, self._clock.t())
            painter.restore()
            return
        radius = _cover_radius(round(cover.height()))
        _glow(painter, (cover, radius), QColor(*look.glow, 120))
        painter.setBrush(Qt.NoBrush)
        ends, middle = QColor(look.band[0]), QColor(look.band[1])
        for inset, pen in (
            (1.1, QPen(QColor(look.rim), 2.2)),
            (4.7, QPen(_across(cover, (ends, middle, ends)), 5)),
            (7.7, QPen(_alpha("#ffffff", 0.6), 1)),
        ):
            painter.setPen(pen)
            painter.drawRoundedRect(cover.adjusted(inset, inset, -inset, -inset), max(1.0, radius - inset), max(1.0, radius - inset))
        # Inside the corners, so the flowers stay within the window.
        size = max(8.0, min(13.0, cover.height() * 0.17))
        _knot(painter, cover.left() + size * 0.7, cover.top() + size * 0.7, size, halo=1.2, look=look)
        _knot(painter, cover.right() - size * 0.7, cover.bottom() - size * 0.7, size, halo=1.2, look=look)

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
        self._clock.sync(False)

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
        elif self.mode == "liked":
            # Square, so the flowers on its corners are not cut off; clicks pass through anyway.
            painter.drawRect(0, 0, width, height)
        else:
            painter.drawRoundedRect(0, 0, width, height, radius + _GLOW, radius + _GLOW)
        painter.end()
        self.setMask(mask)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        self._mask_pill()
        _pin_topmost(self)
        self._clock.sync(self._moving())
