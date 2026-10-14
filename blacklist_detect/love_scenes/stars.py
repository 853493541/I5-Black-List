"""星河许愿 Starry Wish: a dusk sky, a heart drawn in stars, wishes falling.

The top of the screen turns to violet dusk with a magenta glow low in the corners, and a faint
Milky Way arches over the title; stars come out around the edges, bright ones and a haze of
faint ones; in the top left, two wishing stars draw a heart from its tip up both sides and meet
at its top in a flash, and it fills with a soft gold glow; a gold crescent moon rises in the top right; shooting stars streak past
either side of the title; gold star dust drifts down. At the end the heart dims and the sky fades.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient

from blacklist_detect.love_scenes.draw import (
    Wash,
    clamp,
    col,
    ease_in,
    ease_in_out,
    ease_out,
    gradient,
    heart_path,
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
    while len(sky) < 150:
        x, y = rnd.uniform(0, width), rnd.uniform(0, height)
        if names.contains(QPointF(x, y)) or title.contains(QPointF(x, y)) or gap.contains(QPointF(x, y)):
            continue
        if y > height * 0.35 and width * 0.16 < x < width * 0.84:
            continue
        # Most stars small and faint, a few bright: depth, not a sprinkle of equal dots.
        r = rnd.uniform(0.7, 2.1) if rnd.random() < 0.45 else rnd.uniform(0.35, 0.8)
        sky.append((x, y, r * u, rnd.uniform(0.2, 1.4), rnd.uniform(1.5, 4.0), rnd.choice((SILVER, SILVER, LILAC, GOLD))))
    heart_at = QPointF(width * 0.118, height * 0.2)
    meteors = (
        (1.3, QPointF(width * 0.34, -height * 0.02), QPointF(width * 0.16, height * 0.24)),
        (2.3, QPointF(width * 0.97, height * 0.0), QPointF(width * 0.74, height * 0.27)),
        (2.85, QPointF(width * 0.2, -height * 0.03), QPointF(width * 0.04, height * 0.2)),
        (3.25, QPointF(width * 0.6, -height * 0.03), QPointF(width * 0.46, height * 0.06)),
    )
    galaxy = Wash(lambda q, w, h: _milky_way(q, w, h, u, title))
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
        galaxy.paint(p, width, height, gap, ease_out(win(t, 0.3, 1.4)) * (1 - leave))
        _sky(p, t, sky, u, leave)
        _moon(p, t, QPointF(width - 150 * u, 100 * u), u, leave)
        _star_heart(p, t, heart_at, 190 * u, u, leave)
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


def _milky_way(p: QPainter, width: float, height: float, u: float, title: QRectF) -> None:
    """A faint band of starlight arching over the title from the left edge to the right: soft clouds
    of lilac, blue and rose along it, and a haze of tiny stars, fewer over the title. Drawn once."""
    rnd = random.Random(52)

    def along(k: float) -> QPointF:
        # A shallow arch: low at the two edges, highest above the middle.
        return QPointF(width * k, height * (0.2 - 0.2 * math.sin(math.pi * k)))

    p.setPen(Qt.NoPen)
    for _ in range(46):
        k = rnd.random()
        c = along(k)
        r = rnd.uniform(60, 130) * u
        cloud = QRadialGradient(QPointF(c.x(), c.y() + rnd.gauss(0, 18) * u), r)
        cloud.setColorAt(0, col(rnd.choice(("#9d8cff", "#7fa8ff", "#e6a2ff", "#b8b2ff")), rnd.uniform(0.04, 0.08)))
        cloud.setColorAt(1, col("#9d8cff", 0))
        p.setBrush(cloud)
        p.drawEllipse(cloud.center(), r, r)
    for _ in range(520):
        k = rnd.random()
        c = along(k)
        x, y = c.x() + rnd.gauss(0, 8) * u, c.y() + rnd.gauss(0, 26) * u
        if y < 0:
            continue
        alpha = rnd.uniform(0.25, 0.8) * (0.3 if title.contains(QPointF(x, y)) else 1.0)
        p.setBrush(col("#ffffff", alpha))
        r = rnd.uniform(0.35, 1.0) * u
        p.drawEllipse(QPointF(x, y), r, r)


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


def _star_heart(p: QPainter, t: float, centre: QPointF, size: float, u: float, leave: float) -> None:
    """Two wishing stars draw a heart, from its tip up both sides, and meet at its top in a flash;
    their trails stay as its glowing edge, it fills with soft gold light and beats once."""
    fade = 1 - ease_in_out(win(t, 4.05, 4.7))
    if fade <= 0:
        return
    beat = 1 + 0.05 * max(0.0, math.sin(math.pi * win(t, 2.2, 2.5)))
    size *= beat
    ring = heart_points(centre.x(), centre.y(), size, 120)
    # heart_points runs clockwise from the top cleft: the right side down to the tip at 60, then the
    # left side back up. Each trail runs from the tip to the cleft.
    sides = (ring[60::-1], [*ring[60:], ring[0]])
    draw = ease_in_out(win(t, 0.5, 1.5))
    filled = ease_out(win(t, 1.45, 2.1)) * fade
    if filled > 0:
        shape = heart_path(centre.x(), centre.y(), size)
        inside = QRadialGradient(QPointF(centre.x(), centre.y() + size * 0.12), size * 0.62)
        inside.setColorAt(0, col(GOLD, 0.42 * filled))
        inside.setColorAt(0.55, col(LILAC, 0.24 * filled))
        inside.setColorAt(1, col(LILAC, 0.08 * filled))
        p.setPen(Qt.NoPen)
        p.setBrush(inside)
        p.drawPath(shape)
    p.setBrush(Qt.NoBrush)
    for side in sides:
        trail = partial(side, draw)
        if len(trail) < 2:
            continue
        path = polyline(trail)
        # Starlight, not a line: a wide faint haze round a fine bright core.
        for width, color, alpha in ((16, LILAC, 0.06), (8, LILAC, 0.14), (3.4, SILVER, 0.38), (1.3, "#ffffff", 0.95)):
            p.setPen(QPen(col(color, alpha * fade), width * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(path)
        p.setPen(Qt.NoPen)
        if 0 < draw < 1:
            head = trail[-1]
            soft_dot(p, head.x(), head.y(), 20 * u, "#ffffff", 0.75)
            star(p, head.x(), head.y(), 13 * u, "#ffffff", 1.0)
        p.setBrush(Qt.NoBrush)
    p.setPen(Qt.NoPen)
    # Where they meet, a flash of gold.
    meet = math.sin(math.pi * win(t, 1.45, 2.05))
    if meet > 0:
        top = ring[0]
        soft_dot(p, top.x(), top.y(), 34 * u * meet, GOLD, 0.7 * meet)
        star(p, top.x(), top.y(), 26 * u * meet, "#ffffff", meet)
    # Now and then, a glint on a lobe.
    for index, when in ((104, 2.7), (22, 3.25)):
        glint = math.sin(math.pi * win(t, when, when + 0.5)) * fade
        if glint > 0:
            point = ring[index]
            star(p, point.x(), point.y(), 14 * u * glint, "#ffffff", glint)


def _moon(p: QPainter, t: float, centre: QPointF, u: float, leave: float) -> None:
    rise = ease_out(win(t, 0.25, 1.4))
    a = rise * (1 - leave)
    if a <= 0:
        return
    c = QPointF(centre.x(), centre.y() + 40 * u * (1 - rise))
    r = 52 * u
    halo = QRadialGradient(c, 180 * u)
    halo.setColorAt(0, col(GOLD, 0.34 * a))
    halo.setColorAt(0.4, col("#e9b8ff", 0.10 * a))
    halo.setColorAt(1, col("#e9b8ff", 0))
    p.setBrush(halo)
    p.drawEllipse(c, 180 * u, 180 * u)
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
    # A few soft craters on the lit crescent.
    p.save()
    p.setClipPath(crescent)
    for cx, cy, cr in ((-0.55, 0.15, 0.13), (-0.35, 0.55, 0.09), (-0.7, -0.25, 0.08)):
        crater = QRadialGradient(QPointF(c.x() + cx * r, c.y() + cy * r), cr * r)
        crater.setColorAt(0, col("#d9a95c", 0.35 * a))
        crater.setColorAt(1, col("#d9a95c", 0))
        p.setBrush(crater)
        p.drawEllipse(QPointF(c.x() + cx * r, c.y() + cy * r), cr * r, cr * r)
    p.restore()
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
    tail = 320 * u * min(1.0, age / 0.25) * fade
    tail_end = QPointF(head.x() - ux * tail, head.y() - uy * tail)
    nx, ny = -uy, ux
    # A wide soft glow under a slim bright streak.
    for w, alpha in ((7.0 * u, 0.25), (2.2 * u, 0.95)):
        shape = QPolygonF([QPointF(head.x() + nx * w, head.y() + ny * w), tail_end, QPointF(head.x() - nx * w, head.y() - ny * w)])
        p.setBrush(gradient(head, tail_end, ((0, "#ffffff", alpha * fade), (0.3, GOLD, 0.6 * alpha * fade), (1, LILAC, 0))))
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
