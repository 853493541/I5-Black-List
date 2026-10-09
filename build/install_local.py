"""Install or update the app on this PC, so the newest code runs without unzipping anything.

    python build/install_local.py            update, then start the app
    python build/install_local.py --verify   also read the reference lobby with the installed copy
    python build/install_local.py --refresh-runtime   copy the Python runtime and models again

The first run copies the trimmed runtime, the OCR models, and the launcher to
%LOCALAPPDATA%\\Programs\\BlackListDetect (the usual place for an app installed
for one user), and puts a 黑名单检测 shortcut on the Desktop and in the Start menu.

Every later run asks the open copy to quit, copies only the app files that
changed (a second or two), and starts it again. The shortcut always opens the
newest version. Your list and settings stay in %APPDATA%\\BlackListDetect.
"""

from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "build"))

from make_release import EXE_NAME, Pruner, _verify  # noqa: E402

from blacklist_detect.paths import message_running_copy  # noqa: E402

SHORTCUT = "黑名单检测"
# Inside the app folder these are never copied from the repo or removed by a sync.
_KEEP = {"__pycache__", "models"}


def install_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "Programs" / "BlackListDetect"


def _powershell(script: str) -> str:
    done = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return done.stdout.strip()


def running_copies(root: Path) -> list[int]:
    """Process ids of the app started from this folder."""
    folder = str(root).replace("'", "''")
    found = _powershell(
        "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
        "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' or Name='python.exe'\" | "
        f"Where-Object {{ $_.ExecutablePath -like '{folder}\\*' }} | ForEach-Object {{ $_.ProcessId }}"
    )
    return [int(line) for line in found.split() if line.strip().isdigit()]


def other_copies(root: Path) -> list[str]:
    """Folders of other unzipped copies that are open. Only one copy runs at a time, so they block this one."""
    folder = str(root).replace("'", "''")
    found = _powershell(
        "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
        "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' or Name='python.exe'\" | "
        "Where-Object { $_.ExecutablePath -like '*\\runtime\\python*.exe' -and "
        f"$_.ExecutablePath -notlike '{folder}\\*' }} | "
        "ForEach-Object { Split-Path (Split-Path $_.ExecutablePath) }"
    )
    return sorted({line.strip() for line in found.splitlines() if line.strip()})


def stop_app(root: Path) -> bool:
    """Ask the open app to quit, then wait for it. Returns whether a copy from this folder was running."""
    was_running = bool(running_copies(root))
    # The pipe write waits for the app to read it, so a frozen app cannot hang the installer.
    sender = threading.Thread(target=message_running_copy, args=(b"quit",), daemon=True)
    sender.start()
    sender.join(5)
    deadline = time.monotonic() + 25
    while running_copies(root) and time.monotonic() < deadline:
        time.sleep(0.5)
    left = running_copies(root)
    for pid in left:
        print(f"  The app did not quit in time; ending process {pid}.")
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, check=False)
    return was_running


def _same(left: Path, right: Path) -> bool:
    return right.is_file() and left.stat().st_size == right.stat().st_size and filecmp.cmp(left, right, shallow=False)


def sync_tree(source: Path, target: Path) -> tuple[int, int]:
    """Make target match source, file by file. Returns (copied, removed)."""
    copied = removed = 0
    wanted: set[Path] = set()
    for path in source.rglob("*"):
        rel = path.relative_to(source)
        if _KEEP & set(rel.parts) or not path.is_file():
            continue
        wanted.add(rel)
        destination = target / rel
        if _same(path, destination):
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        copied += 1
    for path in sorted(target.rglob("*"), reverse=True):
        rel = path.relative_to(target)
        if _KEEP & set(rel.parts):
            continue
        if path.is_file() and rel not in wanted:
            path.unlink()
            removed += 1
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    return copied, removed


def install_runtime(root: Path, runtime: Path, models: Path) -> None:
    print(f"Copying the Python runtime to {root} (once) ...")
    if (root / "runtime").exists():
        shutil.rmtree(root / "runtime")
    pruner = Pruner(runtime / "Lib" / "site-packages")
    shutil.copytree(runtime, root / "runtime", ignore=pruner.ignore)
    target = root / "blacklist_detect" / "models"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(models, target)


def make_shortcuts(root: Path) -> list[str]:
    """A 黑名单检测 shortcut on the Desktop and in the Start menu, pointing at this folder."""
    exe = str(root / EXE_NAME).replace("'", "''")
    work = str(root).replace("'", "''")
    made = _powershell(
        "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
        "$shell = New-Object -ComObject WScript.Shell; "
        "foreach ($place in 'Desktop', 'Programs') { "
        "  $folder = [Environment]::GetFolderPath($place); "
        f"  $link = $shell.CreateShortcut((Join-Path $folder '{SHORTCUT}.lnk')); "
        f"  $link.TargetPath = '{exe}'; $link.WorkingDirectory = '{work}'; "
        f"  $link.IconLocation = '{exe},0'; $link.Description = '{SHORTCUT}'; $link.Save(); "
        "  Join-Path $folder '" + SHORTCUT + ".lnk' }"
    )
    return [line for line in made.splitlines() if line.strip()]


def start_app(root: Path) -> None:
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([str(root / EXE_NAME)], cwd=root, creationflags=flags, close_fds=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runtime", type=Path, default=REPO / "dist" / "黑名单检测" / "runtime")
    parser.add_argument("--models", type=Path, default=REPO / "dist" / "黑名单检测" / "blacklist_detect" / "models")
    parser.add_argument("--launcher", type=Path, default=REPO / "dist" / "exe" / EXE_NAME)
    parser.add_argument("--refresh-runtime", action="store_true", help="copy the runtime and models again")
    parser.add_argument("--verify", action="store_true", help="read the reference lobby with the installed copy")
    parser.add_argument("--no-start", action="store_true", help="do not start the app afterwards")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise SystemExit("The local install is for Windows.")

    root = install_dir()
    if not str(root).isascii():
        print(f"Note: {root} has non-ASCII characters; the app copies its models to an ASCII folder on first use.")
    started = time.monotonic()
    print("Closing the app if it is open ...")
    stop_app(root)
    root.mkdir(parents=True, exist_ok=True)

    if args.refresh_runtime or not (root / "runtime" / "python.exe").is_file():
        for path in (args.runtime / "python.exe", args.models):
            if not path.exists():
                raise SystemExit(f"missing {path}")
        install_runtime(root, args.runtime, args.models)

    copied, removed = sync_tree(REPO / "blacklist_detect", root / "blacklist_detect")
    launcher = root / EXE_NAME
    if args.launcher.is_file() and not _same(args.launcher, launcher):
        shutil.copy2(args.launcher, launcher)
        copied += 1
    print(f"App files: {copied} copied, {removed} removed.")

    links = make_shortcuts(root)
    for link in links:
        print(f"Shortcut: {link}")

    if args.verify:
        _verify(root)

    others = other_copies(root)
    if others:
        print("Another copy of the app is open, so this one would only bring that window forward:")
        for folder in others:
            print(f"  {folder}")
        print("Quit it (tray icon, right-click, 退出), then open 黑名单检测 from the Desktop shortcut.")
    elif not args.no_start:
        start_app(root)
        print("Started 黑名单检测.")
    print(f"Done in {time.monotonic() - started:.1f} s. Installed in {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
