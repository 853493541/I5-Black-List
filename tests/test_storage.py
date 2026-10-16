import json
import os
import stat
import sys

import pytest

from blacklist_detect.paths import app_dir
from blacklist_detect.storage import Store


def test_an_import_adds_each_name_once(tmp_path):
    from blacklist_detect.storage import TAGS

    assert TAGS == ("炸房", "贴脸", "挂机", "场外", "不尊重底牌")
    store = Store(tmp_path)
    store.add("纪戴宁")
    rows = [("纪戴宁", (), "", 0), ("庄园美女", (), "", -1), ("无害虎皮", (), "", -1), ("庄园美女", (), "", -1)]
    assert store.import_rows(rows) == (2, 1)
    assert [entry.name for entry in Store(tmp_path).entries] == ["纪戴宁", "庄园美女", "无害虎皮"]
    store.clear_entries()
    assert Store(tmp_path).entries == []


def test_windows_and_linux_dirs():
    windows = app_dir("win32", {"APPDATA": "/tmp/roaming"})
    assert windows.as_posix() == "/tmp/roaming/BlackListDetect"
    linux = app_dir("linux", {"XDG_CONFIG_HOME": "/tmp/zhibin-config"})
    assert linux.as_posix() == "/tmp/zhibin-config/BlackListDetect"


def test_a_custom_tag_is_remembered(tmp_path):
    from blacklist_detect.importing import read_paste

    store = Store(tmp_path)
    assert store.add_custom_tag("红名") is True
    assert store.add_custom_tag("红名") is False
    assert store.add_custom_tag("炸房") is False
    store.add("甲", tags=("红名", "贴脸"), reason="说明")
    again = Store(tmp_path)
    assert again.custom_tags == ["红名"]
    assert again.entries[0].tags == ("贴脸", "红名")
    assert again.tag_catalog() == ("炸房", "贴脸", "挂机", "场外", "不尊重底牌", "红名")
    assert read_paste("乙，红名，他做了坏事", again.tag_catalog()) == [("乙", ("红名",), "他做了坏事")]
    assert again.remove_custom_tag("红名") is True
    saved = Store(tmp_path)
    assert saved.custom_tags == []
    assert saved.entries[0].tags == ("贴脸",)
    saved.add("乙", tags=("炸房", "挂机"))
    assert saved.remove_custom_tag("炸房") is True
    assert saved.tag_catalog() == ("贴脸", "挂机", "场外", "不尊重底牌")
    assert saved.entries[-1].tags == ("挂机",)
    reloaded = Store(tmp_path)
    assert reloaded.tag_catalog() == ("贴脸", "挂机", "场外", "不尊重底牌")
    assert reloaded.entries[-1].tags == ("挂机",)
    assert reloaded.add_custom_tag("炸房") is True
    reloaded.save_settings()
    assert Store(tmp_path).tag_catalog() == ("炸房", "贴脸", "挂机", "场外", "不尊重底牌")


def test_renaming_a_tag_rewrites_every_name(tmp_path):
    store = Store(tmp_path)
    store.add("甲", tags=("炸房", "贴脸"))
    store.add("乙", tags=("炸房",))
    assert store.rename_tag("炸房", "闹房") == "renamed"
    assert store.rename_tag("闹房", "贴脸") == "taken"
    again = Store(tmp_path)
    assert again.tag_catalog() == ("贴脸", "挂机", "场外", "不尊重底牌", "闹房")
    assert again.entries[0].tags == ("贴脸", "闹房")
    assert again.entries[1].tags == ("闹房",)
    assert again.rename_tag("闹房", "炸房") == "renamed"
    restored = Store(tmp_path)
    assert restored.tag_catalog() == ("炸房", "贴脸", "挂机", "场外", "不尊重底牌")
    assert restored.entries[0].tags == ("炸房", "贴脸")


def test_recheck_adds_a_tag_that_already_sits_in_the_reason(tmp_path):
    store = Store(tmp_path)
    store.add("甲", tags=("炸房",), reason="玩的时候不尊重底牌，还挂机")
    store.add("乙", tags=("贴脸",), reason="没有这些字")
    assert store.recheck_tags() == 1
    again = Store(tmp_path)
    assert again.entries[0].tags == ("炸房", "挂机", "不尊重底牌")
    assert again.entries[0].reason == "玩的时候不尊重底牌，还挂机"
    assert again.entries[1].tags == ("贴脸",)
    assert again.recheck_tags() == 0


def test_reasons_can_be_combined(tmp_path):
    store = Store(tmp_path)
    store.add("甲", tags=("贴脸", "炸房", "其他"), reason="开黑")
    again = Store(tmp_path)
    assert again.entries[0].tags == ("炸房", "贴脸")
    assert again.entries[0].reason == "开黑"
    assert again.update_at(0, "甲", ("炸房",), "") is True
    assert Store(tmp_path).entries[0].tags == ("炸房",)
    assert Store(tmp_path).entries[0].reason == ""


def test_blacklist_roundtrip(tmp_path):
    store = Store(tmp_path)
    added = store.add("  罪玥吉尔曼  ", reason="常挂机")
    assert added is not None
    store.add("无害虎皮…")
    store.hotkey = "Ctrl+F8"
    store.save_settings()

    again = Store(tmp_path)
    assert [entry.name for entry in again.entries] == ["罪玥吉尔曼", "无害虎皮"]
    assert again.entries[0].reason == "常挂机"
    assert again.entries[0].tags == ()
    assert again.hotkey == "Ctrl+F8"
    # 基础模式 and 手动检查 by default.
    assert again.safe_mode is True
    assert again.auto_capture is False
    store.panel_pos = (12, 34)
    store.save_settings()
    assert Store(tmp_path).panel_pos == (12, 34)
    store.consented = ["full", "auto"]
    store.auto_capture = True
    store.save_settings()
    # 自动检查 runs only in 完整模式.
    assert Store(tmp_path).auto_capture is False
    store.safe_mode = False
    store.save_settings()
    assert Store(tmp_path).auto_capture is True
    again.remove_at(0)
    assert [entry.name for entry in Store(tmp_path).entries] == ["无害虎皮"]


def test_scan_history_is_saved_newest_first(tmp_path):
    store = Store(tmp_path)
    assert store.add_scan(
        [{"seat": 3, "name": "纪戴宁", "unclear": False}, {"seat": 12, "name": "", "unclear": True}],
        0.25,
    ) == "added"
    store.scans[0]["at"] = "2020-01-01T00:00:00+00:00"
    store.add_scan([{"seat": 1, "name": "庄园美女", "unclear": False}])
    again = Store(tmp_path)
    assert again.scans[0]["names"][0]["name"] == "庄园美女"
    assert again.scans[1]["names"][0]["name"] == "纪戴宁"
    assert again.scans[1]["names"][1]["unclear"] is True
    assert again.scans[1]["elapsed"] == 0.25
    assert again.contains_name("纪戴宁") is False
    again.add("纪戴宁")
    assert again.contains_name("纪戴宁") is True


def test_same_members_refresh_one_record(tmp_path):
    store = Store(tmp_path)
    store.add_scan(
        [
            {"seat": 1, "name": "纪戴宁", "unclear": False},
            {"seat": 2, "name": "庄园美女...", "unclear": False},
        ]
    )
    store.scans[0]["at"] = "2020-01-01T00:00:00+00:00"
    store.save_scans()
    assert store.add_scan(
        [
            {"seat": 4, "name": "庄园美女", "unclear": False},
            {"seat": 9, "name": "纪戴宁", "unclear": False},
            {"seat": 12, "name": "", "unclear": True},
        ],
        0.4,
    ) == "refreshed"
    again = Store(tmp_path)
    assert len(again.scans) == 1
    assert again.scans[0]["at"] != "2020-01-01T00:00:00+00:00"
    assert again.scans[0]["elapsed"] == 0.4
    assert again.scans[0]["names"][0]["seat"] == 4
    store.scans[0]["at"] = "2020-01-01T00:00:00+00:00"
    store.add_scan([{"seat": 1, "name": "另一个人", "unclear": False}])
    assert len(store.scans) == 2
    assert store.scans[0]["names"][0]["name"] == "另一个人"


def test_a_later_read_of_the_same_lobby_updates_the_time(tmp_path):
    shared = [
        {"seat": seat, "name": name, "unclear": False}
        for seat, name in enumerate(
            ["钻石牛仔裤", "糯米慈楚", "亿萌", "戏剧反讽...", "无序星海...", "囚徒老", "笨蛋讲点理", "狗带俩搏命"],
            start=1,
        )
    ]
    store = Store(tmp_path)
    store.add_scan(
        [
            *shared,
            {"seat": 9, "name": "唯者数值", "unclear": False},
            {"seat": 10, "name": "小珍海味", "unclear": False},
            {"seat": 11, "name": "肥审", "unclear": False},
            {"seat": 12, "name": "", "unclear": True},
        ]
    )
    store.scans[0]["at"] = "2020-01-01T00:00:00+00:00"
    store.save_scans()
    store.add_scan(
        [
            *shared[:5],
            {"seat": 6, "name": "囚徒老公...", "unclear": False},
            *shared[6:],
            {"seat": 9, "name": "咩有数值", "unclear": False},
            {"seat": 10, "name": "山珍海味...", "unclear": False},
            {"seat": 11, "name": "肥审", "unclear": False},
            {"seat": 12, "name": "五人", "unclear": False},
        ]
    )
    again = Store(tmp_path)
    assert len(again.scans) == 1
    assert again.scans[0]["at"] != "2020-01-01T00:00:00+00:00"
    assert again.scans[0]["names"][11]["name"] == "五人"


def test_a_rescan_in_the_same_minute_fills_only_unclear_seats(tmp_path):
    store = Store(tmp_path)
    store.add_scan(
        [
            {"seat": 1, "name": "纪戴宁", "unclear": False},
            {"seat": 2, "name": "", "unclear": True},
        ]
    )
    stamp = store.scans[0]["at"]
    elapsed = store.scans[0]["elapsed"]
    assert store.add_scan(
        [
            {"seat": 1, "name": "纪戴宁", "unclear": False},
            {"seat": 2, "name": "庄园美女", "unclear": False},
        ],
        0.8,
    ) == "filled"
    assert len(store.scans) == 1
    assert store.scans[0]["at"] == stamp
    assert store.scans[0]["elapsed"] == elapsed
    assert store.scans[0]["names"][0]["name"] == "纪戴宁"
    assert store.scans[0]["names"][1]["name"] == "庄园美女"
    assert store.scans[0]["names"][1]["unclear"] is False
    assert store.add_scan(
        [
            {"seat": 1, "name": "完全不同", "unclear": False},
            {"seat": 2, "name": "", "unclear": True},
        ]
    ) == "skipped"
    assert store.scans[0]["names"][0]["name"] == "纪戴宁"


def test_a_second_scan_inside_one_minute_overwrites(tmp_path):
    store = Store(tmp_path)
    assert store.add_scan([{"seat": 1, "name": "纪戴宁", "unclear": False}]) == "added"
    assert store.add_scan([{"seat": 2, "name": "完全不同", "unclear": False}]) == "skipped"
    assert len(store.scans) == 1
    assert store.scans[0]["names"][0]["name"] == "纪戴宁"
    store.scans[0]["at"] = "2020-01-01T00:00:00+00:00"
    store.add_scan([{"seat": 1, "name": "新的一局", "unclear": False}])
    assert len(store.scans) == 2
    assert store.scans[0]["names"][0]["name"] == "新的一局"


def test_history_can_be_deleted_and_cleared(tmp_path):
    store = Store(tmp_path)
    store.add_scan([{"seat": 1, "name": "纪戴宁", "unclear": False}])
    store.scans[0]["at"] = "2020-01-01T00:00:00+00:00"
    store.add_scan([{"seat": 1, "name": "庄园美女", "unclear": False}])
    store.remove_scan(0)
    assert [scan["names"][0]["name"] for scan in store.scans] == ["纪戴宁"]
    store.clear_scans()
    assert Store(tmp_path).scans == []


def test_reset_returns_a_new_application(tmp_path):
    store = Store(tmp_path)
    store.add("甲", reason="常挂机", tags=("炸房",))
    store.add_custom_tag("红名")
    store.hidden_tags.append("贴脸")
    store.player_name = "无害虎皮蛋糕"
    store.hotkey = "Alt+1"
    store.auto_capture = False
    store.theme = "绿色"
    store.column_order = [0, 1, 3, 2]
    store.add_scan([{"seat": 1, "name": "甲", "unclear": False}])
    store.save_settings()
    store.reset()
    again = Store(tmp_path)
    assert again.entries == []
    assert again.scans == []
    assert again.player_name == ""
    assert again.hotkey == "Alt+1"
    assert again.safe_mode is True
    assert again.auto_capture is False
    assert again.theme == "蓝色"
    assert again.custom_tags == []
    assert again.hidden_tags == []
    assert again.tag_catalog() == ("炸房", "贴脸", "挂机", "场外", "不尊重底牌")
    assert again.column_order == [0, 1, 2, 3]


def test_the_same_name_is_not_added_twice(tmp_path):
    store = Store(tmp_path)
    assert store.add("霁玥吉尔曼") is not None
    assert store.add(" 霁玥吉尔曼 ") is None
    assert store.add("★☆★") is None
    assert [entry.name for entry in store.entries] == ["霁玥吉尔曼"]


def test_a_list_file_of_the_wrong_shape_does_not_stop_the_app(tmp_path):
    (tmp_path / "blacklist.json").write_text('{"entries": 5}', encoding="utf-8")
    store = Store(tmp_path)
    assert store.entries == []
    assert "坏了" in store.load_warning
    aside = list(tmp_path.glob("blacklist.unreadable-*.json"))
    assert len(aside) == 1
    assert aside[0].read_text(encoding="utf-8") == '{"entries": 5}'


def test_settings_of_the_wrong_shape_keep_the_defaults(tmp_path):
    (tmp_path / "settings.json").write_text("[1, 2]", encoding="utf-8")
    store = Store(tmp_path)
    assert store.hotkey == "Alt+1"
    assert "设置文件坏了" in store.load_warning


def test_settings_that_cannot_be_read_are_kept_aside_and_the_uploaded_songs_come_back(tmp_path):
    store = Store(tmp_path)
    store.add_scene_song("ice", {"file": _song_wav(store, "ice-1.wav", 1.0), "name": "冰.mp3", "length": 1.0})
    store.add_scene_song("stars", {"file": _song_wav(store, "stars-1.wav", 2.0), "name": "星.mp3", "length": 2.0})
    store.player_name = "心动小鹿"
    store.save_settings()
    whole = store.settings_path.read_text(encoding="utf-8")
    store.settings_path.write_text(whole[: len(whole) // 2], encoding="utf-8")
    back = Store(tmp_path)
    assert "设置文件坏了" in back.load_warning and back.player_name == ""
    aside = list(tmp_path.glob("settings.unreadable-*.json"))
    assert len(aside) == 1 and aside[0].read_text(encoding="utf-8") == whole[: len(whole) // 2]
    assert [song["file"] for song in back.scene_songs("ice")] == ["ice-1.wav"]
    assert [song["file"] for song in back.scene_songs("stars")] == ["stars-1.wav"]
    # Saved again, they stay: the next open lists them from the file.
    back.save_settings()
    again = Store(tmp_path)
    assert again.load_warning == "" and [song["file"] for song in again.scene_songs("stars")] == ["stars-1.wav"]


def test_the_list_is_copied_once_a_day_before_it_changes(tmp_path):
    store = Store(tmp_path)
    store.add("甲")
    assert list((tmp_path / "backups").glob("*.json")) == []
    store.add("乙")
    copies = list((tmp_path / "backups").glob("blacklist-*.json"))
    assert len(copies) == 1
    assert "甲" in copies[0].read_text(encoding="utf-8")
    assert "乙" not in copies[0].read_text(encoding="utf-8")
    store.clear_entries()
    assert len(list((tmp_path / "backups").glob("blacklist-*.json"))) == 1
    for day in range(1, 10):
        (tmp_path / "backups" / f"blacklist-2020-01-{day:02d}.json").write_text("{}", encoding="utf-8")
    (copies[0]).unlink()
    store.add("丙")
    kept = sorted(path.name for path in (tmp_path / "backups").glob("blacklist-*.json"))
    assert len(kept) == 7
    assert kept[0] == "blacklist-2020-01-04.json"


def test_a_shared_list_keeps_custom_tags_and_reasons(tmp_path):
    from blacklist_detect.storage import is_shared, parse_shared, share_text

    sender = Store(tmp_path / "a")
    sender.add("霁玥吉尔曼", reason="开局就炸房，还骂人", tags=("炸房", "开麦骂人"))
    sender.add("gffdsd")
    text = share_text(sender.entries)
    assert text.splitlines()[0] == "#模仿者小工具 黑名单 2人"
    assert is_shared(text)
    rows = parse_shared(text)
    assert rows == [
        ("霁玥吉尔曼", ("炸房", "开麦骂人"), "开局就炸房，还骂人"),
        ("gffdsd", (), ""),
    ]
    friend = Store(tmp_path / "b")
    assert friend.import_rows([(name, tags, reason, -1) for name, tags, reason in rows]) == (2, 0)
    assert friend.entries[0].tags == ("炸房", "开麦骂人")
    assert "开麦骂人" in friend.tag_catalog()
    assert friend.entries[0].reason == "开局就炸房，还骂人"


def test_first_run_is_kept_until_the_guide_is_shown(tmp_path):
    store = Store(tmp_path)
    assert store.first_run is True
    store.theme = "绿色"
    store.save_settings()
    # Saving a setting (the window size on close, say) does not end the first run;
    # showing the welcome guide does.
    assert Store(tmp_path).first_run is True
    store.first_run = False
    store.save_settings()
    again = Store(tmp_path)
    assert again.first_run is False
    assert again.theme == "绿色"


def test_a_settings_file_from_before_counts_as_welcomed(tmp_path):
    (tmp_path / "settings.json").write_text('{"hit_sound": false, "auto_capture": true}', encoding="utf-8")
    store = Store(tmp_path)
    assert store.first_run is False
    # A file from before 基础模式 opens in 基础模式, which checks only on the hotkey.
    assert store.safe_mode is True
    assert store.auto_capture is False


def test_auto_check_needs_no_answer_of_its_own(tmp_path):
    # 自动检查 is not asked about: it is kept with 完整模式 agreed to, and only 基础模式 turns it off.
    store = Store(tmp_path)
    store.consented = ["full"]
    store.safe_mode = False
    store.auto_capture = True
    store.save_settings()
    assert Store(tmp_path).auto_capture is True
    store.safe_mode = True
    store.save_settings()
    assert Store(tmp_path).auto_capture is False


def test_each_level_is_kept_once_agreed_to(tmp_path):
    store = Store(tmp_path)
    assert store.stream_mode == ""
    store.consented = ["full", "auto"]
    store.safe_mode = False
    store.auto_capture = True
    store.stream_mode = "on"
    store.save_settings()
    again = Store(tmp_path)
    assert (again.safe_mode, again.auto_capture) == (False, True)
    assert again.stream_mode == "on"
    # What v0.6.0 and v0.6.1 saved is on.
    for saved in ("key", "alpha"):
        (tmp_path / "settings.json").write_text('{"stream_mode": "%s"}' % saved, encoding="utf-8")
        assert Store(tmp_path).stream_mode == "on"


def test_full_mode_and_auto_checks_need_the_question_answered(tmp_path):
    # Settings saved without it (an older version, or edited by hand) open safe and manual.
    (tmp_path / "settings.json").write_text(
        '{"safe_mode": false, "auto_capture": true, "stream_mode": "nonsense"}', encoding="utf-8"
    )
    store = Store(tmp_path)
    assert (store.safe_mode, store.auto_capture, store.stream_mode) == (True, False, "")


def test_reset_makes_the_next_open_a_first_open(tmp_path):
    store = Store(tmp_path)
    store.first_run = False
    store.env_checked = "v0.2.0"
    store.save_settings()
    store.reset()
    store.window_size = (1000, 700)
    store.save_settings()
    again = Store(tmp_path)
    assert again.first_run is True
    assert again.env_checked == ""


def test_a_snapshot_puts_the_list_back(tmp_path):
    store = Store(tmp_path)
    store.add("甲", tags=("炸房",), reason="说明")
    before = store.snapshot_entries()
    store.clear_entries()
    store.restore_entries(before)
    again = Store(tmp_path)
    assert [(e.name, e.tags, e.reason) for e in again.entries] == [("甲", ("炸房",), "说明")]


def test_an_old_guest_count_setting_is_let_go(tmp_path):
    """嘉宾人数 is gone (嘉宾场景 plays for any 嘉宾): an old settings file's is read past, not saved again."""
    import json

    Store(tmp_path).save_settings()
    path = tmp_path / "settings.json"
    settings = json.loads(path.read_text(encoding="utf-8"))
    settings["love_counts"] = [2, 3]
    path.write_text(json.dumps(settings), encoding="utf-8")
    again = Store(tmp_path)
    again.save_settings()
    assert "love_counts" not in json.loads(path.read_text(encoding="utf-8"))


def _with_settings(root, **saved) -> None:  # noqa: ANN001
    """The settings file as an earlier version left it: these saved over the default ones."""
    import json

    store = Store(root)
    store.save_settings()
    settings = json.loads(store.settings_path.read_text(encoding="utf-8"))
    settings.update(saved)
    store.settings_path.write_text(json.dumps(settings), encoding="utf-8")


def _files(root) -> dict:  # noqa: ANN001
    return {path.name: path.read_bytes() for path in sorted(root.glob("*.json"))}


def test_an_old_scene_switch_turned_off_puts_every_guest_and_combo_on_no_scene(tmp_path):
    """设置 › 嘉宾 › 场景 is gone (v0.9.14 and before). Left off, every 嘉宾 and 组合 is on 不放 instead, their
    ticks dropped, once: the switch is not saved again, the next open changes nothing, and a 嘉宾 added later
    starts on 随机 as ever."""
    import json

    from blacklist_detect.model import ANY_SCENE, Combo, Scenes

    store = Store(tmp_path)
    store.add_like("心动小鹿", scenes=Scenes(("ice", "stars")))
    store.add_like("心动星星")
    store.add_like("示例朋友", scenes=Scenes())
    store.set_combos([Combo(("心动小鹿", "心动星星"), Scenes(("angel",))), Combo(("心动星星", "示例朋友"))])
    _with_settings(tmp_path, love_scene="off", theme="紫色")
    loaded = Store(tmp_path)
    assert [like.scenes for like in loaded.likes] == [Scenes(), Scenes(), Scenes()]
    assert [combo.scenes for combo in loaded.combos] == [Scenes(), Scenes()]
    assert loaded.theme == "紫色" and loaded.load_warning == ""
    assert "love_scene" not in json.loads(loaded.settings_path.read_text(encoding="utf-8"))
    saved = _files(tmp_path)
    again = Store(tmp_path)
    assert _files(tmp_path) == saved and [like.scenes for like in again.likes] == [like.scenes for like in loaded.likes]
    assert again.add_like("新来的嘉宾").scenes == ANY_SCENE
    # Left on, or anything else, nobody's 场景 change; neither does a settings file with no 嘉宾 at all.
    for index, kept in enumerate(("classic", "stars", "random", None, 3, ["off"], "OFF", {"off": True})):
        other = tmp_path / f"kept-{index}"
        Store(other).add_like("心动小鹿", scenes=Scenes(("ice",)))
        _with_settings(other, love_scene=kept)
        assert Store(other).likes[0].scenes == Scenes(("ice",)), kept
    _with_settings(tmp_path / "none", love_scene="off")
    assert Store(tmp_path / "none").likes == [] and not (tmp_path / "none" / "likes.json").exists()


def test_scenes_saved_by_every_version_read_as_ticked_random_or_no_scene(tmp_path):
    """likes.json up to v0.9.14 has no "random": none ticked was any scene (随机 now), "no_scene" true 不放 with
    its ticks dropped; up to v0.9.13 one "theme". Since, "random" as saved, false with none ticked 不放."""
    import json

    from blacklist_detect.model import ANY_SCENE, Scenes

    rows = [
        ({"scenes": [], "no_scene": False}, ANY_SCENE),
        ({"scenes": ["lace", "ice"], "no_scene": False}, Scenes(("lace", "ice"))),
        ({"scenes": ["lace"], "no_scene": True}, Scenes()),
        ({"scenes": [], "no_scene": True}, Scenes()),
        ({"theme": "cyber"}, Scenes(("cyber",))),
        ({"theme": ""}, ANY_SCENE),
        ({}, ANY_SCENE),
        ({"scenes": [], "random": True}, ANY_SCENE),
        ({"scenes": ["lace"], "random": True}, Scenes(("lace",), random=True)),
        ({"scenes": ["lace"], "random": False}, Scenes(("lace",))),
        ({"scenes": [], "random": False}, Scenes()),
        ({"scenes": [], "random": False, "no_scene": False}, Scenes()),
        ({"scenes": [], "random": "yes"}, Scenes()),
    ]
    likes = [{"name": f"嘉宾{index}", **saved} for index, (saved, _read) in enumerate(rows)]
    (tmp_path / "likes.json").write_text(json.dumps({"likes": likes}), encoding="utf-8")
    loaded = Store(tmp_path)
    for (saved, read), like in zip(rows, loaded.likes, strict=True):
        assert like.scenes == read, saved
    # Saved back, each reads the same, and a 不放 one also says "no_scene" for v0.9.14.
    loaded.save_likes()
    assert [like.scenes for like in Store(tmp_path).likes] == [read for _saved, read in rows]
    written = json.loads((tmp_path / "likes.json").read_text(encoding="utf-8"))["likes"]
    assert written[0] == {"name": "嘉宾0", "nickname": "", "reason": "", "added_at": "", "scenes": [], "random": True, "no_scene": False}
    assert [(like["scenes"], like["random"], like["no_scene"]) for like in written[1:4]] == [
        (["lace", "ice"], False, False), ([], False, True), ([], False, True),
    ]  # fmt: skip


def test_a_file_saved_now_reads_the_same_in_v0_9_14(tmp_path):
    """Rolled back, v0.9.14 reads "scenes" and "no_scene": 随机 and ticked ones as they were, 不放 as 不放."""
    import json

    from blacklist_detect.model import ANY_SCENE, Combo, Scenes

    store = Store(tmp_path)
    store.add_like("心动小鹿", scenes=Scenes(("ice",)))
    store.add_like("心动星星")
    store.add_like("示例朋友", scenes=Scenes())
    store.set_combos([Combo(("心动小鹿", "心动星星"), Scenes())])
    data = json.loads((tmp_path / "likes.json").read_text(encoding="utf-8"))
    old = [(like["scenes"], like["no_scene"]) for like in data["likes"]]
    assert old == [(["ice"], False), ([], False), ([], True)]
    assert (data["combos"][0]["scenes"], data["combos"][0]["no_scene"]) == ([], True)
    assert store.likes[1].scenes == ANY_SCENE


def test_me_has_scenes_of_its_own_kept_by_clearing_the_list_but_not_by_reset(tmp_path):
    """我: none (不放) until set, saved in likes.json beside 嘉宾; 清空嘉宾列表 keeps it, 清空数据 does not."""
    import json

    from blacklist_detect.model import ANY_SCENE, Scenes

    store = Store(tmp_path)
    assert store.me == Scenes() and Store(tmp_path).me == Scenes()
    store.set_me(Scenes(("lace", "ice")))
    assert Store(tmp_path).me == Scenes(("lace", "ice"))
    me = json.loads((tmp_path / "likes.json").read_text(encoding="utf-8"))["me"]
    assert me == {"scenes": ["lace", "ice"], "random": False, "no_scene": False}
    store.set_me(ANY_SCENE)
    assert Store(tmp_path).me == ANY_SCENE
    store.add_like("心动小鹿")
    store.clear_likes()
    assert Store(tmp_path).me == ANY_SCENE and Store(tmp_path).likes == []
    store.reset()
    assert store.me == Scenes() and Store(tmp_path).me == Scenes()
    # Saved before 我 had any (v0.9.14), or not one: none.
    for saved in ({"likes": []}, {"me": "lace"}, {"me": None}):
        (tmp_path / "likes.json").write_text(json.dumps(saved), encoding="utf-8")
        assert Store(tmp_path).me == Scenes(), saved
    (tmp_path / "likes.json").write_text(json.dumps({"me": {"scenes": ["cyber"], "no_scene": False}}), encoding="utf-8")
    assert Store(tmp_path).me == Scenes(("cyber",))


def test_the_old_sound_volume_is_folded_into_every_scene_s_own_once(tmp_path):
    """设置 › 声音's slider is gone (v0.9.14 and before): below 100 it is taken into every 场景's own 音量 once, down to
    a step of 5 so nothing is louder, below 5 as it was heard (never 0 when both were above 0), and is not saved again."""
    import json

    from blacklist_detect import love_scenes
    from blacklist_detect.paths import custom_sound_dir

    own = _own_sound(Store(tmp_path), "neon")
    sounds = {
        "ice": {"volume": 100},
        "stars": {"volume": 50},
        "neon": {"volume": 100, "file": own, "name": "我的声音.mp3"},
        "future": {"volume": 40},
    }
    _with_settings(tmp_path, sound_volume=60, scene_sounds=sounds, theme="紫色")
    loaded = Store(tmp_path)
    assert loaded.load_warning == "" and loaded.theme == "紫色"
    expected = {key: {"volume": 60} for key in love_scenes.KEYS}
    song = {"file": own, "name": "我的声音.mp3"}
    expected.update(stars={"volume": 30}, neon={"volume": 60, "songs": [song], "chosen": own}, future={"volume": 20})
    assert loaded.scene_sounds == expected
    assert loaded.scene_sound("neon") == (custom_sound_dir(tmp_path) / own, 60) and loaded.scene_sound("cyber") == (None, 60)
    settings = json.loads(loaded.settings_path.read_text(encoding="utf-8"))
    assert "sound_volume" not in settings and settings["scene_sounds"] == {**expected, "neon": {**expected["neon"], **song}}
    saved = _files(tmp_path)
    assert Store(tmp_path).scene_sounds == expected and _files(tmp_path) == saved
    # Down to a step of 5; below 5 what was heard (5% of 5% played at 1%), kept so the next open; 0 for every
    # 场景 at 声音 0, and for a 场景 at 0.
    cases = ((55, 50, 25, 55), (95, 5, 5, 95), (5, 5, 1, 5), (10, 5, 1, 10), (30, 15, 4, 30), (0, 100, 0, 0), (60, 0, 0, 60),
             (73.4, 100, 75, 75))
    for volume, own_volume, now, rest in cases:
        other = tmp_path / f"{volume}-{own_volume}"
        _with_settings(other, sound_volume=volume, scene_sounds={"ice": {"volume": own_volume}})
        folded = Store(other).scene_sounds
        assert (folded["ice"], folded["stars"]) == ({"volume": now}, {"volume": rest}), (volume, own_volume)
        assert Store(other).scene_sound("ice") == (None, now), (volume, own_volume)
    # At 100, none saved, or none at all (not a number, out of 0-100): as it was, the file not even written again.
    for index, kept in enumerate((100, None, "50", True, -5, 120, [60], {"x": 1})):
        other = tmp_path / f"kept-{index}"
        _with_settings(other, sound_volume=kept, scene_sounds={"stars": {"volume": 50}})
        saved = _files(other)
        assert Store(other).scene_sounds == {"stars": {"volume": 50}} and _files(other) == saved, kept


def test_no_folded_volume_plays_louder_than_v0_9_14_played_it():
    """Every 声音 and 场景 音量 the sliders had: the 音量 folded in is never above what v0.9.14 played (声音 times
    音量, 1% at least when both were above 0), and below 5 it is exactly that."""
    from blacklist_detect.storage import _folded

    for sound in range(0, 101, 5):
        for own in range(0, 101, 5):
            played = round(sound * own / 100)
            played = max(played, 1) if sound > 0 and own > 0 else played
            folded = _folded(own, sound)
            assert folded <= played and (folded == played if played < 5 else folded % 5 == 0), (sound, own)
            assert (folded > 0) == (played > 0), (sound, own)


def test_old_settings_that_cannot_be_saved_are_folded_again_the_next_open(tmp_path, monkeypatch):
    """A settings file that cannot be written: 声音 and 嘉宾 › 场景 are folded in for this open all the same,
    and again the next, the same."""
    from blacklist_detect import storage
    from blacklist_detect.model import Scenes

    Store(tmp_path).add_like("心动小鹿", scenes=Scenes(("ice",)))
    _with_settings(tmp_path, sound_volume=50, love_scene="off")
    saved = _files(tmp_path)

    def refuse(path, payload) -> None:  # noqa: ANN001
        raise OSError("read-only")

    monkeypatch.setattr(storage, "_atomic_write", refuse)
    loaded = Store(tmp_path)
    assert loaded.scene_sound("ice")[1] == 50 and loaded.likes[0].scenes == Scenes()
    assert _files(tmp_path) == saved
    monkeypatch.undo()
    again = Store(tmp_path)
    assert again.scene_sound("ice")[1] == 50 and again.likes[0].scenes == Scenes()
    assert Store(tmp_path).scene_sound("ice")[1] == 50


def test_a_broken_settings_file_folds_nothing_in(tmp_path):
    """A settings file that cannot be read whole is set aside as it was, not written over for the old 声音 or
    嘉宾 › 场景."""
    from blacklist_detect.model import Scenes

    Store(tmp_path).add_like("心动小鹿", scenes=Scenes(("ice",)))
    store = Store(tmp_path)
    store.settings_path.write_text('{"sound_volume": 50, "love_scene": "off", "custom_tags": 5}', encoding="utf-8")
    saved = _files(tmp_path)
    loaded = Store(tmp_path)
    assert loaded.load_warning and loaded.likes[0].scenes == Scenes(("ice",)) and loaded.scene_sound("ice")[1] == 100
    files = _files(tmp_path)
    aside = [name for name in files if name.startswith("settings.unreadable-")]
    assert len(aside) == 1 and files.pop(aside[0]) == saved.pop("settings.json") and files == saved


def test_a_saved_hotkey_of_three_keys_keeps_two(tmp_path):
    import json

    root = tmp_path / "BlackListDetect"
    root.mkdir()
    (root / "settings.json").write_text(json.dumps({"hotkey": "Ctrl+Alt+F11"}), encoding="utf-8")
    assert Store(root).hotkey == "Ctrl+F11"
    (root / "settings.json").write_text(json.dumps({"hotkey": "Alt+1"}), encoding="utf-8")
    assert Store(root).hotkey == "Alt+1"


def test_reminding_about_one_list_only_is_gone(tmp_path):
    """检查 › 提醒 could leave 黑名单 or 嘉宾 out up to v0.9.14: what it saved is not read, and not saved again."""
    import json

    (tmp_path / "settings.json").write_text(json.dumps({"check_blacklist": False, "check_likes": True}), encoding="utf-8")
    store = Store(tmp_path)
    assert not hasattr(store, "check_blacklist") and not hasattr(store, "check_likes")
    store.save_settings()
    settings = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert "check_blacklist" not in settings and "check_likes" not in settings


def test_mute_is_kept_and_reset(tmp_path):
    """设置 › 声音 › 静音: off at first, kept as set, off again after 清空数据; only true is on."""
    import json

    store = Store(tmp_path)
    assert store.sound_muted is False
    store.sound_muted = True
    store.save_settings()
    assert Store(tmp_path).sound_muted is True
    path = tmp_path / "settings.json"
    settings = json.loads(path.read_text(encoding="utf-8"))
    assert "sound_volume" not in settings and "love_scene" not in settings
    settings["sound_muted"] = "yes"
    path.write_text(json.dumps(settings), encoding="utf-8")
    assert Store(tmp_path).sound_muted is False
    store.reset()
    assert store.sound_muted is False and Store(tmp_path).sound_muted is False


def _own_sound(store: Store, key: str) -> str:
    """A player's own sound for a 场景 in custom_sounds: <key>.wav as up to v0.9.15, <key>-<n>.wav since."""
    from blacklist_detect.paths import custom_sound_dir

    folder = custom_sound_dir(store.root)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{key}.wav").write_bytes(b"RIFF")
    return f"{key}.wav"


def test_each_effect_s_volume_and_own_sound_are_kept_and_cleared(tmp_path):
    """场景管理: each 场景's own 音量 and the player's songs for it, one chosen, kept as set; a 场景 left as it was
    (100%, no songs) is not saved. 清空数据 drops them, the sounds' folder too."""
    import json

    from blacklist_detect.paths import custom_sound_dir

    store = Store(tmp_path)
    assert store.scene_sounds == {} and store.scene_sound("ice") == (None, 100)
    store.set_scene_volume("ice", 60)
    store.set_scene_volume("stars", 100)
    store.add_scene_song("classic", {"file": _own_sound(store, "classic-1"), "name": "生日歌.mp3", "start": 12.5, "length": 5.0})
    saved = json.loads(store.settings_path.read_text(encoding="utf-8"))["scene_sounds"]
    assert set(saved) == {"ice", "classic"}
    again = Store(tmp_path)
    assert again.scene_sounds == {"ice": {"volume": 60}, "classic": store.scene_sounds["classic"]}
    assert again.scene_sound("ice") == (None, 60)
    assert again.scene_sound("classic") == (custom_sound_dir(tmp_path) / "classic-1.wav", 100)
    assert again.scene_sound("stars") == (None, 100)
    # A song whose file is gone is gone, 默认 playing if it was chosen; its 音量 stays.
    again.set_scene_volume("ice", 45)
    again.add_scene_song("ice", {"file": _own_sound(again, "ice-1"), "name": "a.wav"})
    (custom_sound_dir(tmp_path) / "ice-1.wav").unlink()
    assert Store(tmp_path).scene_sounds["ice"] == {"volume": 45}
    again.reset()
    assert again.scene_sounds == {} and Store(tmp_path).scene_sounds == {}
    assert not custom_sound_dir(tmp_path).exists()
    # The folder kept apart from the quieter copies' (sounds/), whose files go as new ones are made.
    assert custom_sound_dir(tmp_path).name == "custom_sounds"


def test_a_scene_keeps_up_to_three_songs_one_chosen(tmp_path):
    """Songs are added oldest first, each the one chosen as it comes; a choice is any of them or "" (默认); one
    deleted is gone from the list, 默认 chosen if it was; the last deleted leaves the 音量 alone. Each saved."""
    store = Store(tmp_path)
    store.set_scene_volume("ice", 70)
    files = [_own_sound(store, f"ice-{n}") for n in (1, 2, 3)]
    for number, file in enumerate(files):
        store.add_scene_song("ice", {"file": file, "name": f"{number}.mp3", "start": 0.0, "length": 5.0})
    assert [song["file"] for song in store.scene_songs("ice")] == files and store.scene_sounds["ice"]["chosen"] == "ice-3.wav"
    assert store.scene_sound("ice")[0].name == "ice-3.wav" and Store(tmp_path).scene_sound("ice")[0].name == "ice-3.wav"
    store.choose_scene_song("ice", "ice-1.wav")
    assert store.scene_sound("ice")[1] == 70 and store.scene_sound("ice")[0].name == "ice-1.wav"
    store.choose_scene_song("ice", "not-a-song.wav")
    assert store.scene_sound("ice")[0] is None and Store(tmp_path).scene_sounds["ice"]["chosen"] == ""
    store.choose_scene_song("ice", "ice-2.wav")
    # Deleting one not chosen leaves the choice; deleting the chosen one falls back to 默认.
    store.remove_scene_song("ice", "ice-1.wav")
    assert store.scene_sound("ice")[0].name == "ice-2.wav"
    store.remove_scene_song("ice", "ice-2.wav")
    assert store.scene_sound("ice") == (None, 70) and [song["file"] for song in store.scene_songs("ice")] == ["ice-3.wav"]
    assert Store(tmp_path).scene_sounds["ice"] == {"volume": 70, "songs": store.scene_songs("ice"), "chosen": ""}
    store.remove_scene_song("ice", "ice-3.wav")
    assert store.scene_sounds["ice"] == {"volume": 70} and Store(tmp_path).scene_sounds["ice"] == {"volume": 70}
    # A scene at 100% with no songs left has no entry; choosing among none changes nothing.
    store.add_scene_song("stars", {"file": _own_sound(store, "stars-1"), "name": "a.mp3"})
    store.remove_scene_song("stars", "stars-1.wav")
    store.choose_scene_song("stars", "")
    assert "stars" not in store.scene_sounds and "stars" not in Store(tmp_path).scene_sounds


def test_songs_are_read_checked_three_at_most_and_a_chosen_one_that_is_none_is_the_default(tmp_path):
    import json

    store = Store(tmp_path)
    store.save_settings()
    files = [_own_sound(store, f"lace-{n}") for n in (1, 2, 3, 4)]
    settings = json.loads(store.settings_path.read_text(encoding="utf-8"))
    settings["scene_sounds"] = {
        # A fourth song is past the most, a file twice is once, one not there and one with a path are none.
        "lace": {"volume": 80, "songs": [{"file": "gone.wav"}, *({"file": file, "name": file} for file in files), {"file": files[0]}],
                 "chosen": files[3]},  # fmt: skip
        "ice": {"songs": [{"file": "../" + files[0]}, "x", 3], "chosen": "../" + files[0]},
        "stars": {"songs": "x", "chosen": files[0]},
        "cyber": {"songs": [{"file": files[1], "name": "b", "start": 2.0, "length": 4.5}], "chosen": files[1], "file": files[0]},
    }
    store.settings_path.write_text(json.dumps(settings), encoding="utf-8")
    loaded = Store(tmp_path)
    assert loaded.load_warning == ""
    assert [song["file"] for song in loaded.scene_songs("lace")] == files[:3] and loaded.scene_sounds["lace"]["chosen"] == ""
    assert "ice" not in loaded.scene_sounds and "stars" not in loaded.scene_sounds
    # The copy of the chosen one beside the songs is read from the songs, never on its own.
    assert loaded.scene_sounds["cyber"] == {
        "volume": 100, "songs": [{"file": files[1], "name": "b", "start": 2.0, "length": 4.5}], "chosen": files[1]
    }  # fmt: skip


def test_an_old_single_sound_becomes_the_chosen_song_and_the_chosen_one_is_saved_for_rollback(tmp_path):
    """Up to v0.9.15 a 场景 had one sound of the player's, "file": it becomes its only song, chosen. Saved, the
    chosen song's file, name, start and length are written beside the songs too, as v0.9.15 reads them; with
    默认 chosen, none."""
    import json

    store = Store(tmp_path)
    store.save_settings()
    own = _own_sound(store, "angel")
    settings = json.loads(store.settings_path.read_text(encoding="utf-8"))
    settings["scene_sounds"] = {"angel": {"volume": 55, "file": own, "name": "生日歌.mp3", "start": 3.0, "length": 5.0}}
    store.settings_path.write_text(json.dumps(settings), encoding="utf-8")
    loaded = Store(tmp_path)
    song = {"file": own, "name": "生日歌.mp3", "start": 3.0, "length": 5.0}
    assert loaded.scene_sounds["angel"] == {"volume": 55, "songs": [song], "chosen": own}
    assert loaded.scene_sound("angel")[0].name == "angel.wav"
    loaded.add_scene_song("angel", {"file": _own_sound(loaded, "angel-1"), "name": "新歌.mp3", "start": 0.0, "length": 4.0})
    saved = json.loads(loaded.settings_path.read_text(encoding="utf-8"))["scene_sounds"]["angel"]
    assert (saved["file"], saved["name"], saved["start"], saved["length"]) == ("angel-1.wav", "新歌.mp3", 0.0, 4.0)
    assert saved["chosen"] == "angel-1.wav" and [song["file"] for song in saved["songs"]] == ["angel.wav", "angel-1.wav"]
    loaded.choose_scene_song("angel", "")
    saved = json.loads(loaded.settings_path.read_text(encoding="utf-8"))["scene_sounds"]["angel"]
    assert "file" not in saved and saved["chosen"] == "" and len(saved["songs"]) == 2 and saved["volume"] == 55
    assert Store(tmp_path).scene_sounds == loaded.scene_sounds


def _song_wav(store: Store, file: str, seconds: float) -> str:
    """A silent WAV of seconds in custom_sounds, as a song kept for a 场景."""
    import wave

    from blacklist_detect.paths import custom_sound_dir

    folder = custom_sound_dir(store.root)
    folder.mkdir(parents=True, exist_ok=True)
    with wave.open(str(folder / file), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\0\0" * round(seconds * 8000))
    return file


def test_songs_v0_9_15_left_out_as_it_saved_come_back(tmp_path):
    """v0.9.15 saves a 场景's chosen song only, as "file", and none with 默认 chosen: after it, the songs it left
    out of the list (<key>-<n>.wav) come back by n, named by their file, the chosen one still chosen. Never
    after this version saved: a file it could not delete stays out."""
    import json

    store = Store(tmp_path)
    for n in (1, 2, 3):
        store.add_scene_song("stars", {"file": _song_wav(store, f"stars-{n}.wav", n), "name": f"{n}.mp3", "start": 0.0, "length": n})
    store.add_scene_song("ice", {"file": _song_wav(store, "ice-1.wav", 2.0), "name": "冰.mp3", "length": 2.0})
    store.choose_scene_song("stars", "stars-2.wav")
    store.choose_scene_song("ice", "")
    _song_wav(store, "lace-1.wav", 1.0)
    assert "lace" not in Store(tmp_path).scene_sounds
    # As v0.9.15 saves it.
    settings = json.loads(store.settings_path.read_text(encoding="utf-8"))
    del settings["scene_songs"]
    settings["scene_sounds"] = {"stars": {"volume": 80, "file": "stars-2.wav", "name": "2.mp3", "start": 0.0, "length": 2.0}}
    store.settings_path.write_text(json.dumps(settings), encoding="utf-8")
    back = Store(tmp_path)
    assert back.scene_sounds["stars"] == {
        "volume": 80,
        "songs": [{"file": "stars-1.wav", "name": "", "length": 1.0}, {"file": "stars-2.wav", "name": "2.mp3", "start": 0.0, "length": 2.0},
                  {"file": "stars-3.wav", "name": "", "length": 3.0}],
        "chosen": "stars-2.wav",
    }  # fmt: skip
    assert back.scene_sounds["ice"] == {"volume": 100, "songs": [{"file": "ice-1.wav", "name": "", "length": 2.0}], "chosen": ""}
    assert back.scene_sounds["lace"]["chosen"] == ""
    # A song of v0.9.15's own (<key>.wav) first; past MAX_SONGS the last are left out, never the chosen.
    _song_wav(store, "neon-1.wav", 1.0)
    _song_wav(store, "neon-2.wav", 1.0)
    _song_wav(store, "neon-3.wav", 1.0)
    settings["scene_sounds"] = {"neon": {"file": _song_wav(store, "neon.wav", 1.0), "name": "旧.mp3"}}
    store.settings_path.write_text(json.dumps(settings), encoding="utf-8")
    neon = Store(tmp_path).scene_sounds["neon"]
    assert [song["file"] for song in neon["songs"]] == ["neon.wav", "neon-1.wav", "neon-2.wav"] and neon["chosen"] == "neon.wav"


def test_a_song_past_three_takes_the_oldest_s_file_with_it(tmp_path):
    from blacklist_detect.paths import custom_sound_dir

    store = Store(tmp_path)
    for n in (1, 2, 3, 4):
        store.add_scene_song("ice", {"file": _song_wav(store, f"ice-{n}.wav", 1.0), "name": f"{n}.mp3"})
    assert [song["file"] for song in store.scene_songs("ice")] == ["ice-2.wav", "ice-3.wav", "ice-4.wav"]
    assert not (custom_sound_dir(tmp_path) / "ice-1.wav").exists() and (custom_sound_dir(tmp_path) / "ice-2.wav").exists()


def test_bad_effect_sounds_are_dropped_and_the_other_settings_kept(tmp_path):
    """A 场景管理 entry that is no sound is dropped by itself: the rest of 设置 is as saved. A volume that is
    none is 100%, a file named with a path (or not there) is none, a key this version does not know is kept
    for the version that does."""
    import json

    store = Store(tmp_path)
    store.theme = "紫色"
    own = _own_sound(store, "neon")
    store.save_settings()
    elsewhere = tmp_path / "elsewhere.wav"
    elsewhere.write_bytes(b"RIFF")
    settings = json.loads(store.settings_path.read_text(encoding="utf-8"))
    for garbage in ("loud", [1, 2], 7, None):
        settings["scene_sounds"] = garbage
        store.settings_path.write_text(json.dumps(settings), encoding="utf-8")
        loaded = Store(tmp_path)
        assert (loaded.scene_sounds, loaded.load_warning, loaded.theme) == ({}, "", "紫色"), garbage
    settings["scene_sounds"] = {
        "ice": "loud",
        "stars": {"volume": "x"},
        "cyber": {"volume": 55, "file": 3},
        "neon": {"volume": True, "file": own, "name": 9, "start": "a", "length": -1},
        "lace": {"volume": 72, "file": "lace.wav"},
        "fluffy": {"volume": 30, "file": "../neon.wav"},
        "claw": {"volume": 30, "file": "..\\custom_sounds\\" + own},
        "equation": {"volume": 30, "file": str(elsewhere)},
        "angel": {"volume": 30, "file": f"C:{own}"},
        "future": {"volume": 25},
        "": {"volume": 25},
    }
    store.settings_path.write_text(json.dumps(settings), encoding="utf-8")
    loaded = Store(tmp_path)
    assert (loaded.load_warning, loaded.theme) == ("", "紫色")
    assert loaded.scene_sounds == {
        "cyber": {"volume": 55},
        "neon": {"volume": 100, "songs": [{"file": own, "name": ""}], "chosen": own},
        "lace": {"volume": 70},
        "fluffy": {"volume": 30},
        "claw": {"volume": 30},
        "equation": {"volume": 30},
        "angel": {"volume": 30},
        "future": {"volume": 25},
    }
    loaded.save_settings()
    assert Store(tmp_path).scene_sounds == loaded.scene_sounds


def test_a_replaced_effect_s_sound_is_its_replacement_s(tmp_path):
    """香槟's 音量 and sound are 天使's, which replaced it, unless 天使 has its own."""
    import json

    store = Store(tmp_path)
    store.save_settings()
    settings = json.loads(store.settings_path.read_text(encoding="utf-8"))
    settings["scene_sounds"] = {"champagne": {"volume": 40}}
    store.settings_path.write_text(json.dumps(settings), encoding="utf-8")
    assert Store(tmp_path).scene_sounds == {"angel": {"volume": 40}}
    for both in ({"champagne": {"volume": 40}, "angel": {"volume": 80}}, {"angel": {"volume": 80}, "champagne": {"volume": 40}}):
        settings["scene_sounds"] = both
        store.settings_path.write_text(json.dumps(settings), encoding="utf-8")
        assert Store(tmp_path).scene_sounds == {"angel": {"volume": 80}}


def _read_only(path):
    os.chmod(path, stat.S_IREAD)


def _writable(path):
    os.chmod(path, stat.S_IREAD | stat.S_IWRITE)


def test_a_tag_found_at_open_that_cannot_be_saved_still_opens_the_app_with_the_list(tmp_path):
    entries = {"entries": [{"name": "示例坏人", "tags": ["红名"]}]}
    (tmp_path / "blacklist.json").write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    settings = tmp_path / "settings.json"
    settings.write_text("{}", encoding="utf-8")
    _read_only(settings)
    try:
        store = Store(tmp_path)
    finally:
        _writable(settings)
    assert [(entry.name, entry.tags) for entry in store.entries] == [("示例坏人", ("红名",))]
    assert "红名" in store.custom_tags and store.load_warning == ""
    assert Store(tmp_path).custom_tags == ["红名"]


def test_a_hidden_tag_that_cannot_be_dropped_from_the_list_file_still_opens_the_app(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({"hidden_tags": ["贴脸"]}, ensure_ascii=False), encoding="utf-8")
    listed = tmp_path / "blacklist.json"
    listed.write_text(json.dumps({"entries": [{"name": "示例坏人", "tags": ["贴脸"]}]}, ensure_ascii=False), encoding="utf-8")
    _read_only(listed)
    try:
        store = Store(tmp_path)
    finally:
        _writable(listed)
    assert [(entry.name, entry.tags) for entry in store.entries] == [("示例坏人", ())]
    assert "贴脸" in json.loads(listed.read_text(encoding="utf-8"))["entries"][0]["tags"]


def test_a_check_keeps_its_record_when_the_history_file_cannot_be_written(tmp_path):
    store = Store(tmp_path)
    store.add_scan([{"seat": 1, "name": "示例坏人", "unclear": False}])
    history = tmp_path / "history.json"
    store.scans[0]["at"] = "2020-01-01T00:00:00+00:00"
    _read_only(history)
    try:
        assert store.add_scan([{"seat": 2, "name": "心动小鹿", "unclear": False}]) == "added"
        assert [scan["names"][0]["name"] for scan in store.scans] == ["心动小鹿", "示例坏人"]
        assert len(Store(tmp_path).scans) == 1
    finally:
        _writable(history)


def test_two_broken_files_both_say_so(tmp_path):
    (tmp_path / "settings.json").write_text("{", encoding="utf-8")
    (tmp_path / "likes.json").write_text("", encoding="utf-8")
    (tmp_path / "blacklist.json").write_text("[", encoding="utf-8")
    warning = Store(tmp_path).load_warning
    assert "设置文件坏了" in warning and "嘉宾文件坏了" in warning and "黑名单文件坏了" in warning
    assert warning.count("；") == 2


def test_a_cut_short_history_file_is_kept_aside_and_said(tmp_path):
    history = tmp_path / "history.json"
    history.write_text('{"scans": [{"at": "2020-01-01T00:00:00+00:00", "names": [{"seat": 1, "na', encoding="utf-8")
    store = Store(tmp_path)
    assert store.scans == []
    assert store.load_warning == "记录文件坏了，已备份，先用空记录"
    aside = list(tmp_path.glob("history.unreadable-*.json"))
    assert len(aside) == 1 and aside[0].read_text(encoding="utf-8").startswith('{"scans"')
    for broken in ("", '{"scans": [{"names": [{"seat": "一"}]}]}'):
        history.write_text(broken, encoding="utf-8")
        assert "记录文件坏了" in Store(tmp_path).load_warning, broken


def _held(path):
    """The file open in another program that shares it with no one, as a backup or sync tool may hold it."""
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.restype = wintypes.HANDLE
    handle = kernel.CreateFileW(str(path), 0x80000000, 0, None, 3, 0, None)
    assert handle != wintypes.HANDLE(-1).value, ctypes.get_last_error()
    return lambda: kernel.CloseHandle(wintypes.HANDLE(handle))


@pytest.mark.skipif(sys.platform != "win32", reason="a file held open without sharing is Windows'")
def test_a_file_held_by_another_program_is_not_said_to_be_broken_nor_saved_over(tmp_path):
    history = tmp_path / "history.json"
    scans = {"scans": [{"at": "2020-01-01T00:00:00+00:00", "names": [{"seat": 1, "name": "心动星星"}]}]}
    history.write_text(json.dumps(scans, ensure_ascii=False), encoding="utf-8")
    blacklist = tmp_path / "blacklist.json"
    blacklist.write_text(json.dumps({"entries": [{"name": "示例坏人"}]}, ensure_ascii=False), encoding="utf-8")
    releases = [_held(history), _held(blacklist)]
    try:
        store = Store(tmp_path)
    finally:
        for release in releases:
            release()
    assert store.scans == [] and store.entries == []
    assert store.load_warning == "黑名单文件读不了，这次改动不保存；记录文件读不了，这次记录不保存"
    # The hold over, what is done in this run waits for the next open: the files are as they were.
    store.add("心动小鹿")
    store.add_scan([{"seat": 1, "name": "心动小鹿"}])
    assert not list(tmp_path.glob("*.unreadable-*")) and json.loads(history.read_text(encoding="utf-8")) == scans
    assert [entry.name for entry in Store(tmp_path).entries] == ["示例坏人"]


def test_a_broken_file_that_cannot_be_set_aside_is_not_said_to_be_backed_up(tmp_path, monkeypatch):
    from blacklist_detect import storage

    for name in ("settings.json", "blacklist.json", "likes.json", "history.json"):
        (tmp_path / name).write_text("{", encoding="utf-8")
    monkeypatch.setattr(storage, "_set_aside", lambda _path: None)
    store = Store(tmp_path)
    assert store.entries == [] and store.likes == [] and store.scans == []
    assert "已备份" not in store.load_warning and store.load_warning.count("读不了") == 4
    store.save_entries(), store.save_likes(), store.save_settings(), store.save_scans()
    files = ("settings.json", "blacklist.json", "likes.json", "history.json")
    assert all((tmp_path / name).read_text(encoding="utf-8") == "{" for name in files), "not saved over"
    monkeypatch.undo()
    assert Store(tmp_path).load_warning.count("已备份") == 4


def test_files_saved_with_a_bom_are_read(tmp_path):
    bom = b"\xef\xbb\xbf"
    (tmp_path / "blacklist.json").write_bytes(bom + json.dumps({"entries": [{"name": "示例坏人"}]}).encode("utf-8"))
    (tmp_path / "likes.json").write_bytes(bom + json.dumps({"likes": [{"name": "心动小鹿"}]}).encode("utf-8"))
    (tmp_path / "settings.json").write_bytes(bom + json.dumps({"theme": "紫色"}).encode("utf-8"))
    scans = {"scans": [{"at": "2020-01-01T00:00:00+00:00", "names": [{"seat": 1, "name": "心动星星"}]}]}
    (tmp_path / "history.json").write_bytes(bom + json.dumps(scans).encode("utf-8"))
    store = Store(tmp_path)
    assert store.load_warning == ""
    assert [entry.name for entry in store.entries] == ["示例坏人"]
    assert [like.name for like in store.likes] == ["心动小鹿"]
    assert store.theme == "紫色" and store.scans[0]["names"][0]["name"] == "心动星星"
