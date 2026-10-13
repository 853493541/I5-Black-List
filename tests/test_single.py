"""One copy at a time, and no copy stuck open holding the files an update needs."""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from blacklist_detect import single

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows processes and mutexes")


def _copy_running_from(root):  # noqa: ANN001, ANN202
    """A process whose program is root\runtime\模仿者小工具.exe, as the app's is. Windows' ping,
    renamed, waiting a minute: it needs nothing beside it."""
    runtime = root / "runtime"
    runtime.mkdir(parents=True)
    exe = runtime / "模仿者小工具.exe"
    shutil.copy2(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "PING.EXE", exe)
    return subprocess.Popen([str(exe), "-n", "60", "127.0.0.1"], stdout=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)


def test_a_copy_from_this_folder_is_found_and_nothing_else(tmp_path):
    process = _copy_running_from(tmp_path / "app")
    try:
        time.sleep(0.5)
        assert single.copies_in(tmp_path / "app") == [process.pid]
        assert single.copies_in(tmp_path / "elsewhere") == []
    finally:
        process.kill()


def test_a_copy_that_never_answers_is_ended(tmp_path, monkeypatch):
    process = _copy_running_from(tmp_path / "app")
    monkeypatch.setattr(single.time, "sleep", lambda _s: None)
    try:
        time.sleep(0.5)
        # This start owns the mutex, and the other copy (an older version, without it) never answers.
        assert single.settle(tmp_path / "app", True, lambda: False) is False
        assert process.wait(5) is not None
        assert single.copies_in(tmp_path / "app") == []
    finally:
        process.kill()


def test_a_copy_that_answers_is_shown_and_left_alone(tmp_path):
    process = _copy_running_from(tmp_path / "app")
    try:
        time.sleep(0.5)
        assert single.settle(tmp_path / "app", False, lambda: True) is True
        assert process.poll() is None
    finally:
        process.kill()


def test_a_copy_still_starting_gets_time_to_answer(tmp_path, monkeypatch):
    process = _copy_running_from(tmp_path / "app")
    asked = []

    def answers() -> bool:
        asked.append(1)
        return len(asked) >= 4

    monkeypatch.setattr(single.time, "sleep", lambda _s: None)
    try:
        time.sleep(0.5)
        # The mutex is held by the other copy: it answers on the fourth try and is not ended.
        assert single.settle(tmp_path / "app", False, answers) is True
        assert process.poll() is None
    finally:
        process.kill()


def test_only_the_first_start_owns_the_mutex():
    key = f"BlackListDetect-test-{time.time_ns()}"
    assert single.claim(key) is True
    assert single.claim(key) is False


def test_ending_the_process_does_not_crash_on_the_way_out():
    code = subprocess.run(
        [sys.executable, "-c", "from blacklist_detect.single import exit_now; exit_now(7)"],
        cwd=str(Path(__file__).resolve().parent.parent),
        timeout=30,
    ).returncode
    assert code == 7
