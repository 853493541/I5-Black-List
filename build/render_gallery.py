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
    window.tabs.setCurrentIndex(window.history_tab)
    snap("records_empty_900")
    window.tabs.setCurrentIndex(window.blacklist_tab)
    snap("blacklist_empty_900")

    store = window.store
    store.player_name = "阿强"
    store.add("霁玥吉尔曼", "开局就炸房，还骂人", tags=("炸房", "贴脸"))
    store.add("小猫爆锤大王", tags=("挂机",))
    store.add("gffdsd", "很长的原因文字" * 5, tags=("场外", "不尊重底牌", "炸房", "贴脸"))
    store.add_scan([{"seat": i + 1, "name": n, "unclear": not n} for i, n in enumerate(NAMES)], 1.2)
    window._show_list()
    window._reload_history()
    if hasattr(window, "profile_chip"):
        window.player_edit.setText(store.player_name)
        window.profile_chip.set_name(store.player_name)

    for size in ((900, 560), (1400, 900)):
        window.resize(*size)
        window.tabs.setCurrentIndex(window.history_tab)
        snap(f"records_{size[0]}")
        window.tabs.setCurrentIndex(window.blacklist_tab)
        snap(f"blacklist_{size[0]}")
        window.tabs.setCurrentIndex(window.settings_tab)
        snap(f"settings_{size[0]}")
    window.resize(900, 560)
    window.tabs.setCurrentIndex(window.blacklist_tab)
    say = getattr(window, "_say", None)
    if say is not None:
        say("已添加 3 人", undo=lambda: None)
    toast = getattr(window, "toast", None)
    if toast is not None:
        toast._anim.stop()
        toast._fade.setOpacity(1.0)
    snap("blacklist_notice")
    if toast is not None:
        toast.hide()
    window._hover_blacklist_row(1, 0)
    snap("blacklist_hover")
    window._clear_blacklist_hover()
    if hasattr(window, "tag_list"):
        window.tag_list.setCurrentRow(1)
        window._hover_tag_row(2)
        snap("blacklist_tag_picked")
        window._hover_tag_row(-1)
        window.tag_list.setCurrentRow(0)
    from PySide6.QtCore import QPoint

    window.detail_tip.show_reason("1" * 120 + "\n第二行：很长的原因文字" * 3, QPoint(40, 40))
    snap("reason_tip", window.detail_tip)
    window.detail_tip.hide()
    _focus_scene(app, window, snap)
    window.tabs.setCurrentIndex(window.history_tab)
    window._hover_history_cell(1, 0)
    snap("records_hover")
    window._clear_history_hover()
    window.tabs.setCurrentIndex(window.blacklist_tab)
    window._on_worker(("glance", "err", ui.OcrUnavailable("识别模型没有就绪，请重新解压完整的安装包。")))
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

    _header_scenes(window, snap)
    _setup_scenes(app, window, snap)
    _kit_scenes(window, snap)
    _contact_sheet(out, args.label, shots)
    print(f"{len(shots)} pictures in {out}")
    os._exit(0)


def _focus_scene(app, window, snap) -> None:  # noqa: ANN001
    """Keyboard focus rings, as Tab would leave them."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QPushButton

    window.activateWindow()
    window.tabs.setCurrentIndex(window.blacklist_tab)
    for button in window.findChildren(QPushButton):
        if button.text() == "添加" and button.isVisible():
            button.setFocus(Qt.FocusReason.TabFocusReason)
            break
    snap("focus_primary")
    window._tab_buttons[window.settings_tab].setFocus(Qt.FocusReason.TabFocusReason)
    snap("focus_tab")
    window.tabs.setCurrentIndex(window.settings_tab)
    window.theme_buttons["绿色"].setFocus(Qt.FocusReason.TabFocusReason)
    snap("focus_swatch")
    window.picture_button.setFocus(Qt.FocusReason.TabFocusReason)
    snap("focus_secondary")
    window.setFocus()


def _header_scenes(window, snap) -> None:  # noqa: ANN001
    """The header's right end: 手动检查 with its key cap, the pill under the pointer, and the name box."""
    chip = getattr(window, "status_chip", None)
    if chip is None:
        return
    header = chip.parentWidget().parentWidget()
    window._set_result("手动检查", "watchOff", "idle")
    snap("header_manual", header)
    chip._hover = True
    snap("header_hover", header)
    chip._hover = False
    window._sync_watch_idle()
    window._open_name_box()
    snap("name_box", window.name_box)
    window.name_box.hide()


def _setup_scenes(app, window, snap) -> None:  # noqa: ANN001
    """The environment check card: running, confirmed, and failed."""
    from blacklist_detect.ui_setup import SetupCheck

    window.tabs.setCurrentIndex(window.history_tab)
    setup = SetupCheck(window.centralWidget())
    setup.start()
    setup.step(0, "ok")
    setup.step(1, "run")
    setup._value = 0.5
    setup.bar.setValue(500)
    snap("setup_running")
    setup.step(1, "ok")
    setup.step(2, "ok", "12/12")
    setup.succeed()
    setup._value = 1.0
    setup.bar.setValue(1000)
    snap("setup_ok")
    setup.start()
    setup.step(0, "ok")
    setup.fail(1, "本地 PaddleOCR 中文模型没有就绪。")
    setup.bar.setValue(400)
    snap("setup_failed")
    setup.hide()


def _kit_scenes(window, snap) -> None:  # noqa: ANN001
    """The standard controls on their own, once the kit exists."""
    try:
        from blacklist_detect import ui_kit
        from blacklist_detect.ui_icons import DRAWINGS
    except ImportError:
        return
    from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

    from blacklist_detect.ui_theme import _window_style, chinese_family

    board = QWidget()
    board.setObjectName("root")
    board.setStyleSheet(_window_style(chinese_family()))
    board.resize(760, 640)
    column = QVBoxLayout(board)
    column.setContentsMargins(24, 24, 24, 24)
    column.setSpacing(16)
    row = QHBoxLayout()
    row.addWidget(ui_kit.Switch(True))
    row.addWidget(ui_kit.Switch(False))
    row.addWidget(ui_kit.SegmentedControl([("light", "浅色"), ("dark", "深色"), ("system", "跟随系统")], "dark"))
    for name in ("add", "edit", "delete", "more"):
        row.addWidget(ui_kit.IconButton(name, name))
    primary = QPushButton("添加")
    primary.setObjectName("primary")
    row.addWidget(primary)
    row.addWidget(QPushButton("批量添加"))
    danger = QPushButton("清空列表")
    danger.setObjectName("danger")
    row.addWidget(danger)
    row.addStretch(1)
    column.addLayout(row)
    icons = QHBoxLayout()
    for name in DRAWINGS:
        icons.addWidget(ui_kit.IconButton(name, name, tone="text"))
    icons.addStretch(1)
    column.addLayout(icons)
    section = ui_kit.SettingsSection("检查", 72)
    section.add_row("自动检查", ui_kit.Switch(True), hint="进入「推演成功」大厅时自动检查。")
    section.add_row("开机启动", ui_kit.Switch(False))
    column.addWidget(section)
    empty = ui_kit.EmptyState("records", "还没有记录", "进入「推演成功」大厅时会自动检查，并记在这里。")
    empty.add_action(QPushButton("测试一下"))
    column.addWidget(empty, 1)
    toast = ui_kit.Toast(board)
    board.show()
    toast.show_message("已删除「霁玥吉尔曼」", "撤销", lambda: None, ms=60000)
    toast._fade.setOpacity(1.0)
    snap("kit", board)
    board.close()
    dialog = ui_kit.ConfirmDialog(window, "清空列表？", "将删除黑名单里的全部 3 个名字。", "清空", danger=True)
    dialog.show()
    snap("kit_confirm", dialog)
    dialog.close()


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
