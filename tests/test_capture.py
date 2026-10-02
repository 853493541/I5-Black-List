import sys

import pytest

from blacklist_detect.capture import CaptureUnavailable, capture_capability_message, capture_displays


def test_missing_display_api_is_reported():
    message = capture_capability_message()
    if sys.platform == "win32":
        assert message == "" or "选择图片" in message
        return
    assert "选择图片" in message
    with pytest.raises(CaptureUnavailable) as raised:
        capture_displays()
    assert "选择图片" in str(raised.value)
