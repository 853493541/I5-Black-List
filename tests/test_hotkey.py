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
