"""Golden data for the Rust OCR on an OpenCV with Intel IPP (rust/ocr tests, the CI's Windows job).

opencv-python 4.10 resizes INTER_CUBIC through Intel IPP, and OpenCV 4.6 draws some slanted fillPoly masks a pixel
differently. The real lobby crops show real names and stay out of git, so this script makes its own: name strips with
made-up names (the SEATS of tools/ui_shots.py) drawn on dark, noisy backgrounds at the sizes a lobby crop has, and
slanted quads like the detector's boxes. It writes, under --out:

- crops/*.png and strips.json, in the schema of rust/ocr/tests/golden/rec/strips.json (prepared and plain checksums,
  the plain one also with IPP off), for tests/rec_golden.rs through REC_CROPS and REC_GOLDEN;
- fillpoly.json, the masks cv2.fillPoly draws, for tests/fillpoly_golden.rs through FILLPOLY_GOLDEN.

    PYTHONPATH=. python tools/rust_golden_ipp.py --out /tmp/ipp-golden

Seeded: the same OpenCV and font give the same files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SEATS = ["小林同学", "白日梦想家", "路过的猫", "一只团子", "夏天的风", "心动小鹿", "晚风吹过", "摸鱼大师", "示例坏人", "心动星星",
         "柠檬汽水", "棉花糖"]
FONTS = ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf", "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
         "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]
FRAMES = 20
POLYS = 400


def checksum(image: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(image).tobytes()).hexdigest()


def font_file() -> str | None:
    return next((path for path in FONTS if os.path.exists(path)), None)


def strip(rng: np.random.Generator, name: str, font: str | None) -> np.ndarray:
    """A name card's bottom: a dark noisy band with the name in light ink, now and then a bright portrait edge above."""
    height, width = int(rng.integers(22, 61)), int(rng.integers(90, 321))
    base = rng.integers(10, 70, size=3)
    ramp = np.linspace(0, rng.integers(0, 40), width)[None, :, None]
    background = np.clip(base[None, None, :] + ramp + rng.normal(0, 6, (height, width, 3)), 0, 255).astype(np.uint8)
    image = Image.fromarray(background)
    draw = ImageDraw.Draw(image)
    if rng.random() < 0.4:
        draw.rectangle([0, 0, width, int(height * rng.uniform(0.15, 0.4))], fill=tuple(int(v) for v in rng.integers(150, 256, 3)))
    size = max(10, int(height * rng.uniform(0.45, 0.7)))
    face = ImageFont.truetype(font, size) if font else ImageFont.load_default()
    ink = tuple(int(v) for v in rng.integers(190, 256, 3))
    draw.text((int(rng.integers(2, 12)), height - size - int(rng.integers(2, 6))), name, font=face, fill=ink)
    return np.array(image)


def quad(rng: np.random.Generator) -> tuple[list[list[int]], int, int]:
    """A slanted box as the detector finds it: a rotated rectangle with integer corners, inside its own mask."""
    width, height = rng.uniform(30, 300), rng.uniform(8, 40)
    angle = rng.uniform(-0.12, 0.12)
    cos, sin = np.cos(angle), np.sin(angle)
    corners = np.array([[0, 0], [width, 0], [width, height], [0, height]]) - [width / 2, height / 2]
    turned = corners @ np.array([[cos, sin], [-sin, cos]]) + rng.uniform(0, 1, 2)
    turned -= turned.min(axis=0)
    poly = np.round(turned).astype(np.int32)
    h, w = int(poly[:, 1].max()) + 1, int(poly[:, 0].max()) + 1
    return poly.tolist(), h, w


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path(tempfile.gettempdir()) / "ipp-golden")
    args = parser.parse_args()
    from blacklist_detect import ocr_engine

    crops = args.out / "crops"
    crops.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261118)
    font = font_file()
    frames = []
    for index in range(FRAMES):
        images = [strip(rng, SEATS[(index + slot) % len(SEATS)], font) for slot in range(12)]
        cv2.ipp.setUseIPP(True)
        prepared = [ocr_engine.prepare_name_line(image) for image in images]
        plain = [ocr_engine.prepare_name_line_plain(image) for image in images]
        cv2.ipp.setUseIPP(False)
        plain_noipp = [ocr_engine.prepare_name_line_plain(image) for image in images]
        cv2.ipp.setUseIPP(True)
        strips = []
        for slot, image in enumerate(images):
            name = f"made_{index:02d}_{slot:02d}.png"
            Image.fromarray(image).save(crops / name)
            strips.append({
                "crop": name, "crop_sha": checksum(image),
                "prepared_shape": list(prepared[slot].shape), "prepared_sha": checksum(prepared[slot]),
                "plain_shape": list(plain[slot].shape), "plain_sha": checksum(plain[slot]),
                "noipp": {"plain_sha": checksum(plain_noipp[slot])},
            })
        frames.append({"frame": f"made_{index:02d}", "strips": strips})
    differ = sum(s["plain_sha"] != s["noipp"]["plain_sha"] for f in frames for s in f["strips"])
    with open(args.out / "strips.json", "w", encoding="utf-8") as handle:
        json.dump({"opencv": cv2.__version__, "ipp": cv2.ipp.getIppVersion(), "font": font, "frames": frames}, handle,
                  ensure_ascii=False, indent=1)

    cases = []
    for _ in range(POLYS):
        poly, h, w = quad(rng)
        mask = np.zeros((h, w), np.uint8)
        cv2.fillPoly(mask, [np.array(poly, np.int32)], 1)
        cases.append({"poly": poly, "h": h, "w": w, "sum": int(mask.sum()), "rows": mask.sum(axis=1).tolist()})
    with open(args.out / "fillpoly.json", "w", encoding="utf-8") as handle:
        json.dump(cases, handle)
    print(f"opencv {cv2.__version__} ({cv2.ipp.getIppVersion()}), font {font}: {FRAMES * 12} strips "
          f"({differ} whose plain line differs without IPP), {POLYS} fillPoly masks under {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
