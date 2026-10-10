"""Small painted widgets, icons, and text helpers shared by the windows."""

from __future__ import annotations

from datetime import datetime
from math import pi, sin
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPoint, QRect, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
    QPolygon,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHeaderView,
    QLabel,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from blacklist_detect.ui_icons import pixmap as line_pixmap
from blacklist_detect.ui_kit import _KeyboardRing, activates
from blacklist_detect.ui_theme import (
    BODY_PT,
    RADIUS,
    SMALL_PT,
    THEME,
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


class _FlowHost(QWidget):
    """Pills on a row that wrap onto the next line. It places its children itself.

    This used to be a Python QLayout subclass. That kept Qt's layout items in a
    Python list, and when a dialog closed they were freed after their pills,
    which crashed with PySide6 6.12.
    """

    def __init__(self, gap: int = 8) -> None:
        super().__init__()
        self._gap = gap
        self._widgets: list[QWidget] = []
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def addWidget(self, widget: QWidget) -> None:
        widget.setParent(self)
        self._widgets.append(widget)
        widget.show()
        self.updateGeometry()
        self._arrange(self.width(), place=True)

    def clear(self) -> None:
        for widget in self._widgets:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        self._widgets = []
        self.updateGeometry()

    def widgets(self) -> list[QWidget]:
        return list(self._widgets)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._arrange(width, place=False)

    def sizeHint(self) -> QSize:
        hints = [widget.sizeHint() for widget in self._widgets]
        width = sum(hint.width() for hint in hints) + self._gap * max(0, len(hints) - 1)
        width = max(width, 1)
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:
        widest = max((widget.sizeHint().width() for widget in self._widgets), default=1)
        return QSize(widest, self.heightForWidth(max(self.width(), widest)))

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._arrange(self.width(), place=True)

    def _arrange(self, width: int, place: bool) -> int:
        x = 0
        y = 0
        line_height = 0
        for widget in self._widgets:
            hint = widget.sizeHint()
            if x > 0 and x + hint.width() > width:
                x = 0
                y += line_height + self._gap
                line_height = 0
            if place:
                widget.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._gap
            line_height = max(line_height, hint.height())
        return y + line_height


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
        self._eye_hot = False

    # The eye sits right after the 名字 title, in a 28 px target that lights up under the pointer.
    _EYE = 28

    def _eye_box(self, rect: QRect) -> QRect:
        title = self.model().headerData(0, Qt.Horizontal) if self.model() is not None else ""
        text_width = QFontMetrics(chinese_font(SMALL_PT)).horizontalAdvance(str(title or ""))
        left = min(rect.left() + 14 + text_width + 4, rect.right() - self._EYE - 4)
        return QRect(left, rect.top() + (rect.height() - self._EYE) // 2, self._EYE, self._EYE)

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
        hot = self._eye_at(point)
        if hot != self._eye_hot:
            self._eye_hot = hot
            self.viewport().update()
        if hot:
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
        if self._eye_hot:
            self._eye_hot = False
            self.viewport().update()
        super().leaveEvent(event)

    def paintSection(self, painter, rect, logicalIndex) -> None:  # noqa: ANN001
        super().paintSection(painter, rect, logicalIndex)
        if logicalIndex == 0:
            self._paint_eye(painter, self._eye_box(rect))
        if self.visualIndex(logicalIndex) == self.count() - 1:
            return
        painter.save()
        painter.setPen(QColor(THEME["border"]))
        painter.drawLine(rect.right(), rect.top() + 6, rect.right(), rect.bottom() - 6)
        painter.restore()

    def _paint_eye(self, painter, box: QRect) -> None:  # noqa: ANN001
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        if self._eye_hot:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(THEME["hover"]))
            painter.drawRoundedRect(QRectF(box), 6, 6)
        name = "eye_off" if self.names_hidden else "eye"
        mark = line_pixmap(name, 18, THEME["text"] if self._eye_hot else THEME["muted"], stroke=1.6)
        painter.drawPixmap(box.center().x() - 9 + 1, box.center().y() - 9 + 1, mark)
        painter.restore()


def _paint_ring(painter: QPainter, rect: QRectF, radius: float) -> None:
    """The keyboard focus ring, in the text color the way Windows draws it."""
    painter.save()
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(QColor(THEME["text"]), 1.5))
    painter.drawRoundedRect(rect, radius, radius)
    painter.restore()


class TagPill(_KeyboardRing, QWidget):
    """A painted capsule. Stylesheets were painting flat color over the words.

    A clickable pill emits clicked(text). It does not hold a callback: a lambda
    that refers back to its dialog makes a reference cycle, and PySide6 6.12
    crashed when the garbage collector broke it.

    Tags are red pills: a tag is why someone is on the blacklist.
    """

    clicked = Signal(str)

    _pad = round(8 * 1.1)
    _extra = round(6 * 1.1)

    def __init__(
        self,
        text: str,
        *,
        clickable: bool = False,
        active: bool = True,
        point_size: float | None = None,
    ) -> None:
        super().__init__()
        self._text = text
        self._clickable = clickable
        self._hover = False
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
        self.setAccessibleName(text)
        if clickable:
            self.setMouseTracking(True)
            self.setCursor(Qt.PointingHandCursor)
            self.setFocusPolicy(Qt.TabFocus)
        else:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

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
        width = metrics.horizontalAdvance(self._text) + self._pad_now() * 2
        return QSize(width, metrics.height() + self._extra_now())

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

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
        else:
            self._paint_still(painter)
        if self.show_ring():
            _paint_ring(painter, QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), (self.height() - 1) / 2)

    def keyPressEvent(self, event) -> None:  # noqa: ANN001
        if self._clickable and activates(event):
            self.clicked.emit(self._text)
            return
        super().keyPressEvent(event)

    def enterEvent(self, event) -> None:  # noqa: ANN001
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def _paint_still(self, painter: QPainter) -> None:
        painter.setFont(self._face())
        body = QRect(self.rect())
        body.adjust(0, 1, -1, -1)
        pad = self._pad_now()
        if not self._active:
            hot = self._clickable and self._hover
            line = THEME["red"] if hot else THEME["chip_off_line"]
            painter.setPen(QPen(QColor(line), 1))
            painter.setBrush(QColor(THEME["red_wash"] if hot else THEME["chip_off_bg"]))
            radius = body.height() / 2
            painter.drawRoundedRect(body.adjusted(1, 1, -1, -1), radius, radius)
            ink = THEME["red"] if hot else THEME["muted"] if self._clickable else THEME["gray"]
            painter.setPen(QColor(ink))
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
        fill = _mix(THEME["chip_off_bg"], self._wash, amount)
        ink = _mix(THEME["gray"], self._ink, amount)
        edge = _mix(THEME["chip_off_line"], self._wash, amount)
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
        if self._clickable:
            self.clicked.emit(self._text)
            return
        super().mousePressEvent(event)


_ROW_PAD = 4
_ROW_GAP = 6


def _pill_face() -> QFont:
    face = chinese_font(SMALL_PT)
    face.setWeight(QFont.Weight.DemiBold)
    return face


def _pill_size(text: str, metrics: QFontMetrics) -> QSize:
    return QSize(metrics.horizontalAdvance(text) + TagPill._pad * 2, metrics.height() + TagPill._extra)


def tag_row_layout(tags: tuple[str, ...] | list[str], width: int) -> tuple[int, str]:
    """How many tags fit in a cell this wide, and the +N pill for the rest ("" when all fit)."""
    metrics = QFontMetrics(_pill_face())
    room = width - _ROW_PAD * 2
    widths = [_pill_size(tag, metrics).width() for tag in tags]
    count = len(widths)
    for keep in range(count, -1, -1):
        hidden = count - keep
        needed = sum(widths[:keep]) + _ROW_GAP * max(0, keep - 1)
        if hidden:
            needed += (_ROW_GAP if keep else 0) + _pill_size(f"+{hidden}", metrics).width()
        if needed <= room or keep == 0:
            return keep, f"+{hidden}" if hidden else ""
    return 0, ""


def paint_tag_row(painter: QPainter, rect: QRect, tags: tuple[str, ...] | list[str]) -> None:
    """The tags of one list row, drawn straight onto the table. A widget per row made a long list slow."""
    shown, more = tag_row_layout(tags, rect.width())
    face = _pill_face()
    metrics = QFontMetrics(face)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setFont(face)
    x = rect.left() + _ROW_PAD
    for text, active in [*((tag, True) for tag in tags[:shown]), *([(more, False)] if more else [])]:
        size = _pill_size(text, metrics)
        top = rect.top() + (rect.height() - size.height()) // 2
        _draw_pill(painter, QRect(x, top, size.width(), size.height()), text, active, TagPill._pad)
        x += size.width() + _ROW_GAP
    painter.restore()


def _draw_pill(painter: QPainter, rect: QRect, text: str, active: bool, pad: int) -> None:
    """One pill: red wash and red words, or the outlined grey of a pill that is off or +N."""
    body = QRect(rect)
    body.adjust(0, 1, -1, -1)
    radius = body.height() / 2
    if active:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(THEME["red_wash"]))
        painter.drawRoundedRect(body, radius, radius)
        painter.setPen(QColor(THEME["red"]))
    else:
        painter.setPen(QPen(QColor(THEME["chip_off_line"]), 1))
        painter.setBrush(QColor(THEME["chip_off_bg"]))
        painter.drawRoundedRect(body.adjusted(1, 1, -1, -1), radius, radius)
        painter.setPen(QColor(THEME["gray"]))
    text_box = QRect(body)
    text_box.adjust(pad, 0, -pad, 0)
    painter.drawText(text_box, Qt.AlignCenter, text)


class TagListDelegate(QStyledItemDelegate):
    """The tags beside 黑名单: 全部, then each tag as a red pill with how many names carry it.

    The row under the pointer shows a pencil in place of its number; a click on the pencil opens 修改.
    """

    # The item's margin and padding, so the pill and the number sit inside the row's wash.
    INSET = 12
    ROW = 34

    def paint(self, painter, option, index) -> None:  # noqa: ANN001
        view = self.parent()
        drawn = QStyleOptionViewItem(option)
        self.initStyleOption(drawn, index)
        drawn.state = drawn.state & ~QStyle.State_HasFocus
        drawn.text = ""
        view.style().drawControl(QStyle.CE_ItemViewItem, drawn, painter, view)
        rect = option.rect.adjusted(self.INSET, 0, -self.INSET, 0)
        tag = str(index.data(Qt.UserRole) or "")
        count = int(index.data(Qt.UserRole + 1) or 0)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if tag and view.property("hoverRow") == index.row():
            box = self.edit_box(option.rect)
            painter.drawPixmap(box.topLeft(), line_pixmap("edit", 16, THEME["muted"]))
        elif count:
            painter.setFont(chinese_font(SMALL_PT))
            painter.setPen(QColor(THEME["muted"]))
            painter.drawText(rect, Qt.AlignRight | Qt.AlignVCenter, str(count))
        room = rect.adjusted(0, 0, -32, 0)
        if tag:
            face = _pill_face()
            painter.setFont(face)
            metrics = QFontMetrics(face)
            text = metrics.elidedText(tag, Qt.ElideRight, max(0, room.width() - TagPill._pad * 2))
            size = _pill_size(text, metrics)
            top = rect.top() + (rect.height() - size.height()) // 2
            _draw_pill(painter, QRect(rect.left(), top, size.width(), size.height()), text, True, TagPill._pad)
        else:
            painter.setFont(chinese_font(BODY_PT))
            painter.setPen(QColor(THEME["text"]))
            painter.drawText(room, Qt.AlignLeft | Qt.AlignVCenter, str(index.data(Qt.DisplayRole) or ""))
        painter.restore()

    def sizeHint(self, _option, _index) -> QSize:  # noqa: ANN001
        return QSize(0, self.ROW)

    @classmethod
    def edit_box(cls, rect: QRect) -> QRect:
        """Where a row's pencil is drawn."""
        return QRect(rect.right() - cls.INSET - 15, rect.center().y() - 7, 16, 16)

    @classmethod
    def edit_target(cls, rect: QRect) -> QRect:
        """The area a click on the pencil lands in: larger than the pencil, as a button would be."""
        return cls.edit_box(rect).adjusted(-8, -8, 8, 8)


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
            pen = QPen(ink, 1.4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(QColor(THEME["surface"]))
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
            pen = QPen(ink, 1.4)
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


def _check_icon() -> QPixmap:
    return line_pixmap("check", 16, THEME["green"])


def _reload_icon() -> QPixmap:
    return line_pixmap("reload", 16, THEME["muted"])


def _watch_mark(color: str) -> QPixmap:
    """The status dot: a soft halo with a solid core, 8 px across."""
    ratio = 2
    side = 8
    pixmap = QPixmap(side * ratio, side * ratio)
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    # A painter on a high-DPI pixmap works in logical pixels: the whole dot is side × side.
    painter.setOpacity(0.22)
    painter.drawEllipse(QRectF(0, 0, side, side))
    painter.setOpacity(1)
    painter.drawEllipse(QRectF(2, 2, side - 4, side - 4))
    painter.end()
    return pixmap


class ThemeSwatch(_KeyboardRing, QWidget):
    """One theme, shown as its color only. A click emits chosen(name)."""

    chosen = Signal(str)

    _square = 28
    _badge = 16

    def __init__(self, name: str, color: str) -> None:
        super().__init__()
        self._name = name
        self._color = color
        self._selected = False
        hang = self._badge // 2
        self.setFixedSize(self._square + hang, self._square + hang)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        self.setToolTip(name)
        self.setAccessibleName(name)
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
        if self.show_ring():
            _paint_ring(painter, QRectF(1, hang + 1, self._square - 2, self._square - 2), 7)
        if not self._selected:
            return
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(THEME["green"]))
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
            self.chosen.emit(self._name)
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: ANN001
        if activates(event):
            self.chosen.emit(self._name)
            return
        super().keyPressEvent(event)


def _icon() -> QIcon:
    path = Path(__file__).resolve().parent / "assets" / "app.ico"
    if path.is_file():
        return QIcon(str(path))
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(THEME["accent"]))
    painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
    painter.setBrush(QColor(THEME["on_accent"]))
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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 6, 10)
        layout.setSpacing(0)
        self.label = QLabel()
        self.label.setObjectName("detailTipText")
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.label.setFont(chinese_font(SMALL_PT))
        # A very long reason scrolls inside the card; the card stays open while the pointer is on it.
        self.scroll = QScrollArea()
        self.scroll.setObjectName("detailTipScroll")
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setWidgetResizable(False)
        self.scroll.setWidget(self.label)
        layout.addWidget(self.scroll)
        self.apply_theme()

    def apply_theme(self) -> None:
        family = chinese_family()
        t = THEME
        self.setStyleSheet(
            f"""
            QWidget#detailTip {{
                background: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["border"]};
                border-radius: {RADIUS}px;
            }}
            QScrollArea#detailTipScroll, QScrollArea#detailTipScroll > QWidget > QWidget {{
                background: transparent;
                border: none;
            }}
            QScrollArea#detailTipScroll QScrollBar:vertical {{
                background: transparent;
                width: 6px;
            }}
            QScrollArea#detailTipScroll QScrollBar::handle:vertical {{
                background: {t["border"]};
                border-radius: 3px;
                min-height: 24px;
            }}
            QLabel#detailTipText {{
                background: transparent;
                color: {t["text"]};
                font-family: "{family}";
                font-size: {SMALL_PT}pt;
                border: none;
            }}
            """
        )

    _WIDTH = 400
    _HEIGHT = 320

    def show_reason(self, text: str, anchor: QPoint) -> None:
        self.apply_theme()
        self.label.setFont(chinese_font(SMALL_PT))
        lines = text.split("\n")
        self.text = text
        # Qt wraps only between words; a run like 1111 or a long English word has none.
        # A zero-width space between characters lets every line wrap, and shows nothing.
        self.label.setText("\n".join("\u200b".join(line) for line in lines))
        metrics = QFontMetrics(self.label.font())
        longest = max((metrics.horizontalAdvance(line) for line in lines), default=0)
        width = min(self._WIDTH, max(longest + 4, 48))
        self.label.setFixedWidth(width)
        height = self.label.heightForWidth(width)
        self.label.setFixedHeight(height)
        scrolls = height > self._HEIGHT
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded if scrolls else Qt.ScrollBarAlwaysOff)
        self.scroll.setFixedSize(width + (10 if scrolls else 0), min(height, self._HEIGHT))
        self.scroll.verticalScrollBar().setValue(0)
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


def _row_divider(painter: QPainter, rect: QRect) -> None:
    painter.save()
    color = QColor(THEME["border"])
    color.setAlphaF(0.6)
    painter.setPen(QPen(color, 1))
    painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
    painter.restore()


class _PlainItemDelegate(QStyledItemDelegate):
    """Selection stays a wash. A click does not draw the black focus box."""

    def paint(self, painter, option, index) -> None:  # noqa: ANN001
        view = self.parent()
        # Cells that carry a widget of their own: draw only the background, never the text under it.
        widget_cell = view.objectName() == "recordNames" or (view.objectName() == "blacklist" and index.column() == 1)
        if isinstance(view, QTableWidget) and widget_cell:
            drawn = QStyleOptionViewItem(option)
            self.initStyleOption(drawn, index)
            drawn.state = drawn.state & ~QStyle.State_HasFocus
            drawn.text = ""
            view.style().drawControl(QStyle.CE_ItemViewItem, drawn, painter, view)
            tags = index.data(Qt.UserRole + 3)
            if view.objectName() == "blacklist" and tags:
                paint_tag_row(painter, option.rect, tuple(tags))
            if view.objectName() == "blacklist":
                _row_divider(painter, option.rect)
            return
        option.state = option.state & ~QStyle.State_HasFocus
        super().paint(painter, option, index)
        if isinstance(view, QTableWidget) and view.objectName() == "blacklist":
            _row_divider(painter, option.rect)
        if isinstance(view, QTableWidget) and view.objectName() == "blacklist" and option.state & QStyle.State_Selected:
            header = view.horizontalHeader()
            if index.column() == header.logicalIndex(header.count() - 1):
                # The row under the pointer is selected; a pencil says a click opens 修改.
                mark = line_pixmap("edit", 16, THEME["muted"])
                rect = option.rect
                painter.drawPixmap(rect.right() - 16 - 12, rect.center().y() - 8, mark)
