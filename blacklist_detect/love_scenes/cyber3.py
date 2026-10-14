"""赛博 3, 过载回路 Overload circuit: a neon frame fed by glowing circuitry, and two reactors overloading.

The edges deepen to an indigo night, worked out per pixel: violet pooled in the corners with smog
drifting through it and scan lines over it; the names stay clear. A spark runs round the edge of the
screen from the top left and lights two neon tubes behind it, cyan outside and magenta in, cut at the
corners like a HUD; they stutter on as neon does. In the two top corners a reactor powers up: a
housing of turned dark metal, its glowing rings coming on one by one in their channels and spinning
up round a white-hot plasma core. Circuit traces grow out of the reactors along the top and down the
sides, and from the bottom corners both ways, in bundles of parallel lanes bent at 45° as on a board:
the outer lanes plug into the neon frame, the inner ones end in solder pads. Pulses of energy race
along them, from the reactors and the corners into the frame, which flashes where they land; pads
flare as pulses reach them, and arcs jump between pads facing each other across the breaks, spitting
sparks. Then the reactors overcharge: the rings spin faster, the core swells, the light splits into
magenta and cyan, and each reactor discharges lightning twice along its circuits: a white-hot core in
a cyan and violet bloom that lights up its side of the screen, a flash and a ring where it lands and
a shower of molten sparks that bounce off the bottom tube. At the end the reactors spin down and the
neon powers off.

The marks: a pulse of current races round 准备案件还原's edge along a cut-cornered trace, a fainter
magenta one the other way, and they flash where they cross; the badge is a small reactor of spinning
rings that overcharges every few seconds; the card is a dark circuit board with faint glowing traces,
solder pads and a chip on its top edge, a pulse running along its traces now and then, the names in
cyan, a glowing node before each.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
    QRegion,
)

from blacklist_detect.love_scenes.draw import (
    Wash,
    clamp,
    col,
    ease_back,
    ease_in,
    ease_in_out,
    ease_out,
    lengths,
    mix,
    partial,
    point_at,
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
LOOK = {
    "glow": (33, 246, 255),
    "rim": CYAN,
    "band": (MAGENTA, CYAN),
    "card": ("#130e34", "#0a0820"),
    "edge": CYAN,
    "ink": "#6ff9ff",
    "flowers": (("#fff0fb", "#ff7fe6", MAGENTA), ("#effeff", "#7ff9ff", "#14b8d6")),
    "disc": ("#2a0f5c", "#12062e"),
    "heart": ("#ff7fe6", "#d4149f"),
    "deep": "#d4149f",
    "deep_glow": (255, 60, 210),
}
MARKS_ANIMATED = True
# Room above the card for the chip on its top edge; the body's margins leave room for its traces.
CARD_TOP = 7
CARD_PAD = (12, 9, 16, 11)
CARD_FONT = "Bahnschrift"
# Glow pictures are soft: worked out at this share of the stage's size and laid on scaled up.
SOFT = 0.25
# A reactor's rings from the outside in: (radius as a share of the reactor's, what it is, its tint,
# how fast it turns in degrees a second at rest).
RINGS = (
    (0.84, "ticks", CYAN, 14.0),
    (0.66, "arcs", MAGENTA, -46.0),
    (0.52, "dashes", CYAN, 84.0),
    (0.39, "blades", "#bdfbff", -150.0),
)
# A spark cooling as it flies, (heat, color): white hot, gold, orange, then magenta as it dies.
COOLING = ((0.0, MAGENTA), (0.25, "#ff3d6e"), (0.48, "#ff7f26"), (0.7, "#ffc247"), (0.88, "#fff0b0"), (1.0, "#ffffff"))
# Sparks are drawn in this many steps of heat, one batch of lines each.
HEATS = 8
# A spark's track is worked out in steps this long; its streak is how far it flies in SHUTTER, as a
# camera blurs it.
STEP = 1 / 120
SHUTTER = 0.055
# The leader feels its way out of the core this long before a discharge lands.
LEAD = 0.08
# When each reactor (left, right) overcharges, and when it discharges.
CHARGE = ((1.85, 2.4, 3.55, 3.95), (2.15, 2.7, 3.9, 4.25))
DISCHARGES = ((2.45, 3.3), (2.8, 3.65))
# Pictures the marks are drawn from, made once for each size and sharpness.
_MADE: dict[tuple, object] = {}


@dataclass
class _Lane:
    """One trace of a bundle, from where it grows to where it ends: in the frame, or on a pad."""

    points: list[QPointF]
    run: list[float]
    tint: str
    start: float
    grow: float
    plug: bool
    side: int
    bus: int

    def length(self) -> float:
        return self.run[-1]

    def end(self) -> QPointF:
        return self.points[-1]


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(303)
    outer = _frame(width, height, gap, 15 * u, 34 * u, u)
    inner = _frame(width, height, gap, 25 * u, 40 * u, u)
    frame_glow = _frame_glow(width, height, outer, inner, u)
    night = Wash(lambda q, w, h: _night(q, w, h, u))
    flashes = [_flash(width, height, gap, u, side) for side in (-1, 1)]
    radius = 72 * u
    cores = (QPointF(width * 0.085, height * 0.165), QPointF(width * 0.915, height * 0.165))
    lanes = _lanes(width, height, gap, cores, radius, u)
    buses = sorted({(lane.side, lane.bus) for lane in lanes})
    trace_glow = _trace_glow(width, height, lanes, u)
    names = QRectF(width * 0.13, height * 0.29, width * 0.81, height * 0.55)
    title = QRectF(width * 0.38, height * 0.07, width * 0.3, height * 0.18)
    keep = (names, title, gap.adjusted(-30 * u, -30 * u, 30 * u, 30 * u))
    middle = QRectF(width * 0.15, height * 0.31, width * 0.75, height * 0.49).toRect()
    edges = QRegion(0, 0, math.ceil(width), math.ceil(height)) - QRegion(middle)
    # Arcs jump across the break down each side, and from the top bundle's last pad to the frame.
    tab = (QPointF(width * 0.34 + 12 * u, 37 * u), QPointF(width * 0.66 - 12 * u, 37 * u))
    arcs = []
    for when, side, kind in (
        (1.62, -1, 0), (1.86, 1, 0), (2.12, -1, 1), (2.3, 1, 1), (3.02, -1, 0),
        (3.14, 1, 0), (3.52, -1, 1), (3.86, 1, 1), (4.02, -1, 0),
    ):  # fmt: skip
        if kind == 0:
            a = _last_pad(lanes, side, 1)
            b = _last_pad(lanes, side, 2)
        else:
            a, b = _last_pad(lanes, side, 0), tab[0 if side < 0 else 1]
        arcs.append((when, a, b, rnd.randrange(1000)))
    # Discharges: (when, which reactor, where it lands, which way its sparks fly, how many, seed).
    strikes = []
    for side, core in zip((-1, 1), cores, strict=True):
        first, second = DISCHARGES[0 if side < 0 else 1]
        down = _last_pad(lanes, side, 2, inner=False)
        along = _last_pad(lanes, side, 0)
        if side < 0:
            strikes += [(first, core, along, -1.25, 54, 11), (second, core, down, -1.75, 62, 12)]
        else:
            strikes += [(first, core, down, -1.4, 62, 21), (second, core, along, -1.9, 54, 22)]
    bolts: dict[int, list[tuple]] = {}
    showers = {seed: _shower(end, aim, count, u, seed, width, height, keep) for _when, _core, end, aim, count, seed in strikes}
    # Each arc spits a few sparks from both its ends.
    spits = [[_shower(at, -1.57, 12, u, seed * 10 + k, width, height, keep, short=True) for k, at in enumerate((a, b))] for _when, a, b, seed in arcs]
    lights = {name: _dot(color, white) for name, color, white in (("hot", "#bff9ff", 1.0), ("cyan", CYAN, 0.25), ("magenta", MAGENTA, 0.3), ("violet", VIOLET, 0.0))}
    heats = _heats(u)
    pulses = _pulses(lanes, rnd, u)
    spins = [_spin_table(side) for side in (-1, 1)]
    # The sharp parts, drawn once for each sharpness they are shown at.
    baked: dict[float, tuple] = {}

    def bake(scale: float) -> tuple:
        if scale not in baked:
            tubes = [_tube_strips(points, tint, width, height, u, scale) for points, tint in ((outer, CYAN), (inner, MAGENTA))]
            bundles = {key: _bundle(lanes, key, u, scale) for key in buses}
            baked[scale] = (tubes, bundles, _reactor(radius, scale))
        return baked[scale]

    def bolt(seed: int, start: QPointF, end: QPointF) -> list[tuple]:
        if seed not in bolts:
            bolts[seed] = _bolt_shapes(start, end, seed, u, (names, title))
        return bolts[seed]

    def paint(p: QPainter, t: float) -> None:
        tubes, bundles, reactor = bake(_sharpness(p))
        life = win(t, 0.0, 0.3)
        leave = ease_in(win(t, 4.35, 5.0))
        p.save()
        p.setOpacity(life)
        # The night, the flashes, the frame and the traces have nothing in the middle: no time is spent on it.
        p.save()
        p.setClipRegion(edges, Qt.IntersectClip)
        night.paint(p, width, height, gap, ease_out(win(t, 0.0, 0.7)) * (1 - leave))
        bright = max((_strike_light(t - when) for when, *_rest in strikes), default=0.0)
        for side, flash in zip((-1, 1), flashes, strict=True):
            near = max((_strike_light(t - when) * (1.0 if (core.x() < width / 2) == (side < 0) else 0.25) for when, core, *_rest in strikes), default=0.0)
            if near * (1 - leave) > 0.01:
                p.setOpacity(life * near * (1 - leave))
                scaled_up(flash, p, 0, 0, width, height)
        p.setOpacity(life)
        _neon_frame(p, t, outer, inner, frame_glow, tubes, lights, width, height, u, bright)
        _traces(p, t, lanes, buses, bundles, trace_glow, lights, width, height, u, leave)
        p.restore()
        _pulse_lights(p, t, pulses, lanes, lights, u, leave)
        for side, core, spin in zip((-1, 1), cores, spins, strict=True):
            _power(p, t, side, core, radius, reactor, spin, lights, strikes)
        for when, a, b, seed in arcs:
            _jump(p, t - when, a, b, seed, u, lights)
        for when, core, end, _aim, _count, seed in strikes:
            if -LEAD <= t - when <= 0.55:
                _strike(p, t - when, core, end, bolt(seed, core, end), lights, u)
        for when, *_rest, seed in strikes:
            _spark_shower(p, t - when, showers[seed], heats, u)
        for (when, *_rest), pair in zip(arcs, spits, strict=True):
            for shower in pair:
                _spark_shower(p, t - when, shower, heats, u)
        p.restore()
        # One discharge's lightning worked out ahead each frame, so no frame waits long for it.
        for _when, core, end, _aim, _count, seed in strikes:
            if seed not in bolts:
                bolt(seed, core, end)
                break

    return paint


# The frame: two neon tubes round the screen, as in 赛博.


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


# The night at the edges.


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
    through it, pooling to violet round the reactors and plum in the bottom corners, a little neon
    light spilled into it; then scan lines drawn sharp into it."""
    x, y, clear, rim = _field(width, height, u)
    h, w = x.shape
    smog = noise(w, h, 110 * u * SOFT, 3, 31)
    dark = clear * (0.42 + 0.5 * rim) * (0.85 + 0.3 * smog)
    tone = rgb(NIGHT) * rim[..., None] + rgb(INDIGO) * (1 - rim[..., None])
    for cx, cy, reach, tint in (
        (width * 0.08, height * 0.12, 520 * u, "#1d0a4f"),
        (width * 0.92, height * 0.12, 520 * u, "#1d0a4f"),
        (0.0, height, 560 * u, "#33082f"),
        (width, height, 560 * u, "#2a0838"),
    ):
        g = (np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / reach ** 2 * 2.0) * (0.6 + 0.5 * smog) * 0.9)[..., None]
        tone = tone * (1 - g) + rgb(tint) * g
    light = tone * dark[..., None]
    amount = dark.copy()
    # Neon light spilled into the smog: cyan round the reactors, magenta low in the corners.
    for cx, cy, reach, tint, strength in (
        (width * 0.085, height * 0.165, 300 * u, CYAN, 0.1),
        (width * 0.915, height * 0.165, 300 * u, CYAN, 0.1),
        (0.0, height, 380 * u, MAGENTA, 0.12),
        (width, height, 380 * u, MAGENTA, 0.12),
    ):
        g = np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / reach ** 2 * 2.2) * strength * clear * smog * 2
        light += g[..., None] * rgb(tint)
        amount += g
    alpha = np.clip(amount, 0, 0.94)
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(QRectF(0, 0, width, height), picture(light / np.maximum(amount, 1e-4)[..., None], alpha))
    # Scan lines into the night only, as much as it is there: none over the names.
    p.setCompositionMode(QPainter.CompositionMode_SourceAtop)
    p.setPen(QPen(col("#000000", 0.3), 1.3 * u))
    row = 0.0
    while row < height:
        p.drawLine(QPointF(0, row), QPointF(width, row))
        row += 4 * u
    p.restore()


def _flash(width: float, height: float, gap: QRectF, u: float, side: int) -> QImage:
    """The edges of one side (-1 left, 1 right) lit by a discharge, per pixel at a quarter of the
    size: blue-white at the very edge, through cyan to violet; none over the names or the gap."""
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


# The circuit: bundles of traces from the reactors and the bottom corners.


def _buses(width: float, height: float, core: QPointF, radius: float, u: float, top_end: float, bottom_end: float) -> list[tuple]:
    """The left side's three bundles, as (middle line, which side of it the frame is: 1 left of the
    way it runs, -1 right, how many lanes, where along it they start growing both ways or 0): along
    the top from the reactor, down the side from it, and round the bottom corner both ways."""
    cx, cy = core.x(), core.y()
    lane_x = 62 * u
    top = [
        QPointF(cx, cy - 20 * u), QPointF(cx + radius + 36 * u, cy - 20 * u),
        QPointF(cx + radius + 66 * u, cy - 50 * u), QPointF(top_end, cy - 50 * u),
    ]  # fmt: skip
    turn = cy + radius + 28 * u
    down = [QPointF(cx - 22 * u, cy), QPointF(cx - 22 * u, turn), QPointF(lane_x, turn + max(0.0, cx - 22 * u - lane_x)), QPointF(lane_x, height * 0.45)]
    bend = 30 * u
    floor = height - 62 * u
    corner = [
        QPointF(lane_x, height * 0.6), QPointF(lane_x, floor - bend), QPointF(lane_x + bend / 2, floor - bend / 2),
        QPointF(lane_x + bend, floor), QPointF(bottom_end, floor),
    ]  # fmt: skip
    return [(top, 1, 4, 0), (down, -1, 3, 0), (corner, -1, 3, 2)]


def _offset(points: list[QPointF], d: float) -> list[QPointF]:
    """A line beside points, d to the left of the way they run, its bends mitred."""
    normals = []
    for a, b in zip(points, points[1:], strict=False):
        dx, dy = b.x() - a.x(), b.y() - a.y()
        n = math.hypot(dx, dy) or 1
        normals.append((dy / n, -dx / n))
    out = []
    for i, q in enumerate(points):
        near = [normals[j] for j in (i - 1, i) if 0 <= j < len(normals)]
        nx, ny = sum(a for a, _b in near), sum(b for _a, b in near)
        size = math.hypot(nx, ny) or 1
        nx, ny = nx / size, ny / size
        k = d / max(0.3, nx * near[0][0] + ny * near[0][1])
        out.append(QPointF(q.x() + nx * k, q.y() + ny * k))
    return out


def _lanes(width: float, height: float, gap: QRectF, cores: tuple[QPointF, QPointF], radius: float, u: float) -> list[_Lane]:
    """Every trace, both sides: each bundle's lanes beside its middle line, the outer ones ending
    first and turning 45° into the frame, the inner ones running on to a pad."""
    spacing, stagger, frame = 10 * u, 34 * u, 25 * u
    out = []
    for side, core in zip((-1, 1), cores, strict=True):
        if side < 0:
            ends = (width * 0.32, min(width * 0.29, gap.left() - 60 * u))
        else:
            ends = (width * 0.28, width - max(width * 0.71, gap.right() + 60 * u))
        flip = (lambda q: QPointF(width - q.x(), q.y())) if side > 0 else (lambda q: q)
        mirrored = flip(core)
        for bus, (spine, out_side, count, split) in enumerate(_buses(width, height, mirrored, radius, u, *ends)):
            spine = [flip(q) for q in spine]
            out_side = out_side if side < 0 else -out_side
            tint = MAGENTA if split else CYAN
            for i in range(count):
                points = _offset(spine, out_side * ((count - 1) / 2 - i) * spacing)
                halves = [(points[split::-1], -out_side), (points[split:], out_side)] if split else [(points, out_side)]
                for half, (line, way) in enumerate(halves):
                    run = lengths(line)
                    line = partial(line, (run[-1] - (count - 1 - i) * stagger) / run[-1])
                    plug = i < (2 if count > 3 else 1)
                    if plug:
                        line.append(_into_frame(line, way, width, height, frame))
                    start = (0.72 if split else 0.82 + 0.1 * bus) + 0.05 * i + 0.04 * half + (0.1 if side > 0 else 0.0)
                    out.append(_Lane(line, lengths(line), tint, start, 0.75, plug, side, bus * 2 + half))
    return out


def _into_frame(line: list[QPointF], way: int, width: float, height: float, frame: float) -> QPointF:
    """Where a lane ending at line's end meets the frame, turning 45° toward it (way: 1 to its left)."""
    a, b = line[-2], line[-1]
    dx, dy = b.x() - a.x(), b.y() - a.y()
    n = math.hypot(dx, dy) or 1
    dx, dy = dx / n, dy / n
    nx, ny = way * dy, -way * dx
    if abs(ny) > abs(nx):
        reach = b.y() - frame if ny < 0 else height - frame - b.y()
    else:
        reach = b.x() - frame if nx < 0 else width - frame - b.x()
    reach = max(0.0, reach)
    return QPointF(b.x() + (dx + nx) * reach, b.y() + (dy + ny) * reach)


def _last_pad(lanes: list[_Lane], side: int, which: int, inner: bool = True) -> QPointF:
    """The pad at the end of a bundle's innermost lane (or its outermost pad): which 0 the top
    bundle, 1 the one down the side, 2 the corner's up the side."""
    bus = {0: 0, 1: 2, 2: 4}[which]
    found = [lane for lane in lanes if lane.side == side and lane.bus == bus and not lane.plug]
    return (found[-1] if inner else found[0]).end()


def _lane_pens(tint: str, u: float, level: float = 1.0) -> tuple[QPen, QPen]:
    """A trace's two pens: its colored glass, then its pale lit middle."""
    glass = QPen(col(tint, 0.42 * level), 3.4 * u, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin)
    core = QPen(mix(tint, "#ffffff", 0.55, 0.9 * level), 1.2 * u, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin)
    return glass, core


def _pad(p: QPainter, at: QPointF, r: float, tint: str, level: float = 1.0) -> None:
    """A solder pad: a ring of tin lit from the upper left, its hole glowing."""
    tin = QRadialGradient(QPointF(at.x() - r * 0.4, at.y() - r * 0.45), r * 1.6)
    tin.setColorAt(0, col("#f4f2ff", level))
    tin.setColorAt(0.45, col("#a5a1c4", level))
    tin.setColorAt(1, col("#3b3556", level))
    p.setPen(QPen(col("#120c26", 0.8 * level), r * 0.18))
    p.setBrush(tin)
    p.drawEllipse(at, r, r)
    p.setPen(Qt.NoPen)
    p.setBrush(mix(tint, "#ffffff", 0.45, level))
    p.drawEllipse(at, r * 0.45, r * 0.45)


def _bundle(lanes: list[_Lane], key: tuple[int, int], u: float, scale: float) -> tuple[QRectF, QImage]:
    """One bundle fully grown, drawn once: its lanes and pads."""
    mine = [lane for lane in lanes if (lane.side, lane.bus) == key]
    xs = [q.x() for lane in mine for q in lane.points]
    ys = [q.y() for lane in mine for q in lane.points]
    pad = 10 * u
    rect = QRectF(min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad)

    def draw(q: QPainter) -> None:
        for lane in mine:
            path = polyline(lane.points)
            for pen in _lane_pens(lane.tint, u):
                q.setPen(pen)
                q.drawPath(path)
        for lane in mine:
            if not lane.plug:
                _pad(q, lane.end(), 4.4 * u, lane.tint)

    return rect, _baked(rect, scale, draw)


def _trace_glow(width: float, height: float, lanes: list[_Lane], u: float) -> QImage:
    """The light the grown traces throw, per pixel at a quarter of the size, cyan and magenta."""
    w, h = max(1, round(width * SOFT)), max(1, round(height * SOFT))
    light = np.zeros((h, w, 3), dtype=np.float32)
    for tint in (CYAN, MAGENTA):

        def draw(q: QPainter, tint: str = tint) -> None:
            q.scale(SOFT, SOFT)
            q.setPen(QPen(Qt.white, 3 * u, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin))
            for lane in lanes:
                if lane.tint == tint:
                    q.setBrush(Qt.NoBrush)
                    q.drawPath(polyline(lane.points))
                    if not lane.plug:
                        q.setBrush(Qt.white)
                        q.drawEllipse(lane.end(), 5 * u, 5 * u)

        core = mask(w, h, draw)
        halo = blur(core, 1.0) * 0.7 + blur(core, 2.5) * 0.45 + blur(core, 7) * 0.2
        light += halo[..., None] * rgb(tint)
    return glow(light)


def _traces(
    p: QPainter, t: float, lanes: list[_Lane], buses: list, bundles: dict, light: QImage, lights: dict, width: float, height: float, u: float,
    leave: float
) -> None:
    """The traces growing out from where they start, a hot head at each front and a pad flaring on
    as each arrives; grown, a bundle is its picture, and its light comes up."""
    level = 1 - leave
    if level <= 0 or t < min(lane.start for lane in lanes):
        return
    base = p.opacity()
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    on = ease_in_out(win(t, 1.35, 1.9)) * level * (0.85 + 0.15 * math.sin(t * 5.1))
    if on > 0.01:
        p.setOpacity(base * on)
        p.drawImage(QRectF(0, 0, width, height), light)
    p.setOpacity(base * level)
    heads = []
    for key in buses:
        mine = [lane for lane in lanes if (lane.side, lane.bus) == key]
        if all(t >= lane.start + lane.grow for lane in mine):
            rect, image = bundles[key]
            p.drawImage(rect, image)
            continue
        for lane in mine:
            k = ease_out(win(t, lane.start, lane.start + lane.grow))
            if k <= 0:
                continue
            reach = partial(lane.points, k)
            path = polyline(reach)
            p.setBrush(Qt.NoBrush)
            for pen in _lane_pens(lane.tint, u):
                p.setPen(pen)
                p.drawPath(path)
            if k >= 1 and not lane.plug:
                _pad(p, lane.end(), 4.4 * u, lane.tint)
            elif k < 1:
                heads.append((reach[-1], lane.tint, 1 - win(k, 0.85, 1.0)))
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    for at, tint, a in heads:
        _lay(p, lights["magenta" if tint == MAGENTA else "cyan"], at.x(), at.y(), 14 * u, 0.8 * a * base * level)
        _lay(p, lights["hot"], at.x(), at.y(), 5 * u, a * base * level)
    p.restore()


def _pulses(lanes: list[_Lane], rnd: random.Random, u: float) -> list[tuple[int, float, float]]:
    """When pulses run along each lane: (which lane, when it sets off, how long it takes). The
    first follows the lane's growing; they come faster while its reactor overcharges."""
    out = []
    for index, lane in enumerate(lanes):
        side = 0 if lane.side < 0 else 1
        when = lane.start + lane.grow * 0.55 + rnd.uniform(0.05, 0.35)
        while when < 4.25:
            took = lane.length() / (rnd.uniform(560, 760) * u)
            out.append((index, when, max(0.25, took)))
            hot = CHARGE[side][1] - 0.2 <= when <= CHARGE[side][2]
            when += rnd.uniform(0.35, 0.55) if hot else rnd.uniform(0.8, 1.3)
    return out


def _pulse_lights(p: QPainter, t: float, pulses: list, lanes: list[_Lane], lights: dict, u: float, leave: float) -> None:
    """Each pulse a hot head with a tail fading behind it; where it lands the frame or the pad flares."""
    level = 1 - leave
    if level <= 0:
        return
    tails: dict[tuple[str, int], list[QLineF]] = {}
    heads, flares = [], []
    for index, when, took in pulses:
        age = t - when
        if age < 0 or age > took + 0.35:
            continue
        lane = lanes[index]
        if age <= took:
            s = lane.length() * ease_in(age / took) ** 0.6
            reach = 70 * u
            marks = [point_at(lane.points, lane.run, s - reach * k / 6)[0] for k in range(7)]
            for k in range(6):
                tails.setdefault((lane.tint, k), []).append(QLineF(marks[k + 1], marks[k]))
            heads.append((marks[0], lane.tint, min(1.0, s / (30 * u))))
        else:
            flares.append((lane.end(), lane.tint, 1 - (age - took) / 0.35, lane.plug))
    if not heads and not flares:
        return
    base = p.opacity()
    p.save()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    for (tint, k), lines in tails.items():
        fade = 1 - k / 6
        p.setOpacity(base * level)
        p.setPen(QPen(mix(tint, "#ffffff", 0.7 * fade, 0.85 * fade ** 1.4), (1.0 + 1.8 * fade) * u, Qt.SolidLine, Qt.RoundCap))
        p.drawLines(lines)
    for at, tint, a in heads:
        _lay(p, lights["magenta" if tint == MAGENTA else "cyan"], at.x(), at.y(), 18 * u, 0.85 * a * base * level)
        _lay(p, lights["hot"], at.x(), at.y(), 6.5 * u, a * base * level)
    for at, tint, a, plug in flares:
        a = a * a
        _lay(p, lights["magenta" if tint == MAGENTA else "cyan"], at.x(), at.y(), (34 if plug else 22) * u, 0.9 * a * base * level)
        _lay(p, lights["hot"], at.x(), at.y(), (12 if plug else 8) * u, a * base * level)
    p.restore()


# The reactors.


def _spin_table(side: int) -> np.ndarray:
    """How far a reactor has turned by each 1/240 s, in seconds of turning at rest: it spins up as it
    powers on, faster while it overcharges, and down at the end."""
    lag = 0.0 if side < 0 else 0.1
    rise, full, fall, done = CHARGE[0 if side < 0 else 1]
    ts = np.arange(0, DURATION + 0.1, 1 / 240)
    up = np.clip((ts - 0.55 - lag) / 0.9, 0, 1)
    up = up * up * (3 - 2 * up)
    charge = np.clip((ts - rise) / (full - rise), 0, 1) * (1 - np.clip((ts - fall) / (done - fall), 0, 1))
    down = 1 - 0.9 * np.clip((ts - 4.25) / 0.7, 0, 1) ** 2
    return np.cumsum(up * (1 + 2.6 * charge) * down) / 240


def _charge(t: float, side: int) -> float:
    rise, full, fall, done = CHARGE[0 if side < 0 else 1]
    return ease_in_out(win(t, rise, full)) * (1 - ease_in_out(win(t, fall, done)))


def _reactor(radius: float, scale: float) -> dict:
    """A reactor of radius points, drawn at scale pixels to the point and kept: its housing, each
    ring with a magenta and a cyan ghost of it for the chromatic surge, its core and the plasma
    turning in it."""
    key = ("reactor", round(radius, 2), scale)
    if key in _MADE:
        return _MADE[key]
    rings = []
    k = max(0.35, radius * scale / 80)
    for share, kind, tint, speed in RINGS:
        extent = radius * (share + 0.16)
        n = max(8, math.ceil(2 * extent * scale))

        def draw(q: QPainter, kind: str = kind, share: float = share, extent: float = extent, n: int = n) -> None:
            q.scale(n / (2 * extent), n / (2 * extent))
            q.translate(extent, extent)
            _ring_shape(q, kind, share * radius, radius)

        shape = mask(n, n, draw)
        image = bloom(shape, tint, ((0.8 * k, 1.1), (2.4 * k, 0.8), (6 * k, 0.5)), white=0.7)
        ghosts = tuple(bloom(shape, ghost, ((1.2 * k, 1.3),), white=0.0) for ghost in (MAGENTA, CYAN))
        rings.append((extent, image, ghosts, speed))
    made = {"housing": _housing(radius, scale), "rings": rings, **_core(radius, scale)}
    _MADE[key] = made
    return made


def _ring_shape(q: QPainter, kind: str, r: float, size: float) -> None:
    """One of a reactor's rings in white on black round 0, 0, r its radius, size the reactor's."""
    q.setBrush(Qt.NoBrush)
    thin = max(0.7, size * 0.013)
    if kind == "ticks":
        q.setPen(QPen(Qt.white, thin))
        q.drawEllipse(QPointF(0, 0), r, r)
        count = 60 if size > 45 else 36
        for i in range(count):
            a = 2 * math.pi * i / count
            reach = size * (0.075 if i % 5 == 0 else 0.035)
            q.setPen(QPen(QColor(255, 255, 255, 255 if i % 5 == 0 else 150), thin))
            q.drawLine(QPointF(math.cos(a) * r, math.sin(a) * r), QPointF(math.cos(a) * (r - reach), math.sin(a) * (r - reach)))
    elif kind == "arcs":
        q.setPen(QPen(QColor(255, 255, 255, 90), thin))
        q.drawEllipse(QPointF(0, 0), r, r)
        q.setPen(QPen(Qt.white, size * 0.05, Qt.SolidLine, Qt.FlatCap))
        box = QRectF(-r, -r, 2 * r, 2 * r)
        for i in range(3):
            q.drawArc(box, round((i * 120 + 8) * 16), round(78 * 16))
            q.drawArc(box, round((i * 120 + 92) * 16), round(10 * 16))
    elif kind == "dashes":
        q.setPen(QPen(Qt.white, size * 0.04, Qt.SolidLine, Qt.FlatCap))
        box = QRectF(-r, -r, 2 * r, 2 * r)
        for i in range(20):
            q.drawArc(box, round(i * 18 * 16), round(10 * 16))
    else:
        q.setPen(QPen(QColor(255, 255, 255, 110), thin))
        q.drawEllipse(QPointF(0, 0), r, r)
        q.setPen(QPen(Qt.white, size * 0.035, Qt.SolidLine, Qt.RoundCap))
        box = QRectF(-r, -r, 2 * r, 2 * r)
        for i in range(2):
            q.drawArc(box, round((i * 180 + 20) * 16), round(50 * 16))


def _housing(radius: float, scale: float) -> QImage:
    """The reactor's housing per pixel: dark turned metal, its fine concentric grain catching the
    light in two opposite wedges, a bevelled rim lit from the upper left with six screws in it, a
    dark channel for each ring with the ring's color glowing in it, a deep well for the core, and a
    soft shadow round it."""
    extent = radius * 1.14
    n = max(8, math.ceil(2 * extent * scale))
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    x = (xs + 0.5) / n * 2 * extent - extent
    y = (ys + 0.5) / n * 2 * extent - extent
    r = np.hypot(x, y)
    a = np.arctan2(y, x)
    px = 1 / scale
    R = radius  # noqa: N806
    disc = smooth(R + 0.7 * px, R - 0.7 * px, r)
    rng = np.random.default_rng(7)
    grain = np.interp(r * scale * 1.3, np.arange(int(R * scale * 1.6) + 4), rng.random(int(R * scale * 1.6) + 4)).astype(np.float32)
    wedge = (0.5 + 0.5 * np.cos(2 * (a + 0.75))) ** 6
    metal = 0.05 + 0.3 * wedge + 0.07 * (grain - 0.5) * (0.3 + wedge)
    color = rgb("#05040c") * (1 - metal)[..., None] + rgb("#9c98c8") * metal[..., None]
    # The rim: a bevel from 0.9 to 0.985 of the way out, bright where it faces the upper left.
    bevel = smooth(0.895 * R, 0.91 * R, r) * smooth(0.99 * R, 0.975 * R, r)
    facing = np.clip(np.cos(a + 2.36), -1, 1)
    rim_light = np.clip(0.06 + 0.8 * np.clip(facing, 0, 1) ** 2.2 + 0.35 * wedge, 0, 1)
    rim = rgb("#0c0a1a") * (1 - rim_light)[..., None] + rgb("#e4e2fa") * rim_light[..., None]
    color = color * (1 - bevel)[..., None] + rim * bevel[..., None]
    lip = np.exp(-(((r - 0.988 * R) / (0.6 * px + 0.004 * R)) ** 2)) * np.clip(0.2 + 0.7 * facing, 0, 1)
    groove = np.exp(-(((r - 0.893 * R) / (0.6 * px + 0.006 * R)) ** 2))
    color = color * (1 - 0.7 * groove)[..., None] + lip[..., None] * rgb("#f2f0ff") * 0.6
    for i in range(6):
        sa = math.pi / 6 + i * math.pi / 3
        sx, sy = math.cos(sa) * 0.943 * R, math.sin(sa) * 0.943 * R
        d = np.hypot(x - sx, y - sy)
        head = smooth(0.028 * R + px, 0.028 * R - px * 0.5, d)
        shine = np.clip(0.4 - ((x - sx) + (y - sy)) / (0.05 * R), 0, 1)
        color = color * (1 - head)[..., None] + (rgb("#3a3658") + rgb("#b8b5d8") * shine[..., None]) * head[..., None]
    # Channels the rings sit in: dark, lit by their ring's color.
    for share, _kind, tint, _speed in RINGS:
        channel = np.exp(-(((r - share * R) / (0.045 * R)) ** 2))
        spill = np.exp(-(((r - share * R) / (0.09 * R)) ** 2))
        color = color * (1 - 0.82 * channel)[..., None] + spill[..., None] * rgb(tint) * 0.12
    # The well the core burns in.
    well = smooth(0.33 * R, 0.29 * R, r)
    color = color * (1 - 0.9 * well)[..., None] + well[..., None] * rgb("#1a0b3d") * 0.6
    edge = np.exp(-(((r - 0.33 * R) / (0.6 * px + 0.008 * R)) ** 2)) * (0.3 + 0.35 * facing)
    color += edge[..., None] * rgb("#cfd0f5") * 0.5
    shadow = (1 - smooth(R, extent, r)) ** 1.6 * 0.6
    alpha = disc + (1 - disc) * shadow
    color = color * (disc / np.maximum(alpha, 1e-4))[..., None]
    return picture(color, alpha)


def _core(radius: float, scale: float) -> dict:
    """The core: a white-hot middle in a cyan glow edged with magenta, and plasma filaments to turn
    over it, per pixel."""
    out = {}
    extent = radius * 0.5
    n = max(8, math.ceil(2 * extent * scale))
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    x = (xs + 0.5) / n * 2 * extent - extent
    y = (ys + 0.5) / n * 2 * extent - extent
    r = np.hypot(x, y) / radius
    fade = smooth(0.5, 0.42, r)[..., None]
    light = (
        np.exp(-((r / 0.1) ** 2))[..., None] * rgb("#ffffff") * 2.2
        + np.exp(-((r / 0.2) ** 2))[..., None] * rgb(CYAN) * 1.2
        + np.exp(-(((r - 0.26) / 0.07) ** 2))[..., None] * rgb(MAGENTA) * 0.45
        + np.exp(-r / 0.12)[..., None] * rgb(VIOLET) * 0.3
    ) * fade
    out["core"] = (extent, glow(light.astype(np.float32)))
    field = noise(n, n, max(3.0, 0.16 * radius * scale), 3, 5)
    ridges = (1 - np.abs(2 * field - 1)) ** 6
    a = np.arctan2(y, x)
    swirl = 0.5 + 0.5 * np.sin(a * 3 + r * 18)
    band = np.exp(-(((r - 0.2) / 0.09) ** 2))
    plasma = ridges * (0.6 + 0.4 * swirl) * band * 1.6
    tint = rgb("#bffcff") * (1 - 0.45 * swirl)[..., None] + rgb("#ff8ff0") * (0.45 * swirl)[..., None]
    out["plasma"] = (extent, glow((plasma[..., None] * tint).astype(np.float32)))
    return out


def _spun(p: QPainter, image: QImage, at: QPointF, extent: float, angle: float, grow: float = 1.0) -> None:
    """A square picture extent points from its middle to its side, laid on round at, turned by angle degrees."""
    p.save()
    p.translate(at)
    p.rotate(angle)
    e = extent * grow
    p.drawImage(QRectF(-e, -e, 2 * e, 2 * e), image)
    p.restore()


def _reactor_paint(
    p: QPainter, parts: dict, at: QPointF, turned: float, rings_on: list[float], housing: float, core: float, surge: float,
    glitch: int, u: float
) -> None:
    """A reactor at at: its housing, its rings turned by turned seconds' worth each at its own speed
    and as lit as rings_on says, its core as big and bright as core says; surging, its light splits
    into magenta and cyan ghosts pushed apart."""
    base = p.opacity()
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    if housing > 0:
        p.setOpacity(base * housing)
        side = _extent_of(parts) * 1.14
        p.drawImage(QRectF(at.x() - side, at.y() - side, 2 * side, 2 * side), parts["housing"])
    shift = (2 + 7 * surge) * u if surge > 0.03 else 0.0
    # At the height of a surge, as a discharge leaves, the rings jolt sideways.
    jolt = random.Random(glitch).uniform(-1, 1) * 5 * u * (surge - 0.6) if surge > 0.6 else 0.0
    for (extent, image, ghosts, speed), on in zip(parts["rings"], rings_on, strict=True):
        if on <= 0.01:
            continue
        angle = speed * turned
        p.setOpacity(base * on * (1 - 0.35 * surge))
        _spun(p, image, QPointF(at.x() + jolt, at.y()), extent, angle)
        if shift:
            p.setCompositionMode(QPainter.CompositionMode_Plus)
            p.setOpacity(base * on * min(1.0, 0.25 + 0.75 * surge))
            _spun(p, ghosts[0], QPointF(at.x() - shift + jolt, at.y()), extent, angle - 2 * surge)
            _spun(p, ghosts[1], QPointF(at.x() + shift + jolt, at.y()), extent, angle + 2 * surge)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    if core > 0.01:
        extent, image = parts["core"]
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        p.setOpacity(base * min(1.0, core))
        _spun(p, image, at, extent, 0.0, 0.75 + 0.25 * core)
        extent, image = parts["plasma"]
        p.setOpacity(base * min(1.0, core) * 0.9)
        _spun(p, image, at, extent, -turned * 260, 0.8 + 0.2 * core)
        _spun(p, image, at, extent, turned * 170 + 40, 0.7 + 0.2 * core)
        if core > 1:
            extent, image = parts["core"]
            p.setOpacity(base * min(1.0, core - 1))
            _spun(p, image, at, extent, 0.0, 1.0 + 0.3 * (core - 1))
    p.restore()


def _extent_of(parts: dict) -> float:
    """The reactor's radius, from its outer ring's picture."""
    extent = parts["rings"][0][0]
    return extent / (RINGS[0][0] + 0.16)


def _power(p: QPainter, t: float, side: int, at: QPointF, radius: float, parts: dict, spin: np.ndarray, lights: dict, strikes: list) -> None:
    """A reactor powering on, overcharging with its chromatic surge, and spinning down at the end."""
    lag = 0.0 if side < 0 else 0.12
    housing = ease_out(win(t, 0.4 + lag, 0.75 + lag)) * (1 - ease_in(win(t, 4.45, 5.0)))
    if housing <= 0:
        return
    u = radius / 72
    rings_on = [_neon(t, 0.62 + lag + 0.09 * i, 5 + i + (4 if side > 0 else 0)) * _power_down(t, i + (2 if side > 0 else 0)) for i in range(len(RINGS))]
    charge = _charge(t, side)
    struck = max((_strike_light(t - when) for when, core, *_rest in strikes if abs(core.x() - at.x()) < 1), default=0.0)
    flicker = 0.5 + 0.5 * math.sin(t * 17 + side) * math.sin(t * 7.3)
    surge = clamp(charge * (0.25 + 0.35 * flicker) + struck)
    ignite = ease_back(win(t, 0.98 + lag, 1.3 + lag)) * _power_down(t, 5)
    core = ignite * (1 + 0.08 * math.sin(t * 9)) + 0.45 * charge + 0.8 * struck
    turned = float(spin[min(len(spin) - 1, int(t * 240))])
    p.save()
    base = p.opacity()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    # Its light on what is round it, brighter as it charges.
    _lay(p, lights["violet"], at.x(), at.y(), radius * 2.6, (0.35 + 0.4 * charge + 0.5 * struck) * ignite * base)
    _lay(p, lights["cyan"], at.x(), at.y(), radius * 1.7, (0.18 + 0.3 * charge + 0.4 * struck) * ignite * base)
    p.restore()
    grow = 0.9 + 0.1 * ease_out(win(t, 0.4 + lag, 0.8 + lag))
    p.save()
    p.translate(at)
    p.scale(grow, grow)
    p.translate(-at.x(), -at.y())
    _reactor_paint(p, parts, at, turned, rings_on, housing, core, surge, int(t * 30), u)
    p.restore()
    if ignite > 0 and t < 1.6 + lag:
        # The core catching: a flash and a glint.
        flash = math.sin(math.pi * win(t, 0.98 + lag, 1.35 + lag))
        p.save()
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        _lay(p, lights["hot"], at.x(), at.y(), radius * 0.9, flash * base)
        p.restore()
        star(p, at.x(), at.y(), radius * 0.9 * flash, "#ffffff", 0.8 * flash, 0.06)


# Lightning, as in 赛博, thrown by the reactors.


def _strike_light(age: float) -> float:
    """How bright a discharge is, age seconds after it: a flash, a dip, a second flash, then gone."""
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
    """A discharge's two shapes, the flash and the restrike down the same channel with new branches:
    (main line, branches, the box its light covers, that light, its points). Channel and branches
    keep out of the names and the title: one that strays into them is drawn again."""

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
                b = branch[len(branch) // 2]
                bend = angle + rnd.choice((-1, 1)) * rnd.uniform(0.4, 0.9)
                twig = _bolt_points(b, QPointF(b.x() + math.cos(bend) * reach * 0.4, b.y() + math.sin(bend) * reach * 0.4), rnd, 0.15, 3)
                if clear(twig):
                    branches.append(twig)
            if len(branches) >= 5:
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
    h, w = core.shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    edge = np.minimum(np.minimum(xs, w - 1 - xs), np.minimum(ys, h - 1 - ys))
    light *= smooth(0, pad * k, edge)[..., None]
    return box, glow(light)


def _strike(p: QPainter, age: float, start: QPointF, end: QPointF, shapes: list[tuple], lights: dict, u: float) -> None:
    """A leader feeling its way out of the core, then the discharge: its light, its white core, a
    flash and a ring where it lands."""
    if age < -LEAD or age > 0.55:
        return
    p.save()
    base = p.opacity()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    if age < 0:
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
        _lay(p, lights["violet"], end.x(), end.y(), 190 * u, 0.5 * light * base)
        _lay(p, lights["cyan"], end.x(), end.y(), 110 * u, 0.8 * light * base)
        _lay(p, lights["hot"], end.x(), end.y(), 40 * u, light * base)
    p.setOpacity(base)
    p.setBrush(Qt.NoBrush)
    for delay, tint in ((0.0, CYAN), (0.07, MAGENTA)):
        k = win(age - delay, 0.0, 0.38)
        if 0 < k < 1:
            r = (10 + 52 * ease_out(k)) * u
            p.setPen(QPen(col(tint, 0.85 * (1 - k) ** 2), (3.2 - 2 * k) * u))
            p.drawEllipse(end, r, r)
    p.restore()


def _jump(p: QPainter, age: float, a: QPointF, b: QPointF, seed: int, u: float, lights: dict) -> None:
    """An arc jumping between two pads for a moment, crackling into a new shape every other frame,
    both ends flaring."""
    if age < 0 or age > 0.26:
        return
    light = (1 - age / 0.26) ** 0.7 * (0.75 + 0.25 * math.sin(age * 90))
    points = _bolt_points(a, b, random.Random(seed + int(age * 15)), 0.2, 4)
    path = polyline(points)
    base = p.opacity()
    p.save()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setBrush(Qt.NoBrush)
    for w, color, alpha in ((11, VIOLET, 0.25), (5, CYAN, 0.45), (2.2, "#a5fbff", 0.8), (1.1, "#ffffff", 1.0)):
        p.setPen(QPen(col(color, alpha * light), w * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
    for at in (a, b):
        _lay(p, lights["cyan"], at.x(), at.y(), 30 * u, 0.8 * light * base)
        _lay(p, lights["hot"], at.x(), at.y(), 10 * u, light * base)
    p.restore()


# Molten sparks, as in 赛博.


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
    p.setOpacity(clamp(alpha))
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


def _shower(
    at: QPointF, aim: float, count: int, u: float, seed: int, width: float, height: float, keep: tuple[QRectF, ...], short: bool = False
) -> tuple[np.ndarray, ...]:
    """Molten sparks thrown from at, most toward aim (radians), flown once here: under gravity and
    drag, bouncing off the bottom tube and the screen's sides and skittering along. A spark is gone
    once it reaches the names, the title or the gap. Returns (tracks: steps by sparks by x, y; when
    each leaves; how long it lives; when it is gone; its size)."""
    rng = np.random.default_rng(seed)
    embers = count // 6
    n = count + embers
    speed = np.concatenate([rng.uniform(170, 520, count) * (1 + rng.exponential(0.25, count)), rng.uniform(40, 150, embers)])
    if short:
        speed *= 0.55
    angle = aim + rng.normal(0, 0.7, n)
    vel = np.stack([np.cos(angle), np.sin(angle)], axis=1) * speed[:, None] * u
    pos = np.tile(np.array([at.x(), at.y()], dtype=np.float64), (n, 1)) + rng.normal(0, 3 * u, (n, 2))
    life = np.concatenate([rng.uniform(0.4, 1.05, count), rng.uniform(0.8, 1.15, embers)]) * (1.15 - 0.3 * np.clip(speed / 600, 0, 1))
    if short:
        life *= 0.55
    delay = rng.uniform(0, 0.05, n)
    size = np.concatenate([rng.uniform(0.8, 1.35, count), rng.uniform(0.5, 0.8, embers)]) * (0.8 if short else 1.0)
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


# The marks.


def _glows() -> dict[str, QImage]:
    """The round glows the marks lay on, made once."""
    if "glows" not in _MADE:
        _MADE["glows"] = {"hot": _dot("#bff9ff", 1.0), "cyan": _dot(CYAN, 0.25), "magenta": _dot(MAGENTA, 0.3)}
    return _MADE["glows"]


def _cut_rect(rect: QRectF, cut: float, small: float) -> list[QPointF]:
    """A rectangle's outline from the middle of its top, round clockwise and back, its top-left and
    bottom-right corners cut by cut and the other two by small."""
    x0, y0, x1, y1 = rect.left(), rect.top(), rect.right(), rect.bottom()
    return [
        QPointF((x0 + x1) / 2, y0), QPointF(x1 - small, y0), QPointF(x1, y0 + small), QPointF(x1, y1 - cut), QPointF(x1 - cut, y1),
        QPointF(x0 + small, y1), QPointF(x0, y1 - small), QPointF(x0, y0 + cut), QPointF(x0 + cut, y0), QPointF((x0 + x1) / 2, y0),
    ]  # fmt: skip


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    """A cut-cornered trace round the button, dim, with a pad at each cut corner: a cyan pulse races
    round it clockwise and a fainter magenta one the other way, flashing where they cross."""
    scale = _sharpness(p)
    u = cover.height() / 80
    edge = cover.adjusted(-1.5 * u, -1.5 * u, 1.5 * u, 1.5 * u)
    points = _cut_rect(edge, 12 * u, 6 * u)
    key = ("ring", round(cover.width(), 1), round(cover.height(), 1), scale)
    if key not in _MADE:
        window = cover.adjusted(-9, -9, 9, 9)
        _MADE[key] = (window, _ring_base(window, points, u, scale), lengths(points))
    window, image, run = _MADE[key]
    p.drawImage(window, image)
    total = run[-1]
    lights = _glows()
    lap = 1.5
    heads = [((t / lap) % 1.0, 1, CYAN, 1.0), ((0.5 - t / (lap * 1.3)) % 1.0, -1, MAGENTA, 0.7)]
    p.save()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    for k, way, tint, strength in heads:
        s = k * total
        tail = total * (0.3 if way > 0 else 0.2)
        marks = [point_at(points, run, (s - way * tail * i / 14) % total)[0] for i in range(15)]
        for i in range(14):
            fade = 1 - i / 14
            p.setPen(QPen(col(tint, 0.4 * strength * fade), (4 + 5 * fade) * u, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(marks[i + 1], marks[i])
            p.setPen(QPen(mix(tint, "#ffffff", 0.75 * fade ** 2, strength * fade ** 1.6), (1.2 + 1.6 * fade) * u, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(marks[i + 1], marks[i])
        head = marks[0]
        _lay(p, lights["cyan" if tint == CYAN else "magenta"], head.x(), head.y(), 9, strength)
        _lay(p, lights["hot"], head.x(), head.y(), 4.2 * u, strength)
    # Where the two meet, a flash: they cross twice a lap.
    a, b = heads[0][0] * total, heads[1][0] * total
    apart = min(abs(a - b), total - abs(a - b))
    if apart < 40 * u:
        flash = (1 - apart / (40 * u)) ** 2
        at = point_at(points, run, a)[0]
        _lay(p, lights["hot"], at.x(), at.y(), 8.5, flash)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        star(p, at.x(), at.y(), 8.5 * flash, "#ffffff", flash, 0.08)
    p.restore()


def _ring_base(window: QRectF, points: list[QPointF], u: float, scale: float) -> QImage:
    """The ring's trace, drawn once: a soft cyan light round it per pixel, the trace's glass and
    core, and a pad at each corner."""
    w, h = max(1, math.ceil(window.width() * scale)), max(1, math.ceil(window.height() * scale))
    path = polyline(points)

    def draw(q: QPainter) -> None:
        q.scale(scale, scale)
        q.translate(-window.left(), -window.top())
        q.setPen(QPen(Qt.white, 2.2 * u, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin))
        q.drawPath(path)

    shape = mask(w, h, draw)
    light = bloom(shape, CYAN, ((1.5 * scale, 0.5), (4 * scale, 0.45)), white=0.0)

    def sharp(q: QPainter) -> None:
        q.drawImage(window, light)
        q.setPen(QPen(col(VIOLET, 0.55), 3.6 * u, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin))
        q.drawPath(path)
        q.setPen(QPen(mix(CYAN, "#ffffff", 0.3, 0.75), 1.2 * u, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin))
        q.drawPath(path)
        for i in (2, 4, 6, 8):
            a, b = points[i - 1], points[i]
            _pad(q, QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2), 2.8 * u, CYAN)

    return _baked(window, scale, sharp)


def badge(p: QPainter, box: QRectF, t: float) -> None:
    """A small reactor: its rings spinning round a white-hot core, overcharging every few seconds
    with a chromatic surge, the rings racing."""
    scale = _sharpness(p)
    radius = box.width() / 2
    parts = _reactor(radius, scale)
    cycle, at = 3.4, t % 3.4
    surge = math.sin(math.pi * win(at, 2.5, 3.1)) ** 2
    # Turning: steady, and faster through each surge (its integral, so the rings never jump).
    swell = lambda x: x / 2 - math.sin(2 * math.pi * x) / (4 * math.pi)  # noqa: E731
    turned = t + 2.4 * 0.6 * (math.floor(t / cycle) * 0.5 + swell(win(at, 2.5, 3.1)))
    rings_on = [min(1.0, 0.35 + _neon(t, 0.05 * i, i)) if t < 0.5 else 1.0 for i in range(len(RINGS))]
    core = 0.92 + 0.08 * math.sin(t * 6) + 0.5 * surge
    p.save()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    lights = _glows()
    _lay(p, lights["cyan"], box.center().x(), box.center().y(), radius * 1.3, 0.3 + 0.4 * surge)
    p.restore()
    _reactor_paint(p, parts, box.center(), turned, rings_on, 1.0, core, surge * 0.6, int(t * 30), radius / 68)


def _board(rect: QRectF, scale: float) -> tuple[QImage, list[list[QPointF]]]:
    """The card as a circuit board, per pixel: dark violet soldermask over a fine glass weave with a
    gloss across its top, faint glowing traces with tin pads, a cyan edge cut at the corners with its
    light inside, and a chip on the top edge. Returns the picture and the traces a pulse runs along."""
    body = rect.adjusted(0.5, CARD_TOP + 0.5, -0.5, -0.5)
    u = 1.0
    outline = _cut_rect(body, 9 * u, 4 * u)
    w, h = max(1, math.ceil(rect.width() * scale)), max(1, math.ceil(rect.height() * scale))
    chip = QRectF(body.center().x() - 17 * u, body.top() - 5 * u, 34 * u, 10 * u)
    left, right, top, bottom = body.left(), body.right(), body.top(), body.bottom()
    traces = [
        [QPointF(left + 7, bottom - 6), QPointF(right - 26, bottom - 6), QPointF(right - 8, bottom - 24), QPointF(right - 8, top + 15)],
        [QPointF(chip.left() - 1, top + 3.5), QPointF(left + 20, top + 3.5), QPointF(left + 6, top + 17.5), QPointF(left + 6, bottom - 20)],
        [QPointF(chip.right() + 1, top + 3.5), QPointF(right - 22, top + 3.5), QPointF(right - 14, top + 11.5)],
    ]
    ends = [traces[0][0], traces[0][-1], traces[1][-1], traces[2][-1]]

    def at_scale(draw):  # noqa: ANN001, ANN202
        def inner(q: QPainter) -> None:
            q.scale(scale, scale)
            q.translate(-rect.left(), -rect.top())
            draw(q)

        return inner

    def fill(q: QPainter) -> None:
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawPolygon(QPolygonF(outline))

    def lines(q: QPainter) -> None:
        q.setPen(QPen(Qt.white, 1.2 * u, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin))
        for trace in traces:
            q.drawPath(polyline(trace))

    def border(q: QPainter) -> None:
        q.setPen(QPen(Qt.white, 1.2 * u, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin))
        q.drawPath(polyline(outline))

    inside = mask(w, h, at_scale(fill))
    trace = mask(w, h, at_scale(lines)) * inside
    edge = mask(w, h, at_scale(border))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    x, y = xs / scale, ys / scale
    depth = np.clip((y - top) / max(1.0, bottom - top), 0, 1)
    color = rgb("#160f3a") * (1 - depth)[..., None] + rgb("#0a0820") * depth[..., None]
    weave = np.sin((x + y) * 2.1) * np.sin((x - y) * 2.1)
    grain = noise(w, h, max(2.0, 3 * scale), 2, 13) - 0.5
    color = color * (1 + 0.1 * weave + 0.25 * grain)[..., None]
    gloss = np.exp(-(((y - top) - 0.35 * (x - left) * 0.25 - 4) / 9) ** 2) * 0.07
    color += gloss[..., None] * rgb("#c9c3ff")
    lit = blur(trace, 1.6 * scale) * 0.55 + blur(trace, 4 * scale) * 0.35
    color += (lit[..., None] * rgb(CYAN) + (trace * 0.5)[..., None] * rgb("#7ff9ff")) * 0.55
    halo = blur(edge, 3 * scale) * inside
    color += halo[..., None] * rgb(CYAN) * 0.5 + (edge * 0.9)[..., None] * rgb("#a8fcff")
    alpha = np.clip(inside + edge * 0.9, 0, 1)
    board = picture(color, alpha)

    def finish(q: QPainter) -> None:
        q.drawImage(rect, board)
        for end in ends:
            _pad(q, end, 2.4 * u, CYAN, 0.9)
        _chip(q, chip, u)

    return _baked(rect, scale, finish), traces


def _chip(q: QPainter, chip: QRectF, u: float) -> None:
    """A little chip on the card's top edge: silver legs, a black body with a sheen, its pin-one dot."""
    q.setPen(Qt.NoPen)
    legs = QLinearGradient(chip.topLeft(), chip.bottomLeft())
    legs.setColorAt(0, col("#e8e6f8"))
    legs.setColorAt(1, col("#6e6a90"))
    q.setBrush(legs)
    for i in range(6):
        x = chip.left() + 4 * u + i * (chip.width() - 8 * u) / 5
        q.drawRect(QRectF(x - 1 * u, chip.top() - 2 * u, 2 * u, chip.height() + 4 * u))
    shell = QLinearGradient(chip.topLeft(), chip.bottomRight())
    shell.setColorAt(0, col("#3a3554"))
    shell.setColorAt(0.45, col("#15122a"))
    shell.setColorAt(1, col("#07060f"))
    q.setPen(QPen(col("#4a4470"), 0.8 * u))
    q.setBrush(shell)
    q.drawRoundedRect(chip, 1.5 * u, 1.5 * u)
    q.setPen(Qt.NoPen)
    q.setBrush(col("#57517a"))
    q.drawEllipse(QPointF(chip.left() + 3.5 * u, chip.bottom() - 3 * u), 1.1 * u, 1.1 * u)


def card(p: QPainter, rect: QRectF, t: float) -> None:
    """The circuit board under the names, a light blinking on its chip, and now and then a pulse of
    current running along its traces."""
    scale = _sharpness(p)
    key = ("card", round(rect.width(), 1), round(rect.height(), 1), scale)
    if key not in _MADE:
        _MADE[key] = _board(rect, scale)
    image, traces = _MADE[key]
    p.drawImage(rect, image)
    lights = _glows()
    body = rect.adjusted(0, CARD_TOP, 0, 0)
    led = QPointF(body.center().x() + 11, body.top())
    blink = 0.55 + 0.45 * (math.sin(t * 5) > -0.3)
    p.save()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    _lay(p, lights["magenta"], led.x(), led.y(), 6, blink)
    _lay(p, lights["hot"], led.x(), led.y(), 1.8, blink)
    for index, (offset, took) in enumerate(((0.3, 0.95), (1.5, 0.6))):
        age = (t - offset) % 2.8
        if age > took + 0.25:
            continue
        points = traces[index]
        run = lengths(points)
        if age <= took:
            s = run[-1] * ease_in_out(age / took)
            marks = [point_at(points, run, max(0.0, s - 26 * i / 8))[0] for i in range(9)]
            for i in range(8):
                fade = 1 - i / 8
                p.setOpacity(1.0)
                p.setPen(QPen(mix(CYAN, "#ffffff", 0.7 * fade, fade ** 1.5), 0.8 + 1.4 * fade, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(marks[i + 1], marks[i])
            _lay(p, lights["cyan"], marks[0].x(), marks[0].y(), 7, 0.9)
            _lay(p, lights["hot"], marks[0].x(), marks[0].y(), 2.4, 1.0)
        else:
            end = points[-1]
            fade = 1 - (age - took) / 0.25
            _lay(p, lights["cyan"], end.x(), end.y(), 8, fade)
            _lay(p, lights["hot"], end.x(), end.y(), 3, fade)
    p.restore()


def lead(size: float, index: int) -> QPixmap:
    """A glowing node before each name, per pixel: a ring of tin lit from the upper left round a
    magenta light burning in its hole, the light spilling round it."""
    ratio = 3.0
    n = max(4, round(size * ratio))
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    x = (xs + 0.5) / n - 0.5
    y = (ys + 0.5) / n - 0.5
    r = np.hypot(x, y)
    a = np.arctan2(y, x)
    px = 1 / n
    ring_mask = smooth(0.13 - px, 0.13 + px, r) * smooth(0.27 + px, 0.27 - px, r)
    facing = np.cos(a + 2.36)
    tin = 0.45 + 0.35 * facing + 0.2 * np.cos(2 * (a + 0.75)) ** 8
    metal = rgb("#2e2a4a") * (1 - tin)[..., None] + rgb("#f1efff") * tin[..., None]
    tint = MAGENTA if index % 2 == 0 else CYAN
    heart = np.exp(-((r / 0.075) ** 2))
    halo = np.exp(-((r / 0.2) ** 2)) * 0.55 + np.exp(-r / 0.09) * 0.35
    light = heart[..., None] * rgb("#ffffff") * 1.4 + halo[..., None] * rgb(tint)
    light *= smooth(0.5, 0.4, r)[..., None]
    # The light laid under the tin: as opaque as it is bright, as glow does.
    shine = np.clip(light, 0, 1)
    alpha = ring_mask + shine.max(axis=-1) * (1 - ring_mask)
    lit = metal * ring_mask[..., None] + shine * (1 - ring_mask)[..., None]
    image = picture(lit / np.maximum(alpha, 1e-4)[..., None], alpha)
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(ratio)
    return pixmap
