"""Cut 竖琴清风's birds out of the friend's picture into blacklist_detect/assets/birds/.

    python build/lyre_birds.py [picture [debug_dir]]

The picture is fan art by the Weibo artist @子沐子_ (dist/refs_birds/friend_full.jpg in the main checkout, 1080x1527,
not in the repository), used at the user's decision. Only birds are taken: never the watermark, the seal, the signature,
the door, the text or the feathers.

Each bird is worked at SCALE times the picture's pixels. Every pixel is given the colour of the picture's palette it
belongs to (the drawing is flat colour: the JPEG's noise and its halos go, its edges stay where the picture has them),
then the birds' hidden parts are drawn on in the picture's own line and colours, the bird is taken as what its seeds
reach inside the line (what the line encloses), and it is made small for the file with smooth edges. The birds
overlap, so each cut is held inside a hand-placed outline, in the picture's pixels, just outside its own line.
With a debug folder, each bird is also saved beside the picture's, over dark green, large and at the scene's size.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "dist" / "refs_birds" / "friend_full.jpg"
OUT = ROOT / "blacklist_detect" / "assets" / "birds"
# The picture's colours, sampled from it. White is the bellies' and the paper's both: what is not the bird's is told
# by the line round it, never by its colour.
PALETTE = {
    "white": (219, 252, 241),
    "line": (72, 122, 111),
    "teal": (84, 227, 200),
    "ear": (185, 248, 231),
    "dark": (55, 143, 127),
    "pink": (255, 177, 185),
    "eye": (98, 55, 49),
    "brow": (176, 96, 88),
    "beak": (251, 247, 227),
    "mark": (175, 125, 178),
}
NAMES = list(PALETTE)
COLORS = np.array([PALETTE[name] for name in NAMES], dtype=np.float32)
WHITE, LINE = NAMES.index("white"), NAMES.index("line")
# Worked at this many times the picture's pixels; saved at OUT_SCALE times them.
SCALE, OUT_SCALE = 4, 2
# The line's width in the picture, and how far its gaps (the dashes round a fluffy edge) are closed when what it
# encloses is found.
LINE_WIDE, CLOSE = 7.5, 6
# How far each colour's edge is evened, in the picture's pixels: past the JPEG's wobble, short of the eyes' shapes.
EVEN = 1.1

# Each bird: the box it is worked in; its outline (it is never taken past it); points inside each of its parts the
# line divides it into; what is drawn on before it is cut (each ("fill", colour, points[, only over these colours]) or
# ("line", points[, width[, colour]]), smooth curves through the points); its eyes, shut in a copy for its blink; and
# points the scene places it by, all in the picture's pixels.
BIRDS = {
    # Facing right, eyes open: for the lyre's crossbar, and turned round, the flyer. The sleeping bird to its right
    # lays its tail over its belly's front: the belly is drawn on round to its bottom.
    "perch": {
        "box": (128, 612, 462, 884),
        "outline": [(312, 622), (334, 619), (352, 632), (362, 646), (378, 647), (393, 660), (400, 683), (420, 697),
                    (440, 718), (448, 750), (452, 790), (452, 822), (440, 848), (414, 866), (380, 874), (345, 875),
                    (300, 874), (240, 872), (213, 872), (180, 878), (140, 878), (134, 860), (156, 832), (194, 804),
                    (201, 780), (209, 754), (232, 738), (244, 722), (256, 698), (273, 680), (296, 664), (306, 652)],
        "seeds": [(330, 760), (320, 655), (370, 670), (250, 800), (170, 850), (290, 862)],
        "repair": [
            ("fill", "white", [(352, 870), (344, 846), (370, 822), (400, 812), (428, 802), (436, 780), (448, 776),
                               (455, 805), (450, 836), (433, 856), (405, 872)], ["line", "dark"]),
            ("line", [(441, 766), (446, 790), (445, 815), (436, 838), (416, 856), (390, 866), (356, 869)]),
        ],
        "eyes": [(367, 741), (421, 735)],
        "points": {},
    },
    # Facing the front, eyes open: for the cecilias. The picture's biggest bird, at its bottom left, cut off by the
    # picture's bottom edge: its wings' tips and its belly's bottom are drawn on below it. Its dark tail rises behind
    # its right side.
    "lily": {
        "box": (0, 1050, 612, 1650),
        "outline": [(2, 1360), (2, 1290), (40, 1240), (100, 1180), (160, 1120), (195, 1075), (232, 1056), (272, 1058),
                    (288, 1100), (300, 1130), (326, 1146), (334, 1176), (350, 1186), (400, 1206), (430, 1218),
                    (455, 1232), (476, 1250), (489, 1262), (500, 1258), (512, 1256), (522, 1246), (534, 1234),
                    (548, 1224), (560, 1217), (574, 1212), (588, 1222), (594, 1260), (592, 1300), (590, 1325),
                    (598, 1338), (597, 1352), (586, 1360), (572, 1374), (560, 1400), (558, 1440), (550, 1478),
                    (536, 1505), (520, 1522), (476, 1542), (460, 1575), (440, 1605), (415, 1626), (380, 1632),
                    (300, 1632), (200, 1630), (120, 1615), (70, 1580), (35, 1552), (2, 1530)],
        "seeds": [(200, 1450), (200, 1250), (230, 1130), (295, 1180), (45, 1480), (40, 1420), (390, 1450), (480, 1420),
                  (470, 1470), (540, 1260), (520, 1330), (560, 1350), (200, 1580)],
        "repair": [
            # The left wing's tip, the belly's bottom with the fluff the picture's birds have along it, and the right
            # wing's tip on it.
            ("line", [(38, 1510), (48, 1532), (63, 1543), (77, 1536), (82, 1522)]),
            ("line", [(80, 1528), (96, 1564), (130, 1594), (180, 1612), (240, 1620), (290, 1619)]),
            ("line", [(298, 1618), (306, 1617), (314, 1616)], 6.5),
            ("line", [(322, 1614), (328, 1613)], 6),
            ("line", [(336, 1611), (352, 1608), (370, 1605)]),
            ("line", [(347, 1516), (350, 1550), (360, 1580), (378, 1602), (400, 1612)]),
            ("line", [(458, 1516), (448, 1550), (433, 1584), (416, 1605), (398, 1613)]),
            ("fill", "teal", [(433, 1522), (447, 1522), (441, 1546), (433, 1541)]),
            ("line", [(176, 1516), (180, 1532), (189, 1545)], 5.5, "teal"),
        ],
        "eyes": [(107, 1348), (237, 1346)],
        "points": {},
    },
    # Facing the front, eyes open: the flyer. The bird at the bottom right raising its wing, without it: the bird in
    # front of it hides its belly's left and bottom, and its wing its right side, so its sides and belly are drawn on
    # round to its bottom. The wing below is its own, flapped at both its sides.
    "front": {
        "box": (670, 870, 990, 1240),
        "outline": [(728, 968), (760, 950), (800, 930), (818, 912), (838, 893), (862, 880), (882, 888), (888, 915),
                    (895, 930), (905, 945), (925, 965), (950, 990), (966, 1003), (975, 1040), (978, 1100), (974, 1160),
                    (958, 1195), (930, 1218), (880, 1230), (820, 1230), (760, 1212), (720, 1185), (695, 1150),
                    (680, 1100), (677, 1050), (684, 1010), (700, 985)],
        "seeds": [(820, 975), (845, 920), (720, 1010), (925, 1030), (850, 1150)],
        "repair": [
            # Its sides teal down to its belly, the belly white from under its beak.
            ("fill", "teal", [(684, 1030), (722, 1040), (768, 1056), (776, 1100), (684, 1100)], ["white", "ear", "line", "dark"]),
            ("fill", "teal", [(768, 1056), (783, 1050), (790, 1072), (796, 1100), (774, 1100)], ["white", "ear"]),
            ("fill", "teal", [(930, 1000), (952, 1000), (972, 1010), (976, 1100), (850, 1100), (850, 1078), (880, 1072),
                              (906, 1060)], ["white", "line", "dark", "ear"]),
            ("fill", "white", [(684, 1088), (740, 1090), (790, 1088), (830, 1081), (860, 1079), (900, 1082), (976, 1084), (975, 1160),
                               (940, 1200), (850, 1228), (760, 1215), (700, 1170), (680, 1110)]),
            ("fill", "white", [(810, 1086), (830, 1074), (870, 1074), (870, 1095), (810, 1095)], ["dark", "line", "teal"]),
            # Round and wider than tall as the picture's birds are, its bottom fluffy as theirs: broken, with flicks.
            ("line", [(737, 976), (714, 990), (698, 1015), (690, 1048), (687, 1085), (689, 1120), (699, 1148), (720, 1170),
                      (750, 1185), (768, 1190)]),
            ("line", [(778, 1193), (792, 1195)], 6.5),
            ("line", [(802, 1197), (850, 1198), (892, 1193), (926, 1179), (950, 1155), (962, 1120), (966, 1075), (962, 1032),
                      (944, 1002)]),
            ("line", [(733, 1178), (727, 1187), (720, 1192)], 5.5),
            ("line", [(906, 1188), (914, 1195), (922, 1198)], 5.5),
            ("line", [(956, 1140), (964, 1146), (969, 1154)], 5),
        ],
        "eyes": [(748, 1028), (863, 1045)],
        # Where its wings grow from its sides: at the shoulders, where the teal of its sides meets its white belly.
        "points": {"left": (701, 1090), "right": (953, 1090)},
    },
    # The raised wing of the bird at the bottom right, alone: the flyer flaps it. Its edge where it meets that bird's
    # body is drawn on.
    "wing": {
        "box": (930, 920, 1080, 1196),
        "outline": [(949, 1010), (960, 990), (985, 962), (1020, 940), (1058, 928), (1077, 936), (1080, 975),
                    (1080, 1015), (1080, 1060), (1072, 1092), (1062, 1122), (1047, 1156), (1012, 1180), (978, 1184),
                    (958, 1176), (946, 1158), (938, 1125), (936, 1095), (939, 1060), (944, 1030)],
        "seeds": [(1040, 1000), (972, 1090), (1030, 1135)],
        # Its edge where the top feather ends, open in the picture, wider than the fluff's gaps: closed thinly.
        "repair": [("line", [(950, 1062), (946, 1095), (948, 1125), (955, 1148), (965, 1162), (977, 1170)]),
                   ("line", [(1053, 996), (1062, 1004), (1066, 1013), (1062, 1021)], 4.5),
                   ("fill", "teal", [(1048, 996), (1058, 1000), (1063, 1010), (1059, 1020), (1048, 1018)], ["white"])],
        "eyes": [],
        # Its base, where it turns, and its tip.
        "points": {"root": (962, 1166), "tip": (1058, 930)},
    },
    # A folded wing, alone: the cecilias' bird's own (at its right), held flat on its side as the picture's birds that
    # face us hold theirs. The flyer folds its wings to it. Its bottom, past the picture's edge, is drawn on as that
    # bird's is.
    "fold": {
        "box": (300, 1310, 480, 1640),
        "outline": [(320, 1400), (335, 1365), (365, 1338), (400, 1328), (440, 1336), (462, 1352), (472, 1380), (474, 1420),
                    (474, 1460), (474, 1500), (470, 1530), (458, 1565), (440, 1598), (415, 1624), (390, 1627), (365, 1612),
                    (345, 1587), (332, 1550), (322, 1500), (316, 1450)],
        "seeds": [(380, 1450), (400, 1380)],
        "repair": [
            ("line", [(347, 1516), (350, 1550), (360, 1580), (378, 1602), (400, 1612)]),
            ("line", [(458, 1516), (448, 1550), (433, 1584), (416, 1605), (398, 1613)]),
            # Alone, it is closed where it meets the body: at its top, thinly behind the dashes down its inner edge,
            # and below its scallops, where the body's teal shows, by one more scallop.
            ("fill", "white", [(392, 1352), (446, 1350), (452, 1374), (428, 1366), (398, 1364)], ["teal"]),
            ("line", [(432, 1342), (446, 1352), (452, 1366), (452, 1382)]),
            ("line", [(343, 1418), (337, 1445), (334, 1470), (335, 1497)], 4.5),
            ("fill", "white", [(424, 1494), (463, 1486), (463, 1528), (428, 1530)], ["teal"]),
            ("line", [(428, 1490), (446, 1490), (456, 1500), (459, 1518)]),
        ],
        "eyes": [],
        # The flyer wears it at 0.42 of its size: its line all round, the inner edge too where it lies over the white
        # body, thick enough to be the flyer's line there.
        "rim": 15,
        # Where it hangs from the bird's shoulder, and opens out about: under its top, its outer third past the side.
        "points": {"root": (402, 1415)},
    },
}


def _smooth(points: list, closed: bool, step: float = 1.0) -> np.ndarray:
    """A Catmull-Rom curve through points, sampled about every step pixels."""
    p = np.asarray(points, dtype=np.float64)
    if closed:
        p = np.vstack([p[-1], p, p[0], p[1]])
    else:
        p = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = []
    for i in range(1, len(p) - 2):
        a, b, c, d = p[i - 1], p[i], p[i + 1], p[i + 2]
        n = max(2, int(np.hypot(*(c - b)) / step))
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * (2 * b + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (-a + 3 * b - 3 * c + d) * t ** 3))
    out.append(p[-2])
    return np.array(out)


def labels_of(picture: np.ndarray) -> np.ndarray:
    """Each pixel's colour in the palette (an index into NAMES): what the picture's flat colours are, each edge where
    the colour changes most, as the watershed of the colours from where they are clean."""
    soft = cv2.GaussianBlur(picture, (0, 0), SCALE * 0.35)
    far = np.linalg.norm(soft[..., None, :].astype(np.float32) - COLORS[None, None], axis=3)
    near, nearest = far.min(axis=2), far.argmin(axis=2)
    gray = cv2.cvtColor(soft, cv2.COLOR_RGB2GRAY).astype(np.float32)
    edge = np.hypot(cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1)) / SCALE
    markers = np.where((near < 26) & (edge < 40), nearest + 1, 0).astype(np.int32)
    cv2.watershed(np.ascontiguousarray(soft[..., ::-1]), markers)
    # The watershed's own lines, a pixel wide, go to the colour beside them.
    gaps = markers <= 0
    markers[gaps] = 0
    grown = cv2.dilate(markers.astype(np.uint8), np.ones((3, 3), np.uint8))
    markers[gaps] = grown[gaps]
    return markers.astype(np.int32) - 1


def _draw(labels: np.ndarray, repairs: list, origin: tuple[int, int]) -> None:
    """The repairs drawn on labels (worked at SCALE, its top left at origin in the picture)."""
    ox, oy = origin
    for repair in repairs:
        kind, rest = repair[0], repair[1:]
        if kind == "fill":
            color, points, *over = rest
            curve = (_smooth(points, closed=True) - (ox, oy)) * SCALE
            area = np.zeros(labels.shape, np.uint8)
            cv2.fillPoly(area, [np.round(curve).astype(np.int32)], 1)
            if over:
                area &= np.isin(labels, [NAMES.index(name) for name in over[0]])
            labels[area > 0] = NAMES.index(color)
        else:
            points, wide, color = (*rest, LINE_WIDE, "line")[:3] if len(rest) == 1 else (*rest, "line")[:3]
            curve = (_smooth(points, closed=False) - (ox, oy)) * SCALE
            # Thick in the middle, thinning to its ends as a brush's stroke does.
            k = np.linspace(0, 1, len(curve))
            widths = wide * SCALE * (0.55 + 0.45 * np.sin(np.pi * k) ** 0.5)
            for (x, y), w in zip(curve, widths, strict=True):
                cv2.circle(labels, (round(x), round(y)), max(1, round(w / 2)), NAMES.index(color), -1)


def _even(labels: np.ndarray) -> np.ndarray:
    """labels with each colour's edges smoothed, as a vector drawing's: no JPEG steps or specks."""
    weights = np.stack([cv2.GaussianBlur((labels == k).astype(np.float32), (0, 0), SCALE * EVEN) for k in range(len(NAMES))])
    return weights.argmax(axis=0).astype(np.int32)


def _bird_mask(labels: np.ndarray, spec: dict, origin: tuple[int, int]) -> np.ndarray:
    """Where the bird is: the parts of it its seeds are in, with the line round them, inside its outline. The paper
    is what is reached from outside the outline without crossing the line, the line's gaps (the dashes round a fluffy
    edge) closed, back up to the line; the parts are what the line divides the rest into, thin ones too."""
    ox, oy = origin
    h, w = labels.shape
    outline = np.zeros((h, w), np.uint8)
    cv2.fillPoly(outline, [np.round((_smooth(spec["outline"], closed=True) - (ox, oy)) * SCALE).astype(np.int32)], 1)
    line = (labels == LINE).astype(np.uint8)
    close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * CLOSE * SCALE + 1,) * 2)
    free = (cv2.dilate(line, close) == 0) | (outline == 0)
    _count, parts = cv2.connectedComponents(free.astype(np.uint8), connectivity=4)
    paper = np.isin(parts, np.unique(parts[(outline == 0) & free])).astype(np.uint8)
    paper = cv2.dilate(paper, close) & (line == 0) | (outline == 0)
    _count, parts = cv2.connectedComponents(((paper == 0) & (line == 0)).astype(np.uint8), connectivity=4)
    chosen = {parts[round((y - oy) * SCALE), round((x - ox) * SCALE)] for x, y in spec["seeds"]}
    chosen.discard(0)
    inside = np.isin(parts, list(chosen)).astype(np.uint8)
    # The line round them, as far as it is wide.
    reach = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (round(2 * LINE_WIDE * SCALE) + 1,) * 2)
    bird = (inside > 0) | (line > 0) & (cv2.dilate(inside, reach) > 0)
    bird &= outline > 0
    # Holes (the beak inside its line) are the bird's.
    holes = bird.astype(np.uint8)
    cv2.floodFill(holes, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 1)
    return bird | (holes == 0)


def _shut(labels: np.ndarray, eyes: list, origin: tuple[int, int]) -> np.ndarray:
    """labels with each eye (in the picture's pixels) covered by the face round it and shut: a short, thick stroke of
    the eye's colour, as the picture's sleeping birds have."""
    out = labels.copy()
    ox, oy = origin
    eye = NAMES.index("eye")
    for x, y in eyes:
        cx, cy = round((x - ox) * SCALE), round((y - oy) * SCALE)
        r = 26 * SCALE
        box = out[cy - r : cy + r, cx - r : cx + r]
        _count, parts = cv2.connectedComponents((box == eye).astype(np.uint8))
        mine = parts == parts[r, r]
        ys, xs = np.nonzero(mine)
        # The face round it: each pixel of the eye takes the nearest colour that is not the eye's.
        grown = cv2.dilate(mine.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
        face = ~grown & (box != eye) & (box != NAMES.index("brow"))
        _d, index = cv2.distanceTransformWithLabels((~face).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
        fy, fx = np.nonzero(face)
        lookup = np.zeros(index.max() + 1, np.int32)
        lookup[index[face]] = box[fy, fx]
        box[grown] = lookup[index[grown]]
        wide, high = xs.max() - xs.min(), ys.max() - ys.min()
        mid_x, low = (xs.min() + xs.max()) / 2, ys.min() + high * 0.58
        bar = np.array([(mid_x - wide * 0.62, low - high * 0.03), (mid_x, low + high * 0.03), (mid_x + wide * 0.62, low - high * 0.03)])
        for px, py in _smooth(bar, closed=False):
            cv2.circle(box, (round(px), round(py)), max(2, round(high * 0.2)), eye, -1)
    return out


def render(labels: np.ndarray, mask: np.ndarray) -> Image.Image:
    """The bird in the palette's colours, made small to OUT_SCALE with smooth edges, cropped to it."""
    rgba = np.zeros((*labels.shape, 4), np.float32)
    rgba[..., :3] = COLORS[labels] * mask[..., None]
    rgba[..., 3] = 255 * mask
    k = SCALE // OUT_SCALE
    h, w = (labels.shape[0] // k) * k, (labels.shape[1] // k) * k
    small = rgba[:h, :w].reshape(h // k, k, w // k, k, 4).mean(axis=(1, 3))
    alpha = small[..., 3:4]
    small[..., :3] = np.where(alpha > 0, small[..., :3] * 255 / np.maximum(alpha, 1e-6), 0)
    image = Image.fromarray(np.clip(np.round(small), 0, 255).astype(np.uint8), "RGBA")
    return image


def cut(picture: Image.Image, spec: dict) -> tuple[dict[str, Image.Image], tuple[float, float]]:
    """The bird (and its blink, if it has eyes) as RGBA pictures at OUT_SCALE cropped to it, and where their top left
    is in the picture's pixels."""
    x0, y0, x1, y1 = spec["box"]
    # A box past the picture's edge is the paper's colour there.
    canvas = Image.new("RGB", (x1 - x0, y1 - y0), PALETTE["white"])
    canvas.paste(picture.crop((max(0, x0), max(0, y0), min(picture.width, x1), min(picture.height, y1))), (max(0, -x0), max(0, -y0)))
    big = cv2.resize(np.asarray(canvas), None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_CUBIC)
    labels = labels_of(big)
    _draw(labels, spec["repair"], (x0, y0))
    labels = _even(labels)
    mask = _bird_mask(labels, spec, (x0, y0))
    if "rim" in spec:
        # The line round it all, as thick as asked, inward from its edge.
        inward = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
        labels[(inward > 0) & (inward < spec["rim"] * SCALE)] = LINE
    pictures = {"": render(labels, mask)}
    if spec["eyes"]:
        pictures["_blink"] = render(_shut(labels, spec["eyes"], (x0, y0)), mask)
    left, top, right, bottom = pictures[""].getbbox()
    crops = {key: image.crop((left, top, right, bottom)) for key, image in pictures.items()}
    return crops, (x0 + left / OUT_SCALE, y0 + top / OUT_SCALE)


def _check(image: Image.Image, source: Image.Image, wide: int, path: Path) -> None:
    """The cut-out beside the picture's bird: large, then both wide pixels across, over dark green and over the
    picture's paper."""
    big = image.resize((image.width * 2, image.height * 2), Image.LANCZOS)
    src = source.resize(big.size, Image.LANCZOS).convert("RGBA")
    small = image.resize((wide, round(image.height * wide / image.width)), Image.LANCZOS)
    small_src = source.resize(small.size, Image.LANCZOS).convert("RGBA")
    sheet = Image.new("RGBA", (big.width * 3 + 40, big.height + small.height * 4 + 60), (255, 255, 255, 255))
    sheet.paste(src, (0, 0))
    sheet.paste(Image.new("RGBA", big.size, (24, 84, 64, 255)), (big.width + 20, 0))
    sheet.alpha_composite(big, (big.width + 20, 0))
    sheet.alpha_composite(big, (2 * big.width + 40, 0))
    y = big.height + 20
    for zoom in (1, 3):
        a = small_src.resize((small.width * zoom, small.height * zoom), Image.NEAREST)
        b = small.resize(a.size, Image.NEAREST)
        sheet.paste(a, (0, y))
        sheet.paste(Image.new("RGBA", b.size, (24, 84, 64, 255)), (a.width + 20, y))
        sheet.alpha_composite(b, (a.width + 20, y))
        y += a.height + 20
    sheet.convert("RGB").save(path)


def main() -> None:
    picture = Image.open(sys.argv[1] if sys.argv[1:] else SOURCE).convert("RGB")
    OUT.mkdir(parents=True, exist_ok=True)
    debug = Path(sys.argv[2]) if sys.argv[2:] else None
    places = {}
    for name, spec in BIRDS.items():
        pictures, (left, top) = cut(picture, spec)
        for key, image in pictures.items():
            image.save(OUT / f"{name}{key}.png", optimize=True)
        if debug:
            debug.mkdir(parents=True, exist_ok=True)
            image = pictures[""]
            box = (left, top, left + image.width / OUT_SCALE, top + image.height / OUT_SCALE)
            _check(image, picture.crop(tuple(round(v) for v in box)), 64, debug / f"{name}_check.png")
            if "_blink" in pictures:
                _check(pictures["_blink"], picture.crop(tuple(round(v) for v in box)), 64, debug / f"{name}_blink_check.png")
        places[name] = {key: [round((x - left) * OUT_SCALE), round((y - top) * OUT_SCALE)] for key, (x, y) in spec["points"].items()}
        print(f"{name}: {pictures[''].width}x{pictures[''].height}")
    (OUT / "birds.json").write_text(json.dumps(places, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
