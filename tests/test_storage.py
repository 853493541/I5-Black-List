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
    again.remove_at(0)
    assert [entry.name for entry in Store(tmp_path).entries] == ["无害虎皮"]
