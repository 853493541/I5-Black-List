"""Screenshots of every page and dialog of the app, for a look at the whole UI before a release.

    .venv\\Scripts\\python.exe tools\\ui_shots.py <out dir> [--scale 100 150 200] [--dark]
                                                 [--size 900 560] [--data normal|empty|stress] [--stream]

Each scale is a run of its own (Qt's scale is set before it starts), into <out dir>\\<scale>[-dark]-<data>.
The app runs with made-up names in a data folder of its own: nothing of the user's is read or written.
A dialog the app opens with exec() or open() is shown without waiting, photographed and closed, so
the app's own code builds every one exactly as a player sees it. 截图检查's result reads the
sample lobby for real, so the recognition models must be on this PC.

    normal   five 黑名单 (one with a long name and reason), three 嘉宾, two records
    empty    nothing: the empty pages
    stress   128 黑名单, 15 嘉宾, 40 records over several days, a long player name and hotkey, 自动检查
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEATS = ["小林同学", "白日梦想家", "路过的猫", "一只团子", "夏天的风", "心动小鹿", "晚风吹过", "摸鱼大师", "示例坏人", "心动星星", "柠檬汽水", "棉花糖"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--scale", type=int, nargs="+", default=[100, 150, 200], help="Windows scale, in percent")
    parser.add_argument("--dark", action="store_true")
    parser.add_argument("--size", type=int, nargs=2, default=[900, 560], metavar=("W", "H"), help="the window, in logical pixels")
    parser.add_argument("--data", choices=("normal", "empty", "stress"), default="normal")
    parser.add_argument("--stream", action="store_true", help="直播模式 on: 黑名单 names masked")
    parser.add_argument("--one", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.one is None:
        for scale in args.scale:
            command = [sys.executable, __file__, str(args.out), "--one", str(scale), "--size", *map(str, args.size), "--data", args.data]
            command += ["--dark"] * args.dark + ["--stream"] * args.stream
            done = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
            print(done.stdout.strip() or f"{scale}%: no output\n{done.stderr[-2000:]}")
        return
    shoot(args)


def shoot(args) -> None:  # noqa: ANN001
    out = args.out / f"{args.one}{'-dark' if args.dark else ''}-{args.data}"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    data = Path(tempfile.mkdtemp(prefix="ui_shots_"))
    os.environ.update({"APPDATA": str(data), "XDG_CONFIG_HOME": str(data), "USERNAME": "ui_shots"})
    # Qt scales on top of the screen's own: this run looks like a screen at args.one percent.
    os.environ["QT_SCALE_FACTOR"] = str(args.one / _screen_percent())
    sys.path.insert(0, str(ROOT))
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QDialog

    from blacklist_detect import __version__, ui
    from blacklist_detect.ui_kit import Modal

    _seed(data / "BlackListDetect", args, __version__)
    shots: list[str] = []
    label = {"name": "dialog"}

    def settle(seconds: float = 0.25) -> None:
        end = time.time() + seconds
        while time.time() < end:
            app.processEvents()
            time.sleep(0.02)

    def save(widget, name: str) -> None:  # noqa: ANN001
        settle()
        path = out / f"{len(shots):02d}_{name}.png"
        widget.grab().save(str(path))
        shots.append(path.name)

    def photograph(dialog, *_args):  # noqa: ANN001, ANN202
        dialog.show()
        save(dialog, label["name"])
        dialog.close()
        return QDialog.Rejected

    Modal.exec = photograph
    Modal.open = photograph

    def step(name: str, action) -> None:  # noqa: ANN001
        label["name"] = name
        try:
            action()
        except Exception:  # noqa: BLE001
            print("FAILED", name)
            traceback.print_exc(limit=3)
        settle(0.15)

    window = ui.MainWindow()
    window.resize(*args.size)
    window.show()
    settle(0.8)
    for index, name in enumerate(("记录", "黑名单", "嘉宾", "设置")):
        window.tabs.setCurrentIndex(index)
        save(window, f"page_{name}")
    window.tabs.setCurrentIndex(0)
    step("header_检查", lambda: (window.check_panel.toggle(), save(window, "header_检查"), window.check_panel.close_panel()))

    def offered() -> None:
        from blacklist_detect import updater

        notes = ("花边铺满整个游戏", "卡片跟着游戏大小", "检查更快")
        window._offer_update(updater.Release(version="v0.8.7", url="", sha256="", size=0, base="v0.8.0", notes=notes))
        settle(0.3)
        save(window, "header_发现新版本")
        window.update_panel.close_panel()
        save(window, "header_有更新")
        window.tabs.setCurrentIndex(3)
        save(window, "page_设置_有更新")
        window._offered = None
        window.update_pill.hide()
        window.update_button.setText("检查更新")
        window.tabs.setCurrentIndex(0)

    step("有更新", offered)
    window.tabs.setCurrentIndex(1)
    step("dlg_添加黑名单", window._add_by_dialog)
    step("dlg_批量导入", window._add_many_by_dialog)
    if window.store.entries:
        step("dlg_编辑黑名单", lambda: window._edit_entry(1 if len(window.store.entries) > 1 else 0))
    step("dlg_清空黑名单", window._clear_list)
    window.tabs.setCurrentIndex(2)
    likes = window.likes_page
    step("dlg_添加嘉宾", likes.add_one)
    if window.store.likes:
        step("dlg_编辑嘉宾", lambda: likes.edit(0))
    step("dlg_嘉宾特效", window._show_love_effects)
    window.tabs.setCurrentIndex(3)
    step("dlg_显示说明", window._show_display_guide)
    step("dlg_直播模式说明", window._show_stream_guide)
    step("dlg_使用声明", window._show_disclaimer)
    window.tabs.setCurrentIndex(1)

    def menu() -> None:
        window.more_menu.popup(window.mapToGlobal(QPoint(600, 120)))
        settle(0.3)
        save(window.more_menu, "menu_更多")
        window.more_menu.hide()

    step("menu_更多", menu)
    step("toast", lambda: (window.toast.show_message("已删除「夜猫子」", "撤销", lambda: None, ms=20000), save(window, "toast")))

    def picture() -> None:
        from blacklist_detect.pipeline import check_image
        from blacklist_detect.ui_dialogs import PictureResultDialog

        result = check_image(ROOT / "blacklist_detect" / "assets" / "sample-lobby.jpg", list(window.store.entries))
        label["name"] = "dlg_截图检查"
        PictureResultDialog("截图检查", result=result, parent=window, likes=window.store.likes, me="测试主播").open()
        label["name"] = "dlg_截图检查_打不开"
        PictureResultDialog("截图检查", error="这张图打不开", parent=window).open()

    step("dlg_截图检查", picture)

    def report() -> None:
        from blacklist_detect.diagnostics import FlowTest
        from blacklist_detect.ui_dialogs import FlowReportDialog

        runs = [{"capture": 0.08, "find": 0.6, "read": 0.09}, {"capture": 0.07, "find": 0.04, "read": 0.06}] * 2
        test = FlowTest(size=(3840, 2160), device="gpu:0", capture=0.08, glance=0.12, glance_found=True,
                        auto={"capture": 0.08, "find": 0.05, "read": 0.07}, runs=runs, right=12, cpu_busy=21.0, cpu_own=4.0)  # fmt: skip
        label["name"] = "dlg_环境测试"
        FlowReportDialog(test, lambda: None, window).open()

    step("dlg_环境测试", report)

    def cards() -> None:
        from blacklist_detect.ui_overlay import ClearMark, HitCard, LikeCard

        hit = HitCard()
        hit.set_people([("示例坏人", ("炸房",)), ("路过的捣蛋鬼", ("场外", "挂机"))], 82)
        like = LikeCard()
        like.set_people([("心动小鹿", ()), ("一起开黑的朋友", ())], 82)
        mark = ClearMark()
        mark.set_heart(True)
        mark.set_size(82)
        for widget, name in ((hit, "card_黑名单"), (like, "card_嘉宾"), (mark, "card_嘉宾徽章")):
            widget.move(-3000, -3000)
            widget.show()
            save(widget, name)
            widget.hide()

    step("cards", cards)

    def corner() -> None:
        from blacklist_detect.ui_notice import _Card

        window.notice.show_result([("示例坏人", ("炸房",))], ["心动小鹿", "心动星星"], 1, QApplication.primaryScreen())
        settle(0.8)
        for index, card in enumerate(w for w in QApplication.topLevelWidgets() if isinstance(w, _Card) and w.isVisible()):
            save(card, f"notice_{index}")

    step("notice", corner)
    print(f"{args.one}%: {len(shots)} pictures in {out}")
    window.close()
    settle(0.3)
    shutil.rmtree(data, ignore_errors=True)
    sys.stdout.flush()
    # Qt's teardown of a window shown this way can crash; the pictures are saved by now.
    os._exit(0)


def _screen_percent() -> int:
    """The main screen's Windows scale, in percent (100 elsewhere)."""
    try:
        import ctypes

        return int(ctypes.windll.shcore.GetScaleFactorForDevice(0)) or 100
    except (AttributeError, OSError):
        return 100


def _seed(root: Path, args, version: str) -> None:  # noqa: ANN001
    from blacklist_detect.storage import Store

    store = Store(root)
    if args.data != "empty":
        for name, tags, reason in (
            ("示例坏人", ("炸房",), "开局就退，三把了"),
            ("路过的捣蛋鬼", ("场外", "挂机"), "场外报点，还在频道里骂人"),
            ("一个名字特别特别长的玩家", ("送人头",), ""),
            ("夜猫子", (), "约好的车不来"),
            ("小透明", ("挂机",), "全程挂机不动，一句话也不说，这是一段很长的原因，看看表格会不会把它截断"),
        ):
            store.add(name, tags=tags, reason=reason)
        store.add_like("心动小鹿", nickname="小鹿", reason="声音好听")
        store.add_like("心动星星")
        store.add_like("一起开黑的朋友", reason="每次都带我赢")
        store.add_scan([{"seat": i + 1, "name": n, "unclear": n == "摸鱼大师"} for i, n in enumerate(SEATS)], elapsed=0.31)
    if args.data == "stress":
        store.add_custom_tag("不尊重底牌还骂人")
        for number in range(1, 124):
            name = f"测试玩家{number:03d}" if number % 9 else f"一个名字特别长的测试玩家{number:03d}"
            tags = (("炸房", "挂机", "不尊重底牌还骂人") if number % 7 == 0 else ("场外",)) if number % 3 else ()
            store.add(name, tags=tags, reason="原因写得很长很长，看看在表格里会不会把别的列挤歪" if number % 4 == 0 else "")
        for number in range(1, 13):
            store.add_like(f"嘉宾玩家{number:02d}", nickname=f"昵称很长的嘉宾{number}" if number % 2 else "")
        now = datetime.now().astimezone().replace(microsecond=0)
        names = [f"测试玩家{n:03d}" for n in range(1, 13)]
        store.scans = [
            {
                "at": (now - timedelta(hours=index * 7, minutes=index * 3)).isoformat(),
                "elapsed": 0.3,
                "names": [{"seat": i + 1, "name": n if (i + index) % 5 else "", "unclear": (i + index) % 5 == 0} for i, n in enumerate(names)],
            }
            for index in range(40)
        ]
        store.save_scans()
    store.save_entries()
    store.save_likes()
    store.save_settings()
    path = root / "settings.json"
    settings = json.loads(path.read_text(encoding="utf-8"))
    settings.update({
        "welcomed": True, "disclaimer_accepted": True, "env_checked": version, "consented": ["full"],
        "hotkey": "Alt+F11", "close_to_tray": False, "auto_capture": False, "safe_mode": False,
        "stream_mode": "on" if args.stream else "", "stream_guided": True, "player_name": "测试主播",
        "appearance": "dark" if args.dark else "light", "window_size": list(args.size),
    })  # fmt: skip
    if args.data == "stress":
        settings.update({"player_name": "这是一个非常非常长的游戏名字", "hotkey": "Shift+F12", "auto_capture": True})
    path.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
