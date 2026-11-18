"""The Python app's dialogs as reference pictures for the Rust ones: each card grabbed alone, at 150 %, light.

Run from the checkout's root with its own data folder and no display:
    APPDATA=<tmp> HOME=<tmp> QT_QPA_PLATFORM=offscreen QT_SCALE_FACTOR=1.5 python3 rust/app/shots/dialogs/pyrefs.py <out>
Then `cargo run -p app --bin dialogs-shots -- <rust-out>` and `python3 rust/app/shots/dialogs/pair.py <out> <rust-out>`.
Made-up names only.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])

from blacklist_detect.diagnostics import FlowTest  # noqa: E402
from blacklist_detect.importing import TagSuggestion  # noqa: E402
from blacklist_detect.ui_dialogs import (  # noqa: E402
    AddNameDialog,
    BatchAddDialog,
    DisclaimerDialog,
    DisplayGuideDialog,
    FlowReportDialog,
    GuideDialog,
    StreamGuideDialog,
    TagSuggestDialog,
)
from blacklist_detect.ui_kit import ConfirmDialog  # noqa: E402
from blacklist_detect.ui_sound_trim import SoundTrimDialog  # noqa: E402

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
CATALOG = ("炸房", "贴脸", "挂机", "场外", "不尊重底牌", "送人头")
song = (np.sin(np.arange(20 * 44100) / 44100 * 2 * np.pi * 3) * np.sin(np.arange(20 * 44100) / 44100 * 2 * np.pi * 440) * 12000).astype(np.int16)
runs = [{"capture": 0.08, "find": 0.6, "read": 0.09}, {"capture": 0.07, "find": 0.04, "read": 0.06}] * 2
flow = FlowTest(size=(3840, 2160), device="gpu:0", capture=0.08, glance=0.12, glance_found=True,
                auto={"capture": 0.08, "find": 0.05, "read": 0.07}, runs=runs, right=12, cpu_busy=21.0, cpu_own=4.0)  # fmt: skip


def batch() -> BatchAddDialog:
    dialog = BatchAddDialog(CATALOG, [])
    dialog.edit.setPlainText("示例坏人（炸房，开局就退）\n路过的捣蛋鬼 场外\n心动星星")
    dialog._refresh()
    return dialog


DIALOGS = {
    "add": lambda: AddNameDialog(title="添加", catalog=CATALOG),
    "edit": lambda: AddNameDialog("路过的捣蛋鬼", ("挂机", "场外"), "场外报点，还在频道里骂人", "编辑", True, CATALOG),
    "batch": batch,
    "suggest": lambda: TagSuggestDialog(
        [TagSuggestion("开局就退", False, (0, 1)), TagSuggestion("炸房", True, (0,))],
        [("示例坏人", ("炸房",), "开局就退", -1), ("路过的捣蛋鬼", (), "开局就退，场外", -1)],
    ),
    "confirm": lambda: ConfirmDialog(None, "清空黑名单", "黑名单里的 3 人都会删掉。可以在 设置 › 恢复备份 里找回。", "清空", danger=True),
    "disclaimer": lambda: DisclaimerDialog(asking=True),
    "guide": lambda: GuideDialog(how="在「推演成功」大厅按 Alt+1 检查"),
    "display": DisplayGuideDialog,
    "stream": StreamGuideDialog,
    "flow": lambda: FlowReportDialog(flow, lambda: None),
    "trim": lambda: SoundTrimDialog(song, 44100, "心动音乐.mp3", lambda _s, _l: None, lambda: None),
}

for name, make in DIALOGS.items():
    dialog = make()
    dialog.show()
    for _ in range(5):
        app.processEvents()
    dialog.card.grab().save(str(out / f"{name}.png"))
    dialog.close()
print(len(DIALOGS), "pictures in", out)
