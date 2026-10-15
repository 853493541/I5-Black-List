"""The cast of 喜羊羊与灰太狼 for the 喜羊羊 scene, drawn as the show draws them: 喜羊羊, 美羊羊, 懒羊羊 and
沸羊羊, 灰太狼 and 红太狼 with her frying pan.

Each is drawn in code, part by part, in the show's clean look: bold dark outlines and its flat colors
with a cel shadow on the side away from the light. On top of that the light is worked out per pixel,
as the HD episodes have it: each part rounded so its shadow follows its form, a soft shadow cast where
one part lies over another, creases shaded, a soft rim of light on the far edge, and the wool fluffy at
its edge and shaded puff by puff. A character comes back as a picture standing on (0, 0), s tall.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPainterPathStroker, QPen, QRadialGradient, QTransform

from blacklist_detect.love_scenes.draw import col
from blacklist_detect.love_scenes.light import blur, mask, noise, picture, rgb, smooth

if TYPE_CHECKING:
    from collections.abc import Callable

# The ink of every outline, and how wide a part's outline is, as a share of the character's height.
LINE = "#2b1c16"
LINE_W = 0.0105
# The lambs: wool, face, horns, hooves; 喜羊羊's bell on its blue ribbon and his shoes; 美羊羊's pink;
# 懒羊羊's bib; 沸羊羊's tan.
WOOL = "#fdfdff"
WOOL_SHADE = "#c3c6dd"
SKIN = "#f3d2b3"
SKIN_SHADE = "#d6a482"
HORN = "#6b4228"
HOOF = "#4a2e20"
RIBBON = "#2c7be5"
BELL = "#f6c431"
SHOE = "#2f6fd8"
PINK = "#f37fae"
BIB = "#ffd23f"
TAN = "#c98b58"
# The wolves: their grey, muzzle and belly; his cap and its patch; her crown, robe and the pan.
FUR = "#6f7480"
FUR_SHADE = "#4a4e5e"
FUR_LIGHT = "#c9ccd6"
CAP = "#e2532b"
PATCH = "#f7c641"
GOLD = "#f4c23c"
ROBE = "#d8282f"
IRON = "#2b2c31"

# Light from the upper left, and halfway between it and the eye, for gloss.
LIGHT = np.array([-0.5, -0.62, 0.6]) / np.linalg.norm([-0.5, -0.62, 0.6])
HALF = (LIGHT + [0, 0, 1]) / np.linalg.norm(LIGHT + [0, 0, 1])


# Shapes.


def ellipse(x: float, y: float, rx: float, ry: float, angle: float = 0.0) -> QPainterPath:
    path = QPainterPath()
    path.addEllipse(QPointF(0, 0), rx, ry)
    return QTransform().translate(x, y).rotate(angle).map(path)


def limb(points: list[tuple[float, float]], width: float) -> QPainterPath:
    """A rounded limb through points (two, or three for a bend), width wide."""
    line = QPainterPath(QPointF(*points[0]))
    if len(points) == 3:
        line.quadTo(QPointF(*points[1]), QPointF(*points[2]))
    else:
        line.lineTo(QPointF(*points[1]))
    stroker = QPainterPathStroker()
    stroker.setWidth(width)
    stroker.setCapStyle(Qt.RoundCap)
    stroker.setJoinStyle(Qt.RoundJoin)
    return stroker.createStroke(line).simplified()


def polygon(points: list[tuple[float, float]], round_by: float = 0.0) -> QPainterPath:
    """A closed shape through points; its corners rounded off round_by of the way along each side."""
    if not round_by:
        path = QPainterPath(QPointF(*points[0]))
        for point in points[1:]:
            path.lineTo(QPointF(*point))
        path.closeSubpath()
        return path
    corners = [QPointF(*point) for point in points]
    n = len(corners)

    def toward(a: QPointF, b: QPointF) -> QPointF:
        return a + (b - a) * round_by

    path = QPainterPath(toward(corners[0], corners[1]))
    for i in range(1, n + 1):
        corner, after = corners[i % n], corners[(i + 1) % n]
        path.lineTo(toward(corner, corners[i - 1]))
        path.quadTo(corner, toward(corner, after))
    path.closeSubpath()
    return path


def spline(points: list[tuple[float, float]], closed: bool = True) -> QPainterPath:
    """A smooth curve through points, closed round to the first unless closed is False."""
    pts = [QPointF(*point) for point in points]
    n = len(pts)
    path = QPainterPath(pts[0])
    for i in range(n if closed else n - 1):
        before = pts[(i - 1) % n] if closed or i > 0 else pts[0]
        here, after = pts[i], pts[(i + 1) % n]
        later = pts[(i + 2) % n] if closed or i + 2 < n else pts[-1]
        path.cubicTo(here + (after - before) / 6, after - (later - here) / 6, after)
    if closed:
        path.closeSubpath()
    return path


def taper(points: list[tuple[float, float]], start: float, end: float, steps: int = 36) -> QPainterPath:
    """A stroke along a smooth curve through points, start wide at its first point and end at its last."""
    line = spline(points, closed=False)
    left, right = [], []
    for i in range(steps + 1):
        k = i / steps
        at = line.pointAtPercent(k)
        a = math.radians(line.angleAtPercent(k))
        normal = QPointF(math.sin(a), math.cos(a)) * ((start + (end - start) * k) / 2)
        left.append(at + normal)
        right.append(at - normal)
    path = QPainterPath(left[0])
    for point in left[1:] + right[::-1]:
        path.lineTo(point)
    path.closeSubpath()
    return path


def scaled(points: list[tuple[float, float]], s: float, dx: float = 0.0, dy: float = 0.0, flip: int = 1) -> list[tuple[float, float]]:
    """Points given as shares of s, in points, moved by (dx, dy) shares and mirrored when flip is -1."""
    return [((x * flip + dx) * s, (y + dy) * s) for x, y in points]


def puff_ring(x: float, y: float, rx: float, ry: float, count: int, r: float, rnd: random.Random, fill: bool = True) -> list[tuple[float, float, float]]:
    """Wool puffs round an ellipse, each about r, and one filling its middle."""
    out = []
    start = rnd.random()
    for i in range(count):
        a = 2 * math.pi * (i / count + start)
        out.append((x + rx * math.cos(a), y + ry * math.sin(a), r * rnd.uniform(0.86, 1.14)))
    if fill:
        out.append((x, y, min(rx, ry) + r * 0.7))
    return out


def _shift(a: np.ndarray, dx: float, dy: float) -> np.ndarray:
    """a moved dx pixels right and dy down, what comes in empty."""
    dx, dy = round(dx), round(dy)
    h, w = a.shape
    out = np.zeros_like(a)
    if abs(dx) >= w or abs(dy) >= h:
        return out
    out[max(0, dy) : h + min(0, dy), max(0, dx) : w + min(0, dx)] = a[max(0, -dy) : h + min(0, -dy), max(0, -dx) : w + min(0, -dx)]
    return out


def shade_of(tint: str) -> str:
    """A color's cel shadow, darker and a little cooler, as the show paints it."""
    c = rgb(tint)
    shadow = c * 0.74 + rgb("#3c3f78") * 0.1
    return QColor.fromRgbF(*np.clip(shadow, 0, 1).tolist()).name()


class Toon:
    """A character drawn part by part, at scale pixels to the point in box (points), size tall: each
    part its flat color and the cel shadow it takes away from the light, rounded from its edges so the
    shadow follows its form, a later part over an earlier one and casting a soft shadow on it, its
    outline in ink; wool piled up in puffs, each shaded, fluffy at its edge. Then lit per pixel."""

    def __init__(self, box: QRectF, scale: float, size: float, *, seed: int = 1) -> None:
        self.box, self.scale, self.size, self.seed = box, scale, size, seed
        self.w, self.h = max(1, math.ceil(box.width() * scale)), max(1, math.ceil(box.height() * scale))
        self.sx, self.sy = self.w / box.width(), self.h / box.height()
        shape = (self.h, self.w)
        self.color = np.zeros((*shape, 3), dtype=np.float32)
        self.shade = np.zeros((*shape, 3), dtype=np.float32)
        self.alpha = np.zeros(shape, dtype=np.float32)
        self.bump = np.zeros(shape, dtype=np.float32)
        self.gloss = np.zeros(shape, dtype=np.float32)
        self.grain = np.zeros(shape, dtype=np.float32)
        self.ink = np.zeros(shape, dtype=np.float32)
        self.cast = np.zeros(shape, dtype=np.float32)
        self.cel = np.ones(shape, dtype=np.float32)
        # Fine relief, as wool's curls: in the soft light only, never the cel shadow.
        self.fine = np.zeros(shape, dtype=np.float32)

    @property
    def px(self) -> float:
        """Pixels to one hundredth of the character's height."""
        return 0.01 * self.size * self.scale

    def place(self, q: QPainter) -> None:
        q.scale(self.sx, self.sy)
        q.translate(-self.box.left(), -self.box.top())

    def mask(self, path: QPainterPath) -> np.ndarray:
        def draw(q: QPainter) -> None:
            self.place(q)
            q.fillPath(path, QColor("#ffffff"))

        return mask(self.w, self.h, draw)

    def part(
        self,
        path: QPainterPath,
        tint: str,
        shade: str | None = None,
        *,
        soft: float = 2.0,
        swell: float = 1.0,
        rest: float = 0.0,
        gloss: float = 0.0,
        grain: float = 0.03,
        line: float = 1.0,
        cast: float = 0.55,
        cel: float = 1.0,
    ) -> None:
        """A part in tint, its shadow side in shade, rounded up from its edges over soft hundredths of
        the height (swell less than 0 dishes it in), resting on what is under it by rest; its outline
        line times the usual width; cast, how dark a shadow it throws on what is under it."""
        m = self.mask(path)
        px = max(1.0, soft * self.px)
        height = np.sqrt(np.clip(2 * blur(m, px) - 1, 0, 1)) * px * swell
        if rest:
            height = height + blur(self.bump, px) * rest
        self._lay(m, tint, shade, height, gloss, grain, cast, cel)
        if line:
            self.outline(path, line)

    def wool(
        self,
        puffs: list[tuple[float, float, float]],
        tint: str = WOOL,
        shade: str = WOOL_SHADE,
        *,
        flat: float = 0.6,
        curl: float = 1.0,
        fuzz: float = 1.0,
        line: float = 1.0,
        cast: float = 0.55,
        clip: QPainterPath | None = None,
    ) -> None:
        """Round puffs (x, y, r) piled up into one heap of wool: each a ball flat times as deep as it is
        wide, so each takes its own crescent of shadow and two meeting make a crease; curled all over in
        the soft light (curl), its edge and outline wavering a little like fluff (fuzz)."""
        m = np.zeros((self.h, self.w), dtype=np.float32)
        height = np.zeros((self.h, self.w), dtype=np.float32)
        xs = np.arange(self.w, dtype=np.float32) + 0.5
        ys = np.arange(self.h, dtype=np.float32) + 0.5
        for x, y, r in puffs:
            cx, cy, rp = (x - self.box.left()) * self.sx, (y - self.box.top()) * self.sy, r * self.sx
            x0, x1 = max(0, int(cx - rp - 2)), min(self.w, int(cx + rp + 3))
            y0, y1 = max(0, int(cy - rp - 2)), min(self.h, int(cy + rp + 3))
            if x0 >= x1 or y0 >= y1:
                continue
            d = np.hypot(xs[None, x0:x1] - cx, ys[y0:y1, None] - cy)
            disc = np.clip(rp - d + 0.5, 0, 1)
            ball = np.sqrt(np.clip(1 - (d / rp) ** 2, 0, 1)) * rp * flat
            m[y0:y1, x0:x1] = np.maximum(m[y0:y1, x0:x1], disc)
            height[y0:y1, x0:x1] = np.maximum(height[y0:y1, x0:x1], ball)
        if clip is not None:
            m *= self.mask(clip)
        seed = self.seed + len(puffs)
        if fuzz:
            # The edge wavers by about a pixel or two, as fluff does.
            hair = noise(self.w, self.h, max(1.5, 0.45 * self.px), 2, seed)
            soft = blur(m, max(0.7, 0.25 * fuzz * self.px))
            m = smooth(0.38, 0.62, soft + (hair - 0.5) * 0.5 * fuzz) * (soft > 0.02)
        self._lay(m, tint, shade, height, 0.0, 0.04, cast, 1.0)
        if curl:
            self.fine += (noise(self.w, self.h, max(2.0, 1.6 * self.px), 3, seed + 1) - 0.5) * curl * 2.2 * self.px * m
        if line:
            width = max(0.9, line * LINE_W * self.size * self.scale)
            inner = blur(m, 0.6 * width)
            self.ink = np.maximum(self.ink, m * (1 - smooth(0.66, 0.86, inner)))

    def blush(self, path: QPainterPath, tint: str, soft: float, amount: float) -> None:
        """A soft flush of tint over what is there, as on a cheek; soft in hundredths of the height."""
        k = (blur(self.mask(path), max(1.0, soft * self.px)) * amount)[..., None]
        self.color += (rgb(tint) - self.color) * k
        self.shade += (rgb(shade_of(tint)) - self.shade) * k * 0.7

    def outline(self, path: QPainterPath, line: float = 1.0) -> None:
        stroker = QPainterPathStroker()
        stroker.setWidth(line * LINE_W * self.size)
        stroker.setCapStyle(Qt.RoundCap)
        stroker.setJoinStyle(Qt.RoundJoin)
        self.ink = np.maximum(self.ink, self.mask(stroker.createStroke(path)))

    def _lay(self, m: np.ndarray, tint: str, shade: str | None, height: np.ndarray, gloss: float, grain: float, cast: float, cel: float) -> None:
        # The shadow this part throws down and to the right, on what is under it.
        self.cast *= 1 - m
        if cast:
            r = 1.6 * self.px
            fall = blur(_shift(m, 0.5 * r, 0.9 * r), r) * (1 - m) * cast
            self.cast = np.maximum(self.cast, fall * self.alpha)
        k = m[..., None]
        self.color += (rgb(tint) - self.color) * k
        self.shade += (rgb(shade or shade_of(tint)) - self.shade) * k
        self.alpha = np.maximum(self.alpha, m)
        self.bump += (height - self.bump) * m
        self.gloss += (gloss - self.gloss) * m
        self.grain += (grain - self.grain) * m
        self.cel += (cel - self.cel) * m
        self.fine *= 1 - m
        self.ink *= 1 - m

    def render(self, after: Callable[[QPainter], None] | None = None, *, edge: float = 0.4, rim: float = 0.5, ao: float = 0.4) -> QImage:
        """The character lit: the cel shadow where a part turns from the light past edge, softened a
        little per pixel, creases and cast shadows darkened, a rim of warm light on the far edges and a
        hard shine where a part is glossy; its outlines in ink, the outer one bolder. after draws on top
        (eyes, mouths) in the box's points."""
        gy, gx = np.gradient(self.bump)
        nz = 1 / np.sqrt(1 + gx * gx + gy * gy)
        nx, ny = -gx * nz, -gy * nz
        d = nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]
        lit = smooth(edge - 0.035, edge + 0.035, d)
        lit = 1 - (1 - lit) * self.cel
        color = self.shade + (self.color - self.shade) * lit[..., None]
        # Soft light within the flat colors: a touch lighter toward the light, darker in the creases.
        reach = max(1.5, 1.2 * self.px)
        crease = np.clip((blur(self.bump, reach * 2) - self.bump) / (reach * 1.5), 0, 1)
        fy, fx = np.gradient(self.bump + self.fine)
        fz = 1 / np.sqrt(1 + fx * fx + fy * fy)
        fine = -fx * fz * LIGHT[0] - fy * fz * LIGHT[1] + fz * LIGHT[2]
        soft = (1 + 0.22 * (d - LIGHT[2]) + 0.35 * (fine - d)) * (1 - ao * crease) * (1 - 0.5 * self.cast)
        texture = 1 + self.grain * (noise(self.w, self.h, max(2.0, 0.5 * self.px), 2, self.seed + 7) - 0.5) * 2
        color = color * (soft * texture)[..., None] + (self.cast * 0.12)[..., None] * rgb("#3c3f78")
        # A rim of warm light round the far side of the outline, from behind on the right.
        width = max(1.0, 0.9 * self.px)
        held = blur(self.alpha, width)
        hy, hx = np.gradient(held)
        g = np.maximum(np.hypot(hx, hy), 1e-5)
        facing = np.clip((-hx * 0.85 + hy * 0.35) / g, 0, 1)
        band = self.alpha * (1 - smooth(0.55, 0.92, held))
        color += (band * facing * rim)[..., None] * rgb("#fff3dc") * 0.55
        sheen = np.clip(nx * HALF[0] + ny * HALF[1] + nz * HALF[2], 0, 1) ** 24
        color += (smooth(0.45, 0.6, sheen) * 0.55 + sheen * 0.25)[..., None] * self.gloss[..., None]
        # The outer outline bolder than the lines within.
        thick = max(1.0, 0.55 * LINE_W * self.size * self.scale)
        outer = self.alpha * (1 - smooth(0.62, 0.9, blur(self.alpha, thick)))
        ink = np.maximum(self.ink, outer)
        color = color * (1 - ink[..., None]) + rgb(LINE) * ink[..., None]
        image = picture(color, np.maximum(self.alpha, ink)).convertToFormat(QImage.Format_ARGB32_Premultiplied)
        if after is not None:
            q = QPainter(image)
            q.setRenderHint(QPainter.Antialiasing)
            self.place(q)
            after(q)
            q.end()
        image.setDevicePixelRatio(self.sx)
        return image


# Faces: eyes, brows and mouths, drawn flat over the lit picture, as the show draws them.


def eye(
    q: QPainter,
    at: QPointF,
    rx: float,
    ry: float,
    iris: str,
    *,
    look: QPointF | None = None,
    lid: float = 0.0,
    lid_color: str = SKIN,
    lashes: int = 0,
    line: float = 1.0,
    pupil: float = 0.55,
    iris_size: float = 0.8,
) -> None:
    """A big cartoon eye about at, rx by ry: a white with a shadow under its lid, an iris shaded
    from dark at the top, a pupil, two shines; looking by look (shares of rx, ry); its upper lid down
    by lid (0 open, 1 shut) in lid_color; lashes flicking out from its outer corner (1 left, -1 right
    side of the face, 0 none). line is the outline's width."""
    look = look or QPointF(0, 0)
    white = QPainterPath()
    white.addEllipse(at, rx, ry)
    q.fillPath(white, QColor("#ffffff"))
    q.save()
    q.setClipPath(white)
    shadow = QLinearGradient(QPointF(at.x(), at.y() - ry), QPointF(at.x(), at.y()))
    shadow.setColorAt(0, col("#9aa0c8", 0.55))
    shadow.setColorAt(1, col("#9aa0c8", 0))
    q.fillRect(QRectF(at.x() - rx, at.y() - ry, 2 * rx, ry), shadow)
    middle = at + QPointF(look.x() * rx, look.y() * ry)
    irx, iry = rx * iris_size, ry * iris_size
    tone = QLinearGradient(QPointF(middle.x(), middle.y() - iry), QPointF(middle.x(), middle.y() + iry))
    base = QColor(iris)
    tone.setColorAt(0, base.darker(190))
    tone.setColorAt(0.55, base)
    tone.setColorAt(1, base.lighter(150))
    q.setPen(Qt.NoPen)
    q.setBrush(tone)
    q.drawEllipse(middle, irx, iry)
    q.setBrush(QColor("#120a08"))
    q.drawEllipse(middle + QPointF(0, iry * 0.06), irx * pupil, iry * pupil)
    q.setBrush(QColor("#ffffff"))
    q.drawEllipse(middle + QPointF(-irx * 0.36, -iry * 0.38), irx * 0.32, iry * 0.3)
    q.drawEllipse(middle + QPointF(irx * 0.38, iry * 0.4), irx * 0.13, iry * 0.12)
    if lid > 0:
        top = at.y() - ry - 2
        bottom = at.y() - ry + 2 * ry * lid
        lid_path = QPainterPath(QPointF(at.x() - rx - 2, top))
        lid_path.lineTo(QPointF(at.x() + rx + 2, top))
        lid_path.lineTo(QPointF(at.x() + rx + 2, bottom - ry * 0.1))
        lid_path.quadTo(QPointF(at.x(), bottom + ry * 0.12), QPointF(at.x() - rx - 2, bottom - ry * 0.1))
        lid_path.closeSubpath()
        q.fillPath(lid_path, QColor(lid_color))
        q.strokePath(lid_path, QPen(col(LINE), line * 1.1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    q.restore()
    q.strokePath(white, QPen(col(LINE), line))
    # The upper lid's line, bolder.
    upper = QPainterPath()
    upper.arcMoveTo(QRectF(at.x() - rx, at.y() - ry, 2 * rx, 2 * ry), 200)
    upper.arcTo(QRectF(at.x() - rx, at.y() - ry, 2 * rx, 2 * ry), 200, -220)
    if lid <= 0:
        q.strokePath(upper, QPen(col(LINE), line * 1.9, Qt.SolidLine, Qt.RoundCap))
    if lashes:
        q.setPen(QPen(col(LINE), line * 1.3, Qt.SolidLine, Qt.RoundCap))
        for k in range(3):
            a = math.radians(150 - k * 22) if lashes > 0 else math.radians(30 + k * 22)
            root = at + QPointF(math.cos(a) * rx, -math.sin(a) * ry)
            tip = root + QPointF(math.cos(a) * rx * 0.45, -math.sin(a) * ry * 0.4 - ry * 0.08)
            lash = QPainterPath(root)
            lash.quadTo(root + QPointF(math.cos(a) * rx * 0.3, -math.sin(a) * ry * 0.05), tip)
            q.drawPath(lash)


def ink_line(q: QPainter, points: list[tuple[float, float]], width: float, color: str = LINE) -> None:
    q.strokePath(spline(points, closed=False), QPen(col(color), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))


def ink_stroke(q: QPainter, points: list[tuple[float, float]], start: float, end: float, color: str = LINE) -> None:
    """A brush stroke through points, start wide at the first and end at the last."""
    q.fillPath(taper(points, start, end, 20), QColor(color))


def mouth(q: QPainter, path: QPainterPath, line: float, *, tongue: QPointF | None = None, tongue_r: tuple[float, float] = (0.0, 0.0), teeth: Callable[[QPainter], None] | None = None) -> None:
    """An open mouth: dark inside, a tongue at tongue, teeth drawn by teeth, its outline in ink."""
    q.fillPath(path, QColor("#5e1520"))
    q.save()
    q.setClipPath(path)
    if tongue is not None:
        q.setPen(Qt.NoPen)
        q.setBrush(QColor("#f0727f"))
        q.drawEllipse(tongue, *tongue_r)
    if teeth is not None:
        teeth(q)
    q.restore()
    q.strokePath(path, QPen(col(LINE), line, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))


# The lambs.


# How each lamb differs: face and its shadow, irises, horns, how plump.
LAMBS = {
    "xi": {"face": SKIN, "face_shade": SKIN_SHADE, "iris": "#5b351f", "horn": HORN, "wide": 1.0},
    "mei": {"face": "#f6d8bd", "face_shade": "#dcab8b", "iris": "#b0479a", "horn": "#7a4a2c", "wide": 1.0},
    "lan": {"face": "#f7e2c2", "face_shade": "#dcb895", "iris": "#4a3020", "horn": "#7a4a2c", "wide": 1.12},
    "fei": {"face": TAN, "face_shade": "#9a6438", "iris": "#3a2416", "horn": "#5a361e", "wide": 1.04},
}


def lamb(who: str, s: float, scale: float, pose: str = "stand") -> tuple[QImage, QRectF]:
    """One of the lambs, s tall standing on (0, 0) and facing us: who is "xi" (喜羊羊), "mei" (美羊羊),
    "lan" (懒羊羊) or "fei" (沸羊羊); pose "stand", "hop" (arms flung up, legs tucked) or "cheer" (both
    arms up, eyes shut in a grin)."""
    look = LAMBS[who]
    wide = look["wide"]
    box = QRectF(-0.5 * s * wide, -1.08 * s, s * wide, 1.12 * s)
    art = Toon(box, scale, s, seed={"xi": 11, "mei": 23, "lan": 37, "fei": 41}[who])
    rnd = random.Random(art.seed)
    face, face_shade = look["face"], look["face_shade"]
    # The head's middle, and how big it is.
    hy = -0.66 if who == "lan" else -0.68
    head_r = 0.25 * wide

    def at(x: float, y: float) -> tuple[float, float]:
        return x * s, y * s

    # Legs, and shoes or hooves.
    tuck = pose == "hop"
    for side in (-1, 1):
        if tuck:
            leg = [at(side * 0.065, -0.2), at(side * 0.11, -0.13), at(side * 0.1, -0.075)]
        else:
            leg = [at(side * 0.065 * wide, -0.2), at(side * 0.072 * wide, -0.06)]
        art.part(limb(leg, 0.072 * s), face, face_shade, soft=1.5)
        foot_x, foot_y = leg[-1][0] / s + side * 0.012, leg[-1][1] / s + 0.02
        if who == "xi":
            shoe = spline(scaled([(-0.06, 0.0), (-0.05, -0.04), (0.0, -0.05), (0.05, -0.035), (0.068, 0.0), (0.0, 0.016)], s, foot_x, foot_y, side))
            art.part(shoe, SHOE, soft=1.5, gloss=0.35)
            sole = spline(scaled([(-0.064, 0.0), (0.0, 0.004), (0.07, -0.002), (0.066, 0.016), (0.0, 0.024), (-0.06, 0.014)], s, foot_x, foot_y, side))
            art.part(sole, "#ffffff", "#c7cce0", soft=0.8, cast=0.3)
            toe = ellipse((foot_x + side * 0.042) * s, (foot_y - 0.012) * s, 0.022 * s, 0.017 * s)
            art.part(toe, "#ffffff", "#c7cce0", soft=0.8, cast=0.2, line=0.7)
        else:
            hoof = spline(scaled([(-0.045, 0.0), (-0.04, -0.035), (0.0, -0.045), (0.04, -0.035), (0.048, 0.0), (0.0, 0.012)], s, foot_x, foot_y, side))
            art.part(hoof, HOOF, soft=1.4, gloss=0.4)
    # The body: a small heap of wool, and 懒羊羊's yellow bib or the others' plain wool.
    body_y, body_rx, body_ry = (-0.3, 0.15, 0.11) if who == "lan" else (-0.3, 0.12 * wide, 0.09)
    art.wool(puff_ring(0, body_y * s, body_rx * s, body_ry * s, 11, 0.062 * s, rnd), curl=0.4)
    # Arms: from the shoulder, through the elbow, to the hoof.
    arms = {
        "stand": ([(-0.12, -0.37), (-0.2, -0.31), (-0.215, -0.24)], [(0.12, -0.38), (0.21, -0.44), (0.235, -0.53)]),
        "hop": ([(-0.12, -0.38), (-0.21, -0.45), (-0.26, -0.53)], [(0.12, -0.38), (0.21, -0.45), (0.26, -0.53)]),
        "cheer": ([(-0.12, -0.39), (-0.2, -0.5), (-0.21, -0.6)], [(0.12, -0.39), (0.2, -0.5), (0.21, -0.6)]),
    }[pose]
    if who == "mei" and pose == "stand":
        arms = ([(-0.11, -0.38), (-0.17, -0.31), (-0.1, -0.27)], [(0.11, -0.38), (0.17, -0.31), (0.1, -0.27)])
    if who == "lan" and pose == "stand":
        arms = ([(-0.14, -0.37), (-0.2, -0.3), (-0.13, -0.24)], [(0.14, -0.37), (0.2, -0.3), (0.13, -0.24)])
    if who == "fei" and pose == "stand":
        arms = ([(-0.13, -0.38), (-0.25, -0.4), (-0.25, -0.52)], [(0.13, -0.38), (0.25, -0.4), (0.25, -0.52)])
    thick = 0.085 if who == "fei" else 0.062
    for points in arms:
        art.part(limb(scaled(points, s), thick * s), face, face_shade, soft=1.4)
        if who == "fei":
            # His muscles: a round bulge at the upper arm.
            (sx_, sy_), (ex, ey), _hand = points
            art.part(ellipse((sx_ + ex) / 2 * s, ((sy_ + ey) / 2 - 0.012) * s, 0.055 * s, 0.045 * s), face, face_shade, soft=2.2, rest=0.4, line=0.8)
        hx, hy_ = points[-1]
        hoof = ellipse(hx * s, hy_ * s, 0.04 * s, 0.035 * s)
        art.part(hoof, HOOF, soft=1.4, gloss=0.4)
    # Round the neck: 喜羊羊's blue ribbon (its bell hangs from it last), 美羊羊's pink scarf, 懒羊羊's bib.
    neck = -0.445 if who != "lan" else -0.44
    if who == "xi":
        art.part(taper([at(-0.12, neck - 0.012), at(0.0, neck + 0.022), at(0.12, neck - 0.012)], 0.034 * s, 0.034 * s), RIBBON, soft=1.0, gloss=0.3)
    elif who == "mei":
        art.part(taper([at(-0.14, neck - 0.02), at(0.0, neck + 0.028), at(0.14, neck - 0.02)], 0.06 * s, 0.06 * s), PINK, soft=1.6)
        tail = spline(scaled([(0.06, neck + 0.01), (0.12, neck + 0.03), (0.13, neck + 0.12), (0.09, neck + 0.13), (0.07, neck + 0.05)], s))
        art.part(tail, PINK, soft=1.4)
        art.outline(spline(scaled([(0.085, neck + 0.04), (0.105, neck + 0.11)], s), closed=False), 0.6)
    elif who == "lan":
        bib = spline(scaled([(-0.14, neck - 0.01), (-0.12, neck + 0.07), (0.0, neck + 0.14), (0.12, neck + 0.07), (0.14, neck - 0.01), (0.0, neck + 0.025)], s))
        art.part(bib, BIB, soft=1.6, swell=0.6)
    # Ears, out from under the wool at the sides.
    ear_y = hy + 0.035
    for side in (-1, 1):
        ear = ellipse(side * (head_r + 0.06) * s, ear_y * s, 0.08 * s, 0.038 * s, side * 18)
        art.part(ear, face, face_shade, soft=1.4)
        inner = ellipse(side * (head_r + 0.075) * s, (ear_y + 0.004) * s, 0.05 * s, 0.018 * s, side * 18)
        art.part(inner, look["face_shade"], soft=0.8, rest=0.9, line=0, cast=0.2)
    # Horns, their roots under the wool: small and curving back, bigger and curled on 沸羊羊.
    for side in (-1, 1):
        if who == "fei":
            points = [(0.1, hy - 0.2), (0.2, hy - 0.29), (0.31, hy - 0.26), (0.33, hy - 0.17), (0.27, hy - 0.13)]
            art.part(taper(scaled(points, s, flip=side), 0.07 * s, 0.025 * s), look["horn"], soft=1.4, gloss=0.25, grain=0.06)
        else:
            points = [(0.1, hy - 0.2), (0.16, hy - 0.29), (0.24, hy - 0.305), (0.275, hy - 0.265)]
            art.part(taper(scaled(points, s, flip=side), 0.052 * s, 0.018 * s), look["horn"], soft=1.2, gloss=0.25, grain=0.06)
        if who == "mei":
            # A pink bow on each horn.
            bx, by = side * 0.2 * s, (hy - 0.29) * s
            for wing in (-1, 1):
                loop = spline([(bx, by), (bx + wing * 0.035 * s, by - 0.035 * s), (bx + wing * 0.06 * s, by - 0.01 * s), (bx + wing * 0.05 * s, by + 0.03 * s), (bx + wing * 0.02 * s, by + 0.012 * s)])
                art.part(loop, PINK, soft=1.2)
            art.part(ellipse(bx, by, 0.018 * s, 0.016 * s), "#e2588f", soft=0.8)
    # The wool hood round the face, and 懒羊羊's swirl piled on top.
    hood = puff_ring(0, hy * s, head_r * s, 0.215 * s, 15, 0.072 * s, rnd)
    if who == "mei":
        # Her wool falls a little lower at the sides, like hair.
        hood += [(side * 0.24 * s, (hy + 0.13) * s, 0.06 * s) for side in (-1, 1)]
    art.wool(hood, curl=0.4)
    if who == "lan":
        swirl = [(0.0, hy - 0.24, 0.16), (-0.01, hy - 0.33, 0.12), (0.01, hy - 0.41, 0.085), (0.0, hy - 0.47, 0.05)]
        for x, y, r in swirl:
            tier = [(x * s + dx * r * s, y * s + 0.08 * r * s * math.sin(dx * 3), 0.42 * r * s) for dx in (-0.85, -0.45, 0.0, 0.45, 0.85)]
            art.wool(tier, flat=0.9, curl=0.3)
        art.part(taper(scaled([(0.0, hy - 0.5), (0.03, hy - 0.535), (0.06, hy - 0.52)], s), 0.03 * s, 0.006 * s), WOOL, WOOL_SHADE, soft=0.8)
    # The face, framed by the hood: wide across the eyes, a slightly long rounded muzzle below.
    f = 1.0 if who != "lan" else 1.08
    outline = [
        (-0.17, -0.12), (-0.085, -0.155), (0.0, -0.16), (0.085, -0.155), (0.17, -0.12),
        (0.215, -0.04), (0.212, 0.05), (0.17, 0.14), (0.09, 0.19), (0.0, 0.205),
        (-0.09, 0.19), (-0.17, 0.14), (-0.212, 0.05), (-0.215, -0.04),
    ]  # fmt: skip
    face_path = spline([(x * f * wide * s, (hy + y) * s) for x, y in outline])
    art.part(face_path, face, face_shade, soft=3.2, swell=0.7, rest=0.3)
    # The muzzle catches a little more light.
    art.blush(ellipse(0, (hy + 0.12) * s, 0.12 * s, 0.07 * s), "#fbe6d2" if who != "fei" else "#d9a171", 2.5, 0.45)
    if who in ("mei", "xi", "lan"):
        cheeks = QPainterPath()
        for side in (-1, 1):
            cheeks.addEllipse(QPointF(side * 0.135 * s, (hy + 0.085) * s), 0.042 * s, 0.025 * s)
        art.blush(cheeks, "#f59a9a", 1.6, 0.6 if who == "mei" else 0.3)
    # 喜羊羊's tuft of wool curling down over his forehead; a smaller fringe on the others.
    if who == "xi":
        tuft = [(-0.06, hy - 0.2, 0.07), (0.0, hy - 0.17, 0.07), (0.05, hy - 0.15, 0.05), (0.03, hy - 0.115, 0.038), (-0.005, hy - 0.11, 0.028)]
    elif who == "lan":
        tuft = [(-0.07, hy - 0.17, 0.055), (0.0, hy - 0.165, 0.06), (0.07, hy - 0.17, 0.055)]
    else:
        tuft = [(-0.06, hy - 0.175, 0.055), (0.0, hy - 0.16, 0.055), (0.06, hy - 0.175, 0.055)]
    art.wool([(x * s, y * s, r * s) for x, y, r in tuft], flat=0.9, curl=0.3)
    if who == "xi":
        # The ribbon's bell, in front of everything.
        bell_r = 0.05 * s
        art.part(ellipse(0, (neck + 0.03) * s, 0.016 * s, 0.016 * s), "#d79a1c", soft=0.6, gloss=0.6, cast=0.3)
        bell = spline(scaled([(-0.05, 0.11), (-0.045, 0.05), (-0.025, 0.012), (0.0, 0.004), (0.025, 0.012), (0.045, 0.05), (0.05, 0.11), (0.0, 0.122)], s, 0, neck + 0.03))
        art.part(bell, BELL, "#c98c16", soft=2.2, gloss=0.9, grain=0.02)
        art.part(ellipse(0, (neck + 0.142) * s, 0.054 * s, 0.013 * s), "#e7ae25", "#b67812", soft=0.6, gloss=0.8, rest=0.6, cast=0.2)
        del bell_r

    def features(q: QPainter) -> None:
        thin = LINE_W * s
        ey = (hy + 0.0) * s
        happy = pose == "cheer"
        sleepy = who == "lan"
        rx, ry = 0.068 * s, 0.085 * s
        if who == "fei":
            rx, ry = 0.062 * s, 0.075 * s
        for side in (-1, 1):
            middle = QPointF(side * 0.074 * s * (f if who == "lan" else 1), ey)
            if happy:
                ink_stroke(q, [(middle.x() - rx * 0.85, middle.y() + ry * 0.15), (middle.x(), middle.y() - ry * 0.55), (middle.x() + rx * 0.85, middle.y() + ry * 0.15)], 0.6 * thin, 0.6 * thin)
                ink_line(q, [(middle.x() - rx * 0.85, middle.y() + ry * 0.15), (middle.x(), middle.y() - ry * 0.55), (middle.x() + rx * 0.85, middle.y() + ry * 0.15)], 1.6 * thin)
                continue
            eye(
                q,
                middle,
                rx,
                ry,
                look["iris"],
                look=QPointF(-side * 0.06, 0.08 if sleepy else 0.04),
                lid=0.5 if sleepy else 0.0,
                lid_color=face,
                lashes=side if who == "mei" else 0,
                line=thin,
            )
        # Brows: short; thick and set low on 沸羊羊; lifted on 美羊羊.
        for side in (-1, 1):
            x0, x1 = side * 0.035 * s, side * 0.115 * s
            if who == "fei":
                ink_stroke(q, [(x0, ey - ry - 0.012 * s), (side * 0.08 * s, ey - ry - 0.03 * s), (x1, ey - ry - 0.035 * s)], 0.032 * s, 0.018 * s)
            elif who == "lan":
                ink_stroke(q, [(x0, ey - ry - 0.03 * s), (x1, ey - ry - 0.02 * s)], 0.014 * s, 0.01 * s)
            else:
                ink_stroke(q, [(x0, ey - ry - 0.02 * s), (side * 0.075 * s, ey - ry - 0.034 * s), (x1, ey - ry - 0.026 * s)], 0.018 * s, 0.012 * s)
        # The nose: small and brown, a shine on it.
        ny = (hy + 0.095) * s
        q.setPen(QPen(col(LINE), 0.8 * thin))
        q.setBrush(QColor("#7a3f24"))
        q.drawEllipse(QPointF(0, ny), 0.024 * s, 0.015 * s)
        q.setPen(Qt.NoPen)
        q.setBrush(col("#ffffff", 0.8))
        q.drawEllipse(QPointF(-0.008 * s, ny - 0.005 * s), 0.007 * s, 0.004 * s)
        my = (hy + 0.14) * s
        if sleepy:
            # 懒羊羊: a small sleepy smile, a bubble at his nose.
            ink_line(q, [(-0.04 * s, my), (0, my + 0.015 * s), (0.04 * s, my)], 1.2 * thin)
            bubble = QRadialGradient(QPointF(0.045 * s, ny + 0.012 * s), 0.04 * s)
            bubble.setColorAt(0, col("#e8f6ff", 0.25))
            bubble.setColorAt(0.85, col("#bfe6ff", 0.45))
            bubble.setColorAt(1, col("#8cc8f0", 0.8))
            q.setBrush(bubble)
            q.setPen(QPen(col("#6aa8d8", 0.9), 0.5 * thin))
            q.drawEllipse(QPointF(0.055 * s, ny + 0.02 * s), 0.035 * s, 0.035 * s)
            q.setPen(Qt.NoPen)
            q.setBrush(col("#ffffff", 0.9))
            q.drawEllipse(QPointF(0.045 * s, ny + 0.008 * s), 0.008 * s, 0.006 * s)
            return
        if who == "mei" and not happy:
            smile = QPainterPath(QPointF(-0.045 * s, my))
            smile.quadTo(QPointF(0, my + 0.012 * s), QPointF(0.045 * s, my))
            smile.quadTo(QPointF(0, my + 0.05 * s), QPointF(-0.045 * s, my))
            mouth(q, smile, 1.1 * thin, tongue=QPointF(0, my + 0.04 * s), tongue_r=(0.025 * s, 0.015 * s))
            return
        if who == "fei" and not happy:
            grin = QPainterPath(QPointF(-0.075 * s, my - 0.008 * s))
            grin.quadTo(QPointF(0, my + 0.008 * s), QPointF(0.075 * s, my - 0.008 * s))
            grin.quadTo(QPointF(0, my + 0.05 * s), QPointF(-0.075 * s, my - 0.008 * s))

            def teeth(q: QPainter) -> None:
                q.fillRect(QRectF(-0.08 * s, my - 0.02 * s, 0.16 * s, 0.025 * s), QColor("#ffffff"))
                q.setPen(QPen(col(LINE, 0.6), 0.5 * thin))
                q.drawLine(QPointF(-0.08 * s, my + 0.005 * s), QPointF(0.08 * s, my + 0.005 * s))

            mouth(q, grin, 1.1 * thin, teeth=teeth)
            return
        # 喜羊羊's confident open grin, a little to one side; wide open when he cheers.
        deep = 0.07 if happy else 0.055
        grin = QPainterPath(QPointF(-0.07 * s, my - 0.012 * s))
        grin.quadTo(QPointF(0, my + 0.004 * s), QPointF(0.075 * s, my - 0.018 * s))
        grin.quadTo(QPointF(0.01 * s, my + deep * s), QPointF(-0.07 * s, my - 0.012 * s))
        mouth(q, grin, 1.1 * thin, tongue=QPointF(0.005 * s, my + (deep - 0.012) * s), tongue_r=(0.035 * s, 0.022 * s))
        q.setPen(QPen(col(LINE), 0.8 * thin, Qt.SolidLine, Qt.RoundCap))
        q.drawLine(QPointF(0, ny + 0.015 * s), QPointF(0, my - 0.003 * s))

    return art.render(features), box
