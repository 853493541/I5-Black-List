"""Cut the 演说家遇袭 notice's own art out of a picture of it, for 遇袭 (love_scenes.claw).

    python build/orator_notice_art.py <cover.jpg>

The picture is the cover of Bilibili video BV1xDsaexE92 (1728x1080), a close shot of the game's notice;
the user chose to use the game's own art, knowing NetEase owns it. It writes blacklist_detect/assets/
orator_paper.png (the BIG NEWS newspaper, its stacked sheets and dark outline kept) and orator_words.png
(演说家遇袭 in the game's lettering), both RGBA, and prints where each sat in the picture, which
love_scenes.claw keeps so the two stay as the game spaces them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ASSETS = Path(__file__).resolve().parent.parent / "blacklist_detect" / "assets"
# Where the newspaper and the words are in the picture: left, top, right, bottom.
PAPER_BOX = (0, 300, 572, 790)
WORDS_BOX = (585, 430, 1640, 660)


def smooth(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    k = np.clip((x - e0) / (e1 - e0), 0, 1)
    return k * k * (3 - 2 * k)


def fill_from_corners(mask: Image.Image) -> np.ndarray:
    """What of a white-on-black mask is enclosed: everything not reachable from its corners through black."""
    inv = Image.fromarray(255 - np.asarray(mask)).copy()
    for corner in ((0, 0), (inv.width - 1, 0), (0, inv.height - 1), (inv.width - 1, inv.height - 1)):
        if inv.getpixel(corner) == 255:
            ImageDraw.floodfill(inv, corner, 128)
    return np.asarray(inv) != 128


def big_pieces(mask: np.ndarray, least: int) -> np.ndarray:
    """The pieces of a mask at least this many pixels big."""
    work = Image.fromarray((mask * 255).astype(np.uint8)).copy()
    keep = np.zeros(mask.shape, dtype=bool)
    while True:
        ys, xs = np.nonzero(np.asarray(work) == 255)
        if len(ys) == 0:
            return keep
        ImageDraw.floodfill(work, (int(xs[0]), int(ys[0])), 100)
        piece = np.asarray(work) == 100
        if piece.sum() >= least:
            keep |= piece
        # A copy: a picture made from an array is read-only, and the next fill would change nothing.
        work = Image.fromarray(np.where(piece, 50, np.asarray(work)).astype(np.uint8)).copy()


def cut(rgb: np.ndarray, alpha: np.ndarray, box: tuple[int, int, int, int]) -> tuple[Image.Image, tuple[int, int]]:
    image = Image.fromarray((np.dstack([rgb, alpha]) * 255).astype(np.uint8), "RGBA")
    bbox = image.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    return image.crop(bbox), (box[0] + bbox[0], box[1] + bbox[1])


def main() -> None:
    picture = np.asarray(Image.open(sys.argv[1]).convert("RGB")).astype(np.float32) / 255.0
    lum = picture @ np.array([0.299, 0.587, 0.114], dtype=np.float32)

    left, top, right, bottom = PAPER_BOX
    light = lum[top:bottom, left:right]
    # The paper is bright with dark ink on it and a dark outline: grow the bright part to close its
    # outlines, fill what they enclose, shrink back, keep the sheets (not specks), and grow a little
    # so the outline comes with them. Its smoke, faint, round it.
    solid = Image.fromarray(((light > 0.5) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(13))
    closed = Image.fromarray((fill_from_corners(solid) * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(13))
    sheets = big_pieces(np.asarray(closed) == 255, 3000)
    shape = Image.fromarray((sheets * 255).astype(np.uint8))
    body = np.asarray(shape.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(1.5))).astype(np.float32) / 255
    near = np.asarray(shape.filter(ImageFilter.MaxFilter(41))).astype(np.float32) / 255
    alpha = np.clip(np.maximum(body, smooth(0.32, 0.6, light) * 0.5 * near), 0, 1)
    paper, paper_at = cut(picture[top:bottom, left:right], alpha, PAPER_BOX)
    paper.save(ASSETS / "orator_paper.png")

    left, top, right, bottom = WORDS_BOX
    light = lum[top:bottom, left:right]
    rgb = picture[top:bottom, left:right]
    # White on dark: how bright a pixel is says how much of it is the words; their own colour kept.
    color = np.clip(rgb / np.maximum(rgb.max(axis=2, keepdims=True), 1e-4) * 0.97, 0, 1)
    words, words_at = cut(color, smooth(0.42, 0.78, light), WORDS_BOX)
    words.save(ASSETS / "orator_words.png")
    print(f"paper {paper.size} at {paper_at}; words {words.size} at {words_at}")


if __name__ == "__main__":
    main()
