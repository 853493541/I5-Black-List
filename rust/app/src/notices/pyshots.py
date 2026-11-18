# Python reference pictures for rust/app/shots/notices (the ones tools/ui_shots.py does not take).
# QT_SCALE_FACTOR=1.5 QT_QPA_PLATFORM=offscreen APPDATA=<tmp> HOME=<tmp> PYTHONPATH=. python rust/app/src/notices/pyshots.py <out>
import sys, time
from pathlib import Path
from unittest import mock
from PySide6.QtWidgets import QApplication, QWidget
app = QApplication([])
from blacklist_detect import ui_theme, ui_notice, ui_update, updater
out = Path(sys.argv[1]); out.mkdir(exist_ok=True)
ui_theme._apply_theme(app)
from blacklist_detect.ui import _window_style
def settle(s=0.4):
    end=time.monotonic()+s
    while time.monotonic()<end: app.processEvents(); time.sleep(0.01)
def save(w,name):
    w.grab().save(str(out/f"{name}.png"))
n = ui_notice.CornerNotice(); scr = app.primaryScreen()
for name, call in [("notice_clear", lambda: n.show_result([], [], 0, scr)), ("notice_checking", lambda: n.show_checking(scr)),
                   ("notice_missing", lambda: n.show_missing(scr)), ("notice_error", lambda: n.show_error("截图失败，等会儿再试", scr)),
                   ("notice_many", lambda: n.show_result([(f"示例坏人{i}", ("炸房","挂机")) for i in range(7)], [], 0, scr))]:
    n.hide(); call(); settle(0.5); save(n.main, name)
n.hide()
host = QWidget(); host.setStyleSheet(_window_style(ui_theme.chinese_family())); host.setStyleSheet(host.styleSheet()); host.resize(900, 560); host.show()
notes=("花边铺满整个游戏","卡片跟着游戏大小","检查更快")
def rel(base): return updater.Release(version="v0.8.7", url="", sha256="", size=41_200_000, base=base, notes=notes)
root = Path(sys.argv[1])
with mock.patch.object(ui_update.Download, "start", lambda *a: None), mock.patch.object(updater, "staged_version", lambda r: None), mock.patch.object(ui_update, "__version__", "v0.8.6"), mock.patch.object(updater, "__version__", "v0.8.6"):
    for name, base, src, step in [("update_downloading","v0.8.0",False,lambda d:(d.start(), d._on_progress(2,5))),
                                  ("update_failed","v0.8.0",False,lambda d:(d.start(), d._on_failed("下载失败，等会儿再试"))),
                                  ("update_restarting","v0.8.0",False,lambda d:d._on_done("v0.8.7")),
                                  ("update_full","v9.0.0",False,lambda d:None),("update_source","v0.8.0",True,lambda d:None)]:
        d = ui_update.UpdateDialog(rel(base), None if src else root, root, host)
        d.RESTART_MS = 10**8
        d.open(); step(d); settle(0.4); save(d, name); d._state="source"; d.reject(); settle(0.1)
print("done")
