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

    def snap(name: str, widget=None, picture=None) -> None:
        settle()
        path = out / f"{len(shots) + 1:02d}_{name}.png"
        (picture if picture is not None else (widget or window).grab()).save(str(path))
        shots.append((name, path))

    def over_window(dialog):  # noqa: ANN001, ANN202
        """The window as it looks with the dialog open over it: dimmed, the card on top."""
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QPainter

        settle()
        base = window.grab()
        painter = QPainter(base)
        painter.drawPixmap(dialog.pos() - window.mapToGlobal(QPoint(0, 0)), dialog.grab())
        painter.end()
        return base

    window.resize(900, 560)
    window.show()
    window.tabs.setCurrentIndex(window.history_tab)
    snap("records_empty_900")
    window.tabs.setCurrentIndex(window.blacklist_tab)
    snap("blacklist_empty_900")
    if hasattr(window, "likes_tab"):
        window.tabs.setCurrentIndex(window.likes_tab)
        snap("likes_empty_900")

    store = window.store
    store.player_name = "阿强"
    store.add("霁玥吉尔曼", "开局就炸房，还骂人", tags=("炸房", "贴脸"))
    store.add("小猫爆锤大王", tags=("挂机",))
    store.add("gffdsd", "很长的原因文字" * 5, tags=("场外", "不尊重底牌", "炸房", "贴脸"))
    if hasattr(store, "add_like"):
        store.add_like("庚", "", "")
        store.add_like("丙丙的猫猫头", "猫猫", "救人很稳，开局就报点")
        store.add_like("戊", "", "")
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
        if hasattr(window, "likes_tab"):
            window.likes_page.refresh()
            window.tabs.setCurrentIndex(window.likes_tab)
            snap(f"likes_{size[0]}")
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
        # The boxes close when focus leaves them, so the window has to be the active one.
        window.activateWindow()
        window.raise_()
        window._edit_tag("贴脸")
        snap("blacklist_tag_edit")
        window._finish_tag_edit(keep=False)
        window._create_tag()
        snap("blacklist_tag_new")
        window._finish_tag_new(keep=False)
    from PySide6.QtCore import QPoint

    window.detail_tip.show_reason("1" * 120 + "\n第二行：很长的原因文字" * 3, QPoint(40, 40))
    snap("reason_tip", window.detail_tip)
    window.detail_tip.hide()
    _focus_scene(app, window, snap)
    window.tabs.setCurrentIndex(window.history_tab)
    window._clear_history_hover()
    window._hover_history_cell(1, 0)
    snap("records_hover")
    window._clear_history_hover()
    window.tabs.setCurrentIndex(window.blacklist_tab)
    window._on_worker(("glance", "err", ui.OcrUnavailable("识别模型未就绪，请重新解压完整的安装包。")))
    snap("status_error")

    dialogs = [
        ("dialog_add", lambda: ui.AddNameDialog(catalog=store.tag_catalog(), parent=window)),
        (
            "dialog_edit",
            lambda: ui.AddNameDialog(
                "霁玥吉尔曼", ("炸房",), "开局就炸房", title="编辑", allow_delete=True,
                catalog=store.tag_catalog(), parent=window,
            ),
        ),
        ("dialog_import_empty", lambda: ui.BatchAddDialog(store.tag_catalog(), store.entries, parent=window)),
        ("dialog_import", lambda: _import_dialog(ui, store, window)),
        ("dialog_guide", lambda: ui.GuideDialog(window)),
        ("dialog_like", lambda: _like_dialog(window)),
    ]
    slots = [NameSlot(i, (0, 0, 1, 1), n, n, False, 0.9, not n) for i, n in enumerate(NAMES)]
    hits = [Hit(1, "霁玥吉尔曼", "霁玥吉尔曼", "", False, ""), Hit(6, "gffdsd", "gffdsd", "", False, "")]
    dialogs.append(
        ("dialog_picture", lambda: ui.PictureResultDialog("识别测试", result=CheckResult(True, "", names=slots, hits=hits), parent=window))
    )
    window.resize(1100, 760)
    for name, make in dialogs:
        dialog = make()
        dialog.show()
        snap(name, picture=over_window(dialog))
        dialog.close()
    confirm = ui.ConfirmDialog(window, "清空黑名单", "黑名单里的 3 个名字会被删除。", "清空", danger=True)
    confirm.show()
    snap("dialog_confirm", picture=over_window(confirm))
    confirm.close()
    window.resize(900, 560)

    _overlay_scenes(window, snap)

    _header_scenes(window, snap)
    _update_scenes(window, snap, over_window)
    _setup_scenes(app, window, snap)
    _kit_scenes(window, snap)
    _contact_sheet(out, args.label, shots)
    print(f"{len(shots)} pictures in {out}")
    os._exit(0)


def _like_dialog(window):  # noqa: ANN001, ANN202
    from blacklist_detect.ui_likes import LikeDialog

    return LikeDialog("丙丙的猫猫头", "猫猫", "救人很稳，开局就报点", title="编辑", allow_delete=True, parent=window)


def _import_dialog(ui, store, window):  # noqa: ANN001, ANN202
    """批量导入 with a friend's list pasted in: new names, one already listed, and its title."""
    dialog = ui.BatchAddDialog(store.tag_catalog(), store.entries, parent=window)
    pasted = [
        "这游戏有这么多神人吗",
        "霁玥吉尔曼（开局就炸房，这把又炸）",
        "挖野菜养你吖（纯粹的傻逼）",
        "好知知这就来帮（好人帮狼炸房）",
        "西西zo（挂机占麦）",
        "小小丑不会输，少主薇（狼能赢的送双排顾问）",
        "翻箱震慑是北城（讲了行为狼、轨迹狼、身份撞了，还给狼弃",
        "票，弱智来着）",
        "誘之（轨迹差表水差被踩就情绪贴脸）",
    ]
    dialog.edit.setPlainText("\n".join(pasted))
    dialog._refresh()
    return dialog


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
    window.tabs.setCurrentIndex(window.history_tab)
    window.picture_button.setFocus(Qt.FocusReason.TabFocusReason)
    snap("focus_secondary")
    window.setFocus()


def _overlay_scenes(window, snap) -> None:  # noqa: ANN001
    """The marks over the reference lobby: 检查中, a hit with its card, and a clear lobby."""
    from PySide6.QtCore import QPoint, QRect, QRectF
    from PySide6.QtGui import QImage, QPainter, QPixmap

    from blacklist_detect.ui_overlay import _COVER_OUTSET, _GLOW

    lobby = QImage(str(REPO / "tests" / "fixtures" / "reference-lobby.png"))
    # 准备案件还原 in that screenshot, as the check finds it; the capture is at twice the scale.
    x0, y0, x1, y1 = 1498, 1518, 2010, 1667
    crop = QRectF(x0 - 420, y0 - 123, 1700, 300)
    button = QRect(420 // 2, 123 // 2, (x1 - x0) // 2, (y1 - y0) // 2)
    outset = _COVER_OUTSET

    def scene(mode: str, text: str, beside=None, likes=None) -> QPixmap:  # noqa: ANN001
        ratio = window.devicePixelRatioF()
        width, height = round(crop.width() / 2), round(crop.height() / 2)
        canvas = QPixmap(round(width * ratio), round(height * ratio))
        canvas.setDevicePixelRatio(ratio)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawImage(QRectF(0, 0, width, height), lobby, crop)
        panel = window.panel
        cover = button.adjusted(-outset, -outset, outset, outset)
        panel.setFixedSize(cover.width() + 2 * _GLOW, cover.height() + 2 * _GLOW)
        panel.set_mode(mode, text)
        panel._shine.stop()
        panel._glint(0.3)
        painter.drawPixmap(cover.topLeft() - QPoint(_GLOW, _GLOW), panel.grab())
        if beside is not None:
            beside.layout().activate() if beside.layout() is not None else None
            beside.resize(beside.size())
            mark = beside.grab()
            left = cover.x() + cover.width() + 16 - beside.margin
            mark_h = round(mark.height() / mark.devicePixelRatio())
            top = cover.center().y() - mark_h // 2 + 1
            card = likes.grab() if likes is not None else None
            card_h = round(card.height() / card.devicePixelRatio()) if card is not None else 0
            if card is not None:
                # The 心动 card on the left, as in the app.
                card_w = round(card.width() / card.devicePixelRatio())
                painter.drawPixmap(QPoint(cover.x() - 16 - card_w, cover.center().y() - card_h // 2 + 1), card)
            painter.drawPixmap(QPoint(left, top), mark)
        painter.end()
        return canvas

    snap("overlay_checking", picture=scene("checking", "检查中"))
    window.hit_card.set_people([("霁玥吉尔曼", ("炸房", "贴脸")), ("gffdsd", ("挂机",))], button.height())
    snap("overlay_hit", picture=scene("hit", "", window.hit_card))
    many = [("霁玥吉尔曼", ("炸房", "贴脸")), ("gffdsd", ("挂机",)), ("EluElu", ("演员",)), ("玩的很菜了", ("挂机",))]
    window.hit_card.set_people(many, button.height())
    snap("overlay_hit_many", picture=scene("hit", "", window.hit_card))
    window.clear_mark.set_size(button.height() + outset * 2)
    snap("overlay_clear", picture=scene("clear", "没有黑名单", window.clear_mark))
    like_card = getattr(window, "like_card", None)
    if like_card is not None:
        like_card.set_people([("猫猫", ()), ("阿强", ())], button.height())
        window.clear_mark.set_heart(True)
        snap("overlay_clear_likes", picture=scene("liked", "没有黑名单", window.clear_mark, like_card))
        window.clear_mark.set_heart(False)
        window.hit_card.set_people([("霁玥吉尔曼", ("炸房", "贴脸"))], button.height())
        snap("overlay_hit_likes", picture=scene("both", "", window.hit_card, like_card))
    if hasattr(window, "love"):
        # The border for two or more 心动 players, over the whole lobby, two seconds in.
        ratio = window.devicePixelRatioF()
        width, height = lobby.width() // 2, lobby.height() // 2
        canvas = QPixmap(round(width * ratio), round(height * ratio))
        canvas.setDevicePixelRatio(ratio)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawImage(QRectF(0, 0, width, height), lobby)
        keep = QRectF(x0 / 2 - 200, y0 / 2 - 10, (x1 - x0) / 2 + 300, (y1 - y0) / 2 + 20)
        gap = QRectF(keep.left() - 28, keep.top() - 30, keep.width() + 56, height - keep.top() + 30)
        window.love.paint_at(painter, 2.0, width, height, gap)
        painter.end()
        snap("overlay_love", picture=canvas)


def _header_scenes(window, snap) -> None:  # noqa: ANN001
    """The header's right end: 手动检查 with its key cap, the pill under the pointer, and the name being edited."""
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
    window.activateWindow()
    window._edit_player_name()
    snap("name_edit", header)
    window._finish_player_name(keep=False)


def _update_scenes(window, snap, over_window) -> None:  # noqa: ANN001
    """Updates, every state: the header pill, 设置 › 更新, the dialog from offer to restart, and the toast."""
    if not hasattr(window, "update_pill"):
        return
    from blacklist_detect.ui_update import UpdateDialog
    from blacklist_detect.updater import DOWNLOADS, Release

    release = Release(
        "v0.4.1",
        f"{DOWNLOADS}v0.4.1/BlackListDetect-v0.4.1-update.zip",
        "0" * 64,
        1_900_000,
        base="v0.3.0",
        notes=("心动列表支持按最近遇到排序", "修复偶尔无法识别大厅的问题"),
    )
    header = window.status_chip.parentWidget().parentWidget()
    window.resize(1000, 640)
    window.tabs.setCurrentIndex(window.settings_tab)
    snap("update_settings_idle")
    window.update_button.setEnabled(False)
    window.update_button.setText("检查中…")
    snap("update_settings_checking")
    window._update_asked = True
    window._on_update_latest()
    snap("update_settings_latest")
    window._update_asked = True
    window._on_update_failed("无法连接更新服务器，请稍后重试")
    snap("update_settings_failed")
    window._on_update_found(release)
    snap("update_settings_found")
    snap("update_header_new", header)

    def dialog_shot(name: str, prepare, base: str = "v0.3.0") -> None:  # noqa: ANN001
        shown = Release(release.version, release.url, release.sha256, release.size, base=base, notes=release.notes)
        dialog = UpdateDialog(shown, REPO, REPO / "dist", window)
        dialog._download.start = lambda *_args: None
        prepare(dialog)
        dialog.show()
        snap(name, picture=over_window(dialog))
        dialog.close()

    def downloading(dialog) -> None:  # noqa: ANN001
        dialog.action.click()
        dialog._on_progress(42, 100)

    def failed(dialog) -> None:  # noqa: ANN001
        dialog.action.click()
        dialog._on_failed("下载失败，请检查网络后重试")

    dialog_shot("update_dialog_offer", lambda dialog: None)
    dialog_shot("update_dialog_downloading", downloading)
    dialog_shot("update_dialog_failed", failed)
    dialog_shot("update_dialog_ready", lambda dialog: dialog._ready())
    dialog_shot("update_dialog_full", lambda dialog: None, base="v0.4.1")
    window.update_pill.hide()
    window._release = None
    window.update_button.setText("检查更新")
    window._update_note("")
    window.tabs.setCurrentIndex(window.history_tab)
    window._say("已更新到 v0.4.1")
    # The toast fades in over 150 ms.
    from PySide6.QtTest import QTest

    QTest.qWait(400)
    snap("update_toast")
    window.toast.hide()
    window.resize(900, 560)


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
    setup.fail(1, "识别模型未就绪，请重新解压完整的安装包。")
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
    row.addWidget(QPushButton("批量导入"))
    danger = QPushButton("清空黑名单")
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
