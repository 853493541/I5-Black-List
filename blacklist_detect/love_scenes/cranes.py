"""纸鹤晚霞 Paper Cranes: a sunset glow, garlands of origami cranes, a flock flying over.

Warm sunset light rises from the bottom corners and a soft sun flares in the top right with a
long anamorphic streak. Strings of folded paper cranes in cream, peach, coral, apricot, lilac and
blush unroll from the top corners, swaying and slowly turning on their threads. A loose flock of
cranes flies across above the title, wings beating. Warm motes float up. At the end the strings
roll back up and the light goes down.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPen, QPolygonF, QRadialGradient

from blacklist_detect.love_scenes.draw import clamp, col, ease_in, ease_out, gradient, soft_dot, spring, star, win

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
PAPERS = (
    ("#fff6ea", "#f3e1c9", "#d9bf9c"),
    ("#ffd9c2", "#ffb895", "#e48c68"),
    ("#ffc0b6", "#ff9a90", "#dc6a62"),
    ("#ffe3ad", "#ffc46b", "#e39d40"),
    ("#f1e2ff", "#d7c0f2", "#b097d6"),
    ("#ffe1ea", "#ffc0d1", "#e893aa"),
)


def make(stage: Stage):  # noqa: ANN201
    width, height = stage.width, stage.height
    u = stage.unit()
    rnd = random.Random(9)
    names = QRectF(width * 0.13, height * 0.29, width * 0.81, height * 0.55)
    strings = []
    for side, xs in ((1, (46, 120, 190)), (-1, (44, 116, 184))):
        for k, x in enumerate(xs):
            at = (x * u) if side > 0 else width - x * u
            gap = rnd.uniform(94, 106) * u
            sizes = [rnd.uniform(72, 86) * u for _ in range(4)]
            # As many cranes as hang clear of the players' cards, swaying included.
            count = 0
            for i, size in enumerate(sizes):
                along = 30 * u + gap * (i + 0.5)
                reach = QRectF(at - size * 0.6, along - size * 0.5, size * 1.2, size * 0.85)
                if reach.intersects(names):
                    break
                count += 1
            count = max(1, count)
            strings.append(
                dict(
                    x=at,
                    count=count,
                    gap=gap,
                    start=0.2 + 0.12 * k + (0.1 if side < 0 else 0),
                    phase=rnd.uniform(0, 6.28),
                    papers=[rnd.randrange(len(PAPERS)) for _ in range(count)],
                    sizes=sizes[:count],
                    spins=[rnd.uniform(0, 6.28) for _ in range(count)],
                )
            )
    flock = [
        dict(
            start=0.45 + 0.2 * i + rnd.uniform(0, 0.1),
            y=rnd.uniform(26, 58) * u,
            size=rnd.uniform(74, 92) * u,
            paper=rnd.randrange(len(PAPERS)),
            phase=rnd.uniform(0, 6.28),
            speed=rnd.uniform(470, 560) * u,
            bob=rnd.uniform(6, 14) * u,
        )
        for i in range(5)
    ]
    motes = [
        (rnd.uniform(0.2, 3.4), rnd.uniform(0.0, 1.0) * width, rnd.uniform(0.7, 1.05) * height, rnd.uniform(18, 46) * u, rnd.uniform(1.2, 2.8) * u, rnd.uniform(0, 6.28))
        for _ in range(40)
    ]

    def paint(p: QPainter, t: float) -> None:
        life = win(t, 0.0, 0.35)
        leave = ease_in(win(t, 4.1, 4.95))
        p.save()
        p.setOpacity(life)
        _sunset(p, t, width, height, u, leave)
        _motes(p, t, motes, names, u, 1 - leave)
        for string in strings:
            _garland(p, t, string, u, leave)
        for bird in flock:
            _flyer(p, t, bird, width, u)
        p.restore()

    return paint


def _sunset(p: QPainter, t: float, width: float, height: float, u: float, leave: float) -> None:
    a = ease_out(win(t, 0.0, 1.0)) * (1 - leave)
    if a <= 0:
        return
    for x in (0.0, width):
        warm = QRadialGradient(QPointF(x, height), 560 * u)
        warm.setColorAt(0, col("#ffb08a", 0.62 * a))
        warm.setColorAt(0.45, col("#ff8f86", 0.26 * a))
        warm.setColorAt(1, col("#ff8f86", 0))
        p.fillRect(QRectF(0, 0, width, height), warm)
    dusk = QRadialGradient(QPointF(0, 0), 480 * u)
    dusk.setColorAt(0, col("#f4b9cf", 0.26 * a))
    dusk.setColorAt(1, col("#f4b9cf", 0))
    p.fillRect(QRectF(0, 0, width, height), dusk)
    sun = QPointF(width * 0.83, height * 0.035)
    glow = QRadialGradient(sun, 330 * u)
    glow.setColorAt(0, col("#fff2d6", 0.7 * a))
    glow.setColorAt(0.2, col("#ffd08f", 0.42 * a))
    glow.setColorAt(1, col("#ffb08a", 0))
    p.fillRect(QRectF(0, 0, width, height * 0.6), glow)
    # An anamorphic streak through the sun, gently breathing.
    breathe = 0.85 + 0.15 * math.sin(t * 2.1)
    streak = gradient(QPointF(width * 0.4, 0), QPointF(width, 0), ((0, "#ffd9a8", 0), (0.72, "#fff4e0", 0.55 * a * breathe), (1, "#ffd9a8", 0.1 * a)))
    p.fillRect(QRectF(width * 0.4, sun.y() - 1.2 * u, width * 0.6, 2.4 * u), streak)
    p.fillRect(QRectF(width * 0.4, sun.y() - 6 * u, width * 0.6, 12 * u), gradient(QPointF(width * 0.4, 0), QPointF(width, 0), ((0, "#ffc38a", 0), (0.72, "#ffc38a", 0.16 * a), (1, "#ffc38a", 0))))
    for k, r, alpha in ((0.22, 26, 0.12), (0.36, 14, 0.10)):
        ghost = QPointF(sun.x() + (width * 0.5 - sun.x()) * k, sun.y() + (height * 0.45 - sun.y()) * k)
        soft_dot(p, ghost.x(), ghost.y(), r * u, "#ffe7c2", alpha * a)
    star(p, sun.x(), sun.y(), 34 * u * breathe, "#ffffff", 0.8 * a, 0.06)


def _crane(p: QPainter, x: float, y: float, size: float, paper: tuple[str, str, str], flap: float, turn: float = 1.0, alpha: float = 1.0) -> None:
    """A folded paper crane seen from the side, facing right: diamond body, neck and tail points,
    two wings, each wing split along its crease into a light and a shaded half."""
    light, mid, dark = paper
    s = size
    p.save()
    p.translate(x, y)
    p.scale(turn, 1.0)
    p.setPen(Qt.NoPen)

    def poly(points, color, a=1.0):  # noqa: ANN001, ANN202
        p.setBrush(col(color, a * alpha))
        p.drawPolygon(QPolygonF([QPointF(px * s, py * s) for px, py in points]))

    lift = -0.16 - 0.5 * flap
    # Far wing, darker and a little behind.
    poly(((-0.16, -0.06), (-0.10, lift - 0.04), (0.04, -0.06)), dark)
    poly(((0.04, -0.06), (-0.10, lift - 0.04), (0.12, -0.06)), mid)
    # Tail and neck: long points, the neck ending in a folded head.
    poly(((-0.12, -0.02), (-0.22, -0.06), (-0.50, -0.40)), mid)
    poly(((-0.12, -0.02), (-0.50, -0.40), (-0.20, 0.05)), dark, 0.92)
    poly(((0.12, -0.02), (0.22, -0.06), (0.44, -0.42)), light)
    poly(((0.12, -0.02), (0.44, -0.42), (0.21, 0.05)), mid, 0.92)
    poly(((0.44, -0.42), (0.56, -0.35), (0.43, -0.36)), dark)
    # Body: a deep diamond, lit on top.
    poly(((-0.26, 0.0), (0.0, -0.12), (0.26, 0.0)), light)
    poly(((-0.26, 0.0), (0.26, 0.0), (0.0, 0.17)), mid)
    poly(((0.0, 0.0), (0.26, 0.0), (0.0, 0.17)), dark, 0.55)
    # Near wing, split along its crease.
    poly(((-0.14, -0.06), (-0.02, lift), (0.02, -0.06)), mid)
    poly(((0.02, -0.06), (-0.02, lift), (0.16, -0.06)), light)
    p.setPen(QPen(col("#ffffff", 0.5 * alpha), max(0.6, s * 0.012)))
    p.drawLine(QPointF(0.02 * s, -0.06 * s), QPointF(-0.02 * s, lift * s))
    p.restore()


def _garland(p: QPainter, t: float, string: dict, u: float, leave: float) -> None:
    """A thread of cranes unrolling from the top edge, swaying, each crane slowly turning."""
    drop = ease_out(win(t, string["start"], string["start"] + 1.0)) * (1 - leave)
    if drop <= 0:
        return
    length = (30 * u + string["gap"] * string["count"]) * drop
    sway = math.radians(3.5 * math.sin(t * 1.3 + string["phase"]) + 9 * spring(t - string["start"] - 0.6, 0.9, 1.6) * (t > string["start"] + 0.6))
    top = QPointF(string["x"], -2 * u)
    end = QPointF(top.x() + math.sin(sway) * length, top.y() + math.cos(sway) * length)
    p.setPen(QPen(col("#fff3e6", 0.65), 0.9 * u))
    p.drawLine(top, end)
    p.setPen(Qt.NoPen)
    for i in range(string["count"]):
        along = 30 * u + string["gap"] * (i + 0.5)
        if along > length:
            break
        cx = top.x() + math.sin(sway) * along
        cy = top.y() + math.cos(sway) * along
        turn = math.cos(t * 0.9 + string["spins"][i])
        size = string["sizes"][i]
        # Light through the paper: a faint warm glow behind each crane, so it reads on the dark lobby.
        soft_dot(p, cx, cy, size * 0.62, "#ffd9b8", 0.22)
        _crane(p, cx, cy + size * 0.08, size, PAPERS[string["papers"][i]], 0.32 + 0.04 * math.sin(t * 2 + i), turn if abs(turn) > 0.12 else 0.12)
        p.setBrush(col("#fff1dd", 0.9))
        p.drawEllipse(QPointF(cx, cy + string["gap"] * 0.5), 2.0 * u, 2.0 * u)


def _flyer(p: QPainter, t: float, bird: dict, width: float, u: float) -> None:
    age = t - bird["start"]
    if age <= 0:
        return
    x = -60 * u + bird["speed"] * age
    if x > width + 80 * u:
        return
    y = bird["y"] + bird["bob"] * math.sin(age * 2.6 + bird["phase"])
    beat = math.sin(age * 2 * math.pi * 2.1 + bird["phase"])
    flap = 0.25 + 0.75 * (0.5 + 0.5 * beat)
    flap = flap * 2 - 1.0
    fade = min(1.0, age / 0.3)
    _crane(p, x, y, bird["size"], PAPERS[bird["paper"]], clamp(flap, -0.6, 1.0), 1.0, fade)


def _motes(p: QPainter, t: float, motes: list[tuple], names: QRectF, u: float, a: float) -> None:
    for born, x, y, rise, r, phase in motes:
        age = t - born
        if age <= 0 or age > 3.4:
            continue
        px, py = x + 10 * u * math.sin(age * 1.3 + phase), y - rise * age
        fade = min(1.0, age / 0.4) * min(1.0, (3.4 - age) / 0.9) * a
        if names.contains(QPointF(px, py)):
            fade *= 0.35
        soft_dot(p, px, py, r * 3.2, "#ffd29a", 0.55 * fade * (0.6 + 0.4 * math.sin(age * 5 + phase)))
