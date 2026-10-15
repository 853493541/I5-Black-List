"""Light worked out per pixel, for the scenes that glow: masks painted with QPainter, blurred and
tinted with numpy, and turned back into pictures drawn once and laid on every frame."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter


def rgb(color: str) -> np.ndarray:
    c = QColor(color)
    return np.array([c.redF(), c.greenF(), c.blueF()], dtype=np.float32)


def smooth(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    k = np.clip((x - e0) / (e1 - e0), 0, 1)
    return k * k * (3 - 2 * k)


def blur(a: np.ndarray, sigma: float) -> np.ndarray:
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


def mask(width: int, height: int, draw: Callable[[QPainter], None]) -> np.ndarray:
    """What draw paints in white on black, as 0..1 per pixel (height by width)."""
    image = QImage(max(1, width), max(1, height), QImage.Format_Grayscale8)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    draw(painter)
    painter.end()
    stride = image.bytesPerLine()
    rows = np.frombuffer(image.constBits(), dtype=np.uint8, count=stride * image.height())
    return rows.reshape(image.height(), stride)[:, : image.width()].astype(np.float32) / 255.0


def picture(color: np.ndarray, alpha: np.ndarray) -> QImage:
    """A picture from straight color (h, w, 3) and alpha (h, w), both 0..1."""
    alpha = np.clip(alpha, 0, 1)[..., None]
    premultiplied = np.clip(color, 0, 1) * alpha
    pixels = np.ascontiguousarray((np.dstack([premultiplied, alpha]) * 255 + 0.5).astype(np.uint8))
    height, width = pixels.shape[:2]
    return QImage(pixels.data, width, height, width * 4, QImage.Format_RGBA8888_Premultiplied).copy()


def glow(light: np.ndarray) -> QImage:
    """Light (h, w, 3, may run over 1) as a picture that adds it over what is under: as opaque as its
    brightest channel, so dim light stays see-through and a hot core goes white."""
    light = np.maximum(light, 0)
    # Over-bright light bleeds to white, as a camera sees it.
    over = np.clip(light.max(axis=-1, keepdims=True) - 1, 0, None)
    light = light + over * 0.6
    alpha = np.clip(light.max(axis=-1), 0, 1)
    color = np.clip(light, 0, 1) / np.maximum(alpha, 1e-4)[..., None]
    return picture(color, alpha)


def bloom(core: np.ndarray, tint: str, spread: tuple[tuple[float, float], ...], white: float = 1.0) -> QImage:
    """A lit tube or line: core (0..1) burns white at its middle and the tint spreads round it, one
    blur for each (sigma in pixels, strength) in spread."""
    color = rgb(tint)
    halo = np.zeros(core.shape, dtype=np.float32)
    for sigma, strength in spread:
        halo += blur(core, sigma) * strength
    light = halo[..., None] * color + (core ** 1.5)[..., None] * (color * 0.5 + white * 0.7)
    return glow(light)


def noise(width: int, height: int, scale: float, octaves: int, seed: int) -> np.ndarray:
    """Smooth value noise, 0..1, octaves of it each half the size of the last. Each grid is smoothed
    across first, once per grid row, then down: the same numbers as per pixel, several times faster."""
    rnd = np.random.default_rng(seed)
    out = np.zeros((height, width), dtype=np.float32)
    total = 0.0
    amp = 1.0
    for octave in range(octaves):
        cell = max(2.0, scale / (2 ** octave))
        gw, gh = int(width / cell) + 3, int(height / cell) + 3
        grid = rnd.random((gh, gw), dtype=np.float32)
        fx = np.arange(width, dtype=np.float32) / cell
        fy = (np.arange(height, dtype=np.float32) / cell)[:, None]
        x0, y0 = fx.astype(int), fy[:, 0].astype(int)
        sx, sy = fx - x0, fy - y0[:, None]
        sx, sy = sx * sx * (3 - 2 * sx), sy * sy * (3 - 2 * sy)
        across = grid[:, x0] * (1 - sx) + grid[:, x0 + 1] * sx
        out += (across[y0] * (1 - sy) + across[y0 + 1] * sy) * amp
        total += amp
        amp *= 0.5
    return out / total


def scaled_up(image: QImage, painter: QPainter, x: float, y: float, width: float, height: float) -> None:
    """A soft picture made small, laid on at its full size, smoothed."""
    painter.save()
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    painter.drawImage(QRectF(x, y, width, height), image)
    painter.restore()

