"""Main window, tray status, and the always-on-top warning."""

from __future__ import annotations

import queue
import sys
import time
from datetime import datetime
from pathlib import Path
from math import cos, pi, radians, sin

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt, QThread, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import (
    QBitmap,
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QPolygon,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLayoutItem,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from blacklist_detect import __version__
from blacklist_detect.capture import (
    CaptureUnavailable,
    capture_capability_message,
    capture_displays,
    capture_top_band,
    lock_foreground,
    virtual_origin,
)
from blacklist_detect.hotkey import GlobalHotkey, parse_hotkey
from blacklist_detect.logs import log, log_dir, on_uncaught, setup_logging
from blacklist_detect.match import NameLabel, clean_stored_name, fold, format_hit, match_label, seat_number, split_ellipsis
from blacklist_detect.model import Entry
from blacklist_detect.ocr_engine import OcrUnavailable, get_engine
from blacklist_detect.pipeline import CheckResult, Hit, NameSlot, check_frames, check_image, glance_title
from blacklist_detect.storage import Store, describe_entry, tag_text
from blacklist_detect.watch import GLANCE_INTERVAL_MS, LobbyWatch


def _claim_windows_app() -> None:
    """Tell Windows this is its own app, so the taskbar uses our icon instead of Python's."""
    if sys.platform != "win32":
        return
    import ctypes

    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Local.BlackListDetect")


def run_app() -> int:
    log_path = setup_logging()
    log.info("Start %s, Python %s, %s", __version__, sys.version.split()[0], sys.platform)
    _claim_windows_app()
    app = QApplication(sys.argv)
    app.setApplicationName("黑名单检测")
    app.setApplicationVersion(__version__)
    key = instance_key()
    if notify_running_instance(key):
        log.info("Already running. Brought the open window forward.")
        return 0
    app.setWindowIcon(_icon())
    app.setFont(chinese_font())
    _apply_theme(app)
    try:
        window = MainWindow()
    except Exception as exc:
        log.critical("The window could not open", exc_info=True)
        from PySide6.QtWidgets import QMessageBox

        where = f"\n\n详情在 {log_path}" if log_path else ""
        QMessageBox.critical(None, "黑名单检测", f"程序没能打开：{exc}{where}")
        return 1
    window.instance_server = listen_for_instances(key, window._show_from_tray)
    on_uncaught(window.report_uncaught)
    window.show()
    window.start_warmup()
    QTimer.singleShot(0, window.show_first_run_guide)
    code = app.exec()
    log.info("Exit %s", code)
    return code


def instance_key() -> str:
    """One name per Windows user, so a second copy can find the first."""
    import getpass
    import hashlib

    try:
        user = getpass.getuser()
    except Exception:
        user = "user"
    return "BlackListDetect-" + hashlib.sha1(user.encode("utf-8")).hexdigest()[:12]


def notify_running_instance(key: str) -> bool:
    """Ask a copy that is already open to show its window. False when none is open."""
    from PySide6.QtNetwork import QLocalSocket

    socket = QLocalSocket()
    socket.connectToServer(key)
    if not socket.waitForConnected(300):
        return False
    socket.write(b"show")
    socket.flush()
    socket.waitForBytesWritten(300)
    socket.disconnectFromServer()
    return True


def listen_for_instances(key: str, on_show):
    """Show this window when the app is opened a second time. Two copies would overwrite each other's files."""
    from PySide6.QtNetwork import QLocalServer

    QLocalServer.removeServer(key)
    server = QLocalServer()
    server.listen(key)

    def accept() -> None:
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            connection.disconnectFromServer()
            connection.deleteLater()
            on_show()

    server.newConnection.connect(accept)
    return server


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


def chinese_family() -> str:
    """A face that actually contains simplified Chinese. Qt does not fall back by itself."""
    from PySide6.QtGui import QFontDatabase

    installed = set(QFontDatabase.families())
    for name in (
        "Microsoft YaHei",
        "微软雅黑",
        "Microsoft YaHei UI",
        "Sarasa Gothic SC",
        "Noto Sans CJK SC",
        "Noto Sans SC",
        "Source Han Sans SC",
        "思源黑体",
        "PingFang SC",
        "SimHei",
        "黑体",
    ):
        if name in installed:
            return name
    return "Microsoft YaHei"


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


def _mix(start: str, end: str, amount: float) -> QColor:
    left = QColor(start)
    right = QColor(end)
    amount = max(0.0, min(1.0, amount))
    return QColor(
        round(left.red() + (right.red() - left.red()) * amount),
        round(left.green() + (right.green() - left.green()) * amount),
        round(left.blue() + (right.blue() - left.blue()) * amount),
    )


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


READ_PT = 13
SMALL_PT = 11
TITLE_PT = 15


def chinese_font(point_size: int = READ_PT) -> QFont:
    font = QFont(chinese_family())
    font.setPointSize(point_size)
    font.setWeight(QFont.Weight.Normal)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.NoSubpixelAntialias)
    return font


def ui_font() -> QFont:
    """Buttons use the same size and weight as the names."""
    return chinese_font(READ_PT)


def record_font() -> QFont:
    """Record names and times, the same reading size as the rest of the window."""
    return chinese_font(READ_PT)


# One inset and one corner for the whole window.
PAD = 24
GAP = 12
DIALOG_PAD = 20
RADIUS = 8

def _palette(
    page: str,
    ink: str,
    muted: str,
    wash: str,
    edge: str,
    accent: str,
    accent_line: str,
    accent_hover: str,
    accent_press: str,
    on_accent: str,
) -> dict[str, str]:
    return {
        "bg": page,
        "text": ink,
        "muted": muted,
        "surface": "#ffffff",
        "line": edge,
        "button": "#ffffff",
        "button_line": edge,
        "selected": wash,
        "head": wash,
        "head_text": ink,
        "gold": accent,
        "gold_line": accent_line,
        "on_gold": on_accent,
        "green": "#1c7a3e",
        "green_wash": "#f3fbf6",
        "green_hover": "#e3f6eb",
        "red": "#c23b2e",
        "red_wash": "#fff6f6",
        "red_hover": "#fde4e1",
        "gray": "#6b7280",
        "gray_wash": "#f3f4f6",
        "gray_hover": "#e6e8ec",
        "add": accent,
        "danger": "#a33b2c",
        "hover": wash,
        "gold_hover": accent_hover,
        "gold_press": accent_press,
        "danger_hover": "#f8e6e1",
    }


THEMES = {
    "蓝色": _palette("#f2f6fb", "#172033", "#5d6d82", "#e4eef8", "#d3deec", "#12325a", "#2c6cb3", "#1a4578", "#0c243f", "#f4f8ff"),
    "棕色": _palette("#f7f3ee", "#2a2118", "#6f6256", "#f3ebe3", "#e6d9cc", "#6b4428", "#a67c52", "#7d5334", "#4a2e1a", "#fff8f2"),
    "紫色": _palette("#f6f4fb", "#241833", "#6a5d80", "#eee8f6", "#ddd4ec", "#4a2d73", "#7a5caf", "#5c3b8c", "#321d52", "#f8f5ff"),
    "绿色": _palette("#f3f7f4", "#17241c", "#5c6e64", "#e5f0ea", "#d2e2d8", "#1b5340", "#3d8f6e", "#24664e", "#12382b", "#f4fbf7"),
    "红色": _palette("#fbf5f4", "#2c1818", "#7a6565", "#f6e8e6", "#ead8d4", "#a24f28", "#c46a3e", "#92471f", "#6e3416", "#fdf6ec"),
}
THEME = THEMES["蓝色"]


def use_theme(name: str) -> None:
    global THEME
    THEME = THEMES.get(name, THEMES["蓝色"])


def _apply_theme(app: QApplication | None = None) -> None:
    """Keep every native control on the same palette, even when Windows is dark."""
    app = app or QApplication.instance()
    if app is None:
        return
    scheme = Qt.ColorScheme.Light
    app.styleHints().setColorScheme(scheme)
    t = THEME
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(t["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(t["surface"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(t["head"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(t["button"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(t["selected"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(t["surface"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(t["muted"]))
    palette.setColor(QPalette.ColorRole.Mid, QColor(t["line"]))
    app.setPalette(palette)


def _button_rules(family: str) -> str:
    """Ghost buttons, filled primary, and the danger outline. Every surface uses this."""
    t = THEME
    return f"""
            QPushButton {{
                font-family: "{family}";
                font-size: 13pt;
                font-weight: 400;
                background: {t["button"]};
                color: {t["text"]};
                border: 1px solid {t["button_line"]};
                border-radius: 8px;
                padding: 0 16px;
                min-height: 36px;
            }}
            QPushButton#primary {{
                background: {t["gold"]};
                border-color: {t["gold_line"]};
                color: {t["on_gold"]};
            }}
            QPushButton#danger {{
                background: {t["button"]};
                color: {t["danger"]};
                border-color: {t["danger"]};
            }}
            QPushButton:hover {{
                background: {t["hover"]};
                border-color: {t["gold_line"]};
            }}
            QPushButton:pressed {{ background: {t["selected"]}; }}
            QPushButton#primary:hover {{
                background: {t["gold_hover"]};
                border-color: {t["gold_line"]};
                color: {t["on_gold"]};
            }}
            QPushButton#primary:pressed {{
                background: {t["gold_press"]};
                color: {t["on_gold"]};
            }}
            QPushButton#danger:hover {{
                background: {t["danger_hover"]};
                color: {t["danger"]};
                border-color: {t["danger"]};
            }}
            QPushButton#recheck {{
                font-size: 11pt;
                background: {t["gold"]};
                border-color: {t["gold_line"]};
                color: {t["on_gold"]};
                border-radius: 8px;
                padding: 0 10px;
                min-height: 26px;
            }}
            QPushButton#recheck:hover {{
                background: {t["gold_hover"]};
                border-color: {t["gold_line"]};
                color: {t["on_gold"]};
            }}
            QPushButton#recheck:pressed {{
                background: {t["gold_press"]};
                color: {t["on_gold"]};
            }}
            """


def _input_rules(family: str) -> str:
    t = THEME
    return f"""
            QLineEdit, QPlainTextEdit {{
                font-family: "{family}";
                font-size: 13pt;
                font-weight: 400;
                background: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["line"]};
                border-radius: 8px;
                padding: 8px 12px;
            }}
            QLineEdit {{
                padding: 4px 12px;
                min-height: 28px;
            }}
            QLineEdit:hover, QPlainTextEdit:hover {{
                border: 1px solid {t["gold_line"]};
            }}
            QLineEdit:focus, QPlainTextEdit:focus {{
                border: 1px solid {t["gold"]};
            }}
            QLineEdit:disabled {{
                color: {t["muted"]};
                background: {t["head"]};
                border: 1px solid {t["line"]};
            }}
            """


def _card_rules() -> str:
    t = THEME
    return f"""
            QWidget#settingsCard, QWidget#recordCard, QWidget#noticeCard {{
                background: {t["surface"]};
                border: 1px solid {t["line"]};
                border-radius: 12px;
            }}
            QWidget#settingsRow {{
                background: transparent;
                border: none;
                border-bottom: 1px solid {t["line"]};
            }}
            QWidget#settingsRowLast {{
                background: transparent;
                border: none;
            }}
            """


def _pointing(root) -> None:
    for widget in (*root.findChildren(QPushButton), *root.findChildren(QCheckBox)):
        widget.setCursor(Qt.PointingHandCursor)


def _menu_style(family: str) -> str:
    t = THEME
    return f"""
            QMenu {{
                font-family: "{family}";
                background: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["line"]};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                font-family: "{family}";
                background: transparent;
                color: {t["text"]};
                border-radius: 6px;
                padding: 8px 14px;
            }}
            QMenu::item:selected {{ background: {t["selected"]}; }}
            """


def _window_style(family: str) -> str:
    t = THEME
    return f"""
            QWidget#root, QLabel, QLineEdit, QPlainTextEdit, QCheckBox,
            QTabWidget, QTabBar, QListWidget, QTableWidget, QHeaderView, QTableWidget QWidget {{
                font-family: "{family}";
            }}
            QMainWindow, QWidget#root, QTabWidget, QTabBar, QTabWidget::pane {{
                background: {t["bg"]};
                color: {t["text"]};
                border: none;
                padding: 0;
                margin: 0;
            }}
            QTabBar {{ height: 0; max-height: 0; }}
            QWidget#tabHeader {{
                background: transparent;
                border: none;
                border-bottom: 1px solid {t["line"]};
            }}
            QWidget#tabHeader QLabel {{ background: transparent; }}
            QWidget#tabHeader QWidget#modeCluster, QWidget#modeCycle {{
                background: transparent;
                border: none;
            }}
            QLabel#sub {{
                font-family: "{family}";
                font-size: 11pt;
                font-weight: 400;
                color: {t["muted"]};
            }}
            QLabel#emptyTitle {{
                font-family: "{family}";
                font-size: 15pt;
                font-weight: 400;
                color: {t["text"]};
                background: transparent;
            }}
            QLabel#clear {{
                font-family: "{family}";
                font-size: 13pt;
                font-weight: 400;
                color: {t["green"]};
                background: transparent;
            }}
            QLabel#hit {{
                font-family: "{family}";
                font-size: 13pt;
                font-weight: 400;
                color: {t["red"]};
                background: transparent;
            }}
            QLabel#idle {{
                font-family: "{family}";
                font-size: 13pt;
                font-weight: 400;
                color: {t["muted"]};
                background: transparent;
            }}
            QLabel#status {{
                font-family: "{family}";
                font-size: 13pt;
                font-weight: 400;
                color: {t["text"]};
                background: transparent;
            }}
            QLabel#watchOn {{
                font-family: "{family}";
                font-size: 13pt;
                font-weight: 400;
                color: {t["green"]};
                background: transparent;
            }}
            QLabel#watchOff {{
                font-family: "{family}";
                font-size: 13pt;
                font-weight: 400;
                color: #6b4428;
                background: transparent;
            }}
            QLabel#hotkey {{
                font-family: "{family}";
                font-size: 13pt;
                font-weight: 400;
                color: #6b4428;
                background: transparent;
            }}
            """ + _input_rules(family) + f"""
            QPlainTextEdit, QTableWidget, QListWidget {{
                background: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["line"]};
                border-radius: 8px;
                padding: 8px 12px;
            }}
            QListWidget::item {{
                font-family: "{family}";
                background: transparent;
                color: {t["text"]};
                padding: 8px 12px;
                border: none;
            }}
            QListWidget#history {{
                font-family: "{family}";
                font-size: 13pt;
                font-weight: 400;
                color: {t["text"]};
                padding: 0;
                outline: none;
                border-radius: 12px;
            }}
            QListWidget#history:focus {{
                border: 1px solid {t["line"]};
                outline: none;
            }}
            QListWidget#history::item {{
                padding: 2px 8px;
                margin: 1px 4px;
                border: none;
                border-radius: 8px;
                outline: none;
                font-weight: 400;
                color: {t["text"]};
            }}
            QListWidget#history::item:selected, QListWidget#history::item:selected:hover {{
                color: {t["text"]};
                font-weight: 400;
            }}
            QListWidget::item:hover {{ background: {t["hover"]}; }}
            QListWidget::item:selected, QListWidget::item:selected:hover {{
                background: {t["selected"]};
                color: {t["text"]};
            }}
            QTableWidget::item {{
                background: {t["surface"]};
                color: {t["text"]};
                border: none;
            }}
            QTableWidget::item:hover {{ background: {t["hover"]}; }}
            QTableWidget::item:selected, QTableWidget::item:selected:hover {{
                background: {t["selected"]};
                color: {t["text"]};
            }}
            QTableWidget#recordNames::item,
            QTableWidget#recordNames::item:hover,
            QTableWidget#recordNames::item:selected {{
                background: transparent;
            }}
            QTableWidget#blacklist {{
                background: {t["surface"]};
                border-radius: 12px;
                padding: 0;
                outline: none;
            }}
            QTableWidget#blacklist:focus {{
                border: 1px solid {t["line"]};
                outline: none;
            }}
            QTableWidget#blacklist::item {{
                background: {t["surface"]};
                padding: 10px 14px;
                border: none;
                outline: none;
            }}
            QTableWidget#blacklist::item:hover {{
                background: {t["surface"]};
                color: {t["text"]};
            }}
            QTableWidget#blacklist::item:selected,
            QTableWidget#blacklist::item:selected:hover {{
                background: {t["hover"]};
                color: {t["text"]};
            }}
            QHeaderView {{ background: {t["surface"]}; }}
            QHeaderView::section, QTableCornerButton::section {{
                background: {t["head"]};
                color: {t["head_text"]};
                border: none;
                padding: 10px 16px;
                font-size: 13pt;
                font-weight: 400;
            }}
            QScrollBar:vertical, QScrollBar:horizontal {{
                background: {t["surface"]};
                border: none;
                margin: 0;
            }}
            QScrollBar:vertical {{ width: 10px; }}
            QScrollBar:horizontal {{ height: 10px; }}
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
                background: {t["button_line"]};
                border-radius: 5px;
                min-height: 24px;
                min-width: 24px;
            }}
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
                background: {t["gold_line"]};
            }}
            QScrollBar::add-line, QScrollBar::sub-line,
            QScrollBar::add-page, QScrollBar::sub-page {{
                background: transparent;
                height: 0;
                width: 0;
            }}
            QWidget#tableHead {{
                background: {t["head"]};
                border: none;
                border-bottom: 1px solid {t["line"]};
                border-top-left-radius: 11px;
                border-top-right-radius: 11px;
            }}
            QWidget#tableHead QLabel {{
                font-family: "{family}";
                color: {t["head_text"]};
                background: transparent;
            }}
            QWidget#recordCard QTableWidget#recordNames {{
                background: {t["surface"]};
                border: none;
                border-radius: 0;
                padding: 0;
            }}
            """ + _card_rules() + f"""
            QCheckBox {{
                spacing: 8px;
                min-height: 28px;
                color: {t["text"]};
                background: transparent;
            }}
            QCheckBox:hover {{ color: {t["gold"]}; }}
            """ + _button_rules(family) + f"""
            QPushButton#rowDelete {{
                background: transparent;
                color: {t["danger"]};
                border: none;
                border-radius: 6px;
                padding: 0;
                min-width: 0;
                min-height: 0;
                max-height: 22px;
                font-size: 13pt;
                font-weight: 400;
            }}
            QPushButton#rowDelete:hover {{
                background: {t["danger_hover"]};
                color: {t["danger"]};
            }}
            QPushButton[clearPair="true"] {{
                padding: 0 8px;
            }}
            """ + _menu_style(family) + f"""
            QPushButton#tab {{
                color: {t["muted"]};
                background: transparent;
                border: none;
                border-radius: 8px;
                padding: 0 14px;
                margin: 0 2px;
                min-height: 28px;
                max-height: 28px;
            }}
            QPushButton#tab:hover {{
                color: {t["text"]};
                background: {t["hover"]};
                border: none;
            }}
            QPushButton#tab:checked,
            QPushButton#tab:checked:hover,
            QPushButton#tab:checked:pressed {{
                color: {t["gold"]};
                background: {t["selected"]};
                border: none;
            }}
            QPushButton#tab:pressed {{
                background: {t["hover"]};
                border: none;
            }}
            QPushButton#mode:checked,
            QPushButton#mode:checked:hover {{
                background: {t["gold"]};
                border-color: {t["gold_line"]};
                color: {t["on_gold"]};
            }}
            QPushButton#tagNew {{
                background: transparent;
                border: none;
                padding: 0;
                margin: 0;
                min-width: 0;
                min-height: 0;
                font-size: 11pt;
                font-weight: 400;
            }}
            """


def _dialog_style(family: str) -> str:
    t = THEME
    return f"""
            QDialog, QMessageBox {{
                font-family: "{family}";
                background: {t["bg"]};
                color: {t["text"]};
            }}
            QLabel {{
                font-family: "{family}";
                background: transparent;
                color: {t["text"]};
            }}
            QLabel#field, QLabel#sub {{
                font-family: "{family}";
                font-size: 11pt;
                font-weight: 400;
                color: {t["muted"]};
                background: transparent;
            }}
            QLabel#error {{
                font-family: "{family}";
                color: {t["red"]};
                background: transparent;
            }}
            QCheckBox {{
                font-family: "{family}";
                background: transparent;
                spacing: 8px;
                min-height: 28px;
                padding: 2px 4px;
                color: {t["text"]};
            }}
            QCheckBox:hover {{
                background: {t["hover"]};
                color: {t["text"]};
            }}
            """ + _input_rules(family) + _button_rules(family)


def _colorref(value: str):
    import ctypes

    color = QColor(value)
    return ctypes.c_uint((color.blue() << 16) | (color.green() << 8) | color.red())


def _caption_color(widget) -> None:
    """Match the window caption to the chrome. Windows only."""
    if sys.platform != "win32":
        return
    import ctypes

    hwnd = int(widget.winId())
    dark = ctypes.c_int(0)
    dwm = ctypes.windll.dwmapi
    values = (
        (20, dark),
        (19, dark),
        (34, _colorref(THEME["line"])),
        (35, _colorref(THEME["bg"])),
        (36, _colorref(THEME["text"])),
    )
    for attribute, value in values:
        dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))


def _page(layout) -> None:
    layout.setContentsMargins(0, GAP, 0, 0)
    layout.setSpacing(GAP)


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


def _cancel_button(dialog: QDialog) -> QPushButton:
    """Close without saving. Esc does the same."""
    cancel = QPushButton("取消")
    cancel.setAutoDefault(False)
    cancel.setDefault(False)
    cancel.clicked.connect(dialog.reject)
    return cancel


def _confirm(parent, text: str) -> bool:
    box = QDialog(parent)
    box.setWindowTitle("黑名单检测")
    box.setFont(chinese_font())
    box.setStyleSheet(_dialog_style(chinese_family()))
    _caption_color(box)
    layout = QVBoxLayout(box)
    layout.setContentsMargins(DIALOG_PAD, DIALOG_PAD, DIALOG_PAD, DIALOG_PAD)
    layout.setSpacing(GAP)
    message = QLabel(text)
    message.setWordWrap(True)
    layout.addWidget(message)
    buttons = QHBoxLayout()
    buttons.addStretch(1)
    yes = QPushButton("确定")
    yes.setObjectName("primary")
    yes.setAutoDefault(True)
    yes.setDefault(True)
    yes.clicked.connect(box.accept)
    buttons.addWidget(_cancel_button(box))
    buttons.addWidget(yes)
    layout.addLayout(buttons)
    box.setMinimumWidth(360)
    _pointing(box)
    return box.exec() == QDialog.Accepted


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


class TagEditDialog(QDialog):
    """Rename one tag, or delete it from the list and from every name."""

    def __init__(self, tag: str, catalog: tuple[str, ...], parent=None) -> None:
        super().__init__(parent)
        self.original = tag
        self.catalog = catalog
        self.renamed = tag
        self.deleted = False
        self.setWindowTitle("修改标签")
        self.setFont(chinese_font())
        self.setStyleSheet(_dialog_style(chinese_family()))
        _caption_color(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(DIALOG_PAD, DIALOG_PAD, DIALOG_PAD, DIALOG_PAD)
        layout.setSpacing(GAP)
        label = QLabel("标签")
        label.setObjectName("field")
        layout.addWidget(label)
        self.name_edit = QLineEdit(tag)
        layout.addWidget(self.name_edit)
        self.error = QLabel("")
        self.error.setObjectName("error")
        layout.addWidget(self.error)
        self.name_edit.textChanged.connect(lambda _text: self.error.setText(""))
        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        remove = QPushButton("删除")
        remove.setObjectName("danger")
        remove.setAutoDefault(False)
        remove.setDefault(False)
        remove.clicked.connect(self._delete)
        # The destructive button stands apart on the left, away from 保存.
        buttons.addWidget(remove)
        buttons.addStretch(1)
        save = QPushButton("保存")
        save.setObjectName("primary")
        save.setAutoDefault(True)
        save.setDefault(True)
        save.clicked.connect(self._accept)
        buttons.addWidget(_cancel_button(self))
        buttons.addWidget(save)
        layout.addLayout(buttons)
        self.setMinimumWidth(360)
        self.name_edit.returnPressed.connect(self._accept)
        _pointing(self)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)

    def _accept(self) -> None:
        from blacklist_detect.storage import clean_tag

        renamed = clean_tag(self.name_edit.text())
        if not renamed:
            self.error.setText("请填写标签")
            return
        if renamed != self.original and renamed in self.catalog:
            self.error.setText("已有这个标签")
            return
        self.error.setText("")
        self.renamed = renamed
        self.deleted = False
        self.accept()

    def _delete(self) -> None:
        self.deleted = True
        self.accept()


class TagCreateDialog(QDialog):
    """Name a tag that is not in the list yet."""

    def __init__(self, catalog: tuple[str, ...], parent=None) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.created = ""
        self.setWindowTitle("新标签")
        self.setFont(chinese_font())
        self.setStyleSheet(_dialog_style(chinese_family()))
        _caption_color(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(DIALOG_PAD, DIALOG_PAD, DIALOG_PAD, DIALOG_PAD)
        layout.setSpacing(GAP)
        label = QLabel("标签")
        label.setObjectName("field")
        layout.addWidget(label)
        self.name_edit = QLineEdit()
        layout.addWidget(self.name_edit)
        self.error = QLabel("")
        self.error.setObjectName("error")
        layout.addWidget(self.error)
        self.name_edit.textChanged.connect(lambda _text: self.error.setText(""))
        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        buttons.addStretch(1)
        add = QPushButton("添加")
        add.setObjectName("primary")
        add.setAutoDefault(True)
        add.setDefault(True)
        add.clicked.connect(self._accept)
        buttons.addWidget(_cancel_button(self))
        buttons.addWidget(add)
        layout.addLayout(buttons)
        self.setMinimumWidth(360)
        self.name_edit.returnPressed.connect(self._accept)
        _pointing(self)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)

    def _accept(self) -> None:
        from blacklist_detect.storage import clean_tag

        tag = clean_tag(self.name_edit.text())
        if not tag:
            self.error.setText("请填写标签")
            return
        if tag in self.catalog:
            self.error.setText("已有这个标签")
            return
        self.error.setText("")
        self.created = tag
        self.accept()


class AddNameDialog(QDialog):
    """One player. Click a tag to put it on this record, and click it again to take it off."""

    def __init__(
        self,
        name: str = "",
        tags: tuple[str, ...] = (),
        detail: str = "",
        title: str = "添加",
        allow_delete: bool = False,
        catalog: tuple[str, ...] = (),
        added_at: str = "",
        parent=None,
        taken: frozenset[str] | set[str] = frozenset(),
    ) -> None:
        super().__init__(parent)
        from blacklist_detect.storage import TAGS

        self.setWindowTitle(title)
        # Folded names already on the list. Saving one of them again would make a second row.
        self.taken = frozenset(taken)
        self.name = name
        self.tags: tuple[str, ...] = tuple(tags)
        self.detail = detail
        self.catalog = list(catalog or TAGS)
        self.picked = [tag for tag in self.catalog if tag in tags]
        self.picked.extend(tag for tag in tags if tag not in self.picked)
        self._tag_order = list(self.picked)
        self._tag_order.extend(tag for tag in self.catalog if tag not in self._tag_order)
        self.deleted = False
        self.setFont(chinese_font())
        self.setStyleSheet(_dialog_style(chinese_family()))
        _caption_color(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(DIALOG_PAD, DIALOG_PAD, DIALOG_PAD, DIALOG_PAD)
        layout.setSpacing(10)
        label_width = QFontMetrics(chinese_font()).horizontalAdvance("名字") + 8

        def add_field(title: str, widget: QWidget) -> None:
            row = QHBoxLayout()
            row.setSpacing(12)
            label = QLabel(title)
            label.setObjectName("field")
            label.setFixedWidth(label_width)
            row.addWidget(label, 0, Qt.AlignVCenter)
            row.addWidget(widget, 1)
            layout.addLayout(row)

        self.name_edit = QLineEdit(name)
        added_on = _zh_date(added_at)
        if added_on:
            name_row = QHBoxLayout()
            name_row.setSpacing(12)
            name_label = QLabel("名字")
            name_label.setObjectName("field")
            name_label.setFixedWidth(label_width)
            name_row.addWidget(name_label, 0, Qt.AlignVCenter)
            name_row.addWidget(self.name_edit, 1)
            self.added_on = QLabel(added_on)
            self.added_on.setObjectName("sub")
            self.added_on.setFixedWidth(QFontMetrics(chinese_font()).horizontalAdvance(added_on) + 2)
            name_row.addWidget(self.added_on, 0, Qt.AlignVCenter)
            layout.addLayout(name_row)
        else:
            add_field("名字", self.name_edit)
        self.name_error = QLabel("")
        self.name_error.setObjectName("error")
        self.name_error.hide()
        layout.addWidget(self.name_error)
        self.name_edit.textChanged.connect(self._clear_name_error)
        tag_row = QHBoxLayout()
        tag_row.setSpacing(12)
        tag_label = QLabel("标签")
        tag_label.setObjectName("field")
        tag_label.setFixedWidth(label_width)
        tag_row.addWidget(tag_label, 0, Qt.AlignVCenter)
        self.tag_host = _FlowHost()
        self.tag_rows = _FlowLayout(self.tag_host, gap=8)
        tag_row.addWidget(self.tag_host, 1)
        layout.addLayout(tag_row)
        self._refresh_tags()
        self.detail_edit = QPlainTextEdit()
        self.detail_edit.setPlainText(detail)
        self.detail_edit.setTabChangesFocus(True)
        self.detail_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.detail_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.detail_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.detail_edit.document().setDocumentMargin(0)
        self.detail_edit.setFixedHeight(QFontMetrics(self.font()).lineSpacing() * 3 + 18)
        detail_row = QHBoxLayout()
        detail_row.setSpacing(12)
        detail_label = QLabel("详情")
        detail_label.setObjectName("field")
        detail_label.setFixedWidth(label_width)
        detail_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        detail_label.setContentsMargins(0, 8, 0, 0)
        detail_row.addWidget(detail_label, 0, Qt.AlignTop)
        detail_row.addWidget(self.detail_edit, 1)
        layout.addLayout(detail_row)
        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        remove = None
        if allow_delete:
            remove = QPushButton("删除")
            remove.setObjectName("danger")
            remove.setAutoDefault(False)
            remove.setDefault(False)
            remove.clicked.connect(self._delete)
            # The destructive button stands apart on the left, away from 保存.
            buttons.addWidget(remove)
        buttons.addStretch(1)
        confirm = QPushButton("保存" if allow_delete else "添加")
        confirm.setObjectName("primary")
        confirm.setAutoDefault(True)
        confirm.setDefault(True)
        confirm.clicked.connect(self._accept)
        buttons.addWidget(_cancel_button(self))
        buttons.addWidget(confirm)
        layout.addLayout(buttons)
        self.setMinimumWidth(420)
        self.name_edit.returnPressed.connect(self._accept)
        _pointing(self)

    def _clear_name_error(self, _text: str) -> None:
        self.name_error.setText("")
        self.name_error.hide()

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)

    def _refresh_tags(self) -> None:
        _clear_layout(self.tag_rows)
        for tag in self._tag_order:
            self.tag_rows.addWidget(
                TagPill(tag, on_click=lambda picked=tag: self._toggle_tag(picked), active=tag in self.picked)
            )
        self.tag_host.updateGeometry()
        self.tag_host.setVisible(bool(self._tag_order))

    def _toggle_tag(self, tag: str) -> None:
        if tag in self.picked:
            self._detach_tag(tag)
            return
        self._attach_tag(tag)

    def _attach_tag(self, tag: str | None = None) -> None:
        chosen = tag or ""
        if not chosen or chosen in self.picked or chosen not in self.catalog:
            return
        self.picked.append(chosen)
        self._paint_tag(chosen)

    def _detach_tag(self, tag: str) -> None:
        self.picked = [item for item in self.picked if item != tag]
        self._paint_tag(tag)

    def _paint_tag(self, tag: str) -> None:
        for index in range(self.tag_rows.count()):
            pill = self.tag_rows.itemAt(index).widget()
            if isinstance(pill, TagPill) and pill._text == tag:
                pill.set_active(tag in self.picked)
                return

    def _chosen(self) -> tuple[str, ...]:
        ordered = [tag for tag in self.catalog if tag in self.picked]
        ordered.extend(tag for tag in self.picked if tag not in ordered)
        return tuple(ordered)

    def _accept(self) -> None:
        key = fold(clean_stored_name(self.name_edit.text()))
        if not self.name_edit.text().strip():
            problem = "请填写名字"
        elif not key:
            problem = "名字里要有文字或数字"
        elif key in self.taken:
            problem = "黑名单里已经有这个名字"
        else:
            problem = ""
        if problem:
            self.name_error.setText(problem)
            self.name_error.show()
            return
        self.name_error.setText("")
        self.name_error.hide()
        self.name = self.name_edit.text()
        self.tags = self._chosen()
        self.detail = self.detail_edit.toPlainText()
        self.deleted = False
        self.accept()

    def _delete(self) -> None:
        self.deleted = True
        self.accept()


class BatchAddDialog(QDialog):
    """Many names from one paste. Spaces separate names, or each person is 名字（说明）."""

    def __init__(self, catalog: tuple[str, ...] = (), parent=None) -> None:
        super().__init__(parent)
        from blacklist_detect.storage import TAGS

        self.setWindowTitle("批量添加")
        self.names: list[str] = []
        self.annotated: list[tuple[str, tuple[str, ...], str]] | None = None
        self.catalog = catalog or TAGS
        self.setFont(chinese_font())
        self.setStyleSheet(_dialog_style(chinese_family()))
        _caption_color(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(DIALOG_PAD, DIALOG_PAD, DIALOG_PAD, DIALOG_PAD)
        layout.setSpacing(GAP)
        hint = QLabel(
            "可以这样粘贴：\n"
            "· 一行一个：名字，炸房，贴脸，原因\n"
            "· 名字（说明），说明里的标签会自动选上\n"
            "· 只有名字，用空格或换行隔开\n"
            "· 朋友用「分享」复制的名单"
        )
        hint.setObjectName("field")
        layout.addWidget(hint)
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("把名字粘在这里")
        self.edit.setMinimumHeight(180)
        layout.addWidget(self.edit)
        self.error = QLabel("")
        self.error.setObjectName("error")
        layout.addWidget(self.error)
        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        buttons.addStretch(1)
        confirm = QPushButton("添加")
        confirm.setObjectName("primary")
        confirm.setAutoDefault(True)
        confirm.setDefault(True)
        confirm.clicked.connect(self._accept)
        buttons.addWidget(_cancel_button(self))
        buttons.addWidget(confirm)
        layout.addLayout(buttons)
        self.setMinimumWidth(420)
        _pointing(self)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)

    def _accept(self) -> None:
        from blacklist_detect.storage import annotated_from_block, is_shared, names_from_block, parse_blacklist, parse_shared

        text = self.edit.toPlainText()
        if is_shared(text):
            # A list copied with 分享 in this app. Its tags come with it.
            self.annotated = parse_shared(text)
            self.names = [name for name, _tags, _reason in self.annotated]
            if not self.names:
                self.error.setText("没有名字")
                return
            self.accept()
            return
        self.annotated = annotated_from_block(text, self.catalog)
        if self.annotated is None and ("," in text or "，" in text):
            self.annotated = parse_blacklist(text, self.catalog) or None
        if self.annotated is None:
            self.names = names_from_block(text)
        else:
            self.names = [name for name, _tags, _reason in self.annotated]
        if not self.names:
            self.error.setText("没有名字")
            return
        self.accept()


SAMPLE_LOBBY = Path(__file__).resolve().parent / "assets" / "sample-lobby.jpg"


class PictureResultDialog(QDialog):
    """What one picture check read: the twelve seats, with blacklist matches in red."""

    def __init__(self, title: str, result: CheckResult | None = None, error: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFont(chinese_font())
        self.setStyleSheet(_dialog_style(chinese_family()))
        _caption_color(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(DIALOG_PAD, DIALOG_PAD, DIALOG_PAD, DIALOG_PAD)
        layout.setSpacing(GAP)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.seats: list[QLabel] = []
        if error:
            self.summary.setText(f"没能检查：{error}")
        elif result is None or not result.header_found:
            reason = result.message if result is not None else ""
            self.summary.setText(f"{reason}\n截图里要有「推演成功」大厅的画面。".strip())
        else:
            if result.hits:
                head = f"{len(result.hits)} 人在黑名单里"
            else:
                head = "这间大厅里没有黑名单"
            unclear = sum(1 for slot in result.names if slot.unclear)
            if unclear:
                head += f"，{unclear} 人没看清"
            self.summary.setText(head)
            hits = {}
            for hit in result.hits:
                hits.setdefault(hit.index, hit)
            grid = QGridLayout()
            grid.setHorizontalSpacing(8)
            grid.setVerticalSpacing(8)
            for slot in result.names:
                cell = QLabel()
                cell.setMinimumWidth(200)
                base = f'font-family: "{chinese_family()}"; border-radius: 8px; padding: 8px 12px;'
                if slot.unclear:
                    cell.setText("未看清")
                    cell.setStyleSheet(base + f' color: {THEME["gray"]}; background: {THEME["surface"]}; font-style: italic;')
                elif slot.index in hits:
                    hit = hits[slot.index]
                    shown = split_ellipsis(slot.visible)[0] or slot.visible
                    listed = "" if fold(hit.entry_name) == fold(shown) else f"　名单：{hit.entry_name}"
                    cell.setText(shown + listed)
                    cell.setStyleSheet(base + f' color: {THEME["red"]}; background: {THEME["red_wash"]};')
                else:
                    cell.setText(split_ellipsis(slot.visible)[0] or slot.visible)
                    cell.setStyleSheet(base + f' color: {THEME["text"]}; background: {THEME["surface"]};')
                grid.addWidget(cell, slot.index // 2, slot.index % 2)
                self.seats.append(cell)
            layout.addLayout(grid)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close = QPushButton("关闭")
        close.setObjectName("primary")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self.setMinimumWidth(460)
        _pointing(self)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)


class GuideDialog(QDialog):
    """Shown once on a new PC: what the app does and the three things to set up."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.wants_test = False
        self.setWindowTitle("欢迎使用黑名单检测")
        self.setFont(chinese_font())
        self.setStyleSheet(_dialog_style(chinese_family()))
        _caption_color(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(DIALOG_PAD, DIALOG_PAD, DIALOG_PAD, DIALOG_PAD)
        layout.setSpacing(GAP)
        intro = QLabel("进入「推演成功」大厅时，它会读出十二个名字，并标出黑名单里的人。只读屏幕，不碰游戏。")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        steps = (
            "1. 在「设置」里填上你的角色名称，记录里会标出你自己。",
            "2. 在「黑名单」里添加名字，或用「批量添加」粘贴朋友分享的名单。",
            "3. 进游戏就好。有黑名单的人时，「准备案件还原」按钮会被标红，旁边列出名字。",
        )
        for text in steps:
            step = QLabel(text)
            step.setObjectName("sub")
            step.setWordWrap(True)
            layout.addWidget(step)
        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        buttons.addStretch(1)
        test = QPushButton("测试一下")
        test.setAutoDefault(False)
        test.setToolTip("用自带的大厅截图试一次识别")
        test.clicked.connect(self._test)
        buttons.addWidget(test)
        start = QPushButton("开始使用")
        start.setObjectName("primary")
        start.setDefault(True)
        start.clicked.connect(self.accept)
        buttons.addWidget(start)
        layout.addLayout(buttons)
        self.setMinimumWidth(600)
        _pointing(self)

    def _test(self) -> None:
        self.wants_test = True
        self.accept()

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)


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


def _qt_key_name(key: int) -> str | None:
    if Qt.Key_A <= key <= Qt.Key_Z or Qt.Key_0 <= key <= Qt.Key_9:
        return chr(key)
    if Qt.Key_F1 <= key <= Qt.Key_F12:
        return f"F{key - Qt.Key_F1 + 1}"
    return None


class CheckWorker(QThread):
    """Owns the OCR engine. Paddle is loaded on this thread and reused here."""

    done = Signal(object)
    placed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._queue: queue.Queue = queue.Queue()
        self.running_job = False

    def request(self, fn, kind: str = "check") -> bool:
        if self.running_job:
            return False
        self.running_job = True
        self._queue.put((kind, fn))
        if not self.isRunning():
            self.start()
        return True

    def run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            kind, fn = item
            try:
                self.done.emit((kind, "ok", fn()))
            except Exception as exc:
                self.done.emit((kind, "err", exc))

    def stop(self) -> None:
        self._queue.put(None)


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


class WarningWindow(QWidget):
    """Small topmost notice. It does not take keyboard focus."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.Window
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setWindowTitle("黑名单玩家")
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(DIALOG_PAD, DIALOG_PAD, DIALOG_PAD, DIALOG_PAD)
        layout.setSpacing(GAP)
        title = QLabel("黑名单玩家")
        title.setObjectName("warnTitle")
        layout.addWidget(title)
        self.body = QPlainTextEdit()
        self.body.setReadOnly(True)
        self.body.setFocusPolicy(Qt.NoFocus)
        self.body.setMinimumWidth(420)
        layout.addWidget(self.body)
        close = QPushButton("关闭")
        close.setFocusPolicy(Qt.NoFocus)
        close.clicked.connect(self.close)
        layout.addWidget(close, 0, Qt.AlignLeft)
        self.setFont(chinese_font())
        self.body.setFont(chinese_font(READ_PT))
        self.apply_theme()
        _pointing(self)

    def apply_theme(self) -> None:
        family = chinese_family()
        t = THEME
        self.setStyleSheet(
            f"""
            QWidget {{ background: {t["bg"]}; color: {t["text"]}; font-family: "{family}"; }}
            QLabel#warnTitle {{
                color: {t["red"]};
                font-family: "{family}";
                font-size: 15pt;
                font-weight: 400;
                background: transparent;
            }}
            QPlainTextEdit {{
                background: {t["surface"]};
                color: {t["text"]};
                border: 1px solid {t["line"]};
                border-radius: 12px;
                padding: 12px 16px;
                font-family: "{family}";
                font-size: 13pt;
            }}
            """ + _button_rules(family)
        )

    def present(self, lines: list[str]) -> None:
        self.body.setPlainText("\n".join(lines))
        self.adjustSize()
        screen = QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.move(area.right() - self.width() - 28, area.top() + 28)
        self.show()
        self._pin_without_focus()

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)
        self._pin_without_focus()

    def _pin_without_focus(self) -> None:
        _pin_topmost(self)


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


class ClearWindow(QWidget):
    """Topmost green notice when the lobby has nobody on the blacklist."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.Window
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setWindowTitle("没有发现黑名单")
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(DIALOG_PAD, DIALOG_PAD, DIALOG_PAD, DIALOG_PAD)
        layout.setSpacing(GAP)
        title = QLabel("没有发现黑名单")
        title.setObjectName("clearTitle")
        layout.addWidget(title)
        card = QWidget()
        card.setObjectName("noticeCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        self.detail = QLabel("本局没有黑名单玩家。")
        self.detail.setObjectName("clearDetail")
        self.detail.setWordWrap(True)
        self.detail.setMinimumWidth(360)
        card_layout.addWidget(self.detail)
        layout.addWidget(card)
        close = QPushButton("关闭")
        close.setFocusPolicy(Qt.NoFocus)
        close.clicked.connect(self.close)
        layout.addWidget(close, 0, Qt.AlignLeft)
        self.setFont(chinese_font())
        self.apply_theme()
        _pointing(self)

    def apply_theme(self) -> None:
        family = chinese_family()
        t = THEME
        self.setStyleSheet(
            f"""
            QWidget {{ background: {t["bg"]}; color: {t["text"]}; font-family: "{family}"; }}
            QLabel#clearTitle {{
                color: {t["green"]};
                font-family: "{family}";
                font-size: 15pt;
                font-weight: 400;
                background: transparent;
            }}
            QLabel#clearDetail {{
                color: {t["text"]};
                font-family: "{family}";
                font-size: 13pt;
                background: transparent;
            }}
            """ + _card_rules() + _button_rules(family)
        )

    def present(self, detail: str) -> None:
        self.detail.setText(detail)
        self.adjustSize()
        screen = QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.move(area.right() - self.width() - 28, area.top() + 28)
        self.show()
        self._pin_without_focus()

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)
        self._pin_without_focus()

    def _pin_without_focus(self) -> None:
        _pin_topmost(self)


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


class MainWindow(QMainWindow):
    uncaught = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.uncaught.connect(self._show_uncaught)
        self.setWindowTitle(f"黑名单检测 {__version__}")
        self.store = Store()
        use_theme(self.store.theme)
        self.setMinimumSize(900, 560)
        saved = self.store.window_size or (900, 560)
        self.resize(saved[0], saved[1])
        self.setWindowIcon(_icon())
        self.hotkey = GlobalHotkey(self.check_now)
        self.worker = CheckWorker()
        self.worker.done.connect(self._on_worker)
        self.worker.placed.connect(self._on_lobby_placed)
        self.watch = LobbyWatch()
        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(GLANCE_INTERVAL_MS)
        self._watch_timer.timeout.connect(self._auto_tick)
        self._closing = False
        self.warning = WarningWindow()
        self.clear_notice = ClearWindow()
        self.panel = LobbyPanel()
        self.hit_card = HitCard()
        self.clear_mark = ClearMark()
        self._panel_hide_timer = QTimer(self)
        self._panel_hide_timer.setSingleShot(True)
        self._panel_hide_timer.timeout.connect(self._hide_panel_after_title)
        self._live_check = False
        self._rescan_active = False
        self._history_hover = (-1, -1)
        self._closed_days: set[str] = set()
        self._day_hover = -1
        self._check_started: float | None = None
        self._release_foreground = False
        self._told_tray = False
        self._manual_check = False
        self._problem = ""
        self._told_problems: set[str] = set()
        self._glance_pause_until = 0.0
        self._warm_started: float | None = None
        self._picture_pending = ""
        self._picture_dialog = None
        self.instance_server = None
        self._status_kind = "idle"
        self._watch_tone = "idle"
        self._watch_full = "未开启"
        self._watch_tip = ""
        self._blacklist_sort: tuple[int, bool] | None = None
        self._blacklist_hover = -1
        self._build()
        self._apply_style()
        _caption_color(self)
        self._show_list()
        self._reload_history()
        self._restore_hotkey()
        if self.store.auto_capture:
            app = QApplication.instance()
            if app is not None and app.platformName() == "offscreen":
                self._watch_timer.setInterval(60_000)
            self._watch_timer.start()
        self._sync_watch_idle()
        notice = self.store.load_warning or capture_capability_message()
        if notice:
            self._set_result(notice, "hit", "error")

    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(PAD, PAD, PAD, PAD)
        outer.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.history_tab = self.tabs.addTab(self._history_page(), "记录")
        self.blacklist_tab = self.tabs.addTab(self._list_page(), "黑名单")
        self.tabs.addTab(self._settings_page(), "设置")
        self.tabs.tabBar().hide()
        self.tabs.currentChanged.connect(self._sync_tab_buttons)
        header = QWidget()
        header.setObjectName("tabHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(0, 0, 0, 8)
        header_row.setSpacing(6)
        self._tab_buttons: list[QPushButton] = []
        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        for index in range(self.tabs.count()):
            button = QPushButton(self.tabs.tabText(index))
            button.setObjectName("tab")
            button.setFont(ui_font())
            button.setFixedHeight(28)
            button.setCheckable(True)
            button.setFocusPolicy(Qt.NoFocus)
            button.setCursor(Qt.PointingHandCursor)
            self._tab_group.addButton(button, index)
            self._tab_buttons.append(button)
            header_row.addWidget(button, 0, Qt.AlignVCenter)
        self._tab_group.idClicked.connect(self.tabs.setCurrentIndex)
        header_row.addStretch(1)
        self.mode_cluster = QWidget()
        self.mode_cluster.setObjectName("modeCluster")
        self.mode_cluster.setAttribute(Qt.WA_NoSystemBackground, True)
        self.mode_cluster.setAttribute(Qt.WA_TranslucentBackground, True)
        self.mode_cluster.setAutoFillBackground(False)
        self.mode_cluster.setMouseTracking(True)
        self.mode_cluster.setCursor(Qt.PointingHandCursor)
        cluster_row = QHBoxLayout(self.mode_cluster)
        cluster_row.setContentsMargins(0, 0, 0, 0)
        cluster_row.setSpacing(6)
        self.mode_cycle = QLabel()
        self.mode_cycle.setObjectName("modeCycle")
        self.mode_cycle.setFixedSize(16, 16)
        self.mode_cycle.setPixmap(_reload_icon())
        self.mode_cycle.setCursor(Qt.PointingHandCursor)
        self.mode_cycle.hide()
        self.watch_mark = QLabel()
        self.watch_mark.setPixmap(_watch_mark(THEME["muted"]))
        self.watch_mark.setCursor(Qt.PointingHandCursor)
        self.watch_label = QLabel("未开启")
        self.watch_label.setObjectName("idle")
        self.watch_label.setMaximumWidth(200)
        self.watch_label.setFont(chinese_font(READ_PT))
        self.watch_label.setCursor(Qt.PointingHandCursor)
        cluster_row.addWidget(self.mode_cycle, 0, Qt.AlignVCenter)
        cluster_row.addWidget(self.watch_label, 0, Qt.AlignVCenter)
        cluster_row.addWidget(self.watch_mark, 0, Qt.AlignVCenter)
        for widget in (self.mode_cluster, self.mode_cycle, self.watch_mark, self.watch_label):
            widget.setMouseTracking(True)
            widget.installEventFilter(self)
        header_row.addWidget(self.mode_cluster, 0, Qt.AlignVCenter)
        self._sync_tab_buttons(self.tabs.currentIndex())
        outer.addWidget(header)
        outer.addWidget(self.tabs)

        self.names_view = QPlainTextEdit()
        self.names_view.hide()

        self.tray = None
        if QSystemTrayIcon_available():
            from PySide6.QtWidgets import QSystemTrayIcon

            self.tray = QSystemTrayIcon(_icon(), self)
            self.tray.setToolTip(f"黑名单检测 {__version__}")
            self.tray_menu = QMenu()
            self.tray_menu.setFont(chinese_font())
            self.tray_menu.setStyleSheet(_menu_style(chinese_family()))
            self.tray_menu.addAction("打开", self._show_from_tray)
            self.tray_menu.addAction("退出", self.close)
            self.tray.setContextMenu(self.tray_menu)
            self.tray.activated.connect(self._on_tray)
            self.tray.show()

    def _list_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        _page(layout)
        add_row = QHBoxLayout()
        add_row.setSpacing(GAP)
        # A short report after a change, with 撤销 when the change can be taken back.
        self.list_notice = QWidget()
        notice_row = QHBoxLayout(self.list_notice)
        notice_row.setContentsMargins(0, 0, 0, 0)
        notice_row.setSpacing(8)
        self.list_notice_text = QLabel("")
        self.list_notice_text.setObjectName("sub")
        notice_row.addWidget(self.list_notice_text)
        self.list_undo = QPushButton("撤销")
        self.list_undo.setObjectName("recheck")
        self.list_undo.setFont(chinese_font(SMALL_PT))
        self.list_undo.setAutoDefault(False)
        self.list_undo.setCursor(Qt.PointingHandCursor)
        self.list_undo.clicked.connect(self._undo_last)
        notice_row.addWidget(self.list_undo)
        self.list_notice.hide()
        self._undo = None
        self._notice_timer = QTimer(self)
        self._notice_timer.setSingleShot(True)
        self._notice_timer.timeout.connect(self._hide_list_notice)
        add_row.addWidget(self.list_notice, 0, Qt.AlignVCenter)
        add_row.addStretch(1)
        self.share_button = QPushButton("分享")
        self.share_button.setToolTip("复制整个名单。朋友在「批量添加」里粘贴即可。")
        self.share_button.clicked.connect(self._share_list)
        add_row.addWidget(self.share_button)
        self.clear_list_button = QPushButton("清空列表")
        self.clear_list_button.clicked.connect(self._arm_clear_list)
        add_row.addWidget(self.clear_list_button)
        self.clear_list_pair = self._clear_confirm_pair(self._cancel_clear_list, self._confirm_clear_list)
        add_row.addWidget(self.clear_list_pair)
        batch = QPushButton("批量添加")
        batch.clicked.connect(self._add_many_by_dialog)
        add = QPushButton("添加")
        add.setObjectName("primary")
        add.clicked.connect(self._add_by_dialog)
        add_row.addWidget(batch)
        add_row.addWidget(add)
        self.blacklist_table = QTableWidget(0, 4)
        self.blacklist_table.setObjectName("blacklist")
        name_header = _ColumnHeader(self.blacklist_table)
        name_header.names_hidden = self.store.names_hidden
        name_header.on_eye = self._toggle_name_hiding
        self.blacklist_table.setHorizontalHeader(name_header)
        self.blacklist_table.setHorizontalHeaderLabels(["名字", "标签", "原因", "最后遇到"])
        for column in range(4):
            item = self.blacklist_table.horizontalHeaderItem(column)
            if item is not None:
                item.setToolTip("拖动换顺序，拖边缘改宽度")
        header = self.blacklist_table.horizontalHeader()
        header.setStretchLastSection(True)
        for column in range(4):
            header.setSectionResizeMode(column, header.ResizeMode.Interactive)
        header.setMinimumSectionSize(72)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionsClickable(True)
        header.setSectionsMovable(True)
        header.setHighlightSections(False)
        header.setSortIndicatorShown(False)
        header.sectionClicked.connect(self._sort_blacklist)
        header.sectionMoved.connect(self._save_column_order)
        header.sectionResized.connect(self._save_column_width)
        self._apply_column_widths()
        self._apply_column_order()
        self.blacklist_table.verticalHeader().setVisible(False)
        self.blacklist_table.verticalHeader().setDefaultSectionSize(44)
        self.blacklist_table.setSelectionMode(QTableWidget.SingleSelection)
        self.blacklist_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.blacklist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.blacklist_table.setShowGrid(False)
        self.blacklist_table.setAutoScroll(False)
        self.blacklist_table.setWordWrap(False)
        self.blacklist_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.blacklist_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.blacklist_table.setFocusPolicy(Qt.NoFocus)
        self.blacklist_table.setItemDelegate(_PlainItemDelegate(self.blacklist_table))
        self.blacklist_table.setMouseTracking(True)
        self.blacklist_table.viewport().setMouseTracking(True)
        self.blacklist_table.viewport().installEventFilter(self)
        self.blacklist_table.setCursor(Qt.PointingHandCursor)
        self.blacklist_table.cellEntered.connect(self._hover_blacklist_row)
        self.blacklist_table.cellClicked.connect(self._edit_row)
        self.detail_tip = _DetailTip()
        self.detail_tip.installEventFilter(self)
        self._detail_tip_timer = QTimer(self)
        self._detail_tip_timer.setSingleShot(True)
        self._detail_tip_timer.setInterval(160)
        self._detail_tip_timer.timeout.connect(self._hide_detail_tip)
        self.list_empty, self.list_hint = _empty_block("还没有名字")
        self.list_search = QLineEdit()
        self.list_search.setPlaceholderText("搜索名字、标签或原因")
        self.list_search.setClearButtonEnabled(True)
        self.list_search.textChanged.connect(lambda _text: self._show_list())
        layout.addWidget(self.list_search)
        layout.addWidget(self.blacklist_table, 1)
        layout.addWidget(self.list_empty, 1)
        layout.addLayout(add_row)
        return page

    def _history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        _page(layout)
        body = QHBoxLayout()
        body.setSpacing(GAP)
        side = QWidget()
        side.setFixedWidth(168)
        self.history_side = side
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(GAP)
        self.history_list = QListWidget()
        self.history_list.setObjectName("history")
        self.history_list.setFocusPolicy(Qt.NoFocus)
        self.history_list.setItemDelegate(_PlainItemDelegate(self.history_list))
        self.history_list.setCursor(Qt.PointingHandCursor)
        self.history_list.setMouseTracking(True)
        self.history_list.viewport().setMouseTracking(True)
        self.history_list.viewport().installEventFilter(self)
        self.history_list.currentRowChanged.connect(self._on_history_picked)
        self.history_list.itemClicked.connect(self._on_history_clicked)
        side_layout.addWidget(self.history_list, 1)
        self.clear_history_button = QPushButton("清空记录")
        self.clear_history_button.clicked.connect(self._arm_clear_history)
        side_layout.addWidget(self.clear_history_button)
        self.clear_history_pair = self._clear_confirm_pair(self._cancel_clear_history, self._confirm_clear_history)
        side_layout.addWidget(self.clear_history_pair)
        body.addWidget(side)
        record = QWidget()
        record.setObjectName("recordCard")
        record.setAttribute(Qt.WA_StyledBackground, True)
        self.record_card = record
        names = QVBoxLayout(record)
        names.setContentsMargins(0, 0, 0, 0)
        names.setSpacing(0)
        head_bar = QWidget()
        head_bar.setObjectName("tableHead")
        head_bar.setAttribute(Qt.WA_StyledBackground, True)
        head = QHBoxLayout(head_bar)
        head.setContentsMargins(16, 12, 16, 12)
        head.setSpacing(GAP)
        catalog = QLabel("模仿者游戏（12人狂欢场）")
        catalog.setFont(record_font())
        catalog.setStyleSheet(
            f'color: {THEME["text"]}; background: transparent; font-family: "{chinese_family()}"; font-size: 13pt;'
        )
        head.addWidget(catalog)
        head.addStretch(1)
        names.addWidget(head_bar)
        self.history_table = QTableWidget(0, 2)
        self.history_table.setObjectName("recordNames")
        self.history_table.horizontalHeader().setVisible(False)
        header = self.history_table.horizontalHeader()
        header.setStretchLastSection(True)
        for column in range(2):
            header.setSectionResizeMode(column, header.ResizeMode.Stretch)
        self.history_table.setCursor(Qt.PointingHandCursor)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.verticalHeader().setDefaultSectionSize(48)
        self.history_table.setSelectionMode(QTableWidget.NoSelection)
        self.history_table.setFocusPolicy(Qt.NoFocus)
        self.history_table.setItemDelegate(_PlainItemDelegate(self.history_table))
        self.history_table.setShowGrid(False)
        self.history_table.setMouseTracking(True)
        self.history_table.viewport().setMouseTracking(True)
        self.history_table.viewport().installEventFilter(self)
        self.history_table.cellEntered.connect(self._hover_history_cell)
        self.history_table.cellClicked.connect(self._on_history_cell)
        names.addWidget(self.history_table, 1)
        body.addWidget(record, 1)
        self.history_empty, self.history_hint = _empty_block("还没有记录")
        empty_column = self.history_empty.layout()
        explain = QLabel("进入「推演成功」大厅时会自动检查，并记在这里。")
        explain.setObjectName("sub")
        explain.setAlignment(Qt.AlignCenter)
        explain.setWordWrap(True)
        empty_column.insertSpacing(2, 8)
        empty_column.insertWidget(3, explain)
        self.history_test_button = QPushButton("测试一下")
        self.history_test_button.setToolTip("用自带的大厅截图试一次识别，不用进游戏")
        self.history_test_button.setAutoDefault(False)
        self.history_test_button.clicked.connect(self.test_recognition)
        empty_column.insertSpacing(4, GAP)
        empty_column.insertWidget(5, self.history_test_button, 0, Qt.AlignHCenter)
        body.addWidget(self.history_empty, 1)
        layout.addLayout(body, 1)
        return page

    def _settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        _page(layout)
        layout.setSpacing(0)
        metrics = QFontMetrics(chinese_font())
        name_width = metrics.horizontalAdvance("中" * 7) + 28
        slot = metrics.horizontalAdvance("手动检查") + 36
        label_width = metrics.horizontalAdvance("角色名称") + 8

        def add_row(last: bool = False) -> QHBoxLayout:
            host = QWidget()
            host.setObjectName("settingsRowLast" if last else "settingsRow")
            host.setAttribute(Qt.WA_StyledBackground, True)
            line = QHBoxLayout(host)
            line.setContentsMargins(0, 16, 0, 16)
            line.setSpacing(16)
            layout.addWidget(host)
            return line

        def add_label(line: QHBoxLayout, text: str, align: Qt.AlignmentFlag = Qt.AlignVCenter) -> None:
            label = QLabel(text)
            label.setObjectName("sub")
            label.setFixedWidth(label_width)
            line.addWidget(label, 0, align)

        name_line = add_row()
        add_label(name_line, "角色名称")
        self.player_edit = QLineEdit(self.store.player_name)
        self.player_edit.setPlaceholderText("游戏里的名字")
        self.player_edit.editingFinished.connect(self._save_player_name)
        self.player_edit.setFixedWidth(name_width)
        name_line.addWidget(self.player_edit, 0, Qt.AlignVCenter)
        name_line.addStretch(1)

        mode_line = add_row()
        add_label(mode_line, "检查")
        modes = QHBoxLayout()
        modes.setSpacing(GAP)
        modes.setContentsMargins(0, 0, 0, 0)
        self.auto_on = QPushButton("自动检查")
        self.auto_off = QPushButton("手动检查")
        self.auto_group = QButtonGroup(self)
        self.auto_group.setExclusive(True)
        for button in (self.auto_on, self.auto_off):
            button.setObjectName("mode")
            button.setCheckable(True)
            button.setFixedWidth(slot)
            button.setFocusPolicy(Qt.NoFocus)
            button.setCursor(Qt.PointingHandCursor)
            button.setAutoDefault(False)
            self.auto_group.addButton(button)
            modes.addWidget(button)
        self.hotkey_edit = QLineEdit()
        self.hotkey_edit.setReadOnly(True)
        self.hotkey_edit.setPlaceholderText("无")
        self.hotkey_edit.setFixedWidth(slot)
        self.hotkey_edit.setCursor(Qt.PointingHandCursor)
        self.hotkey_edit.installEventFilter(self)
        modes.addWidget(self.hotkey_edit)
        self.auto_on.setChecked(self.store.auto_capture)
        self.auto_off.setChecked(not self.store.auto_capture)
        self.auto_on.clicked.connect(lambda: self._toggle_auto(True))
        self.auto_off.clicked.connect(lambda: self._toggle_auto(False))
        mode_line.addLayout(modes)
        mode_line.addStretch(1)

        read_line = add_row()
        add_label(read_line, "识别")
        self.test_button = QPushButton("测试一下")
        self.test_button.setToolTip("用自带的大厅截图试一次识别，不用进游戏")
        self.test_button.setFixedWidth(slot)
        self.test_button.setAutoDefault(False)
        self.test_button.clicked.connect(self.test_recognition)
        self.picture_button = QPushButton("检查截图")
        self.picture_button.setToolTip("选一张大厅截图，看看里面有没有黑名单")
        self.picture_button.setFixedWidth(slot)
        self.picture_button.setAutoDefault(False)
        self.picture_button.clicked.connect(self.check_picture)
        read_line.addWidget(self.test_button, 0, Qt.AlignVCenter)
        read_line.addWidget(self.picture_button, 0, Qt.AlignVCenter)
        read_line.addStretch(1)

        sound_line = add_row()
        add_label(sound_line, "提示音")
        self.sound_on = QPushButton("开")
        self.sound_off = QPushButton("关")
        self.sound_group = QButtonGroup(self)
        self.sound_group.setExclusive(True)
        for button in (self.sound_on, self.sound_off):
            button.setObjectName("mode")
            button.setCheckable(True)
            button.setFixedWidth(slot)
            button.setFocusPolicy(Qt.NoFocus)
            button.setCursor(Qt.PointingHandCursor)
            button.setAutoDefault(False)
            self.sound_group.addButton(button)
            sound_line.addWidget(button, 0, Qt.AlignVCenter)
        self.sound_on.setToolTip("发现黑名单时响一声")
        self.sound_on.setChecked(self.store.hit_sound)
        self.sound_off.setChecked(not self.store.hit_sound)
        self.sound_on.clicked.connect(lambda: self._set_hit_sound(True))
        self.sound_off.clicked.connect(lambda: self._set_hit_sound(False))
        sound_line.addStretch(1)

        theme_line = add_row()
        add_label(theme_line, "主题")
        swatches = QHBoxLayout()
        swatches.setSpacing(8)
        swatches.setContentsMargins(0, 0, 0, 0)
        self.theme_buttons: dict[str, ThemeSwatch] = {}
        for name in THEMES:
            swatch = ThemeSwatch(name, THEMES[name]["gold"], lambda picked=name: self._set_theme(picked))
            self.theme_buttons[name] = swatch
            swatches.addWidget(swatch, 0, Qt.AlignVCenter)
        theme_line.addLayout(swatches)
        theme_line.addStretch(1)

        tag_line = add_row()
        add_label(tag_line, "标签", Qt.AlignTop)
        self.tag_settings = QVBoxLayout()
        self.tag_settings.setSpacing(0)
        self.tag_settings.setContentsMargins(0, 0, 0, 0)
        self._fill_tag_settings()
        tag_line.addLayout(self.tag_settings, 1)
        recheck = QPushButton("按原因补标签")
        recheck.setObjectName("recheck")
        recheck.setFont(chinese_font(SMALL_PT))
        recheck.setAutoDefault(False)
        recheck.setCursor(Qt.PointingHandCursor)
        recheck.clicked.connect(self._recheck_tags)
        tag_line.addWidget(recheck, 0, Qt.AlignTop)

        reset_line = add_row()
        add_label(reset_line, "控制")
        reset = QPushButton("清除数据且复原")
        reset.setObjectName("danger")
        reset.setFont(ui_font())
        self.reset_button = reset
        reset.setAutoDefault(False)
        reset.setCursor(Qt.PointingHandCursor)
        reset.clicked.connect(self._ask_reset)
        reset_line.addWidget(reset, 0, Qt.AlignVCenter)
        reset_line.addStretch(1)

        version_line = add_row(last=True)
        add_label(version_line, "版本")
        version = QLabel(__version__)
        version_line.addWidget(version, 0, Qt.AlignVCenter)
        version_line.addStretch(1)

        self.settings_label = QLabel("")
        self.settings_label.setObjectName("sub")
        self.settings_label.setWordWrap(True)
        self.settings_label.hide()
        layout.addWidget(self.settings_label)
        layout.addStretch(1)
        return page

    def _fill_tag_settings(self) -> None:
        while self.tag_settings.count():
            item = self.tag_settings.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        host = _FlowHost()
        host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        flow = _FlowLayout(host, gap=6)
        for tag in self.store.tag_catalog():
            flow.addWidget(TagPill(tag, on_click=lambda picked=tag: self._edit_settings_tag(picked)))
        create = NewTagButton()
        create.clicked.connect(self._create_settings_tag)
        flow.addWidget(create)
        self.tag_settings.addWidget(host)

    def _recheck_tags(self) -> None:
        self.store.recheck_tags()
        self._show_list()

    def _create_settings_tag(self) -> None:
        dialog = TagCreateDialog(self.store.tag_catalog(), parent=self)
        if dialog.exec() != QDialog.Accepted or not dialog.created:
            return
        if not self.store.add_custom_tag(dialog.created):
            return
        self.store.save_settings()
        self._fill_tag_settings()

    def _edit_settings_tag(self, tag: str) -> None:
        dialog = TagEditDialog(tag, self.store.tag_catalog(), parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        if dialog.deleted:
            if self.store.remove_custom_tag(tag):
                self._refresh_tag_views()
            return
        if dialog.renamed == tag:
            return
        if self.store.rename_tag(tag, dialog.renamed) == "renamed":
            self._refresh_tag_views()

    def _refresh_tag_views(self) -> None:
        self._fill_tag_settings()
        self._show_list()
        self._show_history_scan(self._selected_scan())

    def _remove_settings_tag(self, tag: str) -> None:
        names = [entry.name for entry in self.store.entries if tag in entry.tags]
        if not names:
            text = f"没有名字使用「{tag}」。确定删除？"
        else:
            shown = "、".join(names[:6])
            if len(names) > 6:
                shown += "等"
            text = f"{len(names)} 个名字使用「{tag}」：{shown}。确定删除？"
        if not _confirm(self, text):
            return
        if not self.store.remove_custom_tag(tag):
            return
        self._refresh_tag_views()

    def _set_settings_note(self, text: str) -> None:
        self.settings_label.setText(text)
        self.settings_label.setVisible(bool(text))

    def _ask_reset(self) -> None:
        if not _confirm(self, "清除数据且复原会清空角色名称、记录、黑名单和设置。确定清除？"):
            return
        self.store.reset()
        self.hotkey.clear()
        self.player_edit.setText("")
        self.hotkey_edit.clearFocus()
        self._show_hotkey()
        self._sync_hotkey_mode()
        self._set_settings_note("")
        self.auto_on.setChecked(True)
        self.auto_off.setChecked(False)
        self.sound_off.setChecked(True)
        if not self._watch_timer.isActive():
            self.watch = LobbyWatch()
            self._watch_timer.start()
        self._sync_watch_idle()
        use_theme(self.store.theme)
        icon = _icon()
        self.setWindowIcon(icon)
        if self.tray is not None:
            self.tray.setIcon(icon)
        self._apply_style()
        _caption_color(self)
        self.warning.apply_theme()
        self.clear_notice.apply_theme()
        self._apply_column_widths()
        self._apply_column_order()
        self._panel_hide_timer.stop()
        self.panel.hide()
        self.hit_card.hide()
        self.clear_mark.hide()
        self._reload_history()

    def _save_player_name(self) -> None:
        name = self.player_edit.text().strip()
        if name == self.store.player_name:
            return
        self.store.player_name = name
        self.store.save_settings()
        self._show_history_scan(self._selected_scan())

    def _is_my_name(self, shown: str) -> bool:
        mine = self.store.player_name
        if not mine or not shown:
            return False
        return bool(match_label(NameLabel(raw=shown, visible=shown, truncated=False), [Entry(mine)]))

    def _apply_style(self) -> None:
        _apply_theme()
        self.setFont(chinese_font())
        self.setStyleSheet(_window_style(chinese_family()))
        self.setFont(chinese_font())
        for button in getattr(self, "_tab_buttons", []):
            button.setFont(ui_font())
        if getattr(self, "reset_button", None) is not None:
            self.reset_button.setFont(ui_font())
        _pointing(self)
        self._mark_theme_buttons()
        if hasattr(self, "tag_settings"):
            self._fill_tag_settings()
        if hasattr(self, "watch_label"):
            self._set_result(self._watch_full, self._watch_tone, self._status_kind, self._watch_tip)
        if hasattr(self, "mode_cycle"):
            self.mode_cycle.setPixmap(_reload_icon())
        if hasattr(self, "warning"):
            self.warning.apply_theme()
            self.clear_notice.apply_theme()
        if hasattr(self, "detail_tip"):
            self.detail_tip.apply_theme()

    def _mark_theme_buttons(self) -> None:
        for name, swatch in self.theme_buttons.items():
            swatch.set_selected(name == self.store.theme)

    def _set_theme(self, name: str) -> None:
        if name not in THEMES or name == self.store.theme:
            self._mark_theme_buttons()
            return
        self.store.theme = name
        self.store.save_settings()
        use_theme(name)
        icon = _icon()
        self.setWindowIcon(icon)
        if self.tray is not None:
            self.tray.setIcon(icon)
        self._apply_style()
        _caption_color(self)
        self.warning.apply_theme()
        self.clear_notice.apply_theme()
        self._reload_history(max(0, self._selected_scan()))
        self._show_list()

    def _filter_mode_cluster(self, watched, event) -> bool:  # noqa: ANN001
        cycle = getattr(self, "mode_cycle", None)
        cluster = getattr(self, "mode_cluster", None)
        if cycle is None or cluster is None or not hasattr(self, "watch_label"):
            return False
        if watched not in (cluster, cycle, self.watch_mark, self.watch_label):
            return False
        kind = event.type()
        if kind in (QEvent.Type.Enter, QEvent.Type.HoverEnter):
            cycle.show()
        elif kind in (QEvent.Type.Leave, QEvent.Type.HoverLeave) and not self._pointer_over_mode_cluster():
            cycle.hide()
        elif kind == QEvent.Type.MouseButtonPress and event.button() == Qt.LeftButton:
            self._cycle_capture_mode()
            return True
        return False

    def _pointer_over_mode_cluster(self) -> bool:
        cluster = self.mode_cluster
        if not cluster.isVisible():
            return False
        pos = cluster.mapFromGlobal(QCursor.pos())
        return cluster.rect().adjusted(-2, -2, 2, 2).contains(pos)

    def eventFilter(self, watched, event) -> bool:  # noqa: ANN001
        if getattr(self, "_closing", False):
            # Child widgets are being torn down. Touching them now raises.
            return False
        if self._filter_mode_cluster(watched, event):
            return True
        edit = getattr(self, "hotkey_edit", None)
        if edit is not None and watched is edit:
            kind = event.type()
            if kind == QEvent.Type.FocusIn:
                if not self.store.auto_capture:
                    self._begin_hotkey()
            elif kind == QEvent.Type.FocusOut:
                self._end_hotkey()
            elif kind == QEvent.Type.KeyPress and event.key() not in (Qt.Key_Tab, Qt.Key_Backtab):
                if not self.store.auto_capture:
                    self._take_hotkey(event)
                return True
        table = getattr(self, "history_table", None)
        if table is not None and watched is table.viewport() and event.type() == QEvent.Type.Leave:
            self._clear_history_hover()
        history = getattr(self, "history_list", None)
        if history is not None and watched is history.viewport():
            if event.type() == QEvent.Type.Leave:
                self._hover_day_folder(-1)
            elif event.type() == QEvent.Type.MouseMove:
                self._hover_day_folder(history.indexAt(event.position().toPoint()).row())
        names = getattr(self, "blacklist_table", None)
        if names is not None and watched is names.viewport():
            if event.type() == QEvent.Type.Leave:
                self._clear_blacklist_hover()
                self._schedule_detail_tip_hide()
            elif event.type() == QEvent.Type.MouseMove:
                index = names.indexAt(event.position().toPoint())
                if index.isValid():
                    self._sync_detail_tip(index.row(), index.column())
            elif event.type() == QEvent.Type.Resize:
                self._fit_blacklist_columns()
        tip = getattr(self, "detail_tip", None)
        if tip is not None and watched is tip:
            if event.type() == QEvent.Type.Enter:
                self._detail_tip_timer.stop()
            elif event.type() == QEvent.Type.Leave:
                self._schedule_detail_tip_hide()
        if watched.property("scanRow") is not None:
            button = watched.findChild(QPushButton, "rowDelete")
            kind = event.type()
            if button is not None and kind == QEvent.Type.Enter:
                button.show()
            elif button is not None and kind == QEvent.Type.Leave:
                button.hide()
            elif kind == QEvent.Type.MouseButtonPress and event.button() == Qt.LeftButton:
                scan = int(watched.property("scanRow"))
                for row in range(self.history_list.count()):
                    item = self.history_list.item(row)
                    if item.data(Qt.UserRole) == scan and not item.isHidden():
                        self.history_list.setCurrentRow(row)
                        break
        return super().eventFilter(watched, event)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)
        self._remember_size()

    def _tag_cell(self, tags: tuple[str, ...] | list[str]) -> QWidget:
        return _TagRow(tags)

    def _list_cell(self, text: str, store_index: int | None = None) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setFont(chinese_font(READ_PT))
        item.setForeground(QColor(THEME["text"]))
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        if store_index is not None:
            item.setData(Qt.UserRole, store_index)
        return item

    def _sort_stamp(self, entry: Entry, column: int) -> float | None:
        if column != 3:
            return None
        for scan in self.store.scans:
            for seat in scan.get("names", []):
                if seat.get("unclear") or not str(seat.get("name") or ""):
                    continue
                shown = str(seat["name"])
                if match_label(NameLabel(raw=shown, visible=shown, truncated=False), [entry]):
                    moment = _local_moment(str(scan.get("at", "")))
                    return None if moment is None else moment.timestamp()
        return None

    def _search_text(self) -> str:
        search = getattr(self, "list_search", None)
        return search.text().strip() if search is not None else ""

    def _ordered_entries(self) -> list[tuple[int, Entry]]:
        rows = list(enumerate(self.store.entries))
        query = self._search_text()
        if query:
            folded = fold(query)
            lowered = query.casefold()

            def hit(entry: Entry) -> bool:
                if folded and folded in fold(entry.name):
                    return True
                if any(lowered in tag.casefold() for tag in entry.tags):
                    return True
                return lowered in entry.reason.casefold()

            rows = [pair for pair in rows if hit(pair[1])]
        if self._blacklist_sort is None:
            return rows
        column, newest = self._blacklist_sort

        def key(pair: tuple[int, Entry]) -> tuple[bool, float, int]:
            index, entry = pair
            stamp = self._sort_stamp(entry, column)
            if stamp is None:
                return (True, 0.0, index)
            return (False, -stamp if newest else stamp, index)

        return sorted(rows, key=key)

    def _column_labels(self) -> list[str]:
        header = self.blacklist_table.horizontalHeader()
        return [
            self.blacklist_table.horizontalHeaderItem(header.logicalIndex(visual)).text()
            for visual in range(header.count())
        ]

    def _apply_column_widths(self) -> None:
        header = self.blacklist_table.horizontalHeader()
        widths = self.store.column_widths
        if len(widths) != header.count():
            return
        header.blockSignals(True)
        for logical, width in enumerate(widths):
            self.blacklist_table.setColumnWidth(logical, width)
        header.blockSignals(False)
        self._fit_blacklist_columns()

    def _fit_blacklist_columns(self, prefer: int | None = None) -> None:
        """Keep every column inside the list. Extra width comes out of the last column."""
        table = getattr(self, "blacklist_table", None)
        if table is None or getattr(self, "_fitting_columns", False):
            return
        header = table.horizontalHeader()
        available = table.viewport().width()
        count = header.count()
        minimum = header.minimumSectionSize()
        if count == 0 or available < minimum:
            return
        logicals = [header.logicalIndex(visual) for visual in range(count)]
        if prefer is None:
            saved = self.store.column_widths
            if len(saved) != count:
                saved = [header.sectionSize(index) for index in range(count)]
            sizes = [max(minimum, saved[logical]) for logical in logicals]
        else:
            sizes = [max(minimum, header.sectionSize(logical)) for logical in logicals]
        others = sizes[:-1]
        overflow = sum(others) + minimum - available
        if overflow > 0 and prefer is not None and prefer in logicals[:-1]:
            index = logicals.index(prefer)
            spare = others[index] - minimum
            cut = min(max(spare, 0), overflow)
            others[index] -= cut
            overflow -= cut
        if overflow > 0:
            for index in range(len(others) - 1, -1, -1):
                spare = others[index] - minimum
                if spare <= 0:
                    continue
                cut = min(spare, overflow)
                others[index] -= cut
                overflow -= cut
                if overflow <= 0:
                    break
        room = available - sum(others)
        if room < minimum:
            room = minimum
        target = [*others, max(minimum, room)]
        self._fitting_columns = True
        header.blockSignals(True)
        try:
            for logical, size in zip(logicals, target, strict=True):
                if header.sectionSize(logical) != size:
                    table.setColumnWidth(logical, size)
                visual = header.visualIndex(logical)
                if (
                    prefer is not None
                    and visual != count - 1
                    and 0 <= logical < len(self.store.column_widths)
                ):
                    self.store.column_widths[logical] = size
        finally:
            header.blockSignals(False)
            self._fitting_columns = False

    def _save_column_width(self, logical: int, _old: int, new: int) -> None:
        header = self.blacklist_table.horizontalHeader()
        if getattr(self, "_fitting_columns", False):
            return
        if header.visualIndex(logical) == header.count() - 1:
            return
        if not 0 <= logical < len(self.store.column_widths) or self.store.column_widths[logical] == new:
            return
        self.store.column_widths[logical] = new
        self._fit_blacklist_columns(prefer=logical)
        self.store.save_settings()

    def _apply_column_order(self) -> None:
        header = self.blacklist_table.horizontalHeader()
        order = self.store.column_order
        if sorted(order) != list(range(header.count())):
            return
        header.blockSignals(True)
        for visual, logical in enumerate(order):
            current = header.visualIndex(logical)
            if current != visual:
                header.moveSection(current, visual)
        header.blockSignals(False)
        self._fit_blacklist_columns()

    def _save_column_order(self, _logical: int = 0, _old: int = 0, _new: int = 0) -> None:
        header = self.blacklist_table.horizontalHeader()
        order = [header.logicalIndex(visual) for visual in range(header.count())]
        if order == self.store.column_order:
            return
        self.store.column_order = order
        self.store.save_settings()
        self._fit_blacklist_columns()

    def _sort_blacklist(self, column: int) -> None:
        if column != 3:
            return
        newest = self._blacklist_sort != (column, True)
        self._blacklist_sort = (column, newest)
        header = self.blacklist_table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(column, Qt.DescendingOrder if newest else Qt.AscendingOrder)
        self._show_list()

    def _last_met_all(self) -> dict[int, str]:
        """When each listed name was last seen, from one pass over the records (newest first)."""
        found: dict[int, str] = {}
        by_id = {id(entry): index for index, entry in enumerate(self.store.entries)}
        for scan in self.store.scans:
            for seat in scan.get("names", []):
                if seat.get("unclear") or not str(seat.get("name") or ""):
                    continue
                shown = str(seat["name"])
                for match in match_label(NameLabel(raw=shown, visible=shown, truncated=False), self.store.entries):
                    index = by_id.get(id(match.entry))
                    if index is not None and index not in found:
                        found[index] = _zh_ago(str(scan.get("at", "")))
            if len(found) == len(self.store.entries):
                break
        return found

    def _show_list(self) -> None:
        rows = self._ordered_entries()
        met = self._last_met_all()
        bar = self.blacklist_table.verticalScrollBar()
        position = bar.value()
        self.blacklist_table.setRowCount(len(rows))
        for row, (index, entry) in enumerate(rows):
            shown = masked_name(entry.name) if self.store.names_hidden else entry.name
            self.blacklist_table.setItem(row, 0, self._list_cell(shown, index))
            tags_item = self._list_cell(tag_text(entry))
            tags_item.setToolTip(tag_text(entry))
            self.blacklist_table.setItem(row, 1, tags_item)
            self.blacklist_table.setCellWidget(row, 1, self._tag_cell(entry.tags))
            detail = " ".join(entry.reason.split())
            self.blacklist_table.setItem(row, 2, self._list_cell(detail))
            self.blacklist_table.setItem(row, 3, self._list_cell(met.get(index, "")))
            self.blacklist_table.setRowHeight(row, 44)
        self._blacklist_hover = -1
        self.blacklist_table.setCurrentCell(-1, -1)
        bar.setValue(position)
        self._hide_detail_tip()
        self._refresh_blacklist_tab()
        count = len(self.store.entries)
        self.list_search.setVisible(count > 0 or bool(self._search_text()))
        self.share_button.setVisible(count > 0)
        if count and rows:
            self.list_empty.hide()
            self.blacklist_table.setVisible(True)
            if self.clear_list_pair.isHidden():
                self.clear_list_button.show()
        elif count:
            self.list_hint.setText(f"没有找到「{self._search_text()}」")
            self.list_empty.show()
            self.blacklist_table.setVisible(False)
            if self.clear_list_pair.isHidden():
                self.clear_list_button.show()
        else:
            self.list_hint.setText("还没有名字")
            self.list_empty.show()
            self.blacklist_table.setVisible(False)
            self.clear_list_button.hide()
            self.clear_list_pair.hide()

    def _reason_for_row(self, row: int) -> str:
        item = self.blacklist_table.item(row, 0)
        if item is None or item.data(Qt.UserRole) is None:
            return ""
        index = int(item.data(Qt.UserRole))
        if not 0 <= index < len(self.store.entries):
            return ""
        return self.store.entries[index].reason

    def _toggle_name_hiding(self, hidden: bool) -> None:
        self.store.names_hidden = bool(hidden)
        header = self.blacklist_table.horizontalHeader()
        if isinstance(header, _ColumnHeader):
            header.names_hidden = self.store.names_hidden
            header.viewport().update()
        self.store.save_settings()
        self._show_list()

    def _sync_detail_tip(self, row: int, column: int) -> None:
        text = self._reason_for_row(row) if column == 2 else ""
        if not text.strip():
            self._hide_detail_tip()
            return
        self._detail_tip_timer.stop()
        rect = self.blacklist_table.visualRect(self.blacklist_table.model().index(row, 2))
        anchor = self.blacklist_table.viewport().mapToGlobal(rect.bottomLeft())
        self.detail_tip.show_reason(text, anchor)

    def _schedule_detail_tip_hide(self) -> None:
        tip = getattr(self, "detail_tip", None)
        if tip is None or not tip.isVisible():
            return
        if tip.geometry().contains(QCursor.pos()):
            self._detail_tip_timer.stop()
            return
        self._detail_tip_timer.start()

    def _hide_detail_tip(self) -> None:
        tip = getattr(self, "detail_tip", None)
        if tip is None:
            return
        self._detail_tip_timer.stop()
        tip.hide()

    def _hover_blacklist_row(self, row: int, column: int = 0) -> None:
        if row >= 0:
            self._sync_detail_tip(row, column)
        if row < 0:
            return
        if row == self._blacklist_hover:
            return
        bar = self.blacklist_table.verticalScrollBar()
        position = bar.value()
        self._blacklist_hover = row
        self.blacklist_table.selectRow(row)
        bar.setValue(position)

    def _clear_blacklist_hover(self) -> None:
        bar = self.blacklist_table.verticalScrollBar()
        position = bar.value()
        self._blacklist_hover = -1
        self.blacklist_table.clearSelection()
        self.blacklist_table.setCurrentCell(-1, -1)
        bar.setValue(position)

    def _set_tab_title(self, index: int, text: str) -> None:
        self.tabs.setTabText(index, text)
        if 0 <= index < len(self._tab_buttons):
            self._tab_buttons[index].setText(text)

    def _sync_tab_buttons(self, index: int) -> None:
        for button_index, button in enumerate(self._tab_buttons):
            button.setChecked(button_index == index)

    def _refresh_blacklist_tab(self) -> None:
        count = len(self.store.entries)
        self._set_tab_title(self.blacklist_tab, f"黑名单  {count}" if count else "黑名单")

    def _clear_confirm_pair(self, on_cancel, on_confirm) -> QWidget:
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        cancel = QPushButton("取消")
        cancel.setProperty("clearPair", True)
        cancel.setAutoDefault(False)
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(on_cancel)
        confirm = QPushButton("确认清空")
        confirm.setObjectName("danger")
        confirm.setProperty("clearPair", True)
        confirm.setAutoDefault(False)
        confirm.setCursor(Qt.PointingHandCursor)
        confirm.clicked.connect(on_confirm)
        row.addWidget(cancel)
        row.addWidget(confirm)
        host.hide()
        return host

    def _arm_clear_list(self) -> None:
        self.clear_list_button.hide()
        self.clear_list_pair.show()

    def _cancel_clear_list(self) -> None:
        self.clear_list_pair.hide()
        self.clear_list_button.show()

    def _confirm_clear_list(self) -> None:
        self._cancel_clear_list()
        before = self.store.snapshot_entries()
        self.store.clear_entries()
        self._list_changed()
        self._say(f"已清空 {len(before)} 人", undo=lambda: self._put_back(before))

    def _list_changed(self) -> None:
        self._show_list()
        self._show_history_scan(self._selected_scan())

    def _put_back(self, entries: list[Entry]) -> None:
        self.store.restore_entries(entries)
        self._refresh_tag_views()
        self._say("已撤销")

    def _say(self, text: str, undo=None) -> None:  # noqa: ANN001
        """Report a change under the list. 撤销 stays for eight seconds."""
        self._undo = undo
        self.list_notice_text.setText(text)
        self.list_undo.setVisible(undo is not None)
        self.list_notice.show()
        self._notice_timer.start(8000 if undo is not None else 4000)

    def _hide_list_notice(self) -> None:
        self._undo = None
        self.list_notice.hide()

    def _undo_last(self) -> None:
        undo = self._undo
        self._hide_list_notice()
        if undo is not None:
            undo()

    def _share_list(self) -> None:
        """Copy the whole list in the 批量添加 line format, so a friend can paste it."""
        from blacklist_detect.storage import share_text

        count = len(self.store.entries)
        if not count:
            return
        QApplication.clipboard().setText(share_text(self.store.entries))
        self._say(f"已复制 {count} 人。朋友在「批量添加」里粘贴即可。")

    def _add_by_dialog(self) -> None:
        dialog = AddNameDialog(catalog=self.store.tag_catalog(), parent=self, taken=self._taken_names())
        if dialog.exec() != QDialog.Accepted or dialog.deleted:
            return
        before = self.store.snapshot_entries()
        entry = self.store.add(dialog.name, dialog.detail, tags=dialog.tags)
        if entry is None:
            return
        self._list_changed()
        self._say(f"已添加「{entry.name}」", undo=lambda: self._put_back(before))

    def _add_many_by_dialog(self) -> None:
        dialog = BatchAddDialog(self.store.tag_catalog(), parent=self)
        if dialog.exec() != QDialog.Accepted or not dialog.names:
            return
        before = self.store.snapshot_entries()
        if dialog.annotated is None:
            added = self.store.add_names(dialog.names)
        else:
            added = self.store.add_annotated(dialog.annotated)
        skipped = len(dialog.names) - added
        if added == 0:
            self._say(f"这 {skipped} 个名字都已经在名单里")
            return
        # A shared list may bring tags this list has not seen. They now show in 设置.
        self._refresh_tag_views()
        text = f"已添加 {added} 人"
        if skipped:
            text += f"，{skipped} 个已在名单里没有重复添加"
        self._say(text, undo=lambda: self._put_back(before))

    def _taken_names(self, skip: int = -1) -> frozenset[str]:
        return frozenset(fold(entry.name) for index, entry in enumerate(self.store.entries) if index != skip)

    def _edit_row(self, row: int, _column: int = 0) -> None:
        item = self.blacklist_table.item(row, 0)
        if item is None or item.data(Qt.UserRole) is None:
            return
        self._edit_entry(int(item.data(Qt.UserRole)))

    def _edit_entry(self, index: int) -> None:
        if not 0 <= index < len(self.store.entries):
            return
        entry = self.store.entries[index]
        dialog = AddNameDialog(
            entry.name,
            entry.tags,
            entry.reason,
            title="修改",
            allow_delete=True,
            catalog=self.store.tag_catalog(),
            added_at=entry.added_at,
            parent=self,
            taken=self._taken_names(skip=index),
        )
        if dialog.exec() != QDialog.Accepted:
            return
        before = self.store.snapshot_entries()
        if dialog.deleted:
            self.store.remove_at(index)
            self._list_changed()
            self._say(f"已删除「{entry.name}」", undo=lambda: self._put_back(before))
            return
        self.store.update_at(index, dialog.name, dialog.tags, dialog.detail)
        self._list_changed()

    def _reload_history(self, select: int = 0) -> None:
        self.history_list.blockSignals(True)
        self.history_list.clear()
        folders: list[tuple[str, list[tuple[int, str]]]] = []
        seen: dict[str, int] = {}
        for index, scan in enumerate(self.store.scans):
            day, clock = self._day_and_clock(str(scan.get("at", "")))
            key = day or clock
            if key not in seen:
                seen[key] = len(folders)
                folders.append((key, []))
            folders[seen[key]][1].append((index, clock))
        count = len(self.store.scans)
        for key, rows in folders:
            closed = key in self._closed_days
            self._add_day_folder(key, closed)
            for index, clock in rows:
                self._add_history_time(key, index, clock, closed)
        self.history_side.setVisible(count > 0)
        self.history_list.setVisible(count > 0)
        self.record_card.setVisible(count > 0)
        self.history_table.setVisible(count > 0)
        self.history_empty.setVisible(count == 0)
        self.clear_history_pair.hide()
        self.clear_history_button.setVisible(count > 0)
        self._set_tab_title(self.history_tab, f"记录  {count}" if count else "记录")
        chosen = -1
        if count:
            chosen = max(0, min(select, count - 1))
            for list_row in range(self.history_list.count()):
                if self.history_list.item(list_row).data(Qt.UserRole) == chosen:
                    self.history_list.setCurrentRow(list_row)
                    break
        self.history_list.blockSignals(False)
        self._mark_selected_record()
        self._show_history_scan(chosen)
        self._show_list()

    def _add_day_folder(self, day: str, closed: bool) -> None:
        item = QListWidgetItem("")
        item.setData(Qt.UserRole, -1)
        item.setData(Qt.UserRole + 1, "day")
        item.setData(Qt.UserRole + 2, day)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        item.setSizeHint(QSize(0, 30))
        wrap = QWidget()
        wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        wrap.setStyleSheet("background: transparent;")
        line = QHBoxLayout(wrap)
        line.setContentsMargins(0, 0, 8, 0)
        line.setSpacing(8)
        line.addWidget(DayFolderIcon(opened=not closed), 0, Qt.AlignVCenter)
        label = QLabel(day)
        label.setObjectName("dayFolder")
        label.setFont(record_font())
        label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        label.setStyleSheet(
            f'color: {THEME["text"]}; background: transparent; font-family: "{chinese_family()}"; font-size: 13pt; font-weight: 400;'
        )
        line.addWidget(label)
        self.history_list.addItem(item)
        self.history_list.setItemWidget(item, wrap)

    def _add_history_time(self, day: str, index: int, text: str, closed: bool) -> None:
        item = QListWidgetItem("")
        item.setData(Qt.UserRole, index)
        item.setData(Qt.UserRole + 1, "time")
        item.setData(Qt.UserRole + 2, day)
        item.setFont(record_font())
        item.setSizeHint(QSize(0, 30))
        self.history_list.addItem(item)
        item.setHidden(closed)
        wrap = QWidget()
        wrap.setProperty("scanRow", index)
        wrap.setStyleSheet("background: transparent;")
        wrap.installEventFilter(self)
        line = QHBoxLayout(wrap)
        line.setContentsMargins(24, 0, 4, 0)
        line.setSpacing(0)
        clock = QLabel(text)
        clock.setObjectName("recordTime")
        clock.setFont(record_font())
        clock.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        clock.setStyleSheet(
            f'color: {THEME["text"]}; background: transparent; font-family: "{chinese_family()}"; font-size: 13pt; font-weight: 400;'
        )
        line.addWidget(clock, 0, Qt.AlignVCenter)
        line.addStretch(1)
        remove = QPushButton("×")
        remove.setObjectName("rowDelete")
        remove.setFixedSize(22, 22)
        mark = chinese_font(READ_PT)
        remove.setFont(mark)
        remove.setCursor(Qt.PointingHandCursor)
        remove.setFocusPolicy(Qt.NoFocus)
        remove.hide()
        remove.clicked.connect(lambda _checked=False, scan=index: self._delete_scan(scan))
        line.addWidget(remove, 0, Qt.AlignVCenter)
        self.history_list.setItemWidget(item, wrap)

    def _on_history_clicked(self, item: QListWidgetItem) -> None:
        if item.data(Qt.UserRole + 1) != "day":
            return
        day = str(item.data(Qt.UserRole + 2) or "")
        if day in self._closed_days:
            self._closed_days.discard(day)
        else:
            self._closed_days.add(day)
        self._sync_day_folders()

    def _sync_day_folders(self) -> None:
        self.history_list.blockSignals(True)
        selected = self._selected_scan()
        for row in range(self.history_list.count()):
            item = self.history_list.item(row)
            day = str(item.data(Qt.UserRole + 2) or "")
            closed = day in self._closed_days
            kind = item.data(Qt.UserRole + 1)
            if kind == "day":
                wrap = self.history_list.itemWidget(item)
                mark = wrap.findChild(DayFolderIcon, "dayMark") if wrap is not None else None
                if mark is not None:
                    mark.set_open(not closed)
            else:
                item.setHidden(closed)
        if selected >= 0:
            for row in range(self.history_list.count()):
                item = self.history_list.item(row)
                if item.data(Qt.UserRole) == selected and not item.isHidden():
                    self.history_list.setCurrentRow(row)
                    break
        self.history_list.blockSignals(False)

    def _hover_day_folder(self, row: int) -> None:
        if self._day_hover == row:
            return
        self._day_hover = row
        for index in range(self.history_list.count()):
            item = self.history_list.item(index)
            if item.data(Qt.UserRole + 1) != "day":
                continue
            wrap = self.history_list.itemWidget(item)
            mark = wrap.findChild(DayFolderIcon, "dayMark") if wrap is not None else None
            if mark is not None:
                mark.set_hovered(index == row)

    def _on_history_picked(self, list_row: int) -> None:
        index = self._scan_at(list_row)
        if index < 0:
            return
        self._show_history_scan(index)

    def _selected_scan(self) -> int:
        return self._scan_at(self.history_list.currentRow())

    def _scan_at(self, list_row: int) -> int:
        if list_row < 0:
            return -1
        item = self.history_list.item(list_row)
        if item is None:
            return -1
        value = item.data(Qt.UserRole)
        try:
            index = int(value)
        except (TypeError, ValueError):
            return -1
        if index < 0:
            return -1
        return index

    def _delete_scan(self, index: int) -> None:
        self.store.remove_scan(index)
        self._reload_history(index)

    def _delete_history(self) -> None:
        self._delete_scan(self._selected_scan())

    def _arm_clear_history(self) -> None:
        self.clear_history_button.hide()
        self.clear_history_pair.show()

    def _cancel_clear_history(self) -> None:
        self.clear_history_pair.hide()
        self.clear_history_button.show()

    def _confirm_clear_history(self) -> None:
        self._cancel_clear_history()
        self._clear_history()

    def _clear_history(self) -> None:
        self.store.clear_scans()
        self._reload_history()

    def _day_and_clock(self, stamp: str) -> tuple[str, str]:
        try:
            moment = datetime.fromisoformat(stamp)
        except ValueError:
            return "", stamp
        return f"{moment.month}月{moment.day}日", _zh_clock(moment)

    def _show_history_scan(self, row: int) -> None:
        self._history_hover = (-1, -1)
        self._mark_selected_record()
        self.history_table.setRowCount(0)
        if row < 0 or row >= len(self.store.scans):
            return
        names = self.store.scans[row].get("names", [])
        self.history_table.setRowCount((len(names) + 1) // 2)
        for index, seat in enumerate(names):
            self._set_history_seat(index // 2, index % 2, seat)
            self.history_table.setRowHeight(index // 2, 48)

    def _mark_selected_record(self) -> None:
        for row in range(self.history_list.count()):
            item = self.history_list.item(row)
            if item.data(Qt.UserRole + 1) != "time":
                continue
            item.setFont(record_font())

    def _history_match(self, shown: str):
        label = NameLabel(raw=shown, visible=shown, truncated=False)
        found = match_label(label, list(self.store.entries))
        return found[0] if found else None

    def _set_history_seat(self, row: int, column: int, seat: dict) -> None:
        unclear = bool(seat.get("unclear")) or not str(seat.get("name") or "")
        shown = "未看清" if unclear else str(seat.get("name"))
        visible = "未知" if unclear else shown
        match = None if unclear else self._history_match(shown)
        stored = match.entry.name if match is not None else ""
        mine = not unclear and match is None and self._is_my_name(shown)
        if mine:
            action = "你"
        elif unclear or match is not None:
            action = ""
        else:
            action = "添加"
        # The name as read off the screen. A match shows the list's spelling beside it,
        # so a cut-off or near name that matched can be told apart from an exact one.
        title = shown
        if not unclear:
            title = split_ellipsis(title)[0] or title
        listed = stored if match is not None and fold(stored) != fold(title) else ""
        # Lobby order is not the player's number. Show the name until a later stage.
        label = title
        name_item = QTableWidgetItem(label)
        name_item.setData(Qt.UserRole, "" if unclear else title)
        name_item.setData(Qt.UserRole + 1, action)
        name_item.setData(Qt.UserRole + 2, stored)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        name_font = record_font()
        name_item.setFont(name_font)
        if unclear:
            tone = THEME["gray"]
            wash = ""
            hover = ""
        elif match is not None:
            tone = THEME["red"]
            wash = THEME["red_wash"]
            hover = THEME["red_hover"]
        elif self._is_my_name(shown):
            tone = THEME["green"]
            wash = THEME["green_wash"]
            hover = ""
        else:
            tone = THEME["text"]
            wash = ""
            hover = THEME["red_hover"]
        name_item.setForeground(QColor(tone))
        self.history_table.setItem(row, column, name_item)
        wrap = QWidget()
        wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        wrap.setProperty("toneWash", wash)
        wrap.setProperty("toneHover", hover)
        wrap.setStyleSheet(self._history_wrap_style(wash))
        line = QHBoxLayout(wrap)
        line.setContentsMargins(16, 0, 16, 0)
        line.setSpacing(GAP)
        name_label = QLabel(visible if unclear else label)
        name_label.setFont(name_font)
        name_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        name_color = tone
        if unclear:
            missed = record_font()
            missed.setItalic(True)
            name_label.setFont(missed)
        name_label.setStyleSheet(
            f'color: {name_color}; background: transparent; font-family: "{chinese_family()}"; font-size: 13pt;'
            + (" font-style: italic;" if unclear else "")
        )
        line.addWidget(name_label)
        line.addStretch(1)
        if listed:
            listed_label = QLabel(f"名单：{listed}")
            listed_label.setObjectName("rowListed")
            listed_label.setFont(chinese_font(SMALL_PT))
            listed_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            listed_label.setStyleSheet(
                f'color: {THEME["red"]}; background: transparent; font-family: "{chinese_family()}";'
            )
            name_item.setToolTip(f"画面是「{title}」，黑名单里是「{listed}」")
            line.addWidget(listed_label)
        if action:
            action_label = QLabel(action)
            action_label.setObjectName("rowAction")
            action_label.setFont(chinese_font())
            action_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            if action == "你":
                you = record_font()
                you.setBold(True)
                you.setItalic(True)
                action_label.setFont(you)
                color = THEME["gray"]
                action_label.setStyleSheet(
                    f'color: {color}; background: transparent; font-family: "{chinese_family()}"; font-size: 13pt; font-weight: 700; font-style: italic;'
                )
            else:
                color = THEME["red"]
                action_label.setFont(record_font())
                action_label.setStyleSheet(
                    f'color: {color}; background: transparent; font-family: "{chinese_family()}"; font-size: 13pt;'
                )
            if action == "添加":
                action_label.hide()
            line.addWidget(action_label)
        self.history_table.setCellWidget(row, column, wrap)

    def _history_wrap_style(self, wash: str = "") -> str:
        return f"background: {wash or THEME['surface']}; border-radius: 8px;"

    def _history_cell_is_mine(self, row: int, column: int) -> bool:
        item = self.history_table.item(row, column)
        return item is not None and str(item.data(Qt.UserRole + 1) or "") == "你"

    def _history_cell_is_unclear(self, row: int, column: int) -> bool:
        item = self.history_table.item(row, column)
        return item is not None and item.text() == "未看清"

    def _hover_history_cell(self, row: int, column: int) -> None:
        if self._history_cell_is_mine(row, column) or self._history_cell_is_unclear(row, column):
            self._clear_history_hover()
            self.history_table.viewport().setCursor(Qt.ArrowCursor)
            return
        self.history_table.viewport().setCursor(Qt.PointingHandCursor)
        if self._history_hover == (row, column):
            return
        self._paint_history_hover(*self._history_hover, False)
        self._history_hover = (row, column)
        self._paint_history_hover(row, column, True)

    def _clear_history_hover(self) -> None:
        self._paint_history_hover(*self._history_hover, False)
        self._history_hover = (-1, -1)

    def _paint_history_hover(self, row: int, column: int, hot: bool) -> None:
        if row < 0 or column < 0:
            return
        item = self.history_table.item(row, column)
        wrap = self.history_table.cellWidget(row, column)
        if item is None or wrap is None:
            return
        if hot and str(item.data(Qt.UserRole + 1) or "") == "你":
            hot = False
        hover = str(wrap.property("toneHover") or "")
        wash = hover if hot and hover else str(wrap.property("toneWash") or "")
        if hot and not hover:
            wash = THEME["red_hover"]
        wrap.setStyleSheet(self._history_wrap_style(wash))
        action_label = wrap.findChild(QLabel, "rowAction")
        if action_label is not None and action_label.text() == "添加":
            action_label.setVisible(hot)

    def _on_history_cell(self, row: int, column: int) -> None:
        item = self.history_table.item(row, column)
        if item is None:
            return
        shown = str(item.data(Qt.UserRole) or "")
        shown = split_ellipsis(shown)[0] or shown
        if not shown or str(item.data(Qt.UserRole + 1) or "") == "你":
            return
        stored = str(item.data(Qt.UserRole + 2) or "")
        if stored:
            for index, entry in enumerate(self.store.entries):
                if entry.name == stored:
                    self._edit_entry(index)
                    return
            return
        dialog = AddNameDialog(shown, title="添加", catalog=self.store.tag_catalog(), parent=self, taken=self._taken_names())
        if dialog.exec() != QDialog.Accepted or dialog.deleted:
            return
        if self.store.add(dialog.name, dialog.detail, tags=dialog.tags) is None:
            return
        self._show_list()
        self._show_history_scan(self._selected_scan())

    def _cycle_capture_mode(self) -> None:
        self._toggle_auto(not self.store.auto_capture)

    def _toggle_auto(self, checked: bool) -> None:
        self.store.auto_capture = bool(checked)
        self.store.save_settings()
        if self.store.auto_capture:
            self.auto_on.setChecked(True)
            self.watch = LobbyWatch()
            self._watch_timer.start()
        else:
            self.auto_off.setChecked(True)
            if not self.panel.isVisible():
                self._watch_timer.stop()
        self._sync_hotkey_mode()
        self._sync_mode_cycle_tip()
        if self._status_kind in ("idle", "watch"):
            self._sync_watch_idle()

    def _begin_hotkey(self) -> None:
        self._set_settings_note("")
        self.hotkey.clear()
        self.hotkey_edit.clear()
        self.hotkey_edit.setPlaceholderText("按下热键")

    def _end_hotkey(self) -> None:
        self.hotkey_edit.setPlaceholderText("无")
        self._show_hotkey()
        self._sync_hotkey_mode()

    def _sync_hotkey_mode(self) -> None:
        """Auto check and the hotkey do not run together."""
        manual = not self.store.auto_capture
        self.hotkey_edit.setEnabled(manual)
        self.hotkey_edit.setCursor(Qt.PointingHandCursor if manual else Qt.ArrowCursor)
        if not manual:
            self.hotkey.clear()
            return
        spec = parse_hotkey(self.store.hotkey)
        if spec is not None and self.hotkey.active != spec.display:
            self.hotkey.apply(spec)

    def _take_hotkey(self, event) -> None:
        if event.isAutoRepeat():
            return
        if event.key() == Qt.Key_Escape:
            self.hotkey_edit.clearFocus()
            return
        if event.key() in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta):
            return
        key = _qt_key_name(event.key())
        if key is None:
            self._set_settings_note("请按字母、数字，或 F1 到 F12。")
            return
        modifiers = []
        flags = event.modifiers()
        if flags & Qt.ControlModifier:
            modifiers.append("Ctrl")
        if flags & Qt.AltModifier:
            modifiers.append("Alt")
        if flags & Qt.ShiftModifier:
            modifiers.append("Shift")
        if flags & Qt.MetaModifier:
            modifiers.append("Win")
        spec = parse_hotkey("+".join([*modifiers, key]))
        if spec is None:
            self._set_settings_note("这个组合不能用。")
            return
        registered = self.hotkey.apply(spec)
        self.store.hotkey = spec.display
        self.store.save_settings()
        self.hotkey_edit.setText(spec.display)
        if registered:
            self._set_settings_note("")
        elif sys.platform != "win32":
            self._set_settings_note("这台电脑不能用热键。")
        else:
            self.store.hotkey = ""
            self.store.save_settings()
            self.hotkey_edit.clear()
            self._set_settings_note("换一个热键。")
        self.hotkey_edit.clearFocus()
        if self._status_kind == "idle":
            self._sync_watch_idle()

    def _show_hotkey(self) -> None:
        spec = parse_hotkey(self.store.hotkey)
        if spec is None:
            self.hotkey_edit.clear()
            return
        self.hotkey_edit.setText(spec.display)

    def _restore_hotkey(self) -> None:
        self._show_hotkey()
        self._sync_hotkey_mode()

    def check_now(self) -> None:
        self._release_foreground = True
        self._rescan_active = False
        lock_foreground(True)
        if self._start(self._capture_job, live=True):
            self._manual_check = True
        elif self._status_kind == "loading":
            self._notify("识别模型还在加载", "请过几秒再按一次快捷键。")

    def start_warmup(self) -> None:
        """Load the OCR models now, so the first lobby check does not wait for them."""
        if not self.worker.request(get_engine().warmup, kind="warmup"):
            return
        self._warm_started = time.perf_counter()
        self._set_result("正在加载识别模型", "idle", "loading")

    def show_first_run_guide(self) -> None:
        """Once per PC: the app opened with no settings file yet."""
        if not self.store.first_run:
            return
        self.store.first_run = False
        self.store.save_settings()
        guide = GuideDialog(self)
        if guide.exec() == QDialog.Accepted and guide.wants_test:
            self.test_recognition()

    def test_recognition(self) -> None:
        """Read the bundled lobby picture, so a friend can see recognition work without the game."""
        self._run_picture(str(SAMPLE_LOBBY), "识别测试")

    def check_picture(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "选择大厅截图", "", "图片 (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self._run_picture(path, "截图检查")

    def _run_picture(self, path: str, title: str, tries: int = 0) -> None:
        if self._picture_pending and tries == 0:
            return
        entries = list(self.store.entries)
        # Hold the lobby glances back so this check gets the reader next.
        self._glance_pause_until = max(self._glance_pause_until, time.perf_counter() + 2.0)
        if self.worker.request(lambda: check_image(path, entries), kind="picture"):
            self._picture_pending = title
            self._sync_picture_buttons()
            return
        if tries == 0:
            self._picture_pending = title
            self._sync_picture_buttons()
        if tries < 300:
            # The reader is busy: a glance, a lobby check, or the first model load.
            QTimer.singleShot(100, lambda: self._run_picture(path, title, tries + 1))
            return
        self._picture_pending = ""
        self._sync_picture_buttons()
        self._picture_dialog = PictureResultDialog(title, error="识别一直在忙，请稍后再试。", parent=self)
        self._picture_dialog.open()

    def _sync_picture_buttons(self) -> None:
        busy = bool(self._picture_pending)
        for button in (self.test_button, self.picture_button, self.history_test_button):
            button.setEnabled(not busy)
        self.test_button.setText("正在识别" if busy else "测试一下")

    def _on_picture(self, status: str, value) -> None:  # noqa: ANN001
        title = self._picture_pending or "截图检查"
        self._picture_pending = ""
        self._sync_picture_buttons()
        if status != "ok":
            log.warning("Picture check failed: %s", value)
            self._picture_dialog = PictureResultDialog(title, error=str(value), parent=self)
        else:
            log.info("Picture check: lobby %s, %d on the list", value.header_found, len(value.hits))
            self._picture_dialog = PictureResultDialog(title, result=value, parent=self)
        self._picture_dialog.open()

    def _set_hit_sound(self, enabled: bool) -> None:
        self.store.hit_sound = bool(enabled)
        self.store.save_settings()
        (self.sound_on if enabled else self.sound_off).setChecked(True)
        if enabled:
            _play_hit_sound()

    def report_uncaught(self, text: str) -> None:
        """Any thread may call this. The window is updated on its own thread."""
        self.uncaught.emit(text)

    def _show_uncaught(self, text: str) -> None:
        tip = f"{text}\n\n日志：{log_dir(self.store.root) / 'app.log'}"
        self._set_result("程序出错了", "hit", "error", tip=tip)

    def _report_problem(self, problem) -> None:  # noqa: ANN001
        """Say what went wrong in the header and the tray. A check that silently stops is worse than an error."""
        if isinstance(problem, OcrUnavailable):
            label = "识别模型没有就绪"
        elif isinstance(problem, CaptureUnavailable):
            label = "无法读取屏幕"
        else:
            label = "检查出错"
        detail = str(problem).strip() or label
        if detail != self._problem:
            trace = (type(problem), problem, problem.__traceback__) if isinstance(problem, BaseException) else None
            expected = isinstance(problem, (OcrUnavailable, CaptureUnavailable))
            log.warning("%s: %s", label, detail, exc_info=None if expected else trace)
        if self._status_kind != "error" or detail != self._problem:
            tip = f"{detail}\n\n日志：{log_dir(self.store.root) / 'app.log'}"
            self._set_result(label, "hit", "error", tip=tip)
        self._problem = detail
        if label not in self._told_problems:
            self._told_problems.add(label)
            self._notify(label, detail[:200])

    def _clear_problem(self) -> None:
        if not self._problem:
            return
        self._problem = ""
        log.info("Checks work again.")
        if self._status_kind == "error":
            self._sync_watch_idle()

    def _notify(self, title: str, text: str, warning: bool = True) -> None:
        """A Windows notification from the tray icon. The window is usually hidden behind the game."""
        if self.tray is None or not self.tray.isVisible():
            return
        from PySide6.QtWidgets import QSystemTrayIcon

        icon = QSystemTrayIcon.MessageIcon.Warning if warning else QSystemTrayIcon.MessageIcon.Information
        self.tray.showMessage(title, text, icon, 5000)

    def _capture_job(self) -> CheckResult:
        frames = capture_displays()
        return check_frames(frames, list(self.store.entries), on_lobby=self.worker.placed.emit)

    def _glance_job(self) -> bool:
        return glance_title(capture_top_band())

    def _auto_tick(self) -> None:
        if self._closing:
            return
        if not self.store.auto_capture and not self.panel.isVisible():
            self._watch_timer.stop()
            return
        if time.perf_counter() < self._glance_pause_until:
            return
        self.worker.request(self._glance_job, kind="glance")

    def _start(self, fn, live: bool = False) -> bool:
        self._live_check = live
        quiet = self._rescan_active
        if live and self.panel.isVisible() and not quiet:
            self._panel_hide_timer.stop()
            self.panel.set_mode("checking", "请等待")
            self.hit_card.hide()
            self.clear_mark.hide()
        if not self.worker.request(fn):
            self._unlock_foreground()
            return False
        self._check_started = time.perf_counter()
        return True

    def _unlock_foreground(self) -> None:
        if not self._release_foreground:
            return
        self._release_foreground = False
        lock_foreground(False)

    def _on_worker(self, payload) -> None:
        job, status, value = payload
        self.worker.running_job = False
        if self._closing:
            return
        if job == "warmup":
            self._on_warmed(status, value)
            return
        if job == "glance":
            self._on_glanced(status, value)
            return
        if job == "picture":
            self._on_picture(status, value)
            return
        self._on_checked(status, value)

    def _on_warmed(self, status: str, value) -> None:
        if status != "ok":
            self._report_problem(value)
            return
        if self._warm_started is not None:
            log.info("OCR ready in %.1f s", time.perf_counter() - self._warm_started)
        if self._status_kind == "loading":
            self._sync_watch_idle()

    def _on_glanced(self, status: str, value) -> None:
        if status != "ok":
            self._report_problem(value)
            # Do not reload a missing model or retry a dead screen copy every 0.4 seconds.
            pause = 15.0 if isinstance(value, OcrUnavailable) else 5.0
            self._glance_pause_until = time.perf_counter() + pause
            return
        was_error = self._status_kind == "error"
        if self._problem:
            self._clear_problem()
        elif was_error:
            self._sync_watch_idle()
        if not value:
            if self.panel.isVisible():
                self._hide_panel_after_title()
        else:
            self._panel_hide_timer.stop()
        if not self.store.auto_capture:
            return
        now = time.perf_counter()
        if not self.watch.wants_check(bool(value), now):
            return
        self.watch.arm(now)
        self._rescan_active = False
        if not self._start(self._capture_job, live=True):
            self.watch.retry_after(now)

    def _note_watch(self, found: bool) -> None:
        if not self.store.auto_capture:
            return
        if found:
            self.watch.hold()
        else:
            self.watch.retry_after(time.perf_counter())

    def _on_checked(self, status: str, value) -> None:
        self._unlock_foreground()
        if self._closing:
            return
        rescan = self._rescan_active
        self._rescan_active = False
        elapsed = None
        if self._check_started is not None:
            elapsed = time.perf_counter() - self._check_started
            self._check_started = None
        manual = self._manual_check
        if status == "err":
            if not rescan and self._live_check and self._rescan_now():
                return
            self._manual_check = False
            self._report_problem(value)
            if self.store.auto_capture:
                self.watch.retry_after(time.perf_counter())
            self._hide_panel_after_title()
            return
        result: CheckResult = value
        if not result.header_found:
            if not rescan and self._live_check and self._rescan_now():
                return
            self._manual_check = False
            log.info("No lobby on screen: %s", result.message)
            if manual:
                self._notify("没有看到大厅", "按快捷键时，「推演成功」的画面要在屏幕上。")
            if self.store.auto_capture:
                self.watch.retry_after(time.perf_counter())
            self._hide_panel_after_title()
            return
        self._manual_check = False
        self._clear_problem()
        log.info(
            "Checked the lobby: %d on the list, %d unclear, %.2f s",
            len(result.hits),
            sum(1 for slot in result.names if slot.unclear),
            elapsed or 0.0,
        )
        self._note_watch(bool(result.header_found))
        if result.header_found and result.names:
            outcome = self.store.add_scan(
                [
                    {
                        "seat": seat_number(slot.index),
                        "name": "" if slot.unclear else slot.visible,
                        "unclear": slot.unclear,
                    }
                    for slot in result.names
                ],
                elapsed,
            )
            if outcome == "filled":
                self._apply_filled(result)
            self._reload_history()
        self._show_result(result)
        self._show_panel(result)
        if result.hits and self._live_check and self.store.hit_sound:
            _play_hit_sound()
        if self.store.save_debug_frames and result.preview_rgb is not None:
            self._save_debug(result)

    def _rescan_now(self) -> bool:
        if self._closing:
            return False
        self._rescan_active = True
        if self.store.auto_capture:
            self.watch.arm(time.perf_counter())
        if self._start(self._capture_job, live=True):
            return True
        self._rescan_active = False
        return False

    def _apply_filled(self, result: CheckResult) -> None:
        if not self.store.scans:
            return
        saved = {int(item["seat"]): item for item in self.store.scans[0]["names"]}
        slots: list[NameSlot] = []
        for slot in result.names:
            item = saved.get(seat_number(slot.index))
            if item is None or item.get("unclear") or not str(item.get("name") or ""):
                slots.append(slot)
                continue
            name = str(item["name"])
            slots.append(
                NameSlot(
                    index=slot.index,
                    box=slot.box,
                    raw=name,
                    visible=name,
                    truncated=name.endswith("..."),
                    confidence=slot.confidence,
                    unclear=False,
                )
            )
        result.names = slots
        hits: list[Hit] = []
        for slot in slots:
            if slot.unclear or not slot.visible:
                continue
            label = NameLabel(raw=slot.visible, visible=slot.visible, truncated=slot.truncated, unclear=False)
            for found in match_label(label, self.store.entries):
                note = describe_entry(found.entry)
                hits.append(
                    Hit(
                        index=slot.index,
                        read_text=slot.visible,
                        entry_name=found.entry.name,
                        note=note,
                        truncated=slot.truncated,
                        line=format_hit(slot.index, slot.visible, slot.truncated, found.entry.name, note),
                        tags=tuple(found.entry.tags),
                    )
                )
        result.hits = hits

    def _hide_panel_after_title(self) -> None:
        self._panel_hide_timer.stop()
        self.panel.hide()
        self.hit_card.hide()
        self.clear_mark.hide()
        if not self.store.auto_capture:
            self._watch_timer.stop()

    def _on_lobby_placed(self, box) -> None:
        if self._closing or not self._live_check:
            return
        # A finished cover stays put. A second pass must not turn it yellow again.
        if self.panel.isVisible() and self.panel.mode in ("clear", "hit"):
            return
        self._open_panel("checking", "请等待", box)
        self.hit_card.hide()
        self.clear_mark.hide()

    def _show_panel(self, result: CheckResult) -> None:
        if not self._live_check or not result.header_found:
            self._hide_panel_after_title()
            return
        if result.button_box is None:
            self._hide_panel_after_title()
            return
        if result.hits:
            self.clear_mark.hide()
            self._open_panel("hit", "", result.button_box)
            self._show_hit_card(result.hits)
            return
        self.hit_card.hide()
        text = "没有黑名单"
        unclear = sum(1 for slot in result.names if slot.unclear)
        if unclear:
            text += f"\n{unclear} 人没看清"
        self._open_panel("clear", text, result.button_box)
        self._show_clear_mark()

    def _open_panel(self, mode: str, text: str, box) -> None:
        self._panel_hide_timer.stop()
        if box is None:
            return
        self._show_panel_at(box, mode, text)
        if not self._watch_timer.isActive():
            self._watch_timer.start()

    def _show_panel_at(self, box, mode: str, text: str) -> None:
        origin_x, origin_y = virtual_origin()
        left, top, right, bottom = box
        x, y, ratio = native_to_logical(left + origin_x, top + origin_y)
        outset = _COVER_OUTSET
        self.panel.show_over(
            x - outset,
            y - outset,
            (right - left) / ratio + outset * 2,
            (bottom - top) / ratio + outset * 2,
            mode,
            text,
        )

    def _show_hit_card(self, hits: list[Hit]) -> None:
        people: list[tuple[str, tuple[str, ...]]] = []
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for hit in hits:
            person = (hit.entry_name, tuple(hit.tags))
            if person in seen:
                continue
            seen.add(person)
            people.append(person)
        if not people:
            self.hit_card.hide()
            self.clear_mark.hide()
            return
        self.hit_card.set_people(people, self.panel.height())
        self._place_beside(self.hit_card)

    def _show_clear_mark(self) -> None:
        self.clear_mark.set_size(self.panel.height())
        self._place_beside(self.clear_mark)

    def _place_beside(self, widget: QWidget) -> None:
        gap = 12
        panel = self.panel
        x = panel.x() + panel.width() + gap
        y = panel.y() + (panel.height() - widget.height()) // 2
        screen = QApplication.screenAt(panel.pos()) or QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            if x + widget.width() > area.right() - 8:
                x = panel.x() - gap - widget.width()
            x = max(area.left() + 8, min(x, area.right() - widget.width() - 8))
            y = max(area.top() + 8, min(y, area.bottom() - widget.height() - 8))
        widget.move(int(x), int(y))
        widget.show()
        _pin_topmost(widget)

    def _show_result(self, result: CheckResult) -> None:
        lines = []
        for slot in result.names:
            text = "未看清" if slot.unclear else slot.visible
            lines.append(text)
        self.names_view.setPlainText("\n".join(lines))

    def _brief(self, result: CheckResult) -> tuple[str, bool]:
        if not result.header_found:
            return result.message, False
        parts: list[str] = []
        clear = not result.hits
        if result.hits:
            parts.append(f"{len(result.hits)} 人在名单里")
        else:
            parts.append("没有发现黑名单")
        unclear = sum(1 for slot in result.names if slot.unclear)
        if unclear:
            parts.append(f"{unclear} 人没看清")
        return "，".join(parts), clear

    def _sync_mode_cycle_tip(self) -> None:
        cycle = getattr(self, "mode_cycle", None)
        if cycle is None:
            return
        tip = "切换为手动检查" if self.store.auto_capture else "切换为自动检查"
        self.mode_cycle.setToolTip(tip)
        self.mode_cluster.setToolTip(tip)
        self.watch_mark.setToolTip(tip)

    def _sync_watch_idle(self) -> None:
        if self.store.auto_capture:
            self._set_result("自动检查中", "watchOn", "watch")
        else:
            self._set_result("手动检查", "watchOff", "idle")
        self._sync_mode_cycle_tip()

    def _show_status_mark(self, pixmap: QPixmap) -> None:
        self.watch_mark.setText("")
        self.watch_mark.setObjectName("")
        self.watch_mark.setPixmap(pixmap)
        self.watch_mark.show()
        self.watch_mark.style().unpolish(self.watch_mark)
        self.watch_mark.style().polish(self.watch_mark)

    def _show_hotkey_mark(self) -> None:
        self.watch_mark.setPixmap(QPixmap())
        self.watch_mark.setObjectName("hotkey")
        self.watch_mark.setFont(chinese_font(READ_PT))
        self.watch_mark.setText(f"[{self.store.hotkey}]")
        self.watch_mark.setVisible(bool(self.store.hotkey))
        self.watch_mark.style().unpolish(self.watch_mark)
        self.watch_mark.style().polish(self.watch_mark)

    def _set_result(self, text: str, tone: str = "status", kind: str = "result", tip: str = "") -> None:
        self._status_kind = kind
        self._watch_tone = tone
        self._watch_full = text
        self._watch_tip = tip
        colors = {
            "clear": THEME["green"],
            "hit": THEME["red"],
            "idle": THEME["muted"],
            "status": THEME["text"],
        }
        self.watch_label.setObjectName(tone)
        self.watch_label.setFont(chinese_font(READ_PT))
        self.watch_label.setToolTip(tip or text)
        width = max(1, self.watch_label.maximumWidth())
        self.watch_label.setText(self.watch_label.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, width))
        self.watch_label.style().unpolish(self.watch_label)
        self.watch_label.style().polish(self.watch_label)
        if kind == "watch":
            self._show_status_mark(_check_icon())
        elif kind == "idle":
            self._show_hotkey_mark()
        else:
            self._show_status_mark(_watch_mark(colors.get(tone, THEME["muted"])))
        self._set_tray(text)

    def _remember_size(self) -> None:
        if not hasattr(self, "store"):
            return
        width, height = self.width(), self.height()
        if width < 900 or height < 560:
            return
        if self.store.window_size == (width, height):
            return
        self.store.window_size = (width, height)
        self.store.save_settings()

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._remember_size()

    def copy_result(self) -> None:
        text = self.names_view.toPlainText().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)

    def _save_debug(self, result: CheckResult) -> None:
        directory = self.store.root / "debug"
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = directory / f"{stamp}.png"
        from PIL import Image

        image = Image.fromarray(result.preview_rgb)
        image.save(path)

    def _set_tray(self, text: str) -> None:
        if self.tray is not None:
            self.tray.setToolTip(text[:120])

    def _show_from_tray(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_tray(self, reason) -> None:
        from PySide6.QtWidgets import QSystemTrayIcon

        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._show_from_tray()

    def closeEvent(self, event) -> None:  # noqa: ANN001
        if event.spontaneous() and self.tray is not None and self.tray.isVisible():
            # Keep checking from the tray. Without a tray icon there would be no way back, so X quits.
            event.ignore()
            self.hide()
            if not self._told_tray:
                self._told_tray = True
                self._notify("黑名单检测仍在运行", "它会继续检查大厅。在右下角的托盘图标上右键可以退出。", warning=False)
            return
        self._remember_size()
        self.hide()
        self._closing = True
        self._panel_hide_timer.stop()
        self._watch_timer.stop()
        self.warning.close()
        self.clear_notice.close()
        if hasattr(self, "detail_tip"):
            self.detail_tip.close()
        self.panel.close()
        self.hit_card.close()
        self.clear_mark.close()
        self.hotkey.clear()
        self.worker.stop()
        # A check or a model load cannot be interrupted. Ending the thread under it crashes on exit.
        if not self.worker.wait(20_000):
            log.warning("The check thread was still running at exit.")
        if self.instance_server is not None:
            self.instance_server.close()
        if self.tray is not None:
            self.tray.hide()
        super().closeEvent(event)


def QSystemTrayIcon_available() -> bool:
    try:
        from PySide6.QtWidgets import QSystemTrayIcon

        return QSystemTrayIcon.isSystemTrayAvailable()
    except Exception:
        return False
