"""Golden data for rust/overlay: the marks ui_overlay.py draws over the game, as the Python app paints them.

Writes rust/overlay/golden/: one PNG per mark (alpha kept) and marks.json with each mark's size and the
cards' row geometry, for the Rust crate's parity tests. Offscreen Qt at 96 dpi, ratio 1, in a data folder
of its own, silent. Made-up names only.

    QT_QPA_PLATFORM=offscreen python tools/rust_golden_overlay.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "rust" / "overlay" / "golden"

# Cover sizes: the full-screen one (FULL_COVER) and the one round the sample lobby's button in a 1152x648 game.
COVERS = {"full": (176, 82), "small": (170, 51)}
HITS = [("示例坏人", ("炸房",)), ("路过的捣蛋鬼", ("场外", "挂机"))]
LIKES = [("心动小鹿", ()), ("一起开黑的朋友", ())]


def main() -> None:
    data = Path(tempfile.mkdtemp(prefix="overlay_golden_"))
    os.environ["APPDATA"] = str(data)
    os.environ["HOME"] = str(data)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.pop("BLACKLIST_DETECT_SOUND", None)
    sys.path.insert(0, str(ROOT))
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    from blacklist_detect import ui_overlay as ov
    from blacklist_detect.ui_theme import chinese_family

    OUT.mkdir(parents=True, exist_ok=True)
    meta: dict = {"family": chinese_family(), "marks": {}}

    def save(widget, name: str, extra: dict | None = None) -> None:  # noqa: ANN001
        widget.move(-3000, -3000)
        widget.show()
        app.processEvents()
        widget.grab().toImage().save(str(OUT / f"{name}.png"))
        meta["marks"][name] = {"w": widget.width(), "h": widget.height(), **(extra or {})}
        widget.hide()

    for size, (width, height) in COVERS.items():
        for mode in ("hit", "clear", "liked", "both", "checking"):
            for key in ("lace", "ice", "stars") if mode in ("liked", "both") else ("lace",):
                panel = ov.LobbyPanel()
                panel.set_look(ov.LOOKS[key])
                panel.setFixedSize(width + 2 * ov._GLOW, height + 2 * ov._GLOW)
                panel.set_mode(mode, "检查中" if mode == "checking" else "")
                panel._shine.stop()
                panel._phase = 0.3
                save(panel, f"ring_{mode}_{key}_{size}")
        for heart, key in ((False, "lace"), (True, "lace"), (True, "ice"), (True, "stars")):
            mark = ov.ClearMark()
            mark.set_look(ov.LOOKS[key])
            mark.set_heart(heart)
            mark.set_size(height)
            save(mark, f"badge_{'heart' if heart else 'check'}_{key}_{size}")
        hit = ov.HitCard()
        hit.set_people(HITS, height)
        save(hit, f"card_hit_{size}", {"rows": rows(hit), "scale": hit.scale})
        for key in ("lace", "ice", "stars"):
            like = ov.LikeCard()
            like.set_look(ov.LOOKS[key])
            like.set_people(LIKES, height)
            save(like, f"card_like_{key}_{size}", {"rows": rows(like), "scale": like.scale, "top": like.top})
    (OUT / "marks.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(meta['marks'])} marks in {OUT} ({meta['family']})")


def rows(card) -> list:  # noqa: ANN001
    """Each name row's children: what they are and where, in the card's own pixels."""
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QLabel

    out = []
    for i in range(card.rows.count()):
        person = card.rows.itemAt(i).widget()
        for child in person.findChildren(QLabel) + [w for w in person.children() if type(w).__name__ == "TagPill"]:
            top_left = child.mapTo(card, QPoint(0, 0))
            kind = child.objectName() or type(child).__name__
            text = child.text() if hasattr(child, "text") and callable(child.text) else ""
            out.append({"row": i, "kind": kind, "text": text, "x": top_left.x(), "y": top_left.y(), "w": child.width(), "h": child.height()})
    return out


if __name__ == "__main__":
    main()
