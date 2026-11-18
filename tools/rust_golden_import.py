"""Golden data for the Rust port of importing.py, guests.py and names.py (rust/data/src/import/).

Runs the Python functions on every paste in tests/test_importing.py and tests/test_paste_formats.py plus edge
cases of our own, and saves inputs and outputs as JSON under rust/data/tests/golden/import/. Made-up names only.

    PYTHONPATH=. python tools/rust_golden_import.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def _stub_qt() -> None:
    """guests.py needs only love_scenes' keys; without PySide6 here, Qt is a stub that is never drawn with."""
    import importlib.util
    import types

    if importlib.util.find_spec("PySide6") is not None:
        return

    class _Any:
        def __init__(self, *args, **kwargs):
            pass

        def __getattr__(self, name):
            return _Any()

        def __call__(self, *args, **kwargs):
            return _Any()

    def module(name: str) -> types.ModuleType:
        mod = types.ModuleType(name)
        mod.__getattr__ = lambda attr: _Any  # type: ignore[method-assign]
        mod.__path__ = []
        return mod

    for name in ("PySide6", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "PySide6.QtMultimedia"):
        sys.modules[name] = module(name)


_stub_qt()

from blacklist_detect import guests, importing, love_scenes, names  # noqa: E402
from blacklist_detect.match import clean_stored_name, fold  # noqa: E402
from blacklist_detect.model import Combo, Entry, Scenes  # noqa: E402
from blacklist_detect.storage import TAGS  # noqa: E402

import test_importing as ti  # noqa: E402
import test_paste_formats as tp  # noqa: E402

OUT = ROOT / "rust" / "data" / "tests" / "golden" / "import"
PASTE_CATALOG = tp.CATALOG

EDGE = [
    "", "\n\n\n", "   ", "﻿示例坏人（炸房）", "﻿#模仿者小工具 黑名单 1人\n示例坏人，炸房",
    "示例坏人\r\n心动小鹿\r\n心动星星", "示例坏人\r心动小鹿", "ｓｈｉｌｉ（挂机）", "示例坏人　心动小鹿",
    "示例坏人（炸房）\n\n心动小鹿 挂机\n心动星星：贴脸", "示例坏人,心动小鹿；心动星星|小明/小红",
    "示例坏人" * 30, "示例坏人（" + "坏" * 300 + "）", "Ａｂｃ Ｄｅｆ（演员）", "Lucky Star Moon（挂机）",
    "1. 示例坏人\n2. 心动小鹿\n3. 心动星星", "①示例坏人②心动小鹿", "⑴示例坏人", "示例坏人…（挂机）", "示例坏人...",
    "（炸房）", "）", "（", "（（（", "））", "示例坏人（炸房）（贴脸）", "示例坏人（未闭合\n心动小鹿（也没\n心动星星）",
    "\t\t", "|", "| |", "|---|", "名字\t原因", "示例坏人\t\t炸房\t", "| 示例坏人 | 炸房 | 贴脸 |",
    "炸房：\n示例坏人\n挂机 贴脸\n心动小鹿", "【炸房，挂机】示例坏人 心动小鹿", "【未知标签】示例坏人",
    "以下：", "以下是名单：\n示例坏人", "示例坏人：", "示例坏人：\n", "名字：示例坏人 原因：炸房",
    "2026年10月12日 示例坏人\n心动小鹿 挂机", "12:30 心动星星", "1234567890", "²³", "示例坏人 骂人",
    "示例坏人 心动小鹿\n心动星星 炸房\n小明 挂机", "ß大写ẞ", "İstanbul", "ΣΑΣ", "😀示例坏人", "★示例坏人 炸房",
    "示例坏人  心动小鹿", "示例坏人\x1c心动小鹿", "示例坏人\x0b心动小鹿\x0c心动星星", "a\u0085b", "示例坏人　炸房",
    "其他：送人头", "示例坏人，其他：送人头", "#黑名单检测 名单 2人\n示例坏人，自定义标签，原因：开局，就炸\n示例坏人，重复",
    "#模仿者小工具 黑名单 1人\n\n#注释\n心动小鹿，，，原因：", "示例坏人 原因：", "示例坏人，理由：一直挂机，备注：再说",
    "示例坏人-", "-示例坏人", "~~示例坏人~~挂机", "示例坏人——", "示例坏人（炸房）心动小鹿（挂机）心动星星",
    "1.示例坏人（炸房）2.心动小鹿", "示例坏人、心动小鹿 炸房贴脸", "示例坏人/心动小鹿 一起送人头", "a b", "a  b c",
    "炸房", "炸房 挂机", "炸房：", "：", ":", "以下", "避雷", "示例坏人 避雷名单", "示例坏人（\n）", "示例坏人（\n\n\n心动小鹿）",
    "​示例坏人", "示例‍坏人", "示例坏人️", "＃示例坏人", "@@示例坏人", "> 示例坏人", ">>> 示例坏人 炸房",
    "1 示例坏人", "12 34", "999 示例", "1000 示例", "1)示例坏人", "1：示例坏人", "-  -  示例坏人", "•• 示例坏人",
]

EXTRA_CATALOGS = [(), ("炸房", "演员", "送人头", "人头"), ("好人",), ("Abc", "abc")]

ENTRY_SETS = [
    [],
    [{"name": "示例坏人", "reason": "炸房还骂人", "tags": ["炸房"]}, {"name": "心动小鹿大王", "reason": "", "tags": []},
     {"name": "心动星星", "reason": "挂机", "tags": ["挂机"]}],
    [{"name": "Lucky Star", "reason": "", "tags": ["演员"]}, {"name": "示例", "reason": "", "tags": []}],
]
ELSEWHERE_SETS = [[], [{"name": "心动小鹿", "reason": "", "tags": []}, {"name": "LUCKYSTAR", "reason": "", "tags": []}]]


def entry(d: dict) -> Entry:
    return Entry(d["name"], d["reason"], tuple(d["tags"]))


def rows_out(rows) -> list:
    return [{"name": r.name, "tags": list(r.tags), "reason": r.reason, "status": r.status, "target": r.target,
             "checked": r.checked} for r in rows]


def pastes() -> list[str]:
    found = [ti.FRIEND, ti.FRIEND.replace("（", "(").replace("）", ")")]
    for module in (ti, tp):
        source = Path(module.__file__).read_text(encoding="utf-8")
        import ast

        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.strip():
                found.append(node.value)
    found += [paste for _title, paste, _expected in tp.CASES]
    found += EDGE
    return list(dict.fromkeys(found))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cases = []
    for text in pastes():
        for catalog in (TAGS, PASTE_CATALOG, *EXTRA_CATALOGS):
            cases.append({"text": text, "catalog": list(catalog),
                          "read": [[n, list(t), r] for n, t, r in importing.read_paste(text, catalog)]})
    plans = []
    for text in pastes():
        for ei, entries in enumerate(ENTRY_SETS):
            for elsewhere in ELSEWHERE_SETS:
                for catalog in (TAGS, PASTE_CATALOG):
                    out = importing.plan_import(text, [entry(e) for e in entries], catalog, [entry(e) for e in elsewhere])
                    plans.append({"text": text, "catalog": list(catalog), "entries": entries, "elsewhere": elsewhere,
                                  "rows": rows_out(out)})
            del ei
    reason_sets = [ti.SHARED_REASONS, ti.GAME_REASONS,
                   [("甲", (), "演员一个", -1), ("乙", (), "纯演员", -1), ("丙", ("演员",), "又是演员", -1)],
                   [("甲", ("炸房",), "又炸房了", -1), ("乙", ("炸房",), "炸房狗", -1)],
                   [("甲", (), "又是好人", -1), ("乙", (), "全是好人", -1)],
                   [("甲", (), "ABC abc 送人头", -1), ("乙", (), "abc送人头了", -1), ("丙", (), "", -1)],
                   [("甲", (), "".join(chr(0x4e00 + i) for i in range(40)), -1),
                    ("乙", (), "".join(chr(0x4e00 + i) for i in range(5, 45)), -1)]]
    suggests = []
    for rows in reason_sets:
        for catalog in (("炸房", "挂机"), ("炸房", "演员"), ("好人",), TAGS, ("Abc",)):
            found = importing.suggest_tags(list(rows), catalog)
            tagged = importing.with_tags(list(rows), found)
            suggests.append({"rows": [[n, list(t), r, g] for n, t, r, g in rows], "catalog": list(catalog),
                             "found": [{"tag": s.tag, "existing": s.existing, "rows": list(s.rows)} for s in found],
                             "tagged": [[n, list(t), r, g] for n, t, r, g in tagged]})
    words = ["银行", "探团", "送人头", "炸房", "好人", "狂欢", "", "模仿者狂欢之夜"]
    folds = [{"text": t, "fold": fold(t), "clean": clean_stored_name(t)} for t in pastes() + EDGE]
    (OUT / "read.json").write_text(json.dumps(cases, ensure_ascii=False, indent=0), encoding="utf-8")
    (OUT / "plan.json").write_text(json.dumps(plans, ensure_ascii=False, indent=0), encoding="utf-8")
    (OUT / "suggest.json").write_text(json.dumps({"suggest": suggests, "game_words": list(importing.GAME_WORDS),
                                                  "is_game_word": {w: importing.is_game_word(w) for w in words}},
                                                 ensure_ascii=False, indent=0), encoding="utf-8")
    (OUT / "fold.json").write_text(json.dumps(folds, ensure_ascii=False, indent=0), encoding="utf-8")
    (OUT / "guests.json").write_text(json.dumps(guest_cases(), ensure_ascii=False, indent=0), encoding="utf-8")
    (OUT / "names.json").write_text(json.dumps({"app_name": names.APP_NAME, "launchers": list(names.LAUNCHERS),
                                                "processes": list(names.PROCESSES)}, ensure_ascii=False), encoding="utf-8")
    print(len(cases), "read,", len(plans), "plan,", len(suggests), "suggest,", len(folds), "fold")


def guest_cases() -> list:
    import itertools
    import random

    rng = random.Random(20261118)
    keys = [*love_scenes.KEYS, "champagne", "gone"]
    pool = ["示例坏人", "心动小鹿", "心动星星", "Lucky Star", "小明", "小红"]

    def scenes() -> dict:
        kind = rng.choice(["off", "random", "keys", "keys", "both"])
        picked = rng.sample(keys, rng.randint(1, 3)) if kind in ("keys", "both") else []
        return {"keys": picked, "random": kind in ("random", "both")}

    def make(s: dict) -> Scenes:
        return Scenes(tuple(s["keys"]), s["random"])

    out = []
    for _ in range(400):
        likes = [{"name": n if rng.random() < 0.8 else n.upper().replace(" ", ""), "scenes": scenes(),
                  "nickname": rng.choice(["", "", "昵称"])} for n in rng.sample(pool, rng.randint(0, len(pool)))]
        combos = [{"names": rng.sample(pool, rng.randint(1, 3)), "scenes": scenes()} for _ in range(rng.randint(0, 3))]
        present = [{"name": n} for n in rng.sample(pool, rng.randint(0, 4))]
        me = scenes()
        blacklisted = rng.random() < 0.3
        L = [Entry(d["name"], nickname=d["nickname"], scenes=make(d["scenes"])) for d in likes]
        C = [Combo(tuple(c["names"]), make(c["scenes"])) for c in combos]
        P = [Entry(p["name"]) for p in present]

        def enc(value):
            return list(value) if isinstance(value, tuple) else value

        who, choice = guests.lobby_scene(L, C, P, make(me), blacklisted)
        out.append({"likes": likes, "combos": combos, "present": present, "me": me, "blacklisted": blacklisted,
                    "lobby_choice": enc(guests.lobby_choice(L, C, P, "classic")), "lobby_scene": [who, enc(choice)],
                    "ticked": [list(guests.ticked(make(d["scenes"]))) for d in likes],
                    "members": [[list(m) for m in guests.members(c, L)] for c in C]})
    del itertools
    return out


if __name__ == "__main__":
    main()
