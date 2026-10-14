"""What the 心动 scenes draw with: easing, colors, pearls, glints, stars, hearts and paths."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient

# The pink scenes' palette: ivory, blush, rose, deep rose, champagne gold.
IVORY = "#fff7f4"
BLUSH = "#f8d7e0"
PETAL = "#f2b5c8"
ROSE = "#e58aa8"
DEEP = "#b8456f"
GOLD = "#e2c08d"
GOLD_LIGHT = "#fbecd0"
GOLD_DEEP = "#b98a55"


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def win(t: float, a: float, b: float) -> float:
    """0 before a, 1 after b, linear between."""
    return clamp((t - a) / (b - a))


def ease_out(k: float) -> float:
    k = clamp(k)
    return 1 - (1 - k) ** 3


def ease_in(k: float) -> float:
    k = clamp(k)
    return k ** 3


def ease_in_out(k: float) -> float:
    k = clamp(k)
    return 4 * k ** 3 if k < 0.5 else 1 - (-2 * k + 2) ** 3 / 2


def ease_back(k: float, s: float = 1.9) -> float:
    k = clamp(k)
    return 1 + (s + 1) * (k - 1) ** 3 + s * (k - 1) ** 2


def spring(seconds: float, freq: float = 1.6, damp: float = 3.2) -> float:
    """Swing that dies away: 1 at 0, toward 0."""
    if seconds <= 0:
        return 1.0
    return math.exp(-damp * seconds) * math.cos(2 * math.pi * freq * seconds)


def col(color: str, alpha: float = 1.0) -> QColor:
    shade = QColor(color)
    shade.setAlphaF(clamp(alpha))
    return shade


def gradient(start: QPointF, end: QPointF, stops, alpha: float = 1.0) -> QLinearGradient:  # noqa: ANN001
    g = QLinearGradient(start, end)
    for at, color, *rest in stops:
        g.setColorAt(at, col(color, (rest[0] if rest else 1.0) * alpha))
    return g


def gold_pen(width: float, alpha: float, span: float) -> QPen:
    """A champagne-gold line that catches light every so often along its length."""
    g = QLinearGradient(QPointF(0, 0), QPointF(span, span * 0.35))
    g.setSpread(QLinearGradient.ReflectSpread)
    g.setColorAt(0, col(GOLD_DEEP, alpha))
    g.setColorAt(0.45, col(GOLD, alpha))
    g.setColorAt(0.55, col(GOLD_LIGHT, alpha))
    g.setColorAt(1, col(GOLD, alpha))
    pen = QPen(g, width)
    pen.setCapStyle(Qt.RoundCap)
    return pen


def pearl(painter: QPainter, x: float, y: float, r: float, alpha: float = 1.0, shine: float = 0.0) -> None:
    """A pearl lit from the upper left: cream body, lilac shade, a blush bounce and a sharp highlight."""
    if r < 0.4 or alpha <= 0.01:
        return
    painter.setPen(Qt.NoPen)
    shadow = QRadialGradient(QPointF(x + r * 0.25, y + r * 0.45), r * 1.5)
    shadow.setColorAt(0, col("#3a1426", 0.28 * alpha))
    shadow.setColorAt(1, col("#3a1426", 0))
    painter.setBrush(shadow)
    painter.drawEllipse(QPointF(x + r * 0.25, y + r * 0.45), r * 1.5, r * 1.5)
    body = QRadialGradient(QPointF(x - r * 0.35, y - r * 0.4), r * 1.35)
    body.setColorAt(0, col("#ffffff", alpha))
    body.setColorAt(0.28, col("#fff6f2", alpha))
    body.setColorAt(0.62, col("#f2e4ea", alpha))
    body.setColorAt(0.88, col("#d8c5d8", alpha))
    body.setColorAt(1, col("#bba5c0", alpha))
    painter.setBrush(body)
    painter.drawEllipse(QPointF(x, y), r, r)
    bounce = QRadialGradient(QPointF(x + r * 0.5, y + r * 0.55), r * 0.75)
    bounce.setColorAt(0, col("#ffc9db", 0.55 * alpha))
    bounce.setColorAt(1, col("#ffc9db", 0))
    painter.setBrush(bounce)
    painter.drawEllipse(QPointF(x, y), r, r)
    painter.setBrush(col("#ffffff", clamp(0.9 * alpha + shine)))
    painter.drawEllipse(QPointF(x - r * 0.36, y - r * 0.38), r * 0.24, r * 0.17)
    if shine > 0.02:
        glint(painter, x - r * 0.36, y - r * 0.38, r * (1.2 + 2.4 * shine), shine * alpha)


def glint(painter: QPainter, x: float, y: float, r: float, alpha: float = 1.0) -> None:
    """A thin four-point star with a soft halo, the way light catches a stone."""
    if alpha <= 0.01 or r < 0.5:
        return
    halo = QRadialGradient(QPointF(x, y), r * 1.2)
    halo.setColorAt(0, col("#fff4f8", 0.55 * alpha))
    halo.setColorAt(1, col("#ffd6e6", 0))
    painter.setPen(Qt.NoPen)
    painter.setBrush(halo)
    painter.drawEllipse(QPointF(x, y), r * 1.2, r * 1.2)
    star = QPainterPath(QPointF(x, y - r))
    k = 0.09
    for px, py in ((r * k, -r * k), (r, 0), (r * k, r * k), (0, r), (-r * k, r * k), (-r, 0), (-r * k, -r * k)):
        star.lineTo(x + px, y + py)
    star.closeSubpath()
    painter.setBrush(col("#ffffff", alpha))
    painter.drawPath(star)


def partial(points: list[QPointF], frac: float) -> list[QPointF]:
    """The first frac of a polyline, by length."""
    frac = clamp(frac)
    if frac <= 0 or len(points) < 2:
        return []
    lengths = [math.dist((a.x(), a.y()), (b.x(), b.y())) for a, b in zip(points, points[1:], strict=False)]
    goal = sum(lengths) * frac
    out = [points[0]]
    for (a, b), seg in zip(zip(points, points[1:], strict=False), lengths, strict=True):
        if goal >= seg:
            out.append(b)
            goal -= seg
            continue
        k = goal / seg if seg else 0
        out.append(QPointF(a.x() + (b.x() - a.x()) * k, a.y() + (b.y() - a.y()) * k))
        break
    return out


def polyline(points: list[QPointF]) -> QPainterPath:
    path = QPainterPath()
    if points:
        path.moveTo(points[0])
        for point in points[1:]:
            path.lineTo(point)
    return path


def quad(a: QPointF, c: QPointF, b: QPointF, s: float) -> QPointF:
    m = 1 - s
    return QPointF(m * m * a.x() + 2 * m * s * c.x() + s * s * b.x(), m * m * a.y() + 2 * m * s * c.y() + s * s * b.y())


def spectrum(stops: list[str], k: float, alpha: float = 1.0) -> QColor:
    """A color along a looping list of colors, k in any range (it wraps)."""
    k = k % 1.0
    n = len(stops)
    at = k * n
    i = int(at) % n
    f = at - int(at)
    a, b = QColor(stops[i]), QColor(stops[(i + 1) % n])
    shade = QColor(
        round(a.red() + (b.red() - a.red()) * f),
        round(a.green() + (b.green() - a.green()) * f),
        round(a.blue() + (b.blue() - a.blue()) * f),
    )
    shade.setAlphaF(clamp(alpha))
    return shade


def mix(a: str | QColor, b: str | QColor, k: float, alpha: float = 1.0) -> QColor:
    ca, cb = QColor(a), QColor(b)
    k = clamp(k)
    shade = QColor(
        round(ca.red() + (cb.red() - ca.red()) * k),
        round(ca.green() + (cb.green() - ca.green()) * k),
        round(ca.blue() + (cb.blue() - ca.blue()) * k),
    )
    shade.setAlphaF(clamp(alpha))
    return shade


def heart_points(cx: float, cy: float, size: float, count: int, start: float = 0.0) -> list[QPointF]:
    """Points around a heart, size its width; start in turns, 0 at the top cleft, going clockwise."""
    out = []
    for i in range(count):
        a = (start + i / count) * 2 * math.pi
        x = 16 * math.sin(a) ** 3
        y = 13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)
        out.append(QPointF(cx + x * size / 34, cy - (y - 2.5) * size / 34))
    return out


def heart_path(cx: float, cy: float, size: float) -> QPainterPath:
    """The heart of heart_points as one smooth outline: the plain heart everyone knows."""
    points = heart_points(cx, cy, size, 120)
    path = QPainterPath(points[0])
    for point in points[1:]:
        path.lineTo(point)
    path.closeSubpath()
    return path


def soft_dot(painter: QPainter, x: float, y: float, r: float, color: str | QColor, alpha: float) -> None:
    """A round glow: bright core, soft edge."""
    if alpha <= 0.01 or r <= 0.2:
        return
    g = QRadialGradient(QPointF(x, y), r)
    c = QColor(color)
    c0 = QColor(c)
    c0.setAlphaF(clamp(alpha))
    c1 = QColor(c)
    c1.setAlphaF(clamp(alpha * 0.35))
    c2 = QColor(c)
    c2.setAlphaF(0)
    g.setColorAt(0, c0)
    g.setColorAt(0.35, c1)
    g.setColorAt(1, c2)
    painter.setPen(Qt.NoPen)
    painter.setBrush(g)
    painter.drawEllipse(QPointF(x, y), r, r)


def star(painter: QPainter, x: float, y: float, r: float, color: str | QColor, alpha: float, thin: float = 0.12) -> None:
    """A four-point star, its arms thin."""
    if alpha <= 0.01 or r < 0.4:
        return
    path = QPainterPath(QPointF(x, y - r))
    k = thin
    for px, py in ((r * k, -r * k), (r, 0), (r * k, r * k), (0, r), (-r * k, r * k), (-r, 0), (-r * k, -r * k)):
        path.lineTo(x + px, y + py)
    path.closeSubpath()
    c = QColor(color)
    c.setAlphaF(clamp(alpha))
    painter.setPen(Qt.NoPen)
    painter.setBrush(c)
    painter.drawPath(path)


def catmull(points: list[QPointF], per: int = 12) -> list[QPointF]:
    """A smooth curve through points."""
    if len(points) < 3:
        return list(points)
    pts = [points[0], *points, points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for s in range(per):
            t = s / per
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1.x()) + (-p0.x() + p2.x()) * t + (2 * p0.x() - 5 * p1.x() + 4 * p2.x() - p3.x()) * t2 + (-p0.x() + 3 * p1.x() - 3 * p2.x() + p3.x()) * t3)
            y = 0.5 * ((2 * p1.y()) + (-p0.y() + p2.y()) * t + (2 * p0.y() - 5 * p1.y() + 4 * p2.y() - p3.y()) * t2 + (-p0.y() + 3 * p1.y() - 3 * p2.y() + p3.y()) * t3)
            out.append(QPointF(x, y))
    out.append(points[-1])
    return out


def lengths(points: list[QPointF]) -> list[float]:
    out = [0.0]
    for a, b in zip(points, points[1:], strict=False):
        out.append(out[-1] + math.dist((a.x(), a.y()), (b.x(), b.y())))
    return out


def point_at(points: list[QPointF], cumulative: list[float], distance: float) -> tuple[QPointF, float]:
    """The point at a distance along a polyline, and the direction there in radians."""
    distance = clamp(distance, 0.0, cumulative[-1])
    lo, hi = 0, len(cumulative) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if cumulative[mid] < distance:
            lo = mid
        else:
            hi = mid
    a, b = points[lo], points[hi]
    seg = cumulative[hi] - cumulative[lo] or 1
    k = (distance - cumulative[lo]) / seg
    return QPointF(a.x() + (b.x() - a.x()) * k, a.y() + (b.y() - a.y()) * k), math.atan2(b.y() - a.y(), b.x() - a.x())



class Wash:
    """A wash of light at the screen's edges, drawn once at full strength with a soft-edged hole
    where the button and its marks are, then laid on each frame at the strength wanted.

    draw(painter, width, height) paints the wash. Soft light needs no more than one pixel per point.
    """

    FEATHER = 40.0
    STEPS = 12

    def __init__(self, draw) -> None:  # noqa: ANN001
        self._draw = draw
        self._image: QImage | None = None
        self._key: tuple = ()

    def paint(self, painter: QPainter, width: float, height: float, gap: QRectF, alpha: float) -> None:
        if alpha <= 0.005:
            return
        key = (round(width), round(height), gap.x(), gap.y(), gap.width(), gap.height())
        if self._image is None or key != self._key:
            self._image = self._make(width, height, gap)
            self._key = key
        painter.save()
        painter.setOpacity(painter.opacity() * clamp(alpha))
        painter.drawImage(QRectF(0, 0, width, height), self._image)
        painter.restore()

    def _make(self, width: float, height: float, gap: QRectF) -> QImage:
        image = QImage(max(1, round(width)), max(1, round(height)), QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        inner = QPainter(image)
        inner.setRenderHint(QPainter.Antialiasing)
        self._draw(inner, width, height)
        # Rings rubbed out one over another: nearly all of it gone over the gap, less and less out
        # to FEATHER beyond it, so the light fades into the hole instead of stopping at an edge.
        inner.setCompositionMode(QPainter.CompositionMode_DestinationOut)
        inner.setPen(Qt.NoPen)
        inner.setBrush(QColor(0, 0, 0, 62))
        for step in range(self.STEPS):
            grow = self.FEATHER * (1 - step / (self.STEPS - 1))
            inner.drawRoundedRect(gap.adjusted(-grow, -grow, grow, grow), 14 + grow, 14 + grow)
        inner.end()
        return image
