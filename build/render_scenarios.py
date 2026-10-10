"""Draw the app as three kinds of user see it, and time what gets slow as data grows.

    python build/render_scenarios.py [--names 1500] [--appearance light|dark]

    new    a first run: no names, no records, no 角色名称
    heavy  a long-time user: many names from shared lists, 40 records over weeks, every tag slot
    edge   awkward content: 64-character names, a lobby nobody could read, one with only hits

Pictures land in dist/gallery/scenarios/<scenario>/. Timings print as they are measured.
A throwaway settings folder is used, so the real list and settings are never touched.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

SYLLABLES = list("霁玥吉尔曼小猫爆锤大王路人甲阿强丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥星月云风雨雪霜花草木")
TAGS = ("炸房", "贴脸", "挂机", "场外", "不尊重底牌")
CUSTOM = [f"标签{i:02d}" for i in range(24)]
REASONS = ("开局就炸房，还骂人", "挂机三局", "场外报点", "", "很长的原因文字" * 8, "贴脸不讲理，第二局又遇到")


def _name(rng: random.Random) -> str:
    return "".join(rng.choice(SYLLABLES) for _ in range(rng.randint(2, 7)))


class Run:
    """One scenario: its data, its window, its pictures and timings."""

    def __init__(self, app, scenario: str, names: int, appearance: str, results: list[str]) -> None:  # noqa: ANN001
        self.app = app
        self.scenario = scenario
        self.names = names
        self.appearance = appearance
        self.results = results
        self.out = REPO / "dist" / "gallery" / "scenarios" / scenario
        self.out.mkdir(parents=True, exist_ok=True)
        self.window = None

    def timed(self, label: str, action):  # noqa: ANN001
        start = time.perf_counter()
        value = action()
        for _ in range(3):
            self.app.processEvents()
        took = (time.perf_counter() - start) * 1000
        line = f"[{self.scenario}] {label:<38} {took:8.0f} ms"
        print(line, flush=True)
        self.results.append(line)
        return value

    def snap(self, name: str, widget=None) -> None:  # noqa: ANN001
        for _ in range(10):
            self.app.processEvents()
        (widget or self.window).grab().save(str(self.out / f"{name}.png"))

    def seed(self) -> None:
        from blacklist_detect.storage import Store

        store = Store()
        store.appearance = self.appearance
        rng = random.Random(7)
        base = datetime.now().astimezone().replace(microsecond=0)
        if self.scenario == "heavy":
            for tag in CUSTOM:
                store.add_custom_tag(tag)
            catalog = store.tag_catalog()
            for _ in range(self.names):
                store.add(_name(rng), rng.choice(REASONS), tags=tuple(rng.sample(catalog, rng.randint(0, 4))))
            listed = [entry.name for entry in store.entries]
            scans = []
            for index in range(40):
                seats = []
                for seat in range(12):
                    roll = rng.random()
                    name = rng.choice(listed) if roll < 0.15 else ("" if roll < 0.25 else _name(rng))
                    seats.append({"seat": seat + 1, "name": name, "unclear": not name})
                at = base - timedelta(days=index // 2, hours=rng.randint(0, 12), minutes=index)
                scans.append({"at": at.isoformat(), "elapsed": 1.2, "names": seats})
            store.scans = scans
            store.player_name = listed[5]
        elif self.scenario == "edge":
            long_name = ("超长的名字" * 13)[:64]
            store.add(long_name, "原" * 200, tags=TAGS)
            store.add("emoji🙂名字", "", tags=("炸房",))
            store.add("Latin_Name_With_No_Breaks_1234567890", "1" * 200)
            store.player_name = "我自己的名字特别长"
            unclear = [{"seat": i + 1, "name": "", "unclear": True} for i in range(12)]
            hits = [{"seat": i + 1, "name": long_name if i % 2 else "emoji🙂名字", "unclear": False} for i in range(12)]
            store.scans = [
                {"at": base.isoformat(), "elapsed": 1.0, "names": hits},
                {"at": (base - timedelta(minutes=5)).isoformat(), "elapsed": 1.0, "names": unclear},
            ]
        store.save_entries()
        store.save_scans()
        store.save_settings()

    def go(self) -> None:
        from blacklist_detect import ui

        self.app.setFont(ui.chinese_font())
        ui._apply_theme(self.app)
        self.window = window = self.timed("open the window", ui.MainWindow)
        window._watch_timer.stop()
        window.resize(1100, 700)
        window.show()
        pages = (("records", window.history_tab), ("blacklist", window.blacklist_tab), ("settings", window.settings_tab))
        for page, index in pages:
            self.timed(f"switch to {page}", lambda index=index: window.tabs.setCurrentIndex(index))
            self.snap(page)
        if self.scenario == "heavy":
            self.timed("redraw the whole list", window._show_list)
            window.tabs.setCurrentIndex(window.blacklist_tab)
            self.timed("type one search letter", lambda: window.list_search.setText("霁"))
            self.snap("blacklist_search")
            self.timed("clear the search", window.list_search.clear)
            self.timed("reload the records", window._reload_history)
            self.timed("add one name", lambda: (window.store.add("新来的人"), window._list_changed()))
            self.timed("change the theme", lambda: window._set_theme("绿色"))
            self.timed("switch to dark", lambda: window._set_appearance("dark"))
            window.tabs.setCurrentIndex(window.history_tab)
            self.snap("records_dark")
            window.tabs.setCurrentIndex(window.blacklist_tab)
            self.snap("blacklist_dark")
        if self.scenario == "edge":
            window.tabs.setCurrentIndex(window.history_tab)
            window._reload_history(1)
            self.snap("records_unclear")
        window.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--names", type=int, default=1500, help="blacklist size for the heavy user")
    parser.add_argument("--appearance", default="light")
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")

    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    results: list[str] = []
    for scenario in ("new", "heavy", "edge"):
        os.environ["APPDATA"] = tempfile.mkdtemp()
        run = Run(app, scenario, args.names, args.appearance, results)
        run.seed()
        run.go()
    print("\n".join(["", "Summary:", *results]))
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
