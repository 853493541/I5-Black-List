"""Re-makes the 基础模式 halves of 显示's guide pictures (assets/display-diff-1.jpg and -2.jpg) with the corner
notice the app shows today, drawn by its own _Card.

Each picture is two halves of the same lobby, 基础模式 left and 完整模式 right, 10 px apart. Only the corner cards
on the left change: the lobby under the old cards comes back from assets/sample-lobby.jpg (the halves are a crop of
it, scaled), and the new cards go in the same corner at the same scale. The 完整模式 half stays as it is.

    .venv/Scripts/python.exe build/display_diff.py

Runs in a data folder of its own and opens no window; look at both pictures at full size before committing them.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="display-diff-")

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from blacklist_detect.ui_notice import _GAP, _WIDTH, _Card, result_messages  # noqa: E402
from blacklist_detect.ui_theme import use_theme  # noqa: E402

ASSETS = ROOT / "blacklist_detect" / "assets"
# Where the 基础模式 half sits in sample-lobby.jpg: the lobby scaled by LOBBY_SCALE, then cut from LOBBY_AT.
LOBBY_SCALE = 0.216
LOBBY_AT = (247, 123)
HALF_WIDTH = 460
# The lobby under the cards that comes back, in the picture: left, top, right, bottom (exclusive).
PATCH = (300, 120, HALF_WIDTH - 1, 243)
# The cards' corner in the picture (right edge, and the bottom of the tallest stack) and their scale, a logical px
# to a picture px, as the cards were shot before.
CORNER = (452, 233)
CARD_SCALE = 0.367
# Cards are drawn this many times larger, then brought down, so their words stay sharp.
SUPERSAMPLE = 4
# Windows 11 rounds the card window by 8 px.
RADIUS = 8
SHOWN = 0.85
PICTURES = {
    "display-diff-1.jpg": ([("示例坏人", ())], ["心动小鹿", "心动星星"]),
    "display-diff-2.jpg": ([], ["心动小鹿", "心动星星"]),
}


def card_pictures(hits: list[tuple[str, tuple[str, ...]]], likes: list[str]) -> list[np.ndarray]:
    """The cards for one result, the bottom one first, as BGRA at the picture's scale with Windows 11's corners."""
    messages = result_messages(hits, likes, 0)
    cards = [_Card() for _message in messages]
    for card, message in zip(cards, messages, strict=True):
        card.set_message(message)
        card.left = SHOWN
    width = min(max(max(card.natural_width() for card in cards), _WIDTH[0]), _WIDTH[1])
    shown = []
    for card in cards:
        card.fit(width)
        size = card.size()
        image = QImage(size.width() * SUPERSAMPLE, size.height() * SUPERSAMPLE, QImage.Format_ARGB32_Premultiplied)
        image.setDevicePixelRatio(SUPERSAMPLE)
        image.fill(Qt.transparent)
        card.render(image)
        # Clip to the rounded window.
        corners = QImage(image.size(), QImage.Format_ARGB32_Premultiplied)
        corners.setDevicePixelRatio(SUPERSAMPLE)
        corners.fill(Qt.transparent)
        painter = QPainter(corners)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, size.width(), size.height()), RADIUS, RADIUS)
        painter.fillPath(path, QColor("#ffffff"))
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.drawImage(0, 0, image)
        painter.end()
        corners = corners.convertToFormat(QImage.Format_ARGB32)
        pixels = np.frombuffer(corners.constBits(), np.uint8).reshape(corners.height(), corners.width(), 4).copy()
        small = (round(size.width() * CARD_SCALE), round(size.height() * CARD_SCALE))
        shown.append(cv2.resize(pixels, small, interpolation=cv2.INTER_AREA))
        card.deleteLater()
    return shown


def put(picture: np.ndarray, card: np.ndarray, left: int, top: int) -> None:
    """Lay a BGRA card over the picture, with the soft shadow Windows gives a window."""
    height, width = card.shape[:2]
    alpha = card[:, :, 3:4].astype(np.float32) / 255
    shadow = np.zeros(picture.shape[:2], np.float32)
    shadow[top + 1 : top + 1 + height, left : left + width] = alpha[:, :, 0]
    shadow = cv2.GaussianBlur(shadow, (0, 0), 1.5)[:, :, None] * 0.45
    picture[:] = (picture.astype(np.float32) * (1 - shadow)).astype(np.uint8)
    area = picture[top : top + height, left : left + width].astype(np.float32)
    # The card's pixels are straight (not premultiplied) after convertToFormat.
    mixed = card[:, :, :3].astype(np.float32) * alpha + area * (1 - alpha)
    picture[top : top + height, left : left + width] = mixed.round().astype(np.uint8)


def main() -> None:
    QApplication.instance() or QApplication([])
    use_theme("蓝色", "light")
    lobby = cv2.imread(str(ASSETS / "sample-lobby.jpg"))
    lobby = cv2.resize(lobby, None, fx=LOBBY_SCALE, fy=LOBBY_SCALE, interpolation=cv2.INTER_AREA)
    left, top, right, bottom = PATCH
    gap = round(_GAP * CARD_SCALE)
    stacks = {name: card_pictures(hits, likes) for name, (hits, likes) in PICTURES.items()}
    # Every picture's cards start where the tallest stack's do, down from CORNER: a shorter stack put on the
    # corner left half a lobby name showing above its top card.
    first = min(CORNER[1] - sum(card.shape[0] + gap for card in cards) + gap for cards in stacks.values())
    for name, cards in stacks.items():
        path = ASSETS / name
        picture = cv2.imread(str(path))
        x, y = LOBBY_AT
        picture[top:bottom, left:right] = lobby[y + top : y + bottom, x + left : x + right]
        place = first
        for card in reversed(cards):
            height, width = card.shape[:2]
            put(picture[:, :HALF_WIDTH], card, CORNER[0] - width, place)
            place += height + gap
        cv2.imwrite(str(path), picture, [cv2.IMWRITE_JPEG_QUALITY, 92])
        print(f"{name}: {picture.shape[1]}x{picture.shape[0]}")


if __name__ == "__main__":
    main()
