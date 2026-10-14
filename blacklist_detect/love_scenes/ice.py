"""冰蓝极光 Ice Aurora: deep sapphire night, an aurora that shifts through the blues.

The edges deepen to sapphire. Aurora curtains ripple across the top, their colors flowing from
cobalt through ice cyan, aqua, periwinkle and violet, arching up over the title instead of
across it. In the top left glints gather into a heart of clear ice-blue glass (a height field
shaded like glass: clear face on, the sky in its bevel, soft lights on its lobes) with aurora light
drifting inside it and an edge of icy starlight, and a prism of light sweeps across it. Frost grows from the two bottom corners in fine lit lines, and
prismatic diamond dust drifts down the sides. At the end the heart melts into light and the
aurora rises away.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient

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
# The aurora inside the heart: its cyans and violets.
WITHIN = ("#46c6ff", "#7ff2e6", "#9a7bff", "#4fa6ff", "#c08bff", "#46c6ff")


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(14)
    heart_at = QPointF(width * 0.118, height * 0.175)
    sparks = _sparks(heart_at, 150 * u, random.Random(15))
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
    # The glass heart, drawn once for each size in pixels it is shown at.
    glass: dict[int, QImage] = {}

    def heart(p: QPainter, t: float) -> None:
        p.save()
        p.setOpacity(p.opacity() * win(t, 0.0, 0.35))
        _heart(p, t, heart_at, sparks, u, glass)
        p.restore()

    def paint(p: QPainter, t: float, sharp: bool = True) -> None:
        life = win(t, 0.0, 0.35)
        leave = ease_in(win(t, 4.1, 5.0))
        p.save()
        p.setOpacity(life)
        night.paint(p, width, height, gap, ease_out(win(t, 0.0, 0.8)) * (1 - leave))
        _soft_aurora(p, t, width, height, u, leave)
        _frost_paint(p, t, frost, u, leave, frost_drawn)
        _dust(p, t, dust, u, 1 - leave)
        p.restore()
        if sharp:
            heart(p, t)

    # Glass needs its edges and its highlights crisp, whatever the aurora is drawn at.
    paint.sharp = heart
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


def _blur(a: np.ndarray, sigma: float) -> np.ndarray:
    """About a Gaussian blur: three box blurs along each axis, from running sums."""
    r = max(1, round(sigma * 0.9))
    out = a.astype(np.float32)
    for axis in (0, 1):
        for _ in range(3):
            pad = [(0, 0), (0, 0)]
            pad[axis] = (r + 1, r)
            sums = np.cumsum(np.pad(out, pad, mode="edge"), axis=axis)
            high = np.take(sums, np.arange(2 * r + 1, sums.shape[axis]), axis=axis)
            low = np.take(sums, np.arange(0, sums.shape[axis] - 2 * r - 1), axis=axis)
            out = (high - low) / (2 * r + 1)
    return out


def _rgb(color: str) -> np.ndarray:
    c = QColor(color)
    return np.array([c.redF(), c.greenF(), c.blueF()], dtype=np.float32)


def _smooth(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    k = np.clip((x - e0) / (e1 - e0), 0, 1)
    return k * k * (3 - 2 * k)


def _glass(px: int) -> QImage:
    """A heart of clear ice-blue glass px pixels wide, centred in a square picture.

    Its surface rises in a rounded bevel from the outline. Face on it is mostly clear, a pale blue
    deepening to sapphire low on the right, with a cold light gathered low inside; at the bevel it
    reflects the sky (bright above, deep navy below) more and more as it turns away, as glass does;
    two lights show in it with soft edges, a window up on the left (once on each lobe, never at the
    cleft) and a cyan light low on the right; a faint rainbow runs round the bevel."""
    side = int(px * 1.04) + 4
    cx, cy = side / 2, side / 2 - px * 0.145
    outline = QImage(side, side, QImage.Format_Grayscale8)
    outline.fill(0)
    q = QPainter(outline)
    q.setRenderHint(QPainter.Antialiasing)
    q.setPen(Qt.NoPen)
    q.setBrush(QColor(255, 255, 255))
    q.drawPath(heart_path(cx, cy, px))
    q.end()
    stride = outline.bytesPerLine()
    mask = np.frombuffer(outline.constBits(), dtype=np.uint8, count=stride * side).reshape(side, stride)[:, :side] / 255.0
    inside = (mask > 0.5).astype(np.float32)
    # How far in from the outline: the nearest of its segments, measured on every other pixel (the
    # bevel is smoothed after, which hides it) and spread back out.
    ring = heart_points(cx, cy, px, 72)
    ax = np.array([point.x() for point in ring], dtype=np.float32)
    ay = np.array([point.y() for point in ring], dtype=np.float32)
    half_y, half_x = np.mgrid[0:side:2, 0:side:2].astype(np.float32) + 0.5
    dist = np.full(half_x.shape, np.inf, dtype=np.float32)
    for x0, y0, x1, y1 in zip(ax, ay, np.roll(ax, -1), np.roll(ay, -1), strict=True):
        dx, dy = x1 - x0, y1 - y0
        k = np.clip(((half_x - x0) * dx + (half_y - y0) * dy) / (dx * dx + dy * dy + 1e-6), 0, 1)
        dist = np.minimum(dist, np.hypot(half_x - x0 - k * dx, half_y - y0 - k * dy))
    dist = np.kron(dist, np.ones((2, 2), dtype=np.float32))[:side, :side]
    yy, xx = np.mgrid[0:side, 0:side].astype(np.float32)
    bevel = px * 0.2
    k = np.clip(dist / bevel, 0, 1)
    height = _blur(np.sqrt(1 - (1 - k) ** 2) * inside, px * 0.02) * inside
    gy, gx = np.gradient(height * bevel)
    norm = np.sqrt(gx * gx + gy * gy + 1)
    nx, ny, nz = -gx / norm, -gy / norm, 1 / norm
    # What the bevel reflects, looking straight at it.
    rx, ry, rz = 2 * nz * nx, 2 * nz * ny, 2 * nz * nz - 1
    up = np.clip(-ry, -1, 1)[..., None]
    horizon, sky, ground = _rgb("#4f8fe0"), _rgb("#e8fbff"), _rgb("#06123f")
    env = np.where(up > 0, horizon + (sky - horizon) * _smooth(0.0, 0.7, up), horizon + (ground - horizon) * _smooth(0.0, 0.6, -up))
    fresnel = (0.06 + 0.94 * (1 - nz) ** 2.2)[..., None]
    x = (xx - cx) / px
    y = (yy - cy) / px - 0.14
    lights = np.zeros((side, side, 3), dtype=np.float32)
    away_from_cleft = _smooth(0.1, 0.22, np.hypot(x, y + 0.12))
    for (lx, ly, lz), color, strength, mask_by in (
        ((-0.55, -0.62, 0.56), "#ffffff", 0.85, away_from_cleft),
        ((0.62, 0.35, 0.7), "#9ff4ff", 0.5, 1.0),
    ):
        length = (lx * lx + ly * ly + lz * lz) ** 0.5
        facing = (rx * lx + ry * ly + rz * lz) / length
        lights += _rgb(color) * (_smooth(0.9, 0.96, facing) * strength * mask_by)[..., None]
    light, deep = _rgb("#8fd8ff"), _rgb("#1747d8")
    tint = light + (deep - light) * np.clip(0.45 + x * 0.5 + y * 0.9, 0, 1)[..., None]
    gathered = np.exp(-(((x - 0.12) / 0.2) ** 2 + ((y - 0.16) / 0.13) ** 2))
    core = np.exp(-((x / 0.3) ** 2 + ((y - 0.02) / 0.26) ** 2)) * 0.25
    clear = np.clip(0.45 + 0.25 * gathered + 0.3 * core, 0, 1)[..., None]
    through = tint + _rgb("#d9fbff") * (0.6 * gathered)[..., None] + _rgb("#7fe6ff") * core[..., None]
    turn = np.arctan2(ny, nx)
    rainbow = np.stack([0.5 + 0.5 * np.cos(turn * 2 + shift) for shift in (0, 2.1, 4.2)], axis=-1)
    slope = 1 - nz
    fringe = (_smooth(0.15, 0.45, slope) * (1 - _smooth(0.5, 0.8, slope)) * 0.06)[..., None]
    color = through * clear * (1 - fresnel) + env * fresnel + rainbow * fringe + lights
    alpha = clear * (1 - fresnel) + fresnel * np.clip(env.max(axis=-1, keepdims=True) * 0.6 + 0.5, 0, 1)
    alpha = np.clip(np.maximum(alpha, lights.max(axis=-1, keepdims=True)) * mask[..., None], 0, 1)
    color = np.minimum(np.clip(color * mask[..., None], 0, 1), alpha)
    pixels = np.ascontiguousarray((np.dstack([color, alpha]) * 255 + 0.5).astype(np.uint8))
    return QImage(pixels.data, side, side, side * 4, QImage.Format_RGBA8888_Premultiplied).copy()


def _density(p: QPainter) -> float:
    """Pixels per point where p draws: the screen's ratio and any scaling (the small preview)."""
    device = p.device()
    ratio = device.devicePixelRatioF() if device is not None else 1.0
    m = p.worldTransform()
    return max(0.3, ratio * math.hypot(m.m11(), m.m12()))


def _sparks(centre: QPointF, size: float, rnd: random.Random) -> list[tuple]:
    """Glints that gather on the heart's edge as it forms: (from, to, starts)."""
    out = []
    for i, point in enumerate(heart_points(centre.x(), centre.y(), size, 12, 0.5 / 12)):
        angle = math.atan2(point.y() - centre.y(), point.x() - centre.x()) + rnd.uniform(-0.4, 0.4)
        far = size * rnd.uniform(0.9, 1.5)
        start = QPointF(point.x() + math.cos(angle) * far, point.y() + math.sin(angle) * far)
        out.append((start, point, 0.55 + 0.04 * i + rnd.uniform(0, 0.12)))
    return out


def _heart(p: QPainter, t: float, centre: QPointF, sparks: list[tuple], u: float, glass: dict[int, QImage]) -> None:
    """The glass heart: glints gather and it forms; a prism of light sweeps it, it beats once, and at
    the end it melts into light."""
    form = ease_out(win(t, 0.8, 1.55))
    melt = ease_in(win(t, 4.05, 4.75))
    float_y = 3 * u * math.sin(t * 1.7)
    # The glass, drawn for the largest it gets (beating, melting) and only ever shown smaller; made
    # on the first frame, while there is nothing yet to see, so it never holds up the heart.
    px = max(16, math.ceil(150 * u * 1.14 * _density(p) / 8) * 8)
    if px not in glass:
        glass[px] = _glass(px)
    for start, end, when in sparks:
        k = ease_in_out(win(t, when, when + 0.6))
        if 0 < k < 1:
            x = start.x() + (end.x() - start.x()) * k
            y = start.y() + (end.y() - start.y()) * k + float_y * k
            star(p, x, y, 9 * u * (0.5 + 0.5 * math.sin(math.pi * k)), "#ffffff", 0.9)
    if form <= 0 or melt >= 1:
        return
    beat = 1 + 0.06 * max(0.0, math.sin(math.pi * win(t, 2.25, 2.45))) + 0.04 * max(0.0, math.sin(math.pi * win(t, 2.5, 2.68)))
    a = form * (1 - melt)
    c = QPointF(centre.x(), centre.y() + float_y)
    size = 150 * u * (0.82 + 0.18 * form) * beat * (1 + 0.12 * melt)
    glow = QRadialGradient(QPointF(c.x(), c.y() + 6 * u), 150 * u * beat)
    glow.setColorAt(0, col("#7fd0ff", 0.42 * a))
    glow.setColorAt(0.45, col("#2f7bff", 0.18 * a))
    glow.setColorAt(1, col("#2f7bff", 0))
    p.setPen(Qt.NoPen)
    p.setBrush(glow)
    p.drawEllipse(QPointF(c.x(), c.y() + 6 * u), 150 * u * beat, 150 * u * beat)
    picture = glass[px]
    scale = size / px
    side = picture.width()
    p.save()
    p.setOpacity(p.opacity() * a)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(QRectF(c.x() - side / 2 * scale, c.y() - (side / 2 - px * 0.145) * scale, side * scale, side * scale), picture)
    shape = heart_path(c.x(), c.y(), size)
    p.setClipPath(shape)
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    _aurora_within(p, t, c, size)
    p.restore()
    p.save()
    p.setClipPath(shape)
    p.setPen(Qt.NoPen)
    # The prism: a band of spectrum and white crossing from the top left.
    for sweep, strength in ((win(t, 1.75, 2.55), 0.8), (win(t, 3.1, 3.7), 0.45)):
        if not 0 < sweep < 1:
            continue
        p.save()
        p.translate(c.x() - size * 0.75 + size * 1.5 * sweep, c.y() - size * 0.6 + size * 1.2 * sweep)
        p.rotate(-45)
        band = QLinearGradient(QPointF(-size * 0.16, 0), QPointF(size * 0.16, 0))
        band.setColorAt(0, col("#7ff2e6", 0))
        band.setColorAt(0.3, col("#7ff2e6", 0.45 * strength * a))
        band.setColorAt(0.5, col("#ffffff", 0.8 * strength * a))
        band.setColorAt(0.7, col("#ff9ad5", 0.4 * strength * a))
        band.setColorAt(1, col("#9a7bff", 0))
        p.setBrush(band)
        p.drawRect(QRectF(-size * 0.16, -size, size * 0.32, 2 * size))
        p.restore()
    p.restore()
    # The edge: icy starlight, a haze round a fine bright line.
    p.setBrush(Qt.NoBrush)
    for width, color, alpha in ((10, "#7fd0ff", 0.10), (4, "#bff3ff", 0.30), (1.3, "#ffffff", 0.85)):
        p.setPen(QPen(col(color, alpha * a), width * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(shape)
    p.setPen(Qt.NoPen)
    sweep = win(t, 1.75, 2.55)
    if 0 < sweep < 1:
        star(p, c.x() - size * 0.3 + size * 0.6 * sweep, c.y() - size * 0.2 + size * 0.4 * sweep, 22 * u * math.sin(math.pi * sweep), "#ffffff", 0.95 * a)
    if melt <= 0 and t > 2.3:
        twinkle = max(0.0, math.sin(math.pi * win(t, 3.4, 3.8)))
        star(p, c.x() + size * 0.23, c.y() - size * 0.2, 16 * u * twinkle, "#ffffff", twinkle)
    # Melting: the light it held goes up as glints.
    if melt > 0:
        for i, point in enumerate(heart_points(c.x(), c.y(), size, 8, 0.5 / 8)):
            rise = 60 * u * melt * (0.6 + 0.08 * i)
            star(p, point.x(), point.y() - rise, 8 * u * math.sin(math.pi * melt), "#ffffff", 0.9 * (1 - melt))


def _aurora_within(p: QPainter, t: float, c: QPointF, size: float) -> None:
    """Aurora light drifting inside the heart: two wide bands, cyan through violet, drawn a quarter
    size and laid on scaled up, so they are soft light and not stripes."""
    shrink = 4.0
    box = QRectF(c.x() - size * 0.55, c.y() - size * 0.45, size * 1.1, size * 0.95)
    small = QImage(max(1, round(box.width() / shrink)), max(1, round(box.height() / shrink)), QImage.Format_ARGB32_Premultiplied)
    small.fill(Qt.transparent)
    inner = QPainter(small)
    inner.setRenderHint(QPainter.Antialiasing)
    inner.scale(1 / shrink, 1 / shrink)
    inner.translate(-box.left(), -box.top())
    inner.setCompositionMode(QPainter.CompositionMode_Plus)
    for i, (off, amp, speed, phase, bright) in enumerate(((-0.04, 0.08, 0.9, 0.0, 1.0), (0.22, 0.06, -0.7, 2.4, 0.75))):
        path = QPainterPath()
        for s in range(25):
            k = s / 24
            y = c.y() + size * (off + amp * math.sin(k * 4.2 + t * speed + phase) + 0.025 * math.sin(k * 9 + t * 1.3 + phase))
            point = QPointF(box.left() + box.width() * k, y)
            if s == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        across = QLinearGradient(QPointF(box.left(), 0), QPointF(box.right(), 0))
        for s in range(7):
            across.setColorAt(s / 6, spectrum(WITHIN, s / 6 * 0.8 + t * 0.12 + i * 0.3))
        for width, alpha in ((0.34, 0.12), (0.2, 0.16), (0.09, 0.22)):
            inner.setOpacity(alpha * bright)
            inner.setPen(QPen(across, size * width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            inner.drawPath(path)
    inner.end()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(box, small)


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
