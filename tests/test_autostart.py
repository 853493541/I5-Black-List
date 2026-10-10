"""开机自动启动 writes one Run entry for the current user, pointing at this copy, and removes it."""

import sys
import types
from pathlib import Path

import pytest

from blacklist_detect import autostart


class FakeRegistry:
    """Stands in for winreg, so a test never touches the real Windows settings."""

    HKEY_CURRENT_USER = "HKCU"
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self):
        self.values: dict[str, str] = {}

    class _Key:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def OpenKey(self, root, path):  # noqa: N802
        return self._Key()

    def CreateKeyEx(self, root, path, reserved, access):  # noqa: N802
        return self._Key()

    def QueryValueEx(self, key, name):  # noqa: N802
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name], self.REG_SZ

    def SetValueEx(self, key, name, reserved, kind, value):  # noqa: N802
        self.values[name] = value

    def DeleteValue(self, key, name):  # noqa: N802
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]


@pytest.fixture()
def registry(monkeypatch):
    fake = FakeRegistry()
    module = types.ModuleType("winreg")
    for name in dir(fake):
        if not name.startswith("__"):
            setattr(module, name, getattr(fake, name))
    monkeypatch.setitem(sys.modules, "winreg", module)
    monkeypatch.setattr(autostart.sys, "platform", "win32")
    return fake


def test_turning_it_on_and_off(registry, monkeypatch):
    exe = Path("C:/Programs/BlackListDetect/黑名单检测.exe")
    monkeypatch.setattr(autostart, "launcher", lambda: exe)
    assert autostart.is_enabled() is False
    assert autostart.set_enabled(True) is True
    assert registry.values[autostart.VALUE_NAME] == f'"{exe}" --background'
    assert autostart.is_enabled() is True
    assert autostart.set_enabled(False) is True
    assert autostart.is_enabled() is False
    assert autostart.set_enabled(False) is True, "turning off twice is fine"


def test_an_entry_follows_the_app_when_it_moves(registry, monkeypatch):
    registry.values[autostart.VALUE_NAME] = '"D:/old place/黑名单检测.exe" --background'
    exe = Path("C:/new place/黑名单检测.exe")
    monkeypatch.setattr(autostart, "launcher", lambda: exe)
    autostart.refresh()
    assert registry.values[autostart.VALUE_NAME] == f'"{exe}" --background'


def test_without_the_launcher_it_cannot_be_turned_on(registry, monkeypatch):
    monkeypatch.setattr(autostart, "launcher", lambda: None)
    assert autostart.available() is False
    assert autostart.set_enabled(True) is False
    assert autostart.is_enabled() is False
