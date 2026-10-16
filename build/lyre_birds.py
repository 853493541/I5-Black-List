"""Cut 竖琴清风's three birds out of the friend's picture into blacklist_detect/assets/birds/.

    python build/lyre_birds.py [picture [debug_dir]]

The picture is fan art by the Weibo artist @子沐子_ (dist/refs_birds/friend_full.jpg in the main checkout, 1080x1527,
not in the repository), used at the user's decision. Only birds are taken: never the watermark, the seal, the signature,
the door, the text or the feathers. The birds overlap, so each is cut by hand-placed outline points (in the
picture's pixels, just outside its own line or the line it meets a neighbour along) and what the line encloses:
the dark line and the teal are walls, its small gaps closed, and the mint background is flooded from outside, so
the white belly (almost the background's colour) stays. Where a neighbour hides a bird's edge, the edge is drawn
on in the picture's line colour and the neighbour's part painted over in the bird's own colour. The flyer's raised
wing is cut as a layer of its own, its body closed where the wing was, so the scene can flap it.
With a debug folder, each cut-out is also saved 4x over dark green and over white, to look for halos and holes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "dist" / "refs_birds" / "friend_full.jpg"
OUT = ROOT / "blacklist_detect" / "assets" / "birds"
# Sampled from the picture: its line, the white of a belly, the teal of a body.
LINE, WHITE, TEAL = (70, 118, 104), (219, 252, 241), (84, 226, 200)
LINE_WIDE = 7
# How far the walls are widened to close the line's gaps before the background is flooded.
CLOSE = 5

# Each cut: its outline points; the stretches of that outline a neighbour hides, drawn on (as runs of point
# indices); parts painted over in a colour before it is cut (a neighbour showing inside the outline); its eyes,
# shut in a copy for its blink; and points the scene places it by, all in the picture's pixels.
BIRDS = {
    # Facing right, eyes open: for the lyre's crossbar, and turned round, the flyer.
    "perch": {
        "outline": [(312, 626), (332, 624), (350, 634), (360, 649), (374, 650), (390, 660), (396, 684), (416, 699),
                    (437, 721), (447, 751), (445, 778), (436, 800), (412, 836), (380, 858), (345, 867), (300, 869),
                    (240, 867), (213, 867), (180, 873), (144, 873), (139, 860), (160, 834), (196, 806), (205, 780),
                    (213, 756), (236, 742), (248, 726), (260, 700), (276, 684), (298, 668), (309, 655)],
        "drawn": [(10, 14)],
        # A neighbour's tail lies over the front of its belly.
        "paint": [([(356, 798), (416, 792), (446, 804), (444, 852), (384, 862), (354, 836)], WHITE)],
        "eyes": [(367, 741), (421, 735)],
        # Where the flyer's wing grows from its back.
        "points": {"back": (262, 724)},
    },
    # Facing the front, eyes open: for the cecilias.
    "lily": {
        "outline": [(690, 800), (705, 778), (730, 762), (752, 752), (770, 735), (787, 714), (806, 707), (822, 714),
                    (838, 735), (845, 766), (870, 778), (896, 800), (912, 825), (925, 852), (944, 870), (948, 905),
                    (940, 925), (925, 955), (890, 980), (840, 993), (770, 996), (700, 990), (640, 974), (606, 950),
                    (596, 925), (598, 880), (612, 852), (640, 840), (668, 836), (684, 826)],
        "drawn": [(16, 24)],
        # The heads of the two birds below it, over its belly.
        "paint": [([(596, 952), (660, 955), (713, 950), (737, 950), (770, 934), (809, 916), (847, 884), (875, 875),
                    (913, 893), (935, 906), (952, 912), (952, 1005), (590, 1005)], WHITE)],
        "eyes": [(776, 850), (859, 845)],
        "points": {},
    },
    # The raised wing of the bird at the bottom right, alone: the flyer flaps it.
    "wing": {
        "outline": [(960, 1180), (951, 1150), (946, 1100), (949, 1062), (957, 1022), (975, 989), (1000, 964),
                    (1030, 944), (1062, 933), (1075, 941), (1074, 975), (1076, 1010), (1075, 1040), (1070, 1075),
                    (1058, 1110), (1040, 1140), (1010, 1166), (980, 1184)],
        "drawn": [(0, 4)],
        "paint": [],
        "eyes": [],
        "points": {"root": (946, 1105)},
    },
}
# A shut eye as the picture's sleeping birds have one: a short thick red-brown stroke, curved a little.
SHUT = (101, 51, 44)


def _polygon(size: tuple[int, int], points: list, offset: tuple[int, int]) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).polygon([(x - offset[0], y - offset[1]) for x, y in points], fill=255)
    return mask


def cut(picture: Image.Image, spec: dict) -> tuple[Image.Image, tuple[int, int]]:
    """One bird as an RGBA picture cropped to it, and where its top left was in the picture."""
    xs, ys = zip(*spec["outline"], strict=True)
    box = (min(xs) - 12, min(ys) - 12, max(xs) + 12, max(ys) + 12)
    rgb = picture.crop(box).convert("RGB")
    offset = box[:2]
    draw = ImageDraw.Draw(rgb)
    painted = Image.new("L", rgb.size, 0)
    for points, color in spec["paint"]:
        draw.polygon([(x - offset[0], y - offset[1]) for x, y in points], fill=color)
        ImageDraw.Draw(painted).polygon([(x - offset[0], y - offset[1]) for x, y in points], fill=255)
    outline = [(x - offset[0], y - offset[1]) for x, y in spec["outline"]]
    for start, end in spec["drawn"]:
        draw.line(outline[start : end + 1], fill=LINE, width=LINE_WIDE, joint="curve")
    a = np.asarray(rgb).astype(int)
    ink = a.mean(axis=2) < 150
    teal = a[..., 1] - a[..., 0] > 90
    # What was painted over is the bird's own, a wall too.
    solid = ink | teal | (np.asarray(painted) > 0)
    walls = Image.fromarray((solid * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * CLOSE + 1))
    inside_outline = _polygon(rgb.size, spec["outline"], offset)
    # Flood the background from outside the outline; what it cannot reach is the bird.
    field = ImageChops.multiply(walls, inside_outline).point(lambda v: 255 if v else 0)
    ImageDraw.floodfill(field, (0, 0), 128)
    bird = field.point(lambda v: 0 if v == 128 else 255)
    # The walls were widened: take back as much, keeping the line itself.
    bird = ImageChops.lighter(bird.filter(ImageFilter.MinFilter(2 * CLOSE + 1)),
                              ImageChops.multiply(bird, Image.fromarray((ink * 255).astype(np.uint8))))
    bird = ImageChops.multiply(bird, inside_outline).filter(ImageFilter.GaussianBlur(0.7))
    out = rgb.convert("RGBA")
    out.putalpha(bird)
    left, top, right, bottom = out.getbbox()
    return out.crop((left, top, right, bottom)), (offset[0] + left, offset[1] + top)


def shut(image: Image.Image, eyes: list[tuple[int, int]]) -> Image.Image:
    """image with each eye (where it is in image's pixels) painted over in the face round it and shut."""
    out = image.copy()
    a = np.asarray(out).astype(int)
    draw = ImageDraw.Draw(out)
    for x, y in eyes:
        near = a[y - 22 : y + 23, x - 22 : x + 23]
        r, g = near[..., 0], near[..., 1]
        eye = (r > g + 20) & (near[..., :3].mean(axis=2) < 130)
        rows, cols = np.flatnonzero(eye.any(axis=1)), np.flatnonzero(eye.any(axis=0))
        top, bottom, left, right = y - 22 + rows[0], y - 22 + rows[-1], x - 22 + cols[0], x - 22 + cols[-1]
        # The face just round it: what is neither eye, blush nor line, in a ring a few pixels out.
        ys, xs = np.mgrid[y - 22 : y + 23, x - 22 : x + 23]
        dx = np.maximum(np.maximum(left - xs, xs - right), 0)
        dy = np.maximum(np.maximum(top - ys, ys - bottom), 0)
        ring = (np.hypot(dx, dy) > 3) & (np.hypot(dx, dy) < 7)
        face = ring & ~eye & (near[..., :3].mean(axis=2) > 150) & ~((r > 230) & (g < 215)) & (near[..., 3] > 250)
        # Each pixel of the eye, and a little round it, takes the colour of the nearest of those, so an eye on the
        # line between teal and white is covered by both.
        cover = (np.hypot(dx, dy) <= 3) & (near[..., 3] > 0)
        fy, fx = np.nonzero(face)
        for cy, cx in zip(*np.nonzero(cover), strict=True):
            k = np.argmin((fy - cy) ** 2 + (fx - cx) ** 2)
            out.putpixel((x - 22 + cx, y - 22 + cy), (*(int(v) for v in near[fy[k], fx[k], :3]), int(near[cy, cx, 3])))
        wide, low = (right - left) * 0.8 + 3, top + (bottom - top) * 0.62
        cx = (left + right) / 2
        draw.line([(cx - wide, low - 2), (cx - wide / 3, low + 1), (cx + wide / 3, low + 1), (cx + wide, low - 2)],
                  fill=(*SHUT, 255), width=max(3, round((bottom - top) * 0.3)), joint="curve")
    return out


def _check(image: Image.Image, path: Path) -> None:
    """The cut-out 4x over dark green and over white, side by side."""
    big = image.resize((image.width * 4, image.height * 4), Image.LANCZOS)
    sheet = Image.new("RGBA", (big.width * 2 + 20, big.height), (255, 255, 255, 255))
    sheet.paste(Image.new("RGBA", big.size, (24, 84, 64, 255)), (0, 0))
    sheet.alpha_composite(big, (0, 0))
    sheet.alpha_composite(big, (big.width + 20, 0))
    sheet.convert("RGB").save(path)


def main() -> None:
    picture = Image.open(sys.argv[1] if sys.argv[1:] else SOURCE)
    OUT.mkdir(parents=True, exist_ok=True)
    debug = Path(sys.argv[2]) if sys.argv[2:] else None
    places = {}
    for name, spec in BIRDS.items():
        image, (left, top) = cut(picture, spec)
        pictures = {name: image}
        if spec["eyes"]:
            pictures[f"{name}_blink"] = shut(image, [(x - left, y - top) for x, y in spec["eyes"]])
        for key, picture_of in pictures.items():
            picture_of.save(OUT / f"{key}.png", optimize=True)
            if debug:
                debug.mkdir(parents=True, exist_ok=True)
                _check(picture_of, debug / f"{key}_check.png")
        places[name] = {key: [x - left, y - top] for key, (x, y) in spec["points"].items()}
        print(f"{name}: {image.width}x{image.height}")
    (OUT / "birds.json").write_text(json.dumps(places, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
