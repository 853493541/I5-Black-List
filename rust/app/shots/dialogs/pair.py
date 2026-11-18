"""Side-by-side pictures: the Python card (pyrefs.py) on the left, the Rust one cropped from its dimmed window on the
right. Usage: python3 pair.py <python-dir> <rust-dir> <out-dir>"""

import sys
from pathlib import Path

from PIL import Image, ImageChops

py, rs, out = (Path(arg) for arg in sys.argv[1:4])
out.mkdir(parents=True, exist_ok=True)
for left_path in sorted(py.glob("*.png")):
    right_path = rs / left_path.name
    if not right_path.exists():
        continue
    left = Image.open(left_path).convert("RGB")
    right = Image.open(right_path).convert("RGB")
    # The card is what differs from the backdrop in the corner; its shadow fades out a little way round it.
    ground = Image.new("RGB", right.size, right.getpixel((0, 0)))
    mask = ImageChops.difference(right, ground).convert("L").point(lambda value: 255 if value > 40 else 0)
    box = mask.getbbox()
    if box:
        right = right.crop(box)
    gap = 24
    pair = Image.new("RGB", (left.width + gap + right.width, max(left.height, right.height)), "#9a9a9a")
    pair.paste(left, (0, 0))
    pair.paste(right, (left.width + gap, 0))
    pair.save(out / left_path.name)
    print(left_path.name, left.size, right.size)
