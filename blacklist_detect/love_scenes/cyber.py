"""赛博: the screen becomes a visor, a heads-up display drawn in light.

The edges deepen to an indigo night worked out per pixel, darkest behind the top corners, with scan
lines over it. A spark runs round the screen from the top left and lights two neon tubes behind it,
cyan outside and magenta in, cut at the corners like a HUD; they stutter on as neon does. Then two
holographic panels materialize in the top corners, each opening out of a bright line and flickering
in with its colors split. On the left a radar: its sweep leaves a phosphor trail, finds targets and
locks magenta brackets onto two of them, beside segmented data bars and a magenta waveform. On the
right a hex grid with a projector casting a cone of light up into a wireframe icosahedron, turning
round a magenta octahedron inside it, an orbit ring round both, hex readouts typing themselves and
a level meter. Thin tick scales slide up and down the two sides. Twice a scan beam sweeps the top
band and the panels flare where it passes; it dims over the title. Five times a leader feels its way
down and lightning strikes a corner of a panel: a white-hot core in a cyan and violet bloom that
lights its side of the screen and the tubes, then the restrike down the same channel and a shower of
molten sparks, and the panel struck tears into color-split slices and surges. At the end the panels
fold into a line and go out, and the neon powers down.

Its marks: neon brackets lock onto the corners of 准备案件还原 and hold it, breathing, magenta dash
segments running round its edge and now and then an arc jumping a corner; the badge is a hexagonal
chip of smoked glass with a cyan neon rim, a light running round it and a magenta lightning bolt
that surges with its colors split; the card is a smoked-glass HUD panel with cut corners, a cyan
edge and scan lines, a header with a blinking cursor, the names white over a faint magenta glow,
each after a cyan chevron.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

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
ICE = "#e9fdff"
# The card's smoked glass at its top and bottom; its scan lines darken it to about the look's card color.
GLASS = ("#170c3c", "#0a0720")
LOOK = {
    "glow": (33, 246, 255),
    "rim": CYAN,
    "band": (MAGENTA, CYAN),
    "card": ("#140a34", "#08061b"),
    "edge": CYAN,
    "ink": "#f6f8ff",
    "flowers": (("#effeff", "#7ff9ff", "#14b8d6"), ("#fff0fb", "#ff7fe6", "#ff2bd6")),
    "disc": ("#2a1462", "#0b0622"),
    "heart": ("#ff7fe6", "#d4149f"),
    "deep": "#d4149f",
    "deep_glow": (255, 43, 214),
}
MARKS_ANIMATED = True
# Room on top of the card for its header and cursor.
CARD_TOP = 17
CARD_PAD = (12, 7, 14, 9)
# A narrow, engineered face for the names; Chinese falls back to the app's face.
CARD_FONT = "Bahnschrift"
TAU = 2 * math.pi
# Glow pictures are soft: worked out at this share of the stage's size and laid on scaled up.
SOFT = 0.25
MONO = "Consolas"
# A spark cooling as it flies, (heat, color): white hot, gold, orange, then magenta as it dies.
COOLING = ((0.0, MAGENTA), (0.25, "#ff3d6e"), (0.48, "#ff7f26"), (0.7, "#ffc247"), (0.88, "#fff0b0"), (1.0, "#ffffff"))
# Sparks are drawn in this many steps of heat, one batch of lines each.
HEATS = 8
# A spark's track is worked out in steps this long; its streak is how far it flies in SHUTTER.
STEP = 1 / 120
SHUTTER = 0.055
# The leader feels its way down this long before a strike lands.
LEAD = 0.09
# The panels fold away from here, the right one a little after the left.
FOLD = 4.1
# The scan beam's sweeps: (from, to, which way).
SWEEPS = ((1.2, 2.05, 1), (3.0, 3.8, -1))


def _solid(corners: list[tuple[float, float, float]]) -> tuple[np.ndarray, list[tuple[int, int]], np.ndarray]:
    """A regular solid from its corners: the corners on the unit sphere, its edges (the nearest
    pairs) and its triangles."""
    v = np.array(corners, dtype=np.float32)
    d = np.linalg.norm(v[:, None] - v[None], axis=-1)
    near = np.abs(d - d[d > 1e-6].min()) < 1e-3
    n = len(v)
    edges = [(i, j) for i in range(n) for j in range(i + 1, n) if near[i, j]]
    faces = [(i, j, k) for i, j in edges for k in range(j + 1, n) if near[i, k] and near[j, k]]
    return v / np.linalg.norm(v, axis=1, keepdims=True), edges, np.array(faces)


_PHI = (1 + 5 ** 0.5) / 2
ICOSAHEDRON = _solid(
    [(0, a, b * _PHI) for a in (-1, 1) for b in (-1, 1)]
    + [(a, b * _PHI, 0) for a in (-1, 1) for b in (-1, 1)]
    + [(a * _PHI, 0, b) for a in (-1, 1) for b in (-1, 1)]
)
OCTAHEDRON = _solid([(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)])
# Light on the solids' faces: from the upper left, in front.
LIGHT = np.array([-0.45, 0.6, 0.66], dtype=np.float32)


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    outer = _frame(width, height, gap, 15 * u, 34 * u, u)
    inner = _frame(width, height, gap, 25 * u, 40 * u, u)
    frame_glow = _frame_glow(width, height, outer, inner, u)
    top = 48 * u
    left = QRectF(50 * u, top, min(500 * u, width * 0.38 - 66 * u), min(184 * u, height * 0.29 - top - 12 * u))
    span = min(452 * u, width * 0.32 - 80 * u)
    right = QRectF(width - 50 * u - span, top, span, left.height())
    fonts = _fonts(u)
    panels = (_Holo(left, u, *_radar(left, u, fonts), appear=0.45, seed=1), _Holo(right, u, *_mesh(right, u, fonts), appear=0.7, seed=2))
    rails = [_Rail(x, height * 0.34, height * 0.79, side, u) for x, side in ((88 * u, -1), (width - 88 * u, 1))]
    night = Wash(lambda q, w, h: _night(q, w, h, u, (left, right)))
    flashes = [_flash(width, height, gap, u, side) for side in (-1, 1)]
    band = height * 0.285
    beam = _beam_picture(band, u)
    names = QRectF(width * 0.13, height * 0.29, width * 0.81, height * 0.55)
    title = QRectF(width * 0.38, height * 0.07, width * 0.3, height * 0.18)
    # (when it lands, where from, where to, which way its sparks fly, how many, seed, the panel struck)
    strikes = [
        (1.5, QPointF(width * 0.27, -height * 0.03), QPointF(left.right(), left.bottom()), -2.2, 64, 1, 0),
        (2.1, QPointF(width * 0.74, -height * 0.03), QPointF(right.left(), right.bottom()), -0.9, 64, 2, 1),
        (2.75, QPointF(width, height * 0.62), QPointF(right.right(), right.bottom()), -2.3, 74, 3, 1),
        (3.3, QPointF(0.0, height * 0.6), QPointF(left.left(), left.bottom()), -0.8, 64, 4, 0),
        (3.8, QPointF(width * 0.9, -height * 0.03), QPointF(right.right(), right.top()), 2.6, 50, 5, 1),
    ]
    keep = (names, title, gap.adjusted(-30 * u, -30 * u, 30 * u, 30 * u))
    # Each strike's lightning, worked out when first wanted.
    bolts: dict[int, list[tuple]] = {}
    showers = {seed: _shower(end, aim, count, u, seed, width, height, keep) for _when, _start, end, aim, count, seed, _panel in strikes}
    lights = {name: _dot(color, white) for name, color, white in (("hot", "#bff9ff", 1.0), ("cyan", CYAN, 0.25), ("violet", VIOLET, 0.0))}
    heats = _heats(u)
    # Glitches besides the strikes: (the panel, when, how long, how hard).
    glitches = [(0, 2.55, 0.12, 0.55), (1, 3.5, 0.14, 0.65), (0, 4.0, 0.1, 0.5)]
    # The lit tubes, drawn once for each sharpness they are shown at.
    baked: dict[float, list] = {}

    def bake(scale: float) -> list:
        if scale not in baked:
            baked[scale] = [_tube_strips(points, tint, width, height, u, scale) for points, tint in ((outer, CYAN), (inner, MAGENTA))]
        return baked[scale]

    def bolt(seed: int, start: QPointF, end: QPointF) -> list[tuple]:
        if seed not in bolts:
            bolts[seed] = _bolt_shapes(start, end, seed, u, (names, title))
        return bolts[seed]

    def paint(p: QPainter, t: float) -> None:
        scale = _sharpness(p)
        tubes = bake(scale)
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
        _neon_frame(p, t, outer, inner, frame_glow, tubes, lights, width, height, u, bright)
        for rail in rails:
            rail.paint(p, t, scale, 1 - leave)
        at = _beam_at(t, width, beam[1])
        for index, panel in enumerate(panels):
            struck = [when for when, *_rest, which in strikes if which == index]
            tear = max(
                [math.sin(math.pi * win(t, when, when + 0.24)) for when in struck]
                + [k * math.sin(math.pi * win(t, when, when + length)) for which, when, length, k in glitches if which == index]
            )
            surge = max(_strike_light(t - when) for when in struck)
            panel.paint(p, t, scale, tear, surge, at[0] if at else None)
        _beam(p, at, beam, band, title, u)
        for when, start, end, _aim, _count, seed, _panel in strikes:
            if -LEAD <= t - when <= 0.55:
                _strike(p, t - when, start, end, bolt(seed, start, end), lights, u)
        for when, *_rest, seed, _panel in strikes:
            _spark_shower(p, t - when, showers[seed], heats, u)
        p.restore()
        # One strike's lightning worked out ahead each frame, so no frame waits long for it.
        for _when, start, end, _aim, _count, seed, _panel in strikes:
            if seed not in bolts:
                bolt(seed, start, end)
                break

    return paint


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


def _fonts(u: float) -> dict[str, QFont]:
    """The HUD's lettering: a title face and a small one, spaced out a little."""
    out = {}
    for name, size in (("title", 10.5), ("small", 9.0)):
        font = QFont(MONO)
        font.setPixelSize(max(4, round(size * u)))
        font.setLetterSpacing(QFont.AbsoluteSpacing, 0.8 * u)
        out[name] = font
    return out


# The holographic panels.


class _Holo:
    """A holographic panel in a top corner. Its still parts are lit once per sharpness, its moving
    parts drawn each frame, both into a layer of its own that is laid on as a whole: it opens out of
    a bright line and flickers in, tears into color-split slices when it glitches, surges when struck,
    flares where the scan beam passes and folds back into a line at the end."""

    def __init__(self, box: QRectF, u: float, still, moving, appear: float, seed: int) -> None:  # noqa: ANN001
        self.box, self.u, self.still, self.moving, self.appear, self.seed = box, u, still, moving, appear, seed
        pad = 16 * u
        self.area = area = box.adjusted(-pad, -pad, pad, pad)
        k = 0.5

        def draw(q: QPainter) -> None:
            q.scale(k, k)
            q.translate(-area.left(), -area.top())
            still(q, False)

        self.light = bloom(mask(round(area.width() * k), round(area.height() * k), draw), CYAN, ((1.5, 0.55), (5, 0.45)), white=0.0)
        self.baked: dict[float, QImage] = {}
        self.layers: dict[float, QImage] = {}

    def _still(self, scale: float) -> QImage:
        if scale not in self.baked:

            def draw(q: QPainter) -> None:
                q.drawImage(self.area, self.light)
                self.still(q, True)

            self.baked[scale] = _baked(self.area, scale, draw)
        return self.baked[scale]

    def _layer(self, scale: float, t: float) -> QImage:
        """The panel as it is at t, still and moving parts together."""
        a = self.area
        image = self.layers.get(scale)
        if image is None:
            image = QImage(max(1, math.ceil(a.width() * scale)), max(1, math.ceil(a.height() * scale)), QImage.Format_ARGB32_Premultiplied)
            self.layers[scale] = image
        image.fill(Qt.transparent)
        q = QPainter(image)
        q.setRenderHint(QPainter.Antialiasing)
        q.setRenderHint(QPainter.SmoothPixmapTransform)
        q.scale(image.width() / a.width(), image.height() / a.height())
        q.translate(-a.left(), -a.top())
        q.drawImage(a, self._still(scale))
        self.moving(q, t - self.appear)
        q.end()
        return image

    def paint(self, p: QPainter, t: float, scale: float, tear: float, surge: float, beam: float | None) -> None:
        age = t - self.appear
        end = FOLD + 0.12 * self.seed
        if age <= 0 or t > end + 0.62:
            return
        u, a, box = self.u, self.area, self.box
        mid = box.center()
        spread = ease_out(win(age, 0.0, 0.14))
        opened = ease_in_out(win(age, 0.1, 0.5))
        fold = ease_in(win(t, end, end + 0.26))
        shrink = ease_in(win(t, end + 0.26, end + 0.42))
        level = _holo_level(age, t, self.seed)
        # Opening, its colors still split.
        tear = max(tear, 0.7 * (1 - opened) if age < 0.55 else 0.0)
        base = p.opacity()
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if opened > 0 and fold < 1:
            image = self._layer(scale, t)
            p.save()
            if fold > 0:
                p.translate(0, mid.y())
                p.scale(1, 1 - fold)
                p.translate(0, -mid.y())
            if opened < 1:
                half = opened * a.height() / 2
                p.setClipRect(QRectF(a.left() - 60 * u, mid.y() - half, a.width() + 120 * u, 2 * half), Qt.IntersectClip)
            if tear > 0.03:
                self._torn(p, image, t, tear, base * level)
            else:
                p.setOpacity(base * level)
                p.drawImage(a, image)
            p.setCompositionMode(QPainter.CompositionMode_Plus)
            if surge > 0.02:
                p.setOpacity(base * level * surge * 0.75)
                p.drawImage(a, image)
            # A brighter band rolls down the panel now and then, as a hologram's does.
            roll = (age % 2.3) / 1.1
            if roll < 1:
                y = a.top() - 20 * u + roll * (a.height() + 40 * u)
                p.save()
                p.setClipRect(QRectF(a.left(), y - 9 * u, a.width(), 18 * u), Qt.IntersectClip)
                p.setOpacity(base * level * 0.35 * math.sin(math.pi * roll))
                p.drawImage(a, image)
                p.restore()
            # Where the scan beam passes, it reads the panel and the panel flares.
            if beam is not None and a.left() - 30 * u < beam < a.right() + 30 * u:
                # Nested strips, so the flare has no edge.
                for reach, alpha in ((40 * u, 0.1), (30 * u, 0.12), (21 * u, 0.15), (13 * u, 0.2), (6 * u, 0.25)):
                    p.save()
                    p.setClipRect(QRectF(beam - reach, a.top(), 2 * reach, a.height()), Qt.IntersectClip)
                    p.setOpacity(base * alpha)
                    p.drawImage(a, image)
                    p.restore()
            p.restore()
        # The bright line it opens out of and folds back into.
        line = 0.0
        if age < 0.6:
            line = (1 - opened) ** 0.6 * spread
        if fold > 0:
            line = max(line, fold ** 2 * (1 - win(t, end + 0.42, end + 0.62)))
        if line > 0.01:
            reach = box.width() / 2 * (spread if age < 0.6 else 1 - shrink * 0.98)
            half = (opened if age < 0.6 else 1 - fold) * a.height() / 2
            p.setCompositionMode(QPainter.CompositionMode_Plus)
            p.setOpacity(base)
            for y in {mid.y() - half, mid.y() + half}:
                for w, color, alpha in ((7, CYAN, 0.3), (2.6, "#9ffcff", 0.7), (1.1, "#ffffff", 1.0)):
                    p.setPen(QPen(col(color, alpha * line), w * u, Qt.SolidLine, Qt.RoundCap))
                    p.drawLine(QPointF(mid.x() - reach, y), QPointF(mid.x() + reach, y))
            if shrink > 0:
                star(p, mid.x(), mid.y(), (10 + 26 * shrink) * u, "#ffffff", line)
        p.restore()

    def _torn(self, p: QPainter, image: QImage, t: float, tear: float, alpha: float) -> None:
        """The panel torn into slices pushed sideways, each with a red ghost to its left and a blue
        one to its right, as a screen splits its colors."""
        u, a = self.u, self.area
        ghosts = []
        for tint in ("#ff2a55", "#2a7dff"):
            ghost = QImage(image)
            q = QPainter(ghost)
            q.setCompositionMode(QPainter.CompositionMode_SourceIn)
            q.fillRect(ghost.rect(), QColor(tint))
            q.end()
            ghosts.append(ghost)
        rnd = random.Random(int(t * 30) * 13 + self.seed)
        split = (3 + 7 * tear) * u
        y = a.top()
        while y < a.bottom():
            tall = rnd.uniform(5, 28) * u
            shift = rnd.uniform(-24, 24) * u * tear if rnd.random() < 0.55 else 0.0
            p.save()
            p.setClipRect(QRectF(a.left() - 60 * u, y, a.width() + 120 * u, tall + 0.5), Qt.IntersectClip)
            p.setCompositionMode(QPainter.CompositionMode_Plus)
            p.setOpacity(alpha * 0.8 * tear)
            p.drawImage(a.translated(shift - split, 0), ghosts[0])
            p.drawImage(a.translated(shift + split, 0), ghosts[1])
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            p.setOpacity(alpha * (1 - 0.25 * tear))
            p.drawImage(a.translated(shift, 0), image)
            p.restore()
            y += tall


def _holo_level(age: float, t: float, seed: int) -> float:
    """How lit a panel is: stuttering in as it opens, then a faint shimmer."""
    for end, level in ((0.12, 0.9), (0.17, 0.35), (0.25, 1.0), (0.3, 0.5), (0.42, 1.0), (0.46, 0.7)):
        if age < end:
            return level
    return 0.94 + 0.06 * math.sin(t * 31 + seed) * math.sin(t * 5.3 + seed)


def _chrome(q: QPainter, box: QRectF, u: float, fonts: dict[str, QFont], title: str, tag: str, mirror: bool) -> None:
    """A panel's edge: a faint pane of light with two corners cut, a fine outline, bright brackets on
    its corners, the title bar with its rule, and ticks along its foot."""
    c = 14 * u
    l, t, r, b = box.left(), box.top(), box.right(), box.bottom()
    if mirror:
        corners = [QPointF(l, t), QPointF(r - c, t), QPointF(r, t + c), QPointF(r, b), QPointF(l + c, b), QPointF(l, b - c)]
    else:
        corners = [QPointF(l + c, t), QPointF(r, t), QPointF(r, b - c), QPointF(r - c, b), QPointF(l, b), QPointF(l, t + c)]
    pane = QPolygonF(corners)
    fill = QLinearGradient(QPointF(l, t), QPointF(l, b))
    fill.setColorAt(0, col(CYAN, 0.07))
    fill.setColorAt(1, col(CYAN, 0.025))
    q.setPen(QPen(col(CYAN, 0.32), 0.9 * u))
    q.setBrush(fill)
    q.drawPolygon(pane)
    q.setBrush(Qt.NoBrush)
    arm = 26 * u
    q.setPen(QPen(col(CYAN, 0.95), 2.0 * u, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin))
    n = len(corners)
    for i, corner in enumerate(corners):
        before, after = corners[i - 1], corners[(i + 1) % n]
        path = QPainterPath()
        for k, other in enumerate((before, after)):
            d = math.dist((corner.x(), corner.y()), (other.x(), other.y())) or 1
            reach = min(arm, d * 0.45) / d
            end = QPointF(corner.x() + (other.x() - corner.x()) * reach, corner.y() + (other.y() - corner.y()) * reach)
            if k == 0:
                path.moveTo(end)
                path.lineTo(corner)
            else:
                path.lineTo(end)
        q.drawPath(path)
    # The title bar.
    q.setFont(fonts["title"])
    q.setPen(col(ICE, 0.95))
    q.drawText(QPointF(l + 22 * u, t + 16 * u), title)
    q.setPen(col(MAGENTA, 0.95))
    tag_width = QFontMetricsF(fonts["title"]).horizontalAdvance(tag)
    q.drawText(QPointF(r - 22 * u - tag_width, t + 16 * u), tag)
    q.setPen(QPen(col(CYAN, 0.4), 0.8 * u))
    q.drawLine(QPointF(l + 14 * u, t + 23 * u), QPointF(r - 14 * u, t + 23 * u))
    q.setPen(QPen(col(CYAN, 0.95), 2.2 * u, Qt.SolidLine, Qt.FlatCap))
    q.drawLine(QPointF(l + 14 * u, t + 23 * u), QPointF(l + 70 * u, t + 23 * u))
    q.setPen(QPen(col(MAGENTA, 0.95), 2.2 * u, Qt.SolidLine, Qt.FlatCap))
    q.drawLine(QPointF(r - 40 * u, t + 23 * u), QPointF(r - 14 * u, t + 23 * u))
    # Ticks along the foot.
    q.setPen(QPen(col(CYAN, 0.6), 1.0 * u))
    start = r - 150 * u if mirror else l + 40 * u
    for i in range(14):
        x = start + i * 8 * u
        q.drawLine(QPointF(x, b - 5 * u), QPointF(x, b - (9 if i % 4 == 0 else 7) * u))


def _brackets(q: QPainter, x: float, y: float, size: float, arm: float) -> None:
    """Four corner brackets round x, y, size from it: a target locked."""
    path = QPainterPath()
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        cx, cy = x + sx * size, y + sy * size
        path.moveTo(cx, cy - sy * arm)
        path.lineTo(cx, cy)
        path.lineTo(cx - sx * arm, cy)
    q.drawPath(path)


def _radar(box: QRectF, u: float, fonts: dict[str, QFont]) -> tuple:
    """The left panel's parts, (still, moving): a radar of rings and ticks whose sweep leaves a
    phosphor trail and finds targets, two of them locked in magenta; segmented data bars easing
    between readings; a magenta waveform."""
    rr = (box.height() - 48 * u) / 2
    c = QPointF(box.left() + 26 * u + rr, box.top() + 32 * u + rr)
    sweep = _sweep_picture(max(16, round(rr * 4)))
    x0 = c.x() + rr + 32 * u
    bar0, bar1 = x0 + 40 * u, box.right() - 58 * u
    rows = [box.top() + 44 * u + i * 21 * u for i in range(5)]
    labels = ("PWR", "SIG", "SYNC", "FLUX", "LINK")
    wave = QRectF(bar0, rows[-1] + 14 * u, box.right() - 22 * u - bar0, box.bottom() - 12 * u - rows[-1] - 14 * u)
    rnd = random.Random(5)
    readings = [[rnd.uniform(0.3, 0.97) for _ in range(24)] for _ in labels]
    # (how far out, at what angle, locked)
    targets = ((0.68, -2.25, True), (0.4, 0.7, False), (0.8, 1.95, True), (0.55, -0.55, False), (0.3, 2.85, False))
    dots = {tint: _dot(tint, 0.3) for tint in (CYAN, MAGENTA)}
    small = fonts["small"]
    rate = TAU / 1.8

    def still(q: QPainter, lit: bool) -> None:
        _chrome(q, box, u, fonts, "嘉宾 · TARGET SCAN", "SYS.07", mirror=False)
        q.setPen(Qt.NoPen)
        q.setBrush(col(CYAN, 0.06))
        q.drawEllipse(c, rr, rr)
        q.setBrush(Qt.NoBrush)
        q.setPen(QPen(col(CYAN, 0.95), 1.4 * u))
        q.drawEllipse(c, rr, rr)
        q.setPen(QPen(col(CYAN, 0.38), 0.9 * u))
        for k in (0.34, 0.67):
            q.drawEllipse(c, rr * k, rr * k)
        q.setPen(QPen(col(CYAN, 0.28), 0.8 * u))
        q.drawLine(QPointF(c.x() - rr, c.y()), QPointF(c.x() + rr, c.y()))
        q.drawLine(QPointF(c.x(), c.y() - rr), QPointF(c.x(), c.y() + rr))
        for i in range(72):
            a = i * TAU / 72
            major = i % 6 == 0
            q.setPen(QPen(col(CYAN, 0.9 if major else 0.45), (1.3 if major else 0.8) * u))
            r0, r1 = rr + 2.5 * u, rr + (8 if major else 4.5) * u
            q.drawLine(QPointF(c.x() + math.cos(a) * r0, c.y() + math.sin(a) * r0), QPointF(c.x() + math.cos(a) * r1, c.y() + math.sin(a) * r1))
        q.setFont(small)
        for i, (label, y) in enumerate(zip(labels, rows, strict=True)):
            q.setPen(col(MAGENTA if i == 4 else CYAN, 0.85))
            q.drawText(QPointF(x0, y + 3.5 * u), label)
            q.setPen(QPen(col(CYAN, 0.16), 4 * u, Qt.SolidLine, Qt.FlatCap))
            q.drawLine(QPointF(bar0, y), QPointF(bar1, y))
        q.setPen(QPen(col(CYAN, 0.22), 0.8 * u))
        q.drawLine(QPointF(wave.left(), wave.center().y()), QPointF(wave.right(), wave.center().y()))
        for x in (wave.left(), wave.right()):
            q.drawLine(QPointF(x, wave.top()), QPointF(x, wave.bottom()))

    def moving(q: QPainter, age: float) -> None:
        theta = -math.pi / 2 + age * rate
        q.save()
        q.translate(c)
        q.rotate(math.degrees(theta))
        q.drawImage(QRectF(-rr, -rr, 2 * rr, 2 * rr), sweep)
        q.restore()
        # Three arcs turning slowly the other way, a notch on each.
        ring = QRectF(c.x() - rr * 0.86, c.y() - rr * 0.86, rr * 1.72, rr * 1.72)
        turn = -math.degrees(age * 0.7)
        q.setBrush(Qt.NoBrush)
        for k in range(3):
            q.setPen(QPen(col(CYAN, 0.55), 1.6 * u, Qt.SolidLine, Qt.FlatCap))
            q.drawArc(ring, round((turn + k * 120) * 16), 70 * 16)
            a = math.radians(-(turn + k * 120))
            q.setPen(QPen(col(MAGENTA, 0.9), 2.4 * u, Qt.SolidLine, Qt.FlatCap))
            q.drawLine(
                QPointF(c.x() + math.cos(a) * rr * 0.8, c.y() + math.sin(a) * rr * 0.8),
                QPointF(c.x() + math.cos(a) * rr * 0.92, c.y() + math.sin(a) * rr * 0.92),
            )
        for r, phi, locked in targets:
            # Not there until the sweep first finds it.
            found = (age * rate - (phi + math.pi / 2) % TAU) / rate
            if found < 0:
                continue
            lit = math.exp(-((theta - phi) % TAU) / 1.3)
            x, y = c.x() + math.cos(phi) * r * rr, c.y() + math.sin(phi) * r * rr
            tint = MAGENTA if locked else CYAN
            if locked:
                lit = max(lit, 0.55)
            _lay(q, dots[tint], x, y, (6 + 7 * lit) * u, 0.4 + 0.6 * lit)
            q.setOpacity(1.0)
            q.setPen(Qt.NoPen)
            q.setBrush(col("#ffffff", 0.4 + 0.6 * lit))
            q.drawEllipse(QPointF(x, y), 1.6 * u, 1.6 * u)
            if locked:
                k = ease_out(win(found, 0.05, 0.4))
                q.setBrush(Qt.NoBrush)
                q.setPen(QPen(col(MAGENTA, 0.95 * win(found, 0.0, 0.1)), 1.4 * u))
                size = (6 + 14 * (1 - k)) * u
                _brackets(q, x, y, size, 3.5 * u)
                if k > 0.6:
                    q.setFont(small)
                    q.setPen(col(MAGENTA, (k - 0.6) / 0.4))
                    q.drawText(QPointF(x + size + 3 * u, y - size + 2 * u), "LOCK")
        grow = ease_out(win(age, 0.35, 1.0))
        q.setFont(small)
        for i, (seq, y) in enumerate(zip(readings, rows, strict=True)):
            k = age / 0.62 + i * 0.37
            n = int(k)
            f = ease_in_out(k - n)
            v = (seq[n % len(seq)] * (1 - f) + seq[(n + 1) % len(seq)] * f) * grow
            tint = MAGENTA if i == 4 else CYAN
            end = bar0 + (bar1 - bar0) * v
            pen = QPen(mix(tint, "#ffffff", 0.15, 0.95), 4 * u, Qt.SolidLine, Qt.FlatCap)
            pen.setDashPattern([1.15, 0.38])
            q.setPen(pen)
            q.drawLine(QPointF(bar0, y), QPointF(end, y))
            q.setPen(QPen(col("#ffffff", 0.95), 1.3 * u))
            q.drawLine(QPointF(end, y - 4.5 * u), QPointF(end, y + 4.5 * u))
            q.setPen(col(ICE, 0.85))
            q.drawText(QPointF(bar1 + 9 * u, y + 3.5 * u), f"{v * 100:4.1f}")
        points = []
        for j in range(73):
            s = j / 72
            swing = 0.62 * math.sin(s * 21 - age * 9) + 0.38 * math.sin(s * 47 + age * 13)
            points.append(QPointF(wave.left() + s * wave.width(), wave.center().y() + wave.height() * 0.46 * math.sin(math.pi * s) * swing * grow))
        line = QPolygonF(points)
        q.setPen(QPen(col(MAGENTA, 0.3), 4 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        q.drawPolyline(line)
        q.setPen(QPen(col("#ffd9f6", 0.95), 1.1 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        q.drawPolyline(line)

    return still, moving


def _sweep_picture(side: int) -> QImage:
    """The radar's sweep pointing right, per pixel: a bright leading edge and a phosphor trail fading
    behind it, round, side pixels across."""
    r0 = side / 2
    ys, xs = np.mgrid[0:side, 0:side].astype(np.float32)
    dx, dy = xs + 0.5 - r0, ys + 0.5 - r0
    r = np.hypot(dx, dy) / r0
    angle = np.arctan2(dy, dx)
    behind = np.mod(-angle, TAU)
    inside = 1 - smooth(0.96, 1.0, r)
    trail = (np.exp(-behind / 0.9) * 0.8 + np.exp(-behind / 0.12) * 0.5) * (0.25 + 0.75 * r)
    edge = np.exp(-((dy / (side * 0.008)) ** 2)) * (dx > 0) * (0.3 + 0.7 * r)
    light = (trail[..., None] * rgb(CYAN) + edge[..., None] * rgb("#d8fdff") * 1.2) * inside[..., None]
    return glow(light.astype(np.float32))


def _mesh(box: QRectF, u: float, fonts: dict[str, QFont]) -> tuple:
    """The right panel's parts, (still, moving): a hex grid lit round a projector whose cone of light
    holds a wireframe icosahedron turning round a magenta octahedron, an orbit ring round both, hex
    readouts typing themselves and a level meter."""
    r = 58 * u
    center = QPointF(box.right() - 138 * u, box.top() + 100 * u)
    emitter = QPointF(center.x(), box.bottom() - 13 * u)
    cone_rect = QRectF(center.x() - 90 * u, center.y() - r * 0.9, 180 * u, emitter.y() + 10 * u - (center.y() - r * 0.9))
    cone = _cone_picture(cone_rect, emitter, u)
    hexes = []
    size = 12 * u
    grid = box.adjusted(8 * u, 30 * u, -8 * u, -8 * u)
    i = 0
    x = grid.left()
    while x < grid.right() + size:
        y = grid.top() + (size * math.sqrt(3) / 2 if i % 2 else 0)
        while y < grid.bottom() + size:
            d = math.hypot(x - center.x(), y - center.y())
            hexes.append((QPointF(x, y), 0.06 + 0.5 * math.exp(-((d / (150 * u)) ** 2))))
            y += size * math.sqrt(3)
        x += size * 1.5
        i += 1
    rnd = random.Random(11)
    blinkers = [(hexes[rnd.randrange(len(hexes))][0], rnd.uniform(1.5, 3.5), rnd.uniform(0, TAU)) for _ in range(9)]
    text_x = box.left() + 22 * u
    meter = QRectF(text_x, box.bottom() - 52 * u, 132 * u, 40 * u)
    small = fonts["small"]
    dots = {tint: _dot(tint, 0.6) for tint in (CYAN, MAGENTA)}

    def hexagon(at: QPointF, s: float) -> QPolygonF:
        return QPolygonF([QPointF(at.x() + s * math.cos(k * TAU / 6), at.y() + s * math.sin(k * TAU / 6)) for k in range(6)])

    def still(q: QPainter, lit: bool) -> None:
        _chrome(q, box, u, fonts, "HOLO MESH · ICO-20", "LIVE", mirror=True)
        q.save()
        q.setClipRect(grid)
        q.setBrush(Qt.NoBrush)
        for at, alpha in hexes:
            q.setPen(QPen(col(CYAN, alpha), 0.8 * u))
            q.drawPolygon(hexagon(at, size * 0.94))
        q.restore()
        if lit:
            q.drawImage(cone_rect, cone)
        q.setBrush(Qt.NoBrush)
        for k, alpha in ((1.0, 0.95), (0.7, 0.6), (0.4, 0.4)):
            q.setPen(QPen(col(CYAN, alpha), 1.1 * u))
            q.drawEllipse(emitter, 46 * u * k, 7 * u * k)
        q.setFont(small)
        q.setPen(col(CYAN, 0.6))
        q.drawText(QPointF(meter.left(), meter.top() - 6 * u), "OUTPUT")
        q.setPen(QPen(col(CYAN, 0.3), 0.8 * u))
        q.drawLine(QPointF(meter.left(), meter.bottom() + 2 * u), QPointF(meter.right(), meter.bottom() + 2 * u))

    def moving(q: QPainter, age: float) -> None:
        grow = ease_out(win(age, 0.3, 0.9))
        for at, rate, phase in blinkers:
            k = max(0.0, math.sin(age * rate + phase)) ** 4 * grow
            if k > 0.02:
                q.setPen(QPen(col("#9ffcff", 0.8 * k), 1.0 * u))
                q.setBrush(col(CYAN, 0.22 * k))
                q.drawPolygon(hexagon(at, size * 0.94))
        _lay(q, dots[CYAN], emitter.x(), emitter.y(), 34 * u, 0.6 + 0.15 * math.sin(age * 11))
        q.setOpacity(1.0)
        reach = r * ease_back(win(age, 0.3, 0.95), 1.2)
        orbit = QRectF(center.x() - reach * 1.55, center.y() + reach * 0.12 - reach * 0.3, reach * 3.1, reach * 0.6)
        spin = age * 2.1
        dot = QPointF(orbit.center().x() + orbit.width() / 2 * math.cos(spin), orbit.center().y() + orbit.height() / 2 * math.sin(spin))
        if reach > 1:
            _orbit(q, orbit, 0, u)
            if math.sin(spin) < 0:
                _lay(q, dots[MAGENTA], dot.x(), dot.y(), 10 * u, 0.6)
                q.setOpacity(1.0)
            yaw, pitch = age * 0.85, 0.42 + 0.14 * math.sin(age * 0.7)
            _wire(q, OCTAHEDRON, center, reach * 0.48, _turn(-age * 1.6, -0.35), MAGENTA, u, 0.95)
            _wire(q, ICOSAHEDRON, center, reach, _turn(yaw, pitch), CYAN, u, 1.0)
            _orbit(q, orbit, 180, u)
            if math.sin(spin) >= 0:
                _lay(q, dots[MAGENTA], dot.x(), dot.y(), 13 * u, 0.95)
                q.setOpacity(1.0)
        q.setFont(small)
        for i in range(5):
            typed = int((age - 0.35 - i * 0.07) * 70)
            if typed <= 0:
                continue
            rnd = random.Random(int(age * 6 + i * 0.53) * 97 + i)
            text = " ".join(f"{rnd.randrange(65536):04X}" for _ in range(3))[:typed]
            q.setPen(col(MAGENTA if i == 2 else CYAN, 0.8))
            q.drawText(QPointF(text_x, box.top() + 44 * u + i * 15 * u), text)
        bars = 16
        step = meter.width() / bars
        for j in range(bars):
            level = (0.2 + 0.8 * abs(math.sin(age * (2.7 + j * 0.31) + j * 1.7) * math.sin(age * 1.3 + j * 0.9))) * grow
            x = meter.left() + j * step + step / 2
            pen = QPen(mix(CYAN, MAGENTA, level ** 2, 0.9), step * 0.62, Qt.SolidLine, Qt.FlatCap)
            pen.setDashPattern([0.45, 0.22])
            q.setPen(pen)
            q.drawLine(QPointF(x, meter.bottom()), QPointF(x, meter.bottom() - meter.height() * level))

    return still, moving


def _orbit(q: QPainter, rect: QRectF, start: int, u: float) -> None:
    """Half the orbit ring: the far half from 0 degrees, the near half from 180."""
    path = QPainterPath()
    path.arcMoveTo(rect, start)
    path.arcTo(rect, start, 180)
    q.setBrush(Qt.NoBrush)
    near = start == 180
    q.setPen(QPen(col(MAGENTA, 0.25 if near else 0.12), 4 * u))
    q.drawPath(path)
    q.setPen(QPen(col("#ff9be9", 0.9 if near else 0.4), 1.0 * u))
    q.drawPath(path)


def _cone_picture(rect: QRectF, emitter: QPointF, u: float) -> QImage:
    """The projector's cone of light, per pixel: rising from the emitter and widening, faint lines
    of light in it, fading out as it goes up."""
    k = 1.0
    w, h = max(2, round(rect.width() * k)), max(2, round(rect.height() * k))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    x = rect.left() + (xs + 0.5) / k - emitter.x()
    y = rect.top() + (ys + 0.5) / k
    rise = np.clip((emitter.y() - y) / max(1.0, emitter.y() - rect.top()), 0, 1)
    spread = 40 * u + 46 * u * rise
    beam = np.exp(-((x / spread) ** 2) * 2.2) * (1 - rise) ** 1.3 * smooth(-0.02, 0.06, rise)
    streaks = 0.75 + 0.25 * np.cos(x / spread * 9)
    light = (beam * streaks * 0.42)[..., None] * rgb(CYAN)
    return glow(light.astype(np.float32))


def _turn(yaw: float, pitch: float) -> np.ndarray:
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    spin = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float32)
    tilt = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]], dtype=np.float32)
    return tilt @ spin


def _wire(q: QPainter, solid: tuple, center: QPointF, r: float, turn: np.ndarray, tint: str, u: float, alpha: float) -> None:
    """A wireframe solid turned: the faces toward us tinted faintly as the light falls on them, the
    edges brighter the nearer they are, a glowing point at each corner."""
    corners, edges, faces = solid
    w = corners @ turn.T
    depth = 1 / (1 - w[:, 2] * 0.22)
    xs = (center.x() + w[:, 0] * r * depth).tolist()
    ys = (center.y() - w[:, 1] * r * depth).tolist()
    zs = w[:, 2].tolist()
    a, b, c = w[faces[:, 0]], w[faces[:, 1]], w[faces[:, 2]]
    normals = np.cross(b - a, c - a)
    normals *= np.sign((normals * (a + b + c)).sum(axis=1))[:, None]
    normals /= np.linalg.norm(normals, axis=1, keepdims=True)
    q.setPen(Qt.NoPen)
    for (i, j, k), facing, lit in zip(faces.tolist(), normals[:, 2].tolist(), (normals @ LIGHT).tolist(), strict=True):
        if facing > 0:
            q.setBrush(col(tint, alpha * (0.03 + 0.13 * max(0.0, lit))))
            q.drawPolygon(QPolygonF([QPointF(xs[i], ys[i]), QPointF(xs[j], ys[j]), QPointF(xs[k], ys[k])]))
    buckets: tuple[list[QLineF], ...] = ([], [], [])
    for i, j in edges:
        z = (zs[i] + zs[j]) / 2
        buckets[0 if z < -0.3 else 1 if z < 0.3 else 2].append(QLineF(xs[i], ys[i], xs[j], ys[j]))
    for k, lines in enumerate(buckets):
        if lines:
            near = (0.3, 0.62, 1.0)[k]
            q.setPen(QPen(col(tint, 0.2 * near * alpha), (3 + 2 * k) * u, Qt.SolidLine, Qt.RoundCap))
            q.drawLines(lines)
            q.setPen(QPen(mix(tint, "#ffffff", 0.5, near * alpha), (0.7 + 0.45 * k) * u, Qt.SolidLine, Qt.RoundCap))
            q.drawLines(lines)
    for x, y, z in zip(xs, ys, zs, strict=True):
        q.setBrush(col("#ffffff", alpha * (0.35 + 0.65 * (z + 1) / 2)))
        q.drawEllipse(QPointF(x, y), (1.2 + 0.8 * (z + 1) / 2) * u, (1.2 + 0.8 * (z + 1) / 2) * u)


class _Rail:
    """A thin tick scale down one side, as on a pilot's visor: ticks and numbers lit once, sliding up
    and down to a reading, a caret holding the middle."""

    def __init__(self, x: float, top: float, bottom: float, side: int, u: float) -> None:
        self.x, self.top, self.bottom, self.side, self.u = x, top, bottom, side, u
        self.step = 9 * u
        self.area = QRectF(x - 46 * u if side < 0 else x - 10 * u, top - 3 * self.step, 56 * u, bottom - top + 6 * self.step)
        self.tape = QRectF(self.area.left(), top - 30 * self.step, self.area.width(), bottom - top + 60 * self.step)
        self.baked: dict[float, QImage] = {}

    def _bake(self, scale: float) -> QImage:
        if scale not in self.baked:
            u, x, side, tape = self.u, self.x, self.side, self.tape
            font = QFont(MONO)
            font.setPixelSize(max(4, round(8 * u)))

            def draw(q: QPainter) -> None:
                q.setFont(font)
                count = int(tape.height() / self.step)
                for i in range(count + 1):
                    y = tape.top() + i * self.step
                    major = i % 5 == 0
                    q.setPen(QPen(col(CYAN, 0.85 if major else 0.4), (1.2 if major else 0.8) * u))
                    q.drawLine(QPointF(x, y), QPointF(x + side * (10 if major else 5) * u, y))
                    if major:
                        label = f"{(count - i) * 5:03d}"
                        q.setPen(col(CYAN, 0.7))
                        q.drawText(QPointF(x + side * 13 * u - (26 * u if side < 0 else 0), y + 3 * u), label)

            self.baked[scale] = _baked(tape, scale, draw)
        return self.baked[scale]

    def paint(self, p: QPainter, t: float, scale: float, stay: float) -> None:
        on = ease_out(win(t, 1.0, 1.5)) * stay
        if on <= 0.01:
            return
        u = self.u
        # The reading drifts, easing from one value to the next.
        k = t / 1.3 + (self.side + 1) * 0.4
        n = int(k)
        f = ease_in_out(k - n)
        pick = [((i * 7 + self.side * 3) % 11 - 5) * 2.3 * self.step for i in range(n, n + 2)]
        shift = pick[0] * (1 - f) + pick[1] * f
        # The tape fades out toward its ends, in steps.
        tape = self._bake(scale)
        fade = 4 * self.step
        base = p.opacity() * on * 0.75
        zones = [(self.area.top() + fade * i / 4, fade / 4, (i + 0.5) / 4) for i in range(4)]
        zones.append((self.area.top() + fade, self.area.height() - 2 * fade, 1.0))
        zones += [(self.area.bottom() - fade * (i + 1) / 4, fade / 4, (i + 0.5) / 4) for i in range(4)]
        for y, tall, alpha in zones:
            p.save()
            p.setOpacity(base * alpha)
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            p.setClipRect(QRectF(self.area.left(), y, self.area.width(), tall), Qt.IntersectClip)
            p.drawImage(self.tape.translated(0, shift), tape)
            p.restore()
        # A spine, fading at its ends, and the caret on the middle.
        p.save()
        p.setOpacity(p.opacity() * on)
        g = QLinearGradient(QPointF(self.x, self.top), QPointF(self.x, self.bottom))
        for at, alpha in ((0, 0.0), (0.2, 0.7), (0.8, 0.7), (1, 0.0)):
            g.setColorAt(at, col(CYAN, alpha))
        p.setPen(QPen(g, 1.2 * u))
        p.drawLine(QPointF(self.x, self.top), QPointF(self.x, self.bottom))
        mid = (self.top + self.bottom) / 2
        tip = self.x - self.side * 3 * u
        caret = QPolygonF([QPointF(tip, mid), QPointF(tip - self.side * 9 * u, mid - 5 * u), QPointF(tip - self.side * 9 * u, mid + 5 * u)])
        p.setPen(Qt.NoPen)
        p.setBrush(col(MAGENTA, 0.95))
        p.drawPolygon(caret)
        p.restore()


# The scan beam.


def _beam_picture(band: float, u: float) -> tuple[QImage, float, float]:
    """The scan beam moving right, per pixel, down the top band: a white-hot line, cyan round it and
    a violet haze, and behind it the afterglow of what it has read, in fine streaks; fading at its
    foot. Returns it, how far it reaches behind the line and how far ahead."""
    behind, ahead = 190 * u, 50 * u
    w, h = max(2, round(behind + ahead)), max(2, round(band))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    dx = (xs + 0.5) * ((behind + ahead) / w) - behind
    y = (ys + 0.5) * (band / h)
    fall = smooth(0, 10 * u, y) * (1 - smooth(band * 0.45, band, y))
    core = np.exp(-((dx / (1.4 * u)) ** 2))
    near = np.exp(-np.abs(dx) / (8 * u))
    wide = np.exp(-((dx / (30 * u)) ** 2)) * (1 - smooth(ahead * 0.5, ahead, dx))
    streaks = 0.55 + 0.45 * noise(w, 1, 3 * u, 2, 4)[0]
    trail = np.exp(np.minimum(dx, 0) / (60 * u)) * (dx < 0) * smooth(-behind, -behind * 0.7, dx) * streaks * 0.2
    light = (
        core[..., None] * rgb("#ffffff") * 0.95
        + near[..., None] * rgb(CYAN) * 0.6
        + wide[..., None] * rgb(VIOLET) * 0.35
        + trail[..., None] * rgb(CYAN)
    ) * fall[..., None]
    return glow(light.astype(np.float32)), behind, ahead


def _beam_at(t: float, width: float, reach: float) -> tuple[float, int] | None:
    """Where the scan beam is at t and which way it goes, or None between its sweeps."""
    for start, end, way in SWEEPS:
        if start <= t <= end:
            k = ease_in_out(win(t, start, end))
            return -reach + (width + 2 * reach) * (k if way > 0 else 1 - k), way
    return None


def _beam(p: QPainter, at: tuple[float, int] | None, beam: tuple, band: float, title: QRectF, u: float) -> None:
    """The scan beam at x going one way, down the top band; where it crosses the title it dims, so
    the words stay."""
    if at is None:
        return
    x, way = at
    image, behind, ahead = beam
    k = image.height() / band
    lo, hi = (x - behind, x + ahead) if way > 0 else (x - ahead, x + behind)
    if lo < title.right() and hi > title.left():
        f = 14 * u
        stops = [0.0, title.top() - f, title.top() - f / 2, title.top(), title.bottom(), title.bottom() + f / 2, title.bottom() + f, band]
        alphas = [1.0, 0.65, 0.35, 0.12, 0.35, 0.65, 1.0]
    else:
        stops, alphas = [0.0, band], [1.0]
    p.save()
    p.setCompositionMode(QPainter.CompositionMode_Plus)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.translate(x, 0)
    p.scale(way, 1)
    base = p.opacity()
    for y0, y1, alpha in zip(stops, stops[1:], alphas, strict=False):
        y0, y1 = max(0.0, y0), min(band, y1)
        if y1 <= y0:
            continue
        p.setOpacity(base * alpha)
        p.drawImage(QRectF(-behind, y0, behind + ahead, y1 - y0), image, QRectF(0, y0 * k, image.width(), (y1 - y0) * k))
    p.restore()


# The night and the neon frame.


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


def _night(p: QPainter, width: float, height: float, u: float, panels: tuple[QRectF, ...]) -> None:
    """The night at the edges, per pixel: deep indigo darkening toward the edges with smog drifting
    through it, darkest behind the panels so their light reads, pooling to violet and plum with a
    little neon light spilled in; then scan lines drawn sharp into it."""
    x, y, clear, rim = _field(width, height, u)
    h, w = x.shape
    smog = noise(w, h, 110 * u * SOFT, 3, 9)
    dark = clear * (0.42 + 0.5 * rim) * (0.85 + 0.3 * smog)
    # Behind the panels, but not over the names under them.
    above = 1 - smooth(height * 0.29 - 26 * u, height * 0.29, y)
    for box in panels:
        dx = np.maximum(np.maximum(box.left() - x, x - box.right()), 0)
        dy = np.maximum(np.maximum(box.top() - y, y - box.bottom()), 0)
        dark = np.maximum(dark, 0.88 * (1 - smooth(0, 60 * u, np.hypot(dx, dy))) * above)
    tone = rgb(NIGHT) * rim[..., None] + rgb(INDIGO) * (1 - rim[..., None])
    for cx, cy, reach, tint in (
        (0.0, 0.0, 600 * u, "#1d0a4a"),
        (width, 0.0, 620 * u, "#0d0f4d"),
        (0.0, height, 640 * u, "#33082f"),
        (width, height, 620 * u, "#0b1245"),
    ):
        g = (np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / reach ** 2 * 2.0) * (0.6 + 0.5 * smog) * 0.9)[..., None]
        tone = tone * (1 - g) + rgb(tint) * g
    light = tone * dark[..., None]
    amount = dark.copy()
    for cx, cy, reach, tint, strength in (
        (0.0, height * 0.55, 320 * u, MAGENTA, 0.08),
        (width * 0.5, 0.0, 420 * u, VIOLET, 0.1),
        (0.0, height, 420 * u, MAGENTA, 0.14),
        (width, height, 400 * u, CYAN, 0.1),
    ):
        g = np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / reach ** 2 * 2.2) * strength * clear * smog * 2
        light += g[..., None] * rgb(tint)
        amount += g
    alpha = np.clip(amount, 0, 0.92)
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(QRectF(0, 0, width, height), picture(light / np.maximum(amount, 1e-4)[..., None], alpha))
    # Scan lines are drawn into the night only, as much as it is there: none over the names.
    p.setCompositionMode(QPainter.CompositionMode_SourceAtop)
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


# Lightning and its sparks.


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
        # Small where it lands, for the names are near.
        _lay(p, lights["violet"], end.x(), end.y(), 120 * u, 0.4 * light * base)
        _lay(p, lights["cyan"], end.x(), end.y(), 64 * u, 0.75 * light * base)
        _lay(p, lights["hot"], end.x(), end.y(), 30 * u, light * base)
        _lay(p, lights["violet"], start.x(), start.y(), 200 * u, 0.6 * light * base)
    # A ring thrown off where it lands, cyan then magenta.
    p.setOpacity(base)
    p.setBrush(Qt.NoBrush)
    for delay, tint in ((0.0, CYAN), (0.07, MAGENTA)):
        k = win(age - delay, 0.0, 0.38)
        if 0 < k < 1:
            r = (10 + 46 * ease_out(k)) * u
            p.setPen(QPen(col(tint, 0.85 * (1 - k) ** 2), (3.2 - 2 * k) * u))
            p.drawEllipse(end, r, r)
    p.restore()


def _arc(p: QPainter, a: QPointF, b: QPointF, seed: int, u: float, light: float, scale: float) -> None:
    """A little arc of lightning from a to b."""
    points = _bolt_points(a, b, random.Random(seed), 0.25, 4)
    path = polyline(points)
    p.setBrush(Qt.NoBrush)
    for w, color, alpha in ((10, CYAN, 0.25), (3.5, "#9ffcff", 0.7), (1.4, "#ffffff", 1.0)):
        p.setPen(QPen(col(color, alpha * light), w * u * scale, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)


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
    at: QPointF, aim: float, count: int, u: float, seed: int, width: float, height: float, keep: tuple[QRectF, ...]
) -> tuple[np.ndarray, ...]:
    """Molten sparks thrown from at, most toward aim (radians), flown once here: under gravity and
    drag, bouncing off the bottom tube and the screen's sides and skittering along. A spark is gone
    once it reaches the names, the title or the gap. Returns (tracks: steps by sparks by x, y; when
    each leaves; how long it lives; when it is gone; its size)."""
    rng = np.random.default_rng(seed)
    embers = count // 6
    n = count + embers
    # Most fast, a few very fast and short-lived, and some slow embers that drift and glow longest.
    speed = np.concatenate([rng.uniform(170, 480, count) * (1 + rng.exponential(0.25, count)), rng.uniform(40, 150, embers)])
    angle = aim + rng.normal(0, 0.7, n)
    vel = np.stack([np.cos(angle), np.sin(angle)], axis=1) * speed[:, None] * u
    pos = np.tile(np.array([at.x(), at.y()], dtype=np.float64), (n, 1)) + rng.normal(0, 3 * u, (n, 2))
    life = np.concatenate([rng.uniform(0.4, 1.0, count), rng.uniform(0.8, 1.15, embers)]) * (1.15 - 0.3 * np.clip(speed / 600, 0, 1))
    delay = rng.uniform(0, 0.05, n)
    size = np.concatenate([rng.uniform(0.8, 1.35, count), rng.uniform(0.5, 0.8, embers)])
    bounce = rng.uniform(0.25, 0.55, n)
    floor, left, right, ceiling = height - 25 * u, 6 * u, width - 6 * u, 6 * u
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
        high = pos[:, 1] < ceiling
        if high.any():
            pos[high, 1] = 2 * ceiling - pos[high, 1]
            vel[high, 1] *= -0.4
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


# The marks: the ring, the badge, the card and the chevron before each name.

# Pictures the marks are drawn from, made once for each size and sharpness.
_PICTURES: dict[tuple, object] = {}


def _kept(key: tuple, make_it):  # noqa: ANN001, ANN202
    if key not in _PICTURES:
        _PICTURES[key] = make_it()
    return _PICTURES[key]


def _hum(t: float, on: float) -> float:
    """A mark's neon: stuttering on, then a faint hum."""
    age = t - on
    if age < 0:
        return 0.0
    for end, level in ((0.05, 1.0), (0.1, 0.2), (0.16, 0.9), (0.2, 0.1), (0.27, 0.75)):
        if age < end:
            return level
    return 0.93 + 0.07 * math.sin(t * 19) * math.sin(t * 6.1)


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    """Neon brackets lock onto the button's corners and hold it, breathing; magenta dash segments run
    round its edge over a soft glow; now and then an arc jumps across a corner."""
    w, h = cover.width(), cover.height()
    halo = _kept(("ring", round(w), round(h)), lambda: _ring_glow(w, h))
    base = p.opacity()
    lock = ease_out(win(t, 0.0, 0.45))
    level = _hum(t, 0.0)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setOpacity(base * (0.4 + 0.6 * win(t, 0.0, 0.3)) * (0.75 + 0.25 * math.sin(t * 2.4)))
    p.drawImage(cover.adjusted(-9, -9, 9, 9), halo)
    # The dashes run round the edge.
    radius = max(4.0, h * 0.14)
    edge = QPainterPath()
    edge.addRoundedRect(cover.adjusted(1.6, 1.6, -1.6, -1.6), radius, radius)
    p.setOpacity(base * win(t, 0.15, 0.45))
    p.setBrush(Qt.NoBrush)
    for width, color, alpha in ((5.0, MAGENTA, 0.3), (2.0, "#ff8ee9", 0.95)):
        pen = QPen(col(color, alpha), width, Qt.SolidLine, Qt.FlatCap)
        pen.setDashPattern([v * 2.0 / width for v in (16, 6, 3, 6, 3, 6, 34, 10)])
        pen.setDashOffset(-t * 26 / width)
        p.setPen(pen)
        p.drawPath(edge)
    # The brackets close in onto the corners, then breathe.
    out = 4.2 + 3.5 * (1 - lock) + 0.9 * math.sin(t * 2.2)
    arm = min(h * 0.36, 26.0) * (0.4 + 0.6 * lock)
    p.setOpacity(base)
    brackets = QPainterPath()
    box = cover.adjusted(-out, -out, out, out)
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        cx = box.left() if sx < 0 else box.right()
        cy = box.top() if sy < 0 else box.bottom()
        brackets.moveTo(cx, cy - sy * arm)
        brackets.lineTo(cx, cy)
        brackets.lineTo(cx - sx * arm * 1.6, cy)
    _tube(p, brackets, CYAN, level, 3.4)
    # Little marks at the middle of each side, pointing in.
    p.setPen(Qt.NoPen)
    p.setBrush(col(CYAN, 0.9 * level))
    mid = cover.center()
    for y, way in ((cover.top() - 2.5, -1), (cover.bottom() + 2.5, 1)):
        p.drawPolygon(QPolygonF([QPointF(mid.x(), y), QPointF(mid.x() - 4, y + way * 4.5), QPointF(mid.x() + 4, y + way * 4.5)]))
    # Now and then an arc jumps across a corner.
    cycle, age = divmod(t, 2.9)
    if 1.7 <= age < 1.9:
        corner = int(cycle) % 4
        sx, sy = ((-1, -1), (1, -1), (1, 1), (-1, 1))[corner]
        cx = box.left() if sx < 0 else box.right()
        cy = box.top() if sy < 0 else box.bottom()
        a, b = QPointF(cx, cy - sy * arm), QPointF(cx - sx * arm * 1.6, cy)
        p.save()
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        _arc(p, a, b, int(t * 30), 1.0, 1 - (age - 1.7) / 0.2, 0.32)
        p.restore()


def _ring_glow(w: float, h: float) -> QImage:
    """The light round the button, per pixel: magenta along its edge, violet further out, cyan where
    the brackets hold its corners."""
    m = 9
    side = (round(w + 2 * m), round(h + 2 * m))
    radius = max(4.0, h * 0.14)

    def edge(q: QPainter) -> None:
        q.setPen(QPen(Qt.white, 2.4))
        q.drawRoundedRect(QRectF(m, m, w, h).adjusted(1.5, 1.5, -1.5, -1.5), radius, radius)

    def corners(q: QPainter) -> None:
        q.setPen(QPen(Qt.white, 3.4, Qt.SolidLine, Qt.FlatCap))
        box = QRectF(m - 4, m - 4, w + 8, h + 8)
        arm = min(h * 0.36, 26.0)
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            cx = box.left() if sx < 0 else box.right()
            cy = box.top() if sy < 0 else box.bottom()
            q.drawLine(QPointF(cx, cy), QPointF(cx, cy - sy * arm))
            q.drawLine(QPointF(cx, cy), QPointF(cx - sx * arm * 1.6, cy))

    line = mask(*side, edge)
    hold = mask(*side, corners)
    light = (
        blur(line, 2.2)[..., None] * rgb(MAGENTA) * 0.9
        + blur(line, 5.5)[..., None] * rgb(VIOLET) * 1.0
        + blur(hold, 3.0)[..., None] * rgb(CYAN) * 1.2
    )
    return glow(light.astype(np.float32))


BOLT = ((0.2, -1.0), (-0.5, 0.14), (-0.04, 0.14), (-0.24, 1.0), (0.52, -0.2), (0.06, -0.2))


def badge(p: QPainter, box: QRectF, t: float) -> None:
    """A hexagonal chip of smoked glass with a cyan neon rim and a light running round it; the
    magenta lightning bolt in it stutters on, hums, and every few seconds surges with its colors
    split."""
    scale = _sharpness(p)
    side = box.width()
    body, bolt, ghosts, rim = _kept(("badge", round(side, 1), scale), lambda: _badge_pictures(side, scale))
    dots = _kept(("dots",), lambda: {tint: _dot(tint, 0.5) for tint in (CYAN, MAGENTA)})
    area = box.adjusted(-9, -9, 9, 9)
    base = p.opacity()
    # The window fades in by itself; the bolt stutters on once it has.
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(area, body)
    on = win(t, 0.0, 0.3)
    p.setOpacity(base * _hum(t, 0.15))
    p.drawImage(area, bolt)
    surge = _strike_light(t % 3.2 - 2.3)
    if surge > 0.02:
        p.save()
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        p.setOpacity(base * surge * 0.8)
        p.drawImage(area, bolt)
        split = 2.2 * surge
        p.setOpacity(base * surge * 0.75)
        p.drawImage(area.translated(-split, 0), ghosts[0])
        p.drawImage(area.translated(split, 0), ghosts[1])
        p.restore()
    # A light runs round the rim.
    corners = [QPointF(area.left() + x, area.top() + y) for x, y in rim]
    spot, _angle = point_at(corners, lengths(corners), lengths(corners)[-1] * ((t / 2.4) % 1.0))
    _lay(p, dots[CYAN], spot.x(), spot.y(), side * 0.16, base * on * 0.9)
    p.setOpacity(base * on)
    star(p, spot.x(), spot.y(), side * 0.1, "#ffffff", 0.85)


def _hexagon(cx: float, cy: float, r: float) -> list[tuple[float, float]]:
    """A hexagon standing on a point, round cx, cy."""
    return [(cx + r * math.cos(math.radians(90 + 60 * k)), cy + r * math.sin(math.radians(90 + 60 * k))) for k in range(6)]


def _badge_pictures(side: float, scale: float) -> tuple:
    """The badge's pictures at scale, per pixel: the chip (dark glass graded top to bottom, a bevel
    catching light along its upper edges, grain, faint traces, the cyan neon rim and its bloom), the
    bolt (magenta glass, white-hot in its middle, in its own bloom), the bolt's red and blue ghosts,
    and the rim's corners in points, closed."""
    m = 9
    n = max(4, math.ceil((side + 2 * m) * scale))
    cx = cy = m + side / 2
    r = side * 0.5
    outline = _hexagon(cx, cy, r * 0.94)
    hexagon = QPolygonF([QPointF(x, y) for x, y in outline])
    bolt = QPolygonF([QPointF(cx + x * r * 0.5, cy + y * r * 0.52) for x, y in BOLT])

    def fill(shape: QPolygonF):  # noqa: ANN202
        def draw(q: QPainter) -> None:
            q.scale(scale, scale)
            q.setPen(Qt.NoPen)
            q.setBrush(Qt.white)
            q.drawPolygon(shape)

        return draw

    def rim(q: QPainter) -> None:
        q.scale(scale, scale)
        q.setPen(QPen(Qt.white, max(1.5, side * 0.04), Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin))
        q.drawPolygon(hexagon)

    inside = mask(n, n, fill(hexagon))
    edge = mask(n, n, rim)
    ys = (np.mgrid[0:n, 0:n][0].astype(np.float32) + 0.5) / scale
    down = np.clip((ys - (cy - r)) / (2 * r), 0, 1)[..., None]
    color = rgb("#2c1668") * (1 - down) + rgb("#07031a") * down
    bevel = np.clip(inside - blur(inside, 1.6 * scale), 0, 1) * (1 - down[..., 0]) ** 1.5
    grain = (np.random.default_rng(3).random((n, n), dtype=np.float32) - 0.5) * 0.04
    color = color + bevel[..., None] * rgb("#9ffcff") * 1.4 + grain[..., None]
    plate = picture(color, inside * 0.95)
    light = bloom(edge, CYAN, ((1.2 * scale, 0.9), (3.5 * scale, 0.75)), white=0.5)
    q = QPainter(plate)
    q.setRenderHint(QPainter.Antialiasing)
    q.drawImage(0, 0, light)
    q.scale(scale, scale)
    # Faint traces from an inner ring to the rim, with pads.
    q.setBrush(Qt.NoBrush)
    q.setPen(QPen(col(CYAN, 0.28), max(0.6, side * 0.016)))
    q.drawPolygon(QPolygonF([QPointF(x, y) for x, y in _hexagon(cx, cy, r * 0.72)]))
    q.setPen(QPen(col(MAGENTA, 0.3), max(0.6, side * 0.016)))
    for k in (1, 3, 5):
        a = math.radians(90 + 60 * k)
        start = QPointF(cx + math.cos(a) * r * 0.72, cy + math.sin(a) * r * 0.72)
        q.drawLine(start, QPointF(cx + math.cos(a) * r * 0.86, cy + math.sin(a) * r * 0.86))
        q.drawEllipse(start, side * 0.025, side * 0.025)
    q.end()
    shape = mask(n, n, fill(bolt))
    core = np.clip((blur(shape, 0.9 * scale) - 0.55) * 2.5, 0, 1) * shape
    glass = shape[..., None] * rgb(mix(MAGENTA, "#ffffff", 0.35).name())
    halo = (blur(shape, 2.0 * scale) * 1.1 + blur(shape, 5.0 * scale) * 0.9)[..., None] * rgb(MAGENTA)
    bolt_light = glow((glass + halo + core[..., None] * 1.2).astype(np.float32))
    ghosts = []
    for tint in ("#ff2a55", "#2a7dff"):
        ghost = QImage(bolt_light)
        g = QPainter(ghost)
        g.setCompositionMode(QPainter.CompositionMode_SourceIn)
        g.fillRect(ghost.rect(), QColor(tint))
        g.end()
        ghosts.append(ghost)
    return plate, bolt_light, ghosts, [*outline, outline[0]]


def card(p: QPainter, rect: QRectF, t: float) -> None:
    """A smoked-glass HUD panel with two corners cut: a cyan edge, scan lines, a faint magenta glow
    behind the names and a header with a blinking cursor; a scan band slides down it now and then and
    a light runs along its edge."""
    scale = _sharpness(p)
    glass, cursor, outline = _kept(
        ("card", round(rect.width()), round(rect.height()), scale), lambda: _card_pictures(rect.width(), rect.height(), scale)
    )
    base = p.opacity()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(rect, glass)
    if (t % 1.06) < 0.62:
        p.fillRect(cursor.translated(rect.topLeft()), col(CYAN, 0.95))
    shape = QPainterPath()
    shape.addPolygon(QPolygonF([point + rect.topLeft() for point in outline]))
    k = (t % 3.6) / 1.4
    if k < 1:
        y = rect.top() + CARD_TOP - 10 + (rect.height() - CARD_TOP + 20) * k
        band = QLinearGradient(QPointF(0, y - 9), QPointF(0, y + 9))
        band.setColorAt(0, col(CYAN, 0))
        band.setColorAt(0.5, col(CYAN, 0.12 * math.sin(math.pi * k)))
        band.setColorAt(1, col(CYAN, 0))
        p.save()
        p.setClipPath(shape, Qt.IntersectClip)
        p.fillRect(QRectF(rect.left(), y - 9, rect.width(), 18), band)
        p.restore()
    k = (t % 2.8) / 1.6
    if k < 1:
        corners = [point + rect.topLeft() for point in outline]
        reach = lengths(corners)
        head = reach[-1] * ease_in_out(k)
        trail = [point_at(corners, reach, head - reach[-1] * 0.12 * i / 8)[0] for i in range(9)]
        p.setOpacity(base * math.sin(math.pi * k))
        p.setBrush(Qt.NoBrush)
        for width, color, alpha in ((4.0, CYAN, 0.35), (1.4, "#ffffff", 0.95)):
            p.setPen(QPen(col(color, alpha), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPolyline(QPolygonF(trail))


def _card_outline(w: float, h: float) -> list[QPointF]:
    """The card's edge: its top left and bottom right corners cut, the others only nicked."""
    c, n = 9.0, 2.5
    return [
        QPointF(c, 0), QPointF(w - n, 0), QPointF(w, n), QPointF(w, h - c), QPointF(w - c, h), QPointF(n, h), QPointF(0, h - n),
        QPointF(0, c), QPointF(c, 0),
    ]  # fmt: skip


def _card_pictures(w: float, h: float, scale: float) -> tuple[QImage, QRectF, list[QPointF]]:
    """The card at scale, per pixel: smoked glass graded down to its bottom color, grain, a sheen,
    scan lines, a faint magenta glow behind the names, a cyan light inside its edge; then its edge,
    header and the small marks on it drawn sharp. Returns it, where the cursor blinks and its edge."""
    width, height = max(2, math.ceil(w * scale)), max(2, math.ceil(h * scale))
    outline = _card_outline(w - 0.5, h - 0.5)
    pane = QPolygonF([point + QPointF(0.25, 0.25) for point in outline])

    def fill(q: QPainter) -> None:
        q.scale(scale, scale)
        q.setPen(Qt.NoPen)
        q.setBrush(Qt.white)
        q.drawPolygon(pane)

    def edge(q: QPainter) -> None:
        q.scale(scale, scale)
        q.setPen(QPen(Qt.white, 1.4))
        q.drawPolyline(pane)

    inside = mask(width, height, fill)
    rim = mask(width, height, edge)
    ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
    x, y = (xs + 0.5) / scale, (ys + 0.5) / scale
    down = np.clip(y / h, 0, 1)[..., None]
    color = rgb(GLASS[0]) * (1 - down) + rgb(GLASS[1]) * down
    body = h - CARD_TOP
    # Gone by the foot, where the names fade into the glass's own color when more wait below.
    haze = np.exp(-(((x - w * 0.42) / (w * 0.5)) ** 2) - (((y - CARD_TOP - body * 0.45) / (body * 0.5)) ** 2)) * 0.26
    haze *= 1 - smooth(h - 36, h - 14, y)
    sheen = np.exp(-(((x * 0.45 + y - h * 0.3) / (h * 0.16)) ** 2)) * 0.05 * (1 - down[..., 0])
    grain = (np.random.default_rng(7).random((height, width), dtype=np.float32) - 0.5) * 0.03
    scan = 1 - 0.28 * (np.floor(y / 1.5) % 2)
    within = blur(rim, 3.0 * scale) * inside
    color = (color + haze[..., None] * rgb(MAGENTA) * 0.55 + (sheen + grain)[..., None]) * scan[..., None] + within[..., None] * rgb(CYAN) * 0.45
    image = picture(color, inside * 0.94)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    q.scale(scale, scale)
    q.setBrush(Qt.NoBrush)
    q.setPen(QPen(col(CYAN, 0.95), 1.1))
    q.drawPolyline(pane)
    # Magenta on the two cut corners.
    q.setPen(QPen(col(MAGENTA, 0.95), 2.0, Qt.SolidLine, Qt.FlatCap))
    q.drawLine(QPointF(0.8, 9.0), QPointF(9.0, 0.8))
    q.drawLine(QPointF(w - 1.3, h - 9.5), QPointF(w - 9.5, h - 1.3))
    # The header: its words, the cursor after them, its rule.
    font = QFont(CARD_FONT)
    font.setFamilies([CARD_FONT, "Microsoft YaHei"])
    font.setPixelSize(10)
    font.setLetterSpacing(QFont.AbsoluteSpacing, 0.6)
    label = "嘉宾 // LINK"
    q.setFont(font)
    q.setPen(col(CYAN, 0.9))
    q.drawText(QPointF(12, CARD_TOP - 5), label)
    after = 12 + QFontMetricsF(font).horizontalAdvance(label) + 3
    cursor = QRectF(after, CARD_TOP - 13, 5, 9)
    q.setPen(QPen(col(CYAN, 0.45), 0.8))
    q.drawLine(QPointF(9, CARD_TOP - 1), QPointF(w - 6, CARD_TOP - 1))
    q.setPen(QPen(col(CYAN, 0.95), 1.6, Qt.SolidLine, Qt.FlatCap))
    q.drawLine(QPointF(w - 24, CARD_TOP - 1), QPointF(w - 6, CARD_TOP - 1))
    # Ticks on the right edge.
    q.setPen(QPen(col(CYAN, 0.7), 1.0))
    for i in range(3):
        yy = CARD_TOP + 6 + i * 4
        q.drawLine(QPointF(w - 4.5, yy), QPointF(w - 1.5, yy))
    q.end()
    return image, cursor, outline


def lead(size: float, index: int) -> QPixmap:
    """A cyan chevron, lit: a bright one with a fainter one behind it, both in their glow."""
    ratio = 3.0
    image = _kept(("lead", round(size * 10)), lambda: _chevron(size, ratio))
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def _chevron(size: float, ratio: float) -> QImage:
    n = max(4, round(size * ratio))
    s = size * ratio

    def shape(dx: float):  # noqa: ANN202
        def draw(q: QPainter) -> None:
            q.setPen(QPen(Qt.white, s * 0.12, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
            q.drawPolyline(QPolygonF([QPointF(s * (0.36 + dx), s * 0.24), QPointF(s * (0.62 + dx), s * 0.5), QPointF(s * (0.36 + dx), s * 0.76)]))

        return draw

    front = mask(n, n, shape(0.1))
    back = mask(n, n, shape(-0.16))
    light = (
        blur(front, 1.6 * ratio)[..., None] * rgb(CYAN) * 1.3
        + (front ** 1.5)[..., None] * (rgb(CYAN) * 0.5 + 0.6)
        + back[..., None] * rgb(CYAN) * 0.45
        + blur(back, 1.4 * ratio)[..., None] * rgb(CYAN) * 0.4
    )
    return glow(light.astype(np.float32))
