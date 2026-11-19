r"""Every outcome of a hotkey check is visible, on the preview as the player unzips it (the fix/rust-check-visible case).

    python -I check_visible.py <preview folder> <exe name> <work folder> <report folder> <folder for an older ORT>

On a Windows runner, set to 1920x1080 before: a whole 16:9 lobby frame full-screen, Notepad in front, Alt+1 by SendInput.
Asserted through the app's log ("Check 1 (hotkey): 12 seats read", "Header: <the pill's words>") and history.json:
  normal       the check reads 12 seats and writes a 记录 entry; an older onnxruntime.dll first on PATH changes nothing
  no models    the pill says 识别还没准备好 at start and after a press
  junk dll     识别还没准备好, and the next press checks again (a crash in the check left every later press "busy")
  ours gone    with only an older onnxruntime.dll on PATH (Windows ML ships one in System32): 识别还没准备好, never theirs
  in the zip   the exe alone in %TEMP%\Temp1_<zip>.zip\ (opened from inside the zip): 请先把压缩包全部解压，再运行
Every case runs a copy in a folder with spaces and Chinese in its path, from another working folder.
Silent (BLACKLIST_DETECT_SILENT=1); each case in an APPDATA of its own.
"""

import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

from PIL import Image, ImageGrab, ImageTk

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ctypes.windll.shcore.SetProcessDpiAwareness(2)
user32 = ctypes.windll.user32
FOLDER = "BlackListDetect-RustPreview"
ROOT = Path(__file__).resolve().parents[3]
results: list[tuple[str, bool, str]] = []


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def key(vk: int, up: bool = False) -> INPUT:
    return INPUT(type=1, ki=KEYBDINPUT(wVk=vk, dwFlags=2 if up else 0))


def alt_1() -> None:
    keys = [key(0x12), key(0x31), key(0x31, True), key(0x12, True)]
    array = (INPUT * len(keys))(*keys)
    sent = user32.SendInput(len(keys), array, ctypes.sizeof(INPUT))
    print(f"  SendInput Alt+1: {sent} of {len(keys)}; foreground: {title(user32.GetForegroundWindow())!r}")


def title(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buffer, 256)
    return buffer.value


def record(name: str, ok: bool, detail: str) -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")


def windows_of(pid: int) -> list[int]:
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):  # noqa: ANN001
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(each, 0)
    return found


class Lobby:
    """A whole 1920x1080-style frame: the sample lobby (a crop) centred on black, full-screen and topmost."""

    def __init__(self) -> None:
        self.tk = tk.Tk()
        width, height = self.tk.winfo_screenwidth(), self.tk.winfo_screenheight()
        crop = Image.open(ROOT / "blacklist_detect" / "assets" / "sample-lobby.jpg").convert("RGB")
        scale = min(width * 0.9 / crop.width, height * 0.82 / crop.height)
        crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.LANCZOS)
        frame = Image.new("RGB", (width, height))
        frame.paste(crop, ((width - crop.width) // 2, (height - crop.height) // 2))
        self.top = (height - crop.height) // 2
        self.photo = ImageTk.PhotoImage(frame)
        self.tk.overrideredirect(True)
        self.tk.geometry(f"{width}x{height}+0+0")
        self.tk.attributes("-topmost", True)
        tk.Label(self.tk, image=self.photo, borderwidth=0).pack()
        self.pump(1.0)
        print(f"  lobby frame {width}x{height}, crop {crop.width}x{crop.height} at y {self.top}")

    def pump(self, seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            self.tk.update()
            time.sleep(0.05)


class App:
    def __init__(self, exe: Path, home: Path, path_first: Path | None = None) -> None:
        shutil.rmtree(home, ignore_errors=True)
        self.data = home / FOLDER
        self.data.mkdir(parents=True)
        # 使用声明 agreed, 完整模式 (the player's), the default hotkey.
        settings = {"disclaimer_accepted": True, "safe_mode": False, "auto_capture": False, "hotkey": "Alt+1"}
        (self.data / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        env = dict(os.environ, APPDATA=str(home), LOCALAPPDATA=str(home), USERPROFILE=str(home),
                   BLACKLIST_DETECT_SILENT="1")
        if path_first is not None:
            env["PATH"] = f"{path_first};{env['PATH']}"
        self.log = self.data / "logs" / "app.log"
        self.proc = subprocess.Popen([str(exe)], env=env, cwd=str(home))

    def text(self) -> str:
        return self.log.read_text(encoding="utf-8", errors="replace") if self.log.exists() else ""

    def wait(self, pattern: str, budget: float, lobby: Lobby, start: int = 0) -> re.Match | None:
        end = time.time() + budget
        while time.time() < end:
            found = re.search(pattern, self.text()[start:])
            if found:
                return found
            lobby.pump(0.5)
        return None

    def minimise(self) -> None:
        for hwnd in windows_of(self.proc.pid):
            user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE: the main window would cover the lobby

    def stop(self) -> None:
        self.proc.kill()
        self.proc.wait(10)


def focus_notepad(notepad: subprocess.Popen, lobby: Lobby) -> None:
    for _ in range(20):
        hwnds = windows_of(notepad.pid)
        if hwnds:
            hwnd = hwnds[0]
            user32.MoveWindow(hwnd, 0, 0, 300, max(lobby.top, 80), True)
            user32.keybd_event(0x12, 0, 0, 0)  # an Alt tap lets this process hand over the foreground
            user32.SetForegroundWindow(hwnd)
            user32.keybd_event(0x12, 0, 2, 0)
            lobby.pump(0.5)
            return
        lobby.pump(0.5)


def press(app: App, lobby: Lobby, notepad: subprocess.Popen) -> int:
    focus_notepad(notepad, lobby)
    start = len(app.text())
    alt_1()
    return start


def tail(app: App, start: int = 0) -> str:
    return app.text()[start:].strip()[-600:]


def started(app: App, lobby: Lobby) -> bool:
    ok = app.wait(r"Hotkeys registered", 30, lobby) is not None
    lobby.pump(1.0)
    app.minimise()
    lobby.tk.attributes("-topmost", True)
    lobby.pump(1.0)
    return ok


def normal(exe: Path, work: Path, old_dir: Path, lobby: Lobby, notepad: subprocess.Popen, report: Path) -> None:
    app = App(exe, work / "normal", path_first=old_dir)
    try:
        record("normal: starts, hotkeys registered", started(app, lobby), tail(app)[-200:])
        models = re.search(r"Start-up: (exe [^\n]*|models [^\n]*)", app.text())
        record("normal: models ok from a nested folder with spaces and Chinese", "Start-up: models ok" in app.text(),
               "; ".join(re.findall(r"Start-up: (?:exe|models)[^\n]*", app.text()))[-400:] if models else tail(app)[-300:])
        start = press(app, lobby, notepad)
        ImageGrab.grab(all_screens=True).save(report / "normal-pressed.png")
        done = app.wait(r"Check 1 \(hotkey\)[^\n]*", 180, lobby, start)
        line = done.group(0) if done else ""
        record("normal: the hotkey check reads 12 seats", "12 seats read" in line, line or tail(app, start))
        record("normal: 记录 written", app.wait(r"Check 1: 记录 added\.", 10, lobby, start) is not None, tail(app, start)[-200:])
        history = app.data / "history.json"
        entries = json.loads(history.read_text(encoding="utf-8")) if history.exists() else None
        count = len(entries) if isinstance(entries, list) else len((entries or {}).get("scans", [])) if entries else 0
        record("normal: history.json has the entry", count >= 1, f"{count} entries in {history.name}")
        record("normal: the pill shows no problem", "Header: " not in app.text(), tail(app, start)[-200:])
        record("normal: older onnxruntime.dll on PATH not used", "ONNX Runtime from" not in app.text(), "")
        ImageGrab.grab(all_screens=True).save(report / "normal-shown.png")
    finally:
        app.stop()


def unready(name: str, exe: Path, work: Path, lobby: Lobby, notepad: subprocess.Popen, report: Path,
            path_first: Path | None = None, at_start: bool = False) -> str:
    app = App(exe, work / name.replace(" ", "-"), path_first)
    try:
        record(f"{name}: starts", started(app, lobby), tail(app)[-200:])
        if at_start:
            shown = app.wait(r"Header: 识别还没准备好", 10, lobby) is not None
            record(f"{name}: pill 识别还没准备好 before any press", shown, tail(app)[-300:])
        start = press(app, lobby, notepad)
        failed = app.wait(r"识别还没准备好 \(step: OCR load\)[^\n]*", 60, lobby)
        record(f"{name}: pill 识别还没准备好 after the press", failed is not None and "Header: 识别还没准备好" in app.text(),
               tail(app, start))
        app.wait(r"Check 1 \(second look\) failed", 30, lobby, start)
        start = press(app, lobby, notepad)
        again = app.wait(r"Check 2 \((hotkey|second look)\) failed", 60, lobby, start) is not None
        busy = "busy, the press was ignored" in app.text()[start:]
        record(f"{name}: the next press checks again (not busy)", again and not busy, tail(app, start))
        ImageGrab.grab(all_screens=True).save(report / f"{name.replace(' ', '-')}.png")
        return app.text()
    finally:
        app.stop()


def older_ort(folder: Path) -> Path:
    """An onnxruntime.dll older than ours, from the first pip wheel (newest first) that ships one of its own."""
    import zipfile
    folder.mkdir(parents=True, exist_ok=True)
    for version in ("1.22.0", "1.21.1", "1.20.1", "1.19.2", "1.18.1", "1.17.3"):
        wheels = folder / version
        subprocess.run([sys.executable, "-m", "pip", "download", "-q", f"onnxruntime=={version}", "--no-deps",
                        "--only-binary=:all:", "--platform", "win_amd64", "--python-version", "3.11", "-d", str(wheels)],
                       check=False)
        for wheel in wheels.glob("*.whl"):
            with zipfile.ZipFile(wheel) as archive:
                name = next((n for n in archive.namelist() if n.lower().endswith("/onnxruntime.dll")), None)
                if name:
                    (folder / "onnxruntime.dll").write_bytes(archive.read(name))
                    print(f"Older ONNX Runtime: {version} ({name})")
                    return folder / "onnxruntime.dll"
    raise SystemExit("no older onnxruntime.dll found in the wheels tried")


def dll_imports(dll: Path) -> str:
    try:
        import pefile
        pe = pefile.PE(str(dll), fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
        return ", ".join(sorted(entry.dll.decode() for entry in pe.DIRECTORY_ENTRY_IMPORT))
    except Exception as error:  # noqa: BLE001
        return f"(not read: {error})"


def main() -> int:
    unpacked, exe_name, work, report, old_folder = (Path(arg) for arg in sys.argv[1:6])
    old_dll = older_ort(old_folder)
    # The player's unzip: a folder with spaces and Chinese, nested; the app is started from another working folder.
    preview = work / "解压 后的 文件夹" / f"{exe_name} 副本"
    shutil.rmtree(preview, ignore_errors=True)
    shutil.copytree(unpacked, preview)
    exe = preview / f"{exe_name}.exe"
    report.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    dpi = user32.GetDpiForSystem()
    print(f"Screen {user32.GetSystemMetrics(0)}x{user32.GetSystemMetrics(1)}, system DPI {dpi} ({dpi * 100 // 96} %)")
    ours = preview / "onnxruntime.dll"
    print(f"Our onnxruntime.dll imports: {dll_imports(ours)}")
    old_dir = work / "old-ort"
    old_dir.mkdir(exist_ok=True)
    shutil.copy(old_dll, old_dir / "onnxruntime.dll")
    lobby = Lobby()
    notepad = subprocess.Popen(["notepad.exe"])
    try:
        normal(exe, work, old_dir, lobby, notepad, report)
        models = preview / "models"
        models.rename(preview / "models-gone")
        try:
            unready("no models", exe, work, lobby, notepad, report, at_start=True)
        finally:
            (preview / "models-gone").rename(models)
        inside = Path(os.environ["TEMP"]) / f"Temp1_{exe_name}.zip" / exe_name
        shutil.rmtree(inside.parent, ignore_errors=True)
        inside.mkdir(parents=True)
        shutil.copy(exe, inside / exe.name)  # Explorer copies only the exe it runs out of a zip
        app = App(inside / exe.name, work / "in-zip")
        try:
            record("in the zip: starts", started(app, lobby), tail(app)[-200:])
            shown = app.wait(r"Header: 请先把压缩包全部解压，再运行", 10, lobby) is not None
            record("in the zip: pill 请先把压缩包全部解压，再运行", shown and "the zip looks not unpacked" in app.text(),
                   "; ".join(re.findall(r"(?:Start-up|Header): [^\n]*", app.text()))[-400:])
        finally:
            app.stop()
            shutil.rmtree(inside.parent, ignore_errors=True)
        shutil.move(ours, work / "ours.dll")
        try:
            (preview / "onnxruntime.dll").write_bytes(b"MZ not a real dll")
            unready("junk dll", exe, work, lobby, notepad, report)
            (preview / "onnxruntime.dll").unlink()
            log = unready("ours gone", exe, work, lobby, notepad, report, path_first=old_dir)
            record("ours gone: the path looked at is ours, never a search by name",
                   f"ONNX Runtime from {preview}" in log or f"ONNX Runtime from {preview.resolve()}" in log,
                   next((line for line in log.splitlines() if "ONNX Runtime from" in line), "no such line")[-300:])
        finally:
            (preview / "onnxruntime.dll").unlink(missing_ok=True)
            shutil.move(work / "ours.dll", ours)
    finally:
        notepad.kill()
        lobby.tk.destroy()
    failed = [name for name, ok, _ in results if not ok]
    lines = [f"- {'✅' if ok else '❌'} {name}: {detail[-300:]!r}" for name, ok, detail in results]
    summary = "\n".join([f"### Check visible ({len(results) - len(failed)} of {len(results)})",
                         f"Screen {user32.GetSystemMetrics(0)}x{user32.GetSystemMetrics(1)}, DPI {dpi}", *lines])
    (report / "summary.md").write_text(summary, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
            out.write(summary + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
