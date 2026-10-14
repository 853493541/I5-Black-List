"""毛茸茸: the screen becomes a teal notebook page, doodled by hand.

A white name tab drops in at the top middle, reading 毛茸茸保护协会, and from under it two pens draw
the screen's edge as a notebook frame: a wobbly ink line that swells and thins as a hand presses,
a lighter line inside it with a lift or two, and behind them a band of pale teal paper, grained per
pixel, filling in as they go. Enamel binder rings pop on down the right edge as the pen passes
them. Green crescent-leaf sprouts, each with a blue bead on its tip, pop up from the frame and sway:
a tall one in the bottom left, small ones on the left edge and in the bottom right. Puffy mint ❖
stars pop in round the top corners and down the sides and twinkle, with little sparkles, and
looping doodles draw themselves between them. Paw prints trot across the two bottom corners,
stamped one after another. At the end it all fades.

Its marks: the card is a notebook page in a teal frame with binder holes down its right, dotted
like a bullet journal, a sprout peeking over its top and a ❖ on its corner; the names are in a
rounded hand (幼圆 where it is installed), each after a mint or bead-blue ❖. The ring is a
hand-drawn double line round the button that boils as drawn lines do, with tiny paw prints trotting
round it; the badge is a fluffy white cat paw with pink pads that boops now and then.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPainterPathStroker, QPen, QPixmap, QPolygonF, QTransform

from blacklist_detect.love_scenes.draw import clamp, col, ease_back, ease_in, ease_out, soft_dot, spring, star, win
from blacklist_detect.love_scenes.light import blur, glow, mask, noise, picture, rgb

if TYPE_CHECKING:
    from collections.abc import Callable

    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
# Her colors: the pens' dark teal ink, teal, mint, the paper and its pale teal frame, the sprout's
# greens and its blue bead, the paw's pink, the light mint the doodles take on the dark game and
# the pale pink of the paw prints.
INK = "#2b6268"
TEAL = "#5fbdb8"
MINT = "#a8e6dc"
PAPER = "#fbfdfb"
BAND = "#a9d6d2"
LEAF = "#9ccf6e"
VEIN = "#4f8f3c"
BEAD = "#a6dcf6"
PINK = "#f6aabd"
CHALK = "#e2f7f2"
PRINT = "#ffd9e2"
LOOK = {
    "glow": (108, 205, 196),
    "rim": "#6fcfc6",
    "band": ("#6fcfc6", "#c4ece6"),
    "card": (PAPER, PAPER),
    "edge": "#6fc4bd",
    "ink": INK,
    "flowers": (("#f2fbf9", MINT, TEAL), ("#f3fbff", "#bfe3f6", "#7cc0e4")),
    "disc": (PAPER, "#d6f1ec"),
    "heart": (MINT, TEAL),
    "deep": "#4fb0aa",
    "deep_glow": (100, 200, 192),
}
MARKS_ANIMATED = True
# Room over the card for the sprout peeking over its top.
CARD_TOP = 15
# The binder holes down the card's right take room there.
CARD_PAD = (12, 8, 22, 8)
# A rounded hand; the app's Chinese face where it is not installed.
CARD_FONT = "YouYuan"

# Light from the top left, for the puffy stickers, and halfway between it and the eye, for their sheen.
LIGHT = np.array([-0.45, -0.6, 0.66]) / np.linalg.norm([-0.45, -0.6, 0.66])
HALF = (LIGHT + [0, 0, 1]) / np.linalg.norm(LIGHT + [0, 0, 1])
# The pens draw the frame over these seconds; the lighter line follows LAG behind.
PEN = (0.1, 1.4)
LAG = 0.12
# The ring's lines are redrawn this many times a second, a little differently each time, as a drawn line boils.
BOIL = 6


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(41)
    edge, right, corner = 16 * u, 32 * u, 26 * u
    # Two pens from the top middle, each round its side of the screen to its side of the gap.
    routes = []
    for x0, x1 in ((edge, gap.left() - 4 * u), (width - right, gap.right() + 4 * u)):
        corners = [(width / 2, edge, 0), (x0, edge, corner), (x0, height - edge, corner), (x1, height - edge, 10 * u), (x1, height + 2 * u, 0)]
        routes.append(_even(_fillet(corners), 2.5 * u))
    inside = np.vstack([routes[0][::-1], routes[1]])
    pens = [_frame_lines(route, side, rnd, u, gap) for route, side in zip(routes, (-1, 1), strict=True)]
    rings = _ring_stops(routes[1], width - right, edge + corner + 20 * u, height - edge - corner - 16 * u, 50 * u)
    tab = QRectF(width / 2 - 165 * u, 4 * u, 330 * u, 44 * u)
    # (where it grows from, how tall, its lean in degrees, when it pops up)
    sprouts = [
        (QPointF(96 * u, height - edge + 2 * u), 1.0, -6.0, 0.95),
        (QPointF(edge - 2 * u, height * 0.43), 0.42, 72.0, 1.25),
        (QPointF(width - 92 * u, height - edge + 2 * u), 0.5, 8.0, 1.6),
        (QPointF(width - 128 * u, height - edge + 2 * u), 0.36, -16.0, 1.72),
    ]
    # (x, y, radius, tint, when it pops in), from the corners they belong to.
    stars = [
        (70 * u, 74 * u, 24 * u, MINT, 0.75), (160 * u, 160 * u, 14 * u, BEAD, 1.05), (268 * u, 46 * u, 12 * u, MINT, 0.9),
        (46 * u, 300 * u, 17 * u, MINT, 1.2), (172 * u, 392 * u, 11 * u, BEAD, 1.45),
        (150 * u, height - 330 * u, 13 * u, MINT, 1.6),
        (width - 405 * u, 46 * u, 15 * u, BEAD, 0.95), (width - 300 * u, 136 * u, 23 * u, MINT, 0.8),
        (width - 150 * u, 72 * u, 17 * u, MINT, 1.1), (width - 92 * u, 236 * u, 12 * u, BEAD, 1.35),
        (width - 74 * u, height * 0.53, 11 * u, MINT, 1.55), (width - 238 * u, height - 106 * u, 12 * u, MINT, 2.0),
        (width / 2 - 215 * u, 28 * u, 10 * u, MINT, 0.6), (width / 2 + 215 * u, 28 * u, 10 * u, MINT, 0.65),
    ]  # fmt: skip
    doodles = [
        (_doodle(QPointF(186 * u, 172 * u), QPointF(520 * u, 120 * u), 4, 11 * u, rnd, u), 1.0, 1.8),
        (_doodle(QPointF(width - 470 * u, 222 * u), QPointF(width - 190 * u, 190 * u), 3, 11 * u, rnd, u), 1.3, 2.05),
    ]
    trails = [
        [(QPointF((150 + 44 * i) * u, height - (52 + (9 if i % 2 else -9)) * u), 1.5 + 0.2 * i) for i in range(8)],
        [(QPointF(width - (478 - 44 * i) * u, height - (54 + (9 if i % 2 else -9)) * u), 2.15 + 0.2 * i) for i in range(7)],
    ]
    # On a narrow window the prints near the gap are left out.
    trails = [[(at, when) for at, when in trail if not gap.left() - 24 * u < at.x() < gap.right() + 24 * u] for trail in trails]
    names = QRectF(width * 0.13, height * 0.29, width * 0.81, height * 0.55)
    title = QRectF(width * 0.38, height * 0.07, width * 0.3, height * 0.18)
    keep = (names, title.adjusted(-20 * u, 0, 20 * u, 0), gap.adjusted(-30 * u, -30 * u, 30 * u, 0))
    sparkles = []
    while len(sparkles) < 22:
        x, y = rnd.uniform(30 * u, width - 50 * u), rnd.uniform(30 * u, height - 30 * u)
        if not any(rect.contains(QPointF(x, y)) for rect in keep):
            sparkles.append((x, y, rnd.uniform(4, 8) * u, rnd.uniform(1.0, 4.0)))
    # Pictures worked out per pixel, for each sharpness they are shown at: (name, how), in the order
    # they are first wanted. Each is made when first wanted, or a frame or two ahead (see paint).
    makers = [
        ("band", lambda scale: _band(width, height, inside, u, scale)),
        ("tab", lambda scale: _tab(tab, u, scale)),
        *(
            (("star", r, tint), lambda scale, r=r, tint=tint: _star_sticker(r, tint, scale))
            for _x, _y, r, tint, _when in sorted(stars, key=lambda each: each[4])
        ),
        ("ring", lambda scale: _binder(11 * u, scale)),
        *(
            (f"sprout{index}", lambda scale, tall=tall, index=index: _sprout(118 * u * tall, scale, index))
            for index, (_base, tall, *_rest) in enumerate(sprouts)
        ),
        ("paw", lambda scale: _paw_print(34 * u, scale)),
    ]
    how = dict(makers)
    baked: dict[tuple, object] = {}

    def picture_of(name: object, scale: float) -> object:
        if (name, scale) not in baked:
            baked[name, scale] = how[name](scale)
        return baked[name, scale]

    def lined(scale: float) -> list:
        """The band with the frame's lines on it, once they are drawn."""
        if ("lined", scale) not in baked:
            out = []
            for rect, image in picture_of("band", scale):
                image = QImage(image)
                q = QPainter(image)
                q.setRenderHint(QPainter.Antialiasing)
                q.scale(scale, scale)
                q.translate(-rect.left(), -rect.top())
                for lines in pens:
                    for line in lines:
                        line.paint(q, line.length, 1.0)
                q.end()
                out.append((rect, image))
            baked["lined", scale] = out
        return baked["lined", scale]

    def paint(p: QPainter, t: float) -> None:
        a = win(t, 0.0, 0.3) * (1 - ease_in(win(t, 4.3, 5.0)))
        if a <= 0:
            return
        scale = _sharpness(p)
        p.save()
        p.setOpacity(a)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        drawn = _glide(win(t, *PEN))
        if drawn >= 1 and t >= PEN[1] + LAG:
            for rect, image in lined(scale):
                p.drawImage(rect, image)
        else:
            _reveal(p, picture_of("band", scale), pens, drawn, _glide(win(t, PEN[0] + LAG, PEN[1] + LAG)), width, height, u)
        for y, when in rings:
            k = win(t, when, when + 0.35)
            if k > 0:
                _place(p, picture_of("ring", scale), QPointF(width - right, y), 0.0, ease_back(k, 2.4))
        for line, start, end in doodles:
            line.paint(p, line.length * _glide(win(t, start, end)), 0.92)
        for index, (base, _tall, lean, when) in enumerate(sprouts):
            if t > when:
                # At the end each ducks back into the frame it grew from.
                duck = 1 - ease_in(win(t, 4.05 + 0.06 * index, 4.55 + 0.06 * index))
                _sprout_pop(p, t, picture_of(f"sprout{index}", scale), base, lean, when, u, duck)
        for index, (x, y, r, tint, when) in enumerate(stars):
            k = win(t, when, when + 0.45)
            if k <= 0:
                continue
            twinkle = 1 + 0.09 * math.sin(2.7 * (t - when) + index * 1.7)
            # At the end they shrink away one after another, spinning.
            gone = ease_in(win(t, 3.95 + 0.04 * index, 4.45 + 0.04 * index))
            image = picture_of(("star", r, tint), scale)
            angle = 35 * (1 - ease_out(k)) + 6 * math.sin(t * 0.9 + index) - 90 * gone
            _place(p, image, QPointF(x, y), angle, ease_back(k, 2.2) * twinkle * (1 - gone))
            # Now and then a sparkle catches its tip.
            glint = math.sin(math.pi * win((t - when - 0.6 - index * 0.37) % 2.3, 0, 0.5))
            if glint > 0.02 and t > when + 0.6:
                gx, gy = x + r * 0.95, y - r * 0.95
                soft_dot(p, gx, gy, r * 0.9, "#ffffff", 0.5 * glint)
                star(p, gx, gy, r * 0.75 * glint, "#ffffff", glint, 0.13)
        for x, y, r, when in sparkles:
            k = math.sin(math.pi * win(t, when, when + 0.6))
            if k > 0.02:
                soft_dot(p, x, y, r * 2.2, MINT, 0.45 * k)
                star(p, x, y, r * (0.6 + 0.6 * k), "#ffffff", k, 0.12)
        for trail in trails:
            for at, when in trail:
                k = win(t, when, when + 0.12)
                fade = 1 - ease_in(win(t, when + 1.7, when + 2.2))
                if k > 0 and fade > 0:
                    p.setOpacity(a * ease_out(k) * fade * 0.92)
                    _place(p, picture_of("paw", scale), at, 0.0, 1.3 - 0.3 * ease_out(k))
        p.setOpacity(a)
        # The tab drops in, swings, and at the end is lifted away.
        drop = ease_back(win(t, 0.05, 0.6), 1.6) - ease_in(win(t, 4.2, 4.75)) * 1.2
        if drop > 0:
            swing = 4 * spring(t - 0.5, 1.4, 3.0) if t > 0.5 else 0.0
            _place(p, picture_of("tab", scale), QPointF(tab.center().x(), tab.center().y() - 60 * u * (1 - drop)), swing, 1.0)
        p.restore()
        # One picture worked out ahead each frame, so no frame waits long for it.
        for name, _how in makers:
            if (name, scale) not in baked:
                picture_of(name, scale)
                break
        else:
            lined(scale)

    return paint


def _glide(k: float) -> float:
    """A hand drawing a long line: setting off and slowing at the end gently, steady between."""
    k = clamp(k)
    return k * k * (3 - 2 * k)


def _sharpness(p: QPainter) -> float:
    """Pixels per point where p draws: its screen's and its own scaling."""
    device = p.device()
    ratio = device.devicePixelRatioF() if device is not None else 1.0
    return round(ratio * math.hypot(p.transform().m11(), p.transform().m12()), 2)


def _place(p: QPainter, image: QImage, at: QPointF, angle: float, size: float, pivot: QPointF | None = None) -> None:
    """A picture made for _sticker put with its pivot (its middle unless given, in points from its
    top left) at at, turned about it by angle degrees and sized by size."""
    if size <= 0.01:
        return
    w, h = image.width() / image.devicePixelRatio(), image.height() / image.devicePixelRatio()
    pivot = pivot or QPointF(w / 2, h / 2)
    p.save()
    p.translate(at)
    if angle:
        p.rotate(angle)
    if abs(size - 1) > 1e-3:
        p.scale(size, size)
    p.drawImage(QRectF(-pivot.x(), -pivot.y(), w, h), image)
    p.restore()


# Lines as a hand draws them.


def _fillet(corners: list[tuple[float, float, float]]) -> np.ndarray:
    """A line through corners (x, y, r), each corner rounded off r along its sides: dense points."""
    pts = [np.array(c[:2], dtype=np.float64) for c in corners]
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        ab, cb = np.linalg.norm(a - b), np.linalg.norm(c - b)
        r = min(corners[i][2], ab / 2, cb / 2)
        p0, p1 = b + (a - b) / max(ab, 1e-9) * r, b + (c - b) / max(cb, 1e-9) * r
        for k in np.linspace(0, 1, 14):
            out.append((1 - k) ** 2 * p0 + 2 * (1 - k) * k * b + k * k * p1)
    out.append(pts[-1])
    return np.array(out)


def _even(points: np.ndarray, step: float, closed: bool = False) -> np.ndarray:
    """Points along a line every step apart."""
    if closed:
        points = np.vstack([points, points[:1]])
    seg = np.hypot(*np.diff(points, axis=0).T)
    points = np.vstack([points[:1], points[1:][seg > 1e-9]])
    s = np.concatenate([[0.0], np.cumsum(seg[seg > 1e-9])])
    at = np.linspace(0, s[-1], max(3, int(s[-1] / step) + 1))
    out = np.column_stack([np.interp(at, s, points[:, 0]), np.interp(at, s, points[:, 1])])
    return out[:-1] if closed else out


def _along(points: np.ndarray, closed: bool = False) -> np.ndarray:
    """How far along the line each point is."""
    step = np.hypot(*np.diff(np.vstack([points, points[:1]]) if closed else points, axis=0).T)
    return np.concatenate([[0.0], np.cumsum(step)])[: len(points)]


def _normals(points: np.ndarray, closed: bool = False) -> np.ndarray:
    """Each point's sideways unit: right of the way the line goes, on a screen."""
    d = np.roll(points, -1, 0) - np.roll(points, 1, 0) if closed else np.gradient(points, axis=0)
    d = d / np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-9)[:, None]
    return np.column_stack([-d[:, 1], d[:, 0]])


def _tremor(s: np.ndarray, rnd: random.Random, amp: float, wave: float, period: float = 0.0) -> np.ndarray:
    """A hand's slow tremor along a line, s along it: smooth and irregular, about amp at most. Round
    a closed line (period its length) it comes back to where it began."""
    out = np.zeros_like(s)
    for k, weight in ((1.0, 0.6), (2.3, 0.28), (5.2, 0.12)):
        cycles = s / (wave / k)
        if period:
            cycles = s / period * max(1, round(period / (wave / k)))
        out += weight * np.sin(2 * math.pi * cycles + rnd.uniform(0, 2 * math.pi))
    return out * amp


def _poly(points: np.ndarray) -> QPolygonF:
    return QPolygonF([QPointF(x, y) for x, y in points.tolist()])


def _ribbon(points: np.ndarray, widths: np.ndarray) -> QPainterPath:
    """A pen line of varying width through points, as its outline."""
    side = _normals(points) * (widths / 2)[:, None]
    path = QPainterPath()
    path.addPolygon(_poly(np.vstack([points + side, (points - side)[::-1]])))
    path.closeSubpath()
    path.setFillRule(Qt.WindingFill)
    return path


def _loop(points: np.ndarray, widths: np.ndarray) -> QPainterPath:
    """A closed pen line of varying width round points, as its outline."""
    side = _normals(points, closed=True) * (widths / 2)[:, None]
    path = QPainterPath()
    path.addPolygon(_poly(points + side))
    path.closeSubpath()
    path.addPolygon(_poly((points - side)[::-1]))
    path.closeSubpath()
    path.setFillRule(Qt.WindingFill)
    return path


def _inked(path: QPainterPath, width: float, rnd: random.Random) -> list[QPainterPath]:
    """The outline of a shape gone over in ink by hand: wobbling a little, pressing harder here and there."""
    out = []
    for polygon in path.toSubpathPolygons():
        points = np.array([(pt.x(), pt.y()) for pt in polygon], dtype=np.float64)
        if len(points) < 3:
            continue
        points = _even(points, max(0.25, width * 0.6), closed=True)
        s = _along(points, closed=True)
        period = s[-1] + np.hypot(*(points[0] - points[-1]))
        points = points + _normals(points, closed=True) * _tremor(s, rnd, width * 0.3, width * 9, period)[:, None]
        out.append(_loop(points, width * (1 + _tremor(s, rnd, 0.3, width * 14, period))))
    return out


class _Line:
    """A hand-drawn line of one or more strokes, each (points, widths, how far along the whole each
    point is), drawn as far along as wanted."""

    def __init__(self, strokes: list[tuple[np.ndarray, np.ndarray, np.ndarray]], color: str, tip: float) -> None:
        self.strokes = strokes
        self.color = color
        self.tip = tip
        self.whole = [_ribbon(points, widths) for points, widths, _at in strokes]
        self.length = max(at[-1] for _points, _widths, at in strokes)

    def paint(self, p: QPainter, reach: float, alpha: float) -> None:
        p.setPen(Qt.NoPen)
        p.setBrush(col(self.color, alpha))
        for (points, widths, at), whole in zip(self.strokes, self.whole, strict=True):
            if reach >= at[-1]:
                p.drawPath(whole)
                continue
            n = int(np.searchsorted(at, reach))
            if n >= 3:
                # The pen's round tip as it goes.
                p.drawPath(_ribbon(points[:n], widths[:n] * np.clip((reach - at[:n]) / self.tip, 0.45, 1)))

    def head(self, reach: float) -> QPointF | None:
        """Where the pen is, while it draws."""
        for points, _widths, at in self.strokes:
            if at[0] <= reach < at[-1]:
                n = min(len(at) - 1, int(np.searchsorted(at, reach)))
                return QPointF(*points[n])
        return None


def _stroke(
    points: np.ndarray, at: np.ndarray, width: float, rnd: random.Random, wobble: float, start: float = 10.0, end: float = 24.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """One pen stroke along points: wobbled sideways, its width swelling and thinning as the hand
    presses, tapering where the pen lands and lifts."""
    s = at - at[0]
    points = points + _normals(points) * _tremor(s, rnd, wobble, 160)[:, None]
    taper = np.clip(s / start, 0, 1) ** 0.6 * np.clip((s[-1] - s) / end, 0, 1) ** 0.6
    widths = width * (0.86 + _tremor(s, rnd, 0.32, 120)) * np.maximum(taper, 0.08)
    return points, widths, at


def _frame_lines(route: np.ndarray, side: int, rnd: random.Random, u: float, gap: QRectF) -> list[_Line]:
    """One pen's half of the frame: the ink line on the paper's edge, and a lighter one inside it,
    lifted twice, that stops short of the gap."""
    at = _along(route)
    main = _Line([_stroke(route, at, 3.0 * u, rnd, 1.1 * u, 2 * u, 14 * u)], INK, 4 * u)
    inner = route + _normals(route) * side * 6.5 * u
    near = (inner[:, 1] > route[-1][1] - 30 * u) & (np.abs(inner[:, 0] - gap.center().x()) < gap.width() / 2 + 34 * u)
    stop = int(np.argmax(near)) if near.any() else len(inner)
    lifts = [rnd.uniform(0.25, 0.4) * stop, rnd.uniform(0.62, 0.75) * stop]
    strokes, begin = [], 0
    for cut in [*lifts, stop]:
        end = int(cut)
        if end - begin > 6:
            strokes.append(_stroke(inner[begin:end], at[begin:end], 1.7 * u, rnd, 0.8 * u))
        begin = end + int(4 * u / 2.5) + 1
    return [main, _Line(strokes, CHALK, 4 * u)]


def _doodle(a: QPointF, b: QPointF, loops: int, size: float, rnd: random.Random, u: float) -> _Line:
    """A loopy doodle from a to b, as a pen trails between two stars."""
    theta = np.linspace(0, 2 * math.pi * loops + math.pi * 0.5, 160 * loops)
    span = math.hypot(b.x() - a.x(), b.y() - a.y())
    # A prolate trochoid: the pen circles faster than it goes forward, so the circles become loops.
    along = theta / theta[-1] * span - size * 2.4 * np.sin(theta)
    across = size * 1.3 * (np.cos(theta) - 1) - size * 0.8 * np.sin(theta / theta[-1] * math.pi)
    turn = math.atan2(b.y() - a.y(), b.x() - a.x())
    c, s = math.cos(turn), math.sin(turn)
    points = np.column_stack([a.x() + along * c - across * s, a.y() + along * s + across * c])
    points = _even(points, 1.6 * u)
    return _Line([_stroke(points, _along(points), 2.3 * u, rnd, 0.5 * u, 8 * u, 18 * u)], CHALK, 3 * u)


def _reveal(
    p: QPainter, bare: list, pens: list[list[_Line]], drawn: float, follow: float, width: float, height: float, u: float
) -> None:
    """The frame while the pens draw it: the paper filling in behind the ink line as it goes round
    from the top middle, the lines as far as they have come and a sparkle at each pen."""
    middle = QPointF(width / 2, height / 2)
    heads = [lines[0].head(lines[0].length * drawn) for lines in pens]
    if drawn > 0:
        # A slice of the screen from its middle, opening both ways from the top to the two pens.
        turn = [-90.0, -90.0]
        for index, head in enumerate(heads):
            if head is None:
                turn[index] = -270.0 if index == 0 else 90.0
            elif (head.x() < middle.x()) == (index == 0):
                # Left of the middle the slice opens backward, the other way round from -90°.
                angle = math.degrees(math.atan2(head.y() - middle.y(), head.x() - middle.x()))
                turn[index] = angle - 360 if index == 0 and angle > 0 else angle
        reach = math.hypot(width, height)
        slice_ = QPainterPath(middle)
        for k in np.linspace(turn[0], turn[1], 48):
            slice_.lineTo(middle.x() + reach * math.cos(math.radians(k)), middle.y() + reach * math.sin(math.radians(k)))
        slice_.closeSubpath()
        p.save()
        p.setClipPath(slice_)
        for rect, image in bare:
            p.drawImage(rect, image)
        p.restore()
    for lines in pens:
        main, inner = lines
        main.paint(p, main.length * drawn, 1.0)
        inner.paint(p, inner.length * follow, 1.0)
    for head in heads:
        if head is not None:
            soft_dot(p, head.x(), head.y(), 16 * u, MINT, 0.7)
            star(p, head.x(), head.y(), 9 * u, "#ffffff", 1.0, 0.14)


def _ring_stops(route: np.ndarray, x: float, top: float, bottom: float, step: float) -> list[tuple[float, float]]:
    """The binder rings down the right edge: each one's height, and when it pops on, just after the pen passes it."""
    at = _along(route)
    count = max(1, int((bottom - top) / step) + 1)
    out = []
    for k in range(count):
        y = top + (bottom - top) * k / max(1, count - 1)
        nearest = int(np.argmin(np.hypot(route[:, 0] - x, route[:, 1] - y)))
        out.append((y, _pen_time(at[nearest] / at[-1]) + 0.04))
    return out


def _pen_time(share: float) -> float:
    """When the pen has drawn share of its line."""
    ks = np.linspace(0, 1, 200)
    return PEN[0] + (PEN[1] - PEN[0]) * float(np.interp(share, [_glide(k) for k in ks], ks))


# Pictures worked out per pixel.


def _shade(
    masks: list[tuple[np.ndarray, str, float]], soft: float, gloss: float, grain: float, seed: int, shadow: float = 0.0
) -> QImage:
    """Shapes as soft rounded stickers lit from the top left: each mask (0..1) tinted its color, the
    whole swelling up from its edges over soft pixels and a part with lift swelling more, then lit,
    given a sheen and a paper grain, and a soft shadow under it shadow pixels down."""
    height, width = masks[0][0].shape
    color = np.zeros((height, width, 3), dtype=np.float32)
    alpha = np.zeros((height, width), dtype=np.float32)
    swell = np.zeros((height, width), dtype=np.float32)
    for m, tint, lift in masks:
        color += (rgb(tint) - color) * m[..., None]
        alpha = np.maximum(alpha, m)
        if lift:
            swell += blur(m, max(1.0, soft * 0.45)) * m * lift
    swell += blur(alpha, max(1.0, soft)) * alpha
    gy, gx = np.gradient(swell)
    nx, ny = -gx * soft * 5, -gy * soft * 5
    nz = 1 / np.sqrt(1 + nx * nx + ny * ny)
    nx, ny = nx * nz, ny * nz
    lit = np.clip(nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2], 0, 1)
    sheen = np.clip(nx * HALF[0] + ny * HALF[1] + nz * HALF[2], 0, 1) ** 26 * gloss
    texture = 1 + grain * (noise(width, height, 3.0, 2, seed) - 0.5) * 2
    # Flat parts keep their own color. Shade is cool, as in her drawings: teal creeps into what the light misses.
    shade = np.clip(1 + 0.55 * (lit - LIGHT[2]), 0, 1)[..., None]
    lit_color = color * shade * texture[..., None] + (1 - shade) * 0.18 * rgb(TEAL) + sheen[..., None]
    if shadow <= 0:
        return picture(lit_color, alpha)
    drop = blur(np.roll(alpha, max(1, round(shadow)), axis=0), max(1.0, shadow * 1.4)) * 0.32
    total = alpha + drop * (1 - alpha)
    under = rgb("#123a3e")
    mixed = (lit_color * alpha[..., None] + under * (drop * (1 - alpha))[..., None]) / np.maximum(total, 1e-4)[..., None]
    return picture(mixed, total)


def _sticker(
    box: QRectF,
    scale: float,
    parts: list[tuple[QPainterPath, str, float]],
    soft: float,
    outline: list[tuple[QPainterPath, float, str]] = (),
    *,
    gloss: float = 0.3,
    grain: float = 0.05,
    seed: int = 1,
    shadow: float = 0.0,
    after: Callable[[QPainter], None] | None = None,
) -> QImage:
    """Shapes in box (points) as one sticker of scale pixels to the point: the parts (path, color, lift)
    shaded per pixel, then outlined by hand in outline's (path, width, color), then after on top."""
    w, h = max(1, math.ceil(box.width() * scale)), max(1, math.ceil(box.height() * scale))

    def place(q: QPainter) -> None:
        q.scale(w / box.width(), h / box.height())
        q.translate(-box.left(), -box.top())

    masks = []
    for path, tint, lift in parts:

        def draw(q: QPainter, path: QPainterPath = path) -> None:
            place(q)
            q.fillPath(path, QColor("#ffffff"))

        masks.append((mask(w, h, draw), tint, lift))
    image = _shade(masks, soft * scale, gloss, grain, seed, shadow * scale).convertToFormat(QImage.Format_ARGB32_Premultiplied)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    place(q)
    rnd = random.Random(seed)
    for path, width, color in outline:
        for ink in _inked(path, width, rnd):
            q.fillPath(ink, col(color))
    if after is not None:
        after(q)
    q.end()
    image.setDevicePixelRatio(w / box.width())
    return image


def _band(width: float, height: float, inside: np.ndarray, u: float, scale: float) -> list[tuple[QRectF, QImage]]:
    """The pale teal paper round the screen, outside the frame's line, worked out per pixel as four
    pictures along the edges (the middle has none of it): a fine grain and soft blotches like real
    paper, and a little shade along its inner edge, where the page sits on it."""
    w, h = math.ceil(width * scale), math.ceil(height * scale)

    def draw(q: QPainter) -> None:
        q.scale(scale, scale)
        q.fillRect(QRectF(0, 0, width, height), QColor("#ffffff"))
        q.setPen(Qt.NoPen)
        q.setBrush(QColor("#000000"))
        q.drawPolygon(_poly(inside))

    full = mask(w, h, draw)
    reach = 64 * u
    rects = (
        QRectF(0, 0, width, reach), QRectF(0, height - reach, width, reach),
        QRectF(0, reach, reach, height - 2 * reach), QRectF(width - reach, reach, reach, height - 2 * reach),
    )  # fmt: skip
    out = []
    for index, rect in enumerate(rects):
        x0, y0 = round(rect.left() * scale), round(rect.top() * scale)
        x1, y1 = min(w, round(rect.right() * scale)), min(h, round(rect.bottom() * scale))
        paper = full[y0:y1, x0:x1]
        if paper.size == 0:
            continue
        ph, pw = paper.shape
        shade = blur(1 - paper, 3 * u * scale) * paper
        fibers = np.random.default_rng(7 + index).random((ph, pw), dtype=np.float32)
        grain = (blur(fibers, 0.8 * scale) - 0.5) * 3
        # Blotches are soft: worked out on a coarse grid and spread over it.
        step = 8
        coarse = noise(pw // step + 2, ph // step + 2, 46 * u * scale / step, 2, 17 + index) - 0.5
        blotch = coarse[np.arange(ph)[:, None] // step, np.arange(pw)[None, :] // step]
        tone = 1 + 0.07 * grain + 0.06 * blotch - 0.22 * shade
        color = rgb(BAND)[None, None, :] * tone[..., None] + (0.05 * (1 - shade))[..., None]
        image = picture(color, paper * 0.94).convertToFormat(QImage.Format_ARGB32_Premultiplied)
        out.append((QRectF(x0 / scale, y0 / scale, (x1 - x0) / scale, (y1 - y0) / scale), image))
    return out


def _binder(radius: float, scale: float) -> QImage:
    """A white enamel binder ring seen from the front, worked out per pixel as a torus lit from the
    top left, with a soft shadow on the paper and an inked rim."""
    side = math.ceil((radius * 2 + 8) * scale)
    ys, xs = np.mgrid[0:side, 0:side].astype(np.float32)
    c = (side - 1) / 2
    dx, dy = (xs - c) / scale, (ys - c) / scale
    rho = np.hypot(dx, dy) + 1e-6
    middle, tube = radius * 0.72, radius * 0.28
    off = rho - middle
    inside = np.clip((tube - np.abs(off)) * scale + 0.5, 0, 1)
    z = np.sqrt(np.clip(tube * tube - off * off, 0, None)) / tube
    radial = np.clip(off / tube, -1, 1)
    nx, ny, nz = radial * dx / rho, radial * dy / rho, z
    lit = np.clip(nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2], 0, 1)
    sheen = np.clip(nx * HALF[0] + ny * HALF[1] + nz * HALF[2], 0, 1) ** 30 * 0.9
    body = rgb("#eef8f6") * (0.55 + 0.5 * lit)[..., None] + (1 - lit)[..., None] * 0.2 * rgb(TEAL) + sheen[..., None]
    drop = blur(np.roll(np.roll(inside, round(1.5 * scale), 0), round(1 * scale), 1), 1.6 * scale) * 0.4
    total = inside + drop * (1 - inside)
    color = (body * inside[..., None] + rgb("#123a3e") * (drop * (1 - inside))[..., None]) / np.maximum(total, 1e-4)[..., None]
    image = picture(color, total).convertToFormat(QImage.Format_ARGB32_Premultiplied)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    q.scale(scale, scale)
    q.translate(c / scale, c / scale)
    rim = QPainterPath()
    rim.addEllipse(QPointF(0, 0), radius, radius)
    rim.addEllipse(QPointF(0, 0), radius * 0.44, radius * 0.44)
    for ink in _inked(rim, max(0.6, radius * 0.1), random.Random(3)):
        q.fillPath(ink, col(INK, 0.85))
    q.end()
    image.setDevicePixelRatio(scale)
    return image


def _star_path(r: float) -> QPainterPath:
    """Her ❖: four plump diamond petals round a middle, pointing up, down and to the sides."""
    petal = QPainterPath(QPointF(0, -r * 0.06))
    petal.quadTo(QPointF(r * 0.2, -r * 0.3), QPointF(r * 0.29, -r * 0.5))
    petal.quadTo(QPointF(r * 0.24, -r * 0.62), QPointF(0, -r))
    petal.quadTo(QPointF(-r * 0.24, -r * 0.62), QPointF(-r * 0.29, -r * 0.5))
    petal.quadTo(QPointF(-r * 0.2, -r * 0.3), QPointF(0, -r * 0.06))
    path = QPainterPath()
    for k in range(4):
        path.addPath(QTransform().rotate(90 * k).map(petal))
    return path.simplified()


def _star_sticker(r: float, tint: str, scale: float) -> QImage:
    """A puffy ❖ in tint, outlined in ink."""
    box = QRectF(-r * 1.25, -r * 1.25, r * 2.5, r * 2.5)
    shape = _star_path(r)
    outline = [(shape, max(0.7, r * 0.085), INK)]
    return _sticker(box, scale, [(shape, tint, 0)], max(1.0, r * 0.22), outline, gloss=0.55, grain=0.03, seed=5, shadow=max(0.6, r * 0.08))


def _leaf_path(size: float) -> QPainterPath:
    """A crescent leaf, size across, as a new moon opening up and to the right: its thick middle at
    the bottom left, its horns at the top and on the right."""
    disc = QPainterPath()
    disc.addEllipse(QPointF(0, 0), size / 2, size / 2)
    bite = QPainterPath()
    bite.addEllipse(QPointF(size * 0.24, -size * 0.24), size * 0.42, size * 0.42)
    return disc.subtracted(bite)


def _sprout_shapes(size: float, lean: float = 0.0) -> tuple[QPainterPath, QPainterPath, QPainterPath, QPainterPath, QRectF]:
    """A sprout growing from (0, 0) up: its stem, its crescent leaf, the leaf's veins and the blue
    bead on its upper horn, and the box round them all. size is the leaf's width."""
    stem_top = QPointF(size * 0.05, -size * 0.55)
    points = _even(np.array([[0, 0], [size * 0.07, -size * 0.25], [stem_top.x(), stem_top.y()]]), max(0.3, size * 0.02))
    wide = np.linspace(size * 0.09, size * 0.06, len(points))
    stem = _ribbon(points, wide)
    stem.addEllipse(stem_top, size * 0.03, size * 0.03)
    # The leaf meets the stem at its thick middle.
    place = QTransform().translate(stem_top.x(), stem_top.y()).rotate(lean).translate(size * 0.2, -size * 0.43)
    leaf = place.map(_leaf_path(size))
    vein = QPainterPath()
    mid = QRectF(size * 0.12 - size * 0.46, -size * 0.12 - size * 0.46, size * 0.92, size * 0.92)
    vein.arcMoveTo(mid, 136)
    vein.arcTo(mid, 136, 178)
    veins = _stroked(vein, max(0.3, size * 0.028))
    for angle in (185, 225, 265):
        rib = QPainterPath()
        rib.arcMoveTo(mid, angle)
        start = rib.currentPosition()
        rib.lineTo(start.x() + (start.x() - size * 0.12) * 0.17, start.y() + (start.y() + size * 0.12) * 0.17)
        veins.addPath(_stroked(rib, max(0.25, size * 0.018)))
    veins = place.map(veins).intersected(leaf)
    bead = QPainterPath()
    bead.addEllipse(place.map(QPointF(-size * 0.1, -size * 0.52)), size * 0.09, size * 0.09)
    box = stem.boundingRect().united(leaf.boundingRect()).united(bead.boundingRect())
    return stem, leaf, veins, bead, box


def _stroked(path: QPainterPath, width: float) -> QPainterPath:
    """path stroked width wide with round ends, as a shape."""
    stroker = QPainterPathStroker()
    stroker.setWidth(width)
    stroker.setCapStyle(Qt.RoundCap)
    return stroker.createStroke(path)


def _sprout(size: float, scale: float, seed: int) -> tuple[QImage, QPointF, float]:
    """Her crescent-leaf sprout as a sticker, where its stem's foot is in it (points from its top
    left), and how tall it stands."""
    stem, leaf, veins, bead, box = _sprout_shapes(size)
    box = box.adjusted(-size * 0.08, -size * 0.08, size * 0.08, size * 0.1)
    parts = [(stem, "#7fbf5a", 0), (leaf, LEAF, 0), (veins, VEIN, -0.3), (bead, BEAD, 1.2)]
    outline = [(stem.united(leaf), max(0.7, size * 0.022), INK), (bead, max(0.6, size * 0.016), INK)]
    soft, shadow = max(1.0, size * 0.07), max(0.6, size * 0.025)
    image = _sticker(box, scale, parts, soft, outline, gloss=0.45, grain=0.05, seed=11 + seed, shadow=shadow)
    return image, QPointF(-box.left(), -box.top()), -box.top()


def _sprout_pop(
    p: QPainter, t: float, sprout: tuple[QImage, QPointF, float], base: QPointF, lean: float, when: float, u: float, duck: float
) -> None:
    """A sprout popping up from base and swaying: it grows past its size and settles, then sways on;
    duck shrinks it back down. Three little lines spring from it as it pops, as in a doodle."""
    k = win(t, when, when + 0.55)
    if k <= 0:
        return
    image, foot, tall = sprout
    sway = 9 * spring(t - when - 0.25, 1.2, 2.4) * win(t, when + 0.25, when + 0.3) + 2.5 * math.sin(1.7 * t + base.x() * 0.01)
    _place(p, image, base, lean + sway, ease_back(k, 1.8) * duck, foot)
    burst = win(t, when + 0.2, when + 0.6)
    if 0 < burst < 1:
        p.setPen(QPen(col(CHALK, 0.9 * (1 - burst)), 2.2 * u, Qt.SolidLine, Qt.RoundCap))
        reach = tall * (0.95 + 0.25 * ease_out(burst))
        for angle in (-50, -15, 20):
            a = math.radians(angle - 90 + lean)
            inner, outer = reach, reach + 12 * u * (1 - 0.5 * burst)
            p.drawLine(
                QPointF(base.x() + math.cos(a) * inner, base.y() + math.sin(a) * inner),
                QPointF(base.x() + math.cos(a) * outer, base.y() + math.sin(a) * outer),
            )


def _paw_shapes(s: float) -> tuple[QPainterPath, QPainterPath]:
    """A cat's paw, s tall, toes up: its palm pad and its four toe beans."""
    palm = QPainterPath()
    palm.setFillRule(Qt.WindingFill)
    # Wide on top, three soft lobes along its bottom.
    palm.addEllipse(QPointF(0, 0.17 * s), 0.25 * s, 0.17 * s)
    for x, y, r in ((-0.13, 0.27, 0.11), (0, 0.29, 0.11), (0.13, 0.27, 0.11)):
        palm.addEllipse(QPointF(x * s, y * s), r * s, r * s)
    palm = palm.simplified()
    toes = QPainterPath()
    for x, y, angle in ((-0.33, -0.08, -25), (-0.12, -0.27, -8), (0.12, -0.27, 8), (0.33, -0.08, 25)):
        bean = QPainterPath()
        bean.addEllipse(QPointF(0, 0), 0.095 * s, 0.125 * s)
        toes.addPath(QTransform().translate(x * s, y * s).rotate(angle).map(bean))
    return palm, toes


def _paw_print(s: float, scale: float) -> QImage:
    """A paw print in pale pink, stamped: walking right, its ink grainy where the stamp missed."""
    palm, toes = _paw_shapes(s)
    turn = QTransform().rotate(90)
    shape = turn.map(palm).united(turn.map(toes))
    box = QRectF(-s * 0.62, -s * 0.62, s * 1.24, s * 1.24)
    w = math.ceil(box.width() * scale)

    def draw(q: QPainter) -> None:
        q.scale(scale, scale)
        q.translate(-box.left(), -box.top())
        q.fillPath(shape, QColor("#ffffff"))

    ink = mask(w, w, draw)
    speck = noise(w, w, 2.2 * scale, 2, 23)
    # A stamp leaves less ink toward its edges, and a little less in specks.
    edge = blur(ink, max(1.0, s * 0.05 * scale))
    alpha = ink * (0.78 + 0.22 * np.clip((speck - 0.25) * 4, 0, 1)) * np.clip(edge * 1.5, 0, 1)
    image = picture(np.broadcast_to(rgb(PRINT), (*ink.shape, 3)), alpha).convertToFormat(QImage.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(scale)
    return image


def _tab(tab: QRectF, u: float, scale: float) -> QImage:
    """The name tab: a white paper label in an inked edge, 毛茸茸保护协会 spaced out on it between two ❖."""
    shape = QPainterPath()
    shape.addRoundedRect(QRectF(-tab.width() / 2, -tab.height() / 2, tab.width(), tab.height()), 12 * u, 12 * u)
    stars = QPainterPath()
    for x in (-tab.width() / 2 + 22 * u, tab.width() / 2 - 22 * u):
        stars.addPath(QTransform().translate(x, 0).map(_star_path(10 * u)))
    stars = stars.simplified()
    box = QRectF(-tab.width() / 2 - 8 * u, -tab.height() / 2 - 8 * u, tab.width() + 16 * u, tab.height() + 16 * u)

    def words(q: QPainter) -> None:
        font = QFont()
        font.setFamilies(["YouYuan", "Microsoft YaHei", "Microsoft YaHei UI"])
        font.setPixelSize(max(1, round(20 * u)))
        font.setWeight(QFont.Weight.DemiBold)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 7 * u)
        q.setFont(font)
        q.setPen(col(INK))
        # The spacing follows the last character too: the box is that much wider, so the words sit in the middle.
        words_box = QRectF(-tab.width() / 2, -tab.height() / 2, tab.width() + 7 * u, tab.height())
        q.drawText(words_box, Qt.AlignCenter, "毛茸茸保护协会")

    parts = [(shape, PAPER, 0), (stars, MINT, 0.8)]
    outline = [(shape, 1.8 * u, INK), (stars, 0.9 * u, INK)]
    return _sticker(box, scale, parts, 3 * u, outline, gloss=0.12, grain=0.04, seed=9, shadow=2.5 * u, after=words)


# The marks, each drawn once for each size and sharpness it is shown at.

_MARKS: dict[tuple, object] = {}


def _mark(key: tuple, make_it: Callable[[], object]) -> object:
    if key not in _MARKS:
        _MARKS[key] = make_it()
    return _MARKS[key]


def _round_route(rect: QRectF, radius: float, step: float) -> np.ndarray:
    """Points round a rounded rectangle, clockwise from the middle of its top, step apart."""
    left, top, right, bottom, middle = rect.left(), rect.top(), rect.right(), rect.bottom(), rect.center().x()
    corners = [(middle, top, 0), (right, top, radius), (right, bottom, radius), (left, bottom, radius), (left, top, radius), (middle, top, 0)]
    return _even(_fillet(corners)[:-1], step, closed=True)


def _ring_lines(cover: QRectF, seed: int) -> tuple[QPainterPath, QPainterPath]:
    """The ring's two lines as a hand draws them: the outer one going round a little more than once,
    so its ends overlap, the inner one closed but lifted once."""
    rnd = random.Random(seed)
    radius = cover.height() * 0.3
    outer = _round_route(cover.adjusted(-2.5, -2.5, 2.5, 2.5), radius + 2.5, 1.2)
    n = len(outer)
    start = rnd.randrange(n)
    turns = np.arange(start, start + int(n * 1.07)) % n
    points = outer[turns]
    s = _along(points)
    # Spiralling out a little as it goes round, so the overlap shows.
    points = points - _normals(points) * (s / s[-1] * 2.2)[:, None]
    main = _ribbon(*_stroke(points, s, 2.6, rnd, 0.7, 10, 16)[:2])
    inner = _round_route(cover.adjusted(0.5, 0.5, -0.5, -0.5), radius, 1.2)
    lift = rnd.randrange(len(inner))
    inner = np.roll(inner, -lift, axis=0)[: int(len(inner) * 0.95)]
    thin = _ribbon(*_stroke(inner, _along(inner), 1.3, rnd, 0.45, 6, 6)[:2])
    return main, thin


def _ring_glow(cover: QRectF, scale: float) -> tuple[QRectF, QImage]:
    """A soft mint glow round the ring, per pixel."""
    area = cover.adjusted(-9, -9, 9, 9)
    w, h = math.ceil(area.width() * scale), math.ceil(area.height() * scale)

    def draw(q: QPainter) -> None:
        q.scale(scale, scale)
        q.translate(-area.left(), -area.top())
        q.setPen(QPen(QColor("#ffffff"), 3.5))
        q.setBrush(Qt.NoBrush)
        q.drawRoundedRect(cover.adjusted(-2.5, -2.5, 2.5, 2.5), cover.height() * 0.33, cover.height() * 0.33)

    line = mask(w, h, draw)
    light = (blur(line, 2.2 * scale) * 0.9 + blur(line, 5.5 * scale) * 0.7)[..., None] * rgb("#5fd6c8")
    return area, glow(light)


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    """A hand-drawn double line round the button, boiling, a mint glow under it, and tiny paw prints
    trotting round it."""
    scale = _sharpness(p)
    where = (round(cover.x(), 1), round(cover.y(), 1), round(cover.width(), 1), round(cover.height(), 1))
    area, light = _mark(("ring-glow", *where, scale), lambda: _ring_glow(cover, scale))
    p.save()
    p.setOpacity(0.75 + 0.25 * math.sin(t * 2.2))
    p.drawImage(area, light)
    p.restore()
    boil = int(t * BOIL) % 3
    main, thin = _mark(("ring", *where, boil), lambda: _ring_lines(cover, boil))
    p.setPen(Qt.NoPen)
    p.fillPath(main, col("#6fd3c9"))
    p.fillPath(thin, col("#f0fcf9", 0.92))
    route, at, normals = _mark(("ring-route", *where), lambda: _paw_route(cover))
    paw = _mark(("ring-paw", scale), lambda: _tiny_paw(14.0, max(2.0, scale)))
    # A kitten trotting round: a print every step, left and right foot in turn, the old ones fading.
    step, speed = 16.0, 40.0
    walked = t * speed
    for k in range(5):
        index = int(walked // step) - k
        if index < 0:
            continue
        n = min(len(route) - 1, int(np.searchsorted(at, (index * step) % at[-1])))
        x, y = route[n] + normals[n] * (1.8 if index % 2 else -1.8)
        age = (walked - index * step) / speed
        p.setOpacity(clamp(1.2 - age * 0.55) * min(1.0, age * 8))
        _place(p, paw, QPointF(x, y), math.degrees(math.atan2(normals[n][1], normals[n][0])), 1.0)
    p.setOpacity(1.0)


def _paw_route(cover: QRectF) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Where the paw prints go round the ring: the points, how far along each is, and their sideways units."""
    route = _round_route(cover.adjusted(-2.5, -2.5, 2.5, 2.5), cover.height() * 0.3 + 2.5, 0.5)
    return route, _along(route, closed=True), _normals(route, closed=True)


def _tiny_paw(s: float, scale: float) -> QImage:
    """A tiny paw print in the scene's pale pink, toes up."""
    palm, toes = _paw_shapes(s)
    box = QRectF(-s * 0.6, -s * 0.6, s * 1.2, s * 1.2)
    return _sticker(box, scale, [(palm, PRINT, 0), (toes, PRINT, 0)], 0.6, gloss=0.2, grain=0.0, seed=2)


def _fluffy_paw(s: float) -> tuple[QPainterPath, QPainterPath, QPainterPath]:
    """A fluffy white cat's paw, s across, toes up: its furry outline, its palm pad and its beans."""
    body = QPainterPath()
    body.setFillRule(Qt.WindingFill)
    body.addEllipse(QPointF(0, s * 0.1), s * 0.33, s * 0.31)
    for x, y in ((-0.29, -0.1), (-0.11, -0.27), (0.11, -0.27), (0.29, -0.1)):
        body.addEllipse(QPointF(x * s, y * s), s * 0.155, s * 0.155)
    body = body.simplified()
    # Tufts of fur all round its edge.
    fur = QPainterPath(body)
    fur.setFillRule(Qt.WindingFill)
    edge = _even(np.array([(pt.x(), pt.y()) for pt in body.toSubpathPolygons()[0]]), s * 0.05, closed=True)
    for index, (x, y) in enumerate(edge.tolist()):
        r = s * (0.035 + 0.012 * (index % 3 == 0))
        fur.addEllipse(QPointF(x, y), r, r)
    fur = fur.simplified()
    palm, toes = _paw_shapes(s * 0.82)
    return fur, QTransform().translate(0, s * 0.05).map(palm), QTransform().translate(0, s * 0.02).map(toes)


def _badge_parts(box: QRectF, scale: float) -> tuple[QImage, QRectF, QImage]:
    """The paw as a sticker, and a soft mint glow round it."""
    s = box.width() * 0.82
    fur, palm, toes = _fluffy_paw(s)
    square = QRectF(-box.width() / 2 - 4, -box.height() / 2 - 4, box.width() + 8, box.height() + 8)
    parts = [(fur, "#ffffff", 0), (palm, PINK, 0.9), (toes, PINK, 0.9)]
    outline = [(fur, max(0.8, s * 0.022), INK)]
    paw = _sticker(square, scale, parts, s * 0.08, outline, gloss=0.5, grain=0.07, seed=4, shadow=max(0.8, s * 0.03))
    area = box.adjusted(-9, -9, 9, 9)
    w, h = math.ceil(area.width() * scale), math.ceil(area.height() * scale)

    def draw(q: QPainter) -> None:
        q.scale(scale, scale)
        q.translate(box.center().x() - area.left(), box.center().y() - area.top())
        q.fillPath(fur, QColor("#ffffff"))

    shape = mask(w, h, draw)
    light = (blur(shape, 3 * scale) * 0.55 + blur(shape, 7 * scale) * 0.5)[..., None] * rgb("#7fe0d4")
    return paw, area, glow(light)


def badge(p: QPainter, box: QRectF, t: float) -> None:
    """A fluffy white cat paw with pink pads in a mint glow; now and then it boops, squashing down
    and springing back, and a ❖ twinkles by it."""
    scale = _sharpness(p)
    where = (round(box.x(), 1), round(box.y(), 1), round(box.width(), 1))
    paw, area, light = _mark(("badge", *where, scale), lambda: _badge_parts(box, scale))
    p.save()
    p.setOpacity(0.7 + 0.3 * math.sin(t * 2.0))
    p.drawImage(area, light)
    p.restore()
    # A boop every 2.6 seconds: down and up, then a little bounce that dies away.
    since = t % 2.6
    if since < 0.3:
        press = math.sin(math.pi * since / 0.3)
    else:
        press = -0.3 * math.sin(2 * math.pi * (since - 0.3) / 0.35) * math.exp(-(since - 0.3) * 6)
    w, h = paw.width() / paw.devicePixelRatio(), paw.height() / paw.devicePixelRatio()
    foot = QPointF(box.center().x(), box.center().y() + h * 0.42)
    p.save()
    p.translate(foot)
    p.scale(1 + 0.06 * press, 1 - 0.1 * press)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(QRectF(-w / 2, -h * 0.92, w, h), paw)
    p.restore()
    twinkle = 0.5 + 0.5 * math.sin(t * 3.1)
    r = box.width() * 0.13
    star_image = _mark(("badge-star", round(r, 2), scale), lambda: _star_sticker(r, MINT, scale))
    _place(p, star_image, QPointF(box.right() - r * 0.2, box.top() + r * 0.4), 10 * math.sin(t * 1.3), 0.8 + 0.25 * twinkle)
    star(p, box.left() + r * 0.5, box.top() + r * 1.1, r * 0.55 * (1 - twinkle) + 0.5, "#ffffff", 0.9 * (1 - twinkle), 0.13)


def _page(rect: QRectF, scale: float) -> QImage:
    """The card: a white notebook page dotted like a bullet journal in a pale teal frame, its edges
    inked by hand, with binder holes down its right."""
    body = rect.adjusted(0.5, CARD_TOP + 0.5, -0.5, -0.5)
    frame = QPainterPath()
    frame.addRoundedRect(body, 8, 8)
    page = QPainterPath()
    inner = body.adjusted(4, 4, -4, -4)
    page.addRoundedRect(inner, 5, 5)
    holes = QPainterPath()
    count = max(2, int((body.height() - 10) / 11))
    for k in range(count):
        y = body.top() + 7 + (body.height() - 14) * (k + 0.5) / count
        holes.addEllipse(QPointF(body.right() - 5.5, y), 2.7, 2.7)

    def dots(q: QPainter) -> None:
        q.save()
        q.setClipPath(page.subtracted(holes))
        q.setPen(Qt.NoPen)
        q.setBrush(col(TEAL, 0.32))
        y = inner.top() + 4
        while y < inner.bottom():
            x = inner.left() + 4
            while x < inner.right():
                q.drawEllipse(QPointF(x, y), 0.55, 0.55)
                x += 7
            y += 7
        q.restore()
        # Each hole's far side in shade, as a punched hole is.
        for k in range(count):
            y = body.top() + 7 + (body.height() - 14) * (k + 0.5) / count
            q.setBrush(col(TEAL, 0.35))
            q.drawEllipse(QPointF(body.right() - 5.0, y + 0.6), 1.7, 1.7)

    parts = [(frame, BAND, 0), (page, PAPER, 0.25), (holes, "#ffffff", 0.6)]
    outline = [(frame, 1.1, INK), (holes, 0.6, INK)]
    image = _sticker(rect, scale, parts, 2.0, outline, gloss=0.1, grain=0.035, seed=8, after=dots)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    q.translate(-rect.left(), -rect.top())
    q.setPen(QPen(col(INK, 0.3), 0.7))
    q.setBrush(Qt.NoBrush)
    q.drawRoundedRect(inner, 5, 5)
    q.end()
    return image


def card(p: QPainter, rect: QRectF, t: float) -> None:
    """The notebook page, a sprout peeking over its top and swaying, and a ❖ on its top right corner."""
    scale = _sharpness(p)
    page = _mark(("card", round(rect.width()), round(rect.height()), scale), lambda: _page(rect, scale))
    p.drawImage(rect, page)
    body = rect.adjusted(0, CARD_TOP, 0, 0)
    sprout, foot, _tall = _mark(("card-sprout", max(2.0, scale)), lambda: _sprout(11.0, max(2.0, scale), 3))
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    _place(p, sprout, QPointF(body.left() + 16, body.top() + 3), -6 + 7 * math.sin(t * 1.8), 1.0, foot)
    r = 6.5
    star_image = _mark(("card-star", max(2.0, scale)), lambda: _star_sticker(r, BEAD, max(2.0, scale)))
    _place(p, star_image, QPointF(body.right() - 7, body.top() + 2), 8 * math.sin(t * 1.1), 0.92 + 0.1 * math.sin(t * 2.9))


def lead(size: float, index: int) -> QPixmap:
    """A puffy ❖ before each name, mint and bead blue in turn."""
    shape = _star_path(size * 0.36)
    box = QRectF(-size / 2, -size / 2, size, size)
    image = _sticker(box, 3.0, [(shape, (MINT, BEAD)[index % 2], 0)], size * 0.08, [(shape, max(0.6, size * 0.04), INK)], gloss=0.55, grain=0.0, seed=5)
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(image.devicePixelRatio())
    return pixmap
