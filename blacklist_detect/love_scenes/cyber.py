"""赛博闪电 Cyber Spark: neon, lightning and sparks in a cyberpunk night.

The edges darken to a violet night with a neon grid on the floor in the two bottom corners and
digital rain falling down both sides. A spark runs round the edge of the screen from the top left
and lights two neon tubes behind it, cyan outside and magenta in, cut at the corners like a HUD;
they stutter on as neon does. In the top left a neon heart sign flickers on, magenta round a cyan
heart, and little arcs crawl over it. Lightning strikes down the sides and onto the heart, the
edges flash, and each strike throws a shower of hot sparks that cool to orange and magenta as they
fall. Twice the heart glitches, torn into slices with its colors split. At the end the neon
powers down.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QFont, QImage, QPainter, QPainterPath, QPen, QRadialGradient

from blacklist_detect.love_scenes.draw import (
    Wash,
    clamp,
    col,
    ease_in,
    ease_out,
    gradient,
    heart_path,
    heart_points,
    mix,
    soft_dot,
    star,
    win,
)
from blacklist_detect.love_scenes.light import bloom, blur, glow, mask, rgb

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
CYAN = "#21f6ff"
MAGENTA = "#ff2bd6"
VIOLET = "#7a2cff"
NIGHT = "#0a0420"
# Glow pictures are soft: worked out at this share of the stage's size and laid on scaled up.
SOFT = 0.25
GLYPHS = "01アイウカキ7ハ#ナ"


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(77)
    outer = _frame(width, height, gap, 15 * u, 34 * u, u)
    inner = _frame(width, height, gap, 25 * u, 40 * u, u)
    frame_glow = _frame_glow(width, height, outer, inner, u)
    heart_at = QPointF(width * 0.118, height * 0.19)
    size = 165 * u
    hearts = _heart_glow(heart_at, size, u)
    night = Wash(lambda q, w, h: _night(q, w, h, u))
    flash = Wash(lambda q, w, h: _flash(q, w, h, u))
    top = 15 * u
    strikes = [
        (0.75, QPointF(width * 0.07, -height * 0.03), QPointF(top, height * 0.6), 1),
        (1.55, QPointF(width * 0.95, -height * 0.03), QPointF(width - top, height * 0.52), 2),
        (2.2, QPointF(width * 0.27, -height * 0.03), QPointF(heart_at.x() + size * 0.25, heart_at.y() - size * 0.2), 3),
        (2.95, QPointF(width * 1.02, height * 0.22), QPointF(width - top, height * 0.8), 4),
        (3.45, QPointF(-width * 0.02, height * 0.3), QPointF(top, height * 0.86), 5),
        (3.9, QPointF(width * 0.78, -height * 0.03), QPointF(width * 0.85, top), 6),
    ]
    sparks = {seed: _sparks(end, u, random.Random(seed * 13)) for _when, _start, end, seed in strikes}
    rain = [
        (x, rnd.uniform(0.55, 1.1) * height, rnd.uniform(0, 3), rnd.randrange(1000))
        for x in [width * (0.022 + 0.014 * i) for i in range(6)] + [width * (0.908 + 0.014 * i) for i in range(6)]
    ]
    glyphs = _glyphs(u)
    arcs = [(1.7 + 0.32 * i + rnd.uniform(0, 0.12), rnd.randrange(120), rnd.randrange(6, 26)) for i in range(7)]

    def paint(p: QPainter, t: float) -> None:
        life = win(t, 0.0, 0.3)
        leave = ease_in(win(t, 4.35, 5.0))
        p.save()
        p.setOpacity(life)
        night.paint(p, width, height, gap, ease_out(win(t, 0.0, 0.7)) * (1 - leave))
        bright = max((_strike_light(t - when) for when, *_rest in strikes), default=0.0)
        flash.paint(p, width, height, gap, bright * 0.75 * (1 - leave))
        _rain(p, t, rain, glyphs, u, height, (1 - leave) * ease_out(win(t, 0.2, 1.0)))
        _neon_frame(p, t, outer, inner, frame_glow, width, height, u)
        _heart(p, t, heart_at, size, hearts, u, arcs)
        for when, start, end, seed in strikes:
            _bolt(p, t - when, start, end, seed, u)
        for when, _start, _end, seed in strikes:
            _spark_shower(p, t - when, sparks[seed], u)
        p.restore()

    return paint


def _frame(width: float, height: float, gap: QRectF, inset: float, cut: float, u: float) -> list[QPointF]:
    """The neon tube round the screen as one line from the gap's left round to its right: inset from
    the edges, its corners cut, a tab stepping down under the middle of the top edge."""
    m, c = inset, cut
    bottom = height - m
    left_end, right_end = gap.left() - 40 * u, gap.right() + 40 * u
    tab = 12 * u
    corners = [
        QPointF(left_end, bottom), QPointF(m + c, bottom), QPointF(m, bottom - c), QPointF(m, m + c), QPointF(m + c, m),
        QPointF(width * 0.34, m), QPointF(width * 0.34 + tab, m + tab), QPointF(width * 0.66 - tab, m + tab), QPointF(width * 0.66, m),
        QPointF(width - m - c, m), QPointF(width - m, m + c), QPointF(width - m, bottom - c), QPointF(width - m - c, bottom),
        QPointF(right_end, bottom),
    ]  # fmt: skip
    return _dense(corners, 6 * u)


def _dense(corners: list[QPointF], step: float) -> list[QPointF]:
    out = [corners[0]]
    for a, b in zip(corners, corners[1:], strict=False):
        n = max(1, int(math.dist((a.x(), a.y()), (b.x(), b.y())) / step))
        out.extend(QPointF(a.x() + (b.x() - a.x()) * i / n, a.y() + (b.y() - a.y()) * i / n) for i in range(1, n + 1))
    return out


def _path(points: list[QPointF]) -> QPainterPath:
    path = QPainterPath(points[0])
    for point in points[1:]:
        path.lineTo(point)
    return path


def _frame_glow(width: float, height: float, outer: list[QPointF], inner: list[QPointF], u: float) -> tuple[QImage, QImage]:
    """The light the two tubes throw, worked out per pixel at a quarter of the size: soft anyway."""
    w, h = max(1, round(width * SOFT)), max(1, round(height * SOFT))
    out = []
    for points, tint in ((outer, CYAN), (inner, MAGENTA)):

        def draw(q: QPainter, points: list[QPointF] = points) -> None:
            q.scale(SOFT, SOFT)
            q.setPen(QPen(Qt.white, 5 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            q.drawPath(_path(points))

        out.append(bloom(mask(w, h, draw), tint, ((1.5, 1.1), (5, 0.9), (14, 0.7)), white=0.4))
    return out[0], out[1]


def _heart_glow(centre: QPointF, size: float, u: float) -> tuple[QRectF, QImage, QImage]:
    """The neon heart sign's light at half size: a magenta tube round, a cyan one inside."""
    side = size * 2.3
    box = QRectF(centre.x() - side / 2, centre.y() - side / 2 + size * 0.08, side, side)
    k = 0.5
    px = max(8, round(side * k))
    out = []
    for scale, tint in ((1.0, MAGENTA), (0.66, CYAN)):

        def draw(q: QPainter, scale: float = scale) -> None:
            q.scale(k, k)
            q.translate(-box.left(), -box.top())
            q.setPen(QPen(Qt.white, 6 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            q.drawPath(heart_path(centre.x(), centre.y(), size * scale))

        out.append(bloom(mask(px, px, draw), tint, ((2, 1.2), (7, 1.0), (20, 0.8)), white=0.5))
    return box, out[0], out[1]


def _night(p: QPainter, width: float, height: float, u: float) -> None:
    """The violet night at the edges, scan lines in it, and the neon floor grid in the bottom corners."""
    top = height * 0.3
    p.fillRect(QRectF(0, 0, width, top), gradient(QPointF(0, 0), QPointF(0, top), ((0, NIGHT, 0.82), (0.55, "#22095a", 0.34), (1, "#22095a", 0))))
    side = 190 * u
    for start, end, rect in (
        (QPointF(0, 0), QPointF(side, 0), QRectF(0, 0, side, height)),
        (QPointF(width, 0), QPointF(width - side, 0), QRectF(width - side, 0, side, height)),
        (QPointF(0, height), QPointF(0, height - side), QRectF(0, height - side, width, side)),
    ):
        p.fillRect(rect, gradient(start, end, ((0, NIGHT, 0.74), (0.5, "#1a0840", 0.3), (1, NIGHT, 0))))
    for x, tint in ((0.0, MAGENTA), (width, CYAN)):
        corner = QRadialGradient(QPointF(x, height), 520 * u)
        corner.setColorAt(0, col(tint, 0.34))
        corner.setColorAt(0.5, col(VIOLET, 0.16))
        corner.setColorAt(1, col(VIOLET, 0))
        p.fillRect(QRectF(0, 0, width, height), corner)
    # The floor grid: lines running to a point far off in the middle, crossed by lines closer and
    # closer together toward the horizon, fading out toward the middle of the screen.
    horizon = height * 0.8
    vanish = QPointF(width * 0.5, height * 0.66)
    for left in (True, False):
        edge = 0.0 if left else width
        reach = width * 0.3
        fade = gradient(QPointF(edge, 0), QPointF(edge + (reach if left else -reach), 0), ((0, CYAN if left else MAGENTA, 0.5), (1, VIOLET, 0)))
        pen = QPen(QBrush(fade), 1.4 * u)
        p.setPen(pen)
        for i in range(9):
            x = edge + (1 if left else -1) * (i * 46 - 60) * u * 1.4
            k = (horizon - vanish.y()) / (height - vanish.y())
            top_x = vanish.x() + (x - vanish.x()) * k
            p.drawLine(QPointF(top_x, horizon), QPointF(x, height))
        for j in range(7):
            y = horizon + (height - horizon) * (j / 6) ** 1.8
            p.drawLine(QPointF(edge, y), QPointF(edge + (reach if left else -reach), y))
    # Scan lines over the dark edges only: drawn faint everywhere, then the middle rubbed out.
    p.setPen(QPen(col("#000000", 0.16), 1.2 * u))
    y = 0.0
    while y < height:
        p.drawLine(QPointF(0, y), QPointF(width, y))
        y += 4 * u
    p.setCompositionMode(QPainter.CompositionMode_DestinationOut)
    hole = QRadialGradient(QPointF(width * 0.5, height * 0.55), width * 0.5)
    hole.setColorAt(0, col("#000000", 1))
    hole.setColorAt(0.75, col("#000000", 0.9))
    hole.setColorAt(1, col("#000000", 0))
    p.setPen(Qt.NoPen)
    p.setBrush(hole)
    p.drawEllipse(QPointF(width * 0.5, height * 0.55), width * 0.5, height * 0.52)
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)


def _flash(p: QPainter, width: float, height: float, u: float) -> None:
    """The edges lit blue-white by a strike."""
    for start, end, rect in (
        (QPointF(0, 0), QPointF(260 * u, 0), QRectF(0, 0, 260 * u, height)),
        (QPointF(width, 0), QPointF(width - 260 * u, 0), QRectF(width - 260 * u, 0, 260 * u, height)),
        (QPointF(0, 0), QPointF(0, 200 * u), QRectF(0, 0, width, 200 * u)),
    ):
        p.fillRect(rect, gradient(start, end, ((0, "#bff8ff", 0.4), (0.4, CYAN, 0.14), (1, VIOLET, 0))))


def _neon(t: float, on: float, seed: int) -> float:
    """How lit a neon tube is: off, then stuttering on as neon does, then a faint hum."""
    age = t - on
    if age < 0:
        return 0.0
    for end, level in ((0.05, 1.0), (0.1, 0.15), (0.16, 0.85), (0.2, 0.05), (0.26, 0.7), (0.3, 0.3)):
        if age < end:
            return level
    hum = 0.93 + 0.07 * math.sin(t * 23 + seed) * math.sin(t * 7.3 + seed * 2)
    # Now and then a dip, as a tube with a loose wire does.
    dip = 1 - 0.55 * max(0.0, math.sin(math.pi * win(t, 2.6 + seed * 0.37, 2.68 + seed * 0.37)))
    return hum * dip


def _power_down(t: float, seed: int) -> float:
    """1 while on, stuttering to 0 at the end."""
    age = t - (4.3 + 0.08 * seed)
    if age < 0:
        return 1.0
    for end, level in ((0.06, 0.2), (0.12, 0.9), (0.18, 0.1), (0.26, 0.6), (0.4, 0.25)):
        if age < end:
            return level
    return max(0.0, 0.25 * (1 - (age - 0.4) / 0.25))


def _neon_frame(p: QPainter, t: float, outer: list[QPointF], inner: list[QPointF], glows: tuple[QImage, QImage], width: float, height: float, u: float) -> None:
    """A spark runs round from the top left and lights the tubes behind it; their light comes on
    with a stutter once it is round."""
    trace = ease_out(win(t, 0.3, 1.15))
    if trace <= 0:
        return
    for index, (points, tint, picture, on) in enumerate(((outer, CYAN, glows[0], 1.12), (inner, MAGENTA, glows[1], 1.24))):
        # From the top left corner both ways: down the left to the gap, and on round to the gap's right.
        corner = min(range(len(points)), key=lambda i: points[i].x() + points[i].y())
        halves = (points[corner::-1], points[corner:])
        level = _neon(t, on, index) * _power_down(t, index)
        if level > 0:
            p.save()
            p.setOpacity(p.opacity() * level)
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            p.drawImage(QRectF(0, 0, width, height), picture)
            p.restore()
        lit = max(level, 0.55 if t < on + 0.3 else 0.0)
        for half in halves:
            n = max(2, round(len(half) * trace))
            path = _path(half[:n])
            for w, color, alpha in ((7 * u, tint, 0.5), (3 * u, mix(tint, "#ffffff", 0.75), 0.95)):
                p.setPen(QPen(col(color, alpha * lit), w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                p.setBrush(Qt.NoBrush)
                p.drawPath(path)
            if trace < 1 and index == 0:
                head = half[n - 1]
                p.setPen(Qt.NoPen)
                soft_dot(p, head.x(), head.y(), 56 * u, CYAN, 0.7)
                soft_dot(p, head.x(), head.y(), 16 * u, "#ffffff", 1.0)
                star(p, head.x(), head.y(), 30 * u, "#ffffff", 0.95)


def _heart(p: QPainter, t: float, centre: QPointF, size: float, glows: tuple, u: float, arcs: list[tuple]) -> None:
    box, outer_glow, inner_glow = glows
    surge = max(0.0, 1 - abs(t - 2.24) / 0.25)
    beat = 1 + 0.04 * surge
    glitch = max(math.sin(math.pi * win(t, 2.88, 3.02)), math.sin(math.pi * win(t, 3.6, 3.7)))
    for picture, scale, tint, on, seed in ((outer_glow, 1.0, MAGENTA, 1.25, 3), (inner_glow, 0.66, CYAN, 1.5, 4)):
        level = _neon(t, on, seed) * _power_down(t, seed) * (1 + 0.6 * surge)
        if level <= 0:
            continue
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        base = p.opacity()
        if glitch > 0:
            # Torn into slices, each pushed sideways, its colors split.
            rnd = random.Random(int(t * 30) * 7 + seed)
            bands = 7
            for i in range(bands):
                band = QRectF(box.left() - 40 * u, box.top() + box.height() * i / bands, box.width() + 80 * u, box.height() / bands + 1)
                shift = rnd.uniform(-22, 22) * u * glitch
                p.save()
                p.setClipRect(band)
                # Ghosts either side, then the slice itself.
                for dx, alpha in ((shift - 8 * u * glitch, 0.45), (shift + 8 * u * glitch, 0.45), (shift, 1.0)):
                    p.setOpacity(base * min(1.0, level) * alpha)
                    p.drawImage(box.translated(dx, 0), picture)
                p.restore()
        else:
            p.setOpacity(base * min(1.0, level))
            p.drawImage(box, picture)
            _tube(p, heart_path(centre.x(), centre.y(), size * scale * beat), tint, min(1.0, level), u)
        p.restore()
    # Little arcs crawling over the heart, from one point of it to another near by.
    ring = heart_points(centre.x(), centre.y(), size, 120)
    for when, start, span in arcs:
        age = t - when
        if 0 <= age < 0.22:
            a, b = ring[start], ring[(start + span) % 120]
            _arc(p, a, b, int(t * 25) + start, u, 1 - age / 0.22, 0.5)


def _tube(p: QPainter, path: QPainterPath, tint: str, level: float, u: float) -> None:
    p.setBrush(Qt.NoBrush)
    for w, color, alpha in ((9 * u, tint, 0.45), (4.4 * u, mix(tint, "#ffffff", 0.55), 0.9), (1.8 * u, "#ffffff", 0.95)):
        p.setPen(QPen(col(color, alpha * level), w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)


def _strike_light(age: float) -> float:
    """How bright a strike is, age seconds after it: a flash, a dip, a second flash, then gone."""
    if age < 0 or age > 0.5:
        return 0.0
    if age < 0.05:
        return 1.0
    if age < 0.1:
        return 0.3
    if age < 0.16:
        return 0.9
    return max(0.0, 0.9 * (1 - (age - 0.16) / 0.34)) ** 1.6


def _bolt_points(start: QPointF, end: QPointF, rnd: random.Random, rough: float, levels: int) -> list[QPointF]:
    """A jagged line from start to end: midpoints pushed sideways, less at each finer step."""
    points = [start, end]
    spread = math.dist((start.x(), start.y()), (end.x(), end.y())) * rough
    for _ in range(levels):
        out = [points[0]]
        for a, b in zip(points, points[1:], strict=False):
            dx, dy = b.x() - a.x(), b.y() - a.y()
            length = math.hypot(dx, dy) or 1
            push = rnd.gauss(0, spread)
            out.append(QPointF((a.x() + b.x()) / 2 - dy / length * push, (a.y() + b.y()) / 2 + dx / length * push))
            out.append(b)
        points = out
        spread *= 0.55
    return points


def _bolt(p: QPainter, age: float, start: QPointF, end: QPointF, seed: int, u: float) -> None:
    light = _strike_light(age)
    if light <= 0:
        return
    # It crackles while it is bright, a new shape every 50 ms, then holds as it fades.
    rnd = random.Random(seed * 1000 + min(4, int(age / 0.05)))
    main = _bolt_points(start, end, rnd, 0.09, 7)
    branches = []
    for _ in range(3):
        i = rnd.randrange(len(main) // 5, len(main) * 3 // 4)
        a = main[i]
        rest = main[-1]
        angle = math.atan2(rest.y() - a.y(), rest.x() - a.x()) + rnd.choice((-1, 1)) * rnd.uniform(0.35, 0.8)
        reach = math.dist((a.x(), a.y()), (rest.x(), rest.y())) * rnd.uniform(0.25, 0.45)
        b = QPointF(a.x() + math.cos(angle) * reach, a.y() + math.sin(angle) * reach)
        branches.append(_bolt_points(a, b, rnd, 0.12, 5))
    p.setBrush(Qt.NoBrush)
    for points, scale in ((main, 1.0), *((b, 0.55) for b in branches)):
        path = _path(points)
        for w, color, alpha in ((64, VIOLET, 0.05), (36, CYAN, 0.07), (18, CYAN, 0.16), (7, "#a8fcff", 0.6), (2.6, "#ffffff", 1.0)):
            p.setPen(QPen(col(color, alpha * light), w * u * scale, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(path)
    p.setPen(Qt.NoPen)
    soft_dot(p, end.x(), end.y(), 170 * u, CYAN, 0.5 * light)
    soft_dot(p, end.x(), end.y(), 46 * u, "#ffffff", 0.95 * light)
    soft_dot(p, start.x(), start.y(), 120 * u, VIOLET, 0.35 * light)


def _arc(p: QPainter, a: QPointF, b: QPointF, seed: int, u: float, light: float, scale: float) -> None:
    points = _bolt_points(a, b, random.Random(seed), 0.25, 4)
    path = _path(points)
    p.setBrush(Qt.NoBrush)
    for w, color, alpha in ((10, CYAN, 0.25), (3.5, "#9ffcff", 0.7), (1.4, "#ffffff", 1.0)):
        p.setPen(QPen(col(color, alpha * light), w * u * scale, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)


def _sparks(at: QPointF, u: float, rnd: random.Random) -> list[tuple]:
    out = []
    for _ in range(48):
        angle = rnd.uniform(-math.pi * 0.97, -math.pi * 0.03)
        speed = rnd.uniform(260, 900) * u
        out.append((at, math.cos(angle) * speed, math.sin(angle) * speed, rnd.uniform(0.45, 1.05), rnd.uniform(0.0, 0.06)))
    return out


def _spark_at(at: QPointF, vx: float, vy: float, s: float, u: float) -> QPointF:
    drag, g = 2.6, 1500 * u
    k = (1 - math.exp(-drag * s)) / drag
    return QPointF(at.x() + vx * k, at.y() + (vy + g / drag) * k - g * s / drag)


def _spark_shower(p: QPainter, age: float, sparks: list[tuple], u: float) -> None:
    if age <= 0 or age > 1.2:
        return
    for at, vx, vy, life, delay in sparks:
        s = age - delay
        if s <= 0 or s > life:
            continue
        heat = 1 - s / life
        head = _spark_at(at, vx, vy, s, u)
        tail = _spark_at(at, vx, vy, max(0.0, s - 0.05), u)
        color = mix("#ffffff", "#ffd36b", clamp((0.85 - heat) / 0.25)) if heat > 0.6 else mix("#ff6a2b", "#ffd36b", heat / 0.6) if heat > 0.25 else mix(MAGENTA, "#ff6a2b", heat / 0.25)
        p.setPen(QPen(col(color, 0.35 * min(1.0, heat * 1.6)), (5 + 5 * heat) * u, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(tail, head)
        p.setPen(QPen(col(color, min(1.0, heat * 1.6)), (1.6 + 2.2 * heat) * u, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(tail, head)
        if heat > 0.5:
            p.setPen(Qt.NoPen)
            soft_dot(p, head.x(), head.y(), 16 * u, "#ffe9a8", 0.55 * heat)


def _glyphs(u: float) -> dict[tuple[str, bool], QImage]:
    """Each rain glyph lit once: white for the head of a column, cyan for its trail."""
    out = {}
    side = max(8, round(24 * u))
    font = QFont("Consolas")
    font.setPixelSize(max(6, round(15 * u)))
    for glyph in GLYPHS:
        def draw(q: QPainter, glyph: str = glyph) -> None:
            q.setFont(font)
            q.setPen(Qt.white)
            q.drawText(QRectF(0, 0, side, side), Qt.AlignCenter, glyph)

        shape = mask(side, side, draw)
        for head in (True, False):
            tint = rgb("#e9fdff" if head else CYAN)
            light = (blur(shape, 2.0)[..., None] * 0.9 + (shape ** 1.2)[..., None]) * tint
            out[(glyph, head)] = glow(light.astype(np.float32))
    return out


def _rain(p: QPainter, t: float, columns: list[tuple], glyphs: dict, u: float, height: float, a: float) -> None:
    if a <= 0:
        return
    step = 19 * u
    side = 24 * u
    p.save()
    for x, speed, offset, seed in columns:
        head = ((t + offset) * speed) % (height * 1.25) - height * 0.1
        for i in range(10):
            y = head - i * step
            if y < -step or y > height:
                continue
            fade = (1 - i / 10) ** 1.4
            # Only the dark edges show it: dim it toward the middle height, where names are.
            edge = 1 - 0.6 * clamp(1 - abs(y / height - 0.55) / 0.35)
            glyph = GLYPHS[(seed + i * 7 + int((t + i * 0.13) * 9)) % len(GLYPHS)]
            p.setOpacity(a * fade * 0.55 * edge)
            p.drawImage(QRectF(x - side / 2, y - side / 2, side, side), glyphs[(glyph, i == 0)])
    p.restore()

