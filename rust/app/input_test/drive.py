"""Real input on the built app (Windows only): starts the exe in a data folder of its own, then clicks the main
window's buttons with SendInput at the screen positions UIAutomation gives, changes 显示 and 方式, opens and closes one
dialog, and presses the 检查 hotkey. Each step is asserted through settings.json, the app's log, its windows or a
picture of the window; the evidence (windows under each click, styles, z-order, whether the UI thread answers) goes
to a report. Silent: BLACKLIST_DETECT_SILENT=1.

    python drive.py <exe> <empty folder for APPDATA> <report folder> [--bare]

The exe must be built with the `a11y` feature, so UIAutomation sees its controls. --bare is for an exe as shipped
(no UIAutomation tree): only whether clicks on a grid over the window reach it, whether its thread answers, and
whether the hotkey starts a check (the log line, or a corner card opening).
"""

import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # the runner's console is cp1252
ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor: UIA bounds and SendInput in the same physical pixels

import uiautomation as auto  # noqa: E402
from PIL import ImageChops, ImageGrab  # noqa: E402

user32 = ctypes.windll.user32
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.WindowFromPoint.restype = wintypes.HWND
user32.GetAncestor.restype = wintypes.HWND
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindow.restype = wintypes.HWND
user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM, wintypes.UINT,
                                       wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]

FOLDER = "BlackListDetect-RustPreview"
# The title bar's own buttons and what would end the run or close the window under test.
SKIP = {"退出", "清空数据", "导出", "隐藏名字", "显示名字", "最小化", "关闭", "Minimize", "Maximize", "Restore", "Close", "还原", "最大化"}
# In the 检查 panel, which any click outside it folds away: tested on their own, the panel opened first.
PANEL = {"显示说明", "直播模式说明", "快捷键"}
# Clicks that do nothing by design (v1.0.1 the same): a 记录 seat on neither list.
NO_EFFECT = {"心动星星"}
SEGMENTS = {"基础模式", "完整模式", "自动", "手动", "关闭", "开启"}
GW_HWNDNEXT, GA_ROOT = 2, 2
WS_EX = {0x8: "TOPMOST", 0x20: "TRANSPARENT", 0x80: "TOOLWINDOW", 0x80000: "LAYERED", 0x8000000: "NOACTIVATE",
         0x200000: "NOREDIRECTIONBITMAP"}

results: list[tuple[str, bool, str]] = []
notes: list[str] = []


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def send(*inputs: INPUT) -> None:
    array = (INPUT * len(inputs))(*inputs)
    sent = user32.SendInput(len(inputs), array, ctypes.sizeof(INPUT))
    if sent != len(inputs):
        notes.append(f"SendInput sent {sent} of {len(inputs)} (error {ctypes.GetLastError()})")


def mouse(flags: int, x: int = 0, y: int = 0) -> INPUT:
    return INPUT(0, _U(mi=MOUSEINPUT(x, y, 0, flags, 0, 0)))


def key(vk: int, up: bool = False) -> INPUT:
    return INPUT(1, _U(ki=KEYBDINPUT(vk, 0, 2 if up else 0, 0, 0)))


def move(x: int, y: int) -> None:
    left, top = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
    width, height = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
    nx = int((x - left) * 65535 / max(width - 1, 1))
    ny = int((y - top) * 65535 / max(height - 1, 1))
    send(mouse(0x0001 | 0x8000 | 0x4000, nx, ny))  # MOVE | ABSOLUTE | VIRTUALDESK


def click(x: int, y: int) -> None:
    move(x, y)
    time.sleep(0.05)
    send(mouse(0x0002), mouse(0x0004))  # LEFTDOWN, LEFTUP


def right_click(x: int, y: int) -> None:
    move(x, y)
    time.sleep(0.05)
    send(mouse(0x0008), mouse(0x0010))  # RIGHTDOWN, RIGHTUP


def clipboard() -> str:
    """The clipboard's text (CF_UNICODETEXT), "" when none."""
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalLock.restype = ctypes.c_void_p
    user32.GetClipboardData.restype = ctypes.c_void_p
    if not user32.OpenClipboard(None):
        return ""
    try:
        handle = user32.GetClipboardData(13)
        pointer = kernel32.GlobalLock(ctypes.c_void_p(handle)) if handle else None
        if not pointer:
            return ""
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(ctypes.c_void_p(handle))
    finally:
        user32.CloseClipboard()


def window_info(hwnd: int) -> str:
    title = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, title, 256)
    klass = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, klass, 256)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    ex = user32.GetWindowLongPtrW(hwnd, -20)
    style = user32.GetWindowLongPtrW(hwnd, -16)
    flags = "|".join(name for bit, name in WS_EX.items() if ex & bit) or "-"
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    visible = "visible" if user32.IsWindowVisible(hwnd) else "hidden"
    enabled = "" if user32.IsWindowEnabled(hwnd) else " DISABLED"
    return (f"hwnd {hwnd:#x} pid {pid.value} class {klass.value!r} title {title.value!r} "
            f"rect ({rect.left},{rect.top},{rect.right},{rect.bottom}) style {style & 0xffffffff:#010x} "
            f"exstyle {ex & 0xffffffff:#010x} [{flags}] {visible}{enabled}")


def own_windows(pid: int) -> list[int]:
    found: list[int] = []
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def each(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(proc(each), 0)
    return found


def z_order(limit: int = 12) -> list[str]:
    """The visible top-level windows from the top, the first ones: what lies over the main window."""
    lines, hwnd = [], user32.GetTopWindow(None)
    while hwnd and len(lines) < limit:
        if user32.IsWindowVisible(hwnd):
            lines.append(window_info(hwnd))
        hwnd = user32.GetWindow(hwnd, GW_HWNDNEXT)
    return lines


def answers(hwnd: int) -> bool:
    """Whether the window's thread handles a message within 2 s."""
    out = ctypes.c_size_t()
    return bool(user32.SendMessageTimeoutW(hwnd, 0, 0, 0, 0x0002, 2000, ctypes.byref(out)))  # WM_NULL, ABORTIFHUNG


def grab(hwnd: int):
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True)


def differs(a, b) -> bool:
    if a.size != b.size:
        return True
    return ImageChops.difference(a.convert("RGB"), b.convert("RGB")).getbbox() is not None


def center(control) -> tuple[int, int]:
    r = control.BoundingRectangle
    return (r.left + r.right) // 2, (r.top + r.bottom) // 2


def record(name: str, ok: bool, detail: str) -> None:
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + ": " + detail, flush=True)


class App:
    def __init__(self, exe: str, home: Path, out: Path):
        self.home, self.out = home, out
        self.data = home / FOLDER
        env = dict(os.environ, APPDATA=str(home), LOCALAPPDATA=str(home), USERPROFILE=str(home),
                   BLACKLIST_DETECT_SILENT="1")
        env.pop("BLACKLIST_DETECT_SOUND", None)
        # A v1.0.1 folder with one made-up name: the preview copies it at its first start, so the pages have rows.
        old = home / "BlackListDetect"
        old.mkdir(parents=True, exist_ok=True)
        (old / "blacklist.json").write_text(
            json.dumps({"entries": [{"name": "示例坏人", "reason": "", "tags": ["挂机"]}]}, ensure_ascii=False), encoding="utf-8")
        # 心动小鹿 a 嘉宾, so its seat in 记录 opens the 嘉宾 dialog; 心动星星 stays on neither list (its click does nothing).
        (old / "likes.json").write_text(json.dumps({"likes": [{"name": "心动小鹿", "nickname": "", "reason": ""}], "combos": []},
                                                   ensure_ascii=False), encoding="utf-8")
        # One made-up check in 记录, so its day, time and seat rows are there to click.
        seats = [{"seat": i + 1, "name": name, "unclear": False} for i, name in enumerate(["示例坏人", "心动小鹿", "心动星星"])]
        (old / "history.json").write_text(json.dumps(
            {"scans": [{"at": "2026-11-18T20:30:00+08:00", "elapsed": 1.2, "names": seats},
                       {"at": "2026-11-18T19:00:00+08:00", "elapsed": 1.1, "names": seats}]}, ensure_ascii=False), encoding="utf-8")
        self.proc = subprocess.Popen([exe], env=env, cwd=str(home))
        self.log = self.data / "logs" / "app.log"
        self.main = None
        self.hwnd = 0

    def log_text(self) -> str:
        try:
            return self.log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def list_file(self) -> str:
        try:
            return (self.data / "blacklist.json").read_text(encoding="utf-8")
        except OSError:
            return ""

    def settings(self) -> dict:
        try:
            return json.loads((self.data / "settings.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def find_main(self, budget: float = 60) -> bool:
        end = time.time() + budget
        while time.time() < end:
            if self.proc.poll() is not None:
                notes.append(f"the app exited with {self.proc.returncode}")
                return False
            for hwnd in own_windows(self.proc.pid):
                control = auto.ControlFromHandle(hwnd)
                if control and control.Name.startswith("模仿者小工具"):
                    self.main, self.hwnd = control, hwnd
                    return True
            time.sleep(1)
        return False

    def wait_log(self, text: str, start: int, budget: float) -> bool:
        end = time.time() + budget
        while time.time() < end:
            if text in self.log_text()[start:]:
                return True
            time.sleep(0.5)
        return False

    def under(self, x: int, y: int) -> str:
        hit = user32.WindowFromPoint(wintypes.POINT(x, y))
        root = user32.GetAncestor(hit, GA_ROOT) if hit else 0
        if root == self.hwnd:
            return "main window"
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(root, ctypes.byref(pid))
        if root and pid.value == self.proc.pid:
            return "app window: " + window_info(root)
        return "OTHER: " + (window_info(root) if root else "none")

    def close_extra(self, before: set[int]) -> int:
        """Closes the windows a click opened (a dialog), and says how many there were."""
        extra = [h for h in own_windows(self.proc.pid) if h not in before and h != self.hwnd]
        for hwnd in extra:
            user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        if extra:
            time.sleep(1)
        return len(extra)

    def front(self) -> None:
        """The main window restored and in front (a click may have hidden or minimized it)."""
        user32.ShowWindow(self.hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(self.hwnd)
        time.sleep(0.3)

    def open_panel(self) -> bool:
        """The 检查 panel under the header's pill (手动检查 / 自动检查中), where 显示 and 方式 are."""
        shown = lambda wait: self.main.TabItemControl(Name="完整模式", searchDepth=30).Exists(wait, 0.3)
        if shown(2):
            return True
        # The pill opens and folds the panel: click it, and once more if the panel is still not there (a click
        # that landed while the tree was being built folded a panel that was open).
        for _ in range(2):
            pill = next((c for c, _d in auto.WalkControl(self.main, maxDepth=30)
                         if c.ControlTypeName == "ButtonControl" and c.Name.startswith(("手动检查", "自动检查"))), None)
            if pill is None:
                notes.append("no 检查 pill seen")
                return False
            click(*center(pill))
            if shown(3):
                return True
        return False

    def segment(self, group: str, label: str):
        self.open_panel()
        panel = self.main
        control = panel.TabItemControl(Name=label, searchDepth=30)
        return control if control.Exists(3, 0.5) else None

    def snapshot(self, name: str) -> None:
        try:
            grab(self.hwnd).save(self.out / f"{name}.png")
        except OSError as error:
            notes.append(f"screenshot {name}: {error}")


def evidence(app: App, title: str) -> None:
    notes.append(f"--- {title}")
    notes.append(f"main window: {window_info(app.hwnd)}")
    notes.append(f"main window thread answers WM_NULL within 2 s: {answers(app.hwnd)}; "
                 f"IsHungAppWindow: {bool(user32.IsHungAppWindow(app.hwnd))}")
    notes.append(f"foreground: {window_info(user32.GetForegroundWindow())}")
    for hwnd in own_windows(app.proc.pid):
        notes.append(f"app window: {window_info(hwnd)}")
    notes.append("z-order from the top:")
    notes.extend("  " + line for line in z_order())


def agree(app: App) -> None:
    """A new data folder: 使用声明 opens over the window at start, and 同意并继续 lets checks run."""
    button, dialog = None, 0
    for hwnd in own_windows(app.proc.pid):
        if hwnd == app.hwnd:
            continue
        found = auto.ControlFromHandle(hwnd).ButtonControl(Name="同意并继续", searchDepth=30)
        if found.Exists(1, 0.3):
            button, dialog = found, hwnd
            break
    if button is None:
        seen = [window_info(h) for h in own_windows(app.proc.pid) if h != app.hwnd]
        record("使用声明 opens at the first start", False, f"no window with 同意并继续; the app's other windows: {seen}")
        return
    x, y = center(button)
    where_before = app.under(x, y)  # a 使用声明 behind the main window is one the player cannot answer
    user32.SetForegroundWindow(dialog)
    time.sleep(0.4)
    where = app.under(x, y)
    start = len(app.log_text())
    click(x, y)
    end, agreed = time.time() + 5, None
    while time.time() < end and agreed is not True:
        agreed = app.settings().get("disclaimer_accepted")
        time.sleep(0.3)
    on_top = where_before.startswith("app window")
    record("使用声明 opens over the main window", on_top, f"under its button before any raise: {where_before}")
    record("使用声明 opens at the first start and 同意并继续 is saved", agreed is True,
           f"disclaimer_accepted={agreed!r}; under the button at first: {where_before}; after raising it: {where}; "
           f"log: {app.log_text()[start:].strip()[-200:]!r}")


def change_segment(app: App, label: str, key_name: str, wanted) -> None:
    control = app.segment("", label)
    if control is None:
        record(f"{key_name} -> {label}", False, "UIAutomation does not see the option")
        return
    x, y = center(control)
    where = app.under(x, y)
    move(x, y)
    time.sleep(0.4)
    before = grab(app.hwnd)
    click(x, y)
    end = time.time() + 5
    saved = None
    while time.time() < end:
        saved = app.settings().get(key_name)
        if saved == wanted:
            break
        time.sleep(0.3)
    time.sleep(0.5)
    shown = differs(before, grab(app.hwnd))
    ok = saved == wanted and shown
    record(f"{key_name} -> {label}", ok, f"settings.json {key_name}={saved!r} (want {wanted!r}); "
           f"window redrawn: {shown}; under the click: {where}")


def click_pages(app: App) -> None:
    """Each page tab of the header in turn, and every button on it."""
    tabs = [c.Name for c, _ in auto.WalkControl(app.main, maxDepth=30)
            if c.ControlTypeName == "TabItemControl" and c.Name not in SEGMENTS and c.Name]
    notes.append(f"page tabs seen by UIAutomation: {tabs}")
    tabs = list(dict.fromkeys(tabs))
    for name in tabs[1:] + tabs[:1]:  # the page shown at start last, so each click changes the page
        app.front()
        tab = app.main.TabItemControl(Name=name, searchDepth=30)
        if not tab.Exists(2, 0.3):
            record(f"tab {name!r}", False, "gone")
            continue
        before = grab(app.hwnd)
        click(*center(tab))
        time.sleep(1)
        record(f"tab {name!r}", differs(before, grab(app.hwnd)), "page shown")
        app.snapshot(f"page-{len(results)}")
        click_buttons(app, name)


def click_buttons(app: App, page: str = "") -> None:
    buttons = []
    for control, _depth in auto.WalkControl(app.main, maxDepth=30):
        # The 检查 pill opens the panel over the page (its own checks cover it): clicked here it left the panel open,
        # and the next page or menu could not be reached.
        pill = control.Name.startswith(("手动检查", "自动检查"))
        if control.ControlTypeName == "ButtonControl" and control.Name not in SKIP | PANEL | NO_EFFECT and not pill:
            r = control.BoundingRectangle
            if r.width() > 2 and r.height() > 2 and not control.IsOffscreen:
                buttons.append((control.Name, center(control)))
    # The 检查 pill last: it folds the panel away, and the panel's buttons with it.
    # A menu (more) or the tag already chosen (全部) last but one: an open menu eats the next click, and 全部 changes
    # nothing until another tag was picked.
    buttons.sort(key=lambda item: 2 if item[0].startswith(("手动检查", "自动检查")) else 1 if item[0] in ("more", "全部") else 0)
    notes.append(f"buttons seen by UIAutomation on {page or 'the start page'}: {[name for name, _ in buttons]}")
    if not buttons:
        record("main-window buttons", False, "UIAutomation sees no button")
    for name, (x, y) in buttons:
        app.front()
        windows = set(own_windows(app.proc.pid))
        where = app.under(x, y)
        start = len(app.log_text())
        move(x, y)
        time.sleep(0.4)
        before = grab(app.hwnd)
        click(x, y)
        time.sleep(1.2)
        after = grab(app.hwnd)
        logged = app.log_text()[start:].strip()
        opened = app.close_extra(windows)
        shown = differs(before, after)
        user32.SetForegroundWindow(app.hwnd)
        send(key(0x1B), key(0x1B, True))  # Esc: a panel or menu the click opened
        time.sleep(0.4)
        # "UI: <event>" is what main.rs logs for an event nothing handles: a stub, not an effect.
        handled = [line for line in logged.splitlines() if " UI: " not in line and not line.startswith("UI: ")]
        ok = shown or opened > 0 or bool(handled)
        record(f"{page or 'start'}: button {name!r}", ok, f"redrawn {shown}, windows opened {opened}, log {logged[-120:]!r}; "
               f"under the click: {where}")


def open_dialog(app: App, name: str = "显示说明") -> None:
    app.front()
    app.open_panel()
    info = app.main.ButtonControl(Name=name, searchDepth=30)
    if not info.Exists(3, 0.5):
        record(f"dialog {name}", False, "UIAutomation does not see the button")
        return
    windows = set(own_windows(app.proc.pid))
    click(*center(info))
    end, new = time.time() + 5, []
    while time.time() < end and not new:
        new = [h for h in own_windows(app.proc.pid) if h not in windows]
        time.sleep(0.3)
    if not new:
        record(f"dialog {name} opens", False, "no new window within 5 s")
        return
    record(f"dialog {name} opens", True, window_info(new[0]))
    user32.PostMessageW(new[0], 0x0010, 0, 0)
    end = time.time() + 5
    while time.time() < end and user32.IsWindowVisible(new[0]):
        time.sleep(0.3)
    record(f"dialog {name} closes", not user32.IsWindowVisible(new[0]), "")


def press_hotkey(app: App) -> None:
    start = len(app.log_text())
    send(key(0x12), key(0x31), key(0x31, True), key(0x12, True))  # Alt+1
    ok = app.wait_log("Hotkey: 检查", start, 10) and app.wait_log("Hotkey: checking.", start, 2)
    tail = app.log_text()[start:].strip()
    ok = ok and "busy" not in tail and "not agreed" not in tail  # the check really started
    record("hotkey Alt+1 starts a check", ok, f"log after the press: {tail[-300:]!r}")


def open_settings(app: App, section: str) -> bool:
    """设置, then one section of its catalog (常规, 帮助, 关于)."""
    app.front()
    tab = app.main.TabItemControl(Name="设置", searchDepth=30)
    if not tab.Exists(2, 0.3):
        return False
    click(*center(tab))
    time.sleep(0.8)
    row = app.main.ListItemControl(Name=section, searchDepth=30)
    if not row.Exists(2, 0.3):
        return False
    click(*center(row))
    time.sleep(0.8)
    return True


def export_logs(app: App) -> None:
    """设置 › 帮助 › 导出日志 › 导出: the user named it as dead. A zip must land on the Desktop."""
    if not (open_settings(app, "帮助") or open_settings(app, "帮助")):
        record("导出 (导出日志) writes the logs", False, "设置 › 帮助 not reachable")
        return
    button = app.main.ButtonControl(Name="导出", searchDepth=30)
    if not button.Exists(2, 0.3):
        record("导出 (导出日志) writes the logs", False, "UIAutomation does not see 导出")
        return
    start = len(app.log_text())
    where = app.under(*center(button))
    click(*center(button))
    app.wait_log("Logs ", start, 15)
    said = app.log_text()[start:]
    line = next((ln for ln in said.splitlines() if "Logs exported: " in ln), "")
    path = Path(line.split("Logs exported: ", 1)[1].strip()) if line else None
    text = path.read_text(encoding="utf-8", errors="replace") if path is not None and path.exists() else ""
    ok = "==== app.log ====" in text  # the file is there and holds the log
    # The Explorer window 导出 opens (the file selected) stays over everything after: close it.
    time.sleep(1.5)
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def close_explorer(hwnd, _):
        klass = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, klass, 64)
        if klass.value == "CabinetWClass" and user32.IsWindowVisible(hwnd):
            notes.append(f"导出 opened Explorer: {window_info(hwnd)}")
            user32.PostMessageW(hwnd, 0x0010, 0, 0)
        return True

    user32.EnumWindows(proc(close_explorer), 0)
    record("导出 (导出日志) writes the logs", ok, f"file {path} exists {ok}; under the click: {where}; log {said.strip()[-200:]!r}")


def open_tab(app: App, name: str) -> bool:
    app.front()
    tab = app.main.TabItemControl(Name=name, searchDepth=30)
    if not tab.Exists(2, 0.3):
        return False
    click(*center(tab))
    time.sleep(0.8)
    return True


def menu_item(app: App, kind: str, target: str, item: str, check) -> None:
    """Right-click the row named `target` (a list item or a button), click `item` in its menu, and ask `check`
    whether it did what it says. `check(before)` gets the state taken just before the click."""
    app.front()
    row = app.main.ListItemControl(Name=target, searchDepth=30) if kind == "row" else app.main.ButtonControl(Name=target, searchDepth=30)
    if not row.Exists(2, 0.3):
        record(f"menu {target} › {item}", False, f"no {kind} named {target!r}")
        return
    right_click(*center(row))
    time.sleep(0.8)
    entry = app.main.ButtonControl(Name=item, searchDepth=30)
    if not entry.Exists(2, 0.3):
        record(f"menu {target} › {item}", False, "the menu or its item is not there")
        send(key(0x1B), key(0x1B, True))
        return
    before = {"windows": set(own_windows(app.proc.pid)), "log": len(app.log_text()), "list": app.list_file()}
    click(*center(entry))
    time.sleep(1.2)
    ok, detail = check(before)
    app.close_extra(before["windows"])
    send(key(0x1B), key(0x1B, True))
    record(f"menu {target} › {item}", ok, detail)


def row_menus(app: App) -> None:
    """黑名单: the row's and the tag's right-click menus, every item (删除 last: it takes the row)."""
    if not open_tab(app, "黑名单"):
        record("黑名单 row menus", False, "tab not reachable")
        return
    opened = lambda before: (bool(set(own_windows(app.proc.pid)) - before["windows"]), "a dialog opened")
    copied = lambda before: (clipboard() == "示例坏人", f"clipboard {clipboard()!r}")
    menu_item(app, "row", "示例坏人", "编辑", opened)
    menu_item(app, "row", "示例坏人", "复制名字", copied)
    def tag_gone(before):
        # 删除 a tag asks first (ui._remove_tag): answer the question, then the tag must be gone from the list.
        for hwnd in set(own_windows(app.proc.pid)) - before["windows"]:
            yes = auto.ControlFromHandle(hwnd).ButtonControl(Name="删除", searchDepth=30)
            if yes.Exists(1, 0.3):
                click(*center(yes))
                time.sleep(1)
        return "挂机" not in app.list_file(), f"blacklist.json: {app.list_file()[:120]!r}"

    menu_item(app, "button", "挂机", "删除", tag_gone)
    menu_item(app, "row", "示例坏人", "删除", lambda before: ("示例坏人" not in app.list_file(), f"blacklist.json: {app.list_file()[:120]!r}"))


def eye(app: App) -> None:
    """黑名单's eye: names masked or shown, kept in settings.json (names_hidden), the button's name following."""
    if not open_tab(app, "黑名单"):
        record("eye 隐藏名字", False, "tab not reachable")
        return
    before = app.settings().get("names_hidden", False)
    button = app.main.ButtonControl(Name="显示名字" if before else "隐藏名字", searchDepth=30)
    if not button.Exists(2, 0.3):
        record("eye 隐藏名字", False, "UIAutomation does not see the eye")
        return
    x, y = center(button)
    where = app.under(x, y)
    click(x, y)
    time.sleep(1)
    after = app.settings().get("names_hidden", False)
    renamed = app.main.ButtonControl(Name="隐藏名字" if before else "显示名字", searchDepth=30).Exists(1, 0.3)
    record("eye 隐藏名字", after != before, f"names_hidden {before} -> {after}; button renamed {renamed}; under the click: {where}")
    if after != before:
        click(x, y)  # back as it was (the old element is gone: the button was renamed)
        time.sleep(0.6)


def settings_sections(app: App) -> None:
    """Every section of 设置 and every button in it (清空数据 left out; 导出 has its own check)."""
    for section in ("常规", "帮助", "关于"):
        if not open_settings(app, section):
            record(f"设置 › {section}", False, "not reachable")
            continue
        record(f"设置 › {section}", True, "shown")
        click_buttons(app, f"设置/{section}")


def capture_hotkey(app: App) -> None:
    """The hotkey box takes a new key as it is pressed (MainWindow._take_hotkey), and the new key starts a check."""
    app.front()
    app.open_panel()
    box = app.main.ButtonControl(Name="快捷键", searchDepth=30)
    if not box.Exists(3, 0.5):
        record("hotkey box takes Alt+2", False, "UIAutomation does not see the box")
        return
    click(*center(box))
    time.sleep(0.8)
    send(key(0x12), key(0x32), key(0x32, True), key(0x12, True))  # Alt+2
    end, saved = time.time() + 5, None
    while time.time() < end and saved != "Alt+2":
        saved = app.settings().get("hotkey")
        time.sleep(0.3)
    record("hotkey box takes Alt+2", saved == "Alt+2", f"settings.json hotkey={saved!r}")
    if saved != "Alt+2":
        return
    time.sleep(1.5)  # registered again on the next turns of the window's timer
    start = len(app.log_text())
    send(key(0x12), key(0x32), key(0x32, True), key(0x12, True))
    ok = app.wait_log("Hotkey: 检查", start, 10)
    record("new hotkey Alt+2 starts a check", ok, f"log after the press: {app.log_text()[start:].strip()[-300:]!r}")


def bare(app: App) -> None:
    rect = wintypes.RECT()
    user32.GetWindowRect(app.hwnd, ctypes.byref(rect))
    missed = []
    for i in range(1, 6):
        for j in range(1, 5):
            x = rect.left + (rect.right - rect.left) * i // 6
            y = rect.top + 40 + (rect.bottom - rect.top - 40) * j // 5
            where = app.under(x, y)
            if not where.startswith(("main window", "app window")):
                missed.append(f"({x},{y}) {where}")
    record("clicks on a 5x4 grid reach the main window", not missed, "; ".join(missed[:4]) or "all 20 points")
    hung = bool(user32.IsHungAppWindow(app.hwnd))
    record("the window's thread answers", answers(app.hwnd) and not hung, f"IsHungAppWindow {hung}")
    windows = set(own_windows(app.proc.pid))
    start = len(app.log_text())
    send(key(0x12), key(0x31), key(0x31, True), key(0x12, True))  # Alt+1
    end, card = time.time() + 10, []
    while time.time() < end and not card and "Hotkey: 检查" not in app.log_text()[start:]:
        card = [h for h in own_windows(app.proc.pid) if h not in windows]
        time.sleep(0.5)
    logged = "Hotkey: 检查" in app.log_text()[start:]
    record("hotkey Alt+1 starts a check", bool(card) or logged,
           f"new windows {[window_info(h) for h in card]}, log line {logged}, log after: {app.log_text()[start:].strip()[-200:]!r}")


def guarded(step, app: App, *args) -> None:
    """One step; an exception in it is a FAIL in the table, and the next steps still run."""
    try:
        step(app, *args)
    except Exception as error:  # noqa: BLE001 - the report must still be written
        record(f"{step.__name__} crashed", False, repr(error)[:300])


def main() -> int:
    exe, home, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    home.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    app = App(exe, home, out)
    try:
        if not app.find_main():
            record("main window shows", False, "not found within 60 s")
            return finish(app)
        record("main window shows", True, window_info(app.hwnd))
        time.sleep(3)  # start-up work on the window's thread settles
        agree(app)
        user32.SetForegroundWindow(app.hwnd)
        app.snapshot("start")
        evidence(app, "after start")
        if "--bare" in sys.argv[4:]:
            bare(app)
            evidence(app, "at the end")
            return finish(app)
        keys = app.log_text()
        notes.append("hotkey lines in the log: " + repr([ln for ln in keys.splitlines() if "otkey" in ln]))
        # 显示 first (完整模式 lets 方式 pick 自动), then 方式 both ways, then 显示 back.
        change_segment(app, "完整模式", "safe_mode", False)
        change_segment(app, "自动", "auto_capture", True)
        change_segment(app, "手动", "auto_capture", False)
        change_segment(app, "基础模式", "safe_mode", True)
        app.snapshot("after-segments")
        guarded(open_dialog, app)
        guarded(open_dialog, app, "直播模式说明")
        app.front()
        guarded(click_buttons, app)
        guarded(click_pages, app)
        guarded(export_logs, app)
        guarded(settings_sections, app)
        guarded(eye, app)
        guarded(row_menus, app)
        app.front()
        guarded(press_hotkey, app)
        guarded(capture_hotkey, app)
        evidence(app, "at the end")
        app.snapshot("end")
    finally:
        if app.proc.poll() is None:
            app.proc.kill()
    return finish(app)


def finish(app: App) -> int:
    lines = ["### Real input on the main window", "", "| step | result | detail |", "|---|---|---|"]
    for name, ok, detail in results:
        lines.append(f"| {name} | {'PASS' if ok else '**FAIL**'} | {detail.replace('|', '/')[:400]} |")
    lines += ["", "<details><summary>evidence</summary>", "", "```", *notes, "", "--- app.log", app.log_text(), "```",
              "", "</details>"]
    report = "\n".join(lines)
    (app.out / "report.md").write_text(report, encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report + "\n")
    failed = [name for name, ok, _ in results if not ok]
    # The failures alone, for the last lines of the job's log (the report's own host may be out of reach).
    with open(app.out / "failures.txt", "a", encoding="utf-8") as f:
        f.writelines(f"FAIL {name}: {detail[:300]}\n" for name, ok, detail in results if not ok)
        f.write(f"{len(results) - len(failed)} passed, {len(failed)} failed\n")
    print(f"{len(results) - len(failed)} passed, {len(failed)} failed: {failed}")
    return 1 if failed or not results else 0


if __name__ == "__main__":
    sys.exit(main())
