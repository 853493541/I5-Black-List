"""Open the app with the Python that ships beside this program.

A friend does not need Python installed. The exe sits next to ``runtime``
and the ``blacklist_detect`` folder.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def main() -> int:
    root = app_root()
    pythonw = root / "runtime" / "pythonw.exe"
    if not pythonw.is_file():
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            0,
            "缺少运行环境。请解压整个压缩包后再双击本程序。",
            "黑名单检测",
            0x10,
        )
        return 1
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONUTF8"] = "1"
    env["QT_QPA_PLATFORM"] = "windows"
    subprocess.Popen(
        [str(pythonw), "-m", "blacklist_detect", *sys.argv[1:]],
        cwd=str(root),
        env=env,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
