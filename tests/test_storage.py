from blacklist_detect.paths import app_dir
from blacklist_detect.storage import Store


def test_windows_and_linux_dirs():
    windows = app_dir("win32", {"APPDATA": "/tmp/roaming"})
    assert windows.as_posix() == "/tmp/roaming/BlackListDetect"
    linux = app_dir("linux", {"XDG_CONFIG_HOME": "/tmp/zhibin-config"})
    assert linux.as_posix() == "/tmp/zhibin-config/BlackListDetect"


def test_blacklist_roundtrip(tmp_path):
    store = Store(tmp_path)
    added = store.add("  罪玥吉尔曼  ", note="常挂机", match_from_prefix=False)
    assert added is not None
    store.add("无害虎皮…", match_from_prefix=True)
    store.hotkey = "Ctrl+Shift+F8"
    store.muted = True
    store.save_settings()

    again = Store(tmp_path)
    assert [entry.name for entry in again.entries] == ["罪玥吉尔曼", "无害虎皮"]
    assert again.entries[0].note == "常挂机"
    assert again.entries[0].match_from_prefix is False
    assert again.entries[1].match_from_prefix is True
    assert again.hotkey == "Ctrl+Shift+F8"
    assert again.muted is True
    assert again.auto_capture is False
    store.auto_capture = True
    store.save_settings()
    assert Store(tmp_path).auto_capture is True
    again.remove_at(0)
    assert [entry.name for entry in Store(tmp_path).entries] == ["无害虎皮"]


def test_scan_history_is_saved_newest_first(tmp_path):
    store = Store(tmp_path)
    store.add_scan(
        [{"seat": 3, "name": "纪戴宁", "unclear": False}, {"seat": 12, "name": "", "unclear": True}],
        0.25,
    )
    store.add_scan([{"seat": 1, "name": "庄园美女", "unclear": False}])
    again = Store(tmp_path)
    assert again.scans[0]["names"][0]["name"] == "庄园美女"
    assert again.scans[1]["names"][0]["name"] == "纪戴宁"
    assert again.scans[1]["names"][1]["unclear"] is True
    assert again.scans[1]["elapsed"] == 0.25
    assert again.contains_name("纪戴宁") is False
    again.add("纪戴宁")
    assert again.contains_name("纪戴宁") is True
