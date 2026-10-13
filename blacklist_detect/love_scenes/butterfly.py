"""蝶梦 Glass Butterflies: iridescent butterflies flutter in and settle into a heart.

A faint lavender-to-teal haze rises at the edges. Butterflies with iridescent wings, deep at the
body and bright at the tips, edged in a dark margin with white spots, shift from lilac through
periwinkle to aqua as they turn. They fly in from both sides on looping paths, leaving trails of
shimmer, land with a small sparkle and settle into a heart in the top left, where they keep
breathing their wings. Two larger ones land beside the 心动 heart. At the end they lift off and fly out.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPen, QRadialGradient

from blacklist_detect.love_scenes.draw import (
    clamp,
    col,
    ease_in,
    ease_in_out,
    ease_out,
    gradient,
    heart_points,
    lengths,
    mix,
    point_at,
    soft_dot,
    spectrum,
    star,
    win,
)

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
WINGS = ("#c9a8ff", "#a7b5ff", "#8fd8f2", "#a8f0dc", "#e6b3ff", "#b9a3ff")


def make(stage: Stage):  # noqa: ANN201
    width, height = stage.width, stage.height
    u = stage.unit()
    rnd = random.Random(23)
    outline = heart_points(width * 0.112, height * 0.2, 250 * u, 90)
    # Ten perches evenly spaced along the heart's outline, one in its top dip: two either side of
    # the dip would sit close, the outline folding back there.
    fine = heart_points(width * 0.112, height * 0.2, 250 * u, 360)
    along = lengths([*fine, fine[0]])
    heart = [point_at([*fine, fine[0]], along, along[-1] * i / 10)[0] for i in range(10)]
    perches = [(q, rnd.uniform(30, 35) * u, rnd.uniform(-30, 30)) for q in heart]
    # One lands beside the 心动 heart by the button, one in the top right.
    badge = stage.heart()
    perches.append((QPointF(badge.x() + 52 * u, badge.y() - 38 * u), 42 * u, 24))
    perches.append((QPointF(width * 0.91, height * 0.13), 52 * u, -18))
    flies = []
    for k, (spot, size, angle) in enumerate(perches):
        side = -1 if k % 3 else 1
        origin = QPointF(-80 * u if side < 0 else width + 80 * u, rnd.uniform(0.1, 0.95) * height)
        flies.append(
            dict(
                spot=spot,
                size=size,
                angle=angle,
                origin=origin,
                arrive=0.5 + 0.11 * k + rnd.uniform(0, 0.25),
                hue=rnd.random(),
                phase=rnd.uniform(0, 6.28),
                loop=rnd.uniform(60, 140) * u * (1 if rnd.random() < 0.5 else -1),
                exit=QPointF(rnd.uniform(-0.2, 1.2) * width, -120 * u),
            )
        )
    wanderers = [
        dict(y=rnd.uniform(0.15, 0.85) * height, speed=rnd.uniform(160, 240) * u, size=rnd.uniform(18, 24) * u, start=rnd.uniform(0.3, 2.6), hue=rnd.random(), phase=rnd.uniform(0, 6.28), side=rnd.choice((-1, 1)))
        for _ in range(5)
    ]

    def paint(p: QPainter, t: float) -> None:
        life = win(t, 0.0, 0.35)
        leave = ease_in(win(t, 4.0, 4.95))
        p.save()
        p.setOpacity(life)
        _haze(p, t, width, height, u, leave)
        _outline(p, t, outline, u, leave)
        for fly in flies:
            _trail(p, t, fly, u)
        for w in wanderers:
            _wander(p, t, w, width, u)
        for fly in flies:
            _fly(p, t, fly, u, leave)
            _landing(p, t, fly, u)
        p.restore()

    return paint


def _haze(p: QPainter, t: float, width: float, height: float, u: float, leave: float) -> None:
    a = ease_out(win(t, 0.0, 1.0)) * (1 - leave)
    if a <= 0:
        return
    edge = 200 * u
    drift = 0.5 + 0.5 * math.sin(t * 0.7)
    for start, end, rect, color in (
        (QPointF(0, 0), QPointF(edge, 0), QRectF(0, 0, edge, height), mix("#b49cff", "#7fd6e8", drift)),
        (QPointF(width, 0), QPointF(width - edge, 0), QRectF(width - edge, 0, edge, height), mix("#7fd6e8", "#b49cff", drift)),
        (QPointF(0, 0), QPointF(0, edge * 0.7), QRectF(0, 0, width, edge * 0.7), "#c7b2ff"),
    ):
        p.fillRect(rect, gradient(start, end, ((0, color.name() if hasattr(color, "name") else color, 0.16), (1, "#c7b2ff", 0)), a))
    for cx, cy, r in ((0.11, 0.2, 230), (0.9, 0.14, 180)):
        g = QRadialGradient(QPointF(width * cx, height * cy), r * u)
        g.setColorAt(0, col("#e9ddff", 0.2 * a))
        g.setColorAt(1, col("#e9ddff", 0))
        p.fillRect(QRectF(0, 0, width, height), g)


def _position(t: float, fly: dict, u: float) -> tuple[QPointF, float, float]:
    """Where a butterfly is, the way it faces (degrees), and how settled it is (0 flying, 1 perched)."""
    arrive = fly["arrive"]
    travel = 1.3
    k = clamp((t - (arrive - travel)) / travel)
    leave = ease_in(win(t, 4.0 + fly["phase"] * 0.02, 4.9))
    spot = fly["spot"]
    if k < 1:
        e = ease_in_out(k)
        o = fly["origin"]
        x = o.x() + (spot.x() - o.x()) * e
        y = o.y() + (spot.y() - o.y()) * e
        swirl = math.sin(math.pi * e)
        x += fly["loop"] * swirl * math.cos(e * 6 + fly["phase"])
        y += fly["loop"] * 0.6 * swirl * math.sin(e * 6 + fly["phase"])
        y += 10 * u * math.sin(t * 9 + fly["phase"])
        heading = math.degrees(math.atan2(spot.y() - o.y(), spot.x() - o.x())) * 0.25
        return QPointF(x, y), heading, 0.0
    if leave > 0:
        ex = fly["exit"]
        x = spot.x() + (ex.x() - spot.x()) * leave
        y = spot.y() + (ex.y() - spot.y()) * leave + 6 * u * math.sin(t * 10)
        return QPointF(x, y), fly["angle"] * (1 - leave), 0.0
    return spot, fly["angle"], clamp((t - arrive) / 0.25)


def _fly(p: QPainter, t: float, fly: dict, u: float, leave: float) -> None:
    if t < fly["arrive"] - 1.3:
        return
    where, angle, perched = _position(t, fly, u)
    beat_rate = 13 - 9.5 * perched
    open_ = 0.5 + 0.5 * math.sin(t * beat_rate + fly["phase"])
    open_ = 0.25 + 0.75 * open_ if perched < 1 else 0.55 + 0.45 * open_
    alpha = min(1.0, (t - (fly["arrive"] - 1.3)) / 0.25)
    _butterfly(p, where, fly["size"], angle, open_, fly["hue"] + t * 0.12, alpha, perched)


def _butterfly(p: QPainter, at: QPointF, size: float, angle: float, open_: float, hue: float, alpha: float, perched: float) -> None:
    """Seen from above: four wings, deep near the body and bright iridescent at the tips, each edged
    in a dark margin with a few white spots, with fine dark veins and a thin light rim; a slim dark
    body. Wings narrow as they close, as they would seen from above."""
    p.save()
    p.translate(at)
    p.rotate(angle)
    if perched > 0.5:
        soft_dot(p, 0, 0, size * 2.2, spectrum(WINGS, hue), 0.24 * alpha)
    for side in (-1, 1):
        p.save()
        p.scale(side * (0.18 + 0.82 * open_), 1)
        upper = QPainterPath(QPointF(0, -size * 0.08))
        upper.cubicTo(QPointF(size * 0.35, -size * 0.95), QPointF(size * 1.15, -size * 0.95), QPointF(size * 1.05, -size * 0.35))
        upper.cubicTo(QPointF(size * 1.0, -size * 0.05), QPointF(size * 0.5, size * 0.05), QPointF(0, size * 0.02))
        lower = QPainterPath(QPointF(0, size * 0.04))
        lower.cubicTo(QPointF(size * 0.55, size * 0.05), QPointF(size * 0.9, size * 0.35), QPointF(size * 0.7, size * 0.7))
        lower.cubicTo(QPointF(size * 0.5, size * 0.95), QPointF(size * 0.15, size * 0.65), QPointF(0, size * 0.18))
        for wing, k, tip in ((upper, 0.0, QPointF(size * 1.05, -size * 0.65)), (lower, 0.35, QPointF(size * 0.75, size * 0.75))):
            bright = spectrum(WINGS, hue + k + 0.25)
            deep = mix(spectrum(WINGS, hue + k), "#2b1d5c", 0.55)
            fill = gradient(QPointF(0, 0), tip, ((0, deep.name(), 0.92 * alpha), (0.45, spectrum(WINGS, hue + k).name(), 0.88 * alpha), (0.85, bright.name(), 0.85 * alpha), (1, "#ffffff", 0.8 * alpha)))
            p.setPen(Qt.NoPen)
            p.setBrush(fill)
            p.drawPath(wing)
            # The dark margin: a wide stroke of the outline, only its inner half showing.
            p.save()
            p.setClipPath(wing)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(col("#231a48", 0.62 * alpha), size * 0.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(wing)
            p.restore()
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(col("#ffffff", 0.5 * alpha), max(0.5, size * 0.022)))
            p.drawPath(wing)
        # Fine dark veins.
        p.setPen(QPen(col("#2b1d5c", 0.35 * alpha), max(0.4, size * 0.018)))
        for end in ((0.95, -0.7), (0.7, -0.85), (1.0, -0.35), (0.65, 0.55), (0.45, 0.7)):
            vein = QPainterPath(QPointF(size * 0.05, 0))
            vein.quadTo(QPointF(size * end[0] * 0.5, size * end[1] * 0.3), QPointF(size * end[0] * 0.86, size * end[1] * 0.86))
            p.drawPath(vein)
        # White spots in the margin.
        p.setPen(Qt.NoPen)
        p.setBrush(col("#ffffff", 0.85 * alpha))
        for sx, sy, r in ((0.95, -0.5, 0.055), (0.82, -0.72, 0.045), (1.0, -0.3, 0.04), (0.62, 0.62, 0.045)):
            p.drawEllipse(QPointF(size * sx, size * sy), size * r, size * r)
        p.restore()
    p.setPen(Qt.NoPen)
    p.setBrush(gradient(QPointF(-size * 0.06, 0), QPointF(size * 0.06, 0), ((0, "#2a2348", 0.95 * alpha), (0.5, "#5a4c8a", 0.95 * alpha), (1, "#2a2348", 0.95 * alpha))))
    p.drawRoundedRect(QRectF(-size * 0.06, -size * 0.32, size * 0.12, size * 0.72), size * 0.06, size * 0.06)
    p.setPen(QPen(col("#2a2348", 0.8 * alpha), max(0.5, size * 0.025)))
    p.drawLine(QPointF(0, -size * 0.3), QPointF(-size * 0.22, -size * 0.6))
    p.drawLine(QPointF(0, -size * 0.3), QPointF(size * 0.22, -size * 0.6))
    p.setPen(Qt.NoPen)
    p.setBrush(col("#d9ccff", 0.9 * alpha))
    for tip in (QPointF(-size * 0.22, -size * 0.6), QPointF(size * 0.22, -size * 0.6)):
        p.drawEllipse(tip, size * 0.035, size * 0.035)
    p.restore()


def _landing(p: QPainter, t: float, fly: dict, u: float) -> None:
    """A small burst of sparkle where a butterfly settles."""
    age = t - fly["arrive"]
    if not 0 < age < 0.7:
        return
    k = age / 0.7
    spot = fly["spot"]
    fade = 1 - k
    color = spectrum(WINGS, fly["hue"] + t * 0.12)
    soft_dot(p, spot.x(), spot.y(), fly["size"] * (1.2 + 1.6 * k), color, 0.35 * fade)
    for i in range(6):
        a = math.radians(i * 60 + fly["phase"] * 30)
        r = fly["size"] * (0.6 + 1.5 * ease_out(k))
        star(p, spot.x() + math.cos(a) * r, spot.y() + math.sin(a) * r, 5 * u * fade, "#ffffff", 0.9 * fade)


def _trail(p: QPainter, t: float, fly: dict, u: float) -> None:
    """Shimmer left behind in flight."""
    if not (fly["arrive"] - 1.3 < t < fly["arrive"] + 0.5):
        return
    for k in range(1, 9):
        back = t - k * 0.045
        if back < fly["arrive"] - 1.3:
            break
        where, _a, perched = _position(back, fly, u)
        if perched >= 1:
            continue
        fade = (1 - k / 9) * 0.7
        color = spectrum(WINGS, fly["hue"] + back * 0.12)
        soft_dot(p, where.x(), where.y(), 7 * u, color, fade)
        if k % 3 == 0:
            star(p, where.x(), where.y(), 4 * u, "#ffffff", fade)


def _wander(p: QPainter, t: float, w: dict, width: float, u: float) -> None:
    """Small butterflies crossing and leaving, never landing."""
    age = t - w["start"]
    if age <= 0:
        return
    x = (-40 * u + w["speed"] * age) if w["side"] > 0 else (width + 40 * u - w["speed"] * age)
    if x < -60 * u or x > width + 60 * u:
        return
    y = w["y"] + 30 * u * math.sin(age * 2.2 + w["phase"])
    if 0.15 * width < x < 0.85 * width and 0.25 < y / (width * 0.52) < 0.85:
        alpha = 0.45
    else:
        alpha = 0.9
    open_ = 0.25 + 0.75 * (0.5 + 0.5 * math.sin(age * 14 + w["phase"]))
    _butterfly(p, QPointF(x, y), w["size"], 90 * w["side"] * 0.2, open_, w["hue"] + t * 0.12, alpha * min(1.0, age / 0.3), 0.0)


def _outline(p: QPainter, t: float, points: list[QPointF], u: float, leave: float) -> None:
    """Once the butterflies have settled, a faint ribbon of light joins them into a heart."""
    a = ease_out(win(t, 2.1, 2.8)) * (1 - leave)
    if a <= 0:
        return
    path = QPainterPath(points[0])
    for q in points[1:]:
        path.lineTo(q)
    path.closeSubpath()
    hue = t * 0.12
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(spectrum(WINGS, hue, 0.22 * a), 10 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(path)
    p.setPen(QPen(col("#ffffff", 0.55 * a), 1.2 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(path)
    p.setPen(Qt.NoPen)
    inside = QRadialGradient(path.boundingRect().center(), 120 * u)
    inside.setColorAt(0, spectrum(WINGS, hue + 0.3, 0.2 * a))
    inside.setColorAt(1, spectrum(WINGS, hue + 0.3, 0))
    p.setBrush(inside)
    p.drawPath(path)
