"""缎带 Maison Ribbon: the lobby arrives gift-wrapped.

A blush satin ribbon slides in along the top and down the left edge, a couture bow ties itself on
the top ribbon with a pearl at its knot, a champagne double rule draws itself inside the ribbon,
light runs along the satin, and a small 心动 · COUP DE CŒUR signature settles in the bottom right.
At the end the ribbon slides back out the way it came.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient

from blacklist_detect.love_scenes.draw import (
    GOLD,
    GOLD_LIGHT,
    clamp,
    col,
    ease_back,
    ease_in,
    ease_in_out,
    ease_out,
    glint,
    gold_pen,
    gradient,
    partial,
    pearl,
    polyline,
    spring,
    win,
)

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
SATIN = (
    (0.0, "#a95d79"),
    (0.10, "#d995ab"),
    (0.28, "#f6d3dc"),
    (0.40, "#fff7f8"),
    (0.52, "#f5d0d9"),
    (0.78, "#e2a4b5"),
    (1.0, "#b56b86"),
)
FACE = "#fbe3ea"
EDGE = "#a6587a"


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    band = 26 * u
    top_y = 52 * u
    left_x = 26 * u
    bow = QPointF(width * 0.17, top_y)
    inset = 56 * u
    dust = _dust(bow, u)

    def paint(p: QPainter, t: float) -> None:
        life = win(t, 0.0, 0.25)
        leave = ease_in(win(t, 4.25, 4.95))
        p.save()
        p.setOpacity(life)
        _bloom(p, t, bow, width, height, u, leave)
        _frame(p, t, width, height, inset, top_y + band / 2, gap, u, leave)
        reach_v = (height + 40 * u) * ease_out(win(t, 0.2, 1.05)) * (1 - leave)
        reach_h = (width + 40 * u) * ease_out(win(t, 0.12, 1.0)) * (1 - leave)
        sheens = [(s, a) for s, a in ((ease_in_out(win(t, 1.55, 2.6)), 1.0), (ease_in_out(win(t, 3.1, 4.0)), 0.5)) if 0 < s < 1]
        _band(p, left_x, -2 * u, reach_v, band, False, t, u, [(s * height, a) for s, a in sheens])
        _band(p, -2 * u, top_y, reach_h, band, True, t, u, [(bow.x() + s * (width - bow.x()), a) for s, a in sheens])
        # Where the top ribbon lies over the side one, a little shade.
        p.fillRect(QRectF(left_x - band / 2, top_y + band / 2, band, 3 * u), col("#6b2140", 0.18 * min(reach_h / (width + 1), 1)))
        size = 1.05 * ease_back(win(t, 0.75, 1.35), 1.6) * (1 - ease_in(win(t, 4.15, 4.65)))
        if size > 0.01:
            _bow(p, t, bow, size, u)
        _dust_paint(p, t, dust, u, 1 - leave)
        _signature(p, t, width, height, inset, u, leave)
        p.restore()

    return paint


def _bloom(p: QPainter, t: float, bow: QPointF, width: float, height: float, u: float, leave: float) -> None:
    """Blush light behind the bow and a faint rose wash along the wrapped edges."""
    a = ease_out(win(t, 0.4, 1.3)) * (1 - leave)
    if a <= 0:
        return
    halo = QRadialGradient(QPointF(bow.x(), bow.y() + 20 * u), 330 * u)
    halo.setColorAt(0, col("#ffc7da", 0.34 * a))
    halo.setColorAt(0.5, col("#ffc7da", 0.10 * a))
    halo.setColorAt(1, col("#ffc7da", 0))
    p.fillRect(QRectF(0, 0, width, height * 0.6), halo)
    for start, end, rect in (
        (QPointF(0, 0), QPointF(0, 120 * u), QRectF(0, 0, width, 120 * u)),
        (QPointF(0, 0), QPointF(140 * u, 0), QRectF(0, 0, 140 * u, height)),
    ):
        p.fillRect(rect, gradient(start, end, ((0, "#ff9fc2", 0.20), (1, "#ff9fc2", 0)), a))


def _band(p: QPainter, x: float, y: float, length: float, thick: float, across: bool, t: float, u: float, sheens) -> None:  # noqa: ANN001
    """A satin ribbon from (x, y) along its length, its free end cut in a swallowtail."""
    if length <= 1:
        return
    half = thick / 2
    notch = 13 * u
    path = QPainterPath()
    if across:
        end = x + length
        path.moveTo(x, y - half)
        path.lineTo(end, y - half)
        path.lineTo(end - notch, y)
        path.lineTo(end, y + half)
        path.lineTo(x, y + half)
        shade = gradient(QPointF(0, y - half), QPointF(0, y + half), SATIN)
        along = (QPointF(x, 0), QPointF(x + 1, 0))
    else:
        end = y + length
        path.moveTo(x - half, y)
        path.lineTo(x - half, end)
        path.lineTo(x, end - notch)
        path.lineTo(x + half, end)
        path.lineTo(x + half, y)
        shade = gradient(QPointF(x + half, 0), QPointF(x - half, 0), SATIN)
        along = (QPointF(0, y), QPointF(0, y + 1))
    path.closeSubpath()
    p.setPen(Qt.NoPen)
    # A soft shadow under the ribbon, so it lies on the screen and not in it.
    p.setBrush(col("#4a1328", 0.16))
    p.drawPath(path.translated(2 * u, 4 * u) if across else path.translated(4 * u, 2 * u))
    p.setBrush(shade)
    p.drawPath(path)
    p.save()
    p.setClipPath(path)
    # The cloth rises and falls along its length: soft light and shade, drifting slowly.
    period = 230 * u
    drift = t * 26 * u
    if across:
        folds = QLinearGradient(QPointF(drift, 0), QPointF(drift + period, 0))
    else:
        folds = QLinearGradient(QPointF(0, drift), QPointF(0, drift + period))
    folds.setSpread(QLinearGradient.RepeatSpread)
    folds.setColorAt(0, col("#ffffff", 0))
    folds.setColorAt(0.3, col("#ffffff", 0.24))
    folds.setColorAt(0.48, col("#ffffff", 0))
    folds.setColorAt(0.78, col("#9e3f66", 0.16))
    folds.setColorAt(1, col("#ffffff", 0))
    p.fillPath(path, folds)
    # Light running along the satin.
    for s, a in sheens:
        if across:
            run = QLinearGradient(QPointF(s - 70 * u, y + half), QPointF(s + 70 * u, y - half))
        else:
            run = QLinearGradient(QPointF(x - half, s - 70 * u), QPointF(x + half, s + 70 * u))
        run.setColorAt(0, col("#ffffff", 0))
        run.setColorAt(0.5, col("#ffffff", 0.85 * a))
        run.setColorAt(1, col("#ffffff", 0))
        p.fillPath(path, run)
    p.restore()
    # Selvedge: a fine light line inside each edge.
    p.setPen(QPen(col("#fff2f6", 0.75), 0.9 * u))
    if across:
        for edge in (y - half + 2.2 * u, y + half - 2.2 * u):
            p.drawLine(QPointF(x, edge), QPointF(end - (notch if abs(edge - y) < 1 else 0) - 2 * u, edge))
    else:
        for edge in (x - half + 2.2 * u, x + half - 2.2 * u):
            p.drawLine(QPointF(edge, y), QPointF(edge, end - 2 * u))
    p.setPen(Qt.NoPen)
    del along


def _bow(p: QPainter, t: float, at: QPointF, size: float, u: float) -> None:
    p.save()
    p.translate(at)
    settle = ease_out(win(t, 0.75, 1.6))
    p.rotate(-12 * (1 - settle) + 1.6 * math.sin(t * 1.4))
    p.scale(size * u, size * u)
    tails = _tails(t)
    # Shadow, softened by stacking a few offset copies.
    shadow = QPainterPath()
    for strips in tails:
        for quad_path, _light in strips:
            shadow.addPath(quad_path)
    shadow.addPath(_loop())
    shadow.addPath(_mirror(_loop()))
    p.setPen(Qt.NoPen)
    for k, a in ((1.0, 0.07), (2.0, 0.06), (3.2, 0.05)):
        p.setBrush(col("#3d0f22", a))
        p.drawPath(shadow.translated(3 * k, 5 * k))
    for strips in tails:
        for quad_path, light in strips:
            p.setBrush(_mix(EDGE, FACE, light))
            p.drawPath(quad_path)
    pulse = math.sin(math.pi * win(t, 1.4, 1.85))
    for side in (1, -1):
        p.save()
        if side < 0:
            p.scale(-1, 1)
            p.rotate(-4)
        loop = _loop()
        p.setBrush(gradient(QPointF(0, 0), QPointF(-136, -16), ((0, "#a95d79"), (0.16, "#dc9db0"), (0.46, "#fff6f8"), (0.6, "#f6d2dc"), (0.86, "#e2a0b3"), (1, "#c27893"))))
        p.drawPath(loop)
        p.setBrush(gradient(QPointF(-14, 0), QPointF(-118, -14), ((0, "#8e3d61", 0.62), (1, "#c98199", 0.28))))
        p.drawPath(_fold())
        if pulse > 0:
            p.setBrush(col("#ffffff", 0.32 * pulse))
            p.drawPath(loop)
        rim = QPainterPath(QPointF(-12, -4))
        rim.cubicTo(QPointF(-44, -50), QPointF(-124, -54), QPointF(-134, -18))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(col("#ffffff", 0.7), 1.6))
        p.drawPath(rim)
        p.setPen(Qt.NoPen)
        p.restore()
    # The knot, and a pearl set in a gold bezel on it.
    knot = QRectF(-16, -17, 32, 34)
    p.setBrush(gradient(QPointF(0, -17), QPointF(0, 17), ((0, "#dc9db0"), (0.38, "#fff5f7"), (0.62, "#e4a7b7"), (1, "#a95d79"))))
    p.drawRoundedRect(knot, 10, 10)
    p.setBrush(Qt.NoBrush)
    p.setPen(gold_pen(2.4, 1.0, 9))
    p.drawEllipse(QPointF(0, 0), 10.5, 10.5)
    p.setPen(Qt.NoPen)
    pearl(p, 0, 0, 9, 1.0, 0.8 * pulse)
    p.restore()


def _loop() -> QPainterPath:
    loop = QPainterPath(QPointF(-12, -4))
    loop.cubicTo(QPointF(-44, -50), QPointF(-124, -54), QPointF(-134, -18))
    loop.cubicTo(QPointF(-140, 14), QPointF(-96, 34), QPointF(-12, 10))
    loop.closeSubpath()
    return loop


def _fold() -> QPainterPath:
    fold = QPainterPath(QPointF(-14, -2))
    fold.cubicTo(QPointF(-46, -36), QPointF(-106, -40), QPointF(-118, -14))
    fold.cubicTo(QPointF(-100, -6), QPointF(-54, -4), QPointF(-14, 4))
    fold.closeSubpath()
    return fold


def _mirror(path: QPainterPath) -> QPainterPath:
    from PySide6.QtGui import QTransform

    return QTransform().scale(-1, 1).map(path)


def _tails(t: float) -> list[list[tuple[QPainterPath, float]]]:
    """Two tails hanging from the knot, swinging after the bow lands and then stirring in the air.

    Each tail is cut into strips; where the ribbon turns its edge to us it is narrow and darker,
    where it shows its face it is wide and pale, so it reads as satin twisting as it falls.
    """
    swing = 22 * spring(t - 1.05, 1.25, 2.4) * (t > 1.05)
    out = []
    for side, (c1x, c1y, c2x, c2y, ex, ey, phase) in ((-1, (-8, 46, -56, 70, -66, 136, 0.0)), (1, (14, 50, 58, 64, 78, 126, 1.7))):
        stir = 6 * math.sin(t * 1.9 + phase)
        angle = math.radians(swing * side * 0.6 + stir)
        ca, sa = math.cos(angle), math.sin(angle)

        def turn(x: float, y: float, ca: float = ca, sa: float = sa) -> QPointF:
            return QPointF(x * ca - y * sa, x * sa + y * ca)

        pts = (QPointF(side * 6, 8), turn(c1x, c1y), turn(c2x, c2y), turn(ex, ey))
        steps = 26
        centre = []
        for i in range(steps + 1):
            s = i / steps
            m = 1 - s
            x = m ** 3 * pts[0].x() + 3 * m * m * s * pts[1].x() + 3 * m * s * s * pts[2].x() + s ** 3 * pts[3].x()
            y = m ** 3 * pts[0].y() + 3 * m * m * s * pts[1].y() + 3 * m * s * s * pts[2].y() + s ** 3 * pts[3].y()
            centre.append((x, y))
        edges = []
        for i, (x, y) in enumerate(centre):
            nx_, ny_ = centre[min(i + 1, steps)]
            px_, py_ = centre[max(i - 1, 0)]
            dx, dy = nx_ - px_, ny_ - py_
            norm = math.hypot(dx, dy) or 1
            s = i / steps
            face = math.cos(2.6 * s + t * 1.5 + phase)
            w = (12 + 4 * s) * (0.42 + 0.58 * abs(face))
            edges.append((QPointF(x - dy / norm * w, y + dx / norm * w), QPointF(x + dy / norm * w, y - dx / norm * w), abs(face), (dx / norm, dy / norm)))
        strips = []
        for i in range(steps):
            a_l, a_r, a_face, _ = edges[i]
            b_l, b_r, b_face, (tx, ty) = edges[i + 1]
            grow = 0.8
            b_l = QPointF(b_l.x() + tx * grow, b_l.y() + ty * grow)
            b_r = QPointF(b_r.x() + tx * grow, b_r.y() + ty * grow)
            strip = QPainterPath(a_l)
            if i == steps - 1:
                # Swallowtail cut at the end.
                mid = QPointF((b_l.x() + b_r.x()) / 2 - tx * 9, (b_l.y() + b_r.y()) / 2 - ty * 9)
                strip.lineTo(b_l)
                strip.lineTo(mid)
                strip.lineTo(b_r)
            else:
                strip.lineTo(b_l)
                strip.lineTo(b_r)
            strip.lineTo(a_r)
            strip.closeSubpath()
            sheen = 0.25 * max(0.0, math.sin(math.pi * clamp((i / steps) * 1.4 - (t % 3.2) / 3.2 * 1.4 + 0.2)))
            strips.append((strip, clamp(0.15 + 0.85 * (a_face + b_face) / 2 + sheen)))
        out.append(strips)
    return out


def _mix(a: str, b: str, k: float):  # noqa: ANN202
    from PySide6.QtGui import QColor

    ca, cb = QColor(a), QColor(b)
    return QColor(
        round(ca.red() + (cb.red() - ca.red()) * k),
        round(ca.green() + (cb.green() - ca.green()) * k),
        round(ca.blue() + (cb.blue() - ca.blue()) * k),
    )


def _frame(p: QPainter, t: float, width: float, height: float, inset: float, hang: float, gap: QRectF, u: float, leave: float) -> None:
    """A champagne double rule that drops from the ribbon down both sides and runs in along the bottom,
    parting around the button."""
    grow = ease_in_out(win(t, 0.95, 2.05))
    a = 1 - ease_out(win(t, 4.15, 4.75))
    if grow <= 0 or a <= 0:
        return
    for k, (pad, pen_w, alpha) in enumerate(((inset, 1.5 * u, 0.95), (inset + 6 * u, 0.7 * u, 0.6))):
        bottom = height - pad
        right = width - pad
        lines = (
            [QPointF(right, hang), QPointF(right, bottom), QPointF(gap.right() + 6 * u, bottom)],
            [QPointF(pad, hang), QPointF(pad, bottom), QPointF(gap.left() - 6 * u, bottom)],
        )
        p.setBrush(Qt.NoBrush)
        p.setPen(gold_pen(pen_w, alpha * a, 260 * u))
        for line in lines:
            p.drawPath(polyline(partial(line, ease_in_out(clamp(grow * 1.08 - 0.04 * k)))))
    p.setPen(Qt.NoPen)
    corners = (
        (QPointF(width - inset - 3 * u, hang + 4 * u), 0.0),
        (QPointF(inset + 3 * u, hang + 4 * u), 0.0),
        (QPointF(width - inset - 3 * u, height - inset - 3 * u), 0.62),
        (QPointF(inset + 3 * u, height - inset - 3 * u), 0.62),
        (QPointF(gap.right() + 6 * u, height - inset - 3 * u), 0.98),
        (QPointF(gap.left() - 6 * u, height - inset - 3 * u), 0.98),
    )
    for point, when in corners:
        k = ease_back(clamp((grow - when) / 0.12 + (grow >= 1) * 1.0))
        if k > 0:
            pearl(p, point.x(), point.y(), 4.8 * u * k, a, 0.7 * max(0.0, math.sin(math.pi * win(t, 2.45 + when, 2.9 + when))))


def _dust(bow: QPointF, u: float) -> list[tuple]:
    rnd = random.Random(11)
    out = []
    for _ in range(26):
        out.append(
            (
                rnd.uniform(1.25, 3.9),
                bow.x() + rnd.uniform(-70, 70) * u,
                bow.y() + rnd.uniform(10, 50) * u,
                rnd.uniform(-12, 34) * u,
                rnd.uniform(22, 58) * u,
                rnd.uniform(0.9, 2.8) * u,
                rnd.uniform(0, 6.28),
                rnd.random() < 0.55,
            )
        )
    return out


def _dust_paint(p: QPainter, t: float, dust: list[tuple], u: float, a: float) -> None:
    """Gold and white dust shaken loose from the bow, drifting down and twinkling."""
    for born, x, y, vx, vy, r, phase, gold in dust:
        age = t - born
        if age <= 0 or age > 2.6:
            continue
        fade = min(1.0, age / 0.3) * min(1.0, (2.6 - age) / 0.8) * a
        twinkle = 0.55 + 0.45 * math.sin(age * 7 + phase)
        px, py = x + vx * age + 6 * u * math.sin(age * 2 + phase), y + vy * age
        if r > 2.2 * u:
            glint(p, px, py, r * 2.4, fade * twinkle)
        else:
            dot = QRadialGradient(QPointF(px, py), r * 2.2)
            tone = GOLD_LIGHT if gold else "#ffffff"
            dot.setColorAt(0, col(tone, 0.95 * fade * twinkle))
            dot.setColorAt(0.4, col(tone if not gold else GOLD, 0.5 * fade * twinkle))
            dot.setColorAt(1, col(GOLD, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(dot)
            p.drawEllipse(QPointF(px, py), r * 2.2, r * 2.2)


def _signature(p: QPainter, t: float, width: float, height: float, inset: float, u: float, leave: float) -> None:
    """心动 over COUP DE CŒUR, set in the bottom-right corner like a fashion house's mark."""
    a = ease_out(win(t, 1.7, 2.5)) * (1 - ease_out(win(t, 4.1, 4.6)))
    if a <= 0:
        return
    track = 6 + 14 * (1 - ease_out(win(t, 1.7, 2.7)))
    right = width - inset - 18 * u
    base = height - inset - 26 * u
    rise = 8 * u * (1 - ease_out(win(t, 1.7, 2.5)))
    p.save()
    p.setOpacity(p.opacity() * a)
    han = QFont("Noto Serif SC")
    han.setPixelSize(round(40 * u))
    han.setWeight(QFont.Weight.DemiBold)
    han.setLetterSpacing(QFont.AbsoluteSpacing, track * u)
    latin = QFont("Bodoni MT")
    latin.setPixelSize(round(15 * u))
    latin.setLetterSpacing(QFont.AbsoluteSpacing, (4.2 + track * 0.4) * u)
    small = QFont(latin)
    rect_han = QRectF(right - 300 * u, base - 58 * u + rise, 300 * u, 52 * u)
    rect_lat = QRectF(right - 300 * u, base + 5 * u + rise, 300 * u, 22 * u)
    # A soft dark lift so the light letters read on the lobby.
    p.setFont(han)
    p.setPen(col("#2a0b18", 0.45))
    p.drawText(rect_han.translated(1.2 * u, 1.6 * u), Qt.AlignRight | Qt.AlignVCenter, "心动")
    p.setPen(QPen(gradient(rect_han.topLeft(), rect_han.bottomLeft(), ((0, "#ffffff"), (0.55, "#ffe1ea"), (1, "#f3b3c8"))), 1))
    p.drawText(rect_han, Qt.AlignRight | Qt.AlignVCenter, "心动")
    p.setFont(small)
    p.setPen(col("#2a0b18", 0.4))
    p.drawText(rect_lat.translated(1 * u, 1.2 * u), Qt.AlignRight | Qt.AlignVCenter, "COUP DE CŒUR")
    p.setPen(QPen(gradient(rect_lat.topLeft(), rect_lat.bottomLeft(), ((0, GOLD_LIGHT), (1, GOLD))), 1))
    p.drawText(rect_lat, Qt.AlignRight | Qt.AlignVCenter, "COUP DE CŒUR")
    # A hairline between them, with a pearl at its left end.
    line_w = 150 * u * ease_out(win(t, 1.9, 2.6))
    p.setPen(gold_pen(0.9 * u, 0.9, 60 * u))
    p.drawLine(QPointF(right - line_w, base + 1 * u + rise), QPointF(right, base + 1 * u + rise))
    p.setPen(Qt.NoPen)
    if line_w > 4 * u:
        pearl(p, right - line_w - 4 * u, base + 1 * u + rise, 3.2 * u)
    p.restore()
