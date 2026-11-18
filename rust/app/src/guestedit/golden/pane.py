"""Golden data for pane.rs: ui_guest_scenes.ScenePane driven through clicks, what each step leaves.

Run from the checkout's root, Qt offscreen, in a data folder of its own:
QT_QPA_PLATFORM=offscreen APPDATA=<tmp> python rust/app/src/guestedit/golden/pane.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])
from blacklist_detect.model import Scenes  # noqa: E402
from blacklist_detect.ui_guest_scenes import ScenePane  # noqa: E402

STARTS = {
    "off": Scenes(),
    "random": Scenes(random=True),
    "two": Scenes(("fluffy", "stars")),
    "old": Scenes(("champagne", "gone")),
    "gone": Scenes(("gone",)),
}
RUNS = [
    [],
    ["play"],
    ["play", "play"],
    ["tick:stars"],
    ["tick:random"],
    ["tick:stars", "tick:ice"],
    ["tick:stars", "tick:stars"],
    ["tick:stars", "tick:random"],
    ["tick:random", "tick:lyre", "play", "play"],
    ["play", "tick:cyber", "tick:angel", "tick:cyber"],
    ["tick:fluffy", "tick:stars", "play", "tick:ice"],
]


def state(pane: ScenePane) -> dict:
    value = pane.value()
    return {
        "playing": pane.play_box.isChecked(),
        "ticked": [key for key, button in pane.buttons.items() if button.chosen],
        "value": {"keys": list(value.keys), "random": value.random},
        "changed": pane.has_changes(),
    }


def joined(keys) -> str:
    return ",".join(keys)


# One case a line, fields split by |: start keys, start random, the clicks, the row highlighted, then at the end:
# 播放场景, the boxes ticked (随机 too, in the list's order), the value's keys and random, and whether it changed.
lines = []
for scenes in STARTS.values():
    for run in RUNS:
        pane = ScenePane(scenes)
        for step in run:
            if step == "play":
                pane.play_box.click()
            else:
                button = pane.buttons[step.split(":")[1]]
                button.set_chosen(not button.chosen)
                button.chose.emit(button.chosen)
        end = state(pane)
        value = end["value"]
        fields = [joined(scenes.keys), scenes.random, joined(run), pane.key, end["playing"], joined(end["ticked"]),
                  joined(value["keys"]), value["random"], end["changed"]]
        lines.append("|".join(str(field).lower() if isinstance(field, bool) else field for field in fields))
        pane.stop()
out = Path(__file__).with_name("pane.txt")
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(lines)} cases in {out}")
