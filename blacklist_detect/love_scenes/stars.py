"""星河许愿 Starry Wish: a dusk sky, a heart drawn in stars, wishes falling.

The top of the screen turns to violet dusk with a magenta glow low in the corners; stars come out
around the edges; in the top left, stars light one by one and silver lines join them into a heart
constellation that then glows from inside; a gold crescent moon rises in the top right; shooting
stars streak past either side of the title; gold star dust drifts down. At the end the lines draw
back and the sky fades.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient

from blacklist_detect.love_scenes.draw import (
    clamp,
    col,
    ease_back,
    ease_in,
    ease_in_out,
    ease_out,
    gradient,
    heart_points,
    mix,
    partial,
    polyline,
    soft_dot,
    star,
    win,
)

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
SILVER = "#eef0ff"
LILAC = "#b9a3ff"
GOLD = "#f6d68a"


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(31)
    names = QRectF(width * 0.13, height * 0.29, width * 0.81, height * 0.55)
    title = QRectF(width * 0.38, height * 0.07, width * 0.3, height * 0.18)
    sky = []
    while len(sky) < 90:
        x, y = rnd.uniform(0, width), rnd.uniform(0, height)
        if names.contains(QPointF(x, y)) or title.contains(QPointF(x, y)) or gap.contains(QPointF(x, y)):
            continue
        if y > height * 0.35 and width * 0.16 < x < width * 0.84:
            continue
        sky.append((x, y, rnd.uniform(0.7, 2.1) * u, rnd.uniform(0.2, 1.4), rnd.uniform(1.5, 4.0), rnd.choice((SILVER, SILVER, LILAC, GOLD))))
    heart = heart_points(width * 0.112, height * 0.19, 168 * u, 12)
    meteors = (
        (1.3, QPointF(width * 0.34, -height * 0.02), QPointF(width * 0.16, height * 0.24)),
        (2.3, QPointF(width * 0.97, height * 0.0), QPointF(width * 0.74, height * 0.27)),
        (3.25, QPointF(width * 0.6, -height * 0.03), QPointF(width * 0.46, height * 0.06)),
    )
    dust = [
        (rnd.uniform(0.4, 3.4), (rnd.uniform(0.01, 0.13) if rnd.random() < 0.5 else rnd.uniform(0.87, 0.99)) * width, rnd.uniform(-0.05, 0.6) * height, rnd.uniform(16, 40) * u, rnd.uniform(1.2, 2.6) * u, rnd.uniform(0, 6.28))
        for _ in range(36)
    ]

    def paint(p: QPainter, t: float) -> None:
        life = win(t, 0.0, 0.35)
        leave = ease_in(win(t, 4.1, 5.0))
        p.save()
        p.setOpacity(life)
        _dusk(p, t, width, height, u, leave)
        _sky(p, t, sky, u, leave)
        _moon(p, t, QPointF(width - 150 * u, 96 * u), u, leave)
        _constellation(p, t, heart, u, leave)
        for when, a, b in meteors:
            _meteor(p, t - when, a, b, u)
        _dust(p, t, dust, u, 1 - leave)
        p.restore()

    return paint


def _dusk(p: QPainter, t: float, width: float, height: float, u: float, leave: float) -> None:
    a = ease_out(win(t, 0.0, 0.9)) * (1 - leave)
    if a <= 0:
        return
    top = height * 0.34
    p.fillRect(QRectF(0, 0, width, top), gradient(QPointF(0, 0), QPointF(0, top), ((0, "#130b3c", 0.7), (0.5, "#2b1a6b", 0.3), (1, "#3a2479", 0)), a))
    for x in (0.0, width):
        side = QRadialGradient(QPointF(x, height * 0.55), height * 0.75)
        side.setColorAt(0, col("#2a1a66", 0.3 * a))
        side.setColorAt(1, col("#2a1a66", 0))
        p.fillRect(QRectF(0, 0, width, height), side)
        glow = QRadialGradient(QPointF(x, height), 420 * u)
        glow.setColorAt(0, col("#b44aa8", 0.34 * a))
        glow.setColorAt(0.5, col("#7a2e8e", 0.14 * a))
        glow.setColorAt(1, col("#7a2e8e", 0))
        p.fillRect(QRectF(0, 0, width, height), glow)
    # Nebulae: soft clouds of lilac and rose in the two top corners, slowly breathing.
    for cx, cy, r, color, alpha in ((0.2, 0.04, 330, "#a58bff", 0.2), (0.84, 0.1, 280, "#ff8fd0", 0.15), (0.06, 0.3, 200, "#7f6bff", 0.12)):
        breathe = 1 + 0.06 * math.sin(t * 0.9 + cx * 9)
        cloud = QRadialGradient(QPointF(width * cx, height * cy), r * u * breathe)
        cloud.setColorAt(0, col(color, alpha * a))
        cloud.setColorAt(1, col(color, 0))
        p.fillRect(QRectF(0, 0, width, height * 0.6), cloud)


def _sky(p: QPainter, t: float, sky: list[tuple], u: float, leave: float) -> None:
    for x, y, r, born, rate, color in sky:
        a = ease_out(win(t, born * 0.6, born * 0.6 + 0.5)) * (1 - leave)
        if a <= 0:
            continue
        twinkle = 0.55 + 0.45 * math.sin(t * rate + x * 0.01)
        soft_dot(p, x, y, r * 3.2, color, 0.45 * a * twinkle)
        if r > 1.7 * u:
            star(p, x, y, r * (2.4 + 1.6 * twinkle), "#ffffff", a * twinkle, 0.1)
        else:
            p.setBrush(col("#ffffff", 0.9 * a * twinkle))
            p.drawEllipse(QPointF(x, y), r * 0.6, r * 0.6)


def _constellation(p: QPainter, t: float, points: list[QPointF], u: float, leave: float) -> None:
    """Stars light one by one, then silver lines join them into a heart that glows from inside."""
    n = len(points)
    back = ease_in_out(win(t, 4.05, 4.7))
    draw = ease_in_out(win(t, 1.1, 2.15)) * (1 - back)
    loop = [*points, points[0]]
    if draw > 0:
        line = partial(loop, draw)
        path = polyline(line)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(col(LILAC, 0.22), 6 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
        p.setPen(QPen(col(SILVER, 0.85), 1.2 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
        p.setPen(Qt.NoPen)
        if draw < 1 and line:
            head = line[-1]
            soft_dot(p, head.x(), head.y(), 16 * u, "#ffffff", 0.8)
            star(p, head.x(), head.y(), 11 * u, "#ffffff", 1.0)
    closed = win(t, 2.15, 2.5) * (1 - back)
    if closed > 0:
        shape = QPainterPath()
        shape.addPolygon(QPolygonF(points))
        shape.closeSubpath()
        centre = QPointF(sum(q.x() for q in points) / n, sum(q.y() for q in points) / n)
        pulse = 0.7 + 0.3 * math.sin(math.pi * win(t, 2.15, 2.9))
        inside = QRadialGradient(centre, 110 * u)
        inside.setColorAt(0, col(GOLD, 0.30 * closed * pulse))
        inside.setColorAt(0.6, col(LILAC, 0.16 * closed * pulse))
        inside.setColorAt(1, col(LILAC, 0.0))
        p.setBrush(inside)
        p.drawPath(shape)
    for i, q in enumerate(points):
        lit = ease_back(win(t, 0.5 + i * 0.05, 0.75 + i * 0.05)) * (1 - ease_in(win(t, 4.2, 4.8)))
        if lit <= 0:
            continue
        twinkle = 0.75 + 0.25 * math.sin(t * 3 + i)
        soft_dot(p, q.x(), q.y(), 13 * u * lit, LILAC, 0.6 * lit)
        star(p, q.x(), q.y(), (7 + (5 if i % 3 == 0 else 0)) * u * lit * twinkle, "#ffffff", lit)


def _moon(p: QPainter, t: float, centre: QPointF, u: float, leave: float) -> None:
    rise = ease_out(win(t, 0.25, 1.4))
    a = rise * (1 - leave)
    if a <= 0:
        return
    c = QPointF(centre.x(), centre.y() + 40 * u * (1 - rise))
    r = 40 * u
    halo = QRadialGradient(c, 150 * u)
    halo.setColorAt(0, col(GOLD, 0.34 * a))
    halo.setColorAt(0.4, col("#e9b8ff", 0.10 * a))
    halo.setColorAt(1, col("#e9b8ff", 0))
    p.setBrush(halo)
    p.drawEllipse(c, 150 * u, 150 * u)
    disc = QPainterPath()
    disc.addEllipse(c, r, r)
    bite = QPainterPath()
    bite.addEllipse(QPointF(c.x() + r * 0.45, c.y() - r * 0.22), r * 0.86, r * 0.86)
    crescent = disc.subtracted(bite)
    body = QRadialGradient(QPointF(c.x() - r * 0.5, c.y() + r * 0.1), r * 1.2)
    body.setColorAt(0, col("#fffaf0", a))
    body.setColorAt(0.6, col("#fbe3a8", a))
    body.setColorAt(1, col("#e9bd6e", a))
    p.setBrush(body)
    p.drawPath(crescent)
    # A wish orbiting the moon.
    for k in range(3):
        angle = t * 1.6 + k * 2.1
        x = c.x() + math.cos(angle) * r * 1.9
        y = c.y() + math.sin(angle) * r * 1.1
        star(p, x, y, (4 + 2 * math.sin(t * 4 + k)) * u, "#ffffff", 0.8 * a)


def _meteor(p: QPainter, age: float, start: QPointF, end: QPointF, u: float) -> None:
    """A shooting star: a bright head with a tapering tail of lilac and gold."""
    span = 0.7
    if age < 0 or age > span + 0.35:
        return
    k = ease_out(clamp(age / span))
    head = QPointF(start.x() + (end.x() - start.x()) * k, start.y() + (end.y() - start.y()) * k)
    dx, dy = end.x() - start.x(), end.y() - start.y()
    length = math.hypot(dx, dy) or 1
    ux, uy = dx / length, dy / length
    fade = 1 - clamp((age - span) / 0.35)
    tail = 230 * u * min(1.0, age / 0.25) * fade
    tail_end = QPointF(head.x() - ux * tail, head.y() - uy * tail)
    nx, ny = -uy, ux
    w = 3.2 * u
    shape = QPolygonF([QPointF(head.x() + nx * w, head.y() + ny * w), tail_end, QPointF(head.x() - nx * w, head.y() - ny * w)])
    p.setBrush(gradient(head, tail_end, ((0, "#ffffff", 0.95 * fade), (0.3, GOLD, 0.6 * fade), (1, LILAC, 0))))
    p.drawPolygon(shape)
    soft_dot(p, head.x(), head.y(), 26 * u, "#fff4dc", 0.8 * fade)
    star(p, head.x(), head.y(), 14 * u, "#ffffff", fade)


def _dust(p: QPainter, t: float, dust: list[tuple], u: float, a: float) -> None:
    for born, x, y, fall, r, phase in dust:
        age = t - born
        if age <= 0 or age > 3.2:
            continue
        fade = min(1.0, age / 0.4) * min(1.0, (3.2 - age) / 0.8) * a
        twinkle = 0.5 + 0.5 * math.sin(age * 5 + phase)
        px, py = x + 8 * u * math.sin(age * 1.4 + phase), y + fall * age
        soft_dot(p, px, py, r * 3, GOLD, 0.6 * fade)
        star(p, px, py, r * (1 + 1.6 * twinkle), mix(GOLD, "#ffffff", 0.6), fade * twinkle)
