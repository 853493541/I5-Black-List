"""冰蓝极光 Ice Aurora: deep sapphire night, an aurora that shifts through the blues.

The edges deepen to sapphire. Aurora curtains ripple across the top, their colors flowing from
cobalt through ice cyan, aqua, periwinkle and violet, arching up over the title instead of
across it. A faceted crystal heart assembles from flying shards in the top left and a prism of
light sweeps across its facets. Frost grows from the two bottom corners in fine lit lines, and
prismatic diamond dust drifts down the sides. At the end the heart breaks into shards and the
aurora rises away.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient

from blacklist_detect.love_scenes.draw import (
    Wash,
    clamp,
    col,
    ease_in,
    ease_out,
    gradient,
    heart_points,
    mix,
    soft_dot,
    spectrum,
    star,
    win,
)

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
# Soft light throughout: drawn at one pixel per point and scaled up on a sharper screen, to keep 30 fps.
MAX_RATIO = 1.0
# The aurora's colors, leaning on the deep blues.
AURORA = ("#1f4fe0", "#2f7bff", "#46c6ff", "#7ff2e6", "#4fa6ff", "#6f86ff", "#9a7bff", "#c08bff", "#6f86ff", "#2f62f0")
SAPPHIRE = "#0b2a8a"
ICE = "#d6f1ff"


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(14)
    heart_at = QPointF(width * 0.118, height * 0.175)
    facets = _facets(heart_at, 150 * u, rnd)
    frost = _frost(width, height, u, rnd)
    # The grown frost, drawn once and laid on from then on: {(device size, transform): image}.
    frost_drawn: dict[tuple, QImage] = {}
    dust = [
        (
            rnd.uniform(0.3, 3.4),
            (rnd.uniform(0.0, 0.13) if rnd.random() < 0.5 else rnd.uniform(0.87, 1.0)) * width,
            rnd.uniform(-0.05, 0.75) * height,
            rnd.uniform(18, 46) * u,
            rnd.uniform(1.6, 4.6) * u,
            rnd.random(),
            rnd.uniform(0, 6.28),
        )
        for _ in range(46)
    ]

    night = Wash(lambda q, w, h: _ice_wash(q, 9.0, w, h, u, 0.0))

    def paint(p: QPainter, t: float) -> None:
        life = win(t, 0.0, 0.35)
        leave = ease_in(win(t, 4.1, 5.0))
        p.save()
        p.setOpacity(life)
        night.paint(p, width, height, gap, ease_out(win(t, 0.0, 0.8)) * (1 - leave))
        _soft_aurora(p, t, width, height, u, leave)
        _frost_paint(p, t, frost, u, leave, frost_drawn)
        _dust(p, t, dust, u, 1 - leave)
        _heart(p, t, heart_at, facets, u)
        p.restore()

    return paint


def _ice_wash(p: QPainter, t: float, width: float, height: float, u: float, leave: float) -> None:
    a = ease_out(win(t, 0.0, 0.8)) * (1 - leave)
    if a <= 0:
        return
    top = 230 * u
    p.fillRect(QRectF(0, 0, width, top), gradient(QPointF(0, 0), QPointF(0, top), ((0, "#06164f", 0.62), (0.55, SAPPHIRE, 0.22), (1, SAPPHIRE, 0)), a))
    edge = 150 * u
    for start, end, rect in (
        (QPointF(0, 0), QPointF(edge, 0), QRectF(0, 0, edge, height)),
        (QPointF(width, 0), QPointF(width - edge, 0), QRectF(width - edge, 0, edge, height)),
        (QPointF(0, height), QPointF(0, height - edge), QRectF(0, height - edge, width, edge)),
    ):
        p.fillRect(rect, gradient(start, end, ((0, SAPPHIRE, 0.42), (1, SAPPHIRE, 0)), a))


def _soft_aurora(p: QPainter, t: float, width: float, height: float, u: float, leave: float) -> None:
    """The aurora drawn at half size and laid on scaled up: it is all soft light, so it looks the
    same, and it is the costly part of the scene."""
    band = min(height, 260 * u)
    image = QImage(max(1, round(width / 2)), max(1, round(band / 2)), QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    inner = QPainter(image)
    inner.setRenderHint(QPainter.Antialiasing)
    inner.scale(0.5, 0.5)
    _aurora(inner, t, width, height, u, leave)
    inner.end()
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(QRectF(0, 0, width, band), image)
    p.restore()


def _aurora(p: QPainter, t: float, width: float, height: float, u: float, leave: float) -> None:
    """Curtains of light made of thin vertical rays, bright at their lower hem, fading upward."""
    grow = ease_out(win(t, 0.15, 1.3))
    if grow <= 0:
        return
    rise = 70 * u * leave
    fade = 1 - leave
    curtains = (
        # hem height, ray height, ripple, speed, phase, brightness, color offset
        (62, 130, 16, 0.9, 0.0, 0.78, 0.0),
        (92, 100, 11, -0.7, 2.2, 0.6, 0.33),
        (44, 160, 20, 0.5, 4.1, 0.55, 0.66),
    )
    rays = 96
    step = width / rays
    title = width * 0.535
    p.setPen(Qt.NoPen)
    for hem, tall, ripple, speed, phase, bright, offset in curtains:
        hems = []
        for i in range(rays + 1):
            x = i * step
            k = x / width
            # The curtains arch up and part over the title.
            lift = 46 * u * math.exp(-(((x - title) / (width * 0.11)) ** 2))
            y = hem * u - lift + ripple * u * (math.sin(k * 7.3 + t * speed + phase) + 0.45 * math.sin(k * 17.1 - t * speed * 1.7 + phase * 2))
            hems.append(y * (0.35 + 0.65 * grow) - rise)
        # The curtain at an even strength on a layer of its own, as strips that follow the hem on
        # both sides with no antialiased edge (they meet without a seam or a step); then its folds
        # and finer rays cut in with one horizontal mask, so they vary smoothly, never strip by strip.
        tops = [hems[i] - tall * u * (0.88 + 0.12 * math.sin((i * step / width) * 5 + t + phase)) for i in range(rays + 1)]
        a = bright * 1.25 * grow * fade
        if a >= 0.02:
            device = p.device()
            layer = QImage(device.width(), device.height(), QImage.Format_ARGB32_Premultiplied)
            layer.fill(Qt.transparent)
            lp = QPainter(layer)
            lp.setTransform(p.transform())
            lp.setPen(Qt.NoPen)
            for i in range(rays):
                x = i * step
                k = (x + step / 2) / width
                color = spectrum(AURORA, k * 1.3 + t * 0.16 + offset)
                hem_y = (hems[i] + hems[i + 1]) / 2
                top = (tops[i] + tops[i + 1]) / 2
                ray = QLinearGradient(QPointF(0, top), QPointF(0, hem_y + 9 * u))
                ray.setColorAt(0, mix(color, color, 0, 0))
                ray.setColorAt(0.62, mix(color, color, 0, a * 0.38))
                ray.setColorAt(0.9, mix(color, "#ffffff", 0.2, a * 0.92))
                ray.setColorAt(1, mix(color, color, 0, 0))
                lp.setBrush(ray)
                lp.drawPolygon(QPolygonF([
                    QPointF(x, tops[i]), QPointF(x + step, tops[i + 1]),
                    QPointF(x + step, hems[i + 1] + 9 * u), QPointF(x, hems[i] + 9 * u),
                ]))
            mask = QLinearGradient(QPointF(0, 0), QPointF(width, 0))
            for s_ in range(161):
                k = s_ / 160
                folds = 0.5 + 0.5 * math.sin(k * 29 + t * 1.3 + phase)
                streaks = 0.5 + 0.5 * math.sin(k * 83 - t * 1.7 + phase * 3)
                strength = (0.25 + 0.75 * folds) * (0.45 + 0.55 * streaks ** 2) * (0.7 + 0.3 * math.sin(k * 11 - t * 0.8))
                mask.setColorAt(k, col("#000000", clamp(strength)))
            lp.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            lp.fillRect(QRectF(0, 0, width, height), mask)
            lp.end()
            p.save()
            p.resetTransform()
            p.drawImage(0, 0, layer)
            p.restore()
        band = QPainterPath(QPointF(0, hems[0] - 40 * u))
        for i in range(0, rays + 1, 4):
            band.lineTo(QPointF(i * step, hems[i] - 40 * u))
        for i in range(rays, -1, -4):
            band.lineTo(QPointF(i * step, hems[i] + 26 * u))
        band.closeSubpath()
        haze = QLinearGradient(QPointF(0, 0), QPointF(width, 0))
        for s_ in range(9):
            k = s_ / 8
            haze.setColorAt(k, mix(spectrum(AURORA, k * 1.3 + t * 0.16 + offset), "#ffffff", 0.1, 0.16 * bright * grow * fade))
        p.setBrush(haze)
        p.drawPath(band)
        # A soft glow along the hem where the curtain ends, not a drawn line.
        hem_line = QPainterPath(QPointF(0, hems[0]))
        for i in range(1, rays + 1):
            hem_line.lineTo(QPointF(i * step, hems[i]))
        shade = QLinearGradient(QPointF(0, 0), QPointF(width, 0))
        for s in range(9):
            k = s / 8
            shade.setColorAt(k, mix(spectrum(AURORA, k * 1.3 + t * 0.16 + offset), "#ffffff", 0.35, 0.22 * bright * grow * fade))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(shade, 5 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(hem_line)
        p.setPen(Qt.NoPen)


def _facets(centre: QPointF, size: float, rnd: random.Random) -> list[dict]:
    """A low-poly heart: an outer ring, an inner ring and a centre, cut into triangles."""
    outer = heart_points(centre.x(), centre.y(), size, 18)
    inner = heart_points(centre.x(), centre.y() + size * 0.03, size * 0.52, 18, 0.5 / 18)
    middle = QPointF(centre.x() - size * 0.04, centre.y() - size * 0.02)
    tris = []
    n = len(outer)
    for i in range(n):
        j = (i + 1) % n
        tris.append((outer[i], outer[j], inner[i]))
        tris.append((outer[j], inner[j], inner[i]))
        tris.append((inner[i], inner[j], middle))
    out = []
    for k, (a, b, c) in enumerate(tris):
        cx, cy = (a.x() + b.x() + c.x()) / 3, (a.y() + b.y() + c.y()) / 3
        angle = rnd.uniform(0, 2 * math.pi)
        far = rnd.uniform(140, 300) * size / 128
        out.append(
            dict(
                pts=(a, b, c),
                centre=QPointF(cx, cy),
                shade=clamp(0.5 + 0.5 * math.cos(math.atan2(cy - centre.y(), cx - centre.x()) + 2.3) + rnd.uniform(-0.25, 0.25)),
                start=0.7 + 0.55 * rnd.random() * (0.4 + 0.6 * (k % 3 != 2)),
                fly=QPointF(math.cos(angle) * far, math.sin(angle) * far),
                spin=rnd.uniform(-160, 160),
                leave_angle=angle,
            )
        )
    return out


def _heart(p: QPainter, t: float, centre: QPointF, facets: list[dict], u: float) -> None:
    """The crystal heart: shards fly in and lock together, a prism of light sweeps it, it beats once."""
    breaking = ease_in(win(t, 4.05, 4.75))
    beat = 1 + 0.06 * max(0.0, math.sin(math.pi * win(t, 2.25, 2.45))) + 0.04 * max(0.0, math.sin(math.pi * win(t, 2.5, 2.68)))
    float_y = 3 * u * math.sin(t * 1.7)
    assembled = win(t, 1.4, 1.7)
    glow = QRadialGradient(QPointF(centre.x(), centre.y() + 6 * u + float_y), 150 * u * beat)
    glow.setColorAt(0, col("#7fd0ff", 0.42 * assembled * (1 - breaking)))
    glow.setColorAt(0.45, col("#2f7bff", 0.18 * assembled * (1 - breaking)))
    glow.setColorAt(1, col("#2f7bff", 0))
    p.setPen(Qt.NoPen)
    p.setBrush(glow)
    p.drawEllipse(QPointF(centre.x(), centre.y() + 6 * u + float_y), 150 * u * beat, 150 * u * beat)
    sweep = win(t, 1.75, 2.55)
    sweep2 = win(t, 3.1, 3.7)
    for f in facets:
        k = ease_out(win(t, f["start"], f["start"] + 0.55))
        if k <= 0:
            continue
        a, b, c = f["pts"]
        fc = f["centre"]
        # Fly in from afar, turning; at the end fly out again.
        dx = f["fly"].x() * (1 - k) + math.cos(f["leave_angle"]) * 220 * u * breaking
        dy = f["fly"].y() * (1 - k) + math.sin(f["leave_angle"]) * 220 * u * breaking + float_y
        turn = math.radians(f["spin"] * ((1 - k) + breaking))
        scale = beat * (0.6 + 0.4 * k) * (1 - 0.5 * breaking)
        poly = QPolygonF()
        for v in (a, b, c):
            vx, vy = (v.x() - fc.x()) * scale, (v.y() - fc.y()) * scale
            rx = vx * math.cos(turn) - vy * math.sin(turn)
            ry = vx * math.sin(turn) + vy * math.cos(turn)
            hx = (fc.x() - centre.x()) * beat + centre.x()
            hy = (fc.y() - centre.y()) * beat + centre.y()
            poly.append(QPointF(hx + rx + dx, hy + ry + dy))
        # Deep sapphire to ice, by which way the facet faces; the prism adds a band of spectrum and white.
        base = mix("#0f3aa8", "#bfe9ff", f["shade"])
        proj = (fc.x() - centre.x() + fc.y() - centre.y()) / (180 * u) + 0.5
        band = math.exp(-(((proj - (-0.3 + 1.6 * sweep)) / 0.13) ** 2)) * (0 < sweep < 1)
        band += 0.6 * math.exp(-(((proj - (-0.3 + 1.6 * sweep2)) / 0.13) ** 2)) * (0 < sweep2 < 1)
        hue = spectrum(("#7ff2e6", "#9a7bff", "#ff9ad5", "#46c6ff"), proj * 1.5 + t * 0.2)
        fill = mix(mix(base, hue, 0.55 * band), "#ffffff", 0.45 * band)
        alpha = (0.35 + 0.6 * k) * (1 - breaking)
        fill.setAlphaF(clamp(alpha * 0.92))
        p.setBrush(fill)
        p.setPen(QPen(col("#eaf8ff", 0.5 * alpha), 0.9 * u))
        p.drawPolygon(poly)
    p.setPen(Qt.NoPen)
    if 0 < sweep < 1:
        tip = QPointF(centre.x() - 40 * u + 90 * u * sweep, centre.y() - 34 * u + 60 * u * sweep + float_y)
        star(p, tip.x(), tip.y(), 22 * u * math.sin(math.pi * sweep), "#ffffff", 0.95)
    if breaking <= 0 and t > 2.3:
        twinkle = max(0.0, math.sin(math.pi * win(t, 3.4, 3.8)))
        star(p, centre.x() + 34 * u, centre.y() - 30 * u + float_y, 16 * u * twinkle, "#ffffff", twinkle)


def _frost(width: float, height: float, u: float, rnd: random.Random) -> list[tuple]:
    """Branching ice from the two bottom corners: (start, end, born, depth)."""
    segments = []

    def grow(x, y, angle, length, depth, born, side) -> None:  # noqa: ANN001
        if depth > 2 or length < 8 * u:
            return
        ex, ey = x + math.cos(angle) * length, y + math.sin(angle) * length
        speed = 360 * u
        segments.append((QPointF(x, y), QPointF(ex, ey), born, depth))
        end = born + length / speed
        steps = 3 if depth == 0 else 2
        for s in range(1, steps + 1):
            k = s / (steps + 1) + rnd.uniform(-0.06, 0.06)
            bx, by = x + math.cos(angle) * length * k, y + math.sin(angle) * length * k
            at = born + length * k / speed
            for turn in (math.radians(60), math.radians(-60)):
                if rnd.random() < 0.8:
                    grow(bx, by, angle + turn, length * rnd.uniform(0.24, 0.34), depth + 1, at, side)
        if depth < 1:
            grow(ex, ey, angle + rnd.uniform(-0.2, 0.2), length * 0.45, depth + 1, end, side)

    for side, x in ((1, 0.0), (-1, width)):
        for angle, length in ((-74, 175), (-42, 135), (-10, 200)):
            a = math.radians(angle) if side > 0 else math.pi - math.radians(angle)
            grow(x, height + 2 * u, a, length * u, 0, 0.35 + rnd.uniform(0, 0.25), side)
    return segments


def _frost_lines(p: QPainter, core: QPainterPath, u: float, fade: float) -> None:
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(col("#5fb8ff", 0.25 * fade), 5 * u, Qt.SolidLine, Qt.RoundCap))
    p.drawPath(core)
    p.setPen(QPen(col("#cdeeff", 0.85 * fade), 1.3 * u, Qt.SolidLine, Qt.RoundCap))
    p.drawPath(core)
    p.setPen(Qt.NoPen)


def _frost_paint(p: QPainter, t: float, segments: list[tuple], u: float, leave: float, drawn: dict) -> None:
    fade = 1 - leave
    if fade <= 0:
        return
    speed = 360 * u
    core = QPainterPath()
    tips = []
    grown = True
    for a, b, born, depth in segments:
        length = math.dist((a.x(), a.y()), (b.x(), b.y()))
        k = clamp((t - born) * speed / max(length, 1e-3))
        grown = grown and k >= 1
        if k <= 0:
            continue
        end = QPointF(a.x() + (b.x() - a.x()) * k, a.y() + (b.y() - a.y()) * k)
        core.moveTo(a)
        core.lineTo(end)
        if k >= 1 and depth >= 1:
            tips.append((b, depth))
    device = p.device()
    if not grown or device is None:
        _frost_lines(p, core, u, fade)
    else:
        # Grown: the wide glowing strokes are the costly part and no longer change, only fade.
        transform = p.transform()
        key = (device.width(), device.height(), transform.m11(), transform.m22(), transform.dx(), transform.dy())
        if key not in drawn:
            image = QImage(device.width(), device.height(), QImage.Format_ARGB32_Premultiplied)
            image.fill(Qt.transparent)
            inner = QPainter(image)
            inner.setRenderHint(QPainter.Antialiasing)
            inner.setTransform(transform)
            _frost_lines(inner, core, u, 1.0)
            inner.end()
            drawn.clear()
            drawn[key] = image
        p.save()
        p.resetTransform()
        p.setOpacity(p.opacity() * fade)
        p.drawImage(0, 0, drawn[key])
        p.restore()
    for index, (point, depth) in enumerate(tips):
        r = (3.6 - 0.6 * depth) * u
        diamond = QPolygonF([QPointF(point.x(), point.y() - r), QPointF(point.x() + r * 0.6, point.y()), QPointF(point.x(), point.y() + r), QPointF(point.x() - r * 0.6, point.y())])
        p.setBrush(col("#ffffff", 0.8 * fade))
        p.drawPolygon(diamond)
        if index % 5 == 0:
            twinkle = 0.5 + 0.5 * math.sin(t * 3.1 + index)
            size = (7 + 4 * twinkle) * u
            p.setPen(QPen(col("#e9f8ff", 0.85 * fade * (0.5 + 0.5 * twinkle)), 1.0 * u, Qt.SolidLine, Qt.RoundCap))
            for arm in range(6):
                a = math.radians(arm * 60 + 15)
                tip = QPointF(point.x() + math.cos(a) * size, point.y() + math.sin(a) * size)
                p.drawLine(point, tip)
                for side in (-1, 1):
                    b = a + side * math.radians(45)
                    mid = QPointF(point.x() + math.cos(a) * size * 0.6, point.y() + math.sin(a) * size * 0.6)
                    p.drawLine(mid, QPointF(mid.x() + math.cos(b) * size * 0.3, mid.y() + math.sin(b) * size * 0.3))
            p.setPen(Qt.NoPen)


def _dust(p: QPainter, t: float, dust: list[tuple], u: float, a: float) -> None:
    """Diamond dust: tiny prisms drifting down, each flashing a color of the spectrum as it turns."""
    for born, x, y, fall, r, hue, phase in dust:
        age = t - born
        if age <= 0 or age > 3.2:
            continue
        fade = min(1.0, age / 0.4) * min(1.0, (3.2 - age) / 0.8) * a
        flash = max(0.0, math.sin(age * 4.2 + phase)) ** 3
        px, py = x + 12 * u * math.sin(age * 1.2 + phase), y + fall * age
        color = spectrum(("#9fe8ff", "#7ff2e6", "#a99bff", "#ffb4e6", "#6fb2ff"), hue + age * 0.3)
        soft_dot(p, px, py, r * 2.6, color, 0.55 * fade)
        star(p, px, py, r * (1.2 + 2.2 * flash), mix(color, "#ffffff", 0.6), fade * (0.4 + 0.6 * flash))
