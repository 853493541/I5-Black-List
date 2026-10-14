"""漫画手账 Manga Sketchbook: the screen becomes a panel on a page of a manga sketchbook.

A margin of white paper comes up round the screen and two pens rule the panel's border in brush
ink from either side of the button, up the sides and across the top, where they meet. Its top left
corner, bottom right and bottom left are cut off on the slant, and screentone is rubbed on there,
dots worked out per pixel, thick at the corner and thinning away from it. Where the pens meet,
white focus lines burst in from every edge toward the middle, and stay, flickering as drawn lines
do. Sparkle diamonds pop over the tone and the edges. In the top right an inset panel is pasted
down at a tilt: a page of paper with a teal marker stroke and a band of tone, where a staff rules
itself, a treble clef writes itself and notes land on it one by one, then lift off and float away
across the top, over the title, as a conductor's notes would. At the end it all fades.

Its marks: the ring is a brush loop drawn round the button with a teal pencil line beside it and
manga emphasis strokes darting in at its ends; the badge is a round paper panel with a green crescent-leaf
sprout swaying in it, a blue bead on its tip; the card is a manga panel, thick ink border, tone in
its corner, a strip of teal washi tape on top and a little tilted, its names in 楷体 with a ♪ before
each.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPainter, QPainterPath, QPen, QPixmap, QPolygon, QPolygonF, QRegion, QTransform

from blacklist_detect.love_scenes.draw import (
    catmull,
    clamp,
    col,
    ease_back,
    ease_in,
    ease_in_out,
    ease_out,
    lengths,
    partial,
    spring,
    star,
    win,
)
from blacklist_detect.love_scenes.light import blur, mask, noise, picture, rgb, smooth

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 5.0
INK = "#17161b"
PAPER = "#fbf9f3"
TEAL = "#2fb3ac"
MINT = "#a6e6dc"
LEAF = "#86c25e"
LEAF_DARK = "#3f7f3a"
BEAD = "#8fd3f4"
LOOK = {
    "glow": (47, 179, 172),
    "rim": TEAL,
    "band": (INK, TEAL),
    "card": ("#fdfbf6", "#f4f1ea"),
    "edge": INK,
    "ink": INK,
    "flowers": (("#ffffff", "#e2e2e2", INK), ("#effaf8", MINT, TEAL)),
    "disc": ("#fdfbf6", "#ece8df"),
    "heart": ("#3a3a3a", INK),
    "deep": "#1f8a84",
    "deep_glow": (47, 179, 172),
}
MARKS_ANIMATED = True
# Room above the card for the washi tape and a sparkle.
CARD_TOP = 9
CARD_PAD = (15, 9, 15, 10)
# 楷体: names written with a brush, as the ink round them is.
CARD_FONT = "KaiTi"
# The pens meet at the top and the focus lines burst.
MEET = 1.05


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(23)
    g = 9 * u
    tl, bl, br = (270 * u, 200 * u), (150 * u, 110 * u), (210 * u, 150 * u)
    gx0, gx1 = gap.left() - 4 * u, gap.right() + 4 * u
    bottom = height - g
    # The panel's border, from beside the button on the left round by the top to beside it on the
    # right; its ends run off the bottom of the screen.
    corners = [
        QPointF(gx0, height + 8 * u), QPointF(gx0, bottom),
        QPointF(g + bl[0], bottom), QPointF(g, bottom - bl[1]),
        QPointF(g, g + tl[1]), QPointF(g + tl[0], g),
        QPointF(width - g, g),
        QPointF(width - g, bottom - br[1]), QPointF(width - g - br[0], bottom),
        QPointF(gx1, bottom), QPointF(gx1, height + 8 * u),
    ]  # fmt: skip
    line = _wobbled(_resample(corners, 3 * u), u, 0.7 * u, 5)
    along = lengths(line)
    wave = _waver(8)
    widths = [5.6 * u * (0.82 + 0.3 * wave(s / u)) * min(1.0, s / (22 * u), (along[-1] - s) / (22 * u)) for s in along]
    # The ink, and the paper's white showing just inside it, so the line stands off the dark game.
    sides = (_sides(line, [w + 3.6 * u for w in widths]), _sides(line, widths))
    meet = next(i for i, s in enumerate(along) if s >= along[-1] / 2)
    paper = QPainterPath()
    paper.addRect(QRectF(-2, -2, width + 4, height + 4))
    inside = QPainterPath()
    inside.addPolygon(QPolygonF(corners))
    inside.closeSubpath()
    paper = paper.subtracted(inside)
    # Where paper lies, cut into pieces round the edges: (rect, for a cut corner how far across it a
    # point is (0 at the corner's tip, 1 at the border) or None, the corner the tone is rubbed on
    # from and its two legs' far ends).
    a = 7 * u
    tl_rect = QRectF(0, 0, g + tl[0] + a, g + tl[1] + a)
    bl_rect = QRectF(0, bottom - bl[1] - a, g + bl[0] + a, height - (bottom - bl[1] - a))
    br_rect = QRectF(width - g - br[0] - a, bottom - br[1] - a, g + br[0] + a, height - (bottom - br[1] - a))
    pieces = [
        (tl_rect, lambda x, y: (x - g) / tl[0] + (y - g) / tl[1], (QPointF(0, 0), QPointF(g + tl[0], 0), QPointF(0, g + tl[1]))),
        (bl_rect, lambda x, y: (x - g) / bl[0] + (bottom - y) / bl[1], (QPointF(0, height), QPointF(g + bl[0], height), QPointF(0, bottom - bl[1]))),
        (br_rect, lambda x, y: (width - g - x) / br[0] + (bottom - y) / br[1], (QPointF(width, height), QPointF(width - g - br[0], height), QPointF(width, bottom - br[1]))),
        (QRectF(tl_rect.right(), 0, width - tl_rect.right(), g + a), None, None),
        (QRectF(0, tl_rect.bottom(), g + a, bl_rect.top() - tl_rect.bottom()), None, None),
        (QRectF(width - g - a, g + a, g + a, br_rect.top() - g - a), None, None),
        (QRectF(bl_rect.right(), bottom - a, gx0 + a - bl_rect.right(), height - bottom + a), None, None),
        (QRectF(gx1 - a, bottom - a, br_rect.left() - gx1 + a, height - bottom + a), None, None),
    ]
    names = QRectF(width * 0.13, height * 0.29, width * 0.81, height * 0.55)
    title = QRectF(width * 0.38, height * 0.07, width * 0.3, height * 0.18)
    inset = _Inset(QPointF(width - 32 * u - 195 * u, 24 * u + 83 * u), 390 * u, 166 * u, u, width)
    keep = (
        names.adjusted(-12 * u, -12 * u, 12 * u, 12 * u),
        title.adjusted(-8 * u, -6 * u, 8 * u, 6 * u),
        gap.adjusted(-26 * u, -26 * u, 26 * u, 26 * u),
        inset.bounds().adjusted(-10 * u, -10 * u, 10 * u, 10 * u),
    )
    rays = [_focus_lines(QPointF(width * 0.5, height * 0.47), corners[1:-1], keep, u, rnd) for _ in range(3)]
    rule = [_band(*side, 0, len(widths) - 1) for side in sides]
    sparkles = [
        (x * width, y * height, r * 1.5 * u, born, teal)
        for x, y, r, born, teal in (
            (0.026, 0.055, 15, 1.1, False), (0.07, 0.042, 9, 1.25, False), (0.04, 0.15, 11, 1.4, True),
            (0.1, 0.12, 7, 1.55, False), (0.016, 0.24, 7, 1.7, False), (0.94, 0.94, 13, 1.3, False),
            (0.905, 0.955, 8, 1.5, True), (0.978, 0.86, 7, 1.65, False), (0.028, 0.93, 10, 1.45, False),
            (0.066, 0.965, 6, 1.75, False), (0.04, 0.45, 8, 1.9, False), (0.088, 0.64, 6, 2.1, True),
            (0.968, 0.5, 7, 2.0, False), (0.975, 0.68, 6, 2.25, False), (0.745, 0.05, 9, 1.85, True),
            (0.735, 0.22, 6, 2.15, False), (0.355, 0.035, 6, 2.3, False),
        )
    ]  # fmt: skip
    glints = []
    while len(glints) < 22:
        x, y = rnd.uniform(0, width), rnd.uniform(0, height)
        if any(zone.contains(QPointF(x, y)) for zone in keep) or (0.2 * width < x < 0.8 * width and y > 0.3 * height):
            continue
        glints.append((x, y, rnd.uniform(2.5, 5.5) * u, rnd.uniform(1.0, 3.6), rnd.uniform(2, 5)))
    # The pictures, made once for each sharpness they are shown at.
    baked: dict[float, tuple] = {}

    def bake(scale: float) -> tuple:
        if scale not in baked:
            sheets = [(*_paper_piece(rect, scale, paper, rule, level, u, n), wipe) for n, (rect, level, wipe) in enumerate(pieces)]
            lines = [_pictures(variant, scale) for variant in rays]
            baked[scale] = (sheets, lines, inset.picture(scale))
        return baked[scale]

    def paint(p: QPainter, t: float) -> None:
        sheets, lines, inset_picture = bake(_sharpness(p))
        life = win(t, 0.0, 0.3) * (1 - ease_in(win(t, DURATION - 0.6, DURATION)))
        if life <= 0:
            return
        p.save()
        p.setOpacity(life)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        _rays(p, t, lines)
        _paper(p, t, sheets)
        _border(p, t, sides, meet)
        # Where the pens meet, a glint.
        flash = math.sin(math.pi * win(t, MEET - 0.05, MEET + 0.4))
        if flash > 0:
            star(p, line[meet].x(), line[meet].y(), 34 * u * flash, "#ffffff", flash, 0.06)
            _diamond(p, line[meet].x(), line[meet].y(), 9 * u * flash, 0, True, u)
        for x, y, r, born, teal in sparkles:
            _sparkle(p, t, x, y, r, born, teal, u)
        for x, y, r, born, rate in glints:
            k = ease_out(win(t, born, born + 0.3)) * (0.35 + 0.65 * abs(math.sin(t * rate + x)))
            star(p, x, y, r * (0.7 + 0.5 * k), "#ffffff", 0.85 * k, 0.1)
        inset.paint(p, t, inset_picture)
        p.restore()

    return paint


# The scene's parts, frame by frame.


def _rays(p: QPainter, t: float, lines: list[list[tuple[QRectF, QImage]]]) -> None:
    """The focus lines: they burst in when the pens meet, then stay faint, swapping set now and
    then as a drawn animation's lines do."""
    if t < MEET:
        return
    burst = math.exp(-(t - MEET) * 2.4)
    p.save()
    p.setOpacity(p.opacity() * ease_out(win(t, MEET, MEET + 0.06)) * (0.24 + 0.62 * burst))
    for rect, image in lines[int(t * 12) % len(lines)]:
        p.drawImage(rect, image)
    p.restore()


def _paper(p: QPainter, t: float, sheets: list[tuple]) -> None:
    """The paper margin, ruled once the pens have met, then the tone rubbed on from each cut corner."""
    p.save()
    p.setOpacity(p.opacity() * ease_out(win(t, 0.0, 0.4)))
    for rect, sheet, ruled, _tone, _wipe in sheets:
        p.drawImage(rect, ruled if t >= MEET else sheet)
    p.restore()
    for rect, _sheet, _ruled, tone, wipe in sheets:
        if tone is None:
            continue
        k = ease_in_out(win(t, 0.35, 0.95))
        if k <= 0:
            continue
        corner, a, b = wipe
        reach = 1.25 * k
        p.save()
        p.setClipRegion(_wedge(corner, a, b, reach))
        p.drawImage(rect, tone)
        p.restore()


def _wedge(corner: QPointF, a: QPointF, b: QPointF, reach: float) -> QRegion:
    """The triangle from corner toward a and b, reach of the way (past 1, past them)."""
    ends = [corner, corner + (a - corner) * reach, corner + (b - corner) * reach]
    return QRegion(QPolygon([point.toPoint() for point in ends]))


def _border(p: QPainter, t: float, sides: tuple, meet: int) -> None:
    """The panel's border, ruled by two pens in brush ink from the button's sides to the top (once
    they meet, the paper has it)."""
    k = ease_in_out(win(t, 0.05, MEET))
    if k <= 0 or t >= MEET:
        return
    last = len(sides[0][0]) - 1
    reach = round(meet * k)
    back = last - round((last - meet) * k)
    p.setPen(Qt.NoPen)
    for (left, right), shade in zip(sides, (col(PAPER), col(INK)), strict=True):
        p.setBrush(shade)
        for i0, i1, head in ((0, reach, reach), (back, last, back)):
            if i1 <= i0:
                continue
            # In short pieces, overlapping a little: one long thin shape is slow to fill.
            for j in range(i0, i1, 40):
                p.drawPolygon(_band(left, right, j, min(i1, j + 42)))
            tip = (left[head] + right[head]) / 2
            r = math.dist((left[head].x(), left[head].y()), (right[head].x(), right[head].y())) * 0.5
            p.drawEllipse(tip, r, r)


def _sparkle(p: QPainter, t: float, x: float, y: float, r: float, born: float, teal: bool, u: float) -> None:
    """A sparkle diamond: it pops in, turns a little and breathes; now and then it flashes."""
    k = ease_back(win(t, born, born + 0.4), 2.4)
    if k <= 0:
        return
    breathe = 0.9 + 0.1 * math.sin(t * 3.1 + x * 0.05)
    flash = max(0.0, math.sin(math.pi * win((t - born) % 1.9, 0.0, 0.35))) if t > born + 0.5 else 0.0
    turn = 6 * math.sin(t * 1.3 + y * 0.03)
    _diamond(p, x, y, r * k * breathe * (1 + 0.18 * flash), turn, teal, u)
    if flash > 0.05:
        star(p, x, y, r * (1.2 + 0.9 * flash), "#ffffff", flash, 0.07)


class _Inset:
    """The inset panel pasted down in the top right, its staff, clef and notes."""

    ANGLE = 2.4

    def __init__(self, centre: QPointF, width: float, height: float, u: float, stage_width: float) -> None:
        self.centre, self.width, self.height, self.u = centre, width, height, u
        # Past this, floating notes sink toward the top left corner: the title is behind them.
        self.sink = stage_width * 0.34
        self.margin = 18 * u
        self.space = 10 * u
        s = self.space
        self.left, self.right = -width / 2 + 16 * u, width / 2 - 16 * u
        self.top = 2 * u - 2 * s
        rnd = random.Random(7)
        # The staff's notes: (where along it, how high in half spaces from the bottom line, kind,
        # teal head); each lands, lifts off and floats away, and a second takes its place.
        tune = ((0.25, 4, "eighth"), (0.36, 6, "quarter"), (0.47, 3, "beam"), (0.62, 7, "eighth"), (0.73, 5, "sixteenth"), (0.85, 2, "eighth"))
        self.notes = []
        for i, (at, pitch, kind) in enumerate(tune):
            x = self.left + (self.right - self.left) * at
            lands = 1.85 + 0.12 * i
            leaves = 2.35 + 0.2 * i
            again = leaves + 0.55
            gone = again + 0.95 + 0.1 * i if i % 2 == 0 else 99.0
            self.notes.append((x, pitch, kind, i % 3 == 1, lands, leaves, rnd.random()))
            self.notes.append((x, (pitch + 3) % 8 + 1, ("eighth", "quarter", "sixteenth")[i % 3], i % 3 == 2, again, gone, rnd.random()))
        self.clef = _clef(s)
        self.paths: dict[str, QPainterPath] = {}

    def bounds(self) -> QRectF:
        return QRectF(self.centre.x() - self.width / 2, self.centre.y() - self.height / 2, self.width, self.height)

    def staff_y(self, x: float) -> float:
        """The staff's top line at x: it waves a little, as a line drawn by hand."""
        return self.top + 2.6 * self.u * math.sin(x / self.width * 4.4 + 0.6)

    def transform(self, t: float) -> QTransform:
        """It drops in, swings and settles."""
        k = ease_back(win(t, 0.5, 0.95), 1.6)
        swing = 8 * spring(t - 0.5, 1.5, 4.2)
        return QTransform().translate(self.centre.x(), self.centre.y() - 70 * self.u * (1 - k)).rotate(self.ANGLE + swing)

    def picture(self, scale: float) -> tuple[QRectF, QImage]:
        """Its paper, marker stroke, tone, border and shadow, worked out per pixel."""
        u, w, h, m = self.u, self.width, self.height, self.margin
        rect = QRectF(-w / 2 - m, -h / 2 - m, w + 2 * m, h + 2 * m)
        xs, ys = _pixels(rect, scale)
        inner = np.minimum(w / 2 - np.abs(xs), h / 2 - np.abs(ys)) * scale
        sheet = np.clip(inner + 0.5, 0, 1)
        shade = blur(np.clip(np.minimum(w / 2 - np.abs(xs - 5 * u), h / 2 - np.abs(ys - 7 * u)) * scale + 0.5, 0, 1), 5 * u * scale) * 0.55
        color = _grain(xs.shape, scale, 3) * rgb(PAPER)
        # A teal marker stroke across it, darker where the marker pooled at its edges, streaked.
        stroke = QPainterPath(QPointF(-w * 0.44, h * 0.2))
        stroke.cubicTo(QPointF(-w * 0.15, h * 0.32), QPointF(w * 0.12, -h * 0.28), QPointF(w * 0.43, -h * 0.08))
        swash = _mask_in(rect, scale, lambda q: q.strokePath(stroke, QPen(Qt.white, 34 * u, Qt.SolidLine, Qt.FlatCap)))
        swash = blur(swash, 0.8 * scale)
        streak = noise(1, xs.shape[0], 1.6 * scale, 2, 11)[:, :1]
        ink = swash * (0.5 + 0.18 * streak + 0.35 * np.clip(4 * swash * (1 - swash), 0, 1))
        color *= 1 - ink[..., None] * (1 - rgb(TEAL))
        # Tone along its bottom, in the panel's own lines.
        level = 0.5 * smooth(0.6, 1.02, (ys + h / 2) / h + 0.12 * xs / w)
        color = _inked(color, _screentone(xs * scale, ys * scale, level, 4.4 * u * scale))
        # A border ruled side by side, the lines crossing a little at the corners.
        over, bw = 3.5 * u, 5 * u
        border = np.zeros_like(xs)
        for along, across, half_a, half_b in ((xs, ys, w / 2, h / 2), (ys, xs, h / 2, w / 2)):
            for sign in (-1, 1):
                d = np.minimum(half_a + over - np.abs(along), bw * (0.85 + 0.15 * np.sin(along / (23 * u))) / 2 - np.abs(across - sign * (half_b - bw / 2)))
                border = np.maximum(border, np.clip(d * scale + 0.5, 0, 1))
        color = _inked(color, border)
        alpha = np.maximum(sheet, border)
        color = color * alpha[..., None] / np.maximum(alpha + shade * (1 - alpha), 1e-4)[..., None]
        return rect, picture(color, alpha + shade * (1 - alpha))

    def paint(self, p: QPainter, t: float, baked: tuple[QRectF, QImage]) -> None:
        shown = ease_out(win(t, 0.5, 0.7))
        if shown <= 0:
            return
        where = self.transform(t)
        rect, image = baked
        p.save()
        p.setOpacity(p.opacity() * shown)
        p.setTransform(where, True)
        p.drawImage(rect, image)
        self._staff(p, t)
        for x, pitch, kind, teal, lands, leaves, _seed in self.notes:
            if lands <= t < leaves:
                k = ease_back(win(t, lands, lands + 0.28), 2.6)
                self._note(p, QPointF(x, self._pitch_y(x, pitch)), kind, teal, k, 0.0, 0.0)
        p.restore()
        # Notes that have lifted off, floating away across the top.
        for x, pitch, kind, teal, _lands, leaves, seed in self.notes:
            age = t - leaves
            if 0 <= age < 2.6:
                start = where.map(QPointF(x, self._pitch_y(x, pitch)))
                self._float(p, start, age, kind, teal, seed)

    def _pitch_y(self, x: float, pitch: int) -> float:
        return self.staff_y(x) + 4 * self.space - pitch * self.space / 2

    def _staff(self, p: QPainter, t: float) -> None:
        """Five lines ruled left to right, a bar line at each end, then the clef written in."""
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(col(INK, 0.9), 1.1 * self.u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        xs = [self.left + (self.right - self.left) * i / 40 for i in range(41)]
        for line in range(5):
            k = ease_in_out(win(t, 1.0 + 0.07 * line, 1.55 + 0.07 * line))
            if k > 0:
                p.drawPolyline(QPolygonF(partial([QPointF(x, self.staff_y(x) + line * self.space) for x in xs], k)))
        bars = ease_out(win(t, 1.55, 1.75))
        for x in (self.left, self.right):
            if bars > 0:
                top = self.staff_y(x)
                p.drawLine(QPointF(x, top), QPointF(x, top + 4 * self.space * bars))
        k = ease_in_out(win(t, 1.4, 1.9))
        if k > 0:
            origin = QPointF(self.left + 3.2 * self.space, self.staff_y(self.left + 3.2 * self.space))
            points, widths = self.clef
            left, right = _sides([origin + point for point in points], widths)
            end = max(1, round((len(left) - 1) * k))
            p.setPen(Qt.NoPen)
            p.setBrush(col(INK))
            p.drawPolygon(_band(left, right, 0, end))
            if k >= 1:
                ball = origin + points[-1]
                p.drawEllipse(ball, self.space * 0.32, self.space * 0.32)

    def _note(self, p: QPainter, at: QPointF, kind: str, teal: bool, size: float, turn: float, halo: float) -> None:
        if size <= 0.01:
            return
        if kind not in self.paths:
            self.paths[kind] = _note_path(kind, self.space)
        p.save()
        p.translate(at)
        p.rotate(turn)
        p.scale(size, size)
        path = self.paths[kind]
        if halo > 0:
            p.strokePath(path, QPen(col("#ffffff", halo), 2.6 * self.u / size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.fillPath(path, col(INK))
        if teal:
            head = _note_head(0, 0, self.space * 0.82)
            p.fillPath(head, col(TEAL))
        p.restore()

    def _float(self, p: QPainter, start: QPointF, age: float, kind: str, teal: bool, seed: float) -> None:
        """A note floats up off the staff and away to the left, rocking, over the top of the title,
        and past it sinks toward the top left corner."""
        u = self.u
        x = start.x() - (250 + 160 * seed) * u * age - 30 * u * age * age
        # Over the title a note keeps its head low enough for its stem to fit above the words.
        past = max(0.0, self.sink - x)
        high = (45 + 3 * seed) * u + past * 0.36
        y = high + (start.y() - high) * math.exp(-4.0 * age) + 3 * u * math.sin(age * 2.6 + seed * 6)
        fade = min(1.0, age / 0.12) * (1 - _smoothstep(win(age, 1.9, 2.6)))
        size = 1 + 0.5 * _smoothstep(past / (220 * u))
        p.save()
        p.setOpacity(p.opacity() * fade)
        self._note(p, QPointF(x, y), kind, teal, size, -8 + 14 * math.sin(age * 2.1 + seed * 5), 1.0)
        p.restore()


def _smoothstep(k: float) -> float:
    """0 to 1 over k from 0 to 1, easing in and out."""
    k = clamp(k)
    return k * k * (3 - 2 * k)


def _focus_lines(centre: QPointF, corners: list[QPointF], keep: tuple[QRectF, ...], u: float, rnd: random.Random) -> QPainterPath:
    """Thin white wedges from the panel's border toward the middle, each stopping short of what
    must stay clear: the names, the title, the button and the inset."""
    edges = list(zip(corners, corners[1:], strict=False))
    path = QPainterPath()
    count = 120
    for i in range(count):
        angle = 2 * math.pi * (i + rnd.uniform(0, 0.9)) / count
        d = (math.cos(angle), math.sin(angle))
        reach = _ray(centre, d, edges)
        if reach is None:
            continue
        base = QPointF(centre.x() + d[0] * (reach + 2 * u), centre.y() + d[1] * (reach + 2 * u))
        length = rnd.uniform(70, 210) * u
        clear = 0.0
        for step in range(1, 25):
            k = length * step / 24
            point = QPointF(base.x() - d[0] * k, base.y() - d[1] * k)
            if any(zone.contains(point) for zone in keep):
                break
            clear = k
        if clear < 28 * u:
            continue
        half = rnd.uniform(0.6, 1.9) * u
        tip = QPointF(base.x() - d[0] * clear, base.y() - d[1] * clear)
        n = QPointF(-d[1] * half, d[0] * half)
        path.addPolygon(QPolygonF([base + n, tip, base - n]))
        path.closeSubpath()
    return path


def _ray(c: QPointF, d: tuple[float, float], edges: list[tuple[QPointF, QPointF]]) -> float | None:
    """How far from c along d the first edge is, or None."""
    best = None
    for a, b in edges:
        ex, ey = b.x() - a.x(), b.y() - a.y()
        den = d[0] * ey - d[1] * ex
        if abs(den) < 1e-9:
            continue
        wx, wy = a.x() - c.x(), a.y() - c.y()
        far = (wx * ey - wy * ex) / den
        at = (wx * d[1] - wy * d[0]) / den
        if far > 0 and 0 <= at <= 1 and (best is None or far < best):
            best = far
    return best


# Drawing: brush strokes, notes and diamonds.


def _resample(points: list[QPointF], step: float) -> list[QPointF]:
    """Points every step along a polyline, keeping its corners."""
    out = [points[0]]
    for a, b in zip(points, points[1:], strict=False):
        count = max(1, round(math.dist((a.x(), a.y()), (b.x(), b.y())) / step))
        out.extend(a + (b - a) * (i / count) for i in range(1, count + 1))
    return out


def _waver(seed: int):  # noqa: ANN202
    """A slow wander between -1 and 1 along a line: a few long waves at random phases."""
    rnd = random.Random(seed)
    waves = [(rnd.uniform(0.006, 0.04), rnd.uniform(0, 6.3), rnd.uniform(0.4, 1.0)) for _ in range(4)]
    total = sum(a for _f, _ph, a in waves)
    return lambda s: sum(a * math.sin(s * f + ph) for f, ph, a in waves) / total


def _wobbled(points: list[QPointF], u: float, amount: float, seed: int) -> list[QPointF]:
    """A line drawn by hand: pushed a little to either side, slowly, along its length."""
    wave = _waver(seed)
    out = []
    for i, (point, s) in enumerate(zip(points, lengths(points), strict=True)):
        a, b = points[max(0, i - 1)], points[min(len(points) - 1, i + 1)]
        dx, dy = b.x() - a.x(), b.y() - a.y()
        n = math.hypot(dx, dy) or 1
        out.append(QPointF(point.x() - dy / n * amount * wave(s / u), point.y() + dx / n * amount * wave(s / u)))
    return out


def _sides(points: list[QPointF], widths: list[float]) -> tuple[list[QPointF], list[QPointF]]:
    """The two edges of a brush stroke along points, widths wide, mitred at its corners."""
    left, right = [], []
    last = len(points) - 1
    for i, point in enumerate(points):
        a, b = points[max(0, i - 1)], points[min(last, i + 1)]
        dx, dy = b.x() - a.x(), b.y() - a.y()
        n = math.hypot(dx, dy) or 1
        nx, ny = -dy / n, dx / n
        miter = 1.0
        if 0 < i < last:
            ix, iy = point.x() - a.x(), point.y() - a.y()
            m = math.hypot(ix, iy) or 1
            miter = 1 / max(0.5, nx * -iy / m + ny * ix / m)
        h = widths[i] / 2 * miter
        left.append(QPointF(point.x() + nx * h, point.y() + ny * h))
        right.append(QPointF(point.x() - nx * h, point.y() - ny * h))
    return left, right


def _band(left: list[QPointF], right: list[QPointF], i0: int, i1: int) -> QPolygonF:
    return QPolygonF(left[i0 : i1 + 1] + right[i0 : i1 + 1][::-1])


def _clef(s: float) -> tuple[list[QPointF], list[float]]:
    """A treble clef as one brush stroke, s the staff's spacing, from the top line: it starts on
    the G line, curls out round it, climbs to the top loop and comes down the stem to its tail."""
    knots = (
        (0.05, 3.0, 0.16), (0.45, 2.55, 0.2), (0.15, 2.1, 0.22), (-0.45, 2.3, 0.3), (-0.8, 3.05, 0.36), (-0.4, 3.85, 0.3),
        (0.35, 4.05, 0.26), (0.95, 3.45, 0.32), (0.9, 2.45, 0.3), (0.3, 1.55, 0.26), (-0.25, 0.7, 0.24), (-0.3, -0.45, 0.2),
        (0.05, -1.45, 0.16), (0.4, -1.75, 0.15), (0.5, -1.05, 0.18), (0.2, -0.15, 0.22), (0.02, 1.4, 0.24), (0.12, 3.4, 0.24),
        (0.22, 4.95, 0.2), (0.02, 5.7, 0.17), (-0.42, 5.62, 0.15), (-0.5, 5.15, 0.14),
    )  # fmt: skip
    per = 7
    points = catmull([QPointF(x * s, y * s) for x, y, _w in knots], per)
    widths = []
    for i in range(len(points)):
        at = i / per
        j = min(len(knots) - 2, int(at))
        f = at - j
        widths.append((knots[j][2] * (1 - f) + knots[j + 1][2] * f) * s)
    return points, widths


def _note_head(x: float, y: float, s: float) -> QPainterPath:
    """A note's head at (x, y): an oval tipped up, s the staff's spacing."""
    head = QPainterPath()
    head.addEllipse(QPointF(0, 0), 0.68 * s, 0.47 * s)
    return QTransform().translate(x, y).rotate(-22).map(head)


def _note_path(kind: str, s: float) -> QPainterPath:
    """A note in ink, its head's middle at (0, 0), s the staff's spacing: a quarter, an eighth (♪),
    a sixteenth, or two eighths beamed (♫)."""
    path = QPainterPath()
    path.setFillRule(Qt.WindingFill)
    stem, tall = 0.14 * s, 3.3 * s
    heads = [(0.0, 0.0)] if kind != "beam" else [(0.0, 0.0), (1.9 * s, -0.5 * s)]
    for hx, hy in heads:
        path.addPath(_note_head(hx, hy, s))
        x = hx + 0.6 * s
        path.addRect(QRectF(x - stem, hy - tall, stem, tall - 0.1 * s))
    if kind == "beam":
        x0, x1 = 0.6 * s - stem, 2.5 * s
        path.addPolygon(QPolygonF([QPointF(x0, -tall), QPointF(x1, -tall - 0.5 * s), QPointF(x1, -tall + 0.05 * s), QPointF(x0, -tall + 0.55 * s)]))
        path.closeSubpath()
    flags = {"eighth": 1, "sixteenth": 2}.get(kind, 0)
    for f in range(flags):
        x0, y0 = 0.6 * s, -tall + f * 0.85 * s
        flag = QPainterPath(QPointF(x0 - stem, y0))
        flag.cubicTo(QPointF(x0 + 0.1 * s, y0 + 0.9 * s), QPointF(x0 + 1.35 * s, y0 + 1.15 * s), QPointF(x0 + 0.85 * s, y0 + 2.6 * s))
        flag.cubicTo(QPointF(x0 + 0.95 * s, y0 + 1.6 * s), QPointF(x0 + 0.3 * s, y0 + 1.35 * s), QPointF(x0 - stem, y0 + 1.15 * s))
        flag.closeSubpath()
        path.addPath(flag)
    return path


def _diamond_path(x: float, y: float, r: float) -> QPainterPath:
    """A tall diamond with sides bowed in a little, a sparkle in a shoujo manga."""
    w = r * 0.66
    path = QPainterPath(QPointF(x, y - r))
    for (ax, ay), (bx, by) in (((0, -r), (w, 0)), ((w, 0), (0, r)), ((0, r), (-w, 0)), ((-w, 0), (0, -r))):
        mx, my = (ax + bx) / 2 * 0.72, (ay + by) / 2 * 0.72
        path.quadTo(QPointF(x + mx, y + my), QPointF(x + bx, y + by))
    path.closeSubpath()
    return path


def _diamond(p: QPainter, x: float, y: float, r: float, turn: float, teal: bool, u: float) -> None:
    """A sparkle diamond in ink, white or teal, a smaller one inside it, and a white rim so it shows
    on the dark game as on the paper."""
    if r < 0.6:
        return
    p.save()
    p.translate(x, y)
    p.rotate(turn)
    outer = _diamond_path(0, 0, r)
    line = max(0.8, min(1.6, r * 0.12)) * u
    p.strokePath(outer, QPen(col("#ffffff", 0.95), line + 2.4 * u, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.fillPath(outer, col(MINT if teal else "#ffffff"))
    p.strokePath(outer, QPen(col(INK), line, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    inner = _diamond_path(0, 0, r * 0.48)
    if teal:
        p.fillPath(inner, col(TEAL))
    p.strokePath(inner, QPen(col(INK), line * 0.75, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.restore()


# Per pixel: paper, screentone and the pieces made of them.


def _sharpness(p: QPainter) -> float:
    """Pixels per point where p draws: its screen's and its own scaling."""
    device = p.device()
    ratio = device.devicePixelRatioF() if device is not None else 1.0
    return round(ratio * math.hypot(p.transform().m11(), p.transform().m12()), 2)


def _snapped(rect: QRectF, scale: float) -> QRectF:
    """rect with its edges on whole pixels, so pieces side by side meet without a seam."""
    x0, y0 = round(rect.left() * scale) / scale, round(rect.top() * scale) / scale
    x1, y1 = round(rect.right() * scale) / scale, round(rect.bottom() * scale) / scale
    return QRectF(x0, y0, max(1 / scale, x1 - x0), max(1 / scale, y1 - y0))


def _pixels(rect: QRectF, scale: float) -> tuple[np.ndarray, np.ndarray]:
    """Where each pixel's middle is, in points, of a picture of rect at scale pixels to the point."""
    w, h = max(1, round(rect.width() * scale)), max(1, round(rect.height() * scale))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    return rect.left() + (xs + 0.5) / scale, rect.top() + (ys + 0.5) / scale


def _mask_in(rect: QRectF, scale: float, draw) -> np.ndarray:  # noqa: ANN001
    """What draw paints in white over rect, in points, per pixel of a picture of it at scale."""
    w, h = max(1, round(rect.width() * scale)), max(1, round(rect.height() * scale))

    def placed(q: QPainter) -> None:
        q.scale(scale, scale)
        q.translate(-rect.left(), -rect.top())
        q.setPen(Qt.NoPen)
        draw(q)

    return mask(w, h, placed)


def _grain(shape: tuple[int, int], scale: float, seed: int) -> np.ndarray:
    """Paper: a fine, faint grain, as a shade to multiply a color by (h, w, 1): speckle softened
    over a couple of pixels (smooth noise over every piece of the margin is slow to work out)."""
    speck = np.random.default_rng(seed).random(shape, dtype=np.float32)
    reach = max(1, round(scale))
    fine = (speck + np.roll(speck, reach, 0) + np.roll(speck, reach, 1) + np.roll(speck, (reach, reach), (0, 1))) / 4
    return (0.975 + 0.05 * fine)[..., None]


def _screentone(x: np.ndarray, y: np.ndarray, level: np.ndarray | float, period: float) -> np.ndarray:
    """How much ink a 45° dot screen lays at each pixel (x, y in pixels): small dots where level is
    low, dots merging at a half, white holes left near 1. Smoothed to a pixel at their edges."""
    k = 2 * math.pi / (period * math.sqrt(2))
    a, b = (x + y) * k, (x - y) * k
    f = 0.5 + 0.25 * (np.cos(a) + np.cos(b))
    slope = 0.25 * k * math.sqrt(2) * np.sqrt(np.sin(a) ** 2 + np.sin(b) ** 2)
    cover = np.clip((f - (1 - level)) / np.maximum(slope, 0.05) + 0.5, 0, 1)
    return np.where(np.asarray(level) > 0.015, cover, 0.0).astype(np.float32)


def _inked(color: np.ndarray, ink: np.ndarray) -> np.ndarray:
    return color * (1 - ink[..., None]) + rgb(INK) * ink[..., None]


def _paper_piece(rect: QRectF, scale: float, paper: QPainterPath, rule: list[QPolygonF], level, u: float, seed: int) -> tuple:  # noqa: ANN001
    """A piece of the paper margin, then the same with the border ruled on it, and the tone on it
    if it is a cut corner: (rect, paper, ruled, tone)."""
    rect = _snapped(rect, scale)
    xs, ys = _pixels(rect, scale)
    alpha = _mask_in(rect, scale, lambda q: q.fillPath(paper, Qt.white))
    color = _grain(xs.shape, scale, 20 + seed) * rgb(PAPER)
    white, ink = (_mask_in(rect, scale, lambda q, shape=shape: q.fillPath(_shape(shape), Qt.white)) for shape in rule)
    ruled = picture(_inked(color, ink), np.maximum(np.maximum(alpha, white), ink))
    sheet = picture(color, alpha)
    if level is None:
        return rect, sheet, ruled, None
    q = level(xs, ys)
    amount = 0.97 * (1 - smooth(-0.12, 0.9, q)) ** 1.2
    tone = _screentone(xs * scale, ys * scale, amount, 5.0 * u * scale) * alpha
    return rect, sheet, ruled, picture(np.broadcast_to(rgb(INK), (*xs.shape, 3)), tone)


def _shape(polygon: QPolygonF) -> QPainterPath:
    path = QPainterPath()
    path.addPolygon(polygon)
    path.closeSubpath()
    return path


def _pictures(path: QPainterPath, scale: float) -> list[tuple[QRectF, QImage]]:
    """White shapes as pictures, one for each quarter of the screen they lie in, each only as big
    as what is in it: laid on, they cost far less than filling the shapes every frame."""
    middle = path.boundingRect().center()
    groups: dict[tuple[bool, bool], QPainterPath] = {}
    for polygon in path.toSubpathPolygons():
        at = polygon.boundingRect().center()
        groups.setdefault((at.x() < middle.x(), at.y() < middle.y()), QPainterPath()).addPolygon(polygon)
    out = []
    for group in groups.values():
        rect = _snapped(group.boundingRect().adjusted(-2, -2, 2, 2), scale)
        image = QImage(max(1, round(rect.width() * scale)), max(1, round(rect.height() * scale)), QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        q = QPainter(image)
        q.setRenderHint(QPainter.Antialiasing)
        q.scale(scale, scale)
        q.translate(-rect.left(), -rect.top())
        q.fillPath(group, col("#ffffff"))
        q.end()
        out.append((rect, image))
    return out


# The 心动 marks.

_cache: dict[tuple, object] = {}


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    """A loop of brush ink drawn round the button as a pen circles something, overshooting where
    it closes, a teal pencil loop beside it and emphasis strokes darting in at the button's ends."""
    c = cover.center()
    a, b = cover.width() / 2 + 2.5, cover.height() / 2 + 2.5
    k = 0.3 + 0.7 * ease_in_out(win(t, 0.0, 0.55))
    count = 200
    points, widths, pencil = [], [], []
    for i in range(count + 1):
        f = i / count
        angle = math.radians(200) + 2 * math.pi * 1.1 * f
        grow = -2.2 + 4.2 * f + 0.6 * math.sin(angle * 2 + 0.4)
        points.append(_squircle(c, a + grow, b + grow * 0.7, angle))
        pencil.append(_squircle(c, a - 4.5 + 1.2 * math.sin(angle * 2 + 2), b - 3.8, angle + 0.3))
        widths.append(0.6 + 4.0 * math.sin(math.pi * f ** 0.8) ** 0.7)
    end = max(2, round(count * k))
    p.setPen(QPen(col(TEAL, 0.9), 1.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawPolyline(QPolygonF(pencil[: max(2, round(len(pencil) * ease_out(win(t, 0.2, 0.75))))]))
    halo = _sides(points, [w + 1.8 for w in widths])
    left, right = _sides(points, widths)
    p.setPen(Qt.NoPen)
    p.setBrush(col("#ffffff", 0.85))
    p.drawPolygon(_band(*halo, 0, end))
    p.setBrush(col(INK))
    p.drawPolygon(_band(left, right, 0, end))
    # Emphasis strokes at the button's ends, pointing in at its words; every so often they dart in again.
    again = win(t % 2.6, 0.0, 0.25)
    dart = ease_out(win(t, 0.45, 0.75)) * (0.7 + 0.3 * ease_out(again) if t > 0.75 else 1.0)
    if dart <= 0:
        return
    size = cover.height() / 80
    for side in (-1, 1):
        for j, rise in enumerate((-0.3, -0.1, 0.1, 0.3)):
            start = QPointF(c.x() + side * (cover.width() / 2 - 5 * size), c.y() + rise * cover.height())
            d = QPointF(-side, -rise * 0.9)
            d /= math.hypot(d.x(), d.y())
            tip = start + d * (13 + 4 * (j % 2)) * size * dart
            n = QPointF(-d.y(), d.x())
            p.setBrush(col("#ffffff", 0.8))
            p.drawPolygon(QPolygonF([start + n * 2.6 * size, tip + d * 1.5, start - n * 2.6 * size]))
            p.setBrush(col(INK))
            p.drawPolygon(QPolygonF([start + n * 1.5 * size, tip, start - n * 1.5 * size]))


def _squircle(c: QPointF, a: float, b: float, angle: float) -> QPointF:
    """A point on a rounded box, between an ellipse and a rectangle, at angle round its middle."""
    cs, sn = math.cos(angle), math.sin(angle)
    return QPointF(c.x() + a * math.copysign(abs(cs) ** 0.42, cs), c.y() + b * math.copysign(abs(sn) ** 0.42, sn))


def badge(p: QPainter, box: QRectF, t: float) -> None:
    """A round paper panel with a crescent-leaf sprout in it, swaying, a glint on its bead now and then."""
    scale = max(2.0, _sharpness(p))
    side = box.width()
    disc_rect, disc = _badge_disc(side, scale)
    sprout_rect, sprout = _sprout(side, scale)
    c = box.center()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(disc_rect.translated(c), disc)
    base = QPointF(c.x() + side * 0.02, c.y() + side * 0.17)
    grow = 1.15 * (0.8 + 0.2 * ease_back(win(t, 0.0, 0.5), 2.2))
    sway = 6 * math.sin(t * 2.1) * (0.5 + 0.5 * ease_out(win(t, 0.0, 1.0)))
    p.save()
    p.translate(base)
    p.rotate(sway)
    p.scale(grow, grow)
    p.drawImage(sprout_rect, sprout)
    tip = QPointF(-side * 0.035, -side * 0.59)
    shine = math.sin(math.pi * win(t % 3.2, 1.2, 1.7))
    if shine > 0:
        star(p, tip.x() - side * 0.02, tip.y() - side * 0.02, side * 0.13 * shine, "#ffffff", shine, 0.1)
    p.restore()
    twinkle = 0.6 + 0.4 * math.sin(t * 2.7)
    _diamond(p, c.x() - side * 0.36, c.y() - side * 0.3, side * 0.1 * (0.8 + 0.2 * twinkle), 0, True, 1.0)


def _badge_disc(side: float, scale: float) -> tuple[QRectF, QImage]:
    """The badge's paper panel: a disc of paper, tone in its lower right, a brush ink rim, a shadow."""
    key = ("disc", round(side, 2), scale)
    if key not in _cache:
        r = side * 0.43
        rect = QRectF(-side / 2 - 6, -side / 2 - 6, side + 12, side + 12)
        xs, ys = _pixels(rect, scale)
        cy = side * 0.04
        dist = np.hypot(xs, ys - cy)
        sheet = np.clip((r - dist) * scale + 0.5, 0, 1)
        shade = blur(np.clip((r - np.hypot(xs - 1.2, ys - cy - 2.0)) * scale + 0.5, 0, 1), 1.6 * scale) * 0.6
        color = _grain(xs.shape, scale, 41) * rgb(PAPER)
        level = 0.5 * smooth(0.0, 1.0, (xs + ys - cy) / (r * 1.3) + 0.15)
        color = _inked(color, _screentone(xs * scale, ys * scale, level, 3.2 * scale) * (dist < r - 2.5))
        angle = np.arctan2(ys - cy, xs)
        rim_w = 2.0 + 0.7 * np.sin(angle * 2 + 0.8)
        rim = np.clip(np.minimum(r - dist, dist - (r - rim_w)) * scale + 0.5, 0, 1)
        teal = np.clip((0.5 - np.abs(dist - (r - rim_w - 1.6))) * scale + 0.5, 0, 1) * 0.8
        color = color * (1 - teal[..., None]) + rgb(TEAL) * teal[..., None]
        color = _inked(color, rim)
        alpha = sheet + shade * (1 - sheet)
        color = color * sheet[..., None] / np.maximum(alpha, 1e-4)[..., None]
        _cache[key] = (rect, picture(color, alpha))
    return _cache[key]


def _sprout(side: float, scale: float) -> tuple[QRectF, QImage]:
    """The crescent-leaf sprout, its stem's foot at (0, 0): a moon-shaped leaf in two tones of green
    with a crisp shadow along its inner curve, a midrib and a light catching its back, on a short
    stem, a glossy blue bead on its upper tip; edged in ink, a white rim round it all."""
    key = ("sprout", round(side, 2), scale)
    if key not in _cache:
        s = side
        rect = QRectF(-0.36 * s, -0.72 * s, 0.72 * s, 0.78 * s)
        xs, ys = _pixels(rect, scale)
        # The crescent: a disc with a bite out of its upper right. Distances in points, inside > 0.
        c1, r1 = (0.0, -0.35 * s), 0.23 * s
        c2, r2 = (0.11 * s, -0.45 * s), 0.2 * s
        d1 = r1 - np.hypot(xs - c1[0], ys - c1[1])
        d2 = np.hypot(xs - c2[0], ys - c2[1]) - r2
        leaf = np.minimum(d1, d2)
        stem = -np.min([np.hypot(xs - x, ys - y) for x, y in _curve((0.012 * s, 0), (0.03 * s, -0.07 * s), (-0.01 * s, -0.14 * s), 12)], axis=0)
        stem += 0.016 * s + 0.014 * s * np.clip(-ys / (0.14 * s), 0, 1)
        bx, by, br = -0.035 * s, -0.59 * s, 0.062 * s
        bead = br - np.hypot(xs - bx, ys - by)
        body = np.maximum(np.maximum(leaf, stem), bead)
        px = 1 / scale
        # Green in two tones, the shadow's edge crisp as in a cel, lighter toward the upper left.
        lean = np.clip(0.5 - (xs + ys + 0.35 * s) / (0.9 * s), 0, 1)[..., None]
        green = rgb("#5f9f45") + (rgb(LEAF) - rgb("#5f9f45")) * lean
        shadow = smooth(0.07 * s - px, 0.07 * s + px, d2)[..., None]
        color = rgb(LEAF_DARK) * 1.12 + (green - rgb(LEAF_DARK) * 1.12) * (0.25 + 0.75 * shadow)
        # A midrib down the middle of the crescent, fading out toward its tips.
        rib = np.clip(1 - np.abs(d1 - d2) / (0.012 * s + px), 0, 1) * smooth(0.0, 0.05 * s, leaf)
        color = color * (1 - 0.4 * rib[..., None])
        # Light along its back.
        back = np.clip(1 - np.abs(d1 - 0.035 * s) / (0.01 * s + px), 0, 1) * np.clip(-(xs + 0.2 * (ys - c1[1])) / (0.15 * s), 0, 1)
        color = color + (rgb("#e6f8c4") - color) * (0.8 * back)[..., None]
        color = np.where((stem > leaf)[..., None] & (stem > bead)[..., None], rgb("#5a9443") + (rgb(LEAF) - rgb("#5a9443")) * smooth(0.0, 0.02 * s, xs + 0.01 * s)[..., None], color)
        # The bead: a little glass ball, lit from the upper left.
        rr = np.clip(np.hypot(xs - bx, ys - by) / br, 0, 1)
        nz = np.sqrt(1 - rr ** 2)
        lit = np.clip(-(xs - bx) / br * 0.45 - (ys - by) / br * 0.55 + nz * 0.55, 0, 1)
        glass = rgb("#3a86bc") + (rgb(BEAD) - rgb("#3a86bc")) * lit[..., None] + (smooth(0.88, 0.97, lit) * 0.9)[..., None]
        on_bead = np.clip(bead * scale + 0.5, 0, 1)[..., None]
        color = color * (1 - on_bead) + glass * on_bead
        # Ink: the outline of it all, and the bead's own edge where it sits on the leaf.
        line = max(0.9, 0.028 * s)
        fill = np.clip(body * scale + 0.5, 0, 1)
        inked = np.clip((body + line) * scale + 0.5, 0, 1)
        edge = np.clip((line * 0.5 - np.abs(bead + line * 0.25)) * scale + 0.5, 0, 1) * (leaf > -line)
        color = color * (1 - edge[..., None]) + rgb(INK) * edge[..., None]
        color = color * fill[..., None] + rgb(INK) * (inked - fill)[..., None]
        # The rim only where it rises past the panel's top: inside, the paper is white already.
        rim = np.maximum(np.clip((body + line + 0.03 * s) * scale + 0.5, 0, 1) * smooth(-0.4 * s, -0.5 * s, ys), inked)
        color = color + rgb("#ffffff") * (rim - inked)[..., None]
        _cache[key] = (rect, picture(color / np.maximum(rim, 1e-4)[..., None], rim))
    return _cache[key]


def _curve(a: tuple, c: tuple, b: tuple, count: int) -> list[tuple[float, float]]:
    """Points along a quadratic curve from a to b, pulled toward c."""
    out = []
    for i in range(count + 1):
        k = i / count
        m = 1 - k
        out.append((m * m * a[0] + 2 * m * k * c[0] + k * k * b[0], m * m * a[1] + 2 * m * k * c[1] + k * k * b[1]))
    return out


def card(p: QPainter, rect: QRectF, t: float) -> None:
    """A manga panel a little tilted: paper with tone in its lower right, a thick ink border ruled
    side by side, teal washi tape holding its top, and a sparkle by its corner."""
    scale = max(1.0, _sharpness(p))
    key = ("card", round(rect.width()), round(rect.height()), scale)
    if key not in _cache:
        _cache[key] = _card_picture(rect.width(), rect.height(), scale)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(QRectF(0, 0, rect.width(), rect.height()).translated(rect.topLeft()), _cache[key])
    twinkle = 0.75 + 0.25 * math.sin(t * 2.6)
    flash = max(0.0, math.sin(math.pi * win(t % 2.8, 0.0, 0.4)))
    x, y = rect.right() - 9, rect.top() + CARD_TOP + 1
    _diamond(p, x, y, 5.5 * twinkle * (1 + 0.2 * flash), 8 * math.sin(t * 1.2), False, 1.0)
    if flash > 0.05:
        star(p, x, y, 8 * flash, "#ffffff", flash, 0.08)
    _diamond(p, x - 9, y + 4, 3.2 * (1.5 - twinkle), 0, True, 1.0)


def _card_picture(width: float, height: float, scale: float) -> QImage:
    rect = QRectF(0, 0, width, height)
    xs, ys = _pixels(rect, scale)
    body = QRectF(3.5, CARD_TOP + 1.5, width - 7.5, height - CARD_TOP - 5)
    cx, cy = body.center().x(), body.center().y()
    turn = math.radians(-1.3)
    lx = (xs - cx) * math.cos(turn) + (ys - cy) * math.sin(turn)
    ly = -(xs - cx) * math.sin(turn) + (ys - cy) * math.cos(turn)
    hw, hh = body.width() / 2, body.height() / 2
    sheet = np.clip(np.minimum(hw - np.abs(lx), hh - np.abs(ly)) * scale + 0.5, 0, 1)
    shade = blur(np.clip(np.minimum(hw - np.abs(lx - 1.5), hh - np.abs(ly - 2.5)) * scale + 0.5, 0, 1), 2.2 * scale) * 0.6
    color = _grain(xs.shape, scale, 5) * rgb(PAPER)
    # Tone in the margins round the names: down the right edge, thickest at the bottom, and along the bottom.
    level = 0.55 * np.maximum((1 - smooth(1, 13, hw - lx)) * smooth(-0.3, 1, (ly + hh) / (2 * hh)), (1 - smooth(1, 8, hh - ly)) * smooth(0.2, 1, (lx + hw) / (2 * hw)))
    color = _inked(color, _screentone(lx * scale, ly * scale, level, 3.4 * scale) * (np.minimum(hw - np.abs(lx), hh - np.abs(ly)) > 2))
    over, bw = 2.0, 2.6
    border = np.zeros_like(xs)
    for along, across, half_a, half_b in ((lx, ly, hw, hh), (ly, lx, hh, hw)):
        for sign in (-1, 1):
            w = bw * (0.85 + 0.2 * np.sin(along * 0.11 + sign))
            d = np.minimum(half_a + over - np.abs(along), w / 2 - np.abs(across - sign * (half_b - bw / 2)))
            border = np.maximum(border, np.clip(d * scale + 0.5, 0, 1))
    color = _inked(color, border)
    alpha = np.maximum(sheet, border)
    # Teal washi tape over the top edge, its ends torn, little white dots printed on it.
    tx = lx - (hw * 0.38)
    ty = ly + hh - 0.5
    tape_turn = math.radians(-7)
    ax = tx * math.cos(tape_turn) + ty * math.sin(tape_turn)
    ay = -tx * math.sin(tape_turn) + ty * math.cos(tape_turn)
    torn = 1.1 * np.abs(((ay * 0.9) % 2) - 1)
    tape = np.clip(np.minimum(4.6 - np.abs(ay), 15 + torn - np.abs(ax)) * scale + 0.5, 0, 1)
    fibre = noise(xs.shape[1], xs.shape[0], 1.3 * scale, 2, 8)
    dots = _screentone(ax * scale, ay * scale, 0.16, 3.4 * scale)
    tint = rgb("#5fc9bf") * (0.94 + 0.12 * fibre)[..., None]
    tint = tint * (1 - dots[..., None]) + rgb("#f4fffd") * dots[..., None]
    cover = tape * 0.82
    color = color * alpha[..., None] * (1 - cover[..., None]) + tint * cover[..., None]
    alpha = alpha + cover * (1 - alpha)
    color = color / np.maximum(alpha, 1e-4)[..., None]
    total = alpha + shade * (1 - alpha)
    color = color * alpha[..., None] / np.maximum(total, 1e-4)[..., None]
    return picture(color, total)


def lead(size: float, index: int) -> QPixmap:
    """♪ before each name, in ink, every other one with a teal head."""
    ratio = 3.0
    image = QPixmap(round(size * ratio), round(size * ratio))
    image.setDevicePixelRatio(ratio)
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    s = size * 0.21
    p.translate(size * 0.36, size * 0.78)
    p.fillPath(_note_path("eighth", s), col(INK))
    if index % 2:
        p.fillPath(_note_head(0, 0, s * 0.8), col(TEAL))
    p.end()
    return image
