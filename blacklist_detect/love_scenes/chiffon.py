"""雪纺 Runway Chiffon: the lobby becomes the end of a runway.

Sheer chiffon in ivory, blush and rose billows in from both sides as if a fan were blowing it,
its free edges lit; two-strand pearl necklaces drape from the top corners, a drop pearl swinging
below each; light runs along the pearls; camera flashes pop at the edges like a front row; pearl
dust rises along the fabric. At the end the chiffon is pulled away and the pearls lift off.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient

from blacklist_detect.love_scenes.draw import clamp, col, ease_back, ease_in, ease_out, glint, gold_pen, pearl, quad, spring, win

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
# Soft light throughout: drawn at one pixel per point and scaled up on a sharper screen, to keep 30 fps.
MAX_RATIO = 1.0
# Each veil: color, how far in it reaches (part of the width), phase, alpha.
VEILS = (
    ("#f0a9c6", 0.098, 0.0, 0.40),
    ("#ffc9da", 0.080, 2.1, 0.44),
    ("#fff6f8", 0.060, 4.0, 0.50),
)
FLASHES = (1.05, 1.32, 1.62, 2.05, 2.42, 2.9, 3.38, 3.7)


def make(stage: Stage):  # noqa: ANN201
    width, height = stage.width, stage.height
    u = stage.unit()
    sprites = {r: _pearl_sprite(r * u) for r in (5.6, 4.2)}
    rnd = random.Random(8)
    flashes = []
    for when in FLASHES:
        side = rnd.random() < 0.5
        x = rnd.uniform(0.02, 0.11) * width if side else rnd.uniform(0.89, 0.98) * width
        flashes.append((when, x, rnd.uniform(0.18, 0.9) * height))
    dust = [
        (
            rnd.uniform(0.6, 3.6),
            (rnd.uniform(0.01, 0.11) if rnd.random() < 0.5 else rnd.uniform(0.89, 0.99)) * width,
            rnd.uniform(0.55, 1.05) * height,
            rnd.uniform(28, 70) * u,
            rnd.uniform(1.0, 2.6) * u,
            rnd.uniform(0, 6.28),
        )
        for _ in range(34)
    ]

    def paint(p: QPainter, t: float) -> None:
        life = win(t, 0.0, 0.3)
        leave = ease_in(win(t, 4.05, 4.95))
        p.save()
        p.setOpacity(life)
        _stage(p, t, width, height, u, leave)
        for side in (1, -1):
            for color, reach, phase, alpha in VEILS:
                _veil(p, t, side, color, reach, phase, alpha, width, height, u, leave)
        _dust(p, t, dust, u, 1 - leave)
        for side in (1, -1):
            _necklace(p, t, side, width, height, u, sprites, leave)
        _flashes(p, t, flashes, u)
        p.restore()

    return paint


def _stage(p: QPainter, t: float, width: float, height: float, u: float, leave: float) -> None:
    """Soft white stage light from the two top corners."""
    a = ease_out(win(t, 0.0, 0.8)) * (1 - leave)
    for x in (0.0, width):
        light = QRadialGradient(QPointF(x, -40 * u), 520 * u)
        light.setColorAt(0, col("#fff6f9", 0.36 * a))
        light.setColorAt(0.4, col("#ffd3e1", 0.12 * a))
        light.setColorAt(1, col("#ffd3e1", 0))
        p.fillRect(QRectF(0, 0, width, height * 0.7), light)


def _edge(y: float, t: float, reach: float, phase: float, height: float, flutter: float, u: float) -> float:
    """How far in the chiffon reaches at height y: fuller in the middle, rippling upward."""
    k = y / height
    profile = 0.5 + 0.5 * math.sin(math.pi * clamp(k * 0.95 + 0.04) ** 0.85)
    amp = (12 + 34 * flutter) * u
    wave = (
        0.55 * math.sin(2 * math.pi * k / 0.62 + 2.3 * t + phase)
        + 0.3 * math.sin(2 * math.pi * k / 0.24 - 3.2 * t + 2 * phase)
        + 0.15 * math.sin(2 * math.pi * k / 0.11 + 5.1 * t + phase)
    )
    return reach * profile + amp * wave


def _veil(p, t, side, color, reach, phase, alpha, width, height, u, leave) -> None:  # noqa: ANN001
    open_ = ease_back(win(t, 0.05 + phase * 0.03, 1.0 + phase * 0.03), 1.2) * (1 - leave)
    if open_ <= 0.01:
        return
    flutter = math.exp(-1.6 * max(0.0, t - 0.4)) + 1.6 * leave
    full = reach * width * open_
    steps = 64
    xs = []
    for i in range(steps + 1):
        y = -10 * u + (height + 20 * u) * i / steps
        x = max(0.0, _edge(y, t, full, phase, height, flutter, u) * min(1.0, open_ * 1.4))
        xs.append((x, y))

    def place(x: float) -> float:
        return x if side > 0 else width - x

    path = QPainterPath(QPointF(place(-4 * u), -10 * u))
    for x, y in xs:
        path.lineTo(QPointF(place(x), y))
    path.lineTo(QPointF(place(-4 * u), height + 10 * u))
    path.closeSubpath()
    deep = QLinearGradient(QPointF(place(0), 0), QPointF(place(full * 1.15), 0))
    deep.setColorAt(0, col(color, alpha * 1.4))
    deep.setColorAt(0.55, col(color, alpha * 0.8))
    deep.setColorAt(1, col(color, alpha * 0.35))
    p.setPen(Qt.NoPen)
    p.setBrush(deep)
    p.drawPath(path)
    # Folds in the sheer cloth, each following the edge, catching the light.
    p.setBrush(Qt.NoBrush)
    for fold, light in ((0.32, 0.20), (0.55, 0.16), (0.78, 0.22)):
        line = QPainterPath()
        for i, (x, y) in enumerate(xs):
            fx = x * fold + 6 * u * math.sin(y / (70 * u) + t * 1.8 + fold * 9)
            point = QPointF(place(fx), y)
            if i == 0:
                line.moveTo(point)
            else:
                line.lineTo(point)
        p.setPen(QPen(col("#ffffff", light * open_), 1.6 * u))
        p.drawPath(line)
    rim = QPainterPath(QPointF(place(xs[0][0]), xs[0][1]))
    for x, y in xs[1:]:
        rim.lineTo(QPointF(place(x), y))
    p.setPen(QPen(col("#ffffff", 0.12 * open_), 7 * u))
    p.drawPath(rim)
    p.setPen(QPen(col("#ffffff", 0.6 * open_), 1.4 * u))
    p.drawPath(rim)
    p.setPen(Qt.NoPen)


def _pearl_sprite(r: float) -> QImage:
    scale = 4
    side = int(math.ceil(r * 4 * scale))
    image = QImage(side, side, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    q.scale(scale, scale)
    pearl(q, r * 2, r * 2, r)
    q.end()
    return image


def _strand(a: QPointF, b: QPointF, sag: float) -> tuple[QPointF, QPointF, QPointF]:
    mid = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2 + 2 * sag)
    return a, mid, b


def _necklace(p, t, side, width, height, u, sprites, leave) -> None:  # noqa: ANN001
    """Two strands of pearls draped from a top corner, a drop pearl swinging under the longer one."""
    lift = -60 * u * leave
    fade = 1 - ease_out(win(t, 4.1, 4.8))
    if fade <= 0:
        return

    def at(x: float, y: float) -> QPointF:
        return QPointF(x if side > 0 else width - x, y + lift)

    bounce = 1 - 0.22 * spring(t - 0.55, 1.5, 3.0) * (t > 0.55)
    strands = (
        (at(-12 * u, 20 * u), at(width * 0.305, 12 * u), 118 * u * bounce, 5.6, 11.6 * u, 0.5, (1.75, 2.65)),
        (at(-12 * u, 30 * u), at(width * 0.235, 20 * u), 78 * u * bounce, 4.2, 8.8 * u, 0.62, (3.15, 3.9)),
    )
    for a, b, sag, size, step, starts, (g0, g1) in strands:
        curve = _strand(a, b, sag)
        samples = [quad(*curve, i / 400) for i in range(401)]
        lengths = [0.0]
        for s0, s1 in zip(samples, samples[1:], strict=False):
            lengths.append(lengths[-1] + math.dist((s0.x(), s0.y()), (s1.x(), s1.y())))
        count = int(lengths[-1] / step)
        shown = count * ease_out(win(t, starts, starts + 0.9))
        sweep = (t - g0) / (g1 - g0)
        sprite = sprites[size]
        r = size * u
        # A fine gold thread behind the pearls.
        if shown > 1:
            thread = QPainterPath(samples[0])
            last = int(400 * min(1.0, shown / max(count, 1)))
            for point in samples[1 : last + 1]:
                thread.lineTo(point)
            p.setBrush(Qt.NoBrush)
            p.setPen(gold_pen(0.8 * u, 0.7 * fade, 40 * u))
            p.drawPath(thread)
            p.setPen(Qt.NoPen)
        j = 0
        for i in range(count):
            if i > shown:
                break
            goal = i * step
            while j < len(lengths) - 1 and lengths[j] < goal:
                j += 1
            point = samples[j]
            grow = clamp(shown - i)
            shine = math.exp(-(((i / max(count, 1)) - sweep) / 0.05) ** 2) if 0 <= sweep <= 1.1 else 0.0
            p.save()
            p.setOpacity(p.opacity() * fade)
            rr = r * ease_back(grow, 2.2)
            p.drawImage(QRectF(point.x() - rr * 2, point.y() - rr * 2, rr * 4, rr * 4), sprite)
            if shine > 0.05:
                glint(p, point.x() - rr * 0.36, point.y() - rr * 0.38, rr * (1.4 + 3.2 * shine), shine)
            p.restore()
        if size == 5.6 and shown >= count * 0.98:
            # The drop pearl: a teardrop on a short gold link, swinging under the lowest point.
            low = quad(*curve, 0.5)
            swing = math.radians(20 * spring(t - 1.3, 1.1, 1.7) + 3 * math.sin(t * 1.8 + side))
            hang = 30 * u
            tip = QPointF(low.x() + math.sin(swing) * hang, low.y() + math.cos(swing) * hang)
            appear = ease_back(win(t, 1.3, 1.6))
            p.save()
            p.setOpacity(p.opacity() * fade)
            p.setPen(gold_pen(1.1 * u, 0.9, 20 * u))
            p.drawLine(low, tip)
            p.setPen(Qt.NoPen)
            p.translate(tip)
            p.rotate(-math.degrees(swing))
            drop = 9.5 * u * appear
            if drop > 0.5:
                shape = QPainterPath(QPointF(0, -drop * 0.2))
                shape.cubicTo(QPointF(drop * 0.9, drop * 0.5), QPointF(drop * 0.8, drop * 1.7), QPointF(0, drop * 1.8))
                shape.cubicTo(QPointF(-drop * 0.8, drop * 1.7), QPointF(-drop * 0.9, drop * 0.5), QPointF(0, -drop * 0.2))
                body = QRadialGradient(QPointF(-drop * 0.3, drop * 0.6), drop * 1.6)
                body.setColorAt(0, col("#ffffff"))
                body.setColorAt(0.3, col("#fff3f2"))
                body.setColorAt(0.7, col("#efdbe6"))
                body.setColorAt(1, col("#c7b1c9"))
                p.setBrush(body)
                p.drawPath(shape)
                p.setBrush(col("#ffffff", 0.9))
                p.drawEllipse(QPointF(-drop * 0.28, drop * 0.55), drop * 0.18, drop * 0.3)
                p.setBrush(gold_pen(1, 1, 6 * u).brush())
                p.drawEllipse(QPointF(0, -drop * 0.15), drop * 0.32, drop * 0.22)
                pulse = max(0.0, math.sin(math.pi * win(t, 2.55, 2.95)))
                if pulse > 0:
                    glint(p, -drop * 0.28, drop * 0.55, drop * (1.5 + 3 * pulse), pulse)
            p.restore()


def _flashes(p: QPainter, t: float, flashes: list[tuple], u: float) -> None:
    """Front-row camera flashes popping at the edges: a white burst and a sharp star, gone in a blink."""
    for when, x, y in flashes:
        age = t - when
        if age < 0 or age > 0.32:
            continue
        k = math.exp(-age * 14)
        burst = QRadialGradient(QPointF(x, y), 110 * u)
        burst.setColorAt(0, col("#ffffff", 0.6 * k))
        burst.setColorAt(0.25, col("#ffe4ee", 0.22 * k))
        burst.setColorAt(1, col("#ffe4ee", 0))
        p.setPen(Qt.NoPen)
        p.setBrush(burst)
        p.drawEllipse(QPointF(x, y), 110 * u, 110 * u)
        glint(p, x, y, 30 * u * (0.6 + 0.4 * k), k)


def _dust(p: QPainter, t: float, dust: list[tuple], u: float, a: float) -> None:
    """Pearl dust rising slowly along the chiffon, twinkling."""
    p.setPen(Qt.NoPen)
    for born, x, y, rise, r, phase in dust:
        age = t - born
        if age <= 0 or age > 3.0:
            continue
        fade = min(1.0, age / 0.4) * min(1.0, (3.0 - age) / 0.9) * a
        twinkle = 0.5 + 0.5 * math.sin(age * 6 + phase)
        px, py = x + 10 * u * math.sin(age * 1.5 + phase), y - rise * age
        dot = QRadialGradient(QPointF(px, py), r * 3)
        dot.setColorAt(0, col("#ffffff", 0.95 * fade * twinkle))
        dot.setColorAt(0.35, col("#ffd6e4", 0.45 * fade * twinkle))
        dot.setColorAt(1, col("#ffd6e4", 0))
        p.setBrush(dot)
        p.drawEllipse(QPointF(px, py), r * 3, r * 3)
