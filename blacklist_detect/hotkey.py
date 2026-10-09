"""Hotkey text, plus a Windows global hotkey that does not send input."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from blacklist_detect import ui_text as T

# Virtual-key codes used by RegisterHotKey.
_MOD_ALT = 0x0001
_MOD_CONTROL = 0x0002
_MOD_SHIFT = 0x0004
_MOD_WIN = 0x0008
_MOD_NOREPEAT = 0x4000
_WM_HOTKEY = 0x0312

_MODIFIER_NAMES = {
    "ctrl": "Ctrl",
    "control": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "win": "Win",
    "meta": "Win",
    "super": "Win",
}
_MODIFIER_ORDER = ("Ctrl", "Alt", "Shift", "Win")
_MODIFIER_FLAGS = {
    "Ctrl": _MOD_CONTROL,
    "Alt": _MOD_ALT,
    "Shift": _MOD_SHIFT,
    "Win": _MOD_WIN,
}


@dataclass(frozen=True)
class HotkeySpec:
    display: str
    modifiers: tuple[str, ...]
    vk: int

    @property
    def win_modifiers(self) -> int:
        flags = _MOD_NOREPEAT
        for name in self.modifiers:
            flags |= _MODIFIER_FLAGS[name]
        return flags


def _canonical_key(part: str) -> str | None:
    token = part.strip()
    if len(token) == 1 and token.isascii() and token.isalnum():
        return token.upper()
    upper = token.upper()
    if upper.startswith("F") and upper[1:].isdigit():
        number = int(upper[1:])
        if 1 <= number <= 12:
            return f"F{number}"
    return None


def _vk_code(key: str) -> int:
    if len(key) == 1 and "A" <= key <= "Z":
        return 0x41 + (ord(key) - ord("A"))
    if len(key) == 1 and "0" <= key <= "9":
        return 0x30 + (ord(key) - ord("0"))
    number = int(key[1:])
    return 0x70 + number - 1


def parse_hotkey(text: str) -> HotkeySpec | None:
    """Parse 'Ctrl+Shift+F8'. Empty means the capture hotkey is not set."""
    raw = (text or "").strip()
    if not raw:
        return None
    modifiers: list[str] = []
    key: str | None = None
    for part in raw.split("+"):
        piece = part.strip()
        if not piece:
            return None
        modifier = _MODIFIER_NAMES.get(piece.lower())
        if modifier:
            if modifier not in modifiers:
                modifiers.append(modifier)
            continue
        if key is not None:
            return None
        key = _canonical_key(piece)
        if key is None:
            return None
    if key is None:
        return None
    ordered = tuple(name for name in _MODIFIER_ORDER if name in modifiers)
    display = "+".join((*ordered, key))
    return HotkeySpec(display=display, modifiers=ordered, vk=_vk_code(key))


class GlobalHotkey:
    """RegisterHotKey on Windows. The key is not synthesized into the lobby.

    On any other system this stores nothing with the OS. Callers still save
    the chosen text so the same settings file works on Windows later.
    """

    def __init__(self, callback) -> None:
        self.callback = callback
        self._filter = None
        self._registered = False
        self._id = 1
        self.active = ""
        self.error = ""

    @property
    def supported(self) -> bool:
        return sys.platform == "win32"

    def clear(self) -> None:
        self.error = ""
        if self._filter is not None and sys.platform == "win32":
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app is not None:
                app.removeNativeEventFilter(self._filter)
        self._filter = None
        if self._registered and sys.platform == "win32":
            import ctypes

            ctypes.windll.user32.UnregisterHotKey(None, self._id)
        self._registered = False
        self.active = ""

    def apply(self, spec: HotkeySpec | None) -> bool:
        self.clear()
        if spec is None:
            return True
        if sys.platform != "win32":
            self.active = ""
            self.error = T.HOTKEY_SAVED_UNSUPPORTED
            return False
        import ctypes
        from ctypes import wintypes

        from PySide6.QtCore import QAbstractNativeEventFilter
        from PySide6.QtWidgets import QApplication

        user32 = ctypes.windll.user32
        if not user32.RegisterHotKey(None, self._id, spec.win_modifiers, spec.vk):
            self.error = T.HOTKEY_TAKEN
            return False

        owner = self

        class _Filter(QAbstractNativeEventFilter):
            def nativeEventFilter(self, event_type, message):  # noqa: ANN001
                try:
                    kind = bytes(event_type).decode("ascii", "ignore")
                except Exception:
                    kind = str(event_type)
                if "windows" not in kind.lower():
                    return False, 0
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == _WM_HOTKEY and int(msg.wParam) == owner._id:
                    owner.callback()
                    return True, 0
                return False, 0

        self._filter = _Filter()
        app = QApplication.instance()
        if app is not None:
            app.installNativeEventFilter(self._filter)
        self._registered = True
        self.active = spec.display
        return True
