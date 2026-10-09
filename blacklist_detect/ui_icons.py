"""One set of line icons, drawn in code so the bundle needs no image files.

Every icon is drawn on a 24-unit grid with the same round stroke, then scaled
to the size asked for, so they all share one weight. Colors come from the
theme unless one is passed.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from blacklist_detect.ui_theme import THEME


def _add(p: QPainter) -> None:
    p.drawLine(QPointF(12, 5), QPointF(12, 19))
    p.drawLine(QPointF(5, 12), QPointF(19, 12))


def _close(p: QPainter) -> None:
    p.drawLine(QPointF(6, 6), QPointF(18, 18))
    p.drawLine(QPointF(18, 6), QPointF(6, 18))


def _check(p: QPainter) -> None:
    path = QPainterPath(QPointF(5, 12.5))
    path.lineTo(10, 17.5)
    path.lineTo(19, 7)
    p.drawPath(path)


def _search(p: QPainter) -> None:
    p.drawEllipse(QPointF(10.5, 10.5), 6, 6)
    p.drawLine(QPointF(15, 15), QPointF(20, 20))


def _edit(p: QPainter) -> None:
    path = QPainterPath(QPointF(5, 19))
    path.lineTo(5.6, 15.2)
    path.lineTo(15.5, 5.3)
    path.lineTo(18.7, 8.5)
    path.lineTo(8.8, 18.4)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QPointF(13.3, 7.5), QPointF(16.5, 10.7))


def _delete(p: QPainter) -> None:
    p.drawLine(QPointF(4.5, 7), QPointF(19.5, 7))
    p.drawLine(QPointF(9.5, 7), QPointF(10, 4.5))
    p.drawLine(QPointF(10, 4.5), QPointF(14, 4.5))
    p.drawLine(QPointF(14, 4.5), QPointF(14.5, 7))
    path = QPainterPath(QPointF(6.5, 7))
    path.lineTo(7.5, 19.5)
    path.lineTo(16.5, 19.5)
    path.lineTo(17.5, 7)
    p.drawPath(path)
    p.drawLine(QPointF(10.2, 10.5), QPointF(10.2, 16))
    p.drawLine(QPointF(13.8, 10.5), QPointF(13.8, 16))


def _copy(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(8.5, 8.5, 11, 11), 2, 2)
    path = QPainterPath(QPointF(15.5, 8.5))
    path.lineTo(15.5, 5.5)
    path.quadTo(15.5, 4.5, 14.5, 4.5)
    path.lineTo(5.5, 4.5)
    path.quadTo(4.5, 4.5, 4.5, 5.5)
    path.lineTo(4.5, 14.5)
    path.quadTo(4.5, 15.5, 5.5, 15.5)
    path.lineTo(8.5, 15.5)
    p.drawPath(path)


def _import(p: QPainter) -> None:
    p.drawLine(QPointF(12, 4), QPointF(12, 14))
    path = QPainterPath(QPointF(8, 10.5))
    path.lineTo(12, 14.5)
    path.lineTo(16, 10.5)
    p.drawPath(path)
    tray = QPainterPath(QPointF(4.5, 14))
    tray.lineTo(4.5, 19.5)
    tray.lineTo(19.5, 19.5)
    tray.lineTo(19.5, 14)
    p.drawPath(tray)


def _more(p: QPainter) -> None:
    for x in (6, 12, 18):
        p.drawPoint(QPointF(x, 12))


def _chevron_down(p: QPainter) -> None:
    path = QPainterPath(QPointF(7, 10))
    path.lineTo(12, 15)
    path.lineTo(17, 10)
    p.drawPath(path)


def _folder(p: QPainter) -> None:
    path = QPainterPath(QPointF(4, 18.5))
    path.lineTo(4, 6.5)
    path.quadTo(4, 5.5, 5, 5.5)
    path.lineTo(9.5, 5.5)
    path.lineTo(11.5, 7.5)
    path.lineTo(19, 7.5)
    path.quadTo(20, 7.5, 20, 8.5)
    path.lineTo(20, 18.5)
    path.quadTo(20, 19.5, 19, 19.5)
    path.lineTo(5, 19.5)
    path.quadTo(4, 19.5, 4, 18.5)
    p.drawPath(path)


def _eye(p: QPainter) -> None:
    path = QPainterPath(QPointF(3, 12))
    path.quadTo(12, 3.5, 21, 12)
    path.quadTo(12, 20.5, 3, 12)
    p.drawPath(path)
    p.drawEllipse(QPointF(12, 12), 3, 3)


def _eye_off(p: QPainter) -> None:
    _eye(p)
    p.drawLine(QPointF(4.5, 19.5), QPointF(19.5, 4.5))


def _warning(p: QPainter) -> None:
    path = QPainterPath(QPointF(12, 4))
    path.lineTo(21, 19.5)
    path.lineTo(3, 19.5)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QPointF(12, 9.5), QPointF(12, 14))
    p.drawPoint(QPointF(12, 17))


def _info(p: QPainter) -> None:
    p.drawEllipse(QPointF(12, 12), 8.5, 8.5)
    p.drawLine(QPointF(12, 11), QPointF(12, 16.5))
    p.drawPoint(QPointF(12, 8))


def _records(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(4.5, 4.5, 15, 15), 2.5, 2.5)
    for y in (9, 12.5, 16):
        p.drawLine(QPointF(8, y), QPointF(16, y))


def _settings(p: QPainter) -> None:
    for y, knob in ((7, 9), (12, 15), (17, 11)):
        p.drawLine(QPointF(4, y), QPointF(20, y))
        p.drawEllipse(QPointF(knob, y), 1.8, 1.8)


def _users(p: QPainter) -> None:
    p.drawEllipse(QPointF(9, 9), 3.2, 3.2)
    path = QPainterPath(QPointF(3.5, 19))
    path.quadTo(3.5, 13.8, 9, 13.8)
    path.quadTo(14.5, 13.8, 14.5, 19)
    p.drawPath(path)
    p.drawEllipse(QPointF(16.5, 8.5), 2.5, 2.5)
    side = QPainterPath(QPointF(16, 12.8))
    side.quadTo(20.5, 12.8, 20.5, 17.5)
    p.drawPath(side)


def _picture(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(4, 5, 16, 14), 2, 2)
    p.drawEllipse(QPointF(9, 10), 1.6, 1.6)
    path = QPainterPath(QPointF(4.5, 17.5))
    path.lineTo(10, 13)
    path.lineTo(13.5, 15.5)
    path.lineTo(16.5, 12.5)
    path.lineTo(19.5, 15.5)
    p.drawPath(path)


DRAWINGS: dict[str, Callable[[QPainter], None]] = {
    "add": _add,
    "close": _close,
    "check": _check,
    "search": _search,
    "edit": _edit,
    "delete": _delete,
    "copy": _copy,
    "import": _import,
    "more": _more,
    "chevron_down": _chevron_down,
    "folder": _folder,
    "eye": _eye,
    "eye_off": _eye_off,
    "warning": _warning,
    "info": _info,
    "records": _records,
    "settings": _settings,
    "users": _users,
    "picture": _picture,
}


def pixmap(name: str, size: int = 16, color: str | None = None, ratio: float = 2.0) -> QPixmap:
    """One icon at size × size logical pixels, sharp on high-DPI screens."""
    draw = DRAWINGS[name]
    side = max(1, round(size * ratio))
    image = QPixmap(side, side)
    image.setDevicePixelRatio(ratio)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.scale(size / 24.0, size / 24.0)
    # Keep the drawn line about the same thickness at every size: 1.4 px small, 2 px large.
    line_px = 1.4 if size <= 20 else 2.0
    width = line_px * 24.0 / size * (2.4 if name == "more" else 1.0)
    pen = QPen(QColor(color or THEME["muted"]), width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    draw(painter)
    painter.end()
    return image


def icon(name: str, size: int = 16, color: str | None = None) -> QIcon:
    return QIcon(pixmap(name, size, color))
