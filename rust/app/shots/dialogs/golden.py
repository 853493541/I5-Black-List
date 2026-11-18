"""Golden data for the Rust dialogs, written by the Python app's own code: rust/app/src/dialogs/golden.tsv.

    APPDATA=<tmp> HOME=<tmp> QT_QPA_PLATFORM=offscreen python3 rust/app/shots/dialogs/golden.py

One case per line, tab-separated: kind, then its inputs, then what Python gives.
"""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])

from blacklist_detect.match import fold  # noqa: E402
from blacklist_detect.ui_dialogs import AddNameDialog  # noqa: E402
from blacklist_detect.ui_sound_trim import Waveform, clock, peaks  # noqa: E402
from blacklist_detect.ui_widgets import masked_name  # noqa: E402

lines: list[str] = []
TAKEN = ("示例坏人",)
for typed in ("", "   ", "示例坏人", "示例坏人 ", "心动小鹿", "★☆", "abc", "【】", "ABC"):
    dialog = AddNameDialog(typed, taken={fold(name) for name in TAKEN})
    dialog._accept()
    lines.append("\t".join(("name", typed, dialog.name_error.text())))
    dialog.close()
for name in ("", "示", "示例", "心动小鹿", "ab c"):
    lines.append("\t".join(("mask", name, masked_name(name))))
for seconds in (0.0, 0.04, 0.05, 0.15, 12.34, 59.96, 61.0, 600.0, -1.0):
    lines.append("\t".join(("clock", repr(seconds), clock(seconds))))
rng = np.random.default_rng(7)
for count, columns in ((10, 3), (7, 7), (5, 9), (1000, 544)):
    samples = rng.integers(-32768, 32767, count, dtype=np.int16)
    found = peaks(samples, columns)
    lines.append("\t".join(("peaks", " ".join(map(str, samples)), str(columns), " ".join(str(int(v)) for v in found))))
song = np.zeros(int(20 * 44100), dtype=np.int16)
wave = Waveform(song, 44100)
for start, length in ((3.0, 4.0), (19.0, 5.0), (-1.0, 0.1), (2.0, 9.0), (7.25, 0.5)):
    wave.set_selection(start, length)
    a, b = wave.selection()
    lines.append("\t".join(("select", repr(start), repr(length), repr(a), repr(b))))
wave.set_selection(4.0, 2.0)
for x in (0.0, 8.0, 115.0, 120.0, 122.0, 150.0, 170.0, 173.0, 178.0, 300.0, 560.0):
    lines.append("\t".join(("part", repr(x), wave._part(x) or "seek", repr(wave.time_at(x)), repr(wave.x_of(x / 28)))))
out = ROOT / "rust" / "app" / "src" / "dialogs" / "golden.tsv"
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(len(lines), "cases in", out)
