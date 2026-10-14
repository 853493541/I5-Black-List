"""霓虹都市: a rain-soaked skyline at night, under a lightning storm.

The edges deepen to a violet night, worked out per pixel: storm clouds along the top, and the city's
glow hanging in the smog over the two bottom corners. There the skyline rises, tower by tower, the
far ones hazy and the near ones black against the glow: shaded per pixel, rimmed in cyan or magenta
by the neon, their windows lighting up floor by floor, red lights blinking on their spires, a glowing
street haze round their feet, and two searchlights behind them slowly sweeping the clouds.
Holographic billboards of made-up glyphs flicker on: a sign on a roof each side, a screen with a
turning ring on the left tower, a ticker running across the right one. Rain streaks fall over it
all, tinted by the neon, faint over the names, none in the gap. Flying cars cross the top
band above the title and leave long light trails. A spark runs round the screen and lights the
two-tube HUD frame, cyan outside and magenta in, which stutters on as neon does. Lightning feels its
way down onto the spires and the frame: the clouds flash, the skyline stands black against the
light, the rain glints, the struck tower's screen glitches, molten sparks shower off the spire and
arcs crawl over it. At the end the neon powers down.

Its marks are the city's own signs, moving (MARKS_ANIMATED): the button ringed by one magenta neon
tube on clips, its two ends in electrodes, that stutters on and now and then flickers; a cyan neon
star on a dark sign plate; the card a wet glass billboard, raindrops beaded on it and now and then
one running down, edged by a magenta tube that flickers on, a small plate with a cyan diamond on its
top edge, and a cyan neon diamond before each name.
"""

from __future__ import annotations

import math
import random
import time
from typing import TYPE_CHECKING, NamedTuple

import numpy as np
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

from blacklist_detect.love_scenes.draw import (
    Wash,
    catmull,
    clamp,
    col,
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
from blacklist_detect.love_scenes.light import blur, glow, mask, noise, picture, rgb, scaled_up, smooth

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
CYAN = "#21f6ff"
MAGENTA = "#ff2bd6"
VIOLET = "#7a2cff"
NIGHT = "#07021a"
INDIGO = "#12062e"
LOOK = {
    "glow": (255, 43, 214),
    "rim": MAGENTA,
    "band": (MAGENTA, CYAN),
    "card": ("#1b0d3f", "#0a0620"),
    "edge": MAGENTA,
    "ink": "#f4fbff",
    "flowers": (("#effeff", "#7ff9ff", CYAN), ("#fff0fb", "#ff7fe6", MAGENTA)),
    "disc": ("#1d0f42", "#0a0620"),
    "heart": ("#7ff9ff", "#14b8d6"),
    "deep": "#d4149f",
    "deep_glow": (255, 43, 214),
}
MARKS_ANIMATED = True
# Room above the card for the little plate on its top edge.
CARD_TOP = 8
# Room inside the card's neon tube for the names.
CARD_PAD = (15, 10, 15, 10)
# Glow pictures that are soft anyway are worked out at this share of the stage's size.
SOFT = 0.25
# The frame's light reaches this far in from the screen's edges, in points at the design size.
GLOW_BAND = 140
# A spark cooling as it flies, (heat, color): white hot, gold, orange, then magenta as it dies.
COOLING = ((0.0, MAGENTA), (0.25, "#ff3d6e"), (0.48, "#ff7f26"), (0.7, "#ffc247"), (0.88, "#fff0b0"), (1.0, "#ffffff"))
HEATS = 8
# A spark's track is worked out in steps this long; its streak is how far it flies in SHUTTER.
STEP = 1 / 120
SHUTTER = 0.055
# The leader feels its way down this long before a strike lands.
LEAD = 0.09
# Each side's skyline, from its corner inward: (outer and inner side, in points from the screen's
# edge at the design size; top, a share of the height; near (dark, sharp) or far (hazy); crown;
# spire in points; what it shows; when it starts to rise). On another screen a tower is kept out of
# the gap, and one that reaches over the names' side is cut back or kept under them.
LEFT = (
    (-4, 96, 0.37, False, "flat", 0, "", 0.25),
    (86, 168, 0.29, False, "flat", 34, "", 0.32),
    (158, 210, 0.52, False, "slant", 0, "", 0.4),
    (236, 352, 0.862, False, "flat", 0, "", 0.5),
    (344, 470, 0.888, False, "flat", 0, "", 0.56),
    (-4, 36, 0.52, True, "flat", 0, "", 0.36),
    (22, 128, 0.25, True, "step", 74, "screen", 0.42),
    (120, 206, 0.46, True, "slant", 0, "", 0.5),
    (222, 322, 0.868, True, "sign", 0, "sign", 0.6),
    (318, 404, 0.905, True, "tank", 0, "", 0.66),
    (402, 502, 0.935, True, "flat", 0, "", 0.72),
)
RIGHT = (
    (-4, 44, 0.33, False, "flat", 0, "", 0.28),
    (40, 96, 0.4, False, "flat", 28, "", 0.34),
    (96, 214, 0.862, False, "flat", 0, "", 0.48),
    (206, 330, 0.884, False, "flat", 0, "", 0.55),
    (-4, 26, 0.5, True, "flat", 0, "", 0.38),
    (12, 94, 0.27, True, "step", 64, "ticker", 0.44),
    (100, 246, 0.866, True, "sign", 0, "sign", 0.58),
    (242, 346, 0.912, True, "tank", 0, "", 0.64),
    (344, 486, 0.94, True, "flat", 0, "", 0.7),
)
# Lightning: (when it lands, on which side's spire, -1 left or 1 right; 0 strikes the frame's top).
STRIKES = ((1.3, -1), (2.3, 1), (3.05, 0), (3.7, -1))
# Lightning far off in the clouds, no bolt seen: (when, where across the top, a share of the width).
DISTANT = ((0.85, 0.8), (2.8, 0.18))
# Flying cars' lanes over the top band, in shares of the width and height: arcs that keep above the
# title in the middle, and the cars on them: (lane, which way, 1 left to right; when it comes in;
# how long it takes to cross).
LANES = (
    ((-0.06, 0.25), (0.1, 0.16), (0.24, 0.095), (0.37, 0.066), (0.5, 0.06), (0.63, 0.066), (0.76, 0.095), (0.9, 0.16), (1.06, 0.25)),
    ((-0.06, 0.15), (0.14, 0.09), (0.36, 0.058), (0.5, 0.053), (0.64, 0.058), (0.86, 0.09), (1.06, 0.15)),
)
CARS = ((0, 1, 0.5, 1.5), (1, -1, 1.0, 1.9), (0, -1, 1.8, 1.4), (1, 1, 2.45, 1.8), (0, 1, 3.1, 1.45), (1, -1, 3.55, 1.7))
# Rain falls this far sideways for each point it falls.
SLANT = 0.16


class Tower(NamedTuple):
    """A building of the skyline, in points: its sides, the top of its roof (or of its sign), near
    or far, its crown, how tall a spire it has, what it shows (a roof sign, a screen, a ticker or
    nothing), its side (-1 left, 1 right), when it rises and when its windows light, and its seed."""

    left: float
    right: float
    top: float
    near: bool
    crown: str
    spire: float
    show: str
    side: int
    rise: float
    lit: float
    seed: int


class Shape(NamedTuple):
    """A tower's outline and what is on it: its spire's tip, its sign or screen, the blocks its
    windows go on, and the lit lines on its crown."""

    path: QPainterPath
    tip: QPointF | None
    panel: QRectF | None
    blocks: list[QRectF]
    trim: list[QLineF]


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    outer = _frame(width, height, gap, 15 * u, 34 * u, u)
    inner = _frame(width, height, gap, 25 * u, 40 * u, u)
    frame_glow = _frame_glow(width, height, outer, inner, u)
    sky = noise(max(1, round(width * SOFT)), max(1, round(height * SOFT)), 170 * u * SOFT, 4, 21)
    night = Wash(lambda q, w, h: _night(q, w, h, u, sky))
    flashes = [_flash(width, height, gap, u, side) for side in (-1, 1)]
    towers = _skyline(width, height, gap, u)
    shapes = [_tower_shape(tower, height, u) for tower in towers]
    windows = [_windows(tower, shape, u) for tower, shape in zip(towers, shapes, strict=True)]
    heroes = {tower.side: i for i, tower in enumerate(towers) if tower.show in ("screen", "ticker")}
    names = QRectF(width * 0.13, height * 0.29, width * 0.81, height * 0.55)
    title = QRectF(width * 0.38, height * 0.07, width * 0.3, height * 0.18)
    keep = (names, title, gap.adjusted(-30 * u, -30 * u, 30 * u, 30 * u))
    # (when it lands, where from, where to, which way its sparks fly, how many, seed, the tower it hits)
    strikes = []
    for seed, (when, side) in enumerate(STRIKES, 1):
        hero = heroes.get(side)
        if side and hero is not None and shapes[hero].tip is not None:
            end = shapes[hero].tip
            start = QPointF(end.x() - side * width * 0.05, -height * 0.03)
            strikes.append((when, start, end, -1.57, 64, seed, hero))
        else:
            end = QPointF(width * 0.24, 15 * u)
            strikes.append((when, QPointF(width * 0.2, -height * 0.03), end, 1.57, 46, seed, None))
    clouds = {seed: _cloud_flash(width, height, u, sky, start.x() / width, title) for _w, start, _e, _a, _c, seed, _h in strikes}
    distant = [(when, _cloud_flash(width, height, u, sky, at, title)) for when, at in DISTANT]
    bolts: dict[int, list[tuple]] = {}
    showers = {seed: _shower(end, aim, count, u, seed, width, height, keep) for _w, _s, end, aim, count, seed, _h in strikes}
    lights = {name: _dot(color, white) for name, color, white in (("hot", "#bff9ff", 1.0), ("cyan", CYAN, 0.25), ("violet", VIOLET, 0.0))}
    beacon = _dot("#ff2a3a", 0.5, 32)
    heats = _heats(u)
    haze = [_haze(width, height, gap, u, side) for side in (-1, 1)]
    beam = _beam(height, u)
    rain = _rain_drops(width, height, u)
    lanes = [_lane(points, width, height) for points in LANES]
    # Pictures drawn once for each sharpness they are shown at: the towers and their signs, and the
    # frame's lit tubes.
    baked: dict[float, dict] = {}
    tubes: dict[float, list] = {}
    rising = sorted(range(len(towers)), key=lambda i: towers[i].rise)

    def built(scale: float, i: int) -> tuple:
        store = baked.setdefault(scale, {})
        if i not in store:
            tower, shape = towers[i], shapes[i]
            signs = _sign_art(tower, shape.panel, u, scale) if shape.panel is not None else None
            store[i] = (_tower_art(tower, shape, windows[i], height, u, scale), signs)
        return store[i]

    def bolt(seed: int, start: QPointF, end: QPointF) -> list[tuple]:
        if seed not in bolts:
            bolts[seed] = _bolt_shapes(start, end, seed, u, (names, title))
        return bolts[seed]

    def paint(p: QPainter, t: float) -> None:
        began = time.perf_counter()
        scale = _sharpness(p)
        if scale not in tubes:
            tubes[scale] = [_tube_strips(points, tint, width, height, u, scale) for points, tint in ((outer, CYAN), (inner, MAGENTA))]
        life = win(t, 0.0, 0.3)
        leave = ease_in(win(t, 4.35, 5.0))
        p.save()
        p.setOpacity(life)
        night.paint(p, width, height, gap, ease_out(win(t, 0.0, 0.7)) * (1 - leave))
        bright = max((_strike_light(t - when) for when, *_rest in strikes), default=0.0)
        # The clouds light up where lightning comes from, and far off now and then.
        p.save()
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        for when, _start, _end, _aim, _count, seed, _hero in strikes:
            light = _strike_light(t - when) * (1 - leave)
            if light > 0.01:
                p.setOpacity(life * light)
                scaled_up(clouds[seed][1], p, *_box(clouds[seed][0]))
        for when, (rect, image) in distant:
            light = _far_light(t - when) * (1 - leave)
            if light > 0.01:
                p.setOpacity(life * light)
                scaled_up(image, p, *_box(rect))
        p.restore()
        # A strike lights its own side of the screen most, behind the skyline.
        for side, flash in zip((-1, 1), flashes, strict=True):
            near = max(
                (_strike_light(t - when) * (1.0 if (end.x() < width / 2) == (side < 0) else 0.3) for when, _s, end, *_rest in strikes),
                default=0.0,
            )
            if near * (1 - leave) > 0.01:
                p.save()
                p.setRenderHint(QPainter.SmoothPixmapTransform)
                p.setOpacity(life * near * (1 - leave))
                _lay_round(p, flash, width, height, names)
                p.restore()
        p.setOpacity(life * (1 - leave))
        struck = {hero: max(_strike_light(t - when) for when, *_r, h in strikes if h == hero) for *_r, hero in strikes if hero is not None}
        for near in (False, True):
            if near:
                _beams(p, t, beam, width, height, u, life * (1 - leave))
            for i, (tower, shape) in enumerate(zip(towers, shapes, strict=True)):
                if tower.near == near and t > tower.rise:
                    _tower(p, t, tower, shape, *built(scale, i), beacon, u, height, struck.get(i, 0.0), leave)
            # The street haze between the far towers and the near, and over the near ones' feet.
            for rect, image in haze:
                p.setOpacity(life * (1 - leave) * (0.55 if not near else 0.6) * ease_out(win(t, 0.3, 1.2)))
                drift = math.sin(t * 0.7 + (0 if near else 2)) * 8 * u
                scaled_up(image, p, rect.left() + drift, rect.top(), rect.width(), rect.height())
        p.setOpacity(life)
        _rain(p, t, rain, width, height, gap, names, u, (1 - leave) * ease_out(win(t, 0.15, 0.9)), bright)
        _trails(p, t, lanes, lights, width, height, u, 1 - leave)
        _neon_frame(p, t, outer, inner, frame_glow, tubes[scale], lights, width, height, u, bright)
        for when, start, end, _aim, _count, seed, hero in strikes:
            if -LEAD <= t - when <= 0.55:
                _strike(p, t - when, start, end, bolt(seed, start, end), lights, u)
            if hero is not None:
                _spire(p, t - when, end, lights, u, seed)
        for when, *_rest, seed, _hero in strikes:
            _spark_shower(p, t - when, showers[seed], heats, u)
        p.restore()
        # One strike's lightning worked out ahead each frame, so no frame waits long for it.
        for _when, start, end, _aim, _count, seed, _hero in strikes:
            if seed not in bolts:
                bolt(seed, start, end)
                break
        # The towers worked out ahead too, in the order they rise: while the frame has time to
        # spare, and any about to rise whether or not.
        for i in rising:
            if i in baked.get(scale, {}):
                continue
            if time.perf_counter() - began > 0.012 and towers[i].rise > t + 0.15:
                break
            built(scale, i)

    return paint


def _box(rect: QRectF) -> tuple[float, float, float, float]:
    return rect.left(), rect.top(), rect.width(), rect.height()


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


def _over(rect: QRectF, scale: float, draw) -> np.ndarray:  # noqa: ANN001
    """What draw paints in white over rect, as 0..1 per pixel at scale pixels to the point."""
    w, h = max(1, math.ceil(rect.width() * scale)), max(1, math.ceil(rect.height() * scale))

    def placed(q: QPainter) -> None:
        q.scale(w / rect.width(), h / rect.height())
        q.translate(-rect.left(), -rect.top())
        draw(q)

    return mask(w, h, placed)


def _grid(rect: QRectF, shape: tuple[int, ...]) -> tuple[np.ndarray, np.ndarray]:
    """Each pixel of a picture of rect, shape (height, width), in points: x and y."""
    h, w = shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    return rect.left() + (xs + 0.5) * rect.width() / w, rect.top() + (ys + 0.5) * rect.height() / h


def _ready(image: QImage) -> QImage:
    """A picture in the screen's own pixel format, so laying it on every frame costs no conversion."""
    return image.convertToFormat(QImage.Format_ARGB32_Premultiplied)


def _blur3(light: np.ndarray, sigma: float) -> np.ndarray:
    return np.dstack([blur(light[..., c], sigma) for c in range(3)])


def _grown(a: np.ndarray, k: int, shape: tuple[int, ...]) -> np.ndarray:
    """A picture worked out small, k times bigger, cut to shape (height, width, ...)."""
    big = np.repeat(np.repeat(a, k, axis=0), k, axis=1)
    pad = [(0, max(0, shape[0] - big.shape[0])), (0, max(0, shape[1] - big.shape[1]))] + [(0, 0)] * (a.ndim - 2)
    return np.pad(big, pad, mode="edge")[: shape[0], : shape[1]]


def _soft(a: np.ndarray) -> np.ndarray:
    """A pixel's worth of softening: each pixel shared with its four neighbours."""
    return (a * 2 + np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 6


# The skyline ------------------------------------------------------------------------------------


def _skyline(width: float, height: float, gap: QRectF, u: float) -> list[Tower]:
    """The towers of both sides, far ones first, kept out of the gap and off the names."""
    names_left, names_right = width * 0.13, width * 0.94
    under = height * 0.84 + 14 * u
    out = []
    for side, rows in ((-1, LEFT), (1, RIGHT)):
        for i, (near_edge, far_edge, top, near, crown, spire, show, rise) in enumerate(rows):
            top *= height
            if side < 0:
                left, right = near_edge * u, min(far_edge * u, gap.left() - 16 * u)
                over = right > names_left
            else:
                left, right = max(width - far_edge * u, gap.right() + 16 * u), width - near_edge * u
                over = left < names_right
            if over and top < under:
                if spire or show in ("screen", "ticker"):
                    # A tall tower stays tall, beside the names.
                    left, right = (left, min(right, names_left - 3 * u)) if side < 0 else (max(left, names_right + 3 * u), right)
                else:
                    top = under
            if right - left < 14 * u:
                continue
            out.append(Tower(left, right, top, near, crown, spire * u, show, side, rise, rise + 0.62 + 0.07 * (i % 3), 40 + i + 20 * (side > 0)))
    return out


def _tower_shape(tower: Tower, height: float, u: float) -> Shape:
    """A tower's outline: its body to the bottom of the screen and its crown, with a sign on legs,
    a water tank, a slanted roof or setbacks under a spire."""
    rnd = random.Random(tower.seed)
    left, right, top = tower.left, tower.right, tower.top
    w = right - left
    path = QPainterPath()
    path.setFillRule(Qt.WindingFill)
    blocks: list[QRectF] = []
    trim: list[QLineF] = []
    tip = panel = None
    spire_at = left + w * 0.68
    roof = top
    if tower.crown == "step":
        roof = top + 36 * u
        for share, y, tall in ((0.25, top, 18 * u), (0.12, top + 16 * u, 22 * u)):
            block = QRectF(left + w * share, y, w * (1 - 2 * share), tall + 2 * u)
            path.addRect(block)
            blocks.append(block)
            trim.append(QLineF(block.left() + 1.5 * u, block.top() + 0.8 * u, block.right() - 1.5 * u, block.top() + 0.8 * u))
        trim.append(QLineF(left + 1.5 * u, roof + 0.8 * u, right - 1.5 * u, roof + 0.8 * u))
        spire_at = left + w / 2
    elif tower.crown == "slant":
        fall = min(28 * u, w * 0.35)
        high_left = tower.side > 0
        path.addPolygon(QPolygonF([
            QPointF(left, top + (0 if high_left else fall)), QPointF(right, top + (fall if high_left else 0)),
            QPointF(right, height + 2 * u), QPointF(left, height + 2 * u),
        ]))  # fmt: skip
        roof = top + fall
    elif tower.crown == "tank":
        roof = top + 15 * u
        side = min(17 * u, w * 0.3)
        at = left + w * rnd.uniform(0.18, 0.5)
        path.addRect(QRectF(at, top + 3.5 * u, side, 8 * u))
        path.addPolygon(QPolygonF([QPointF(at - 0.6 * u, top + 3.8 * u), QPointF(at + side / 2, top), QPointF(at + side + 0.6 * u, top + 3.8 * u)]))
        for leg in (at + 1.5 * u, at + side - 3 * u):
            path.addRect(QRectF(leg, top + 11 * u, 1.5 * u, roof - top - 10 * u))
    elif tower.crown == "sign":
        roof = top + 34 * u
        panel = QRectF(left + w * 0.05, top, w * 0.9, 25 * u)
        path.addRect(panel)
        for share in (0.22, 0.74):
            path.addRect(QRectF(panel.left() + panel.width() * share, panel.bottom() - 1, 2.2 * u, roof - panel.bottom() + 2))
    else:
        for _ in range(rnd.choice((1, 2))):
            box_w = w * rnd.uniform(0.14, 0.3)
            box_h = rnd.uniform(3.5, 7) * u
            path.addRect(QRectF(left + rnd.uniform(0.05, 0.9) * (w - box_w), top - box_h, box_w, box_h + 1))
    body = QRectF(left, roof, w, height + 2 * u - roof)
    path.addRect(body)
    blocks.append(body)
    if tower.spire:
        base = top if tower.crown == "step" else roof
        tip = QPointF(spire_at, base - tower.spire)
        path.addPolygon(QPolygonF([
            QPointF(spire_at - 2.2 * u, base + 1), QPointF(spire_at - 0.55 * u, tip.y()),
            QPointF(spire_at + 0.55 * u, tip.y()), QPointF(spire_at + 2.2 * u, base + 1),
        ]))  # fmt: skip
        bar = base - tower.spire * 0.45
        path.addRect(QRectF(spire_at - 4.5 * u, bar, 9 * u, 1.4 * u))
    if tower.show == "screen":
        panel = QRectF(left + w * 0.13, roof + 18 * u, w * 0.74, 52 * u)
    elif tower.show == "ticker":
        panel = QRectF(left + 4 * u, roof + 26 * u, w - 8 * u, 15 * u)
    return Shape(path, tip, panel, blocks, trim)


def _windows(tower: Tower, shape: Shape, u: float) -> list[tuple[QRectF, str, float]]:
    """The tower's windows: (where, color, how bright), 0 bright for one that is dark. Some columns
    and floors are busier than others, as in a real tower at night."""
    rnd = random.Random(tower.seed * 31)
    pitch_x, pitch_y = (6.0 * u, 8.6 * u) if tower.near else (5.0 * u, 7.0 * u)
    ww, wh = (3.0 * u, 4.0 * u) if tower.near else (2.2 * u, 3.0 * u)
    share = rnd.uniform(0.13, 0.22) * (1 if tower.near else 0.7)
    # Most windows warm, some cool office white, a few lit by a screen in the room.
    colors = ("#ffb767", "#ffc98a", "#ffc98a", "#ffd9a6", "#ffe8c8", "#dfefff", "#bcd8ff", "#7ff3ff", "#ff8fe6")
    clear = shape.panel.adjusted(-3 * u, -3 * u, 3 * u, 3 * u) if shape.panel is not None else QRectF()
    out = []
    for block in shape.blocks:
        cols = int((block.width() - 5 * u) / pitch_x)
        if cols < 1:
            continue
        x0 = block.left() + (block.width() - cols * pitch_x) / 2 + (pitch_x - ww) / 2
        busy = [rnd.choice((0.2, 0.6, 1.0, 1.0, 1.6)) for _ in range(cols)]
        y = block.top() + 6 * u
        while y + wh < block.bottom():
            # Now and then a whole floor is at work, and many are nearly dark.
            floor = rnd.choice((0.15, 0.4, 0.8, 1.0, 1.3, 4.0)) if rnd.random() < 0.9 else 5.0
            for c in range(cols):
                cell = QRectF(x0 + c * pitch_x, y, ww, wh)
                if clear.intersects(cell):
                    continue
                lit = rnd.random() < share * busy[c] * floor
                out.append((cell, rnd.choice(colors), rnd.uniform(0.3, 1.0) ** 0.8 if lit else 0.0))
            y += pitch_y
    return out


def _tower_art(tower: Tower, shape: Shape, windows: list[tuple], height: float, u: float, scale: float) -> list:
    """A tower worked out per pixel: steel and glass dark against the glow, a little sky light on its
    roofs, a neon rim on the side toward the screen's middle, the street's glow on its feet, the
    grain of its facade; and, as a picture of its own, its lit windows and crown with their bloom.
    Far towers sink into the haze. Returns where it goes, the tower, its lights, and room for the
    two in one picture."""
    rect = shape.path.boundingRect().adjusted(-5 * u, -5 * u, 5 * u, 0)
    rect.setBottom(height)

    def silhouette(q: QPainter) -> None:
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawPath(shape.path)

    m = _over(rect, scale, silhouette)
    h, w = m.shape
    x, y = _grid(rect, m.shape)
    v = np.clip((y - tower.top) / max(1.0, height - tower.top), 0, 1)
    tint, rim_tint = (rgb(MAGENTA), rgb(CYAN)) if tower.side < 0 else (rgb(CYAN), rgb(MAGENTA))
    color = rgb("#130c2c") * (1 - v)[..., None] + rgb("#040210") * v[..., None]
    # The grain is soft: worked out at a quarter of the size.
    grain = _grown(noise(w // 4 + 1, h // 4 + 1, max(2.0, 7 * u * scale / 4), 2, tower.seed), 4, m.shape)
    mullion = 1 - 0.3 * smooth(0.8, 0.97, ((x - tower.left) / (6.0 * u)) % 1)
    color = color * ((0.75 + 0.5 * grain) * mullion)[..., None]
    color += tint * (np.exp(-(height - y) / (70 * u)) * 0.32)[..., None]
    k = max(1, round(1.4 * scale))
    rim = _soft(np.clip(m - np.roll(m, -k if tower.side < 0 else k, axis=1), 0, 1)) * m
    roof = _soft(np.clip(m - np.roll(m, k, axis=0), 0, 1)) * m
    color += rim_tint * (rim * (0.2 + 1.0 * (1 - v) ** 3))[..., None]
    color += rgb("#a294ff") * (roof * 0.45)[..., None]

    def dark(q: QPainter) -> None:
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        for cell, _tint, level in windows:
            if level <= 0:
                q.drawRect(cell)

    # Dark glass catching a little of the sky's glow.
    color += rgb("#2c3070") * (_over(rect, scale, dark) * 0.16 * (1 - v * 0.7))[..., None]
    alpha = m
    if not tower.near:
        haze = rgb("#1e1240") * (1 - v)[..., None] + rgb("#2a0f3c" if tower.side < 0 else "#0e1f48") * v[..., None]
        color = color * 0.35 + haze * 0.65
        alpha = m * 0.95
    body = picture(color, alpha)
    lit = QImage(w, h, QImage.Format_RGBA8888)
    lit.fill(Qt.black)
    q = QPainter(lit)
    q.setRenderHint(QPainter.Antialiasing)
    q.scale(w / rect.width(), h / rect.height())
    q.translate(-rect.left(), -rect.top())
    q.setPen(Qt.NoPen)
    for cell, tone, level in windows:
        if level > 0:
            q.setBrush(mix("#000000", tone, level))
            q.drawRect(cell)
    q.setPen(QPen(col(CYAN if tower.side < 0 else MAGENTA), 1.2 * u, Qt.SolidLine, Qt.FlatCap))
    for line in shape.trim:
        q.drawLine(line)
    q.end()
    stride = lit.bytesPerLine()
    pixels = np.frombuffer(lit.constBits(), dtype=np.uint8, count=stride * h).reshape(h, stride)[:, : w * 4]
    light = pixels.reshape(h, w, 4)[..., :3].astype(np.float32) / 255.0
    # The bloom is soft too: blurred at half the size.
    half = (light[: h // 2 * 2 : 2, : w // 2 * 2 : 2] + light[1 : h // 2 * 2 : 2, 1 : w // 2 * 2 : 2]) / 2
    halo = _blur3(half, 0.65 * scale) * 0.75 + _blur3(half, 2.25 * scale) * 0.4
    light = light + _soft(_grown(halo, 2, light.shape)) * 1.15
    if not tower.near:
        light *= 0.45
    # The tower with its lights on is made when first wanted (see _tower).
    return [rect, _ready(body), _ready(glow(light)), None]


def _glyph(q: QPainter, cell: QRectF, rnd: random.Random) -> None:
    """A made-up character: three or four strokes on a grid of three by three."""
    x0, x1, y0, y1 = cell.left(), cell.right(), cell.top(), cell.bottom()
    xm, ym = cell.center().x(), cell.center().y()
    strokes = (
        (x0, y0, x1, y0), (x0, ym, x1, ym), (x0, y1, x1, y1), (x0, y0, x0, y1), (xm, y0, xm, y1), (x1, y0, x1, y1),
        (x0, y0, xm, ym), (x1, y0, x0, y1), (xm, ym, x1, y1), (x0, ym, xm, y1), (xm, y0, x1, ym),
    )  # fmt: skip
    for stroke in rnd.sample(strokes, rnd.choice((3, 3, 4))):
        q.drawLine(QLineF(*stroke))


def _sign_art(tower: Tower, panel: QRectF, u: float, scale: float) -> tuple[QRectF, list[QImage]]:
    """A billboard's two pictures, worked out per pixel: its glyphs and frame lit in neon with their
    bloom, the panel's hologram light in scan lines. A roof sign shows a row of glyphs, the screen a
    ring and bars, the ticker a long strip of glyphs to scroll. Returns the area they cover."""
    tint = (MAGENTA if tower.side < 0 else CYAN) if tower.show != "screen" else CYAN
    edge = CYAN if tint == MAGENTA else MAGENTA
    pad = 9 * u
    ticker = tower.show == "ticker"
    area = panel.adjusted(-pad, -pad, pad + (panel.width() * 2.2 if ticker else 0), pad)
    rnd = random.Random(tower.seed * 7)
    out = []
    for variant in range(1 if ticker else 2):

        def strokes(q: QPainter, variant: int = variant) -> None:
            q.setPen(QPen(Qt.white, 1.8 * u, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
            if tower.show == "screen":
                r = panel.height() * 0.27
                at = QPointF(panel.center().x(), panel.top() + panel.height() * 0.38)
                q.drawEllipse(at, r, r)
                d = r * (0.5 if variant else 0.62)
                q.drawPolygon(QPolygonF([QPointF(at.x(), at.y() - d), QPointF(at.x() + d * 0.7, at.y()), QPointF(at.x(), at.y() + d), QPointF(at.x() - d * 0.7, at.y())]))
                for row in range(2):
                    y = panel.top() + panel.height() * (0.78 + 0.12 * row)
                    span = panel.width() * rnd.uniform(0.35, 0.75)
                    q.drawLine(QLineF(panel.center().x() - span / 2, y, panel.center().x() + span / 2, y))
                return
            side = panel.height() * 0.6
            count = int(area.width() / (side * 1.55)) if ticker else max(2, int((panel.width() - side * 0.6) / (side * 1.4)))
            spacing = (area.width() if ticker else panel.width()) / count
            start = area.left() if ticker else panel.left()
            for i in range(count):
                cell = QRectF(start + spacing * (i + 0.5) - side / 2, panel.center().y() - side / 2, side, side)
                if ticker and i % 4 == 3:
                    q.drawRect(QRectF(cell.center().x() - u, cell.center().y() - u, 2 * u, 2 * u))
                    continue
                _glyph(q, cell, rnd)

        def frame(q: QPainter) -> None:
            q.setPen(QPen(Qt.white, 1.1 * u))
            q.setBrush(Qt.NoBrush)
            if ticker:
                q.drawLine(QLineF(area.left(), panel.top(), area.right(), panel.top()))
                q.drawLine(QLineF(area.left(), panel.bottom(), area.right(), panel.bottom()))
            else:
                q.drawRect(panel.adjusted(0.6 * u, 0.6 * u, -0.6 * u, -0.6 * u))

        def fill(q: QPainter) -> None:
            q.fillRect(QRectF(area.left(), panel.top(), area.width(), panel.height()) if ticker else panel, Qt.white)

        g, f, inside = (_over(area, scale, draw) for draw in (strokes, frame, fill))
        light = (blur(g, 1.0 * scale) * 1.4 + blur(g, 3.0 * scale) * 1.3 + blur(g, 8 * scale) * 1.0)[..., None] * rgb(tint)
        light += (g ** 1.5)[..., None] * (rgb(tint) * 0.5 + 0.75)
        light += (blur(f, 1.0 * scale) * 0.8 + blur(f, 4 * scale) * 0.5)[..., None] * rgb(edge) + (f ** 1.5)[..., None] * (rgb(edge) * 0.5 + 0.5)
        _x, y = _grid(area, g.shape)
        scan = 0.55 + 0.45 * (((y - area.top()) / (2.2 * u)) % 1 < 0.5)
        light += (inside * scan * 0.16)[..., None] * rgb(tint)
        out.append(_ready(glow(light)))
    return area, out


def _tower(
    p: QPainter, t: float, tower: Tower, shape: Shape, pictures: tuple, signs: tuple | None, beacon: QImage, u: float, height: float,
    struck: float, leave: float
) -> None:
    """A tower rising into place, its windows lighting floor by floor from the bottom, its sign or
    screen flickering on, a red light blinking on its spire."""
    k = ease_out(win(t, tower.rise, tower.rise + (0.9 if tower.near else 1.1)))
    if k <= 0:
        return
    rect, body, lit, whole = pictures
    drop = (1 - k) * (height - rect.top() + 6 * u)
    base = p.opacity()
    wipe = ease_in_out(win(t, tower.lit, tower.lit + 0.6))
    if wipe >= 1:
        # All lit: the tower and its lights as one picture from now on.
        if whole is None:
            whole = pictures[3] = QImage(body)
            q = QPainter(whole)
            q.drawImage(0, 0, lit)
            q.end()
        p.drawImage(rect.translated(0, drop), whole)
    else:
        p.drawImage(rect.translated(0, drop), body)
    if 0 < wipe < 1:
        line = rect.bottom() - rect.height() * wipe
        p.save()
        p.setClipRect(QRectF(rect.left(), line + drop, rect.width(), rect.bottom() - line + 2))
        p.drawImage(rect.translated(0, drop), lit)
        p.restore()
    if signs is not None:
        _sign(p, t, tower, shape.panel, signs, u, drop, struck)
        p.setOpacity(base)
    if shape.tip is not None:
        blink = math.sin(math.pi * clamp(((t + tower.seed * 0.17) % 1.15) / 0.22))
        if blink > 0:
            _lay(p, beacon, shape.tip.x(), shape.tip.y() + drop + 1 * u, 9 * u, base * blink * k)
            p.setOpacity(base)


def _sign(p: QPainter, t: float, tower: Tower, panel: QRectF, signs: tuple, u: float, drop: float, struck: float) -> None:
    """A billboard: off, then flickering on; its two pictures taking turns; torn into slices when its
    tower is struck. A screen's ring turns and a scan line runs down it; a ticker scrolls."""
    area, images = signs
    on = tower.lit + 0.3 + (0.2 if tower.show == "sign" else 0.0)
    level = _neon(t, on, tower.seed) * _power_down(t, tower.seed % 5)
    if level <= 0:
        return
    base = p.opacity()
    age = t - on
    turn = int(age / 1.3) % len(images)
    if len(images) > 1 and age % 1.3 < 0.07 and age > 1:
        level *= 0.3
    level *= 1 + 0.8 * struck
    area = area.translated(0, drop)
    panel = panel.translated(0, drop)
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    if tower.show == "ticker":
        p.setClipRect(QRectF(panel.left(), area.top(), panel.width(), area.height()))
        span = area.width() - panel.width() - 18 * u
        shift = (age * 26 * u) % span
        p.setOpacity(base * min(1.0, level))
        p.drawImage(area.translated(-shift, 0), images[0])
        p.restore()
        return
    glitch = struck > 0.2
    if glitch:
        rnd = random.Random(int(t * 30) * 13 + tower.seed)
        bands = 5
        for i in range(bands):
            band = QRectF(area.left() - 20 * u, area.top() + area.height() * i / bands, area.width() + 40 * u, area.height() / bands + 1)
            shift = rnd.uniform(-9, 9) * u
            p.save()
            p.setClipRect(band)
            for dx, alpha in ((shift - 4 * u, 0.45), (shift + 4 * u, 0.45), (shift, 1.0)):
                p.setOpacity(base * min(1.0, level) * alpha)
                p.drawImage(area.translated(dx, 0), images[turn])
            p.restore()
    else:
        p.setOpacity(base * min(1.0, level))
        p.drawImage(area, images[turn])
    if tower.show == "screen":
        r = panel.height() * 0.27 + 3.2 * u
        at = QPointF(panel.center().x(), panel.top() + panel.height() * 0.38)
        p.setOpacity(base * min(1.0, level))
        for w, color, alpha in ((4.5, CYAN, 0.35), (1.4, "#e9fdff", 0.95)):
            p.setPen(QPen(col(color, alpha), w * u, Qt.SolidLine, Qt.FlatCap))
            p.drawArc(QRectF(at.x() - r, at.y() - r, 2 * r, 2 * r), round(-age * 140 * 16) % (360 * 16), 80 * 16)
        scan = (age % 1.7) / 1.7
        y = panel.top() + panel.height() * scan
        p.setPen(QPen(col(CYAN, 0.55 * (1 - scan)), 1.2 * u))
        p.drawLine(QLineF(panel.left() + 1.5 * u, y, panel.right() - 1.5 * u, y))
    p.restore()


def _haze(width: float, height: float, gap: QRectF, u: float, side: int) -> tuple[QRectF, QImage]:
    """The street's glow in the mist round the towers' feet on one side, per pixel at half size:
    magenta on the left, cyan on the right, thinning upward and toward the gap."""
    reach = 190 * u
    if side < 0:
        rect = QRectF(-20 * u, height - reach, gap.left() + 20 * u, reach)
    else:
        rect = QRectF(gap.right(), height - reach, width - gap.right() + 20 * u, reach)
    w, h = max(1, round(rect.width() * 0.5)), max(1, round(rect.height() * 0.5))
    x, y = _grid(rect, (h, w))
    mist = noise(w, h, 40 * u * 0.5, 3, 30 + side)
    thick = np.exp(-(height - y) / (55 * u)) * (0.45 + 0.9 * mist)
    edge = gap.left() if side < 0 else gap.right()
    thick *= smooth(10 * u, 150 * u, np.abs(x - edge))
    thick *= 1 - smooth(rect.height() * 0.7, rect.height(), height - y)
    tint = rgb(MAGENTA if side < 0 else CYAN)
    light = thick[..., None] * (tint * 0.42 + rgb(VIOLET) * 0.22)
    return rect, _ready(glow(light))


def _beam(height: float, u: float) -> tuple[QRectF, QImage]:
    """A searchlight's beam pointing up from its lamp at (0, 0), per pixel at half size: a pale
    shaft widening and fading as it climbs into the smog, brightest near the lamp."""
    reach = height * 1.08
    rect = QRectF(-80 * u, -reach, 160 * u, reach)
    w, h = max(1, round(rect.width() * 0.5)), max(1, round(rect.height() * 0.5))
    x, y = _grid(rect, (h, w))
    d = -y
    spread = 3 * u + d * 0.055
    smog = noise(w, h, 60 * u * 0.5, 3, 44)
    shaft = np.exp(-2.2 * (x / spread) ** 2) * (1 - smooth(reach * 0.72, reach, d)) * (0.55 + 0.45 * np.exp(-d / (reach * 0.4)))
    shaft *= 0.65 + 0.6 * smog
    light = shaft[..., None] * (rgb("#e4dcff") * 0.45 + rgb(VIOLET) * 0.22)
    return rect, _ready(glow(light))


def _beams(p: QPainter, t: float, beam: tuple[QRectF, QImage], width: float, height: float, u: float, a: float) -> None:
    """Two searchlights behind the near towers, sweeping the clouds slowly and out of step, leaning
    in no further than keeps them off the names."""
    level = ease_out(win(t, 0.9, 1.8)) * a
    if level <= 0.01:
        return
    rect, image = beam
    d = height * 0.71
    edge = 3 * u + d * 0.055 * 1.3
    p.save()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    for side, x0, phase in ((-1, width * 0.04, 0.0), (1, width * 0.965, 2.4)):
        room = (width * 0.13 - 8 * u - x0 - edge) if side < 0 else (x0 - width * 0.94 - 8 * u - edge)
        lean = math.degrees(math.atan2(room, d))
        angle = lean - 26 * (0.5 - 0.5 * math.sin(t * 0.85 + phase))
        p.save()
        p.translate(x0, height)
        p.rotate(angle if side < 0 else -angle)
        p.setOpacity(level)
        p.drawImage(rect, image)
        p.restore()
    p.restore()


# The sky -----------------------------------------------------------------------------------------


def _field(width: float, height: float, u: float) -> tuple[np.ndarray, ...]:
    """Each pixel of a quarter-size picture of the stage, in points: x, y, how clear of the names
    it is (0 over them, 1 well away) and how near the screen's edge (1 at it, 0 far in)."""
    w, h = max(1, round(width * SOFT)), max(1, round(height * SOFT))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    x, y = (xs + 0.5) / SOFT, (ys + 0.5) / SOFT
    r = 120 * u
    dx = np.maximum(np.maximum(width * 0.13 + r - x, x - width * 0.94 + r), 0)
    dy = np.maximum(np.maximum(height * 0.29 + r - y, y - height * 0.84 + r), 0)
    clear = smooth(0, 150 * u, np.hypot(dx, dy) - r)
    rim = 1 - smooth(0, 300 * u, np.minimum(np.minimum(x, width - x), np.minimum(y, height - y)))
    return x, y, clear, rim


def _night(p: QPainter, width: float, height: float, u: float, sky: np.ndarray) -> None:
    """The night at the edges, per pixel: deep indigo darkening toward the edges with smog drifting
    through it, storm clouds banked along the top, and over each bottom corner the city's glow in
    the smog, magenta on the left and cyan on the right, for the skyline to stand against."""
    x, y, clear, rim = _field(width, height, u)
    h, w = x.shape
    sky = sky[:h, :w]
    smog = noise(w, h, 110 * u * SOFT, 3, 9)
    dark = clear * (0.45 + 0.5 * rim) * (0.85 + 0.3 * smog)
    tone = rgb(NIGHT) * rim[..., None] + rgb(INDIGO) * (1 - rim[..., None])
    for cx, cy, reach, tint in ((0.0, 0.0, 600 * u, "#1a0a4d"), (width, 0.0, 620 * u, "#1c0840")):
        g = (np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / reach ** 2 * 2.0) * (0.6 + 0.5 * smog) * 0.9)[..., None]
        tone = tone * (1 - g) + rgb(tint) * g
    cloud = smooth(0.42, 0.78, sky) * (1 - smooth(height * 0.05, height * 0.3, y))
    tone = tone * (1 - cloud[..., None] * 0.55) + rgb("#2e2163") * (cloud[..., None] * 0.55)
    light = tone * dark[..., None]
    amount = dark.copy()
    for cx, tint, deep, strength in ((0.0, MAGENTA, "#4a0c5c", 0.62), (width, CYAN, "#0b3478", 0.68)):
        g = np.exp(-(((x - cx) / (width * 0.24)) ** 2 + ((y - height) / (height * 0.8)) ** 2)) * clear * (0.5 + 0.7 * smog)
        light += g[..., None] * (rgb(deep) * 0.9 + rgb(tint) * 0.3) * strength * 2
        amount += g * strength
    alpha = np.clip(amount, 0, 0.94)
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(QRectF(0, 0, width, height), picture(light / np.maximum(amount, 1e-4)[..., None], alpha))
    p.restore()


def _cloud_flash(width: float, height: float, u: float, sky: np.ndarray, at: float, title: QRectF) -> tuple[QRectF, QImage]:
    """The storm clouds lit from inside by lightning near at (a share of the width), per pixel at a
    quarter of the size: white-hot where they are thick, lavender and violet round it; hardly any
    over the title."""
    rect = QRectF(0, 0, width, height * 0.42)
    h, w = max(1, round(rect.height() * SOFT)), max(1, round(width * SOFT))
    x, y = _grid(rect, (h, w))
    thick = smooth(0.38, 0.85, sky[:h, :w])
    near = np.exp(-(((x - at * width) / (width * 0.2)) ** 2)) * (1 - smooth(height * 0.02, height * 0.38, y))
    away = np.hypot(np.maximum(np.maximum(title.left() - x, x - title.right()), 0), np.maximum(np.maximum(title.top() - y, y - title.bottom()), 0))
    lit = thick * near * (0.1 + 0.9 * smooth(0, 60 * u, away))
    light = (lit ** 2.5)[..., None] * rgb("#ffffff") * 0.8 + lit[..., None] * rgb("#a99bff") * 0.55 + blur(lit, 6)[..., None] * rgb(VIOLET) * 0.45
    return rect, _ready(glow(light))


def _far_light(age: float) -> float:
    """Lightning far off in the clouds: two flickers, dim."""
    if age < 0 or age > 0.42:
        return 0.0
    for end, level in ((0.05, 0.55), (0.1, 0.12), (0.15, 0.4)):
        if age < end:
            return level
    return 0.4 * (1 - (age - 0.15) / 0.27) ** 2


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
    return _ready(picture(color / np.maximum(color.max(axis=-1), 1e-4)[..., None], light * 0.4))


# Rain and traffic --------------------------------------------------------------------------------


def _rain_drops(width: float, height: float, u: float) -> list[tuple[np.ndarray, ...]]:
    """Two layers of rain: far drops, short, thin and slow, and near ones, long and quick, their
    front half brighter. Each layer (x where it would cross the top, phase, speed, length, pen
    width, how bright, whether its front is brighter)."""
    rng = np.random.default_rng(31)
    out = []
    for count, speed, length, pen, alpha, front in ((160, (850, 1100), (9, 16), 0.8, 0.26, False), (60, (1500, 1900), (22, 38), 1.2, 0.3, True)):
        n = round(count * width / 1635)
        out.append((
            rng.uniform(-SLANT * height, width, n), rng.uniform(0, 1, n), rng.uniform(*speed, n) * u,
            rng.uniform(*length, n) * u, pen * u, alpha, front,
        ))  # fmt: skip
    return out


def _rain(p: QPainter, t: float, layers: list[tuple], width: float, height: float, gap: QRectF, names: QRectF, u: float, a: float, flash: float) -> None:
    """The rain: streaks tinted by the neon, magenta on the left, lavender in the middle and cyan on
    the right, faint over the names, none in the gap, glinting white when lightning strikes."""
    if a <= 0:
        return
    p.save()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    tints = (("#ffb3ee", "#ffe0f8"), ("#c2b8ff", "#ece8ff"), ("#a8fbff", "#e2feff"))
    span = height + 80 * u
    for x0, phase, speed, length, pen, alpha, bright_front in layers:
        head = (phase * span + speed * t) % span - 20 * u
        tail = head - length
        middle = head - length * 0.45
        xh, xm, xt = x0 + SLANT * head, x0 + SLANT * middle, x0 + SLANT * tail
        out = (xh > gap.left() - 8 * u) & (xt < gap.right() + 8 * u) & (head > gap.top() - 10 * u)
        over = (xh > names.left()) & (xh < names.right()) & (head > names.top()) & (tail < names.bottom())
        zone = np.digitize(xh, [width / 3, width * 2 / 3])
        for z, (tint, hot) in enumerate(tints):
            for dim in (False, True):
                pick = ~out & (zone == z) & (over == dim)
                if not pick.any():
                    continue
                strength = alpha * a * (0.28 if dim else 1.0) * (1 + 1.6 * flash)
                whole = [QLineF(*q) for q in zip(xt[pick].tolist(), tail[pick].tolist(), xh[pick].tolist(), head[pick].tolist(), strict=True)]
                p.setPen(QPen(mix(tint, "#ffffff", flash * 0.6, strength * 0.6), pen, Qt.SolidLine, Qt.RoundCap))
                p.drawLines(whole)
                if bright_front:
                    front = [QLineF(*q) for q in zip(xm[pick].tolist(), middle[pick].tolist(), xh[pick].tolist(), head[pick].tolist(), strict=True)]
                    p.setPen(QPen(mix(hot, "#ffffff", flash * 0.6, strength), pen, Qt.SolidLine, Qt.RoundCap))
                    p.drawLines(front)
    p.restore()


def _lane(points: tuple, width: float, height: float) -> tuple[list[QPointF], list[float]]:
    path = catmull([QPointF(x * width, y * height) for x, y in points], 16)
    return path, lengths(path)


def _trails(p: QPainter, t: float, lanes: list[tuple], lights: dict, width: float, height: float, u: float, a: float) -> None:
    """Flying cars crossing the top band, each a hot head and a long light trail behind it, as a
    long exposure sees it: cyan going right, magenta going left, thinner where the lane is far."""
    if a <= 0:
        return
    p.save()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    base = p.opacity()
    pieces = 12
    for lane, way, start, cross in CARS:
        k = (t - start) / cross
        if not 0 < k < 1.5:
            continue
        points, cumulative = lanes[lane]
        total = cumulative[-1]
        trail = total * 0.42
        head = k * (total + trail) * 0.75
        tail = head - trail
        if way < 0:
            head, tail = total - head, total - tail
        tint, hot = (CYAN, "#e9fdff") if way > 0 else (MAGENTA, "#ffe3f8")
        fade = a * (1 - win(k, 1.15, 1.5))
        # Along the trail, from its tail to the car: (where, its direction, how near the lane is).
        track = []
        for i in range(pieces + 1):
            s = tail + (head - tail) * i / pieces
            at, angle = point_at(points, cumulative, s)
            track.append((at, angle, 0.45 + 0.55 * clamp((at.y() - height * 0.05) / (height * 0.15)), 0 <= s <= total))
        p.setOpacity(base)
        for i in range(1, pieces + 1):
            (a0, _angle0, _near0, in0), (a1, angle, near, in1) = track[i - 1], track[i]
            if not (in0 and in1):
                continue
            strength = (i / pieces) ** 1.6 * fade
            p.setPen(QPen(col(tint, 0.2 * strength), 8 * u * near, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(a0, a1)
            # Two lights a car's width apart, as a long exposure draws them.
            for side in (-1, 1):
                dx, dy = -math.sin(angle) * side * 1.6 * u * near, math.cos(angle) * side * 1.6 * u * near
                p.setPen(QPen(mix(tint, hot, i / pieces, strength * 0.9), 1.3 * u * near, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(QPointF(a0.x() + dx, a0.y() + dy), QPointF(a1.x() + dx, a1.y() + dy))
        front, _angle, near, inside = track[-1]
        if inside:
            _lay(p, lights["cyan" if way > 0 else "violet"], front.x(), front.y(), 22 * u * near, 0.8 * fade * base)
            _lay(p, lights["hot"], front.x(), front.y(), 8 * u * near, fade * base)
            p.setOpacity(base)
            star(p, front.x(), front.y(), 11 * u * near, "#ffffff", 0.7 * fade)
    p.restore()


# The neon frame (as 赛博 has it) ------------------------------------------------------------------


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


def _frame_glow(width: float, height: float, outer: list[QPointF], inner: list[QPointF], u: float) -> tuple[QImage, ...]:
    """The light the two tubes throw, worked out per pixel at a quarter of the size: soft anyway.
    It dies out within GLOW_BAND of the edges, so only those bands need laying on. The cyan tube's,
    the magenta's, and both together for while they are lit alike."""
    w, h = max(1, round(width * SOFT)), max(1, round(height * SOFT))
    x, y, _clear, _rim = _field(width, height, u)
    edge = np.minimum(np.minimum(x, width - x), np.minimum(y, height - y))
    fade = 1 - smooth(GLOW_BAND * 0.6 * u, GLOW_BAND * u, edge)
    lights = []
    for points, tint in ((outer, CYAN), (inner, MAGENTA)):

        def draw(q: QPainter, points: list[QPointF] = points) -> None:
            q.scale(SOFT, SOFT)
            q.setPen(QPen(Qt.white, 5 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            q.drawPath(polyline(points))

        core = mask(w, h, draw)
        tinted = rgb(tint)
        halo = blur(core, 1.5) * 1.1 + blur(core, 5) * 0.9 + blur(core, 14) * 0.7
        lights.append((halo[..., None] * tinted + (core ** 1.5)[..., None] * (tinted * 0.5 + 0.28)) * fade[..., None])
    return tuple(_ready(glow(light)) for light in (lights[0], lights[1], lights[0] + lights[1]))


def _lay_round(p: QPainter, image: QImage, width: float, height: float, inner: QRectF) -> None:
    """A screen-sized soft picture that is clear over inner, laid on only round it: four pieces cut
    on its own pixels, so they meet without a seam."""
    w, h = image.width(), image.height()
    left, right = round(inner.left() * w / width), round(inner.right() * w / width)
    top, bottom = round(inner.top() * h / height), round(inner.bottom() * h / height)
    for x, y, x2, y2 in ((0, 0, w, top), (0, bottom, w, h), (0, top, left, bottom), (right, top, w, bottom)):
        if x2 > x and y2 > y:
            source = QRectF(x, y, x2 - x, y2 - y)
            p.drawImage(QRectF(x * width / w, y * height / h, (x2 - x) * width / w, (y2 - y) * height / h), image, source)


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
    p: QPainter, t: float, outer: list[QPointF], inner: list[QPointF], glows: tuple[QImage, ...], tubes: list, lights: dict,
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
    parts = ((outer, CYAN, tubes[0], 1.12), (inner, MAGENTA, tubes[1], 1.24))
    levels = [_neon(t, on, index) * _power_down(t, index) for index, (*_rest, on) in enumerate(parts)]
    inside = QRectF(0, 0, width, height).adjusted(GLOW_BAND * u, GLOW_BAND * u, -GLOW_BAND * u, -GLOW_BAND * u)
    # Lit alike, the two tubes' light is laid on as one picture.
    alike = min(levels) > 0 and abs(levels[0] - levels[1]) < 0.08
    for light, level in ((glows[2], sum(levels) / 2),) if alike else zip(glows, levels, strict=False):
        if level > 0:
            p.setOpacity(base * level)
            _lay_round(p, light, width, height, inside)
            if bright > 0.05:
                p.setCompositionMode(QPainter.CompositionMode_Plus)
                p.setOpacity(base * level * bright * 0.7)
                _lay_round(p, light, width, height, inside)
                p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    for index, ((points, tint, strips, on), level) in enumerate(zip(parts, levels, strict=True)):
        lit = max(level, 0.55 if t < on + 0.3 else 0.0)
        if lit <= 0:
            continue
        if trace >= 1:
            p.setOpacity(base * lit)
            for rect, image in strips:
                p.drawImage(rect, image)
            continue
        corner = min(range(len(points)), key=lambda i: points[i].x() + points[i].y())
        for half in (points[corner::-1], points[corner:]):
            path = polyline(partial(half, trace))
            p.setOpacity(base)
            _tube(p, path, tint, lit, 7 * u)
            if index == 0:
                head = path.currentPosition()
                fade = 1 - win(trace, 0.7, 0.97)
                _lay(p, lights["cyan"], head.x(), head.y(), 26 * u, 0.8 * fade * base)
                _lay(p, lights["hot"], head.x(), head.y(), 10 * u, fade * base)
                p.setOpacity(base)
                star(p, head.x(), head.y(), 13 * u, "#ffffff", 0.85 * fade)
    p.restore()


# Lightning and sparks (as 赛博 has them) -----------------------------------------------------------


def _dot(tint: str, white: float, side: int = 64) -> QImage:
    """A round glow as a picture: a hot middle going white by white, the tint round it fading out."""
    ys, xs = np.mgrid[0:side, 0:side].astype(np.float32)
    r = np.hypot(xs - (side - 1) / 2, ys - (side - 1) / 2) / (side / 2)
    halo = np.exp(-((r * 2.4) ** 2)) * 0.75 + np.exp(-r * 5.5) * 0.5
    core = np.exp(-((r * 9) ** 2))
    fade = np.clip((1 - r) * 4, 0, 1)
    color = rgb(tint)
    light = (halo[..., None] * color + core[..., None] * (color * 0.5 + white)) * fade[..., None]
    return _ready(glow(light.astype(np.float32)))


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
    h, w = core.shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    edge = np.minimum(np.minimum(xs, w - 1 - xs), np.minimum(ys, h - 1 - ys))
    light *= smooth(0, pad * k, edge)[..., None]
    return box, _ready(glow(light))


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
        _lay(p, lights["violet"], end.x(), end.y(), 210 * u, 0.55 * light * base)
        _lay(p, lights["cyan"], end.x(), end.y(), 120 * u, 0.8 * light * base)
        _lay(p, lights["hot"], end.x(), end.y(), 42 * u, light * base)
        _lay(p, lights["violet"], start.x(), start.y(), 200 * u, 0.6 * light * base)
    p.setOpacity(base)
    p.setBrush(Qt.NoBrush)
    for delay, tint in ((0.0, CYAN), (0.07, MAGENTA)):
        k = win(age - delay, 0.0, 0.38)
        if 0 < k < 1:
            r = (14 + 80 * ease_out(k)) * u
            p.setPen(QPen(col(tint, 0.85 * (1 - k) ** 2), (3.2 - 2 * k) * u))
            p.drawEllipse(end, r, r)
    p.restore()


def _spire(p: QPainter, age: float, tip: QPointF, lights: dict, u: float, seed: int) -> None:
    """A struck spire: its tip glowing hot and cooling, and little arcs crawling down it."""
    if age < 0 or age > 0.9:
        return
    p.save()
    base = p.opacity()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    cool = (1 - age / 0.9) ** 2
    _lay(p, lights["violet"], tip.x(), tip.y() + 6 * u, 30 * u, 0.6 * cool * base)
    _lay(p, lights["hot"], tip.x(), tip.y(), 9 * u, cool * base)
    p.setOpacity(base)
    for i in range(3):
        start = 0.08 + 0.17 * i
        k = win(age, start, start + 0.16)
        if 0 < k < 1:
            rnd = random.Random(seed * 100 + i + int(age * 30))
            a = QPointF(tip.x() + rnd.uniform(-2, 2) * u, tip.y() + rnd.uniform(4, 18) * u)
            b = QPointF(a.x() + rnd.choice((-1, 1)) * rnd.uniform(8, 16) * u, a.y() + rnd.uniform(10, 26) * u)
            path = polyline(_bolt_points(a, b, rnd, 0.25, 4))
            p.setBrush(Qt.NoBrush)
            for w, color, alpha in ((6, CYAN, 0.3), (2.4, "#9ffcff", 0.75), (1.0, "#ffffff", 1.0)):
                p.setPen(QPen(col(color, alpha * (1 - k)), w * u * 0.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                p.drawPath(path)
    p.restore()


def _shower(at: QPointF, aim: float, count: int, u: float, seed: int, width: float, height: float, keep: tuple[QRectF, ...]) -> tuple[np.ndarray, ...]:
    """Molten sparks thrown from at, most toward aim (radians), flown once here: under gravity and
    drag, bouncing off the bottom tube and the screen's sides. A spark is gone once it reaches the
    names, the title or the gap. Returns (tracks; when each leaves; how long it lives; when it is
    gone; its size)."""
    rng = np.random.default_rng(seed)
    embers = count // 6
    n = count + embers
    speed = np.concatenate([rng.uniform(150, 460, count) * (1 + rng.exponential(0.25, count)), rng.uniform(40, 150, embers)])
    angle = aim + rng.normal(0, 0.75, n)
    vel = np.stack([np.cos(angle), np.sin(angle)], axis=1) * speed[:, None] * u
    pos = np.tile(np.array([at.x(), at.y()], dtype=np.float64), (n, 1)) + rng.normal(0, 2 * u, (n, 2))
    life = np.concatenate([rng.uniform(0.45, 1.1, count), rng.uniform(0.8, 1.2, embers)]) * (1.15 - 0.3 * np.clip(speed / 600, 0, 1))
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


# The marks ---------------------------------------------------------------------------------------

# Pictures of the marks, made once for each size and sharpness they are shown at.
_ART: dict[tuple, object] = {}
# The marks' windows reach this far past what they mark (ui_overlay's _GLOW).
_ROOM = 9.0


def _kept(key: tuple, build):  # noqa: ANN001, ANN202
    if key not in _ART:
        if len(_ART) > 48:
            _ART.clear()
        _ART[key] = build()
    return _ART[key]


def _flick(t: float, on: float, period: float) -> float:
    """How lit a mark's tube is, t seconds after the mark showed: stuttering on at on, then humming,
    and once a period stuttering again, as a tired tube does."""
    age = t - on
    if age < 0:
        return 0.0
    for end, level in ((0.05, 1.0), (0.1, 0.12), (0.16, 0.85), (0.2, 0.05), (0.26, 0.7), (0.3, 0.3), (0.36, 0.9)):
        if age < end:
            return level
    again = (age - 0.36) % period - (period - 0.3)
    if again > 0:
        for end, level in ((0.04, 0.3), (0.08, 1.0), (0.13, 0.15), (0.3, 0.95)):
            if again < end:
                return level
    return 0.94 + 0.06 * math.sin(t * 21) * math.sin(t * 6.7)


def _mark_glow(area: QRectF, scale: float, draw, tint: str, spread: float, fade: float = _ROOM * 0.8) -> QImage:  # noqa: ANN001
    """The bloom of a mark's tube, per pixel: draw paints the tube in white, spread its reach in
    points. It fades out over fade points toward the window's edges, so they never cut it off."""
    core = _over(area, scale, draw)
    color = rgb(tint)
    halo = blur(core, 0.8 * scale) * 1.2 + blur(core, 2.8 * scale * spread) * 1.1 + blur(core, 6.5 * scale * spread) * 0.85
    light = halo[..., None] * color + (core ** 1.5)[..., None] * (color * 0.5 + 0.35)
    h, w = core.shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    edge = np.minimum(np.minimum(xs, w - 1 - xs), np.minimum(ys, h - 1 - ys))
    return glow(light * smooth(0, fade * scale, edge)[..., None])


def _unlit(p: QPainter, path: QPainterPath, width: float) -> None:
    """A neon tube switched off: pale glass, a highlight along its top."""
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(col("#6a5a80", 0.55), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(path)
    p.setPen(QPen(col("#efe6ff", 0.32), width * 0.3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(path.translated(0, -width * 0.18))


def _ring_art(cover: QRectF, scale: float) -> tuple[QRectF, QImage, QImage, QImage]:
    """The button's neon tube: one magenta tube bent round it, its ends meeting at the bottom left in
    two electrodes, held by clips. Pictures of it off, lit with its bloom, and its hardware."""
    area = cover.adjusted(-_ROOM, -_ROOM, _ROOM, _ROOM)
    tube = 3.0
    body = cover.adjusted(1.8, 1.8, -1.8, -1.8)
    r = min(11.0, body.height() * 0.2)
    left, top, right, bottom = body.left(), body.top(), body.right(), body.bottom()
    ends = (left + r + 6, left + r + 17)
    path = QPainterPath(QPointF(ends[1], bottom))
    path.lineTo(right - r, bottom)
    path.arcTo(QRectF(right - 2 * r, bottom - 2 * r, 2 * r, 2 * r), 270, 90)
    path.lineTo(right, top + r)
    path.arcTo(QRectF(right - 2 * r, top, 2 * r, 2 * r), 0, 90)
    path.lineTo(left + r, top)
    path.arcTo(QRectF(left, top, 2 * r, 2 * r), 90, 90)
    path.lineTo(left, bottom - r)
    path.arcTo(QRectF(left, bottom - 2 * r, 2 * r, 2 * r), 180, 90)
    path.lineTo(ends[0], bottom)

    def stroke(q: QPainter) -> None:
        q.setPen(QPen(Qt.white, tube, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        q.drawPath(path)

    light = _mark_glow(area, scale, stroke, MAGENTA, 1.0)

    def lit(q: QPainter) -> None:
        q.drawImage(area, light)
        _tube(q, path, MAGENTA, 1.0, tube)

    def hardware(q: QPainter) -> None:
        # The electrodes: dark metal caps on the tube's two ends.
        for x, way in ((ends[0], 1), (ends[1], -1)):
            cap = QRectF(x - (5 if way > 0 else 0), bottom - 2.4, 5, 4.8)
            _metal(q, cap, 1.4)
            q.setPen(QPen(col("#120c1c", 0.9), 0.9))
            q.drawLine(QLineF(x + way * 0.5, bottom + 2.4, x + way * 0.5, bottom + 5.5))
        # Clips holding it to the wall.
        w, h = body.width(), body.height()
        for at in (QPointF(left + w * 0.3, top), QPointF(left + w * 0.7, top), QPointF(left + w * 0.72, bottom)):
            _metal(q, QRectF(at.x() - 1.3, at.y() - 3.2, 2.6, 6.4), 0.6)
        for at in (QPointF(left, top + h / 2), QPointF(right, top + h / 2)):
            _metal(q, QRectF(at.x() - 3.2, at.y() - 1.3, 6.4, 2.6), 0.6)

    return area, _baked(area, scale, lambda q: _unlit(q, path, tube)), _baked(area, scale, lit), _baked(area, scale, hardware)


def _metal(q: QPainter, rect: QRectF, radius: float) -> None:
    """A little piece of dark metal, lit from above."""
    q.setPen(QPen(col("#0e0a16", 0.9), 0.6))
    shade = col("#2c2540")
    q.setBrush(shade)
    q.drawRoundedRect(rect, radius, radius)
    q.setPen(QPen(col("#8d82ad", 0.8), 0.6))
    q.drawLine(QLineF(rect.left() + radius * 0.6, rect.top() + 0.5, rect.right() - radius * 0.6, rect.top() + 0.5))


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    """The button ringed by a magenta neon tube that stutters on, hums, and now and then flickers."""
    scale = max(1.0, _sharpness(p))
    area, off, lit, hardware = _kept(("ring", round(cover.width(), 1), round(cover.height(), 1), scale), lambda: _ring_art(cover, scale))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(area, off)
    level = _flick(t, 0.0, 6.2)
    if level > 0:
        p.setOpacity(level)
        p.drawImage(area, lit)
        p.setOpacity(1.0)
    p.drawImage(area, hardware)


def _star_path(at: QPointF, r: float, inner: float) -> QPainterPath:
    path = QPainterPath()
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        d = r if i % 2 == 0 else inner
        point = QPointF(at.x() + math.cos(a) * d, at.y() + math.sin(a) * d)
        if i:
            path.lineTo(point)
        else:
            path.moveTo(point)
    path.closeSubpath()
    return path


def _plate(area: QRectF, rect: QRectF, scale: float, radius: float) -> QImage:
    """A dark sign plate over area, per pixel: smoked violet acrylic with a faint grain and sheen, a
    lit bevel along its top left and a dark one at its bottom right."""

    def shape(q: QPainter) -> None:
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawRoundedRect(rect, radius, radius)

    m = _over(area, scale, shape)
    x, y = _grid(area, m.shape)
    v = np.clip((y - rect.top()) / rect.height(), 0, 1)
    color = rgb("#1d0f44") * (1 - v)[..., None] + rgb("#08041c") * v[..., None]
    h, w = m.shape
    grain = noise(w, h, max(2.0, 2.5 * scale), 2, 3)
    color = color * (0.86 + 0.28 * grain)[..., None]
    sheen = np.exp(-(((x - rect.left()) * 0.55 + (y - rect.top()) - rect.height() * 0.32) / (rect.height() * 0.16)) ** 2)
    color += rgb("#bfb3ff") * (sheen * 0.08)[..., None]
    k = max(1, round(1.0 * scale))
    lit = np.clip(m - np.roll(np.roll(m, k, axis=0), k, axis=1), 0, 1)
    shade = np.clip(m - np.roll(np.roll(m, -k, axis=0), -k, axis=1), 0, 1)
    color = color * (1 - shade * 0.6)[..., None] + rgb("#a79ad6") * (lit * 0.55)[..., None]
    return picture(color, m * 0.95)


def _badge_art(box: QRectF, scale: float) -> tuple[QRectF, QImage, QImage, QImage]:
    """The neon star sign: a dark plate with four screws, a cyan star tube on it. Pictures of the
    plate, the tube off, and the tube lit with its bloom."""
    area = box.adjusted(-_ROOM, -_ROOM, _ROOM, _ROOM)
    side = box.width()
    plate = box.adjusted(side * 0.05, side * 0.05, -side * 0.05, -side * 0.05)
    back = _plate(area, plate, scale, side * 0.2)
    at = QPointF(box.center().x(), box.center().y() + side * 0.03)
    path = _star_path(at, side * 0.33, side * 0.145)
    tube = max(1.6, side * 0.055)

    def stroke(q: QPainter) -> None:
        q.setPen(QPen(Qt.white, tube, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        q.drawPath(path)

    light = _mark_glow(area, scale, stroke, CYAN, side / 56)

    def plated(q: QPainter) -> None:
        q.drawImage(area, back)
        for dx, dy in ((0.15, 0.15), (0.85, 0.15), (0.15, 0.85), (0.85, 0.85)):
            screw = QPointF(plate.left() + plate.width() * dx, plate.top() + plate.height() * dy)
            q.setPen(Qt.NoPen)
            q.setBrush(col("#463c63"))
            q.drawEllipse(screw, side * 0.028, side * 0.028)
            q.setBrush(col("#b4a8dc", 0.8))
            q.drawEllipse(QPointF(screw.x() - side * 0.008, screw.y() - side * 0.008), side * 0.011, side * 0.011)

    def lit(q: QPainter) -> None:
        q.drawImage(area, light)
        _tube(q, path, CYAN, 1.0, tube)

    return area, _baked(area, scale, plated), _baked(area, scale, lambda q: _unlit(q, path, tube)), _baked(area, scale, lit)


def badge(p: QPainter, box: QRectF, t: float) -> None:
    """A cyan neon star on a dark sign plate, stuttering on just after the ring."""
    scale = max(1.0, _sharpness(p))
    area, plate, off, lit = _kept(("badge", round(box.width(), 1), scale), lambda: _badge_art(box, scale))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(area, plate)
    p.drawImage(area, off)
    level = _flick(t, 0.2, 5.3)
    if level > 0:
        p.setOpacity(level)
        p.drawImage(area, lit)
        p.setOpacity(1.0)


def _drops(color: np.ndarray, x: np.ndarray, y: np.ndarray, beads: list[tuple[float, float, float]], scale: float) -> None:
    """Raindrops beaded on glass, shaded per pixel into color: each a little lens, dark at its top
    edge, bright at its bottom where the light comes through, a sharp highlight up and left, and a
    faint shadow ring round it."""
    for cx, cy, r in beads:
        box = (slice(max(0, int((cy - r * 1.6 - y[0, 0]) * scale)), int((cy + r * 1.6 - y[0, 0]) * scale) + 2),
               slice(max(0, int((cx - r * 1.6 - x[0, 0]) * scale)), int((cx + r * 1.6 - x[0, 0]) * scale) + 2))  # fmt: skip
        dx, dy = (x[box] - cx) / r, (y[box] - cy) / r
        d = np.hypot(dx, dy)
        edge = 1.0 / max(1.0, r * scale)
        inside = 1 - smooth(1 - edge, 1 + edge, d)
        ring = smooth(0.95, 1.1, d) * (1 - smooth(1.1, 1.5, d))
        dark = smooth(0.35, 1.0, d) * smooth(0.2, -0.9, dy) * 0.7
        bright = smooth(-0.1, 0.8, dy) * (1 - smooth(0.75, 1.0, d)) * smooth(0.2, 0.75, d)
        shine = np.exp(-((dx + 0.3) ** 2 + (dy + 0.4) ** 2) / 0.05)
        patch = color[box]
        patch *= (1 - ring * 0.4 - inside * dark)[..., None]
        patch += (inside * bright)[..., None] * rgb("#e7a0ff") * 0.6 + (inside * shine)[..., None] * 0.7


def _card_art(rect: QRectF, scale: float) -> tuple[QImage, QImage, QImage, QImage]:
    """The billboard: wet smoked glass per pixel with city lights blurred in it, raindrops beaded on
    it and two clear runs where drops slid down; its magenta tube off and lit with its bloom; and
    the little plate on its top edge with a cyan diamond."""
    body = rect.adjusted(0.5, CARD_TOP + 0.5, -0.5, -0.5)
    radius = 5.0

    def shape(q: QPainter) -> None:
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawRoundedRect(body, radius, radius)

    m = _over(rect, scale, shape)
    h, w = m.shape
    x, y = _grid(rect, m.shape)
    v = np.clip((y - body.top()) / body.height(), 0, 1)
    color = rgb("#1d0e44") * (1 - v)[..., None] + rgb("#0a0520") * v[..., None]
    rnd = random.Random(int(body.width() * 7 + body.height()))
    # City lights far behind the glass, out of focus.
    for _ in range(8):
        cx, cy = body.left() + rnd.uniform(0, body.width()), body.top() + body.height() * rnd.uniform(0.3, 1.0)
        r = rnd.uniform(5, 12)
        d = np.hypot(x - cx, y - cy) / r
        disc = (1 - smooth(0.85, 1.0, d)) * (0.55 + 0.45 * smooth(0.5, 0.95, d))
        color += disc[..., None] * rgb(rnd.choice(("#ffb46a", "#ffb46a", CYAN, MAGENTA, "#7f6bff"))) * rnd.uniform(0.08, 0.16)
    mist = noise(w, h, max(2.0, 4 * scale), 3, 12)
    runs = [body.left() + body.width() * rnd.uniform(0.15, 0.85) for _ in range(2)]
    clear = np.zeros_like(m)
    for run in runs:
        clear = np.maximum(clear, np.exp(-(((x - run) / 1.6) ** 2)) * smooth(body.top() + 4, body.top() + body.height() * 0.5, y))
    color = color * (0.86 + 0.26 * mist * (1 - clear))[..., None] * (1 - 0.25 * clear)[..., None]
    sheen = np.exp(-(((x - body.left()) * 0.5 + (y - body.top()) - body.height() * 0.15) / (body.height() * 0.22)) ** 2)
    color += rgb("#c8bfff") * (sheen * 0.08)[..., None]
    beads = []
    for _ in range(int(body.width() * body.height() / 120)):
        r = rnd.uniform(0.8, 1.4) if rnd.random() < 0.65 else rnd.uniform(1.6, 2.8)
        beads.append((body.left() + rnd.uniform(3, body.width() - 3), body.top() + rnd.uniform(3, body.height() - 3), r))
    for run in runs:
        for k in range(4):
            beads.append((run + rnd.uniform(-0.8, 0.8), body.top() + body.height() * (0.55 + 0.1 * k), rnd.uniform(0.5, 0.9)))
    _drops(color, x, y, beads, scale)
    glass = _ready(picture(color, m * 0.94))
    tube = 2.2
    frame = QPainterPath()
    frame.addRoundedRect(body.adjusted(2.6, 2.6, -2.6, -2.6), radius - 1.5, radius - 1.5)

    def stroke(q: QPainter) -> None:
        q.setPen(QPen(Qt.white, tube, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        q.drawPath(frame)

    light = _mark_glow(rect, scale, stroke, MAGENTA, 0.8, 2.0)
    tag = QRectF(body.center().x() - 17, 0.8, 34, CARD_TOP + 4.5)
    mark = _diamond(QPointF(tag.center().x(), tag.center().y()), tag.height() * 0.28, tag.height() * 0.36)
    for way in (-1, 1):
        mark.moveTo(tag.center().x() + way * 5.5, tag.center().y())
        mark.lineTo(tag.center().x() + way * 11.5, tag.center().y())

    def lit(q: QPainter) -> None:
        q.drawImage(rect, light)
        _tube(q, frame, MAGENTA, 1.0, tube)

    def off(q: QPainter) -> None:
        _unlit(q, frame, tube)
        q.setPen(QPen(col("#5a4c7a", 0.9), 0.8))
        q.setBrush(col("#0d0722", 0.96))
        q.drawRoundedRect(tag, 2.5, 2.5)
        q.setPen(QPen(col("#a79ad6", 0.7), 0.6))
        q.drawLine(QLineF(tag.left() + 2.5, tag.top() + 0.6, tag.right() - 2.5, tag.top() + 0.6))

    def mark_stroke(q: QPainter) -> None:
        q.setPen(QPen(Qt.white, 1.3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        q.drawPath(mark)

    mark_light = _mark_glow(rect, scale, mark_stroke, CYAN, 0.4, 2.0)

    def sign(q: QPainter) -> None:
        q.drawImage(rect, mark_light)
        _tube(q, mark, CYAN, 1.0, 1.3)

    return glass, _baked(rect, scale, off), _baked(rect, scale, lit), _baked(rect, scale, sign)


def _diamond(at: QPointF, half_width: float, half_height: float) -> QPainterPath:
    path = QPainterPath(QPointF(at.x(), at.y() - half_height))
    path.lineTo(at.x() + half_width, at.y())
    path.lineTo(at.x(), at.y() + half_height)
    path.lineTo(at.x() - half_width, at.y())
    path.closeSubpath()
    return path


def _bead(scale: float) -> QImage:
    """One raindrop on the glass, a picture to slide down it."""
    r = 2.2
    rect = QRectF(-r * 1.6, -r * 1.6, r * 3.2, r * 3.2)
    side = max(4, math.ceil(rect.width() * scale))
    x, y = _grid(rect, (side, side))
    color = np.zeros((side, side, 3), dtype=np.float32) + rgb("#120830")
    _drops(color, x, y, [(0.0, 0.0, r)], scale)
    d = np.hypot(x, y) / r
    return _ready(picture(color, (1 - smooth(0.9, 1.45, d)) * 0.95))


def card(p: QPainter, rect: QRectF, t: float) -> None:
    """The wet glass billboard: its tube flickering on, and every few seconds a drop running down."""
    scale = max(1.0, _sharpness(p))
    glass, off, lit, sign = _kept(("card", round(rect.width(), 1), round(rect.height(), 1), scale), lambda: _card_art(rect, scale))
    bead = _kept(("bead", scale), lambda: _bead(scale))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(rect, glass)
    body = rect.adjusted(4, CARD_TOP + 4, -4, -4)
    cycle, age = divmod(t + 1.2, 4.6)
    if age < 1.6 and body.height() > 8:
        rnd = random.Random(int(cycle))
        at = body.left() + body.width() * rnd.uniform(0.1, 0.9)
        k = (age / 1.6) ** 1.7
        top = body.top() + 2
        y = top + (body.height() - 4) * k
        fade = 1 - win(age, 1.35, 1.6)
        trail = QPainterPath(QPointF(at, top))
        trail.lineTo(at + 0.4, y)
        p.setPen(QPen(col("#05021a", 0.35 * fade), 1.6, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(trail)
        p.setOpacity(fade)
        side = bead.width() / scale
        p.drawImage(QRectF(at - side / 2, y - side / 2, side, side), bead)
        p.setOpacity(1.0)
    p.drawImage(rect, off)
    level = _flick(t, 0.1, 7.4)
    if level > 0:
        p.setOpacity(level)
        p.drawImage(rect, lit)
    p.setOpacity(_flick(t, 0.45, 8.1))
    p.drawImage(rect, sign)
    p.setOpacity(1.0)


def lead(size: float, index: int) -> QPixmap:
    """A cyan neon diamond, lit, with its bloom."""
    ratio = 3.0

    def build() -> QImage:
        rect = QRectF(0, 0, size, size)
        gem = _diamond(QPointF(size / 2, size / 2), size * 0.24, size * 0.34)
        tube = size * 0.09

        def stroke(q: QPainter) -> None:
            q.setPen(QPen(Qt.white, tube, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            q.drawPath(gem)

        light = _mark_glow(rect, ratio, stroke, CYAN, size / 40, size * 0.15)

        def draw(q: QPainter) -> None:
            q.drawImage(rect, light)
            _tube(q, gem, CYAN, 1.0, tube)
            q.setPen(Qt.NoPen)
            q.setBrush(col("#ffd6f6", 0.9))
            q.drawPath(_diamond(QPointF(size / 2, size / 2), size * 0.05, size * 0.07))

        return _baked(rect, ratio, draw)

    image = _kept(("lead", round(size, 2)), build)
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(ratio)
    return pixmap
