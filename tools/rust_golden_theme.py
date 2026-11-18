"""Write ui_theme.py's tokens as golden JSON for the Rust port (rust/app/src/kit/golden_theme.json).

Every accent's palette in light and dark, the type scale (points and the pixels they make at 100 %), and the spacing.
Run offscreen with a data folder of its own: QT_QPA_PLATFORM=offscreen python tools/rust_golden_theme.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from blacklist_detect import ui_theme  # noqa: E402

TYPE = ("BODY_PT", "SMALL_PT", "SECTION_PT", "TITLE_PT", "DIALOG_TITLE_PT", "OVERLAY_PT")
SPACING = ("PAD", "GAP", "DIALOG_PAD", "CONTROL_H", "ROW_H", "RADIUS", "CARD_RADIUS")


def golden() -> dict:
    palettes = {}
    for name in ui_theme._LIGHT:
        for dark in (False, True):
            colors = ui_theme._palette(name, dark)
            colors.pop("scheme")
            palettes[f"{name}/{'dark' if dark else 'light'}"] = colors
    return {
        "accents": list(ui_theme._LIGHT),
        "palettes": palettes,
        "type_px": {key.removesuffix("_PT").lower(): getattr(ui_theme, key) * 4 / 3 for key in TYPE},
        "spacing": {key.lower(): getattr(ui_theme, key) for key in SPACING},
    }


def main() -> None:
    out = ROOT / "rust" / "app" / "src" / "kit" / "golden_theme.json"
    out.write_text(json.dumps(golden(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
