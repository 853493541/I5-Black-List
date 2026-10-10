"""Standard controls built on the theme tokens: switch, segmented control, icon
button, toast, confirm dialog, empty state, and the settings section card.

Each one reads its colors from THEME and its sizes from ui_theme, so it follows
浅色/深色 and the accent without its own stylesheet values.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from blacklist_detect.ui_icons import icon as line_icon
from blacklist_detect.ui_icons import pixmap as line_pixmap
from blacklist_detect.ui_theme import (
    BODY_PT,
    CONTROL_H,
    DIALOG_PAD,
    DIALOG_TITLE_PT,
    KEYBOARD_FOCUS,
    SECTION_PT,
    SMALL_PT,
    THEME,
    _dialog_style,
    _mix,
    _pointing,
    chinese_family,
    chinese_font,
)


def activates(event) -> bool:  # noqa: ANN001
    """Space or Enter presses a focused control, as on a button."""
    return event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter) and not event.modifiers() & ~Qt.KeypadModifier


class _KeyboardRing:
    """Shows a focus ring only when focus came from the keyboard, the way Windows does,
    so a click or the window opening never leaves a ring behind.
    """

    _ring = False

    def focusInEvent(self, event) -> None:  # noqa: ANN001
        self._ring = event.reason() in KEYBOARD_FOCUS
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event) -> None:  # noqa: ANN001
        self._ring = False
        super().focusOutEvent(event)
        self.update()

    def show_ring(self) -> bool:
        return self._ring and self.hasFocus()


class Switch(_KeyboardRing, QAbstractButton):
    """An on/off switch for a setting that takes effect at once. With text, the words sit
    on its left and clicking them toggles it too.
    """

    _W = 40
    _H = 22
    _TEXT_GAP = 8

    def __init__(self, checked: bool = False, parent: QWidget | None = None, *, text: str = "") -> None:
        super().__init__(parent)
        self.setText(text)
        if text:
            self.setAccessibleName(text)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._pos = 1.0 if checked else 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._set_pos)
        self.toggled.connect(self._slide)

    def _text_width(self) -> int:
        if not self.text():
            return 0
        return QFontMetrics(chinese_font(BODY_PT)).horizontalAdvance(self.text()) + self._TEXT_GAP

    def sizeHint(self) -> QSize:
        return QSize(self._text_width() + self._W + 4, self._H + 4)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def hitButton(self, pos) -> bool:  # noqa: ANN001
        return self.rect().contains(pos)

    def _set_pos(self, value: float) -> None:
        self._pos = float(value)
        self.update()

    def _slide(self, on: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        left = self._text_width()
        top = (self.height() - self._H) / 2
        if left:
            painter.setFont(chinese_font(BODY_PT))
            painter.setPen(QColor(THEME["text"] if self.isEnabled() else THEME["muted"]))
            painter.drawText(QRectF(0, 0, left, self.height()), Qt.AlignLeft | Qt.AlignVCenter, self.text())
        track = QRectF(left + 2, top, self._W, self._H)
        off = THEME["chip_off_line"]
        on = THEME["accent_line"] if THEME.get("scheme") == "dark" else THEME["accent"]
        color = _mix(off, on, self._pos)
        if not self.isEnabled():
            color = QColor(THEME["border"])
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(track, self._H / 2, self._H / 2)
        knob = self._H - 6
        x = track.left() + 3 + self._pos * (self._W - knob - 6)
        # Dark mode puts a dark knob on the bright track, as Windows 11 does, so it stays visible.
        dark_on = THEME.get("scheme") == "dark" and self.isEnabled()
        painter.setBrush(_mix("#ffffff", THEME["on_accent"], self._pos) if dark_on else QColor("#ffffff"))
        painter.drawEllipse(QRectF(x, track.top() + 3, knob, knob))
        if self.show_ring():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(THEME["accent_line"]), 1.5))
            painter.drawRoundedRect(track.adjusted(-1.5, -1.5, 1.5, 1.5), self._H / 2 + 1.5, self._H / 2 + 1.5)


class TabButton(_KeyboardRing, QPushButton):
    """One page tab: its name, a count badge when there is something to count, and an
    accent underline while it is the open page. Painted here so all of it follows the theme.
    """

    _PAD = 12
    _HEIGHT = 36
    _BADGE_H = 18

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("tabButton")
        self.setCheckable(True)
        self.setFocusPolicy(Qt.TabFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self._name = name
        self._count = 0
        self.setAccessibleName(name)
        self.setFixedHeight(self._HEIGHT)

    def name(self) -> str:
        return self._name

    def count(self) -> int:
        return self._count

    def set_name(self, name: str) -> None:
        if name != self._name:
            self._name = name
            self.setAccessibleName(name)
            self.updateGeometry()
            self.update()

    def set_count(self, count: int) -> None:
        if count != self._count:
            self._count = max(0, int(count))
            self.updateGeometry()
            self.update()

    @staticmethod
    def _label_font(bold: bool) -> QFont:
        font = chinese_font(BODY_PT)
        if bold:
            font.setWeight(QFont.Weight.DemiBold)
        return font

    def _badge_text(self) -> str:
        return "99+" if self._count > 99 else str(self._count)

    def _badge_width(self) -> int:
        if not self._count:
            return 0
        metrics = QFontMetrics(chinese_font(SMALL_PT))
        return max(self._BADGE_H, metrics.horizontalAdvance(self._badge_text()) + 10)

    def sizeHint(self) -> QSize:
        # Measure bold, so the label never clips when this becomes the open page.
        metrics = QFontMetrics(self._label_font(True))
        width = metrics.horizontalAdvance(self._name) + self._PAD * 2
        if self._count:
            width += 6 + self._badge_width()
        return QSize(width, self._HEIGHT)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def enterEvent(self, event) -> None:  # noqa: ANN001
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        dark = THEME.get("scheme") == "dark"
        accent = THEME["accent_line"] if dark else THEME["accent"]
        if self.isChecked():
            ink = accent
        elif self.underMouse():
            ink = THEME["text"]
        else:
            ink = THEME["muted"]
        font = self._label_font(self.isChecked())
        painter.setFont(font)
        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(self._name)
        middle = (self.height() - 2) / 2
        painter.setPen(QColor(ink))
        painter.drawText(QRectF(self._PAD, 0, text_width + 2, self.height() - 2), Qt.AlignLeft | Qt.AlignVCenter, self._name)
        right = self._PAD + text_width
        if self._count:
            badge_w = self._badge_width()
            badge = QRectF(right + 6, middle - self._BADGE_H / 2, badge_w, self._BADGE_H)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(THEME["accent_wash"] if self.isChecked() else THEME["chip_bg"]))
            painter.drawRoundedRect(badge, self._BADGE_H / 2, self._BADGE_H / 2)
            painter.setFont(chinese_font(SMALL_PT))
            painter.setPen(QColor(accent if self.isChecked() else THEME["muted"]))
            painter.drawText(badge, Qt.AlignCenter, self._badge_text())
            right = badge.right()
        if self.isChecked():
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(accent))
            painter.drawRoundedRect(QRectF(self._PAD - 2, self.height() - 2.5, right - self._PAD + 4, 2.5), 1.2, 1.2)
        if self.show_ring():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(THEME["accent_line"]), 1.2))
            painter.drawRoundedRect(QRectF(2, 3, self.width() - 4, self.height() - 8), 5, 5)


class SegmentedControl(QWidget):
    """A row of joined buttons where exactly one is chosen, like 浅色 / 深色 / 跟随系统."""

    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]], current: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}
        for index, (key, label) in enumerate(options):
            button = QPushButton(label)
            button.setObjectName("segment")
            place = "only" if len(options) == 1 else "first" if index == 0 else "last" if index == len(options) - 1 else "middle"
            button.setProperty("place", place)
            button.setCheckable(True)
            button.setChecked(key == current)
            button.setAutoDefault(False)
            button.setCursor(Qt.PointingHandCursor)
            button.pressed.connect(self._remember)
            button.clicked.connect(self._on_click)
            button.setProperty("key", key)
            self._group.addButton(button)
            self.buttons[key] = button
            row.addWidget(button)
        self._before = current

    def _remember(self) -> None:
        # The choice as it stood when the press began, however it was set.
        self._before = self.current()

    def _on_click(self) -> None:
        button = self.sender()
        key = str(button.property("key")) if button is not None else ""
        if key and key != self._before:
            self._before = key
            self.changed.emit(key)

    def current(self) -> str:
        checked = self._group.checkedButton()
        return str(checked.property("key")) if checked is not None else ""

    def set_current(self, key: str) -> None:
        for name, button in self.buttons.items():
            button.setChecked(name == key)


class IconButton(QPushButton):
    """A square button that shows only an icon. The tooltip names what it does."""

    def __init__(self, name: str, tip: str, parent: QWidget | None = None, *, tone: str = "muted") -> None:
        super().__init__(parent)
        self.setObjectName("iconButton")
        self._name = name
        self._tone = tone
        self.setToolTip(tip)
        self.setAccessibleName(tip)
        self.setCursor(Qt.PointingHandCursor)
        self.setAutoDefault(False)
        self.setFixedSize(CONTROL_H - 4, CONTROL_H - 4)
        self.setIconSize(QSize(16, 16))
        self.refresh()

    def refresh(self) -> None:
        """Redraw the icon in the current theme's colors."""
        self.setIcon(line_icon(self._name, 16, THEME[self._tone]))


class Toast(QWidget):
    """A short message at the bottom of a window, with an optional action such as 撤销.

    It never takes the focus and disappears on its own.
    """

    def __init__(self, host: QWidget) -> None:
        super().__init__(host)
        self.setObjectName("toast")
        self.setAttribute(Qt.WA_StyledBackground, True)
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 8, 10, 8)
        row.setSpacing(12)
        self.text = QLabel("")
        self.text.setObjectName("toastText")
        self.text.setFont(chinese_font(BODY_PT))
        row.addWidget(self.text)
        self.action = QPushButton("")
        self.action.setObjectName("toastAction")
        self.action.setCursor(Qt.PointingHandCursor)
        self.action.setAutoDefault(False)
        self.action.setFocusPolicy(Qt.NoFocus)
        self.action.clicked.connect(self._act)
        row.addWidget(self.action)
        self._callback: Callable[[], None] | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)
        self._fade = QGraphicsOpacityEffect(self)
        self._fade.setOpacity(1.0)
        self.setGraphicsEffect(self._fade)
        self._anim = QPropertyAnimation(self._fade, b"opacity", self)
        self._anim.setDuration(150)
        self._anim.finished.connect(self._after_fade)
        self._hiding = False
        host.installEventFilter(self)
        self.hide()

    def show_message(self, text: str, action: str = "", on_action: Callable[[], None] | None = None, ms: int = 4000) -> None:
        self.text.setText(text)
        self._callback = on_action if action else None
        self.action.setText(action)
        self.action.setVisible(bool(action))
        self.adjustSize()
        self._place()
        self._hiding = False
        self._anim.stop()
        self._fade.setOpacity(0.0)
        self.show()
        self.raise_()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._timer.start(ms)

    def dismiss(self) -> None:
        if not self.isVisible():
            return
        self._timer.stop()
        # 撤销 keeps working while the toast fades; the action is dropped once it is gone.
        self._hiding = True
        self._anim.stop()
        self._anim.setStartValue(self._fade.opacity())
        self._anim.setEndValue(0.0)
        self._anim.start()

    def _after_fade(self) -> None:
        if self._hiding:
            self.hide()
            self._hiding = False
            self._callback = None

    def _act(self) -> None:
        callback = self._callback
        self._timer.stop()
        self._callback = None
        self.hide()
        if callback is not None:
            callback()

    def _place(self) -> None:
        host = self.parentWidget()
        if host is None:
            return
        width = min(self.sizeHint().width(), max(200, host.width() - 48))
        self.resize(width, self.sizeHint().height())
        # Float clear of the page's bottom edge rather than sitting on a card's border.
        self.move((host.width() - width) // 2, host.height() - self.height() - 40)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize and self.isVisible():
            self._place()
        return False


class Modal(QDialog):
    """A dialog drawn as a card over its dimmed window, the way Windows 11 apps show one.

    There is no Windows title bar: the title and a × share the card's first row, so the
    title is said once. The dialog's own window covers its parent's and paints the dimming,
    so a click anywhere outside the card closes it, as on the web. When closing would throw
    away something typed or picked (has_changes), that click only gives the card a short
    shake instead; × and Esc always close.
    """

    # Room around the card for its shadow, which falls a little downward.
    _SHADOW = 22
    _DROP = 6
    RADIUS = 12

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.Dialog | Qt.FramelessWindowHint)
        self.setObjectName("modal")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.card: QFrame | None = None
        # The window this one covers and dims while open, or None when it stands alone.
        self.host: QWidget | None = None
        self._shake: QVariantAnimation | None = None
        self._shake_from = QPoint()

    def frame(self, title: str) -> QVBoxLayout:
        """Build the card and its title row. Returns the layout the dialog's content goes in."""
        self.setWindowTitle(title)
        self.setFont(chinese_font())
        self.setStyleSheet(_dialog_style(chinese_family()))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(self._SHADOW, self._SHADOW - self._DROP, self._SHADOW, self._SHADOW + self._DROP)
        self.card = QFrame()
        self.card.setObjectName("dialogCard")
        # The card keeps its own size in the middle; the rest of the window is the dimming.
        outer.addStretch(1)
        middle = QHBoxLayout()
        middle.addStretch(1)
        middle.addWidget(self.card)
        middle.addStretch(1)
        outer.addLayout(middle)
        outer.addStretch(1)
        column = QVBoxLayout(self.card)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        top = QWidget()
        column.addWidget(top)
        inner = QVBoxLayout(top)
        # The × sits near the corner; the content below keeps the full padding.
        corner = 12
        inner.setContentsMargins(DIALOG_PAD, 18, corner, DIALOG_PAD)
        # Space says what belongs together: more between the title and the fields than inside a field.
        inner.setSpacing(16)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.heading = QLabel(title)
        self.heading.setObjectName("dialogTitle")
        self.heading.setFont(chinese_font(DIALOG_TITLE_PT))
        self.heading.setWordWrap(True)
        head.addWidget(self.heading, 1, Qt.AlignVCenter)
        self.close_button = IconButton("close", "关闭")
        # Like the × of a title bar it is not a Tab stop; Esc does the same.
        self.close_button.setFocusPolicy(Qt.NoFocus)
        self.close_button.clicked.connect(self.reject)
        head.addWidget(self.close_button, 0, Qt.AlignTop)
        inner.addLayout(head)
        body = QVBoxLayout()
        body.setContentsMargins(0, 0, DIALOG_PAD - corner, 0)
        body.setSpacing(16)
        inner.addLayout(body)
        return body

    def footer(self, *right: QPushButton, left: QPushButton | None = None) -> QHBoxLayout:
        """The buttons in a band along the card's foot, as Windows 11 dialogs have them.

        The main action is on the right; anything destructive stands apart on the left.
        """
        band = QFrame()
        band.setObjectName("dialogFooter")
        row = QHBoxLayout(band)
        row.setContentsMargins(DIALOG_PAD, 14, DIALOG_PAD, 14)
        row.setSpacing(8)
        if left is not None:
            row.addWidget(left)
        row.addStretch(1)
        for button in right:
            row.addWidget(button)
        self.card.layout().addWidget(band)
        return row

    def has_changes(self) -> bool:
        """Whether closing now would throw away something typed or picked. Forms say so."""
        return False

    def setVisible(self, visible: bool) -> None:  # noqa: FBT001
        if visible and not self.isVisible():
            self._cover_host()
        super().setVisible(visible)

    def _cover_host(self) -> None:
        """Lie over the parent window's contents, so all of it is dimmed and takes the outside click."""
        parent = self.parentWidget()
        host = parent.window() if parent is not None else None
        if host is None or not host.isVisible() or host.isMinimized() or isinstance(host, Modal):
            self.host = None
            return
        self.host = host
        area = QRect(host.mapToGlobal(QPoint(0, 0)), host.size())
        # A card taller or wider than a small window still fits: the dimming grows around it.
        need = self.minimumSizeHint().expandedTo(self.sizeHint())
        grow_x = max(0, need.width() - area.width())
        grow_y = max(0, need.height() - area.height())
        self.setGeometry(area.adjusted(-grow_x // 2, -grow_y // 2, grow_x - grow_x // 2, grow_y - grow_y // 2))

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        if self.card is None:
            return
        painter = QPainter(self)
        dark = THEME.get("scheme") == "dark"
        if self.host is not None:
            painter.fillRect(self.rect(), QColor(0, 0, 0, 120 if dark else 72))
        # A soft shadow: rounded layers, each a little larger and adding a little shade.
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 8 if dark else 5))
        box = QRectF(self.card.geometry())
        steps = 12
        for step in range(steps, 0, -1):
            grow = step * self._SHADOW / steps
            rect = box.adjusted(-grow, -grow + self._DROP, grow, grow + self._DROP)
            painter.drawRoundedRect(rect, self.RADIUS + grow, self.RADIUS + grow)

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        outside = self.card is not None and not self.card.geometry().contains(event.position().toPoint())
        if event.button() == Qt.LeftButton and outside:
            self.click_outside()
            return
        super().mousePressEvent(event)

    def click_outside(self) -> None:
        """Close, unless that would lose something; then shake, so the click is not a silent no."""
        if self.has_changes():
            self._nudge()
            return
        self.reject()

    def _nudge(self) -> None:
        if self.card is None:
            return
        if self._shake is None:
            self._shake = QVariantAnimation(self)
            self._shake.setDuration(320)
            self._shake.setStartValue(0.0)
            self._shake.setEndValue(1.0)
            self._shake.valueChanged.connect(self._shake_step)
            self._shake.finished.connect(self._shake_done)
        if self._shake.state() != QVariantAnimation.State.Running:
            self._shake_from = self.card.pos()
        self._shake.start()

    def shaking(self) -> bool:
        return self._shake is not None and self._shake.state() == QVariantAnimation.State.Running

    def _shake_step(self, value) -> None:  # noqa: ANN001
        progress = float(value)
        offset = round(8 * math.sin(progress * math.pi * 6) * (1 - progress))
        self.card.move(self._shake_from.x() + offset, self._shake_from.y())

    def _shake_done(self) -> None:
        self.card.move(self._shake_from)


class ConfirmDialog(Modal):
    """Ask before doing something that is hard to take back. The safe choice is the default."""

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        body: str,
        confirm: str,
        *,
        cancel: str = "取消",
        danger: bool = False,
    ) -> None:
        super().__init__(parent)
        layout = self.frame(title)
        self.body = QLabel(body)
        self.body.setWordWrap(True)
        layout.addWidget(self.body)
        self.cancel_button = QPushButton(cancel)
        self.cancel_button.setDefault(True)
        self.cancel_button.clicked.connect(self.reject)
        self.confirm_button = QPushButton(confirm)
        self.confirm_button.setObjectName("danger" if danger else "primary")
        self.confirm_button.setAutoDefault(False)
        self.confirm_button.clicked.connect(self.accept)
        self.footer(self.cancel_button, self.confirm_button)
        self.card.setMinimumWidth(400)
        _pointing(self)

    @classmethod
    def ask(cls, parent: QWidget | None, title: str, body: str, confirm: str, *, danger: bool = False) -> bool:
        return cls(parent, title, body, confirm, danger=danger).exec() == QDialog.Accepted


class EmptyState(QWidget):
    """What a page shows when it has nothing yet: an icon, a heading, a hint, and maybe one action."""

    def __init__(self, icon_name: str, title: str, hint: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        column = QVBoxLayout(self)
        column.setContentsMargins(24, 0, 24, 0)
        column.setSpacing(0)
        column.addStretch(1)
        self.icon = QLabel()
        self.icon.setObjectName("emptyIcon")
        self.icon.setAlignment(Qt.AlignCenter)
        column.addWidget(self.icon)
        column.addSpacing(12)
        self.title = QLabel(title)
        self.title.setObjectName("emptyTitle")
        self.title.setAlignment(Qt.AlignCenter)
        column.addWidget(self.title)
        column.addSpacing(6)
        self.hint = QLabel(hint)
        self.hint.setObjectName("emptyHint")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setWordWrap(True)
        self.hint.setVisible(bool(hint))
        column.addWidget(self.hint)
        self._actions = QHBoxLayout()
        self._actions.setSpacing(8)
        self._actions.addStretch(1)
        self._actions.addStretch(1)
        column.addSpacing(16)
        column.addLayout(self._actions)
        column.addStretch(1)
        self.refresh()

    def add_action(self, button: QPushButton) -> QPushButton:
        self._actions.insertWidget(self._actions.count() - 1, button)
        return button

    def set_text(self, title: str, hint: str = "") -> None:
        self.title.setText(title)
        self.hint.setText(hint)
        self.hint.setVisible(bool(hint))

    def set_icon(self, name: str) -> None:
        if name != self._icon_name:
            self._icon_name = name
            self.refresh()

    def refresh(self) -> None:
        self.icon.setPixmap(line_pixmap(self._icon_name, 40, THEME["muted"]))


class SettingsSection(QFrame):
    """A titled card in 设置. Each row is a label in a fixed column with its controls after it.

    A compact card puts its title in a column on the left, beside its rows, keeps the rows
    an even height, and puts a row's hint in its tooltip, so cards stacked one per row
    still fit on one screen. Content stays at the top when a card is taller than it needs.
    """

    # The height of a compact row: a control and its padding.
    COMPACT_ROW = CONTROL_H + 12

    def __init__(self, title: str, label_width: int, parent: QWidget | None = None, *, compact: bool = False) -> None:
        super().__init__(parent)
        self.setObjectName("section")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._label_width = label_width
        self._compact = compact
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        heading.setFont(chinese_font(SECTION_PT))
        self._rows = QVBoxLayout()
        self._rows.setSpacing(0)
        if compact:
            beside = QHBoxLayout(self)
            beside.setContentsMargins(20, 8, 20, 8)
            beside.setSpacing(16)
            # Every card's title takes the same width, so the rows line up from card to card.
            heading.setFixedSize(QFontMetrics(heading.font()).horizontalAdvance("中" * 3), self.COMPACT_ROW)
            heading.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            beside.addWidget(heading, 0, Qt.AlignTop)
            beside.addLayout(self._rows, 1)
        else:
            self._rows.setContentsMargins(20, 14, 20, 6)
            self.setLayout(self._rows)
            self._rows.addWidget(heading)
            self._rows.addSpacing(4)
        self._rows.addStretch(1)
        self._count = 0

    def _add(self, widget: QWidget) -> None:
        # Before the closing stretch, so rows stay at the top of the card.
        self._rows.insertWidget(self._rows.count() - 1, widget)

    def add_widget(self, widget: QWidget, *, separated: bool = True, indent: bool = False) -> QWidget:
        """Free content in the card, such as a wrap of chips or a note under the row above."""
        if separated and self._count:
            self._line()
        self._count += 1
        if indent:
            widget.setContentsMargins(self._label_width + 12, 0, 0, 8)
        self._add(widget)
        return widget

    def _line(self) -> None:
        line = QFrame()
        line.setObjectName("sectionLine")
        line.setFixedHeight(1)
        self._add(line)

    def add_row(self, label: str, *widgets: QWidget, hint: str = "", stretch: bool = True) -> QHBoxLayout:
        """The setting's name in a fixed column, its controls right after it.

        The hint goes under the controls, or into their tooltip on a compact card.
        """
        if self._count:
            self._line()
        self._count += 1
        host = QWidget()
        host.setObjectName("sectionRow")
        column = QVBoxLayout(host)
        column.setContentsMargins(0, *((6, 0, 6) if self._compact else (10, 0, 10)))
        column.setSpacing(4)
        if self._compact:
            host.setMinimumHeight(self.COMPACT_ROW)
        row = QHBoxLayout()
        row.setSpacing(12)
        name = QLabel(label)
        name.setObjectName("rowLabel")
        name.setFixedWidth(self._label_width)
        row.addWidget(name, 0, Qt.AlignVCenter)
        for widget in widgets:
            row.addWidget(widget, 0, Qt.AlignVCenter)
        if stretch:
            row.addStretch(1)
        column.addLayout(row)
        if hint and self._compact:
            for widget in (name, *widgets):
                if not widget.toolTip():
                    widget.setToolTip(hint)
        elif hint:
            note = QLabel(hint)
            note.setObjectName("rowHint")
            note.setWordWrap(True)
            note.setContentsMargins(self._label_width + 12, 0, 0, 0)
            column.addWidget(note)
        self._add(host)
        return row
