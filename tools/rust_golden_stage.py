"""Golden data for the Rust stage crate (rust/stage): where a 嘉宾 scene plays and which one.

Writes rust/stage/tests/golden/stage.json from the Python app's own code: love_scenes.choose over seeded
generators, LoveBorder.pick / heard / draw_again in a row, the gap play() leaves round the button, Stage.unit,
names and heart, sample_stage, and each scene's DURATION and whether it warms first.

Run from the root, in a data folder of its own and silent:
    APPDATA=$(mktemp -d) HOME=$(mktemp -d) QT_QPA_PLATFORM=offscreen PYTHONPATH=. python tools/rust_golden_stage.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF
from PySide6.QtWidgets import QApplication

from blacklist_detect import love_scenes
from blacklist_detect.love_scenes import Stage, sample_stage
from blacklist_detect.ui_love import LoveBorder

OUT = Path(__file__).resolve().parent.parent / "rust" / "stage" / "tests" / "golden" / "stage.json"

CHOICES: list[str | tuple[str, ...]] = [
    "random",
    "off",
    "stars",
    "lace",
    "champagne",
    "chiffon",
    ("stars",),
    ("stars", "ice"),
    ("stars", "ice", "claw", "lyre"),
    ("champagne", "angel", "classic"),
    ("chiffon", "ribbon"),
    (),
]
LASTS = ["", "stars", "ice", "classic", "angel"]


def rect(r: QRectF) -> list[float]:
    return [r.x(), r.y(), r.width(), r.height()]


def choose_cases() -> list[dict]:
    cases = []
    for seed in (0, 7, 31, 2026):
        for choice in CHOICES:
            for last in LASTS:
                rng = random.Random(seed)
                picks = [love_scenes.choose(choice, last, rng) for _ in range(6)]
                cases.append({"seed": seed, "choice": choice if isinstance(choice, str) else list(choice), "last": last, "picks": picks})
    return cases


def picker_runs() -> list[dict]:
    """LoveBorder's own pick state: ops applied in order, what each pick() gave."""
    runs = []
    scripts = [
        [("choice", "random"), ("pick",), ("pick",), ("draw_again",), ("pick",), ("heard", "stars"), ("draw_again",), ("pick",)],
        [("choice", ["stars", "ice"]), ("pick",), ("heard", "stars"), ("draw_again",), ("pick",), ("heard", "ice"), ("draw_again",), ("pick",)],
        [("choice", "off"), ("pick",), ("choice", "lace"), ("pick",), ("choice", "random"), ("pick",), ("pick",)],
        [("choice", "random")] + [op for _ in range(10) for op in (("pick",), ("play",), ("draw_again",))],
    ]
    for seed in (1, 5, 99):
        for script in scripts:
            border = LoveBorder(rng=random.Random(seed))
            got = []
            for op in script:
                if op[0] == "choice":
                    border.choice = op[1] if isinstance(op[1], str) else tuple(op[1])
                elif op[0] == "pick":
                    got.append(border.pick())
                elif op[0] == "heard":
                    border.heard(op[1])
                elif op[0] == "draw_again":
                    border.draw_again()
                elif op[0] == "play":
                    # play()'s own bookkeeping without a window: the scene played is the last one.
                    scene = border.pick()
                    if scene:
                        border.scene = border._last = scene
            runs.append({"seed": seed, "ops": [list(op) for op in script], "picks": got})
            border.deleteLater()
    return runs


def gap_cases() -> list[dict]:
    cases = []
    for area, keep in [
        ((0, 0, 1920, 1080), (812, 970, 300, 90)),
        ((100, 50, 1635, 848), (649, 799, 556, 94)),
        ((-1920, 0, 1920, 1080), (-1100, 960, 280, 100)),
        ((0, 0, 2560, 1440), (1140, 1290, 400, 120)),
    ]:
        a, k = QRect(*area), QRect(*keep)
        clear = QRectF(k.translated(-a.topLeft()))
        gap = QRectF(clear.left() - 28, clear.top() - 30, clear.width() + 56, a.height() - clear.top() + 30)
        badge = QPoint(k.right() + 20, k.center().y())
        origin = QPointF(a.topLeft())
        seats = (QRectF(a.left() + 200.5, a.top() + 400, 150, 30), QRectF(a.left() + 900, a.top() + 650.25, 120, 28))
        stage = Stage(a.width(), a.height(), gap, QPointF(badge) - origin, tuple(s.translated(-origin) for s in seats))
        bare = Stage(a.width(), a.height(), gap)
        cases.append({
            "area": list(area), "keep": list(keep), "badge": [badge.x(), badge.y()],
            "seats": [rect(s) for s in seats], "gap": rect(gap), "unit": stage.unit(),
            "heart": [stage.heart().x(), stage.heart().y()], "bare_heart": [bare.heart().x(), bare.heart().y()],
            "names": [rect(r) for r in stage.names()], "bare_names": [rect(r) for r in bare.names()],
        })
    return cases


def main() -> None:
    _app = QApplication.instance() or QApplication([])
    scenes = []
    for key, name in love_scenes.SCENES:
        module = love_scenes.load(key)
        scenes.append({"key": key, "name": name, "duration": float(module.DURATION), "warm": hasattr(module, "warm"),
                       "max_ratio": getattr(module, "MAX_RATIO", None)})
    samples = []
    for w, h in [(1635.0, 848.0), (1920.0, 1080.0), (1280.0, 720.0)]:
        s = sample_stage(w, h)
        samples.append({"size": [w, h], "gap": rect(s.gap), "badge": [s.badge.x(), s.badge.y()], "unit": s.unit()})
    data = {"scenes": scenes, "replaced": love_scenes.REPLACED, "choose": choose_cases(), "picker": picker_runs(),
            "gaps": gap_cases(), "samples": samples, "tick_ms": 33, "ready_s": 0.02}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT}: {len(data['choose'])} choose cases, {len(data['picker'])} picker runs, {len(data['gaps'])} gaps")


if __name__ == "__main__":
    main()
