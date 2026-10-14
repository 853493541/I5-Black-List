"""Where 直播姬 puts each window capture, read from its scene file and its log."""

import json

import pytest

from blacklist_detect import livehime_layout as layout
from blacklist_detect.livehime_layout import Placement


def _placed(**changes) -> Placement:  # noqa: ANN003
    fields = dict(
        scene="Scene 1", name="窗口捕捉", title="游戏", window_class="Game", exe="game.exe", client_area=True,
        whole_screen=False, visible=True, pos=(0.0, 0.0), scale=(1.0, 1.0), crop=(0, 0, 0, 0), bounds_type=0,
        bounds=(0.0, 0.0), bounds_align=0, align=5, rotation=0.0,
    )  # fmt: skip
    fields.update(changes)
    return Placement(**fields)


def test_a_capture_lands_on_the_canvas_as_obs_draws_it():
    # 直播姬 adds a window fitted into the canvas, centered, at a fixed scale (top-left anchor).
    assert _placed(pos=(0.0, 37.0), scale=(0.5, 0.5)).on_canvas(3840, 2014) == (0.0, 37.0, 1920.0, 1007.0)
    # Anchored by its middle, and cropped before it is scaled.
    assert _placed(pos=(960.0, 540.0), align=0).on_canvas(200, 100) == (860.0, 490.0, 200.0, 100.0)
    assert _placed(crop=(10, 20, 30, 40)).on_canvas(200, 100) == (0.0, 0.0, 160.0, 40.0)
    # In a bounding box: fitted inside it and centered there, or stretched to it.
    inner = _placed(bounds_type=layout.INNER, bounds=(1920.0, 1080.0))
    fitted = 1540 * 1080 / 915
    assert inner.on_canvas(1540, 915) == pytest.approx(((1920 - fitted) / 2, 0.0, fitted, 1080.0))
    assert _placed(bounds_type=layout.STRETCH, bounds=(1920.0, 1080.0)).on_canvas(1540, 915) == (0.0, 0.0, 1920.0, 1080.0)


def test_the_scene_file_gives_every_window_capture_in_every_scene(tmp_path):
    collection = {
        "current_scene": "Scene 2",
        "sources": [
            {"id": "window_capture", "name": "窗口捕捉", "uuid": "a",
             "settings": {"window": "MuMu模拟器12:Qt5156QWindowIcon:MuMuNxDevice.exe", "client_area": True}},
            {"id": "window_capture", "name": "窗口捕捉 2", "uuid": "b",
             "settings": {"window": "模仿者小工具·直播画面:Qt6120QWindowIcon:模仿者小工具.exe", "capture_from_whole_screen": True}},
            {"id": "monitor_capture", "name": "显示器", "uuid": "c", "settings": {}},
            {"id": "scene", "name": "Scene 2", "settings": {"items": [
                {"name": "窗口捕捉", "source_uuid": "a", "visible": True, "pos": {"x": 0, "y": 37}, "scale": {"x": 1.1, "y": 1.1},
                 "bounds_type": 0, "bounds": {"x": 0, "y": 0}, "align": 5, "crop_left": 0, "crop_top": 0, "crop_right": 0, "crop_bottom": 0},
                {"name": "窗口捕捉 2", "source_uuid": "b", "visible": False, "pos": {"x": 0, "y": 0}, "scale": {"x": 1, "y": 1},
                 "bounds_type": 0, "bounds": {"x": 0, "y": 0}, "align": 5, "rot": 0},
                {"name": "显示器", "source_uuid": "c", "visible": True},
            ]}},
        ],
    }  # fmt: skip
    path = tmp_path / "Scene Collection" / "collection.json"
    path.parent.mkdir()
    path.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")
    current, placed = layout.placements(path)
    assert current == "Scene 2" and [item.name for item in placed] == ["窗口捕捉", "窗口捕捉 2"]
    game, ours = placed
    assert (game.title, game.window_class, game.exe, game.client_area) == ("MuMu模拟器12", "Qt5156QWindowIcon", "MuMuNxDevice.exe", True)
    assert ours.title == "模仿者小工具·直播画面" and ours.whole_screen and not ours.visible
    assert game.pos == (0.0, 37.0) and game.scale == (1.1, 1.1)
    # The newest scene collection of any account.
    account = tmp_path / "335583400" / "Scene Collection"
    account.mkdir(parents=True)
    (account / "a.json").write_text("{}", encoding="utf-8")
    assert layout.collection_path(tmp_path) == account / "a.json"


def test_the_log_says_the_canvas_and_whether_viewers_see_the_last_change(tmp_path):
    log = tmp_path / "bililive_debug.log"
    log.write_text(
        "\n".join([
            "[1:1014/001000.000:INFO:x] --- Application Startup ---",
            "[1:1014/001100.000:INFO:x] ## [Scene Collection]: is_double_screen-0 main_width-1920 main_height-1080 sub_width-1280 sub_height-720",
            "[1:1014/001200.000:INFO:x] BililiveOBSView::OnLiveProgramModeChanged : 1",
            "[1:1014/001300.000:INFO:x] [ProgramMode] ButtonPressed OpenProgramView",
            "[1:1014/001400.000:INFO:x] scene 'Scene 2' add item : '窗口捕捉 5'",
        ])
        + "\n",
        encoding="utf-8",
    )  # fmt: skip
    found = layout.studio(log)
    assert found.canvas == (1920, 1080) and found.double_screen is False and found.two_canvas is True
    assert (found.synced, found.edited) == ("1014 001300", "1014 001400") and found.unsynced()
    # Synced after the change: viewers see it. Two canvases off: there is nothing to sync.
    with open(log, "a", encoding="utf-8") as more:
        more.write("\n[1:1014/001500.000:INFO:x] [ProgramMode] ButtonPressed OpenProgramView\n")
    assert not layout.studio(log).unsynced()
    with open(log, "a", encoding="utf-8") as more:
        more.write("[1:1014/001600.000:INFO:x] scene 'Scene 2' remove item : '窗口捕捉 5'\n")
        more.write("[1:1014/001700.000:INFO:x] BililiveOBSView::OnLiveProgramModeChanged : 0\n")
    assert not layout.studio(log).unsynced()
    # 直播姬 7.64 writes its times another way.
    old = tmp_path / "old.log"
    old.write_text(
        "[tid:12:2026-10-14/14-39-08:INFO] BililiveOBSView::OnLiveProgramModeChanged : 1\n"
        "[tid:12:2026-10-14/14-40-00:INFO] scene 'Scene 1' add item : 'x'\n",
        encoding="utf-8",
    )
    assert layout.studio(old).edited == "1014 144000" and layout.studio(old).unsynced()
    assert layout.studio(tmp_path / "missing.log").canvas is None
    # Read on as the log grows: a line still being written waits for its end.
    watch = layout.StudioWatch(log)
    assert watch.studio().two_canvas is False
    with open(log, "a", encoding="utf-8") as more:
        more.write("[1:1014/001800.000:INFO:x] BililiveOBSView::OnLiveProgramModeChanged : 1")
    assert watch.studio().two_canvas is False
    with open(log, "a", encoding="utf-8") as more:
        more.write("\n")
    assert watch.studio().two_canvas is True
