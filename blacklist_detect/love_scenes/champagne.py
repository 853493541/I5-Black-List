"""香槟金 Champagne Toast: a toast in light, bubbles and gold confetti.

Warm champagne light fills the edges. Two crystal flutes rise in the bottom left and clink at
their rims with a starburst; bubbles stream up from them and from both lower corners, catching
the light; a burst of gold foil confetti (squares and thin curls) is thrown up from the clink and
flutters down, turning and flashing gold and white as each piece catches the light. A thin
art-deco gold fan opens in the top right corner. At the end it all settles and fades.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient

from blacklist_detect.love_scenes.draw import Wash, col, ease_back, ease_in, ease_out, gradient, mix, soft_dot, star, win

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
GOLDS = ("#f7e2a6", "#e9c46a", "#d4a64a", "#fff4d0", "#f2d7b6")
FOIL = ("#e9c46a", "#f4d58d", "#d9a7a0", "#fff1cf", "#c9a24a")


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(17)
    clink = QPointF(118 * u, height - 270 * u)
    names = QRectF(width * 0.13, height * 0.29, width * 0.81, height * 0.55)
    bubbles = []
    for _ in range(80):
        source = rnd.random()
        if source < 0.35:
            x = clink.x() + rnd.uniform(-60, 60) * u
            y0 = height - 120 * u
        elif source < 0.68:
            x = rnd.uniform(0.0, 0.12) * width
            y0 = height + 10 * u
        else:
            x = rnd.uniform(0.88, 1.0) * width
            y0 = height + 10 * u
        bubbles.append((rnd.uniform(0.3, 3.6), x, y0, rnd.uniform(120, 230) * u, rnd.uniform(2.0, 6.5) * u, rnd.uniform(0, 6.28)))
    confetti = []
    for _ in range(70):
        angle = math.radians(rnd.uniform(-112, -66))
        speed = rnd.uniform(520, 980) * u
        confetti.append(
            dict(
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
                spin=rnd.uniform(-420, 420),
                flip=rnd.uniform(5, 11),
                size=rnd.uniform(5, 10) * u,
                color=rnd.choice(FOIL),
                curl=rnd.random() < 0.3,
                phase=rnd.uniform(0, 6.28),
                delay=rnd.uniform(0, 0.12),
            )
        )
    rain = [
        dict(x=rnd.uniform(0.0, 1.0) * width, start=rnd.uniform(1.4, 3.6), fall=rnd.uniform(60, 120) * u, spin=rnd.uniform(-300, 300), flip=rnd.uniform(5, 10), size=rnd.uniform(5, 9) * u, color=rnd.choice(FOIL), phase=rnd.uniform(0, 6.28))
        for _ in range(40)
    ]

    light = Wash(lambda q, w, h: _champagne_wash(q, 9.0, w, h, u, 0.0))

    def paint(p: QPainter, t: float) -> None:
        life = win(t, 0.0, 0.3)
        leave = ease_in(win(t, 4.1, 4.95))
        p.save()
        p.setOpacity(life)
        light.paint(p, width, height, gap, ease_out(win(t, 0.0, 0.9)) * (1 - leave))
        _fan(p, t, QPointF(width, 0), u, leave)
        _bubbles(p, t, bubbles, names, u, 1 - leave)
        _flutes(p, t, clink, u, leave)
        _confetti(p, t, confetti, clink, names, height, u, 1 - leave)
        _rain(p, t, rain, names, height, u, 1 - leave)
        p.restore()

    return paint


def _champagne_wash(p: QPainter, t: float, width: float, height: float, u: float, leave: float) -> None:
    a = ease_out(win(t, 0.0, 0.9)) * (1 - leave)
    if a <= 0:
        return
    edge = 170 * u
    for start, end, rect in (
        (QPointF(0, 0), QPointF(edge, 0), QRectF(0, 0, edge, height)),
        (QPointF(width, 0), QPointF(width - edge, 0), QRectF(width - edge, 0, edge, height)),
        (QPointF(0, height), QPointF(0, height - edge), QRectF(0, height - edge, width, edge)),
    ):
        p.fillRect(rect, gradient(start, end, ((0, "#e3b964", 0.28), (1, "#e3b964", 0)), a))
    for cx, cy, r in ((0.0, 1.0, 520), (1.0, 0.0, 420)):
        g = QRadialGradient(QPointF(width * cx, height * cy), r * u)
        g.setColorAt(0, col("#fff0c8", 0.34 * a))
        g.setColorAt(0.5, col("#f2cf86", 0.12 * a))
        g.setColorAt(1, col("#f2cf86", 0))
        p.fillRect(QRectF(0, 0, width, height), g)


def _fan(p: QPainter, t: float, corner: QPointF, u: float, leave: float) -> None:
    """An art-deco sunburst opening from the top right corner: fine gold rays and stepped arcs."""
    open_ = ease_out(win(t, 0.35, 1.4)) * (1 - leave)
    if open_ <= 0:
        return
    reach = 250 * u
    p.setBrush(Qt.NoBrush)
    for i in range(13):
        angle = math.radians(90 + 90 * i / 12 * open_)
        end = QPointF(corner.x() + math.cos(angle) * reach, corner.y() + math.sin(angle) * reach)
        p.setPen(QPen(gradient(corner, end, ((0, "#f7e2a6", 0.9), (1, "#e9c46a", 0))), (1.4 if i % 3 == 0 else 0.8) * u))
        p.drawLine(corner, end)
    for r, w, a in ((90, 1.4, 0.85), (140, 0.9, 0.6), (190, 1.6, 0.7), (205, 0.7, 0.45)):
        rr = r * u
        box = QRectF(corner.x() - rr, corner.y() - rr, 2 * rr, 2 * rr)
        p.setPen(QPen(col("#efd18a", a * open_), w * u))
        p.drawArc(box, 180 * 16, int(90 * 16 * open_))
    shine = win(t, 1.5, 2.3)
    if 0 < shine < 1:
        angle = math.radians(90 + 90 * shine)
        q = QPointF(corner.x() + math.cos(angle) * 190 * u, corner.y() + math.sin(angle) * 190 * u)
        star(p, q.x(), q.y(), 18 * u * math.sin(math.pi * shine), "#ffffff", 1.0)
    p.setPen(Qt.NoPen)


def _flute(p: QPainter, base: QPointF, tilt: float, u: float, alpha: float, fill: float) -> None:
    """A crystal champagne flute: tall bowl with golden wine, a fine stem and a foot."""
    p.save()
    p.translate(base)
    p.rotate(tilt)
    h = 150 * u
    bowl = QPainterPath(QPointF(-17 * u, -h))
    bowl.cubicTo(QPointF(-17 * u, -h * 0.55), QPointF(-12 * u, -h * 0.42), QPointF(-2 * u, -h * 0.38))
    bowl.lineTo(QPointF(2 * u, -h * 0.38))
    bowl.cubicTo(QPointF(12 * u, -h * 0.42), QPointF(17 * u, -h * 0.55), QPointF(17 * u, -h))
    bowl.closeSubpath()
    level = -h * 0.38 - (h * 0.55) * fill
    wine = QPainterPath()
    wine.addRect(QRectF(-20 * u, level, 40 * u, h))
    liquid = bowl.intersected(wine)
    p.setPen(Qt.NoPen)
    p.setBrush(gradient(QPointF(-17 * u, 0), QPointF(17 * u, 0), ((0, "#e8b94e", 0.75 * alpha), (0.45, "#fbe6a6", 0.85 * alpha), (1, "#c9952f", 0.75 * alpha))))
    p.drawPath(liquid)
    p.setBrush(gradient(QPointF(-17 * u, 0), QPointF(17 * u, 0), ((0, "#ffffff", 0.18 * alpha), (0.3, "#ffffff", 0.05 * alpha), (1, "#ffffff", 0.12 * alpha))))
    p.setPen(QPen(col("#fffaf0", 0.85 * alpha), 1.2 * u))
    p.drawPath(bowl)
    p.setPen(QPen(col("#ffffff", 0.9 * alpha), 2.0 * u, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(-11 * u, -h * 0.92), QPointF(-11 * u, -h * 0.6))
    p.setPen(QPen(col("#fffaf0", 0.8 * alpha), 1.6 * u))
    p.drawLine(QPointF(0, -h * 0.38), QPointF(0, -6 * u))
    p.setBrush(col("#ffffff", 0.18 * alpha))
    p.drawEllipse(QPointF(0, -3 * u), 20 * u, 4 * u)
    p.restore()


def _flutes(p: QPainter, t: float, clink: QPointF, u: float, leave: float) -> None:
    rise = ease_out(win(t, 0.25, 1.0))
    if rise <= 0:
        return
    alpha = rise * (1 - leave)
    meet = ease_back(win(t, 0.85, 1.15), 2.4)
    tilt = 16 - 6 * meet
    gap = (1 - meet) * 40 * u
    base_y = clink.y() + 150 * u + (1 - rise) * 120 * u
    _flute(p, QPointF(clink.x() - 46 * u - gap, base_y), tilt, u, alpha, 0.72)
    _flute(p, QPointF(clink.x() + 46 * u + gap, base_y), -tilt, u, alpha, 0.66)
    burst = win(t, 1.12, 1.6)
    if 0 < burst < 1:
        k = math.sin(math.pi * burst)
        soft_dot(p, clink.x(), clink.y() - 4 * u, 120 * u * k, "#fff3cf", 0.75 * k)
        star(p, clink.x(), clink.y() - 4 * u, 64 * u * k, "#ffffff", k, 0.07)
        p.save()
        p.translate(clink.x(), clink.y() - 4 * u)
        p.rotate(45)
        star(p, 0, 0, 32 * u * k, "#fff4d6", 0.8 * k, 0.1)
        p.restore()


def _bubbles(p: QPainter, t: float, bubbles: list[tuple], names: QRectF, u: float, a: float) -> None:
    for born, x, y0, rise, r, phase in bubbles:
        age = t - born
        if age <= 0 or age > 3.4:
            continue
        px = x + 9 * u * math.sin(age * 3 + phase)
        py = y0 - rise * age - 12 * u * age * age
        fade = min(1.0, age / 0.3) * min(1.0, (3.4 - age) / 0.8) * a
        if names.contains(QPointF(px, py)):
            fade *= 0.3
        rr = r * (1 + 0.25 * age)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(col("#fff6dc", 0.7 * fade), max(0.6, rr * 0.18)))
        p.drawEllipse(QPointF(px, py), rr, rr)
        p.setPen(Qt.NoPen)
        p.setBrush(col("#fff8e6", 0.12 * fade))
        p.drawEllipse(QPointF(px, py), rr, rr)
        p.setBrush(col("#ffffff", 0.95 * fade))
        p.drawEllipse(QPointF(px - rr * 0.35, py - rr * 0.35), rr * 0.25, rr * 0.25)


def _foil(p: QPainter, x: float, y: float, size: float, color: str, turn: float, flip: float, curl: bool, alpha: float) -> None:
    """A piece of gold foil: a square or a thin curl, flashing white when it faces the light."""
    if alpha <= 0.01:
        return
    shine = max(0.0, flip) ** 6
    shade = mix(mix(color, "#8a6a2c", 0.35 * (1 - abs(flip))), "#ffffff", 0.75 * shine, alpha)
    p.save()
    p.translate(x, y)
    p.rotate(turn)
    p.scale(1.0, 0.15 + 0.85 * abs(flip))
    p.setPen(Qt.NoPen)
    if curl:
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(shade, size * 0.35, Qt.SolidLine, Qt.RoundCap))
        path = QPainterPath(QPointF(-size * 1.4, 0))
        path.cubicTo(QPointF(-size * 0.6, -size * 1.2), QPointF(size * 0.4, size * 1.2), QPointF(size * 1.4, 0))
        p.drawPath(path)
    else:
        p.setBrush(shade)
        p.drawPolygon(QPolygonF([QPointF(-size * 0.6, -size * 0.45), QPointF(size * 0.6, -size * 0.45), QPointF(size * 0.6, size * 0.45), QPointF(-size * 0.6, size * 0.45)]))
    p.restore()
    if shine > 0.6:
        star(p, x, y, size * 1.6 * shine, "#ffffff", alpha * shine)


def _confetti(p: QPainter, t: float, confetti: list[dict], clink: QPointF, names: QRectF, height: float, u: float, a: float) -> None:
    """Thrown up from the clink, slowed by the air, then fluttering down."""
    for c in confetti:
        age = t - 1.12 - c["delay"]
        if age <= 0:
            continue
        drag = 1.9
        k = (1 - math.exp(-drag * age)) / drag
        x = clink.x() + c["vx"] * k + 14 * u * math.sin(age * 3 + c["phase"])
        y = clink.y() + c["vy"] * k + 70 * u * age * age
        if y > height + 20 * u:
            continue
        fade = min(1.0, age / 0.1) * a * min(1.0, (3.6 - age) / 0.8)
        if names.contains(QPointF(x, y)):
            fade *= 0.3
        _foil(p, x, y, c["size"], c["color"], c["spin"] * age, math.cos(age * c["flip"] + c["phase"]), c["curl"], fade)


def _rain(p: QPainter, t: float, rain: list[dict], names: QRectF, height: float, u: float, a: float) -> None:
    """A few pieces drifting down from the top afterwards, slower, fainter over the names."""
    for c in rain:
        age = t - c["start"]
        if age <= 0:
            continue
        x = c["x"] + 22 * u * math.sin(age * 1.6 + c["phase"])
        y = -12 * u + c["fall"] * age
        fade = min(1.0, age / 0.3) * a
        if names.contains(QPointF(x, y)):
            fade *= 0.35
        _foil(p, x, y, c["size"], c["color"], c["spin"] * age, math.cos(age * c["flip"] + c["phase"]), False, fade)
