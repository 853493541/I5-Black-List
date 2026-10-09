"""A log file beside the settings, so a friend's problem can be looked at afterwards.

Player names are not written here. The window runs under pythonw, which has no
console, so without this file an error would leave no trace at all.
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


def log_dir(root: Path | None = None) -> Path:
    return (root or app_dir()) / "logs"


def setup_logging(root: Path | None = None) -> Path | None:
    """Write to logs/app.log (three files of 1 MB at most) and record crashes. Returns the log path."""
    global _crash_file
    if log.handlers:
        return Path(log.handlers[0].baseFilename) if isinstance(log.handlers[0], RotatingFileHandler) else None
    folder = log_dir(root)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(folder / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    except OSError:
        log.addHandler(logging.NullHandler())
        return None
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
    try:
        # A crash inside Paddle or Qt kills the process without a Python traceback.
        _crash_file = open(folder / "crash.log", "a", encoding="utf-8")
        faulthandler.enable(_crash_file)
    except OSError:
        _crash_file = None
    sys.excepthook = _log_uncaught
    threading.excepthook = lambda args: _log_uncaught(args.exc_type, args.exc_value, args.exc_traceback)
    return folder / "app.log"


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
