"""安全模式's result: messages at the bottom right of the screen.

Nothing marks the game: no ring round the button, no card beside it. The result comes as a
message in the corner of the screen the game is on, above the taskbar, the way a chat app's
messages come: what the check found, and, on a card of its own above it, the 心动 players. They
wear the colors of the cards beside the button in 完整模式: crimson edged in gold for 黑名单,
pale pink edged in rose-gold with flowers for 心动.

Each message is a plain opaque window (not layered, never faded) that never takes the focus. It
slides up a little as it comes and goes after a few seconds, or on a click. A thin line along its
foot runs down until then, and waits while the pointer is over it.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass

from PySide6.QtCore import QEasingCurve, QElapsedTimer, QObject, QPoint, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPen, QScreen
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from blacklist_detect.ui_icons import pixmap
from blacklist_detect.ui_overlay import _TAG_INK, _TAG_WASH, _alpha, _heart_path, _knot, _pin_topmost, flower_pixmap
from blacklist_detect.ui_theme import BODY_PT, OVERLAY_PT, SECTION_PT, chinese_family, chinese_font
from blacklist_detect.ui_widgets import TagPill

# How long a result stays up.
NOTICE_MS = 8_000
# 检查中 waits for the result, but never forever.
CHECKING_MS = 20_000
# Names listed before the rest are counted.
_MAX_LINES = 5
# From the corner of the screen, and between two messages.
_MARGIN = 20
_GAP = 10
_WIDTH = (300, 440)
# A message rises this far as it comes in; the second one comes a moment after the first.
_RISE = 14
_RISE_MS = 240
_NEXT_MS = 110
_TICK_MS = 40
_BADGE = 30


@dataclass(frozen=True)
class _Look:
    top: str
    bottom: str
    edge: str
    ink: str  # the title and the names
    soft: str  # the lines under them
    accent: str  # the badge's ring, the rule under the title, the line along the foot
    badge: tuple[str, str]
    mark: str  # what the badge shows: warning, heart, check, search, or spin
    mark_ink: str


# The messages sit over the game, so they keep these colors in 浅色 and 深色. 黑名单 and 心动 are
# the cards beside the button; the rest share their gold edge.
_LOOKS = {
    "hit": _Look("#7a1620", "#4e0c13", "#c9a254", "#fff3e0", "#f1cfae", "#e4c47e", ("#d9434f", "#a8262f"), "warning", "#fff3e0"),
    "liked": _Look("#fff4f9", "#fadcec", "#e8a7bd", "#8a2d55", "#b0668a", "#f08ab4", ("#ff9cc4", "#e0558f"), "heart", "#ffffff"),
    "clear": _Look("#1e6843", "#123f29", "#c9a254", "#f0fff5", "#bfe3cb", "#e4c47e", ("#45c07d", "#2f9e5e"), "check", "#ffffff"),
    "checking": _Look("#302a24", "#1c1915", "#a07c36", "#fff3e0", "#d8c8a6", "#e4c47e", ("#3a3129", "#2a231d"), "spin", "#e4c47e"),
    "missing": _Look("#302a24", "#1c1915", "#a07c36", "#fff3e0", "#d8c8a6", "#e4c47e", ("#e4c47e", "#c9a254"), "search", "#2b1d08"),
    "error": _Look("#6a4314", "#3f280a", "#c9a254", "#fff3e0", "#f0d5a6", "#e4c47e", ("#e39b3b", "#b56e15"), "warning", "#fff3e0"),
}


@dataclass(frozen=True)
class Message:
    """One card: its look, a title, the line under it, and the people it lists."""

    kind: str
    title: str
    note: str = ""
    people: tuple[tuple[str, tuple[str, ...]], ...] = ()
    more: int = 0


def _listed(people: list[tuple[str, tuple[str, ...]]]) -> tuple[tuple[tuple[str, tuple[str, ...]], ...], int]:
    """The people a card lists, and how many more there are."""
    shown = people if len(people) <= _MAX_LINES else people[: _MAX_LINES - 1]
    return tuple(shown), len(people) - len(shown)


def result_messages(
    hits: list[tuple[str, tuple[str, ...]]], likes: list[str], unclear: int, blacklist: bool = True
) -> list[Message]:
    """The messages for one checked lobby, the bottom one first: what was found, then 心动. With 提醒's
    黑名单 off (blacklist), a lobby with nobody to tell about is 检查完成, not 未发现黑名单."""
    missed = f"{unclear} 人未识别" if unclear else ""
    if hits:
        shown, more = _listed(hits)
        first = Message("hit", f"发现 {len(hits)} 名黑名单玩家", missed, shown, more)
    else:
        first = Message("clear", "未发现黑名单" if blacklist else "检查完成", missed)
    if not likes:
        return [first]
    shown, more = _listed([(name, ()) for name in likes])
    return [first, Message("liked", f"发现 {len(likes)} 名心动玩家", "", shown, more)]


def _round_corners(widget: QWidget, edge: str) -> None:
    """Windows 11 rounds the plain window itself and draws its edge in the card's color; older
    Windows keeps square corners and the edge the card paints."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWA_BORDER_COLOR = 34
        DWMWCP_ROUND = 2
        hwnd = int(widget.winId())
        value = ctypes.c_int(DWMWCP_ROUND)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(value), ctypes.sizeof(value))
        color = QColor(edge)
        ref = ctypes.c_uint32(color.red() | color.green() << 8 | color.blue() << 16)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_BORDER_COLOR, ctypes.byref(ref), ctypes.sizeof(ref))
    except Exception:
        pass


class _Badge(QWidget):
    """The round mark at the start of a message: what kind of news it is, at a glance."""

    def __init__(self, card: _Card) -> None:
        super().__init__(card)
        self._card = card
        self.setFixedSize(_BADGE, _BADGE)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        look = self._card.look
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        ring = QRectF(1, 1, _BADGE - 2, _BADGE - 2)
        middle = ring.center()
        if look.mark == "spin":
            track = ring.adjusted(5, 5, -5, -5)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(_alpha(look.accent, 0.22), 2.6))
            painter.drawEllipse(track)
            arc = QPen(QColor(look.accent), 2.6)
            arc.setCapStyle(Qt.RoundCap)
            painter.setPen(arc)
            painter.drawArc(track, round(-math.degrees(self._card.spin) * 16), 100 * 16)
            painter.end()
            return
        fill = QLinearGradient(ring.topLeft(), ring.bottomLeft())
        fill.setColorAt(0, QColor(look.badge[0]))
        fill.setColorAt(1, QColor(look.badge[1]))
        painter.setBrush(fill)
        painter.setPen(QPen(_alpha(look.accent, 0.9), 1.2))
        painter.drawEllipse(ring)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(look.mark_ink))
        if look.mark == "warning":
            painter.drawRoundedRect(QRectF(middle.x() - 1.5, middle.y() - 8, 3, 10.5), 1.5, 1.5)
            painter.drawEllipse(QPointF(middle.x(), middle.y() + 6.5), 1.8, 1.8)
        elif look.mark == "heart":
            painter.drawPath(_heart_path(middle.x(), middle.y() + 0.6, 15))
        else:
            size = 18 if look.mark == "check" else 16
            mark = pixmap(look.mark, size, look.mark_ink, max(2.0, self.devicePixelRatioF()), stroke=2.2)
            painter.drawPixmap(QPointF(middle.x() - size / 2, middle.y() - size / 2), mark)
        painter.end()


class _Card(QWidget):
    """One message: a badge, a title and a line under it, then the people, on a block of color."""

    clicked = Signal()
    hovered = Signal(bool)

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
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.kind = ""
        self.look = _LOOKS["checking"]
        # How much of the line along the foot is left, 1 to 0; None while there is no line.
        self.left: float | None = None
        self.spin = 0.0
        self._family = chinese_family()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 18, 16)
        outer.setSpacing(0)
        self._head = QHBoxLayout()
        self._head.setSpacing(12)
        self.badge = _Badge(self)
        self._head.addWidget(self.badge, 0, Qt.AlignTop)
        words = QVBoxLayout()
        words.setContentsMargins(0, 0, 0, 0)
        words.setSpacing(1)
        self.title = QLabel("")
        title_font = chinese_font(SECTION_PT)
        title_font.setWeight(QFont.Weight.DemiBold)
        self.title.setFont(title_font)
        self.title.setMinimumHeight(_BADGE)
        self.title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        words.addWidget(self.title)
        self.note = QLabel("")
        self.note.setFont(chinese_font(BODY_PT))
        self.note.setTextFormat(Qt.PlainText)
        self.note.setWordWrap(True)
        words.addWidget(self.note)
        self._head.addLayout(words, 1)
        outer.addLayout(self._head)
        # The people line up under the title, below a thin rule.
        self.list = QWidget()
        self._rows = QVBoxLayout(self.list)
        self._rows.setContentsMargins(_BADGE + 12, 12, 0, 0)
        self._rows.setSpacing(6)
        outer.addWidget(self.list)
        for each in (self.title, self.note, self.list):
            each.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def set_message(self, message: Message) -> None:
        self.kind = message.kind
        self.look = _LOOKS.get(message.kind, _LOOKS["missing"])
        look = self.look
        self.title.setText(message.title)
        self.title.setStyleSheet(f'color: {look.ink}; background: transparent; font-family: "{self._family}";')
        self.note.setText(message.note)
        self.note.setStyleSheet(f'color: {look.soft}; background: transparent; font-family: "{self._family}";')
        self.note.setVisible(bool(message.note))
        # 心动 keeps room at the top right for its knot of flowers.
        self._head.setContentsMargins(0, 0, 30 if message.kind == "liked" else 0, 0)
        while self._rows.count():
            item = self._rows.takeAt(0)
            if item.widget() is not None:
                # Hidden now: deleteLater alone leaves the old names painted under the new ones.
                item.widget().hide()
                item.widget().deleteLater()
        self.list.setVisible(bool(message.people))
        if message.people:
            self._fill(message)
        self.layout().invalidate()
        self.layout().activate()
        self.update()

    def _fill(self, message: Message) -> None:
        look = self.look
        name_font = chinese_font(OVERLAY_PT)
        name_font.setWeight(QFont.Weight.DemiBold)
        # The tags start in one column, after the longest name.
        name_width = max(QFontMetrics(name_font).horizontalAdvance(name) for name, _tags in message.people)
        for index, (name, tags) in enumerate(message.people):
            person = QWidget()
            row = QHBoxLayout(person)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            if message.kind == "liked":
                tone = "pink" if index % 2 == 0 else "blue"
                bloom = QLabel()
                bloom.setPixmap(flower_pixmap(7.5, tone, max(2.0, self.devicePixelRatioF())))
                bloom.setStyleSheet("background: transparent;")
                row.addWidget(bloom, 0, Qt.AlignVCenter)
            label = QLabel(name)
            label.setObjectName("noticeName")
            label.setFont(name_font)
            label.setFixedWidth(name_width + 2)
            label.setStyleSheet(
                f'color: {look.ink}; background: transparent; font-family: "{self._family}"; font-size: {OVERLAY_PT}pt; font-weight: 600;'
            )
            row.addWidget(label, 0, Qt.AlignVCenter)
            if tags:
                row.addSpacing(6)
            for tag in tags[:3]:
                pill = TagPill(tag)
                pill.set_colors(_TAG_WASH, _TAG_INK)
                row.addWidget(pill, 0, Qt.AlignVCenter)
            row.addStretch(1)
            for each in person.findChildren(QWidget):
                each.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            person.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self._rows.addWidget(person)
            # Shown now: on a card already up (检查中), a new row waits to be shown, and the
            # card's height is worked out without it.
            person.show()
        if message.more:
            rest = QLabel(f"还有 {message.more} 人")
            rest.setFont(chinese_font(BODY_PT))
            rest.setStyleSheet(f'color: {look.soft}; background: transparent; font-family: "{self._family}";')
            rest.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self._rows.addWidget(rest)
            rest.show()

    def names(self) -> list[str]:
        return [label.text() for label in self.list.findChildren(QLabel, "noticeName")]

    def natural_width(self) -> int:
        return self.layout().sizeHint().width()

    def fit(self, width: int) -> None:
        self.setFixedWidth(width)
        # A card used before keeps the sizes its rows had then, until they are worked out again:
        # without this, two 心动 names after one were cut to the height of one.
        self.list.layout().invalidate()
        self.list.updateGeometry()
        layout = self.layout()
        layout.invalidate()
        layout.activate()
        height = layout.totalHeightForWidth(width) if layout.hasHeightForWidth() else layout.sizeHint().height()
        self.setFixedHeight(max(height, layout.sizeHint().height(), layout.minimumSize().height()))

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        look = self.look
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        box = QRectF(self.rect())
        fill = QLinearGradient(box.topLeft(), box.bottomLeft())
        fill.setColorAt(0, QColor(look.top))
        fill.setColorAt(1, QColor(look.bottom))
        painter.fillRect(box, fill)
        # A faint sheen along the top, like the light on silk or lacquer.
        painter.setPen(QPen(_alpha("#ffffff", 0.16 if look.top.startswith("#f") else 0.09), 1))
        painter.drawLine(QPointF(1, 1.5), QPointF(box.width() - 1, 1.5))
        if self.list.isVisible():
            y = self.list.y() + 5.5
            x = self.list.x() + _BADGE + 12
            painter.setPen(QPen(_alpha(look.accent, 0.38), 1))
            painter.drawLine(QPointF(x, y), QPointF(box.width() - 18, y))
        if self.kind == "liked":
            _knot(painter, box.width() - 26, 22, 9, halo=1.3)
        if self.left is not None:
            y = box.height() - 5
            start, end = 14.0, box.width() - 14
            line = QPen(_alpha(look.accent, 0.16), 2)
            line.setCapStyle(Qt.RoundCap)
            painter.setPen(line)
            painter.drawLine(QPointF(start, y), QPointF(end, y))
            if self.left > 0:
                line.setColor(_alpha(look.accent, 0.85))
                painter.setPen(line)
                painter.drawLine(QPointF(start, y), QPointF(start + (end - start) * self.left, y))
        # The edge, for Windows that does not draw one round the window itself.
        painter.setPen(QPen(QColor(look.edge), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(box.adjusted(0.5, 0.5, -0.5, -0.5))
        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        event.accept()
        self.clicked.emit()

    def enterEvent(self, event) -> None:  # noqa: ANN001
        super().enterEvent(event)
        self.hovered.emit(True)

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        super().leaveEvent(event)
        self.hovered.emit(False)


class CornerNotice(QObject):
    """The messages at the bottom right: the result, and above it, on its own card, 心动."""

    def __init__(self) -> None:
        super().__init__()
        self.main = _Card()
        self.likes = _Card()
        self.kind = ""
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self._clock = QElapsedTimer()
        self._total = 1
        self._left_ms = 0
        self._paused = False
        self._tick = QTimer(self)
        self._tick.setInterval(_TICK_MS)
        self._tick.timeout.connect(self._step)
        # The second message comes a moment after the first.
        self._next = QTimer(self)
        self._next.setSingleShot(True)
        self._next.timeout.connect(self._enter_next)
        self._waiting: tuple[_Card, QPoint] | None = None
        self._rises: dict[int, QPropertyAnimation] = {}
        for card in self.cards():
            card.clicked.connect(self.hide)
            card.hovered.connect(self._hover)

    def cards(self) -> tuple[_Card, _Card]:
        return self.main, self.likes

    def isVisible(self) -> bool:  # noqa: N802 - reads like the window it stands for
        return self.main.isVisible()

    def show_messages(self, kind: str, messages: list[Message], screen: QScreen | None, ms: int = NOTICE_MS) -> None:
        self.kind = kind
        self._next.stop()
        self._waiting = None
        screen = screen or QApplication.primaryScreen()
        cards = self.cards()[: len(messages)]
        for card, message in zip(cards, messages, strict=False):
            card.set_message(message)
            card.left = None if message.kind == "checking" else 1.0
        width = min(max(max(card.natural_width() for card in cards), _WIDTH[0]), _WIDTH[1])
        area = screen.availableGeometry() if screen is not None else None
        right = (area.right() + 1 if area is not None else width + _MARGIN) - _MARGIN
        bottom = (area.bottom() + 1 if area is not None else 400) - _MARGIN
        for order, card in enumerate(cards):
            card.fit(width)
            spot = QPoint(right - width, bottom - card.height())
            bottom = spot.y() - _GAP
            if card.isVisible():
                # Already up, as 检查中: the result takes its place where it is.
                self._stop_rise(card)
                card.move(spot)
                card.update()
                _round_corners(card, card.look.edge)
                _pin_topmost(card)
            elif order == 0:
                self._enter(card, spot)
            else:
                self._waiting = (card, spot)
                self._next.start(_NEXT_MS)
        for card in self.cards()[len(messages) :]:
            self._stop_rise(card)
            card.hide()
        self._total = ms
        self._left_ms = ms
        self._resume()

    def _enter(self, card: _Card, spot: QPoint) -> None:
        """Show a card a little below its place and let it rise into it. The one above rises less,
        so it never comes over the one under it."""
        self._stop_rise(card)
        start = spot + QPoint(0, _RISE if card is self.main else _GAP - 2)
        card.move(start)
        card.show()
        _round_corners(card, card.look.edge)
        _pin_topmost(card)
        rise = QPropertyAnimation(card, b"pos", self)
        rise.setDuration(_RISE_MS)
        rise.setEasingCurve(QEasingCurve.Type.OutCubic)
        rise.setStartValue(start)
        rise.setEndValue(spot)
        self._rises[id(card)] = rise
        rise.start()

    def _enter_next(self) -> None:
        if self._waiting is not None and self.main.isVisible():
            self._enter(*self._waiting)
        self._waiting = None

    def _stop_rise(self, card: _Card) -> None:
        rise = self._rises.pop(id(card), None)
        if rise is not None:
            rise.stop()

    def _remaining(self) -> int:
        if self._paused:
            return self._left_ms
        return max(0, self._left_ms - self._clock.elapsed())

    def _resume(self) -> None:
        self._paused = False
        self._clock.start()
        self._timer.start(max(1, self._left_ms))
        self._tick.start()

    def _hover(self, inside: bool) -> None:
        """The pointer over a message holds them both until it leaves."""
        if not self.main.isVisible():
            return
        if inside and not self._paused:
            self._left_ms = self._remaining()
            self._paused = True
            self._timer.stop()
        elif not inside and self._paused:
            self._resume()

    def _step(self) -> None:
        if not self.main.isVisible():
            self._tick.stop()
            return
        left = self._remaining() / max(1, self._total)
        for card in self.cards():
            if not card.isVisible():
                continue
            if card.left is not None:
                card.left = left
            if card.look.mark == "spin":
                card.spin += 0.32
            card.update()

    def show_checking(self, screen: QScreen | None) -> None:
        self.show_messages("checking", [Message("checking", "检查中…")], screen, CHECKING_MS)

    def show_result(
        self,
        hits: list[tuple[str, tuple[str, ...]]],
        likes: list[str],
        unclear: int,
        screen: QScreen | None,
        blacklist: bool = True,
    ) -> None:
        messages = result_messages(hits, likes, unclear, blacklist)
        kind = "hit" if hits else ("liked" if likes else "clear")
        self.show_messages(kind, messages, screen)

    def show_missing(self, screen: QScreen | None) -> None:
        self.show_messages("missing", [Message("missing", "没有找到大厅", "进了「推演成功」大厅再按")], screen)

    def show_error(self, detail: str, screen: QScreen | None) -> None:
        self.show_messages("error", [Message("error", "检查失败", detail)], screen)

    def hide(self) -> None:
        self._timer.stop()
        self._tick.stop()
        self._next.stop()
        self._waiting = None
        self._paused = False
        for card in self.cards():
            self._stop_rise(card)
            card.hide()

    def close(self) -> None:
        self.hide()
        for card in self.cards():
            card.close()
