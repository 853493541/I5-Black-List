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

A frozen window leaves evidence too: Watchdog writes "Main thread not answering" to app.log and
every thread's stack to crash.log, and in the tray "Tray: alive." comes once an hour.
"""

from __future__ import annotations

import faulthandler
import logging
import sys
import threading
import time
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
_WHERE = {"MainThread": "ui", "check": "check", "update-check": "update", "update-download": "update", "watchdog": "watch"}


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


# The main thread's watch: a beat every BEAT_S on the main thread, a C timer that writes every thread's
# stack to crash.log once the beat is DUMP_S late, and a log line once it is QUIET_S late.
BEAT_S = 2.0
DUMP_S = 30.0
QUIET_S = 10.0
# The watch's own tick this late means the PC slept or hibernated: nobody ran, so it is no freeze.
ASLEEP_S = 20.0
TRAY_ALIVE_MS = 60 * 60 * 1000


class Watchdog:
    """Says when the window's thread stops answering, and leaves where it stopped.

    beat() runs on the main thread (a QTimer, see watch_main_thread). Each beat re-arms
    faulthandler's timer, a C thread that writes every thread's stack to crash.log once no beat
    came for dump_after seconds: it runs even while a C call holds the GIL. tick() runs on a
    Python thread of its own and writes "Main thread not answering" to app.log once per freeze,
    and "answering again" when it ends. A tick far later than its period means the PC slept;
    it starts over and says nothing. (faulthandler's timer is not told: a Timeout dump in
    crash.log without a "not answering" line in app.log beside it was a sleep.)
    """

    def __init__(self, crash_file=None, period: float = BEAT_S, dump_after: float = DUMP_S,  # noqa: ANN001
                 quiet_after: float = QUIET_S, asleep_after: float = ASLEEP_S, clock=time.monotonic) -> None:  # noqa: ANN001
        self.crash_file = crash_file
        self.period = period
        self.dump_after = dump_after
        self.quiet_after = quiet_after
        self.asleep_after = asleep_after
        self._clock = clock
        self._lock = threading.Lock()
        self._beat = self._last_tick = clock()
        self._frozen_since: float | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def beat(self) -> None:
        """On the main thread: it is answering."""
        with self._lock:
            self._beat = self._clock()
        if self.crash_file is not None and not self._stop.is_set():
            faulthandler.dump_traceback_later(self.dump_after, repeat=False, file=self.crash_file)

    def tick(self) -> None:
        """On the watch's thread, every period."""
        now = self._clock()
        gap, self._last_tick = now - self._last_tick, now
        with self._lock:
            if gap > self.asleep_after:
                self._beat = now
                return
            silent = now - self._beat
            since = self._frozen_since
            if since is None and silent >= self.quiet_after:
                self._frozen_since = self._beat
                when = time.strftime("%H:%M:%S", time.localtime(time.time() - silent))
                log.warning("Main thread not answering for %.0f s (since %s); its stack goes to crash.log after %.0f s.",
                            silent, when, self.dump_after)
            elif since is not None and silent < self.quiet_after:
                self._frozen_since = None
                log.warning("Main thread answering again after %.0f s.", self._beat - since)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="watchdog", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self.period):
            self.tick()

    def stop(self) -> None:
        self._stop.set()
        if self.crash_file is not None:
            faulthandler.cancel_dump_traceback_later()


def watch_main_thread(period: float = BEAT_S, dump_after: float = DUMP_S, quiet_after: float = QUIET_S,
                      crash_file=None) -> Watchdog:  # noqa: ANN001
    """Start the main thread's watch (call it on the main thread, once the QApplication exists).
    Its crash file is crash.log unless told otherwise."""
    from PySide6.QtCore import QCoreApplication, QTimer

    dog = Watchdog(crash_file or _crash_file, period, dump_after, quiet_after, asleep_after=max(ASLEEP_S, period * 10))
    dog.timer = QTimer(QCoreApplication.instance())
    dog.timer.timeout.connect(dog.beat)
    dog.timer.start(int(period * 1000))
    QCoreApplication.instance().aboutToQuit.connect(dog.stop)
    dog.beat()
    dog.start()
    return dog


def tray_heartbeat(parent, hidden, every_ms: int = TRAY_ALIVE_MS):  # noqa: ANN001, ANN201
    """While hidden() (the window is in the tray), "Tray: alive." once every every_ms, so a freeze
    there is known to within that time. Returns the QTimer."""
    from PySide6.QtCore import QTimer

    timer = QTimer(parent)
    timer.timeout.connect(lambda: hidden() and log.info("Tray: alive."))
    timer.start(every_ms)
    return timer
