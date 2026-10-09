"""Small painted widgets, icons, and text helpers shared by the windows."""

from __future__ import annotations

from datetime import datetime
from math import cos, pi, radians, sin
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPoint, QPointF, QRect, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygon,
)
from PySide6.QtWidgets import (
    QApplication,
    QHeaderView,
    QLabel,
    QLayout,
    QLayoutItem,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from blacklist_detect.ui_theme import (
    RADIUS,
    SMALL_PT,
    THEME,
    TITLE_PT,
    _mix,
    chinese_family,
    chinese_font,
)


def _zh_clock(moment: datetime) -> str:
    return moment.strftime("%H:%M")


def _local_moment(stamp: str) -> datetime | None:
    try:
        moment = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    now = datetime.now().astimezone()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=now.tzinfo)
    return moment.astimezone(now.tzinfo)


def _zh_date(stamp: str) -> str:
    moment = _local_moment(stamp)
    if moment is None:
        return ""
    return f"{moment.year}-{moment.month:02d}-{moment.day:02d}"


def _zh_ago(stamp: str) -> str:
    moment = _local_moment(stamp)
    if moment is None:
        return ""
    seconds = (datetime.now().astimezone() - moment).total_seconds()
    if seconds < 60:
        return "刚刚"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}分钟前"
    hours = int(seconds // 3600)
    if hours < 24:
        return f"{hours}小时前"
    days = int(seconds // 86400)
    if days < 30:
        return f"{days}天前"
    months = days // 30
    if months < 12:
        return f"{months}个月前"
    return f"{days // 365}年前"


class _FlowLayout(QLayout):
    """Pills sit on a row and wrap onto the next line."""

    def __init__(self, parent=None, gap: int = 8) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._gap = gap
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:  # noqa: ANN001
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: ANN201
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):  # noqa: ANN201
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):  # noqa: ANN201
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._arrange(width)

    def setGeometry(self, rect) -> None:  # noqa: ANN001
        super().setGeometry(rect)
        self._arrange(rect.width(), rect.topLeft())

    def sizeHint(self) -> QSize:
        width = 0
        height = 0
        for item in self._items:
            hint = item.sizeHint()
            width += hint.width()
            height = max(height, hint.height())
        if self._items:
            width += self._gap * (len(self._items) - 1)
        margins = self.contentsMargins()
        return QSize(width + margins.left() + margins.right(), height + margins.top() + margins.bottom())

    def minimumSize(self) -> QSize:
        return self.sizeHint()

    def _arrange(self, width: int, origin: QPoint | None = None) -> int:
        margins = self.contentsMargins()
        x = margins.left()
        y = margins.top()
        line_height = 0
        limit = max(0, width - margins.right())
        for item in self._items:
            hint = item.sizeHint()
            if x > margins.left() and x + hint.width() > limit:
                x = margins.left()
                y += line_height + self._gap
                line_height = 0
            if origin is not None:
                item.setGeometry(QRect(origin + QPoint(x, y), hint))
            x += hint.width() + self._gap
            line_height = max(line_height, hint.height())
        return y + line_height + margins.bottom()


class _FlowHost(QWidget):
    """Gives a wrapping pill row a real height so the next control is not covered."""

    def __init__(self) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        layout = self.layout()
        if layout is None:
            return 0
        return layout.heightForWidth(width)

    def sizeHint(self) -> QSize:
        layout = self.layout()
        if layout is None:
            return super().sizeHint()
        hint = layout.sizeHint()
        return QSize(max(hint.width(), 1), self.heightForWidth(max(hint.width(), 1)))


def masked_name(name: str) -> str:
    """First character, then a star for every character after it."""
    if not name:
        return ""
    return name[0] + ("*" * (len(name) - 1))


class _ColumnHeader(QHeaderView):
    """Arrow on a title means drag to reorder. A left-right arrow on the edge means resize."""

    def __init__(self, parent=None) -> None:
        super().__init__(Qt.Horizontal, parent)
        self.setMouseTracking(True)
        self.names_hidden = False
        self.on_eye = None

    def _eye_box(self, rect: QRect) -> QRect:
        size = 16
        return QRect(rect.right() - 14 - size, rect.top() + (rect.height() - size) // 2, size, size)

    def _eye_at(self, pos: QPoint) -> bool:
        left = self.sectionViewportPosition(0)
        if self.sectionSize(0) <= 0:
            return False
        rect = QRect(left, 0, self.sectionSize(0), self.height())
        return self._eye_box(rect).contains(pos)

    def _cursor_at(self, pos: int) -> Qt.CursorShape:
        if self._eye_at(QPoint(pos, self.height() // 2)):
            return Qt.PointingHandCursor
        logical = self.logicalIndexAt(pos)
        if logical < 0:
            return Qt.ArrowCursor
        left = self.sectionViewportPosition(logical)
        right = left + self.sectionSize(logical)
        if pos - left <= 8 or right - pos <= 8:
            return Qt.SplitHCursor
        return Qt.OpenHandCursor

    def mouseMoveEvent(self, event) -> None:  # noqa: ANN001
        super().mouseMoveEvent(event)
        pos = int(event.position().x())
        point = event.position().toPoint()
        if self._eye_at(point):
            self.setToolTip("显示名字" if self.names_hidden else "隐藏名字")
        else:
            self.setToolTip("")
        if event.buttons() & Qt.LeftButton and self._cursor_at(pos) != Qt.SplitHCursor:
            self.setCursor(Qt.ClosedHandCursor)
            return
        self.setCursor(self._cursor_at(pos))

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.LeftButton and self._eye_at(event.position().toPoint()):
            self.names_hidden = not self.names_hidden
            if self.on_eye is not None:
                self.on_eye(self.names_hidden)
            self.viewport().update()
            event.accept()
            return
        super().mousePressEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        self.unsetCursor()
        super().leaveEvent(event)

    def paintSection(self, painter, rect, logicalIndex) -> None:  # noqa: ANN001
        super().paintSection(painter, rect, logicalIndex)
        if logicalIndex == 0:
            self._paint_eye(painter, self._eye_box(rect))
        if self.visualIndex(logicalIndex) == self.count() - 1:
            return
        painter.save()
        painter.setPen(QColor(THEME["line"]))
        painter.drawLine(rect.right(), rect.top() + 6, rect.right(), rect.bottom() - 6)
        painter.restore()

    def _paint_eye(self, painter, box: QRect) -> None:  # noqa: ANN001
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#6b7280"), 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        center_x = box.center().x()
        center_y = box.center().y()
        path = QPainterPath()
        path.moveTo(box.left() + 1, center_y)
        path.quadTo(center_x, box.top() + 2, box.right() - 1, center_y)
        path.quadTo(center_x, box.bottom() - 2, box.left() + 1, center_y)
        painter.drawPath(path)
        if self.names_hidden:
            painter.drawLine(
                QPointF(box.left() + 2, box.bottom() - 3),
                QPointF(box.right() - 2, box.top() + 3),
            )
        else:
            painter.setBrush(QColor("#6b7280"))
            painter.drawEllipse(QPointF(center_x, center_y), 1.7, 1.7)
        painter.restore()


class TagPill(QWidget):
    """A painted capsule. Stylesheets were painting flat color over the words."""

    _pad = round(8 * 1.1)
    _extra = round(6 * 1.1)
    _close_w = round(16 * 1.1)

    def __init__(
        self,
        text: str,
        on_remove=None,
        *,
        on_click=None,
        active: bool = True,
        point_size: float | None = None,
    ) -> None:
        super().__init__()
        self._text = text
        self._on_remove = on_remove
        self._on_click = on_click
        self._active = active
        self._point_size = point_size
        self._blend = 1.0 if active else 0.0
        self._wash = THEME["red_wash"]
        self._ink = THEME["red"]
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._set_blend)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFont(self._face())
        if on_remove is None and on_click is None:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        else:
            self.setMouseTracking(True)
            self.setCursor(Qt.PointingHandCursor)

    def _face(self) -> QFont:
        face = chinese_font(SMALL_PT)
        if self._point_size:
            face.setPointSizeF(self._point_size)
        face.setWeight(QFont.Weight.DemiBold)
        return face

    def _pad_now(self) -> int:
        if self._point_size:
            return max(4, round(self._point_size * 0.65))
        return self._pad

    def _extra_now(self) -> int:
        if self._point_size:
            return max(2, round(self._point_size * 0.4))
        return self._extra

    def sizeHint(self) -> QSize:
        metrics = QFontMetrics(self._face())
        close = self._close_w if self._on_remove is not None else 0
        width = metrics.horizontalAdvance(self._text) + self._pad_now() * 2 + close
        return QSize(width, metrics.height() + self._extra_now())

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def _close_box(self) -> QRect:
        rect = self.rect()
        return QRect(rect.right() - self._close_w, rect.top(), self._close_w, rect.height())

    def set_active(self, active: bool) -> None:
        active = bool(active)
        self._active = active
        target = 1.0 if active else 0.0
        if abs(self._blend - target) < 0.001:
            return
        self._anim.stop()
        self._anim.setStartValue(float(self._blend))
        self._anim.setEndValue(target)
        self._anim.start()

    def _set_blend(self, value: float) -> None:
        self._blend = float(value)
        self.update()

    def _running(self) -> bool:
        return self._anim.state() == QVariantAnimation.State.Running

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._running():
            self._paint_moving(painter)
            return
        self._paint_still(painter)

    def _paint_still(self, painter: QPainter) -> None:
        painter.setFont(self._face())
        body = QRect(self.rect())
        body.adjust(0, 1, -1, -1)
        pad = self._pad_now()
        if not self._active:
            painter.setPen(QPen(QColor("#9aa1ab"), 1))
            painter.setBrush(QColor("#e4e6eb"))
            radius = body.height() / 2
            painter.drawRoundedRect(body.adjusted(1, 1, -1, -1), radius, radius)
            painter.setPen(QColor(THEME["gray"]))
            text_box = QRect(body)
            text_box.adjust(pad, 0, -pad, 0)
            painter.drawText(text_box, Qt.AlignCenter, self._text)
            return
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._wash))
        radius = body.height() / 2
        painter.drawRoundedRect(body, radius, radius)
        painter.setPen(QColor(self._ink))
        text_box = QRect(body)
        if self._on_remove is not None:
            text_box.adjust(pad, 0, -self._close_w, 0)
            painter.drawText(text_box, Qt.AlignVCenter | Qt.AlignLeft, self._text)
            painter.drawText(self._close_box(), Qt.AlignCenter, "×")
        else:
            text_box.adjust(pad, 0, -pad, 0)
            painter.drawText(text_box, Qt.AlignCenter, self._text)

    def _paint_moving(self, painter: QPainter) -> None:
        amount = max(0.0, min(1.0, self._blend))
        progress = self._anim.currentTime() / max(1, self._anim.duration())
        pulse = sin(progress * pi)
        scale = 1 + (0.08 if self._active else -0.06) * pulse
        body = QRect(self.rect())
        body.adjust(0, 1, -1, -1)
        center = body.center()
        painter.save()
        painter.translate(center.x(), center.y())
        painter.scale(scale, scale)
        painter.translate(-center.x(), -center.y())
        fill = _mix("#e4e6eb", self._wash, amount)
        ink = _mix(THEME["gray"], self._ink, amount)
        edge = _mix("#9aa1ab", self._wash, amount)
        radius = body.height() / 2
        if amount < 0.98:
            painter.setPen(QPen(edge, 1))
            painter.setBrush(fill)
            painter.drawRoundedRect(body.adjusted(1, 1, -1, -1), radius, radius)
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(self._wash))
            painter.drawRoundedRect(body, radius, radius)
        painter.setFont(self._face())
        painter.setPen(ink if amount < 0.98 else QColor(self._ink))
        text_box = QRect(body)
        text_box.adjust(self._pad_now(), 0, -self._pad_now(), 0)
        painter.drawText(text_box, Qt.AlignCenter, self._text)
        painter.restore()

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        if self._on_click is not None:
            self._on_click()
            return
        if self._on_remove is not None and self._close_box().contains(event.position().toPoint()):
            self._on_remove()
            return
        super().mousePressEvent(event)


class _TagRow(QWidget):
    """The tags in one list cell. Pills that do not fit become one +N pill instead of being cut."""

    _pad = 4
    _gap = 6

    def __init__(self, tags: tuple[str, ...] | list[str]) -> None:
        super().__init__()
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.pills = [TagPill(tag) for tag in tags]
        for pill in self.pills:
            pill.setParent(self)
        self.more = TagPill("+0", active=False)
        self.more.setParent(self)
        self.more.hide()

    def sizeHint(self) -> QSize:
        height = self.more.sizeHint().height()
        return QSize(0, height)

    def _more_width(self, hidden: int) -> int:
        self.more._text = f"+{hidden}"
        return self.more.sizeHint().width()

    def arrange(self) -> int:
        """Place the pills that fit. Returns how many are shown."""
        room = self.width() - self._pad * 2
        count = len(self.pills)
        widths = [pill.sizeHint().width() for pill in self.pills]
        shown = 0
        for keep in range(count, -1, -1):
            hidden = count - keep
            needed = sum(widths[:keep]) + self._gap * max(0, keep - 1)
            if hidden:
                needed += (self._gap if keep else 0) + self._more_width(hidden)
            if needed <= room or keep == 0:
                shown = keep
                break
        x = self._pad
        for index, pill in enumerate(self.pills):
            if index >= shown:
                pill.hide()
                continue
            size = pill.sizeHint()
            pill.setGeometry(x, (self.height() - size.height()) // 2, size.width(), size.height())
            pill.show()
            x += size.width() + self._gap
        hidden = count - shown
        if hidden:
            self._more_width(hidden)
            size = self.more.sizeHint()
            self.more.setGeometry(x, (self.height() - size.height()) // 2, size.width(), size.height())
            self.more.show()
            self.more.update()
        else:
            self.more.hide()
        return shown

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self.arrange()


class NewTagButton(QPushButton):
    """Sits after the tag pills and opens the new-tag dialog."""

    def __init__(self) -> None:
        super().__init__("新标签")
        self.setObjectName("tagNew")
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFont(self._face())
        self._hover = False

    @staticmethod
    def _face() -> QFont:
        return chinese_font(SMALL_PT)

    def sizeHint(self) -> QSize:
        metrics = QFontMetrics(self._face())
        return QSize(metrics.horizontalAdvance(self.text()) + 16, metrics.height() + 6)

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

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        face = self._face()
        painter.setFont(face)
        body = QRect(self.rect())
        body.adjust(0, 1, -1, -1)
        painter.setPen(QColor(THEME["button_line"]))
        painter.setBrush(QColor(THEME["hover"] if self._hover else THEME["button"]))
        painter.drawRoundedRect(body, body.height() / 2, body.height() / 2)
        painter.setPen(QColor(THEME["text"]))
        text_box = QRect(body)
        text_box.adjust(8, 0, -8, 0)
        painter.drawText(text_box, Qt.AlignCenter, self.text())


class DayFolderIcon(QWidget):
    """Folder at rest. On hover it becomes the open or closed arrow, like Cursor."""

    def __init__(self, opened: bool = True) -> None:
        super().__init__()
        self.setObjectName("dayMark")
        self.setFixedSize(16, 16)
        self._opened = opened
        self._hover = 0.0
        self._turn = 1.0 if opened else 0.0
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(140)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._set_hover)
        self._turn_anim = QVariantAnimation(self)
        self._turn_anim.setDuration(160)
        self._turn_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._turn_anim.valueChanged.connect(self._set_turn)

    def set_hovered(self, hovered: bool) -> None:
        target = 1.0 if hovered else 0.0
        if abs(self._hover - target) < 0.001:
            return
        self._hover_anim.stop()
        self._hover_anim.setStartValue(float(self._hover))
        self._hover_anim.setEndValue(target)
        self._hover_anim.start()

    def set_open(self, opened: bool) -> None:
        opened = bool(opened)
        self._opened = opened
        target = 1.0 if opened else 0.0
        if abs(self._turn - target) < 0.001:
            return
        self._turn_anim.stop()
        self._turn_anim.setStartValue(float(self._turn))
        self._turn_anim.setEndValue(target)
        self._turn_anim.start()

    def _set_hover(self, value: float) -> None:
        self._hover = float(value)
        self.update()

    def _set_turn(self, value: float) -> None:
        self._turn = float(value)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ink = QColor(THEME["text"])
        if self._hover < 0.98:
            painter.save()
            painter.setOpacity(1 - self._hover)
            pen = QPen(ink, 1.15)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(QColor("#f4f5f7"))
            painter.drawRoundedRect(QRectF(1.5, 5.4, 13.0, 8.0), 1.4, 1.4)
            painter.drawRoundedRect(QRectF(1.5, 3.2, 6.0, 3.6), 1.0, 1.0)
            painter.setPen(Qt.NoPen)
            painter.drawRect(QRectF(2.6, 4.8, 4.0, 2.0))
            painter.restore()
        if self._hover > 0.02:
            painter.save()
            painter.setOpacity(self._hover)
            painter.translate(8, 8)
            painter.rotate(self._turn * 90)
            painter.translate(-8, -8)
            pen = QPen(ink, 1.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawPolyline(QPolygon([QPoint(4, 3), QPoint(11, 8), QPoint(4, 13)]))
            painter.restore()


def _clear_layout(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


def _empty_block(title: str) -> tuple[QWidget, QLabel]:
    """One centered line, for a page that has nothing to list."""
    host = QWidget()
    column = QVBoxLayout(host)
    column.setContentsMargins(24, 0, 24, 0)
    column.setSpacing(0)
    column.addStretch(1)
    heading = QLabel(title)
    heading.setObjectName("emptyTitle")
    heading.setAlignment(Qt.AlignCenter)
    heading.setFont(chinese_font(TITLE_PT))
    column.addWidget(heading)
    column.addStretch(1)
    return host, heading


def _line_icon(draw, color: str) -> QPixmap:
    ratio = 2
    pixmap = QPixmap(16 * ratio, 16 * ratio)
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    draw(painter)
    painter.end()
    return pixmap


def _check_icon() -> QPixmap:
    def draw(painter: QPainter) -> None:
        painter.drawLine(QPointF(3.2, 8.4), QPointF(6.6, 11.8))
        painter.drawLine(QPointF(6.6, 11.8), QPointF(12.8, 4.5))

    return _line_icon(draw, THEME["green"])


def _reload_icon() -> QPixmap:
    def draw(painter: QPainter) -> None:
        cx, cy, radius = 8.0, 8.2, 5.0
        painter.drawArc(QRectF(cx - radius, cy - radius, radius * 2, radius * 2), 60 * 16, -300 * 16)
        end = radians(60)
        tip = QPointF(cx + radius * cos(end), cy - radius * sin(end))
        tx, ty = -sin(end), -cos(end)
        back, wing = 2.7, 1.7
        nx, ny = -ty, tx
        left = QPointF(tip.x() - tx * back + nx * wing, tip.y() - ty * back + ny * wing)
        right = QPointF(tip.x() - tx * back - nx * wing, tip.y() - ty * back - ny * wing)
        painter.drawLine(tip, left)
        painter.drawLine(tip, right)

    return _line_icon(draw, "#6b7280")


def _watch_mark(color: str) -> QPixmap:
    ratio = 2
    size = 8 * ratio
    pixmap = QPixmap(size, size)
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    painter.setOpacity(0.22)
    painter.drawEllipse(0, 0, size, size)
    painter.setOpacity(1)
    inset = 2 * ratio
    painter.drawEllipse(inset, inset, size - inset * 2, size - inset * 2)
    painter.end()
    return pixmap


class ThemeSwatch(QWidget):
    """One theme, shown as its color only."""

    _square = 28
    _badge = 16

    def __init__(self, name: str, color: str, on_click) -> None:
        super().__init__()
        self._name = name
        self._color = color
        self._on_click = on_click
        self._selected = False
        hang = self._badge // 2
        self.setFixedSize(self._square + hang, self._square + hang)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip(name)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        hang = self._badge // 2
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._color))
        painter.drawRoundedRect(0, hang, self._square, self._square, 8, 8)
        if not self._selected:
            return
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#1c9a4b"))
        painter.drawEllipse(self._square - hang, 0, self._badge, self._badge)
        center_x = self._square
        center_y = hang
        pen = QPen(QColor("#ffffff"), 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(center_x - 4, center_y, center_x - 1, center_y + 3)
        painter.drawLine(center_x - 1, center_y + 3, center_x + 4, center_y - 3)

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.LeftButton:
            self._on_click()
            return
        super().mousePressEvent(event)


def _icon() -> QIcon:
    path = Path(__file__).resolve().parent / "assets" / "app.ico"
    if path.is_file():
        return QIcon(str(path))
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(THEME["gold"]))
    painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
    painter.setBrush(QColor(THEME["on_gold"]))
    painter.drawRoundedRect(16, 16, 32, 6, 2, 2)
    painter.drawRoundedRect(16, 29, 32, 6, 2, 2)
    painter.drawRoundedRect(16, 42, 20, 6, 2, 2)
    painter.end()
    return QIcon(pixmap)


class _DetailTip(QWidget):
    """Small hover card for the full 详情. It does not take the click."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus,
        )
        self.setObjectName("detailTip")
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMaximumWidth(320)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(0)
        self.label = QLabel()
        self.label.setObjectName("detailTipText")
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.label.setFont(chinese_font())
        layout.addWidget(self.label)
        self.apply_theme()

    def apply_theme(self) -> None:
        family = chinese_family()
        t = THEME
        self.setStyleSheet(
            f"""
            QWidget#detailTip {{
                background: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["line"]};
                border-radius: {RADIUS}px;
            }}
            QLabel#detailTipText {{
                background: transparent;
                color: {t["text"]};
                font-family: "{family}";
                font-size: 11pt;
                border: none;
            }}
            """
        )

    def show_reason(self, text: str, anchor: QPoint) -> None:
        self.apply_theme()
        self.label.setFont(chinese_font())
        self.label.setText(text)
        metrics = QFontMetrics(self.label.font())
        longest = max((metrics.horizontalAdvance(line) for line in text.split("\n")), default=0)
        self.label.setFixedWidth(min(296, max(longest + 2, 48)))
        self.adjustSize()
        self._place(anchor)
        self.show()

    def _place(self, anchor: QPoint) -> None:
        screen = QApplication.screenAt(anchor) or QApplication.primaryScreen()
        area = screen.availableGeometry() if screen is not None else QRect(0, 0, 1920, 1080)
        x = anchor.x()
        y = anchor.y() + 6
        if y + self.height() > area.bottom() - 8:
            y = anchor.y() - self.height() - 6
        if x + self.width() > area.right() - 8:
            x = area.right() - self.width() - 8
        self.move(max(area.left() + 8, x), max(area.top() + 8, y))


class _PlainItemDelegate(QStyledItemDelegate):
    """Selection stays a wash. A click does not draw the black focus box."""

    def paint(self, painter, option, index) -> None:  # noqa: ANN001
        view = self.parent()
        if isinstance(view, QTableWidget) and view.objectName() == "blacklist" and index.column() == 1:
            drawn = QStyleOptionViewItem(option)
            self.initStyleOption(drawn, index)
            drawn.state = drawn.state & ~QStyle.State_HasFocus
            drawn.text = ""
            view.style().drawControl(QStyle.CE_ItemViewItem, drawn, painter, view)
            return
        option.state = option.state & ~QStyle.State_HasFocus
        super().paint(painter, option, index)
