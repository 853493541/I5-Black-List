import sys

import pytest

from blacklist_detect.capture import CaptureUnavailable, capture_capability_message, capture_displays


def test_missing_display_api_is_reported():
    message = capture_capability_message()
    if sys.platform == "win32":
        assert "dxcam" in message or "显示器" in message
        return
    assert "DXGI" in message
    with pytest.raises(CaptureUnavailable) as raised:
        capture_displays()
    assert "DXGI" in str(raised.value)
