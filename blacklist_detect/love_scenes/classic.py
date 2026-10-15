"""经典: a guest's welcome, simple and in gold, as an invitation card has it.

The screen's edges dim a little, as a hall's lights do before a guest comes in, and a warm light falls
from the top. A fine champagne-gold double frame draws itself round the screen from the top middle,
a spark at its head, a bracket and a diamond in each corner, and parts round the button. In its top
line, where it parts, 心动嘉宾 in gold, a sheen passing over it once it is in. Gold motes drift up
through the light; then it all fades. The default 嘉宾特效; the rose border it replaced is 玫瑰花边 (lace).

The 嘉宾 marks wear it: a navy card edged in a gold hairline with a gold diamond before each name, a
fine gold double line round the button with a glint running round it, and for the badge a gold
medallion with a star.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QFontDatabase, QFontMetricsF, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

from blacklist_detect.love_scenes.draw import (
    clamp,
    col,
    ease_in,
    ease_in_out,
    ease_out,
    gold_pen,
    lengths,
    partial,
    polyline,
    soft_dot,
    star,
    win,
)
from blacklist_detect.love_scenes.light import blur, mask, picture, rgb, smooth

if TYPE_CHECKING:
    from blacklist_detect.love_scenes import Stage

DURATION = 4.4
CHAMPAGNE = "#e9c987"
LIGHT = "#fff1cf"
DEEP = "#a9823d"
NAVY = "#141a2a"
TITLE = "心动嘉宾"
LOOK = {
    "glow": (233, 201, 135),
    "rim": "#f3dca6",
    "band": (CHAMPAGNE, LIGHT),
    "card": ("#222a3e", NAVY),
    "edge": "#c9a45c",
    "ink": "#fbefd2",
    "flowers": ((LIGHT, CHAMPAGNE, DEEP), (LIGHT, CHAMPAGNE, DEEP)),
    "disc": ("#262e44", NAVY),
    "heart": (LIGHT, DEEP),
    "deep": "#b8913f",
    "deep_glow": (233, 190, 110),
}
MARKS_ANIMATED = True
CARD_TOP = 8
CARD_PAD = (14, 8, 14, 8)
# The soft layers (the dimming, the light from above, the frame's glow) are worked out at this share
# of the stage's size.
SOFT = 0.5
# The frame: in from the screen's edge, its second line inside it, a corner bracket's arms, in points.
INSET = 22.0
INNER = 6.0
BRACKET = 30.0
# When each line of the frame draws itself, from the top middle out and down.
OUTER_DRAW = (0.2, 1.35)
INNER_DRAW = (0.35, 1.5)
# The title: its size, the room either side of it in the top line, when it comes in and its sheen.
TITLE_PX = 34.0
TITLE_ROOM = 22.0
TITLE_IN = (0.55, 1.2)
SHEEN = (1.55, 2.35)
# Serif faces for the title, as a certificate would set it; SimSun is on every Chinese Windows.
TITLE_FACES = ("Noto Serif SC", "Source Han Serif SC", "SimSun")


def make(stage: Stage):  # noqa: ANN201
    width, height, gap = stage.width, stage.height, stage.gap
    u = stage.unit()
    rnd = random.Random(23)
    title, shine, title_w, title_h = _title_art(u)
    inset, inner = INSET * u, INNER * u
    top, bottom = inset, height - inset
    half = title_w / 2 + TITLE_ROOM * u
    middle = width / 2
    gap_l = max(inset + 40 * u, gap.left() - 14 * u)
    gap_r = min(width - inset - 40 * u, gap.right() + 14 * u)
    # Each half of each line, from the title out and down to the gap: left, then right.
    halves = []
    for side, x_end in ((-1, gap_l), (1, gap_r)):
        for step, when, thick in ((0.0, OUTER_DRAW, 1.6), (inner, INNER_DRAW, 0.8)):
            edge = inset + step if side < 0 else width - inset - step
            points = [QPointF(middle + side * half, top + step), QPointF(edge, top + step), QPointF(edge, bottom - step), QPointF(x_end, bottom - step)]
            halves.append((points, when, thick))
    outer_l = halves[0][0]
    ends = ((QPointF(gap_l, bottom), -1), (QPointF(gap_r, bottom), 1))
    run = lengths(outer_l)
    # When the outer line reaches each corner: the top ones, then the bottom ones.
    corners_at = (run[1] / run[-1], run[2] / run[-1])
    corners = [
        (QPointF(inset, top), 1, 1, 0),
        (QPointF(width - inset, top), -1, 1, 0),
        (QPointF(inset, bottom), 1, -1, 1),
        (QPointF(width - inset, bottom), -1, -1, 1),
    ]
    keep = _away_picture(width, height, gap, u)
    hall = _hall(width, height, u, keep)
    glow = _frame_glow(width, height, u, halves, corners, keep)
    motes = _motes(width, height, gap, u, rnd)

    def paint(p: QPainter, t: float) -> None:
        life = win(t, 0.0, 0.35) * (1 - ease_in(win(t, DURATION - 0.8, DURATION)))
        if life <= 0:
            return
        p.save()
        p.setOpacity(life)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setOpacity(life * ease_out(win(t, 0.0, 0.7)))
        p.drawImage(QRectF(0, 0, width, height), hall)
        p.setOpacity(life * ease_out(win(t, 1.0, 1.9)) * (0.85 + 0.15 * math.sin(t * 2.2)))
        p.drawImage(QRectF(0, 0, width, height), glow)
        p.setOpacity(life)
        for points, when, thick in halves:
            frac = ease_in_out(win(t, *when))
            drawn = partial(points, frac)
            if len(drawn) < 2:
                continue
            p.setPen(gold_pen(thick * u, 0.95, 180 * u))
            p.setBrush(Qt.NoBrush)
            p.drawPath(polyline(drawn))
            if thick > 1 and frac < 1:
                head = drawn[-1]
                soft_dot(p, head.x(), head.y(), 18 * u, LIGHT, 0.7)
                star(p, head.x(), head.y(), 8 * u, "#ffffff", 0.95, 0.14)
        frac = ease_in_out(win(t, *OUTER_DRAW))
        for corner, sx, sy, which in corners:
            k = clamp((frac - corners_at[which]) / 0.08)
            if k > 0:
                _corner(p, corner, sx, sy, u, k)
        for end, side in ends:
            k = clamp((frac - 0.98) / 0.02)
            if k > 0:
                _diamond(p, QPointF(end.x() - side * 5 * u, end.y()), 4.5 * u, k)
        _title(p, t, title, shine, QRectF(middle - title_w / 2, top - title_h / 2, title_w, title_h), u)
        _motes_paint(p, t, motes, gap, u)
        p.restore()

    return paint


# The hall ------------------------------------------------------------------------------------


def _away_picture(width: float, height: float, gap: QRectF, u: float) -> np.ndarray:
    """At SOFT size, how much may show: none over the button and its marks, all a little way off."""
    w, h = max(1, round(width * SOFT)), max(1, round(height * SOFT))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    x, y = (xs + 0.5) / SOFT, (ys + 0.5) / SOFT
    dx = np.maximum(np.maximum(gap.left() - x, x - gap.right()), 0)
    dy = np.maximum(np.maximum(gap.top() - y, y - gap.bottom()), 0)
    return smooth(0, 90 * u, np.sqrt(dx * dx + dy * dy)) ** 0.8


def _hall(width: float, height: float, u: float, keep: np.ndarray) -> QImage:
    """The edges dimmed, as a hall's lights go down, and a warm light falling from the top middle."""
    h, w = keep.shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    nx, ny = (xs / w - 0.5) * 2, (ys / h - 0.5) * 2
    dim = smooth(0.55, 1.3, np.sqrt(nx * nx * 0.75 + ny * ny)) * 0.42
    # The light: a cone from just above the top middle, widening and fading as it falls.
    down = ys / h + 0.12
    spread = np.abs(nx) / (down * 1.1)
    light = (1 - smooth(0.25, 1.0, spread)) * (1 - smooth(0.15, 0.95, ys / h)) * 0.16
    alpha = dim + light * (1 - dim)
    color = (rgb("#0a0e18") * dim[..., None] + rgb("#ffe7b0") * (light * (1 - dim))[..., None]) / np.maximum(alpha, 1e-4)[..., None]
    return picture(color, alpha * keep)


def _frame_glow(width: float, height: float, u: float, halves: list, corners: list, keep: np.ndarray) -> QImage:
    """The frame's warm glow, worked out once for the whole of it, laid on as it finishes."""
    h, w = keep.shape

    def draw(q: QPainter) -> None:
        q.scale(SOFT, SOFT)
        for points, _when, thick in halves:
            q.setPen(QPen(Qt.white, max(1.2, thick * 2.2 * u)))
            q.drawPath(polyline(points))
        for corner, sx, sy, _which in corners:
            q.setPen(QPen(Qt.white, 1.6 * u))
            q.drawPath(_bracket(corner, sx, sy, u))

    core = mask(w, h, draw)
    halo = blur(core, 5 * u * SOFT) * 0.9 + blur(core, 14 * u * SOFT) * 0.5
    color = rgb("#ffd98f")
    return picture(np.broadcast_to(color, (h, w, 3)).copy(), np.clip(halo, 0, 1) * 0.75 * keep)


# The frame ------------------------------------------------------------------------------------


def _bracket(corner: QPointF, sx: int, sy: int, u: float) -> QPainterPath:
    """A corner's bracket inside the double line: two short arms meeting at a step."""
    at = QPointF(corner.x() + sx * 14 * u, corner.y() + sy * 14 * u)
    arm = BRACKET * u
    path = QPainterPath(QPointF(at.x(), at.y() + sy * arm))
    path.lineTo(at)
    path.lineTo(QPointF(at.x() + sx * arm, at.y()))
    path.moveTo(QPointF(at.x() + sx * 6 * u, at.y() + sy * arm * 0.6))
    path.lineTo(QPointF(at.x() + sx * 6 * u, at.y() + sy * 6 * u))
    path.lineTo(QPointF(at.x() + sx * arm * 0.6, at.y() + sy * 6 * u))
    return path


def _corner(p: QPainter, corner: QPointF, sx: int, sy: int, u: float, k: float) -> None:
    p.save()
    p.setOpacity(p.opacity() * k)
    p.setPen(gold_pen(1.1 * u, 0.9, 60 * u))
    p.setBrush(Qt.NoBrush)
    p.drawPath(_bracket(corner, sx, sy, u))
    _diamond(p, corner, 5.5 * u * (0.6 + 0.4 * ease_out(k)), 1.0)
    p.restore()


def _diamond(p: QPainter, at: QPointF, r: float, alpha: float) -> None:
    """A small gold diamond, lit from above, with a fine dark edge."""
    if alpha <= 0.01 or r <= 0.3:
        return
    path = QPainterPath(QPointF(at.x(), at.y() - r))
    path.lineTo(at.x() + r * 0.72, at.y())
    path.lineTo(at.x(), at.y() + r)
    path.lineTo(at.x() - r * 0.72, at.y())
    path.closeSubpath()
    fill = QLinearGradient(QPointF(at.x(), at.y() - r), QPointF(at.x(), at.y() + r))
    fill.setColorAt(0, col(LIGHT, alpha))
    fill.setColorAt(0.5, col(CHAMPAGNE, alpha))
    fill.setColorAt(1, col(DEEP, alpha))
    p.save()
    p.setPen(QPen(col("#3a2a10", 0.55 * alpha), max(0.6, r * 0.12)))
    p.setBrush(fill)
    p.drawPath(path)
    p.restore()


# The title ------------------------------------------------------------------------------------


def _title_face() -> str:
    families = set(QFontDatabase.families())
    return next((face for face in TITLE_FACES if face in families), "SimSun")


def _title_art(u: float) -> tuple[QImage, QImage, float, float]:
    """心动嘉宾 in gold, per pixel: light at the top of each stroke, deep at its foot, a bevel along its
    edges, a fine dark edge and a soft glow; and the same words in near white, for the sheen. Made at
    twice their size in points; with their width and height in points."""
    ratio = 2.0
    font = QFont(_title_face())
    font.setPixelSize(max(8, round(TITLE_PX * u * ratio)))
    font.setWeight(QFont.Bold)
    font.setLetterSpacing(QFont.AbsoluteSpacing, 7 * u * ratio)
    metrics = QFontMetricsF(font)
    pad = 16 * u * ratio
    w = round(metrics.horizontalAdvance(TITLE) + pad * 2)
    h = round(metrics.height() + pad * 2)

    def draw(q: QPainter) -> None:
        q.setFont(font)
        q.setPen(Qt.white)
        q.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, TITLE)

    words = mask(w, h, draw)
    rows = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    top_y = (h - metrics.height()) / 2 / h
    span = metrics.height() / h
    down = np.clip((rows - top_y) / max(span, 1e-3), 0, 1)
    # Light falls from above: bright at each stroke's top, deep at its foot, a bevel off its edges.
    bevel = blur(words, max(0.8, 1.2 * u * ratio))
    gy, gx = np.gradient(bevel)
    lit = np.clip(0.5 - (gy * 0.8 + gx * 0.4) * 6, 0, 1)
    tone = np.clip(0.75 - down * 0.65 + (lit - 0.5) * 0.9, 0, 1)[..., None]
    gold = np.where(tone > 0.5, rgb(CHAMPAGNE) * (1 - (tone - 0.5) * 2) + rgb(LIGHT) * ((tone - 0.5) * 2), rgb(DEEP) * (1 - tone * 2) + rgb(CHAMPAGNE) * (tone * 2))
    edge = np.clip(blur(words, max(0.8, 1.4 * u * ratio)) * 1.8, 0, 1) * (1 - words)
    halo = blur(words, 9 * u * ratio) * 0.55
    alpha = np.clip(words + edge * 0.75 + halo * 0.6, 0, 1)
    color = (gold * words[..., None] + rgb("#2a1d08") * (edge * 0.75)[..., None] + rgb("#ffd98f") * (halo * 0.6)[..., None])
    color = color / np.maximum(words + edge * 0.75 + halo * 0.6, 1e-4)[..., None]
    shine = picture(np.broadcast_to(rgb("#fffaf0"), (h, w, 3)).copy(), words)
    return picture(color, alpha), shine, w / ratio, h / ratio


def _title(p: QPainter, t: float, title: QImage, shine: QImage, box: QRectF, u: float) -> None:
    """The title coming in, rising a little into place, two diamonds either side; then a sheen across."""
    k = ease_out(win(t, *TITLE_IN))
    if k <= 0:
        return
    p.save()
    p.setOpacity(p.opacity() * k)
    place = box.translated(0, 6 * u * (1 - k))
    p.drawImage(place, title)
    for side in (-1, 1):
        x = place.center().x() + side * (place.width() / 2 - 4 * u)
        _diamond(p, QPointF(x, place.center().y()), 4 * u, 1.0)
    sweep = win(t, *SHEEN)
    if 0 < sweep < 1:
        middle = place.left() + place.width() * (-0.15 + 1.3 * ease_in_out(sweep))
        base = p.opacity()
        for half_width, strength in ((22 * u, 0.35), (12 * u, 0.45), (5 * u, 0.6)):
            p.save()
            p.setClipRect(QRectF(middle - half_width, place.top(), half_width * 2, place.height()))
            p.setOpacity(base * strength * math.sin(math.pi * sweep))
            p.drawImage(place, shine)
            p.restore()
    p.restore()


# The motes ------------------------------------------------------------------------------------


def _motes(width: float, height: float, gap: QRectF, u: float, rnd: random.Random) -> list[tuple]:
    """Gold motes in the light: where each starts, how fast it rises and sways, how big, when."""
    out = []
    clear = gap.adjusted(-60 * u, -60 * u, 60 * u, 0)
    while len(out) < 22:
        x = rnd.uniform(width * 0.08, width * 0.92)
        y = rnd.uniform(height * 0.22, height * 0.92)
        if clear.contains(QPointF(x, y)):
            continue
        out.append((x, y, rnd.uniform(10, 24) * u, rnd.uniform(5, 14) * u, rnd.uniform(0, math.tau), rnd.uniform(1.8, 4.2) * u, rnd.uniform(0.7, 1.7)))
    return out


def _motes_paint(p: QPainter, t: float, motes: list[tuple], gap: QRectF, u: float) -> None:
    clear = gap.adjusted(-40 * u, -40 * u, 40 * u, 0)
    for x0, y0, rise, sway, phase, size, start in motes:
        a = ease_out(win(t, start, start + 0.7))
        if a <= 0:
            continue
        age = t - start
        x = x0 + math.sin(age * 1.3 + phase) * sway
        y = y0 - rise * age
        if clear.contains(QPointF(x, y)):
            continue
        twinkle = 0.55 + 0.45 * math.sin(age * 3.1 + phase * 2)
        soft_dot(p, x, y, size * 3.2, CHAMPAGNE, 0.28 * a * twinkle)
        soft_dot(p, x, y, size, "#fffaf0", 0.85 * a * twinkle)


# The 嘉宾 marks --------------------------------------------------------------------------------

_MADE: dict[tuple, object] = {}


def _made(key: tuple, build):  # noqa: ANN001, ANN202
    """A mark's pictures, made once for its size and sharpness."""
    if key not in _MADE:
        if len(_MADE) > 24:
            _MADE.clear()
        _MADE[key] = build()
    return _MADE[key]


def _sharpness(p: QPainter) -> float:
    """Pixels per point where p draws: its screen's and its own scaling."""
    device = p.device()
    ratio = device.devicePixelRatioF() if device is not None else 1.0
    return round(ratio * math.hypot(p.transform().m11(), p.transform().m12()), 2)


def ring(p: QPainter, cover: QRectF, t: float) -> None:
    """A fine gold double line on the button, a diamond at each side, a glint running round it."""
    radius = cover.height() * 0.16
    outer = cover.adjusted(-1.5, -1.5, 1.5, 1.5)
    inner = cover.adjusted(3.5, 3.5, -3.5, -3.5)
    p.setBrush(Qt.NoBrush)
    for width, alpha in ((9, 0.08), (5.5, 0.14), (3, 0.24)):
        p.setPen(QPen(col(CHAMPAGNE, alpha), width))
        p.drawRoundedRect(outer, radius, radius)
    p.setPen(gold_pen(1.9, 1.0, cover.width() * 0.35))
    p.drawRoundedRect(outer, radius, radius)
    p.setPen(gold_pen(0.9, 0.8, cover.width() * 0.35))
    p.drawRoundedRect(inner, radius * 0.75, radius * 0.75)
    for x in (outer.left(), outer.right()):
        _diamond(p, QPointF(x, outer.center().y()), cover.height() * 0.085, 1.0)
    path = QPainterPath()
    path.addRoundedRect(outer, radius, radius)
    for offset in (0.0, 0.5):
        at = path.pointAtPercent((t * 0.14 + offset) % 1.0)
        shine = 0.6 + 0.4 * math.sin(t * 2.6 + offset * 7)
        soft_dot(p, at.x(), at.y(), cover.height() * 0.18, LIGHT, 0.5 * shine)
        star(p, at.x(), at.y(), cover.height() * (0.05 + 0.03 * shine), "#ffffff", 0.9 * shine, 0.12)


def badge(p: QPainter, box: QRectF, t: float) -> None:
    """A gold medallion: a navy enamel field in a raised gold rim, a gold star on it; it catches the
    light now and then."""
    scale = _sharpness(p)
    side = max(16, round(box.width() * scale))
    art = _made(("badge", side), lambda: _medallion(side))
    soft_dot(p, box.center().x(), box.center().y(), box.width() * 0.62, CHAMPAGNE, 0.22)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(box, art)
    glint = win(t % 3.2, 0.0, 0.7)
    if 0 < glint < 1:
        k = math.sin(math.pi * glint)
        at = QPointF(box.center().x() + box.width() * 0.16, box.center().y() - box.height() * 0.2)
        star(p, at.x(), at.y(), box.width() * 0.16 * k, "#ffffff", 0.95 * k, 0.1)


def _medallion(n: int) -> QImage:
    """The medallion n pixels across, lit per pixel from the top left."""
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32) + 0.5
    x, y = xs / n * 2 - 1, ys / n * 2 - 1
    rho = np.hypot(x, y)
    theta = np.arctan2(y, x)
    px = 2.0 / n
    cover = 1 - smooth(0.96 - px, 0.96, rho)
    rim = smooth(0.79 - px, 0.79 + px, rho) * cover
    # An eight-point star: four long points and four short between them.
    reach = np.maximum(0.17 + 0.43 * np.abs(np.cos(2 * theta)) ** 7, 0.17 + 0.2 * np.abs(np.sin(2 * theta)) ** 7)
    star_in = 1 - smooth(reach - px, reach + px, rho)
    metal = np.clip(rim + star_in, 0, 1)
    height = blur(rim, max(1.0, n * 0.02)) * 0.6 + blur(star_in, max(1.0, n * 0.03)) * 0.9
    gy, gx = np.gradient(height)
    normal = np.dstack([-gx * n * 0.12, -gy * n * 0.12, np.ones_like(gx)])
    normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
    light = np.array([-0.45, -0.6, 0.66], dtype=np.float32)
    light /= np.linalg.norm(light)
    lambert = np.clip(normal @ light, 0, 1)
    halfway = light + np.array([0, 0, 1], dtype=np.float32)
    halfway /= np.linalg.norm(halfway)
    spec = np.clip(normal @ halfway, 0, 1) ** 36
    tone = np.clip(lambert * 1.1 - 0.15, 0, 1)[..., None]
    gold = rgb(DEEP) * (1 - tone) + rgb(LIGHT) * tone + spec[..., None] * 0.7
    # The enamel: navy, lighter toward the top left, a faint gloss.
    sheen = np.clip(0.55 - (x + y) * 0.35, 0, 1)[..., None]
    enamel = rgb(NAVY) * (1 - sheen * 0.5) + rgb("#3a4a72") * (sheen * 0.5) + spec[..., None] * 0.25
    color = enamel * (1 - metal[..., None]) + gold * metal[..., None]
    return picture(color, cover)


def card(p: QPainter, rect: QRectF, t: float) -> None:
    """Navy glass edged in a gold hairline, a finer line inside it, a gold clasp on its top edge; now
    and then a glint runs along the top."""
    body = QRectF(rect.left() + 1, rect.top() + CARD_TOP, rect.width() - 2, rect.height() - CARD_TOP - 1)
    radius = 9.0
    fill = QLinearGradient(body.topLeft(), body.bottomLeft())
    fill.setColorAt(0, col("#262f46", 0.96))
    fill.setColorAt(1, col(NAVY, 0.96))
    p.setPen(Qt.NoPen)
    p.setBrush(fill)
    p.drawRoundedRect(body, radius, radius)
    gloss = QLinearGradient(body.topLeft(), QPointF(body.left(), body.top() + body.height() * 0.5))
    gloss.setColorAt(0, col("#ffffff", 0.07))
    gloss.setColorAt(1, col("#ffffff", 0))
    p.setBrush(gloss)
    p.drawRoundedRect(body, radius, radius)
    p.setBrush(Qt.NoBrush)
    p.setPen(gold_pen(1.3, 0.95, body.width() * 0.5))
    p.drawRoundedRect(body.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
    p.setPen(QPen(col(CHAMPAGNE, 0.35), 0.7))
    p.drawRoundedRect(body.adjusted(3.5, 3.5, -3.5, -3.5), radius - 3, radius - 3)
    # The clasp: a diamond on the top edge, a short line either side of it.
    clasp = QPointF(body.center().x(), body.top())
    p.setPen(gold_pen(1.1, 0.9, 40))
    for side in (-1, 1):
        p.drawLine(QPointF(clasp.x() + side * 7, clasp.y()), QPointF(clasp.x() + side * 18, clasp.y()))
    _diamond(p, clasp, 5.0, 1.0)
    k = (t % 4.0) / 1.1
    if k < 1:
        x = body.left() + radius + (body.width() - 2 * radius) * ease_in_out(k)
        shine = math.sin(math.pi * k)
        soft_dot(p, x, body.top(), 9, LIGHT, 0.55 * shine)
        star(p, x, body.top(), 3.5 * shine, "#ffffff", 0.9 * shine, 0.12)


def lead(size: float, index: int) -> QPixmap:
    """A small gold diamond before each name."""
    ratio = 3.0
    side = max(6, round(size * 0.62))
    image = QPixmap(round(side * ratio), round(side * ratio))
    image.fill(Qt.transparent)
    q = QPainter(image)
    q.setRenderHint(QPainter.Antialiasing)
    q.scale(ratio, ratio)
    _diamond(q, QPointF(side / 2, side / 2), side * 0.42, 1.0)
    q.end()
    image.setDevicePixelRatio(ratio)
    return image
