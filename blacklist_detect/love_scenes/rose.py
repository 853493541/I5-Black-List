"""A garden rose seen from above, lit from one side: open outer petals, shadowed where they overlap,
a cup of curled petals in the middle and a tight dark heart."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient

from blacklist_detect.love_scenes.draw import clamp, col, ease_back

# (heart, body, edge) by variety.
VARIETIES = {
    "ivory": ("#c98b9c", "#f4dbe1", "#fffaf8"),
    "blush": ("#b8577a", "#efadc0", "#fde7ee"),
    "rose": ("#7e2148", "#cf6d91", "#f7c3d3"),
}
SHADE = "#3a0c1e"
LIGHT = math.radians(-128)  # from the upper left


def mix(a: str | QColor, b: str | QColor, k: float) -> QColor:
    ca, cb = QColor(a), QColor(b)
    k = clamp(k)
    return QColor(
        round(ca.red() + (cb.red() - ca.red()) * k),
        round(ca.green() + (cb.green() - ca.green()) * k),
        round(ca.blue() + (cb.blue() - ca.blue()) * k),
    )


def rose(p: QPainter, x: float, y: float, r: float, bloom: float, variety: str, turn: float) -> None:
    if r < 0.6:
        return
    heart, body, edge = VARIETIES[variety]
    p.save()
    p.translate(x, y)
    p.setPen(Qt.NoPen)
    # Shadow on whatever lies beneath.
    shadow = QRadialGradient(QPointF(r * 0.14, r * 0.2), r * 1.3)
    shadow.setColorAt(0, col(SHADE, 0.45 * min(1.0, bloom * 2)))
    shadow.setColorAt(1, col(SHADE, 0))
    p.setBrush(shadow)
    p.drawEllipse(QPointF(r * 0.14, r * 0.2), r * 1.3, r * 1.3)
    rings = (
        # count, length, out from the heart, wide, opens at, turn
        (6, 0.70, 0.44, 0.95, 0.42, 0),
        (5, 0.60, 0.30, 0.92, 0.28, 31),
        (5, 0.47, 0.17, 0.88, 0.14, 11),
    )
    for index, (count, length, spread, wide, opens, offset) in enumerate(rings):
        k = ease_back(clamp((bloom - opens) / 0.5), 1.3)
        if k <= 0:
            continue
        for i in range(count):
            jitter = math.sin(i * 12.9898 + index * 78.233 + turn * 0.37) * 43758.5453 % 1.0
            angle = turn + offset + i * 360 / count + (jitter - 0.5) * 18
            lit = 0.5 + 0.5 * math.cos(math.radians(angle - 90) - LIGHT)
            p.save()
            p.rotate(angle)
            p.translate(0, -r * spread * k * (0.9 + 0.2 * jitter))
            size = r * length * (0.55 + 0.45 * k) * (0.88 + 0.24 * jitter)
            w = size * wide * (1.05 + 0.2 * (1 - jitter))
            petal = QPainterPath(QPointF(-w * 0.2, size * 0.06))
            petal.cubicTo(QPointF(-w * 0.86, -size * 0.2), QPointF(-w * 0.74, -size * 0.98), QPointF(0, -size))
            petal.cubicTo(QPointF(w * 0.74, -size * 0.98), QPointF(w * 0.86, -size * 0.2), QPointF(w * 0.2, size * 0.06))
            petal.closeSubpath()
            fill = QLinearGradient(QPointF(0, size * 0.05), QPointF(0, -size))
            fill.setColorAt(0, mix(heart, SHADE, 0.35))
            fill.setColorAt(0.4, mix(body, heart, 0.45 * (1 - lit)))
            fill.setColorAt(0.85, mix(edge, "#ffffff", 0.35 * lit))
            fill.setColorAt(1, mix(edge, "#ffffff", 0.5 * lit))
            p.setBrush(fill)
            p.setPen(QPen(col(mix(heart, SHADE, 0.3), 0.32), max(0.5, r * 0.012)))
            p.drawPath(petal)
            # The rolled-back lip of the petal, catching light on the lit side.
            p.setPen(QPen(col("#ffffff", 0.18 + 0.55 * lit), max(0.6, r * 0.026)))
            p.setBrush(Qt.NoBrush)
            lip = QPainterPath(QPointF(-w * 0.52, -size * 0.8))
            lip.quadTo(QPointF(0, -size * 1.06), QPointF(w * 0.52, -size * 0.8))
            p.drawPath(lip)
            p.setPen(Qt.NoPen)
            p.restore()
        # The next ring in stands over this one and shades its base.
        reach = r * (rings[index + 1][2] + rings[index + 1][1] * 0.95) if index + 1 < len(rings) else r * 0.42
        occlude = QRadialGradient(QPointF(r * 0.05, r * 0.07), reach * 1.05)
        occlude.setColorAt(0, col(SHADE, 0.22 * k))
        occlude.setColorAt(0.75, col(SHADE, 0.2 * k))
        occlude.setColorAt(1, col(SHADE, 0))
        p.setBrush(occlude)
        p.drawEllipse(QPointF(r * 0.05, r * 0.07), reach * 1.05, reach * 1.05)
    # The cup: curled petals wrapped round each other, each a crescent lit on its outer rim.
    cup = ease_back(clamp(bloom / 0.45), 1.2)
    for k in range(6):
        start = turn + k * 83 + 20
        outer = r * (0.36 - 0.05 * k) * (0.7 + 0.3 * cup)
        if outer < 0.5:
            continue
        mid = math.radians(start + 105)
        shift = QPointF(math.cos(mid) * outer * 0.26, -math.sin(mid) * outer * 0.26)
        inner = outer * 0.8
        crescent = QPainterPath()
        box = QRectF(-outer, -outer, 2 * outer, 2 * outer)
        crescent.arcMoveTo(box, start)
        crescent.arcTo(box, start, 210)
        inner_box = QRectF(shift.x() - inner, shift.y() - inner, 2 * inner, 2 * inner)
        crescent.arcTo(inner_box, start + 210, -210)
        crescent.closeSubpath()
        lit = 0.5 + 0.5 * math.cos(-mid - LIGHT)
        fill = QRadialGradient(QPointF(-shift.x(), -shift.y()), outer * 1.25)
        fill.setColorAt(0.35, mix(heart, SHADE, 0.1))
        fill.setColorAt(0.75, mix(body, heart, 0.15))
        fill.setColorAt(1, mix(edge, "#ffffff", 0.5 * lit))
        p.setBrush(fill)
        p.setPen(QPen(col("#ffffff", 0.25 + 0.5 * lit), max(0.5, r * 0.02)))
        p.drawPath(crescent)
        p.setPen(Qt.NoPen)
    core = QRadialGradient(QPointF(0, 0), r * 0.07)
    core.setColorAt(0, col(mix(heart, SHADE, 0.35)))
    core.setColorAt(1, col(mix(heart, SHADE, 0.1), 0.0))
    p.setBrush(core)
    p.drawEllipse(QPointF(0, 0), r * 0.07, r * 0.07)
    p.restore()
