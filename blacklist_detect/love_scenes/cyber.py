"""赛博闪电 Cyber Spark: neon, lightning and molten sparks in a cyberpunk night.

The edges deepen to an indigo night, worked out per pixel: plum and violet pooled in the corners
with smog drifting through it and a little neon light spilled into it, scan lines over it, a neon
floor grid glowing out to its horizon in the two bottom corners, and digital rain falling down the
right side; the names stay clear. A small spark runs round the edge of the screen from the top left
and lights two neon tubes behind it, cyan outside and magenta in, cut at the corners like a HUD;
they stutter on as neon does. Down the left edge hangs a tall street sign, as in Tokyo: a dark box
on two brackets with a cyan neon border, 心 and 动 stacked in magenta neon tube and a little neon
heart under them. Lightning strikes it and it flickers on; little arcs crawl over its border. Six
times a leader feels its way down and lightning strikes the sign, the sides and the top: a
white-hot core in a cyan and violet bloom that lights up its side of the screen and the tubes, a
flash where it lands and a ring thrown off it, then the restrike down the same channel. Struck
again, the sign surges. Each strike throws a shower of molten sparks, streaks with glowing heads
that cool from white through gold and orange to magenta as they fly, bounce off the bottom tube and
skitter along it. Twice the sign glitches, torn into slices. At the end the neon powers down.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPolygonF

from blacklist_detect.love_scenes.draw import (
    Wash,
    clamp,
    col,
    ease_in,
    ease_out,
    heart_path,
    mix,
    partial,
    polyline,
    star,
    win,
)
from blacklist_detect.love_scenes.light import bloom, blur, glow, mask, noise, picture, rgb, scaled_up, smooth

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
CYAN = "#21f6ff"
MAGENTA = "#ff2bd6"
VIOLET = "#7a2cff"
NIGHT = "#07021a"
INDIGO = "#12062e"
# Glow pictures are soft: worked out at this share of the stage's size and laid on scaled up.
SOFT = 0.25
GLYPHS = "01アイウカキ7ハ#ナ"
# A spark cooling as it flies, (heat, color): white hot, gold, orange, then magenta as it dies.
COOLING = ((0.0, MAGENTA), (0.25, "#ff3d6e"), (0.48, "#ff7f26"), (0.7, "#ffc247"), (0.88, "#fff0b0"), (1.0, "#ffffff"))
# Sparks are drawn in this many steps of heat, one batch of lines each.
HEATS = 8
# A spark's track is worked out in steps this long; its streak is how far it flies in SHUTTER, as a
# camera blurs it.
STEP = 1 / 120
SHUTTER = 0.055
# The leader feels its way down this long before a strike lands.
LEAD = 0.09
# When lightning strikes the sign: the first lights it, the second makes it surge.
SIGN_STRIKES = (0.75, 2.2)


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(77)
    outer = _frame(width, height, gap, 15 * u, 34 * u, u)
    inner = _frame(width, height, gap, 25 * u, 40 * u, u)
    frame_glow = _frame_glow(width, height, outer, inner, u)
    sign = QRectF(width * 0.022, height * 0.22, width * 0.083, height * 0.58)
    shapes = _sign_shapes(sign, u)
    area, sign_glow = _sign_glow(sign, shapes, u)
    border = shapes[0].toSubpathPolygons()[0]
    ring = [border[round(i * (border.size() - 1) / 120)] for i in range(120)]
    night = Wash(lambda q, w, h: _night(q, w, h, u))
    flashes = [_flash(width, height, gap, u, side) for side in (-1, 1)]
    top = 15 * u
    # (when it lands, where from, where to, which way its sparks fly, how many, seed)
    strikes = [
        (SIGN_STRIKES[0], QPointF(width * 0.09, -height * 0.03), QPointF(sign.center().x(), sign.top() + 3 * u), -1.57, 70, 1),
        (1.55, QPointF(width * 0.95, -height * 0.03), QPointF(width - top, height * 0.52), math.pi + 0.95, 84, 2),
        (SIGN_STRIKES[1], QPointF(width * 0.21, -height * 0.03), QPointF(sign.center().x() + 26 * u, sign.top() + 4 * u), -2.1, 56, 3),
        (2.95, QPointF(width * 0.99, height * 0.2), QPointF(width - top, height * 0.8), math.pi + 0.8, 84, 4),
        (3.45, QPointF(width * 0.005, height * 0.8), QPointF(width * 0.12, height - 25 * u), -1.9, 70, 5),
        (3.9, QPointF(width * 0.78, -height * 0.03), QPointF(width * 0.85, top), 1.57, 50, 6),
    ]
    names = QRectF(width * 0.13, height * 0.29, width * 0.81, height * 0.55)
    title = QRectF(width * 0.38, height * 0.07, width * 0.3, height * 0.18)
    keep = (names, title, gap.adjusted(-30 * u, -30 * u, 30 * u, 30 * u))
    # Each strike's lightning, worked out when first wanted.
    bolts: dict[int, list[tuple]] = {}
    showers = {
        seed: _shower(end, aim, count, u, seed, width, height, keep, short=seed in (3, 6))
        for _when, _start, end, aim, count, seed in strikes
    }
    lights = {name: _dot(color, white) for name, color, white in (("hot", "#bff9ff", 1.0), ("cyan", CYAN, 0.25), ("violet", VIOLET, 0.0))}
    heats = _heats(u)
    rain = [(width * (0.908 + 0.012 * i), rnd.uniform(0.55, 1.1) * height, rnd.uniform(0, 3), rnd.randrange(1000)) for i in range(7)]
    glyphs = _glyphs(u)
    arcs = [(1.7 + 0.32 * i + rnd.uniform(0, 0.12), rnd.randrange(120), rnd.randrange(6, 20)) for i in range(7)]
    # The lit tubes and the sign, drawn once for each sharpness they are shown at.
    baked: dict[float, tuple] = {}

    def bake(scale: float) -> tuple:
        if scale not in baked:
            tubes = [_tube_strips(points, tint, width, height, u, scale) for points, tint in ((outer, CYAN), (inner, MAGENTA))]
            baked[scale] = (tubes, _sign_baked(sign, area, shapes, sign_glow, u, scale))
        return baked[scale]

    def bolt(seed: int, start: QPointF, end: QPointF, when: float) -> list[tuple]:
        # Only the strikes meant for the sign cross it.
        if seed not in bolts:
            bolts[seed] = _bolt_shapes(start, end, seed, u, (names, title) if when in SIGN_STRIKES else (names, title, sign))
        return bolts[seed]

    def paint(p: QPainter, t: float) -> None:
        tubes, signs = bake(_sharpness(p))
        life = win(t, 0.0, 0.3)
        leave = ease_in(win(t, 4.35, 5.0))
        p.save()
        p.setOpacity(life)
        night.paint(p, width, height, gap, ease_out(win(t, 0.0, 0.7)) * (1 - leave))
        bright = max((_strike_light(t - when) for when, *_rest in strikes), default=0.0)
        # A strike lights its own side of the screen most.
        for side, flash in zip((-1, 1), flashes, strict=True):
            near = max(
                (_strike_light(t - when) * (1.0 if (end.x() < width / 2) == (side < 0) else 0.3) for when, _start, end, *_rest in strikes),
                default=0.0,
            )
            if near * (1 - leave) > 0.01:
                p.setOpacity(life * near * (1 - leave))
                scaled_up(flash, p, 0, 0, width, height)
        p.setOpacity(life)
        _rain(p, t, rain, glyphs, u, height, (1 - leave) * ease_out(win(t, 0.2, 1.0)))
        _neon_frame(p, t, outer, inner, frame_glow, tubes, lights, width, height, u, bright)
        _sign(p, t, area, signs, u, ring, arcs, leave)
        for when, start, end, _aim, _count, seed in strikes:
            if -LEAD <= t - when <= 0.55:
                _strike(p, t - when, start, end, bolt(seed, start, end, when), lights, u)
        for when, *_rest, seed in strikes:
            _spark_shower(p, t - when, showers[seed], heats, u)
        p.restore()
        # One strike's lightning worked out ahead each frame, so no frame waits long for it.
        for when, start, end, _aim, _count, seed in strikes:
            if seed not in bolts:
                bolt(seed, start, end, when)
                break

    return paint


def _frame(width: float, height: float, gap: QRectF, inset: float, cut: float, u: float) -> list[QPointF]:
    """The neon tube round the screen as one line from the gap's left round to its right: inset from
    the edges, its corners cut, a tab stepping down under the middle of the top edge."""
    m, c = inset, cut
    bottom = height - m
    left_end, right_end = gap.left() - 40 * u, gap.right() + 40 * u
    tab = 12 * u
    return [
        QPointF(left_end, bottom), QPointF(m + c, bottom), QPointF(m, bottom - c), QPointF(m, m + c), QPointF(m + c, m),
        QPointF(width * 0.34, m), QPointF(width * 0.34 + tab, m + tab), QPointF(width * 0.66 - tab, m + tab), QPointF(width * 0.66, m),
        QPointF(width - m - c, m), QPointF(width - m, m + c), QPointF(width - m, bottom - c), QPointF(width - m - c, bottom),
        QPointF(right_end, bottom),
    ]  # fmt: skip


def _frame_glow(width: float, height: float, outer: list[QPointF], inner: list[QPointF], u: float) -> tuple[QImage, QImage]:
    """The light the two tubes throw, worked out per pixel at a quarter of the size: soft anyway."""
    w, h = max(1, round(width * SOFT)), max(1, round(height * SOFT))
    out = []
    for points, tint in ((outer, CYAN), (inner, MAGENTA)):

        def draw(q: QPainter, points: list[QPointF] = points) -> None:
            q.scale(SOFT, SOFT)
            q.setPen(QPen(Qt.white, 5 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            q.drawPath(polyline(points))

        out.append(bloom(mask(w, h, draw), tint, ((1.5, 1.1), (5, 0.9), (14, 0.7)), white=0.4))
    return out[0], out[1]


def _sign_shapes(sign: QRectF, u: float) -> tuple[QPainterPath, QPainterPath, QPainterPath]:
    """The street sign's three neon tubes: its border with a bar across near the bottom, 心 and 动
    stacked, and the little heart under them."""
    border = QPainterPath()
    border.addRoundedRect(sign.adjusted(8 * u, 8 * u, -8 * u, -8 * u), 10 * u, 10 * u)
    bar = sign.top() + sign.height() * 0.86
    border.moveTo(sign.left() + 26 * u, bar)
    border.lineTo(sign.right() - 26 * u, bar)
    font = QFont("Microsoft YaHei")
    font.setWeight(QFont.Light)
    font.setPixelSize(max(4, round(sign.width() * 0.74)))
    letters = QPainterPath()
    for i, glyph in enumerate("心动"):
        shape = QPainterPath()
        shape.addText(0, 0, font, glyph)
        box = shape.boundingRect()
        shape.translate(sign.center().x() - box.center().x(), sign.top() + sign.height() * (0.2 + 0.25 * i) - box.center().y())
        letters.addPath(shape)
    heart = heart_path(sign.center().x(), sign.top() + sign.height() * 0.68, sign.width() * 0.5)
    return border, letters, heart


def _sign_glow(sign: QRectF, shapes: tuple[QPainterPath, ...], u: float) -> tuple[QRectF, list[QImage]]:
    """The light of the sign's three tubes, per pixel at half size: the cyan border, the magenta
    letters and heart. Returns the area the light covers, and the light of each."""
    area = sign.adjusted(-60 * u, -60 * u, 60 * u, 60 * u)
    k = 0.5
    out = []
    for shape, tint, fill in zip(shapes, (CYAN, MAGENTA, MAGENTA), (False, True, False), strict=True):

        def draw(q: QPainter, shape: QPainterPath = shape, fill: bool = fill) -> None:
            q.scale(k, k)
            q.translate(-area.left(), -area.top())
            q.setPen(QPen(Qt.white, (3 if fill else 5) * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            q.setBrush(Qt.white if fill else Qt.NoBrush)
            q.drawPath(shape)

        out.append(bloom(mask(round(area.width() * k), round(area.height() * k), draw), tint, ((2, 1.2), (7, 1.0), (20, 0.8)), white=0.5))
    return area, out


def _sign_baked(sign: QRectF, area: QRectF, shapes: tuple[QPainterPath, ...], glows: list[QImage], u: float, scale: float) -> list[QImage]:
    """The sign drawn once at scale: its dark box on two brackets, then each tube lit over its own
    light, each a picture of its own so each can flicker on its own."""
    border, letters, heart = shapes

    def plate(q: QPainter) -> None:
        q.setPen(Qt.NoPen)
        for y in (sign.top() + 46 * u, sign.bottom() - 46 * u):
            q.setBrush(col("#231c33"))
            q.drawRect(QRectF(0, y - 3 * u, sign.left() + 4 * u, 6 * u))
            q.setBrush(col("#625880", 0.8))
            q.drawRect(QRectF(0, y - 3 * u, sign.left() + 4 * u, 1.2 * u))
        q.setBrush(col("#0a0414", 0.92))
        q.setPen(QPen(col("#3b2d58"), 1.5 * u))
        q.drawRoundedRect(sign, 12 * u, 12 * u)

    def glyphs(q: QPainter) -> None:
        # Tube characters: magenta glass round a pale hot middle.
        q.setPen(QPen(col(MAGENTA, 0.95), 2.2 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        q.setBrush(mix(MAGENTA, "#ffffff", 0.6))
        q.drawPath(letters)

    tubes = (lambda q: _tube(q, border, CYAN, 1.0, 5.5 * u), glyphs, lambda q: _tube(q, heart, MAGENTA, 1.0, 5.5 * u))
    out = [_baked(area, scale, plate)]
    for light, tube in zip(glows, tubes, strict=True):

        def draw(q: QPainter, light: QImage = light, tube=tube) -> None:  # noqa: ANN001
            q.drawImage(area, light)
            tube(q)

        out.append(_baked(area, scale, draw))
    return out


def _sharpness(p: QPainter) -> float:
    """Pixels per point where p draws: its screen's and its own scaling."""
    device = p.device()
    ratio = device.devicePixelRatioF() if device is not None else 1.0
    return round(ratio * math.hypot(p.transform().m11(), p.transform().m12()), 2)


def _baked(rect: QRectF, scale: float, draw) -> QImage:  # noqa: ANN001
    """What draw paints over rect, as a picture of scale pixels to the point."""
    image = QImage(max(1, math.ceil(rect.width() * scale)), max(1, math.ceil(rect.height() * scale)), QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    q.setRenderHint(QPainter.SmoothPixmapTransform)
    q.scale(image.width() / rect.width(), image.height() / rect.height())
    q.translate(-rect.left(), -rect.top())
    draw(q)
    q.end()
    return image


def _tube(p: QPainter, path: QPainterPath, tint: str, level: float, width: float) -> None:
    """A lit neon tube along path, width wide: its colored glass, then its white-hot middle."""
    p.setBrush(Qt.NoBrush)
    for w, color, alpha in ((width, col(tint), 0.5), (width * 3 / 7, mix(tint, "#ffffff", 0.75), 0.95)):
        color.setAlphaF(clamp(alpha * level))
        p.setPen(QPen(color, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)


def _tube_strips(points: list[QPointF], tint: str, width: float, height: float, u: float, scale: float) -> list[tuple[QRectF, QImage]]:
    """A frame tube lit, as four pictures along the screen's edges: the middle has none of it."""
    band = 46 * u
    path = polyline(points)
    rects = (
        QRectF(0, 0, width, band), QRectF(0, height - band, width, band),
        QRectF(0, band, band, height - 2 * band), QRectF(width - band, band, band, height - 2 * band),
    )  # fmt: skip
    return [(rect, _baked(rect, scale, lambda q: _tube(q, path, tint, 1.0, 7 * u))) for rect in rects]


def _field(width: float, height: float, u: float) -> tuple[np.ndarray, ...]:
    """Each pixel of a quarter-size picture of the stage, in points: x, y, how clear of the names
    it is (0 over them, 1 well away) and how near the screen's edge (1 at it, 0 far in)."""
    w, h = max(1, round(width * SOFT)), max(1, round(height * SOFT))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    x, y = (xs + 0.5) / SOFT, (ys + 0.5) / SOFT
    # How far outside the names' box, its corners rounded so the night does not draw a rectangle.
    r = 120 * u
    dx = np.maximum(np.maximum(width * 0.13 + r - x, x - width * 0.94 + r), 0)
    dy = np.maximum(np.maximum(height * 0.29 + r - y, y - height * 0.84 + r), 0)
    clear = smooth(0, 150 * u, np.hypot(dx, dy) - r)
    rim = 1 - smooth(0, 300 * u, np.minimum(np.minimum(x, width - x), np.minimum(y, height - y)))
    return x, y, clear, rim


def _night(p: QPainter, width: float, height: float, u: float) -> None:
    """The night at the edges, per pixel: deep indigo darkening toward the edges with smog drifting
    through it, pooling to plum and violet at the edges where a little neon light spills, the
    floor's glow to its horizon in the bottom corners; then the floor grid and scan lines drawn
    sharp into it."""
    x, y, clear, rim = _field(width, height, u)
    h, w = x.shape
    smog = noise(w, h, 110 * u * SOFT, 3, 9)
    dark = clear * (0.42 + 0.5 * rim) * (0.85 + 0.3 * smog)
    tone = rgb(NIGHT) * rim[..., None] + rgb(INDIGO) * (1 - rim[..., None])
    # Deep color pooled at the edges: plum behind the sign, violet top right, wine bottom left,
    # blue-violet bottom right.
    for cx, cy, reach, tint in (
        (width * 0.05, height * 0.4, 460 * u, "#2a0838"),
        (width, 0.0, 620 * u, "#1a0a4d"),
        (0.0, height, 640 * u, "#33082f"),
        (width, height, 620 * u, "#0b1245"),
    ):
        g = (np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / reach ** 2 * 2.0) * (0.6 + 0.5 * smog) * 0.9)[..., None]
        tone = tone * (1 - g) + rgb(tint) * g
    light = tone * dark[..., None]
    amount = dark.copy()
    horizon = height * 0.865
    # Neon light spilled into the smog.
    for cx, cy, reach, tint, strength in (
        (width * 0.04, height * 0.4, 320 * u, MAGENTA, 0.12),
        (width * 0.98, 0.0, 420 * u, VIOLET, 0.16),
        (0.0, height, 420 * u, MAGENTA, 0.14),
        (width, height, 400 * u, CYAN, 0.08),
    ):
        g = np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / reach ** 2 * 2.2) * strength * clear * smog * 2
        light += g[..., None] * rgb(tint)
        amount += g
    # The floor: a glow on the horizon line, fading down over the floor, magenta left and cyan right.
    below = np.clip((y - horizon) / (height - horizon), 0, 1)
    line = np.exp(-(((y - horizon) / (5 * u)) ** 2)) * 0.55 + (y > horizon) * np.exp(-below * 2.5) * 0.22
    for side, tint in ((1 - smooth(width * 0.05, width * 0.33, x), MAGENTA), (smooth(width * 0.67, width * 0.95, x), CYAN)):
        g = line * side * clear
        light += g[..., None] * rgb(tint)
        amount += g
    alpha = np.clip(amount, 0, 0.94)
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(QRectF(0, 0, width, height), picture(light / np.maximum(amount, 1e-4)[..., None], alpha))
    # Grid and scan lines are drawn into the night only, as much as it is there: none over the names.
    p.setCompositionMode(QPainter.CompositionMode_SourceAtop)
    vanish = QPointF(width * 0.5, height * 0.7)
    for left in (True, False):
        edge = 0.0 if left else width
        reach = width * 0.34
        pen = QPen(col(mix(CYAN if left else MAGENTA, "#ffffff", 0.2), 0.75), 1.3 * u)
        p.setPen(pen)
        for i in range(10):
            bottom_x = edge + (1 if left else -1) * (i * 58 - 70) * u
            k = (horizon - vanish.y()) / (height - vanish.y())
            p.drawLine(QPointF(vanish.x() + (bottom_x - vanish.x()) * k, horizon), QPointF(bottom_x, height))
        for j in range(1, 7):
            row = horizon + (height - horizon) * (j / 6) ** 1.8
            p.drawLine(QPointF(edge, row), QPointF(edge + (reach if left else -reach), row))
    p.setPen(QPen(col("#000000", 0.3), 1.3 * u))
    row = 0.0
    while row < height:
        p.drawLine(QPointF(0, row), QPointF(width, row))
        row += 4 * u
    p.restore()


def _flash(width: float, height: float, gap: QRectF, u: float, side: int) -> QImage:
    """The edges of one side (-1 left, 1 right) lit by a strike, per pixel at a quarter of the size:
    blue-white at the very edge, through cyan to violet; none over the names or the gap."""
    x, y, clear, rim = _field(width, height, u)
    half = 1 - smooth(width * 0.2, width * 0.75, x) if side < 0 else smooth(width * 0.25, width * 0.8, x)
    away = np.hypot(np.maximum(np.maximum(gap.left() - x, x - gap.right()), 0), np.maximum(gap.top() - y, 0))
    light = rim ** 1.6 * clear * half * smooth(0, 60 * u, away)
    color = (
        rgb("#e9fdff") * (light ** 2)[..., None]
        + rgb(CYAN) * (light * (1 - light))[..., None] * 1.6
        + rgb(VIOLET) * (1 - light)[..., None] * 0.3
    )
    return picture(color / np.maximum(color.max(axis=-1), 1e-4)[..., None], light * 0.36)


def _dot(tint: str, white: float, side: int = 64) -> QImage:
    """A round glow as a picture: a hot middle going white by white, the tint round it fading out."""
    ys, xs = np.mgrid[0:side, 0:side].astype(np.float32)
    r = np.hypot(xs - (side - 1) / 2, ys - (side - 1) / 2) / (side / 2)
    halo = np.exp(-((r * 2.4) ** 2)) * 0.75 + np.exp(-r * 5.5) * 0.5
    core = np.exp(-((r * 9) ** 2))
    fade = np.clip((1 - r) * 4, 0, 1)
    color = rgb(tint)
    light = (halo[..., None] * color + core[..., None] * (color * 0.5 + white)) * fade[..., None]
    return glow(light.astype(np.float32))


def _lay(p: QPainter, image: QImage, x: float, y: float, r: float, alpha: float) -> None:
    """A round glow picture laid on at x, y, r its radius."""
    if alpha <= 0.01 or r <= 0.3:
        return
    p.setOpacity(alpha)
    p.drawImage(QRectF(x - r, y - r, 2 * r, 2 * r), image)


def _cool(heat: float) -> QColor:
    for (lo, a), (hi, b) in zip(COOLING, COOLING[1:], strict=False):
        if heat <= hi:
            return mix(a, b, (heat - lo) / (hi - lo))
    return QColor(COOLING[-1][1])


def _heats(u: float) -> list[tuple[QPen, QPen, QImage]]:
    """For each step of heat: the pen of a spark's hot core, the pen of the glow round its front,
    and the glow on its head. Cooler sparks are dimmer and thinner."""
    out = []
    for b in range(HEATS):
        heat = (b + 0.5) / HEATS
        core = mix(_cool(heat), "#ffffff", 0.3 * heat ** 2, 0.12 + 0.88 * heat ** 1.2)
        halo = _cool(heat * 0.85)
        halo.setAlphaF(0.08 + 0.3 * heat)
        out.append((
            QPen(core, (0.8 + 1.4 * heat) * u, Qt.SolidLine, Qt.RoundCap),
            QPen(halo, (2.4 + 4.0 * heat) * u, Qt.SolidLine, Qt.RoundCap),
            _dot(_cool(heat).name(), max(0.0, heat - 0.3) * 1.5, 32),
        ))  # fmt: skip
    return out


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


def _neon_frame(
    p: QPainter, t: float, outer: list[QPointF], inner: list[QPointF], glows: tuple[QImage, QImage], tubes: list, lights: dict,
    width: float, height: float, u: float, bright: float
) -> None:
    """A spark runs round from the top left and lights the tubes behind it; their light comes on
    with a stutter once it is round, and surges when lightning strikes."""
    trace = ease_out(win(t, 0.3, 1.1))
    if trace <= 0:
        return
    base = p.opacity()
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    parts = ((outer, CYAN, glows[0], tubes[0], 1.12), (inner, MAGENTA, glows[1], tubes[1], 1.24))
    for index, (points, tint, light, strips, on) in enumerate(parts):
        level = _neon(t, on, index) * _power_down(t, index)
        if level > 0:
            p.setOpacity(base * level)
            p.drawImage(QRectF(0, 0, width, height), light)
            if bright > 0.05:
                p.setCompositionMode(QPainter.CompositionMode_Plus)
                p.setOpacity(base * level * bright * 0.7)
                p.drawImage(QRectF(0, 0, width, height), light)
                p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        lit = max(level, 0.55 if t < on + 0.3 else 0.0)
        if lit <= 0:
            continue
        if trace >= 1:
            p.setOpacity(base * lit)
            for rect, image in strips:
                p.drawImage(rect, image)
            continue
        # From the top left corner both ways: down the left to the gap, and on round to the gap's right.
        corner = min(range(len(points)), key=lambda i: points[i].x() + points[i].y())
        for half in (points[corner::-1], points[corner:]):
            path = polyline(partial(half, trace))
            p.setOpacity(base)
            _tube(p, path, tint, lit, 7 * u)
            if index == 0:
                # The running spark: small, and gone before it reaches the gap.
                head = path.currentPosition()
                fade = 1 - win(trace, 0.7, 0.97)
                _lay(p, lights["cyan"], head.x(), head.y(), 26 * u, 0.8 * fade * base)
                _lay(p, lights["hot"], head.x(), head.y(), 10 * u, fade * base)
                p.setOpacity(base)
                star(p, head.x(), head.y(), 13 * u, "#ffffff", 0.85 * fade)
    p.restore()


def _sign(
    p: QPainter, t: float, area: QRectF, parts: list[QImage], u: float, ring: list[QPointF], arcs: list[tuple], leave: float
) -> None:
    """The street sign: its box, then border, letters and heart flickering on one after another,
    surging when struck, torn into slices when it glitches, little arcs crawling over its border."""
    surge = max(_strike_light(t - when) for when in SIGN_STRIKES)
    glitch = max(math.sin(math.pi * win(t, 2.88, 3.02)), math.sin(math.pi * win(t, 3.6, 3.7)))
    levels = [1 - leave] + [_neon(t, on, seed) * _power_down(t, seed) for on, seed in ((0.85, 2), (1.0, 3), (1.2, 4))]
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    base = p.opacity()
    if glitch > 0:
        # Torn into slices, each pushed sideways, with ghosts either side.
        rnd = random.Random(int(t * 30) * 7)
        bands = 9
        for i in range(bands):
            band = QRectF(area.left() - 40 * u, area.top() + area.height() * i / bands, area.width() + 80 * u, area.height() / bands + 1)
            shift = rnd.uniform(-20, 20) * u * glitch
            p.save()
            p.setClipRect(band)
            for image, level in zip(parts, levels, strict=True):
                if level <= 0:
                    continue
                for dx, alpha in ((shift - 7 * u * glitch, 0.4), (shift + 7 * u * glitch, 0.4), (shift, 1.0)):
                    p.setOpacity(base * min(1.0, level) * alpha)
                    p.drawImage(area.translated(dx, 0), image)
            p.restore()
    else:
        for index, (image, level) in enumerate(zip(parts, levels, strict=True)):
            if level <= 0:
                continue
            p.setOpacity(base * min(1.0, level))
            p.drawImage(area, image)
            if index and surge > 0:
                # Struck, it burns brighter.
                p.setCompositionMode(QPainter.CompositionMode_Plus)
                p.setOpacity(base * min(1.0, level) * surge * 0.7)
                p.drawImage(area, image)
                p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    p.restore()
    if levels[1] <= 0:
        return
    for when, start, span in arcs:
        age = t - when
        if 0 <= age < 0.22:
            _arc(p, ring[start], ring[(start + span) % len(ring)], int(t * 25) + start, u, (1 - age / 0.22) * min(1.0, levels[1]), 0.5)


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


def _bolt_shapes(start: QPointF, end: QPointF, seed: int, u: float, keep: tuple[QRectF, ...]) -> list[tuple]:
    """A strike's two shapes, the flash and the restrike down the same channel with new branches:
    (main line, branches, the box its light covers, that light). Channel and branches keep out of
    the names and the title: one that strays into them is drawn again."""

    def clear(points: list[QPointF]) -> bool:
        return not any(rect.contains(q) for rect in keep for q in points)

    rnd = random.Random(seed)
    channel = _bolt_points(start, end, rnd, 0.09, 6)
    for _ in range(60):
        if clear(channel):
            break
        channel = _bolt_points(start, end, rnd, 0.09, 6)
    out = []
    for k in range(2):
        rnd = random.Random(seed * 1000 + k)
        main = [channel[0], *(QPointF(q.x() + rnd.gauss(0, 2 * u), q.y() + rnd.gauss(0, 2 * u)) for q in channel[1:-1]), channel[-1]]
        branches = []
        for _ in range(16):
            a, rest = main[rnd.randrange(len(main) // 6, len(main) * 3 // 4)], main[-1]
            angle = math.atan2(rest.y() - a.y(), rest.x() - a.x()) + rnd.choice((-1, 1)) * rnd.uniform(0.35, 0.85)
            reach = math.dist((a.x(), a.y()), (rest.x(), rest.y())) * rnd.uniform(0.2, 0.45)
            branch = _bolt_points(a, QPointF(a.x() + math.cos(angle) * reach, a.y() + math.sin(angle) * reach), rnd, 0.13, 4)
            if not clear(branch):
                continue
            branches.append(branch)
            if rnd.random() < 0.6:
                # A twig off the branch.
                b = branch[len(branch) // 2]
                bend = angle + rnd.choice((-1, 1)) * rnd.uniform(0.4, 0.9)
                twig = _bolt_points(b, QPointF(b.x() + math.cos(bend) * reach * 0.4, b.y() + math.sin(bend) * reach * 0.4), rnd, 0.15, 3)
                if clear(twig):
                    branches.append(twig)
            if len(branches) >= 6:
                break
        box, light = _bolt_light(main, branches, u)
        out.append((QPolygonF(main), [QPolygonF(b) for b in branches], box, light, main))
    return out


def _bolt_light(main: list[QPointF], branches: list[list[QPointF]], u: float) -> tuple[QRectF, QImage]:
    """The light round a bolt, per pixel at a quarter of the size: white where it burns, a pale cyan
    bloom close round it, then cyan and violet spreading wide, lighting what is near."""
    k = 0.25
    pad = 110 * u
    xs = [q.x() for q in main] + [q.x() for b in branches for q in b]
    ys = [q.y() for q in main] + [q.y() for b in branches for q in b]
    box = QRectF(min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad)

    def draw(q: QPainter) -> None:
        q.scale(k, k)
        q.translate(-box.left(), -box.top())
        q.setPen(QPen(Qt.white, 5 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        q.drawPolyline(QPolygonF(main))
        q.setPen(QPen(col("#ffffff", 0.7), 2.6 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for b in branches:
            q.drawPolyline(QPolygonF(b))

    core = mask(round(box.width() * k), round(box.height() * k), draw)
    light = (core ** 1.5)[..., None] * rgb("#ffffff") * 1.1
    for sigma, tint, strength in ((1, "#9ff7ff", 1.2), (3, CYAN, 1.9), (8.5, mix(CYAN, VIOLET, 0.55).name(), 3.4), (21, VIOLET, 6.0)):
        light += blur(core, sigma)[..., None] * rgb(tint) * strength
    # Faded out toward the box's edges, so its widest light shows no edge.
    h, w = core.shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    edge = np.minimum(np.minimum(xs, w - 1 - xs), np.minimum(ys, h - 1 - ys))
    light *= smooth(0, pad * k, edge)[..., None]
    return box, glow(light)


def _strike(p: QPainter, age: float, start: QPointF, end: QPointF, shapes: list[tuple], lights: dict, u: float) -> None:
    """A leader feeling its way down, then the strike: its light, its white core, a flash and a ring
    where it lands."""
    if age < -LEAD or age > 0.55:
        return
    p.save()
    base = p.opacity()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    if age < 0:
        # The leader: a faint stepped line down the channel, a glow at its tip.
        reach = partial(shapes[0][4], (age + LEAD) / LEAD)
        p.setPen(QPen(col("#c9f9ff", 0.65), 1.5 * u, Qt.SolidLine, Qt.RoundCap, Qt.BevelJoin))
        p.drawPolyline(QPolygonF(reach))
        tip = reach[-1]
        _lay(p, lights["cyan"], tip.x(), tip.y(), 34 * u, 0.6 * base)
        p.restore()
        return
    light = _strike_light(age)
    main, branches, box, halo, _points = shapes[0 if age < 0.1 else 1]
    if light > 0:
        p.setOpacity(base * light)
        p.drawImage(box, halo)
        p.setOpacity(base)
        p.setPen(QPen(col("#ffffff", light), 2.2 * u, Qt.SolidLine, Qt.RoundCap, Qt.BevelJoin))
        p.drawPolyline(main)
        p.setPen(QPen(col("#e6fdff", 0.8 * light), 1.1 * u, Qt.SolidLine, Qt.RoundCap, Qt.BevelJoin))
        for branch in branches:
            p.drawPolyline(branch)
        # It lights where it lands and the sky it comes from.
        _lay(p, lights["violet"], end.x(), end.y(), 210 * u, 0.55 * light * base)
        _lay(p, lights["cyan"], end.x(), end.y(), 120 * u, 0.8 * light * base)
        _lay(p, lights["hot"], end.x(), end.y(), 42 * u, light * base)
        _lay(p, lights["violet"], start.x(), start.y(), 200 * u, 0.6 * light * base)
    # A ring thrown off where it lands, cyan then magenta.
    p.setOpacity(base)
    p.setBrush(Qt.NoBrush)
    for delay, tint in ((0.0, CYAN), (0.07, MAGENTA)):
        k = win(age - delay, 0.0, 0.38)
        if 0 < k < 1:
            r = (14 + 80 * ease_out(k)) * u
            p.setPen(QPen(col(tint, 0.85 * (1 - k) ** 2), (3.2 - 2 * k) * u))
            p.drawEllipse(end, r, r)
    p.restore()


def _arc(p: QPainter, a: QPointF, b: QPointF, seed: int, u: float, light: float, scale: float) -> None:
    points = _bolt_points(a, b, random.Random(seed), 0.25, 4)
    path = polyline(points)
    p.setBrush(Qt.NoBrush)
    for w, color, alpha in ((10, CYAN, 0.25), (3.5, "#9ffcff", 0.7), (1.4, "#ffffff", 1.0)):
        p.setPen(QPen(col(color, alpha * light), w * u * scale, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)


def _shower(
    at: QPointF, aim: float, count: int, u: float, seed: int, width: float, height: float, keep: tuple[QRectF, ...], short: bool
) -> tuple[np.ndarray, ...]:
    """Molten sparks thrown from at, most toward aim (radians), flown once here: under gravity and
    drag, bouncing off the bottom tube and the screen's sides and skittering along. A spark is gone
    once it reaches the names, the title or the gap. Returns (tracks: steps by sparks by x, y; when
    each leaves; how long it lives; when it is gone; its size)."""
    rng = np.random.default_rng(seed)
    embers = count // 6
    n = count + embers
    # Most fast, a few very fast and short-lived, and some slow embers that drift and glow longest.
    speed = np.concatenate([rng.uniform(170, 520, count) * (1 + rng.exponential(0.25, count)), rng.uniform(40, 150, embers)])
    if short:
        speed *= 0.7
    angle = aim + rng.normal(0, 0.7, n)
    vel = np.stack([np.cos(angle), np.sin(angle)], axis=1) * speed[:, None] * u
    pos = np.tile(np.array([at.x(), at.y()], dtype=np.float64), (n, 1)) + rng.normal(0, 3 * u, (n, 2))
    life = np.concatenate([rng.uniform(0.4, 1.05, count), rng.uniform(0.8, 1.15, embers)]) * (1.15 - 0.3 * np.clip(speed / 600, 0, 1))
    if short:
        life *= 0.6
    delay = rng.uniform(0, 0.05, n)
    size = np.concatenate([rng.uniform(0.8, 1.35, count), rng.uniform(0.5, 0.8, embers)])
    bounce = rng.uniform(0.25, 0.55, n)
    floor, left, right = height - 25 * u, 6 * u, width - 6 * u
    gravity, slow = 1500 * u * STEP, math.exp(-2.4 * STEP)
    steps = int(life.max() / STEP) + 3
    track = np.empty((steps, n, 2), dtype=np.float32)
    for k in range(steps):
        track[k] = pos
        vel[:, 1] += gravity
        vel *= slow
        pos += vel * STEP
        low = pos[:, 1] > floor
        if low.any():
            pos[low, 1] = floor - (pos[low, 1] - floor) * bounce[low]
            vel[low, 1] *= -bounce[low]
            vel[low, 0] *= 0.82
        for edge, outside in ((left, pos[:, 0] < left), (right, pos[:, 0] > right)):
            if outside.any():
                pos[outside, 0] = 2 * edge - pos[outside, 0]
                vel[outside, 0] *= -0.4
    gone = life.copy()
    for rect in keep:
        x, y = track[..., 0], track[..., 1]
        inside = (x > rect.left()) & (x < rect.right()) & (y > rect.top()) & (y < rect.bottom())
        first = np.where(inside.any(axis=0), inside.argmax(axis=0) * STEP, np.inf)
        gone = np.minimum(gone, first)
    return track, delay, life, gone, size


def _along(track: np.ndarray, s: np.ndarray, which: np.ndarray) -> np.ndarray:
    k = np.clip(s / STEP, 0, track.shape[0] - 1.001)
    k0 = k.astype(int)
    f = (k - k0)[:, None]
    return track[k0, which] * (1 - f) + track[k0 + 1, which] * f


def _spark_shower(p: QPainter, age: float, shower: tuple, heats: list[tuple], u: float) -> None:
    """Each spark a streak, as far as it flew in SHUTTER: a hot core its whole length, a glow round
    its front half and a glowing head, batched by heat."""
    track, delay, life, gone, size = shower
    if age <= 0 or age > gone.max() + delay.max():
        return
    s = age - delay
    which = np.nonzero((s > 0) & (s < gone))[0]
    if not len(which):
        return
    s = s[which]
    # It cools as it flies; one that reaches the names cools out fast.
    heat = np.clip(np.minimum(1 - s / life[which], (gone[which] - s) / 0.12), 0, 1)
    heads = _along(track, s, which).tolist()
    mids = _along(track, np.maximum(0, s - SHUTTER * 0.45), which).tolist()
    tails = _along(track, np.maximum(0, s - SHUTTER), which).tolist()
    steps = np.minimum((heat * HEATS).astype(int), HEATS - 1).tolist()
    radius = ((1.6 + 3.4 * heat) * size[which] * u).tolist()
    cores: list[list[QLineF]] = [[] for _ in range(HEATS)]
    halos: list[list[QLineF]] = [[] for _ in range(HEATS)]
    for head, mid, tail, step in zip(heads, mids, tails, steps, strict=True):
        cores[step].append(QLineF(tail[0], tail[1], head[0], head[1]))
        halos[step].append(QLineF(mid[0], mid[1], head[0], head[1]))
    p.save()
    base = p.opacity()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    for step in range(HEATS):
        if cores[step]:
            p.setPen(heats[step][1])
            p.drawLines(halos[step])
            p.setPen(heats[step][0])
            p.drawLines(cores[step])
    for head, step, r in zip(heads, steps, radius, strict=True):
        _lay(p, heats[step][2], head[0], head[1], r, base)
    p.restore()


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
