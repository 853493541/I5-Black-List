"""The marks drawn over the game: the cover on 准备案件还原, the hit card, and the clear check."""

from __future__ import annotations

import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBitmap,
    QColor,
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

from blacklist_detect.ui_theme import (
    READ_PT,
    THEME,
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


def _play_hit_sound() -> None:
    """The Windows warning sound. It follows the system volume and sound scheme."""
    if sys.platform == "win32":
        try:
            import winsound

            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            return
        except Exception:
            pass
    QApplication.beep()


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


_COVER_BORDER = 6
_COVER_OUTSET = 3


def _cover_radius(height: int) -> int:
    """准备案件还原 is a rounded rectangle, not a pill."""
    return max(4, round(height * 0.14))


class HitCard(QWidget):
    """Name and tags beside the red border. It does not cover the button."""

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
        body_layout.setContentsMargins(0, 0, 0, 0)
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
        self.rows.setContentsMargins(12, 8, 12, 8)
        self.rows.setSpacing(6)
        self.scroll.setWidget(self.content)
        body_layout.addWidget(self.scroll)

    def set_people(self, people: list[tuple[str, tuple[str, ...]]], height: int) -> None:
        name_pt = READ_PT
        self.rows.setContentsMargins(12, 8, 12, 8)
        self.rows.setSpacing(6)
        self.rows.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        _clear_layout(self.rows)
        family = chinese_family()
        ink = THEME["text"]
        mark = THEME["red"]
        name_font = chinese_font(READ_PT)
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
            bullet = QLabel("•")
            bullet.setObjectName("hitBullet")
            bullet.setFont(name_font)
            bullet.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            bullet.setStyleSheet(
                f'color: {mark}; background: transparent; font-family: "{family}"; font-size: {name_pt}pt; font-weight: 400;'
            )
            row.addWidget(bullet, 0, Qt.AlignVCenter)
            label = QLabel(name)
            label.setObjectName("hitName")
            label.setFont(name_font)
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            label.setFixedWidth(name_width)
            label.setStyleSheet(
                f'color: {ink}; background: transparent; font-family: "{family}"; font-size: {name_pt}pt; font-weight: 400;'
            )
            row.addWidget(label, 0, Qt.AlignVCenter)
            for tag in tags[:3]:
                row.addWidget(TagPill(tag), 0, Qt.AlignVCenter)
            row.addStretch(1)
            self.rows.addWidget(person)
            person.setVisible(True)
        self._apply_style(_cover_radius(max(28, int(height))))
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        self.content.setMinimumSize(0, 0)
        self.content.setMaximumSize(16777215, 16777215)
        self.rows.invalidate()
        self.rows.activate()
        count = self.rows.count()
        row_heights = [self.rows.itemAt(i).widget().sizeHint().height() for i in range(count)]
        margins = self.rows.contentsMargins()
        spacing = self.rows.spacing()
        full = margins.top() + margins.bottom() + sum(row_heights) + spacing * max(0, count - 1)
        visible_n = min(3, count)
        visible = margins.top() + margins.bottom() + sum(row_heights[:visible_n]) + spacing * max(0, visible_n - 1)
        content_w = max(self.rows.sizeHint().width(), 1)
        bar = 10 if count > 3 else 0
        self.content.setMinimumSize(content_w, max(full, 1))
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded if count > 3 else Qt.ScrollBarAlwaysOff)
        self.scroll.setFixedHeight(max(visible, 1))
        self.scroll.verticalScrollBar().setValue(0)
        self.setFixedSize(content_w + bar, max(visible, 1))

    def _apply_style(self, radius: int) -> None:
        t = THEME
        self.setStyleSheet(
            f"""
            QWidget#hitCard {{
                background: {t["surface"]};
                border: none;
                border-radius: {radius}px;
            }}
            QScrollArea#hitScroll, QScrollArea#hitScroll QWidget {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 6px 2px 6px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {t["button_line"]};
                border-radius: 4px;
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
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(THEME["green"]))
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


class LobbyPanel(QWidget):
    """Rounded cover sized to 准备案件还原. It sits on the button, not beside it."""

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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel("")
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.label)
        self.setFont(chinese_font(READ_PT))
        self.label.setFont(chinese_font(READ_PT))

    def set_mode(self, mode: str, text: str) -> None:
        self.mode = mode
        self.setToolTip(text)
        self.label.setText(text if mode == "checking" else "")
        radius = _cover_radius(self.height())
        family = chinese_family()
        label_px = max(12, min(22, round(self.height() * 0.32)))
        if mode == "checking":
            background = "#e8892d"
            ink = "#fffaf3"
            border = "none"
        elif mode == "hit":
            background = "transparent"
            ink = "transparent"
            border = f"{_COVER_BORDER}px solid {THEME['red']}"
        else:
            background = "transparent"
            ink = "transparent"
            border = f"{_COVER_BORDER}px solid {THEME['green']}"
        self.setStyleSheet(
            f"""
            LobbyPanel, QWidget {{ background: transparent; }}
            QLabel {{
                background: {background};
                color: {ink};
                border: {border};
                font-family: "{family}";
                font-size: {label_px}px;
                padding: 4px 12px;
                border-radius: {radius}px;
            }}
            """
        )

    def show_over(self, left: float, top: float, width: float, height: float, mode: str, text: str) -> None:
        width = max(1, int(round(width)))
        height = max(1, int(round(height)))
        self.setFixedSize(width, height)
        self.move(int(round(left)), int(round(top)))
        self._apply_input(mode == "clear")
        self.set_mode(mode, text)
        self._mask_pill()
        self.show()
        _pin_topmost(self)

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
