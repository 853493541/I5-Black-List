"""花雨 Rose Atelier: a florist's bouquet blooms in two corners and a gust of petals falls.

Roses of three colors (ivory, blush, deep rose) open in time-lapse in the bottom-left and top-right
corners among silver eucalyptus. A gust throws petals in from the top left, then petals keep falling
in three depths: soft and large in front, crisp in the middle, small and faint behind, with lens
bokeh. A blush light leak drifts across the top right. Petals dim where the names are.
"""

from __future__ import annotations

import io
import math
import random
from typing import TYPE_CHECKING

from PIL import Image, ImageFilter
from PySide6.QtCore import QBuffer, QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient

from blacklist_detect.love_scenes.draw import Wash, clamp, col, ease_back, ease_in, ease_out, gradient, win
from blacklist_detect.love_scenes.rose import rose

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.2
# Soft light throughout: drawn at one pixel per point and scaled up on a sharper screen, to keep 30 fps.
MAX_RATIO = 1.0
# (base, middle, tip) of a petal, by variety.
TONES = {
    "ivory": ("#e9bcc8", "#fbe7ec", "#fffbf9"),
    "blush": ("#d97b9c", "#f4bccc", "#fff0f4"),
    "rose": ("#a83a66", "#e07f9f", "#fbd2de"),
}
SAGE = ("#7f907d", "#a9b8a5", "#d5ddd0")


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    sprites = _sprites(u)
    petals = _petals(width, height, u)
    bokeh = _bokeh(width, height, u)
    names = QRectF(width * 0.13, height * 0.29, width * 0.81, height * 0.55)
    corners = (
        (QPointF(0, height), 1, -1, 0.0),
        (QPointF(width, 0), -1, 1, 0.25),
    )
    cache: dict[str, QPixmap] = {}

    glow = Wash(lambda q, w, h: _petals_wash(q, 9.0, w, h, u))

    def paint(p: QPainter, t: float) -> None:
        leave = ease_in(win(t, 4.2, 5.2))
        life = win(t, 0.0, 0.4) * (1 - leave)
        p.save()
        p.setOpacity(life)
        _leak(p, t, width, height, u)
        glow.paint(p, width, height, gap, ease_out(win(t, 0.0, 0.9)))
        _bokeh_paint(p, t, bokeh, u)
        _petal_paint(p, t, petals, sprites, names, ("far",), u, width, height)
        p.restore()
        # The bouquets: drawn live while they open, then from a picture of them.
        p.save()
        p.setOpacity(win(t, 0.0, 0.2) * (1 - ease_in(win(t, 4.0, 5.0))))
        settle = 1 - 0.04 * leave
        if t < 2.0:
            for origin, dx, dy, delay in corners:
                _bouquet(p, max(0.0, t - delay), origin, dx, dy, u, settle)
        else:
            if "still" not in cache:
                picture = QPixmap(int(width), int(height))
                picture.fill(Qt.transparent)
                inner = QPainter(picture)
                inner.setRenderHint(QPainter.Antialiasing)
                for origin, dx, dy, _delay in corners:
                    _bouquet(inner, 3.0, origin, dx, dy, u, 1.0)
                inner.end()
                cache["still"] = picture
            p.drawPixmap(0, 0, cache["still"])
        p.restore()
        p.save()
        p.setOpacity(life)
        _petal_paint(p, t, petals, sprites, names, ("mid", "near"), u, width, height)
        p.restore()

    return paint


# ---------------------------------------------------------------- light


def _leak(p: QPainter, t: float, width: float, height: float, u: float) -> None:
    """A blush light leak drifting across the top right."""
    a = ease_out(win(t, 0.0, 0.9))
    drift = ease_out(win(t, 0.0, 4.5))
    centre = QPointF(width * (1.02 - 0.12 * drift), height * (-0.08 + 0.06 * drift))
    leak = QRadialGradient(centre, 620 * u)
    leak.setColorAt(0, col("#fff1f5", 0.42 * a))
    leak.setColorAt(0.25, col("#ffc2d6", 0.30 * a))
    leak.setColorAt(0.6, col("#ff9fc0", 0.08 * a))
    leak.setColorAt(1, col("#ff9fc0", 0))
    p.fillRect(QRectF(0, 0, width, height), leak)


def _petals_wash(p: QPainter, t: float, width: float, height: float, u: float) -> None:
    """Warm light low on the left and a soft rose vignette round the edges."""
    a = ease_out(win(t, 0.0, 0.9))
    warm = QRadialGradient(QPointF(0, height), 520 * u)
    warm.setColorAt(0, col("#ffe6ee", 0.34 * a))
    warm.setColorAt(0.5, col("#ffb3cb", 0.10 * a))
    warm.setColorAt(1, col("#ffb3cb", 0))
    p.fillRect(QRectF(0, 0, width, height), warm)
    edge = 110 * u
    for start, end, rect in (
        (QPointF(0, 0), QPointF(edge, 0), QRectF(0, 0, edge, height)),
        (QPointF(width, 0), QPointF(width - edge, 0), QRectF(width - edge, 0, edge, height)),
        (QPointF(0, 0), QPointF(0, edge), QRectF(0, 0, width, edge)),
        (QPointF(0, height), QPointF(0, height - edge), QRectF(0, height - edge, width, edge)),
    ):
        p.fillRect(rect, gradient(start, end, ((0, "#e5789d", 0.24), (1, "#e5789d", 0)), a))


def _bokeh(width: float, height: float, u: float) -> list[tuple]:
    rnd = random.Random(5)
    out = []
    for _ in range(12):
        side = rnd.random() < 0.5
        x = rnd.uniform(0.0, 0.2) * width if side else rnd.uniform(0.78, 1.0) * width
        out.append((x, rnd.uniform(0.05, 1.0) * height, rnd.uniform(10, 34) * u, rnd.uniform(0.10, 0.22), rnd.uniform(6, 16) * u, rnd.random() < 0.3))
    return out


def _bokeh_paint(p: QPainter, t: float, bokeh: list[tuple], u: float) -> None:
    """Out-of-focus discs of light, rising slowly, brighter at their rims like a lens draws them."""
    a = ease_out(win(t, 0.3, 1.4))
    p.setPen(Qt.NoPen)
    for x, y, r, alpha, rise, white in bokeh:
        cy = y - rise * t
        tone = "#fff3f7" if white else "#ffb8cf"
        disc = QRadialGradient(QPointF(x, cy), r)
        disc.setColorAt(0, col(tone, alpha * a))
        disc.setColorAt(0.7, col(tone, alpha * 0.7 * a))
        disc.setColorAt(1, col(tone, 0))
        p.setBrush(disc)
        p.drawEllipse(QPointF(x, cy), r, r)


# ---------------------------------------------------------------- petals


def _petal_path(size: float) -> QPainterPath:
    """A rose petal, base at the bottom: broad, with a soft notch at its rolled tip."""
    w = size * 0.82
    path = QPainterPath(QPointF(0, 0))
    path.cubicTo(QPointF(-0.6 * w, -0.08 * size), QPointF(-0.66 * w, -0.78 * size), QPointF(-0.22 * w, -0.99 * size))
    path.quadTo(QPointF(0, -0.88 * size), QPointF(0.22 * w, -0.99 * size))
    path.cubicTo(QPointF(0.66 * w, -0.78 * size), QPointF(0.6 * w, -0.08 * size), QPointF(0, 0))
    path.closeSubpath()
    return path


def _sprites(u: float) -> dict[tuple[str, bool], QImage]:
    """Each petal color drawn once, crisp, and once softly blurred for the near layer."""
    out = {}
    side = 96
    for tone, (base, middle, tip) in TONES.items():
        image = QImage(side, side, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        q = QPainter(image)
        q.setRenderHint(QPainter.Antialiasing)
        q.translate(side / 2, side * 0.9)
        size = side * 0.8
        q.setBrush(gradient(QPointF(0, 0), QPointF(0, -size), ((0, base), (0.4, middle), (1, tip))))
        q.setPen(QPen(col("#fff7f9", 0.25), 1.0))
        q.drawPath(_petal_path(size))
        # A faint crease up the middle and the lighter, rolled-back rim at the tip.
        q.setPen(QPen(col("#ffffff", 0.28), 1.6))
        crease = QPainterPath(QPointF(0, -size * 0.05))
        crease.quadTo(QPointF(size * 0.04, -size * 0.45), QPointF(0, -size * 0.8))
        q.drawPath(crease)
        q.setPen(QPen(col("#ffffff", 0.5), 2.2))
        rim = QPainterPath(QPointF(-size * 0.3, -size * 0.86))
        rim.quadTo(QPointF(0, -size * 0.76), QPointF(size * 0.3, -size * 0.86))
        q.drawPath(rim)
        q.end()
        out[(tone, False)] = image
        out[(tone, True)] = _blur(image, 4.5)
    del u
    return out


def _blur(image: QImage, radius: float) -> QImage:
    buffer = QBuffer()
    buffer.open(QBuffer.ReadWrite)
    image.save(buffer, "PNG")
    picture = Image.open(io.BytesIO(bytes(buffer.data()))).convert("RGBA")
    pad = int(radius * 3)
    grown = Image.new("RGBA", (picture.width + 2 * pad, picture.height + 2 * pad), (0, 0, 0, 0))
    grown.paste(picture, (pad, pad))
    soft = grown.filter(ImageFilter.GaussianBlur(radius)).crop((pad, pad, pad + picture.width, pad + picture.height))
    out = io.BytesIO()
    soft.save(out, "PNG")
    result = QImage()
    result.loadFromData(out.getvalue(), "PNG")
    return result.convertToFormat(QImage.Format_ARGB32_Premultiplied)


def _petals(width: float, height: float, u: float) -> list[dict]:
    rnd = random.Random(21)
    out = []

    def tone() -> str:
        roll = rnd.random()
        return "blush" if roll < 0.5 else "ivory" if roll < 0.82 else "rose"

    # The gust: thrown in from the top left, fast at first.
    for _ in range(44):
        layer = rnd.choices(("far", "mid", "near"), (0.35, 0.5, 0.15))[0]
        out.append(
            dict(
                born=rnd.uniform(0.3, 1.0),
                x=rnd.uniform(-0.12, 0.12) * width,
                y=rnd.uniform(-0.12, 0.25) * height,
                vx=rnd.uniform(70, 130) * u,
                vy=rnd.uniform(40, 90) * u,
                gx=rnd.uniform(900, 1500) * u,
                gy=rnd.uniform(80, 380) * u,
                layer=layer,
                tone=tone(),
                **_spin(rnd, layer, u),
            )
        )
    # Then a steady fall from the top, drifting right.
    for _ in range(70):
        layer = rnd.choices(("far", "mid", "near"), (0.48, 0.42, 0.10))[0]
        x = rnd.uniform(-0.15, 0.95)
        if layer == "near":
            x = rnd.choice((rnd.uniform(-0.1, 0.12), rnd.uniform(0.8, 1.0)))
        out.append(
            dict(
                born=rnd.uniform(0.8, 3.9),
                x=x * width,
                y=rnd.uniform(-0.12, -0.04) * height,
                vx=rnd.uniform(25, 75) * u,
                vy=rnd.uniform(70, 130) * u * {"far": 0.6, "mid": 1.0, "near": 1.9}[layer],
                gx=0.0,
                gy=0.0,
                layer=layer,
                tone=tone(),
                **_spin(rnd, layer, u),
            )
        )
    return out


def _spin(rnd: random.Random, layer: str, u: float) -> dict:
    size = {"far": rnd.uniform(8, 13), "mid": rnd.uniform(15, 25), "near": rnd.uniform(48, 78)}[layer] * u
    return dict(
        size=size,
        turn=rnd.uniform(0, 360),
        spin=rnd.uniform(-120, 120),
        flip=rnd.uniform(1.4, 3.2),
        phase=rnd.uniform(0, 6.28),
        sway=rnd.uniform(14, 34) * u,
        sway_rate=rnd.uniform(1.2, 2.4),
    )


def _petal_paint(p, t, petals, sprites, names, layers, u, width, height) -> None:  # noqa: ANN001
    base_alpha = {"far": 0.55, "mid": 0.95, "near": 0.62}
    for petal in petals:
        if petal["layer"] not in layers:
            continue
        age = t - petal["born"]
        if age <= 0:
            continue
        gust = (1 - math.exp(-2.6 * age)) / 2.6
        x = petal["x"] + petal["vx"] * age + petal["gx"] * gust + petal["sway"] * math.sin(age * petal["sway_rate"] + petal["phase"])
        y = petal["y"] + petal["vy"] * age + petal["gy"] * gust + 0.4 * petal["sway"] * math.cos(age * petal["sway_rate"] * 1.3 + petal["phase"])
        size = petal["size"]
        if x < -size * 2 or x > width + size * 2 or y > height + size * 2:
            continue
        alpha = base_alpha[petal["layer"]] * min(1.0, age / 0.35)
        if petal["layer"] != "far" and names.contains(QPointF(x, y)):
            # Over the names a petal is only a shadow of itself, so every name still reads.
            edge = min(x - names.left(), names.right() - x, y - names.top(), names.bottom() - y)
            alpha *= 0.35 + 0.65 * (1 - clamp(edge / (60 * u)))
        flip = math.cos(age * petal["flip"] + petal["phase"])
        p.save()
        p.translate(x, y)
        p.rotate(petal["turn"] + petal["spin"] * age)
        p.scale(1.0, 0.22 + 0.78 * abs(flip))
        p.setOpacity(p.opacity() * alpha * (0.75 + 0.25 * abs(flip)))
        image = sprites[(petal["tone"], petal["layer"] == "near")]
        p.drawImage(QRectF(-size / 2, -size * 0.75, size, size), image)
        p.restore()


# ---------------------------------------------------------------- bouquets

# Each corner's bouquet, in units from its corner: (along, out, radius, variety, opens at).
ROSES = (
    (84, 62, 56, "ivory", 0.30),
    (190, 40, 42, "blush", 0.48),
    (42, 168, 42, "blush", 0.58),
    (150, 134, 31, "rose", 0.70),
    (262, 26, 27, "ivory", 0.84),
)
BUDS = ((302, 62, 13, "rose", 0.9), (18, 262, 12, "blush", 0.95), (232, 104, 11, "ivory", 1.0))
# Eucalyptus: (angle from the long edge, length, leaves, starts at).
SPRIGS = ((12, 380, 9, 0.1), (34, 300, 7, 0.18), (62, 280, 7, 0.14), (82, 300, 8, 0.24))


def _bouquet(p: QPainter, t: float, origin: QPointF, dx: int, dy: int, u: float, settle: float) -> None:
    p.save()
    p.translate(origin)
    p.scale(settle, settle)
    # Local axes: x along the bottom/top edge into the screen, y up/down into the screen.
    p.scale(dx, dy)
    for angle, length, leaves, start in SPRIGS:
        _sprig(p, t - start, angle, length * u, leaves, u)
    for along, out, r, variety, start in BUDS:
        k = ease_back(win(t, start, start + 0.5))
        if k > 0:
            rose(p, along * u, out * u, r * u * k, 0.15, variety, 20 + along)
    for along, out, r, variety, start in ROSES:
        k = win(t, start, start + 1.1)
        if k > 0:
            rose(p, along * u, out * u, r * u, k, variety, along * 1.7 + 12 * t)
    p.restore()


def _sprig(p: QPainter, t: float, angle: float, length: float, leaves: int, u: float) -> None:
    """Silver-dollar eucalyptus: a fine stem growing out, round leaves opening along it."""
    grow = ease_out(win(t, 0.0, 0.9))
    if grow <= 0:
        return
    a = math.radians(angle)
    bend = 0.18
    end = QPointF(math.cos(a) * length * grow, math.sin(a) * length * grow)
    ctrl = QPointF(end.x() * 0.5 - end.y() * bend, end.y() * 0.5 + end.x() * bend)
    stem = QPainterPath(QPointF(0, 0))
    stem.quadTo(ctrl, end)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(col(SAGE[0], 0.9), 1.6 * u))
    p.drawPath(stem)
    p.setPen(Qt.NoPen)
    for i in range(leaves):
        s = (i + 1) / (leaves + 1)
        if s > grow:
            break
        open_ = ease_back(clamp((grow - s) / 0.25))
        m = 1 - s
        x = 2 * m * s * ctrl.x() + s * s * end.x()
        y = 2 * m * s * ctrl.y() + s * s * end.y()
        r = (15 - 7 * s) * u * open_
        side = 1 if i % 2 else -1
        nx, ny = -math.sin(a) * side, math.cos(a) * side
        cx, cy = x + nx * r * 0.9, y + ny * r * 0.9
        leaf = QRadialGradient(QPointF(cx - r * 0.3, cy - r * 0.3), r * 1.3)
        leaf.setColorAt(0, col(SAGE[2], 0.95))
        leaf.setColorAt(0.6, col(SAGE[1], 0.9))
        leaf.setColorAt(1, col(SAGE[0], 0.9))
        p.setBrush(leaf)
        p.drawEllipse(QPointF(cx, cy), r, r * 0.92)
        p.setPen(QPen(col("#eef2ea", 0.35), 0.8 * u))
        p.drawLine(QPointF(x, y), QPointF(cx + nx * r * 0.5, cy + ny * r * 0.5))
        p.setPen(Qt.NoPen)


def _rose(p: QPainter, x: float, y: float, r: float, bloom: float, variety: str, turn: float) -> None:
    """A garden rose seen from above: a tight spiral heart, cupped petals opening ring by ring."""
    if r < 0.6:
        return
    base, middle, tip = TONES[variety]
    p.save()
    p.translate(x, y)
    p.rotate(turn)
    shadow = QRadialGradient(QPointF(r * 0.12, r * 0.18), r * 1.35)
    shadow.setColorAt(0, col("#2b0a18", 0.38 * min(1.0, bloom * 2)))
    shadow.setColorAt(1, col("#2b0a18", 0))
    p.setPen(Qt.NoPen)
    p.setBrush(shadow)
    p.drawEllipse(QPointF(r * 0.12, r * 0.18), r * 1.35, r * 1.35)
    rings = (
        # count, length, spread out from the heart, opens at, turn
        (6, 0.72, 0.42, 0.45, 0),
        (5, 0.62, 0.28, 0.3, 30),
        (5, 0.50, 0.16, 0.16, 12),
        (4, 0.38, 0.07, 0.04, 50),
    )
    for count, length, spread, opens, offset in rings:
        k = ease_back(clamp((bloom - opens) / 0.5), 1.4)
        if k <= 0:
            continue
        for i in range(count):
            p.save()
            p.rotate(offset + i * 360 / count)
            p.translate(0, -r * spread * k)
            size = r * length * (0.55 + 0.45 * k)
            petal = QPainterPath(QPointF(-size * 0.18, 0))
            petal.cubicTo(QPointF(-size * 0.78, -size * 0.18), QPointF(-size * 0.7, -size * 0.98), QPointF(0, -size))
            petal.cubicTo(QPointF(size * 0.7, -size * 0.98), QPointF(size * 0.78, -size * 0.18), QPointF(size * 0.18, 0))
            petal.closeSubpath()
            shade = QRadialGradient(QPointF(0, size * 0.1), size * 1.05)
            shade.setColorAt(0, col(base))
            shade.setColorAt(0.55, col(middle))
            shade.setColorAt(1, col(tip))
            p.setBrush(shade)
            p.setPen(QPen(col("#fff8fa", 0.6), max(0.6, r * 0.022)))
            p.drawPath(petal)
            # The rolled-back edge catches the light.
            p.setPen(QPen(col("#ffffff", 0.55), max(0.7, r * 0.03)))
            rim = QPainterPath(QPointF(-size * 0.5, -size * 0.78))
            rim.quadTo(QPointF(0, -size * 1.06), QPointF(size * 0.5, -size * 0.78))
            p.drawPath(rim)
            p.restore()
    # The tight heart: a swirl of the deepest shade.
    heart = r * 0.2
    p.setBrush(QRadialGradient(QPointF(0, 0), heart * 1.2))
    swirl = QRadialGradient(QPointF(0, 0), heart * 1.3)
    swirl.setColorAt(0, col(base))
    swirl.setColorAt(1, col(middle))
    p.setBrush(swirl)
    p.setPen(QPen(col(tip, 0.8), max(0.6, r * 0.02)))
    p.drawEllipse(QPointF(0, 0), heart, heart)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(col(base, 0.9), max(0.7, r * 0.03)))
    spiral = QPainterPath(QPointF(heart * 0.7, 0))
    for step in range(1, 40):
        angle = step * 0.32
        radius = heart * 0.7 * (1 - step / 44)
        spiral.lineTo(QPointF(math.cos(angle) * radius, math.sin(angle) * radius))
    p.drawPath(spiral)
    p.restore()

