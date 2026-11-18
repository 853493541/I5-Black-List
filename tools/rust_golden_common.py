"""Golden data for rust/common: match.py's name rules, paths.py and the shared constants, as Python computes them.

Run from the checkout root with APPDATA/HOME pointed at a folder of its own:
    PYTHONPATH=. python tools/rust_golden_common.py
writes rust/common/tests/golden.json. Made-up names only.
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path
from unittest import mock

from blacklist_detect import love_scenes, match, names, paths, storage

FIXED = [
    "", " ", "　", "示例坏人", "心动小鹿...", "心动星星…", "心动小鹿⋯⋯", "心动星星。", "心动小鹿。。", "心动小鹿·",
    "心动小鹿··", "示例坏人.…", "示例坏人·..", "ＡＢＣ示例", "Ａｂｃ", "Straße", "ǅ心动", "x`y", "a\u001cb", "a\x0bb",
    "名字.。", "名字...。", "…", "......", "·", "Ⅻ心动", "①②", "ﬁ心动", "ＭＩＸ星星…", "  心动 小鹿  ", "心动\t星星\n",
    "İstanbul", "ΣΑΣ", "示例。·。", "。。。示例", "a..b..", "示例坏人!!", "[心动]", "心动_小鹿", "x̃心动",
]
POOL = "示例坏人心动小鹿星星aAbBzZ0９.。·…⋯ 　`!_-ＡＺⅫ①ßİΣ\t\u001c\u0085"


def cases() -> list[str]:
    rng = random.Random(20261118)
    out = list(FIXED)
    for _ in range(600):
        out.append("".join(rng.choice(POOL) for _ in range(rng.randint(1, 10))))
    return out


def main() -> None:
    texts = [
        {
            "raw": raw,
            "normalize_text": match.normalize_text(raw),
            "split_ellipsis": list(match.split_ellipsis(raw)),
            "strip_noise": match.strip_noise(raw),
            "fold": match.fold(raw),
            "clean_stored_name": match.clean_stored_name(raw),
        }
        for raw in cases()
    ]
    app_dirs = []
    for platform, env in [
        ("win32", {"APPDATA": "C:/Users/u/AppData/Roaming"}),
        ("win32", {"APPDATA": ""}),
        ("win32", {}),
        ("linux", {"XDG_CONFIG_HOME": "/x/config"}),
        ("linux", {"XDG_CONFIG_HOME": ""}),
        ("linux", {}),
    ]:
        with mock.patch.object(Path, "home", return_value=Path("/home/u")):
            app_dirs.append({"windows": platform == "win32", "env": env, "dir": paths.app_dir(platform, env).as_posix()})
    child = {"PATH": "/bin", "OMP_NUM_THREADS": "1", "omp_num_threads": "4", "__KMP_REGISTERED_LIB_77": "x",
             "__kmp_registered_lib_9": "y", "PADDLE_PDX_CPU_NUM_THREADS": "6", "KEEP": "1"}
    with mock.patch.dict(os.environ, child, clear=True):
        child_env = paths.child_env()
    golden = {
        "texts": texts,
        "min_prefix_chars": match.MIN_PREFIX_CHARS,
        "app_dirs": app_dirs,
        "child_env_in": child,
        "child_env_out": child_env,
        "ocr_threads": {str(cores): int(paths.ocr_threads(cores)) for cores in range(1, 17)},
        "custom_sound_dir": paths.custom_sound_dir(Path("/data/root")).as_posix(),
        "launchers": list(names.LAUNCHERS),
        "processes": list(names.PROCESSES),
        "tags": list(storage.TAGS),
        "max_name": storage._MAX_NAME,
        "max_note": storage._MAX_NOTE,
        "max_tag": storage._MAX_TAG,
        "share_mark": storage.SHARE_MARK,
        "old_share_marks": list(storage.OLD_SHARE_MARKS),
        "scene_keys": list(love_scenes.KEYS),
    }
    out = Path("rust/common/tests/golden.json")
    out.write_text(json.dumps(golden, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out}: {len(texts)} texts")


if __name__ == "__main__":
    main()
