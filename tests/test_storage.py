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
    # 安全模式 and 手动检查 by default.
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
    # A file from before 安全模式 opens in 安全模式, which checks only on the hotkey.
    assert store.safe_mode is True
    assert store.auto_capture is False


def test_auto_check_needs_no_answer_of_its_own(tmp_path):
    # 自动检查 is not asked about: it is kept with 完整模式 agreed to, and only 安全模式 turns it off.
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
    """嘉宾人数 is gone (嘉宾特效 plays for any 嘉宾): an old settings file's is read past, not saved again."""
    import json

    Store(tmp_path).save_settings()
    path = tmp_path / "settings.json"
    settings = json.loads(path.read_text(encoding="utf-8"))
    settings["love_counts"] = [2, 3]
    path.write_text(json.dumps(settings), encoding="utf-8")
    again = Store(tmp_path)
    again.save_settings()
    assert "love_counts" not in json.loads(path.read_text(encoding="utf-8"))


def test_an_old_effects_choice_is_on_and_an_old_off_stays_off(tmp_path):
    """嘉宾特效 was one scene for every 嘉宾, 随机 or 无 once; it is on or off in 设置 now. A scene or
    随机 is on (经典 for 嘉宾 with no 特效 of their own); 无 stays off."""
    import json

    Store(tmp_path).save_settings()
    path = tmp_path / "settings.json"
    for saved, now in (("stars", "classic"), ("random", "classic"), ("ribbon", "classic"), ("off", "off"), (None, "classic")):
        settings = json.loads(path.read_text(encoding="utf-8"))
        settings["love_scene"] = saved
        path.write_text(json.dumps(settings), encoding="utf-8")
        assert Store(tmp_path).love_scene == now, saved
    store = Store(tmp_path)
    store.love_scene = "off"
    store.save_settings()
    assert Store(tmp_path).love_scene == "off"


def test_a_saved_hotkey_of_three_keys_keeps_two(tmp_path):
    import json

    root = tmp_path / "BlackListDetect"
    root.mkdir()
    (root / "settings.json").write_text(json.dumps({"hotkey": "Ctrl+Alt+F11"}), encoding="utf-8")
    assert Store(root).hotkey == "Ctrl+F11"
    (root / "settings.json").write_text(json.dumps({"hotkey": "Alt+1"}), encoding="utf-8")
    assert Store(root).hotkey == "Alt+1"


def test_reminding_about_each_list_is_kept_and_one_stays_on(tmp_path):
    import json

    store = Store(tmp_path)
    assert (store.check_blacklist, store.check_likes) == (True, True)
    store.check_blacklist = False
    store.save_settings()
    assert (Store(tmp_path).check_blacklist, Store(tmp_path).check_likes) == (False, True)
    # Both off would tell about nothing: both come back on.
    settings = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    settings["check_likes"] = False
    (tmp_path / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    assert (Store(tmp_path).check_blacklist, Store(tmp_path).check_likes) == (True, True)
    store.reset()
    assert (store.check_blacklist, store.check_likes) == (True, True)


def test_the_sound_volume_and_mute_are_kept_and_reset(tmp_path):
    """设置 › 声音: 100% and not muted at first, kept as set, back to that after 清空数据. A volume that is
    none (not a number, out of 0-100) is 100%; one between steps of 5 the nearest step."""
    import json

    store = Store(tmp_path)
    assert (store.sound_volume, store.sound_muted) == (100, False)
    store.sound_volume, store.sound_muted = 35, True
    store.save_settings()
    assert (Store(tmp_path).sound_volume, Store(tmp_path).sound_muted) == (35, True)
    path = tmp_path / "settings.json"
    for saved, now in ((0, 0), (72, 70), (73.4, 75), (-5, 100), (120, 100), ("50", 100), (True, 100), (None, 100)):
        settings = json.loads(path.read_text(encoding="utf-8"))
        settings["sound_volume"] = saved
        path.write_text(json.dumps(settings), encoding="utf-8")
        assert Store(tmp_path).sound_volume == now, saved
    settings["sound_muted"] = "yes"
    path.write_text(json.dumps(settings), encoding="utf-8")
    assert Store(tmp_path).sound_muted is False
    store.reset()
    assert (store.sound_volume, store.sound_muted) == (100, False)
    assert (Store(tmp_path).sound_volume, Store(tmp_path).sound_muted) == (100, False)


def _own_sound(store: Store, key: str) -> str:
    """A player's own sound for a 特效, as 特效管理 keeps it: <key>.wav in custom_sounds."""
    from blacklist_detect.paths import custom_sound_dir

    folder = custom_sound_dir(store.root)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{key}.wav").write_bytes(b"RIFF")
    return f"{key}.wav"


def test_each_effect_s_volume_and_own_sound_are_kept_and_cleared(tmp_path):
    """特效管理: each 特效's own 音量 and the player's own sound for it, kept as set; a 特效 left as it was
    (100%, its own sound) is not saved. 清空数据 drops them, the sounds' folder too."""
    import json

    from blacklist_detect.paths import custom_sound_dir

    store = Store(tmp_path)
    assert store.scene_sounds == {} and store.scene_sound("ice") == (None, 100)
    store.scene_sounds = {
        "ice": {"volume": 60},
        "classic": {"volume": 100, "file": _own_sound(store, "classic"), "name": "生日歌.mp3", "start": 12.5, "length": 5.0},
        "stars": {"volume": 100},
    }
    store.save_settings()
    saved = json.loads(store.settings_path.read_text(encoding="utf-8"))["scene_sounds"]
    assert set(saved) == {"ice", "classic"}
    again = Store(tmp_path)
    assert again.scene_sounds == {"ice": {"volume": 60}, "classic": store.scene_sounds["classic"]}
    assert again.scene_sound("ice") == (None, 60)
    assert again.scene_sound("classic") == (custom_sound_dir(tmp_path) / "classic.wav", 100)
    assert again.scene_sound("stars") == (None, 100)
    # A sound whose file is gone plays the scene's own again; its 音量 stays.
    again.scene_sounds["ice"] = {"volume": 45, "file": _own_sound(again, "ice"), "name": "a.wav"}
    again.save_settings()
    (custom_sound_dir(tmp_path) / "ice.wav").unlink()
    assert Store(tmp_path).scene_sounds["ice"] == {"volume": 45}
    again.reset()
    assert again.scene_sounds == {} and Store(tmp_path).scene_sounds == {}
    assert not custom_sound_dir(tmp_path).exists()
    # The folder kept apart from the quieter copies' (sounds/), whose files go as new ones are made.
    assert custom_sound_dir(tmp_path).name == "custom_sounds"


def test_bad_effect_sounds_are_dropped_and_the_other_settings_kept(tmp_path):
    """A 特效管理 entry that is no sound is dropped by itself: the rest of 设置 is as saved. A volume that is
    none is 100%, a file named with a path (or not there) is none, a key this version does not know is kept
    for the version that does."""
    import json

    store = Store(tmp_path)
    store.sound_volume, store.theme = 35, "紫色"
    own = _own_sound(store, "neon")
    store.save_settings()
    elsewhere = tmp_path / "elsewhere.wav"
    elsewhere.write_bytes(b"RIFF")
    settings = json.loads(store.settings_path.read_text(encoding="utf-8"))
    for garbage in ("loud", [1, 2], 7, None):
        settings["scene_sounds"] = garbage
        store.settings_path.write_text(json.dumps(settings), encoding="utf-8")
        loaded = Store(tmp_path)
        assert (loaded.scene_sounds, loaded.load_warning, loaded.sound_volume, loaded.theme) == ({}, "", 35, "紫色"), garbage
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
    assert (loaded.load_warning, loaded.sound_volume, loaded.theme) == ("", 35, "紫色")
    assert loaded.scene_sounds == {
        "cyber": {"volume": 55},
        "neon": {"volume": 100, "file": own, "name": ""},
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
