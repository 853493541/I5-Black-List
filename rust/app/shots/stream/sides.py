"""Side-by-side pictures of the stream UI: Python (tools/ui_shots.py --scale 150) left, Rust right.

    python rust/app/shots/stream/sides.py <ui_shots out>/150-normal <STREAM_SHOTS_DIR>
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

python, rust = Path(sys.argv[1]), Path(sys.argv[2])
here = Path(__file__).parent
# (picture, Python shot, crop at 150 %, Rust picture)
PAIRS = [
    ("panel-behind", "10_header_检查_直播模式.png", (440, 259, 1106, 343), "slint-panel-behind-light.png"),
    ("panel-off", "09_header_检查.png", (440, 259, 1106, 343), "slint-panel-off-light.png"),
    ("guide", "25_dlg_直播模式说明.png", (138, 77, 1214, 746), "slint-guide-light.png"),
]
for name, shot, box, mine in PAIRS:
    left = Image.open(python / shot).convert("RGB").crop(box)
    right = Image.open(rust / mine).convert("RGB")
    gap = 24
    out = Image.new("RGB", (left.width + gap + right.width, max(left.height, right.height) + 28), "#b8b8b8")
    out.paste(left, (0, 28))
    out.paste(right, (left.width + gap, 28))
    draw = ImageDraw.Draw(out)
    draw.text((4, 6), "Python", fill="black")
    draw.text((left.width + gap + 4, 6), "Rust", fill="black")
    out.save(here / f"{name}.png")
    print("wrote", name)
