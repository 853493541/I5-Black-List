"""Paddle's tool lookup must not open a console window."""

import subprocess

from blacklist_detect.ocr_engine import silence_console_children


def test_where_does_not_run():
    silence_console_children()
    try:
        subprocess.check_output(["where", "ccache"])
    except subprocess.CalledProcessError as exc:
        assert exc.returncode == 1
    else:
        raise AssertionError("where should not run")
