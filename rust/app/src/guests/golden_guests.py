"""Golden data for the Rust 嘉宾 page (rust/app/src/guests): the Python LikesPage's rows, menus and toolbar for a
few lists and searches, written to golden.json beside this file.

Run from the checkout's root, with APPDATA and HOME pointed at a data folder of its own and QT_QPA_PLATFORM=offscreen:
    python3 rust/app/src/guests/golden_guests.py
Made-up names only.
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from blacklist_detect.model import Combo, Scenes  # noqa: E402
from blacklist_detect.storage import Store  # noqa: E402
from blacklist_detect.ui_guests import scene_dots, scenes_said  # noqa: E402
from blacklist_detect.ui_likes import COMBO_ROLE, ME_ROLE, NAME, PEOPLE_ROLE, SCENES_ROLE, LikesPage, share_likes  # noqa: E402

SEATS = ["小林同学", "白日梦想家", "路过的猫", "一只团子", "夏天的风", "心动小鹿", "晚风吹过", "摸鱼大师", "示例坏人", "心动星星", "柠檬汽水", "棉花糖"]


def rows(page: LikesPage) -> list[dict]:
    table = page.table
    out = []
    for row in range(table.rowCount()):
        first = table.item(row, NAME)
        kind = "me" if first.data(ME_ROLE) is not None else "combo" if first.data(COMBO_ROLE) is not None else "like"
        cells = [table.item(row, column).text() if table.item(row, column) else "" for column in range(5)]
        people = first.data(PEOPLE_ROLE)
        out.append({
            "kind": kind,
            "place": page._index_at(row) if kind == "like" else page._combo_at(row),
            "cells": cells,
            "people": [[name, present] for name, present in people] if people else [],
            "dots": list(table.item(row, 2).data(SCENES_ROLE) or []),
            "menu": menu(page, row, kind),
        })
    return out


def menu(page: LikesPage, row: int, kind: str) -> list[str]:
    index = page._index_at(row)
    if kind == "me":
        return ["编辑"]
    if kind == "combo":
        return ["编辑", "-", "删除"]
    top = index == len(page.store.likes) - 1
    return ["编辑", "复制名字", *([] if top else ["置顶"]), "-", "删除"]


def state(page: LikesPage, query: str) -> dict:
    page.search.setText(query)
    return {
        "query": query,
        "rows": rows(page) if page.table.isVisibleTo(page) else [],
        "table": page.table.isVisibleTo(page),
        "toolbar": page.add_like_button.isVisibleTo(page),
        "search": page.search.isVisibleTo(page),
        "more": page.more_button.isVisibleTo(page),
        "add_combo_enabled": page.add_combo_button.isEnabled(),
        "empty_text": page.empty.title.text(),
        "empty_buttons": page.empty_add_button.isVisibleTo(page),
        "drag": page.table.dragEnabled(),
    }


def build(root: Path, kind: str, now: datetime) -> Store:
    store = Store(root)
    if kind == "empty":
        return store
    store.add_like("心动小鹿", nickname="小鹿", reason="声音好听", scenes=Scenes(("fluffy", "stars")))
    store.add_like("心动星星")
    store.add_like("一起开黑的朋友", reason="每次都带我赢\n第二行", scenes=Scenes(("cyber",)))
    store.add_like("柠檬汽水", nickname="汽水", scenes=Scenes((), random=False))
    store.add_like("棉花糖", scenes=Scenes(("champagne", "gone_scene", "lace", "ice", "neon")))
    store.set_combos([
        Combo(("心动小鹿", "心动星星"), Scenes(("angel",))),
        Combo(("心动星星", "一起开黑的朋友"), Scenes()),
        Combo(("棉花糖", "走掉的嘉宾"), Scenes((), random=False)),
    ])
    store.set_me(Scenes(("lace",)))
    store.player_name = "心动星星" if kind == "named" else ""
    seats = [{"seat": i + 1, "name": n, "unclear": n == "摸鱼大师"} for i, n in enumerate(SEATS)]
    older = [{"seat": 1, "name": "棉花糖", "unclear": False}, {"seat": 2, "name": "走掉的嘉宾", "unclear": False}]
    store.scans = [
        {"at": (now - timedelta(hours=3)).isoformat(), "elapsed": 0.3, "names": seats},
        {"at": (now - timedelta(days=40)).isoformat(), "elapsed": 0.3, "names": older},
    ]
    return store


def main() -> None:
    app = QApplication.instance() or QApplication([])
    now = datetime.now().astimezone().replace(microsecond=0)
    cases = []
    for kind in ("empty", "list", "named"):
        with tempfile.TemporaryDirectory() as folder:
            store = build(Path(folder), kind, now)
            page = LikesPage(store, lambda *a, **k: None)
            queries = ("",) if kind == "empty" else ("", "小鹿", "星星", "汽水", "开黑", "走掉", "没有这个人", "XINDONG")
            cases.append({
                "kind": kind,
                "share": share_likes(store.likes),
                "likes": [{"name": like.name, "nickname": like.nickname, "reason": like.reason,
                           "scenes": list(like.scenes.keys), "random": like.scenes.random} for like in store.likes],
                "combos": [{"names": list(c.names), "scenes": list(c.scenes.keys), "random": c.scenes.random} for c in store.combos],
                "me": {"scenes": list(store.me.keys), "random": store.me.random},
                "player_name": store.player_name,
                "scans": [{"at": s["at"], "names": [[n["name"], n["unclear"]] for n in s["names"]]} for s in store.scans],
                "states": [state(page, query) for query in queries],
            })
            page.deleteLater()
    said = []
    for keys, random in ((("classic",), False), ((), True), ((), False), (("ice", "stars"), False), (("gone",), False),
                         (("champagne",), False), (("fluffy",), True), (("a", "b"), False)):
        scenes = Scenes(keys, random=random)
        said.append({"scenes": list(keys), "random": random, "said": scenes_said(scenes), "dots": scene_dots(scenes)})
    out = {"now": now.isoformat(), "cases": cases, "said": said}
    Path(__file__).with_name("golden.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    app.quit()


if __name__ == "__main__":
    main()

