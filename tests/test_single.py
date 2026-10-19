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


@pytest.fixture(autouse=True)
def _own_data_folder(tmp_path, monkeypatch):  # noqa: ANN001, ANN202
    """A stuck copy's dump goes to the data folder's logs: a folder of the test's own, never the player's."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "data"))


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
        # Where it was stuck, written before it was ended.
        assert (tmp_path / "data" / "BlackListDetect" / "logs" / f"stuck-{process.pid}.dmp").read_bytes()[:4] == b"MDMP"
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


class _Said:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def warning(self, text, *args, **_):  # noqa: ANN001, ANN002, ANN003, ANN201
        self.lines.append(text % args)

    info = warning


def _stuck(monkeypatch, write_dump):  # noqa: ANN001, ANN202
    """settle() finding one stuck copy (4242, never a real process: end and the writer are stand-ins)."""
    done, said = [], _Said()
    monkeypatch.setattr(single.time, "sleep", lambda _s: None)
    monkeypatch.setattr(single, "copies_in", lambda _root: [4242])
    monkeypatch.setattr(single, "end", lambda pids: done.append(("end", list(pids))) or list(pids))
    monkeypatch.setattr(single, "write_dump", lambda pid, folder: write_dump(done, pid, folder))
    monkeypatch.setattr(single, "log", said)
    return done, said


def test_a_stuck_copy_is_dumped_before_it_is_ended(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    def write_dump(done, pid, folder):  # noqa: ANN001, ANN202
        done.append(("dump", pid, folder))
        return folder / f"stuck-{pid}.dmp"

    done, said = _stuck(monkeypatch, write_dump)
    assert single.settle(tmp_path / "app", True, lambda: False) is False
    assert [step[0] for step in done] == ["dump", "end"] and done[0][1] == 4242 and done[0][2].name == "logs"
    assert done[1] == ("end", [4242])
    assert any("its pipe did not answer" in line and "stuck-4242.dmp" in line for line in said.lines), said.lines
    assert not any("no window, tray or pipe" in line for line in said.lines)


def test_a_dump_that_fails_still_ends_the_copy(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    def write_dump(done, pid, folder):  # noqa: ANN001, ANN202
        raise OSError(5, "Access is denied")

    done, said = _stuck(monkeypatch, write_dump)
    assert single.settle(tmp_path / "app", True, lambda: False) is False
    assert done == [("end", [4242])]
    assert any("4242" in line and "Access is denied" in line for line in said.lines), said.lines


def test_the_dump_holds_the_stacks_and_only_the_newest_three_are_kept(tmp_path):
    process = _copy_running_from(tmp_path / "app")
    folder = tmp_path / "logs"
    folder.mkdir()
    for age, pid in enumerate((1, 2, 3)):
        old = folder / f"stuck-{pid}.dmp"
        old.write_bytes(b"MDMP")
        os.utime(old, (1000 + age, 1000 + age))
    try:
        time.sleep(0.5)
        written = single.write_dump(process.pid, folder)
        assert process.poll() is None, "a dump leaves the copy running"
    finally:
        process.kill()
    assert written == folder / f"stuck-{process.pid}.dmp"
    assert written.read_bytes()[:4] == b"MDMP" and written.stat().st_size < 5_000_000
    assert sorted(path.name for path in folder.glob("stuck-*.dmp")) == sorted(["stuck-2.dmp", "stuck-3.dmp", written.name])
