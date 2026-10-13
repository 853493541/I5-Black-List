"""命运红线 Red Thread of Fate: one thread finds each 心动 player and ties them together.

A red silk thread, twisted like cord, enters low on the left, climbs the margin and runs along
the top, then comes down to each 心动 player in turn and wraps their card in a heart; last it ties
a love knot with a tassel on the 心动 heart beside the button. Each heart glows as it closes, with
a gold bead at its cleft; then light runs the whole length of the thread.

It needs stage.cards: where each 心动 player's card is. The app has them from the names it read.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient

from blacklist_detect.love_scenes.draw import (
    Wash,
    catmull,
    clamp,
    col,
    ease_back,
    ease_in,
    ease_in_out,
    ease_out,
    gradient,
    heart_points,
    lengths,
    point_at,
    soft_dot,
    star,
    win,
)

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
RED = "#c8102e"
SHEEN = "#ff8a9a"
GOLD = "#f2c14e"
# Where on its heart the thread starts and ends: the upper left, where it comes in from the top.
START = 0.86


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    badge = stage.heart()
    knot = QPointF(badge.x(), badge.y() - 44 * u)
    # The card farthest from the knot first, the nearest last, so the thread ends by the button.
    cards = sorted(stage.cards, key=lambda c: -math.dist((c.x(), c.y()), (knot.x(), knot.y())))
    size = 225 * u
    hearts = [_heart(card, size) for card in cards]
    path: list[QPointF] = []
    closes: list[float] = []
    if hearts:
        first = hearts[0][0]
        lead = [QPointF(-30 * u, height * 0.72), QPointF(70 * u, height * 0.55), QPointF(118 * u, height * 0.29), QPointF(250 * u, 70 * u)]
        # Along the top, then down to the first heart from its upper left.
        top = 36 * u
        lead += [QPointF(max(300 * u, first.x() * 0.6), top), QPointF(max(320 * u, first.x() - 160 * u), top + 14 * u)]
        path = catmull([*lead, first], 14)
        for index, heart in enumerate(hearts):
            if index:
                path += _bridge(path[-1], heart[0], u)[1:]
            path += heart[1:]
            closes.append(lengths(path)[-1])
        a = path[-1]
        tail = catmull([a, QPointF(a.x() + (knot.x() - a.x()) * 0.3, a.y() + (knot.y() - a.y()) * 0.6), knot], 14)
        path += tail[1:]
    total = lengths(path) if path else [0.0]
    rnd = random.Random(4)
    sparks = [(rnd.uniform(0, 1), rnd.uniform(-8, 8) * u, rnd.uniform(-8, 8) * u, rnd.uniform(0, 6.28)) for _ in range(40)]

    warmth = Wash(lambda q, w, h: _thread_wash(q, 9.0, w, h, u))

    def paint(p: QPainter, t: float) -> None:
        if len(path) < 2:
            return
        life = win(t, 0.0, 0.3)
        leave = ease_in(win(t, 4.1, 4.95))
        p.save()
        p.setOpacity(p.opacity() * life * (1 - leave))
        warmth.paint(p, width, height, gap, ease_out(win(t, 0.0, 0.8)))
        reach = total[-1] * ease_in_out(win(t, 0.3, 2.75))
        for heart, at in zip(hearts, closes, strict=True):
            done = clamp((reach - at) / (60 * u) + 1) if reach >= at else 0.0
            _heart_glow(p, heart, done, u)
        _thread(p, path, total, reach, u)
        if 0 < reach < total[-1]:
            head, _ = point_at(path, total, reach)
            soft_dot(p, head.x(), head.y(), 22 * u, GOLD, 0.85)
            star(p, head.x(), head.y(), 12 * u, "#fff6dc", 1.0)
            for offset, dx, dy, _phase in sparks[:14]:
                back = reach - offset * 140 * u
                if back > 0:
                    q, _ = point_at(path, total, back)
                    soft_dot(p, q.x() + dx, q.y() + dy, 5 * u, GOLD, 0.7 * (1 - offset))
        tied = ease_back(win(t, 2.7, 3.05))
        if tied > 0:
            _love_knot(p, t, knot, u * tied)
        run = win(t, 3.05, 3.8)
        if 0 < run < 1:
            along = total[-1] * ease_in_out(run)
            q, _ = point_at(path, total, along)
            soft_dot(p, q.x(), q.y(), 34 * u, "#ffd9a0", 0.85)
            star(p, q.x(), q.y(), 18 * u, "#ffffff", 1.0)
            for offset, dx, dy, phase in sparks:
                back = along - offset * 220 * u
                if back > 0:
                    q, _ = point_at(path, total, back)
                    shine = (1 - offset) * (0.5 + 0.5 * math.sin(t * 9 + phase))
                    star(p, q.x() + dx * 1.6, q.y() + dy * 1.6, (2 + 4 * (1 - offset)) * u, GOLD, shine)
        p.restore()

    return paint


def _heart(card: QPointF, size: float) -> list[QPointF]:
    """A heart round a card, starting and ending at its upper left."""
    points = heart_points(card.x(), card.y(), size, 72, START)
    return [*points, points[0]]


def _bridge(a: QPointF, b: QPointF, u: float) -> list[QPointF]:
    """From one heart to the next, arching up a little so it does not lie along the names."""
    lift = QPointF((a.x() + b.x()) / 2, min(a.y(), b.y()) - 50 * u)
    return catmull([a, lift, b], 14)


def _thread_wash(p: QPainter, t: float, width: float, height: float, u: float) -> None:
    a = ease_out(win(t, 0.0, 0.8))
    edge = 140 * u
    for start, end, rect in (
        (QPointF(0, 0), QPointF(edge, 0), QRectF(0, 0, edge, height)),
        (QPointF(width, 0), QPointF(width - edge, 0), QRectF(width - edge, 0, edge, height)),
        (QPointF(0, 0), QPointF(0, edge), QRectF(0, 0, width, edge)),
        (QPointF(0, height), QPointF(0, height - edge), QRectF(0, height - edge, width, edge)),
    ):
        p.fillRect(rect, gradient(start, end, ((0, "#7a0f1f", 0.30), (1, "#7a0f1f", 0)), a))


def _thread(p: QPainter, path: list[QPointF], total: list[float], reach: float, u: float) -> None:
    """Red silk cord: a soft glow, the red core and a broken light line that reads as a twist."""
    if reach <= 0:
        return
    drawn = QPainterPath(path[0])
    for point, at in zip(path[1:], total[1:], strict=True):
        if at > reach:
            end, _ = point_at(path, total, reach)
            drawn.lineTo(end)
            break
        drawn.lineTo(point)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(col("#ff2e4d", 0.2), 8 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(drawn)
    p.setPen(QPen(col(RED), 3.0 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(drawn)
    twist = QPen(col(SHEEN, 0.85), 1.0 * u, Qt.CustomDashLine, Qt.FlatCap, Qt.RoundJoin)
    twist.setDashPattern([2.2, 2.6])
    p.setPen(twist)
    p.drawPath(drawn.translated(-0.5 * u, -0.6 * u))
    p.setPen(Qt.NoPen)


def _heart_glow(p: QPainter, heart: list[QPointF], done: float, u: float) -> None:
    """When a heart closes it glows red once and a gold bead appears at its cleft."""
    if done <= 0:
        return
    shape = QPainterPath()
    shape.addPolygon(QPolygonF(heart))
    shape.closeSubpath()
    box = shape.boundingRect()
    pulse = math.sin(math.pi * clamp(done)) if done < 1 else 0.0
    glow = QRadialGradient(box.center(), box.width() * 0.62)
    glow.setColorAt(0, col("#ff4d6a", 0.0))
    glow.setColorAt(0.75, col("#ff4d6a", 0.10 + 0.22 * pulse))
    glow.setColorAt(1, col("#ff4d6a", 0.04))
    p.setPen(Qt.NoPen)
    p.setBrush(glow)
    p.drawPath(shape)
    # The cleft: the highest point near the middle of the heart's top.
    upper = [q for q in heart if abs(q.x() - box.center().x()) < box.width() * 0.08]
    cleft = min(upper, key=lambda q: abs(q.x() - box.center().x())) if upper else box.center()
    r = 6.5 * u * ease_back(clamp(done))
    if r > 0.5:
        body = QRadialGradient(QPointF(cleft.x() - r * 0.3, cleft.y() - r * 0.3), r * 1.4)
        body.setColorAt(0, col("#fff3c4"))
        body.setColorAt(0.5, col(GOLD))
        body.setColorAt(1, col("#a8741e"))
        p.setBrush(body)
        p.drawEllipse(cleft, r, r)


def _love_knot(p: QPainter, t: float, at: QPointF, u: float) -> None:
    """A love knot: three loops round a small diamond, a gold cap and a red tassel."""
    p.save()
    p.translate(at)
    loops = QPainterPath(QPointF(0, 0))
    for side in (-1, 1):
        loops.moveTo(0, 0)
        loops.cubicTo(QPointF(side * 10 * u, -16 * u), QPointF(side * 28 * u, -12 * u), QPointF(side * 22 * u, 0))
        loops.cubicTo(QPointF(side * 28 * u, 12 * u), QPointF(side * 10 * u, 16 * u), QPointF(0, 0))
    loops.moveTo(0, 0)
    loops.cubicTo(QPointF(-8 * u, -10 * u), QPointF(-6 * u, -24 * u), QPointF(0, -22 * u))
    loops.cubicTo(QPointF(6 * u, -24 * u), QPointF(8 * u, -10 * u), QPointF(0, 0))
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(col("#ff2e4d", 0.25), 8 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(loops)
    p.setPen(QPen(col(RED), 3.0 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(loops)
    twist = QPen(col(SHEEN, 0.85), 1.1 * u, Qt.CustomDashLine, Qt.FlatCap, Qt.RoundJoin)
    twist.setDashPattern([2.2, 2.6])
    p.setPen(twist)
    p.drawPath(loops.translated(-0.5 * u, -0.6 * u))
    diamond = QPolygonF([QPointF(0, -6 * u), QPointF(6 * u, 0), QPointF(0, 6 * u), QPointF(-6 * u, 0)])
    p.setBrush(col(RED))
    p.setPen(QPen(col(GOLD), 1.2 * u))
    p.drawPolygon(diamond)
    p.setPen(Qt.NoPen)
    p.rotate(6 * math.sin(t * 2.4))
    p.setBrush(gradient(QPointF(-5 * u, 0), QPointF(5 * u, 0), ((0, "#a8741e"), (0.5, "#fff0b8"), (1, "#a8741e"))))
    p.drawRoundedRect(QRectF(-5 * u, 7 * u, 10 * u, 5 * u), 1.5 * u, 1.5 * u)
    p.setPen(QPen(col(RED), 1.1 * u, Qt.SolidLine, Qt.RoundCap))
    for i in range(9):
        x = (i - 4) * 1.2 * u
        p.drawLine(QPointF(x, 12 * u), QPointF(x * 1.8 + 2 * u * math.sin(t * 3 + i), 34 * u))
    p.setPen(Qt.NoPen)
    p.restore()
