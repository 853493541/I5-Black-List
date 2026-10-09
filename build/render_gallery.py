"""Draw every screen and state of the app to PNG, plus one contact sheet.

    python build/render_gallery.py before
    python build/render_gallery.py after --appearance dark

Pictures land in dist/gallery/<label>/. The sheet (<label>.png) puts them side by
side, so a design change can be compared before and after. It uses a throwaway
settings folder, so the real list and settings are never touched.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

NAMES = ["小猫爆锤...", "霁玥吉尔曼", "路人甲", "", "阿强", "丙丙", "gffdsd", "丁丁", "", "戊", "己己", "庚"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("label", help="folder name under dist/gallery, for example before or after")
    parser.add_argument("--appearance", default="", help="light, dark, or system, when the app supports it")
    args = parser.parse_args()

    out = REPO / "dist" / "gallery" / args.label
    out.mkdir(parents=True, exist_ok=True)
    os.environ["APPDATA"] = tempfile.mkdtemp()
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")

    from PySide6.QtWidgets import QApplication

    from blacklist_detect import ui
    from blacklist_detect.pipeline import CheckResult, Hit, NameSlot

    app = QApplication([])
    window_store = None
    if args.appearance:
        from blacklist_detect.storage import Store

        window_store = Store()
        if hasattr(window_store, "appearance"):
            window_store.appearance = args.appearance
            window_store.save_settings()
    app.setFont(ui.chinese_font())
    ui._apply_theme(app)
    window = ui.MainWindow()
    window._watch_timer.stop()
    shots: list[tuple[str, Path]] = []

    def settle() -> None:
        for _ in range(10):
            app.processEvents()

    def snap(name: str, widget=None) -> None:
        settle()
        path = out / f"{len(shots) + 1:02d}_{name}.png"
        (widget or window).grab().save(str(path))
        shots.append((name, path))

    window.resize(900, 560)
    window.show()
    window.tabs.setCurrentIndex(0)
    snap("records_empty_900")
    window.tabs.setCurrentIndex(1)
    snap("blacklist_empty_900")

    store = window.store
    store.player_name = "阿强"
    store.add("霁玥吉尔曼", "开局就炸房，还骂人", tags=("炸房", "贴脸"))
    store.add("小猫爆锤大王", tags=("挂机",))
    store.add("gffdsd", "很长的原因文字" * 5, tags=("场外", "不尊重底牌", "炸房", "贴脸"))
    store.add_scan([{"seat": i + 1, "name": n, "unclear": not n} for i, n in enumerate(NAMES)], 1.2)
    window._show_list()
    window._reload_history()

    for size in ((900, 560), (1400, 900)):
        window.resize(*size)
        window.tabs.setCurrentIndex(0)
        snap(f"records_{size[0]}")
        window.tabs.setCurrentIndex(1)
        snap(f"blacklist_{size[0]}")
        window.tabs.setCurrentIndex(2)
        snap(f"settings_{size[0]}")
    window.resize(900, 560)
    window.tabs.setCurrentIndex(1)
    say = getattr(window, "_say", None)
    if say is not None:
        say("已添加 3 人", undo=lambda: None)
    snap("blacklist_notice")
    window._on_worker(("glance", "err", ui.OcrUnavailable("本地 PaddleOCR 中文模型没有就绪。")))
    snap("status_error")

    dialogs = [
        ("dialog_add", lambda: ui.AddNameDialog(catalog=store.tag_catalog(), parent=window)),
        (
            "dialog_edit",
            lambda: ui.AddNameDialog(
                "霁玥吉尔曼", ("炸房",), "开局就炸房", title="修改", allow_delete=True,
                catalog=store.tag_catalog(), parent=window,
            ),
        ),
        ("dialog_import", lambda: ui.BatchAddDialog(store.tag_catalog(), parent=window)),
        ("dialog_tag", lambda: ui.TagEditDialog("炸房", store.tag_catalog(), parent=window)),
        ("dialog_guide", lambda: ui.GuideDialog(window)),
    ]
    slots = [NameSlot(i, (0, 0, 1, 1), n, n, False, 0.9, not n) for i, n in enumerate(NAMES)]
    hits = [Hit(1, "霁玥吉尔曼", "霁玥吉尔曼", "", False, ""), Hit(6, "gffdsd", "gffdsd", "", False, "")]
    dialogs.append(
        ("dialog_picture", lambda: ui.PictureResultDialog("识别测试", result=CheckResult(True, "", names=slots, hits=hits), parent=window))
    )
    for name, make in dialogs:
        dialog = make()
        dialog.show()
        snap(name, dialog)
        dialog.close()

    panel = window.panel
    panel.resize(260, 64)
    panel.set_mode("clear", "没有黑名单\n1 人没看清")
    snap("overlay_clear", panel)
    panel.set_mode("hit", "")
    snap("overlay_hit", panel)
    window.hit_card.set_people([("霁玥吉尔曼", ("炸房", "贴脸")), ("gffdsd", ("挂机",))], 64)
    snap("overlay_hit_card", window.hit_card)

    _contact_sheet(out, args.label, shots)
    print(f"{len(shots)} pictures in {out}")
    os._exit(0)


def _contact_sheet(folder: Path, label: str, shots: list[tuple[str, Path]]) -> None:
    from PIL import Image, ImageDraw

    width = 760
    tiles = []
    for name, path in shots:
        image = Image.open(path).convert("RGB")
        scale = min(1.0, width / image.width)
        image = image.resize((round(image.width * scale), round(image.height * scale)))
        tiles.append((name, image))
    columns = 2
    rows: list[list[tuple[str, Image.Image]]] = [tiles[i : i + columns] for i in range(0, len(tiles), columns)]
    caption = 28
    height = sum(max(t[1].height for t in row) + caption + 16 for row in rows)
    sheet = Image.new("RGB", (columns * (width + 16) + 16, height + 16), "#808890")
    draw = ImageDraw.Draw(sheet)
    y = 16
    for row in rows:
        x = 16
        for name, image in row:
            draw.text((x, y + 6), name, fill="#ffffff")
            sheet.paste(image, (x, y + caption))
            x += width + 16
        y += max(t[1].height for t in row) + caption + 16
    sheet.save(folder.parent / f"{label}.png")


if __name__ == "__main__":
    sys.exit(main())
