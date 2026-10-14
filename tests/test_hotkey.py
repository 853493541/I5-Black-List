from blacklist_detect.hotkey import parse_hotkey


def test_empty_hotkey_stays_unset():
    assert parse_hotkey("") is None
    assert parse_hotkey("   ") is None
    assert parse_hotkey("Ctrl") is None


def test_hotkey_canonical_form():
    spec = parse_hotkey("shift+ctrl+b")
    assert spec is not None
    assert spec.display == "Ctrl+Shift+B"
    assert spec.vk == 0x42
    assert spec.modifiers == ("Ctrl", "Shift")

    f8 = parse_hotkey("F8")
    assert f8 is not None
    assert f8.display == "F8"
    assert f8.vk == 0x77


def test_two_keys_at_most():
    from blacklist_detect.hotkey import two_keys

    assert two_keys("Ctrl+Alt+F11") == "Ctrl+F11"
    assert two_keys("Alt+Shift+K") == "Alt+K"
    assert two_keys("Alt+1") == "Alt+1" and two_keys("F8") == "F8" and two_keys("") == ""
