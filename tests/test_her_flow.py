"""tools/her_flow.py's own parts: her screen, the stall measure, her list, 直播姬's copy and the summary."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import her_flow  # noqa: E402

from blacklist_detect import livehime, livehime_layout  # noqa: E402
from blacklist_detect.storage import Store  # noqa: E402


def test_screen_frame_puts_the_game_in_her_mumu_window():
    crop = np.full((400, 600, 3), 200, dtype=np.uint8)
    frame = her_flow.screen_frame(crop, (-50, -20, 650, 380))
    assert frame.shape == (1080, 1920, 3)
    left, top, right, bottom = her_flow.GAME
    assert (right - left, bottom - top) == (1538, 865)
    assert tuple(frame[top + 5, left + 5]) == (200, 200, 200)
    assert tuple(frame[5, 5]) == (32, 64, 112)
    bar_left, bar_top, bar_right, bar_bottom = her_flow.mumu_window()
    assert (bar_right - bar_left, bar_bottom - bar_top) == (1538, 914)
    assert tuple(frame[bar_top + 2, bar_left + 2]) == (238, 240, 244)


def test_screen_frame_fills_the_game_once_the_lobby_is_gone():
    crop = np.full((400, 600, 3), 200, dtype=np.uint8)
    frame = her_flow.screen_frame(crop, (0, 0, 600, 400), fill=(40, 90, 60))
    left, top, _right, _bottom = her_flow.GAME
    assert tuple(frame[top + 100, left + 100]) == (40, 90, 60)


def test_logical_is_her_125_percent():
    assert her_flow.logical((191, 107, 1729, 972)) == (153, 86, 1230, 692)


def test_longest_stall_is_the_widest_gap_beyond_the_tick():
    ticks = [0.0, 0.016, 0.032, 0.300, 0.316, 0.332]
    assert abs(her_flow.longest_stall(ticks, 0.0, 0.332) - (0.268 - 0.016)) < 1e-9
    # A gap that spans the start counts; ticks outside the span do not.
    assert abs(her_flow.longest_stall(ticks, 0.1, 0.33) - (0.268 - 0.016)) < 1e-9
    assert her_flow.longest_stall([0.0, 0.016, 0.032], 0.0, 0.032) < 1e-9


def test_her_share_is_of_the_capped_pc():
    # 20 CPUs held to 18 %: her PC is 3.6 CPUs; 1.8 CPU seconds in 1 s is half of it.
    assert abs(her_flow.her_share(1.8, 1.0, 18, 20, 12) - 50.0) < 1e-9
    assert abs(her_flow.her_share(6.0, 1.0, 0, 20, 12) - 50.0) < 1e-9


def test_seed_store_is_her_setup(tmp_path):
    store = Store(tmp_path)
    her_flow.seed_store(store, "classic", filler=20)
    again = Store(tmp_path)
    names = [entry.name for entry in again.entries]
    assert len(names) == 21 and her_flow.BLACK in names
    assert [like.name for like in again.likes] == list(her_flow.GUESTS)
    assert all(like.scenes.keys == ("classic",) for like in again.likes)
    assert (again.safe_mode, again.auto_capture, again.stream_mode, again.disclaimer_accepted) == (False, False, "on", True)


def test_livehime_copy_reads_back_as_her_layout(tmp_path):
    her_flow.livehime_files(tmp_path, "模仿者·直播画面")
    root = tmp_path / "bililive" / "User Data"
    scene = livehime.SceneWatch(root / "bililive_debug.log").scene()
    assert [capture.title for capture in scene] == ["MuMu模拟器12", "模仿者·直播画面"]
    current, placed = livehime_layout.placements(livehime_layout.collection_path(root))
    assert current == "Scene 1"
    game, mirror = placed
    width, height = 1538, 914
    assert [round(v) for v in game.on_canvas(width, height)] == [0, -63, 1890, 1123]
    assert [round(v) for v in mirror.on_canvas(1920, 1080)] == [0, 0, 1280, 720]


def test_summarize_and_targets():
    row = {"marks": 1.2, "frames_check": 92.0, "frames_scene": 96.0, "stall_ms": 80.0, "check_cpu": 60.0,
           "idle_cpu": 1.0, "names": 12, "mirror": "follows"}
    rows = [{**row, "rss_mb": 500.0 + n} for n in range(5)] + [{**row, "marks": 2.0, "rss_mb": 510.0}]
    summary = her_flow.summarize(rows)
    assert summary["marks"] == 1.2 and summary["marks_idle"] == 2.0
    assert summary["memory_mb"] == 510.0 - 502.0
    assert summary["names"] == 12 and summary["mirror"] == "follows"
    assert all(said.endswith("PASS") for said in her_flow.verdicts(summary))
    assert "stall_ms FAIL" in her_flow.verdicts({**summary, "stall_ms": 101.0})
