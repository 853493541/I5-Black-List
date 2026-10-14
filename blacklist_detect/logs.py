"""A log file beside the settings, so a friend's problem can be looked at afterwards.

The window runs under pythonw, which has no console, so without this file an error would leave
no trace at all. Each line is one event:

    2026-10-13 17:43:23.317 INFO    ui     Check 12 (hotkey): lobby found, 1 on the list, 0.23 s (…)
                                    ^ thread: ui, check (recognition), update, …

Each start begins with a ==== line, and a check's lines share its number. Lines after the first
of one event (a report, a traceback) are indented, so every event starts with its time.

Player names are never written whole: masked() keeps the first character (示例坏人 → 示***), so
a seat can be followed from check to check without naming anyone. Lists are logged as counts.

Size: app.log rolls over at 1 MB and five files are kept (app.log, app.log.1 … app.log.4), about
two weeks of play; crash.log is cut to its last part when it grows past half a MB. 导出日志 puts
them in one file.
"""

from __future__ import annotations

import faulthandler
import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from blacklist_detect.paths import app_dir

log = logging.getLogger("blacklist_detect")
_crash_file = None

LINE = "%(asctime)s.%(msecs)03d %(levelname)-7s %(where)-6s %(message)s"
DATE = "%Y-%m-%d %H:%M:%S"
MAX_BYTES = 1_000_000
BACKUPS = 4
# crash.log only grows by a crash; past CRASH_MAX it keeps its last CRASH_KEEP bytes.
CRASH_MAX = 512_000
CRASH_KEEP = 256_000
# The threads, by the name each gives itself: the window's, the recognition's, the update check's.
_WHERE = {"MainThread": "ui", "check": "check", "update-check": "update", "update-download": "update"}


def masked(name: str) -> str:
    """A player's name for the log: the first character, then a * for each one after it."""
    name = str(name or "")
    return name[:1] + "*" * (len(name) - 1)


class _Format(logging.Formatter):
    def __init__(self) -> None:
        super().__init__(LINE, DATE)

    def format(self, record: logging.LogRecord) -> str:
        record.where = _WHERE.get(record.threadName, (record.threadName or "?")[:6])
        # Every event starts with its time: the lines after its first are indented under it.
        return super().format(record).replace("\n", "\n" + " " * 4)


def _trim(path: Path, limit: int = CRASH_MAX, keep: int = CRASH_KEEP) -> None:
    """Keep only the end of a file that only grows, from a whole line on."""
    try:
        if not path.is_file() or path.stat().st_size <= limit:
            return
        tail = path.read_bytes()[-keep:]
        tail = tail[tail.find(b"\n") + 1 :]
        path.write_bytes(b"(older lines removed)\n" + tail)
    except OSError:
        pass


def log_dir(root: Path | None = None) -> Path:
    return (root or app_dir()) / "logs"


def setup_logging(root: Path | None = None) -> Path | None:
    """Write to logs/app.log (five files of 1 MB at most) and record crashes. Returns the log path."""
    global _crash_file
    if log.handlers:
        return Path(log.handlers[0].baseFilename) if isinstance(log.handlers[0], RotatingFileHandler) else None
    folder = log_dir(root)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(folder / "app.log", maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8")
    except OSError:
        log.addHandler(logging.NullHandler())
        return None
    handler.setFormatter(_Format())
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
    try:
        # A crash inside Paddle or Qt kills the process without a Python traceback.
        _trim(folder / "crash.log")
        _crash_file = open(folder / "crash.log", "a", encoding="utf-8")
        faulthandler.enable(_crash_file)
    except OSError:
        _crash_file = None
    sys.excepthook = _log_uncaught
    threading.excepthook = lambda args: _log_uncaught(args.exc_type, args.exc_value, args.exc_traceback)
    return folder / "app.log"


_RUNNING = "running"


def mark_running(root: Path | None = None) -> bool:
    """Note that the app is open. Returns whether the last run never said it was closing.

    A crash leaves crash.log; a process ended from outside (Task Manager, a tool that ends
    every pythonw, a power loss) leaves nothing. The note left behind says it happened.
    """
    marker = log_dir(root) / _RUNNING
    unclean = marker.exists()
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("", encoding="utf-8")
    except OSError:
        pass
    return unclean


def mark_closed(root: Path | None = None) -> None:
    try:
        (log_dir(root) / _RUNNING).unlink(missing_ok=True)
    except OSError:
        pass


def _log_uncaught(kind, value, trace) -> None:  # noqa: ANN001
    if issubclass(kind, KeyboardInterrupt):
        sys.__excepthook__(kind, value, trace)
        return
    log.critical("Unhandled error", exc_info=(kind, value, trace))
    for listener in list(_listeners):
        try:
            listener(f"{kind.__name__}: {value}")
        except Exception:
            pass


_listeners: list = []


def on_uncaught(listener) -> None:
    """Call listener(text) after an error nothing else caught, for example to show it in the window."""
    _listeners.append(listener)
