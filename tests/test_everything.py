"""Every feature, once, end to end: a player's first session in the real window.

It opens fresh, agrees to 使用声明 and runs the first 检查; fills 黑名单 by hand and by 批量导入,
and 嘉宾; checks the bundled sample lobby (made-up names) with the real recognition on the real
worker thread, the way the hotkey does; sees the result in 安全模式, in 完整模式 and in 直播模式;
gets their 组合's scene and music when the lobby has two 嘉宾 players and no 黑名单; reads 记录;
uses the 检查 panel, 选择场景, 设置 › 静音, 设置 › 检查 and 导出日志; and ends with 清空数据.

Each step's own details are tested elsewhere. This one shows they work together. It needs the
local PaddleOCR model, like test_reference_screenshot.py; CI skips it.
"""

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("paddleocr", reason="PaddleOCR is not installed")

from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from blacklist_detect import __version__, love_scenes  # noqa: E402
from blacklist_detect.diagnostics import SAMPLE_NAMES  # noqa: E402
from blacklist_detect.pipeline import check_image  # noqa: E402
from blacklist_detect.storage import Store  # noqa: E402


@pytest.fixture(scope="module")
def qapp():  # noqa: ANN201
    return QApplication.instance() or QApplication([])


def _wait(qapp, done, seconds: float = 120.0) -> None:  # noqa: ANN001
    """Run the event loop until done() is true: the worker thread answers through it."""
    end = time.monotonic() + seconds
    while not done():
        assert time.monotonic() < end, "the app did not finish in time"
        qapp.processEvents()
        time.sleep(0.01)


def _typed(text: str):  # noqa: ANN202
    """A BatchAddDialog.exec that types text into the box and presses 导入."""

    def run(dialog) -> int:  # noqa: ANN001
        dialog.edit.setPlainText(text)
        dialog._accept()
        return dialog.result()

    return run


def test_a_whole_first_session(qapp, tmp_path, monkeypatch):
    from blacklist_detect import ui
    from blacklist_detect.model import Combo, Scenes
    from blacklist_detect.ui import MainWindow
    from blacklist_detect.ui_dialogs import BatchAddDialog, DisclaimerDialog, GuideDialog
    from blacklist_detect.ui_guest_scenes import GuestScenesDialog
    from blacklist_detect.ui_likes import LikeDialog
    from blacklist_detect.ui_music import TUNES, ThemeMusic

    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    # The screen here has no game: a check reads the sample lobby, as if it were on screen.
    monkeypatch.setattr(ui, "capture_top_band", lambda: object())
    said: list[str] = []

    # --- 1. First open: 使用声明, then the first 检查 on the sample, then the welcome. ----------
    window = MainWindow()
    window._watch_timer.stop()
    window.music = ThemeMusic(play=lambda _tune: None)
    monkeypatch.setattr(window, "_say", lambda text, undo=None: said.append(text))
    window.resize(1100, 700)
    window.show()
    assert window.store.first_run and not window.store.disclaimer_accepted
    assert window._start(window._capture_job, live=True) is False, "nothing is checked before 使用声明"
    window.begin()
    _wait(qapp, lambda: window.setup is not None and window.setup.state in ("ok", "failed"))
    assert window.setup.state == "ok", window.setup.message.text()
    assert window.setup.notes[2].text() == "12/12", "the sample's twelve names read right"
    assert window.store.env_checked == __version__
    window.setup._dismiss()
    notice = window.findChild(DisclaimerDialog)
    assert notice is not None and notice.isVisible() and len(notice.points) == 3
    notice.agree_button.click()
    assert Store(window.store.root).disclaimer_accepted is True
    guide = window.findChild(GuideDialog)
    assert guide is not None and guide.isVisible()
    guide.accept()
    _wait(qapp, lambda: window._warm_state == "ready")

    # --- 2. 游戏名 in the header. ----------------------------------------------------------------
    window.profile_chip.click()
    window.player_edit.setText("小林同学")
    window._finish_player_name()
    assert window.store.player_name == "小林同学" and window.profile_chip.name() == "小林同学"

    # --- 3. 黑名单: one by hand, more by 批量导入, a 标签 on them. --------------------------------
    window.store.add("示例坏人", "开局就炸房", tags=("炸房",))
    window._list_changed()
    monkeypatch.setattr(BatchAddDialog, "exec", _typed("路人乙（挂机）\n捣蛋鬼（乱投票）"))
    monkeypatch.setattr(ui, "suggest_tags", lambda _rows, _catalog: [])
    window._add_many_by_dialog()
    assert [entry.name for entry in window.store.entries] == ["示例坏人", "路人乙", "捣蛋鬼"]
    assert said[-1] == "已添加 2 人"
    assert "炸房" in window.store.tag_catalog()

    # --- 4. 嘉宾: two players; a 黑名单 name is refused. ----------------------------------------
    for name, nickname in (("心动小鹿", "小鹿"), ("心动星星", "")):
        window.store.add_like(name, nickname)
    window.likes_page.refresh()
    refused = LikeDialog("示例坏人", blacklisted=window.likes_page._blacklisted())
    refused._accept()
    assert refused.name_error.text() == "已经在黑名单里了" and refused.result() != QDialog.Accepted
    assert [like.name for like in window.store.likes] == ["心动小鹿", "心动星星"]

    # --- 5. A check of the lobby, 安全模式: the hotkey, real recognition on the worker thread. ----
    def sample_lobby():  # noqa: ANN202
        return check_image(str(ui.SAMPLE_LOBBY), list(window.store.entries))

    monkeypatch.setattr(window, "_capture_job", sample_lobby)
    assert window.store.safe_mode is True
    window.check_now()
    _wait(qapp, lambda: window.notice.kind in ("hit", "clear", "error", "missing"))
    assert window.notice.kind == "hit"
    assert window.notice.main.names() == ["示例坏人"]
    assert window.panel.isHidden() and window.hit_card.isHidden(), "安全模式 draws nothing over the game"
    _wait(qapp, lambda: window.notice.likes.isVisible(), 5)
    assert window.notice.likes.names() == ["小鹿", "心动星星"]
    # 记录 has the lobby, every seat read.
    assert len(window.store.scans) == 1
    assert [item["name"] for item in window.store.scans[0]["names"]] == list(SAMPLE_NAMES)
    window.notice.hide()

    # --- 6. The 检查 panel: 完整模式 (asked once) and 自动检查 (not asked). ---------------------
    asked: list[str] = []
    monkeypatch.setattr(ui.ConfirmDialog, "ask", staticmethod(lambda _p, title, *_a, **_k: asked.append(title) or True))
    window.status_chip.click()
    assert window.check_panel.isVisible()
    window.full_on.click()
    window.auto_on.click()
    window.auto_off.click()
    assert asked == ["开启完整模式"]
    assert (window.store.safe_mode, window.store.auto_capture) == (False, False)
    window.check_panel.close_panel()

    # --- 7. The same lobby in 完整模式: the marks over the game and the red glow. ----------------
    window.check_now()
    _wait(qapp, lambda: window.hit_card.isVisible())
    assert window.panel.mode == "both" and window.alert.isVisible() and window.like_card.isVisible()
    assert window.love.playing(), "the 嘉宾's 场景 with a 黑名单 player there too"
    window._hide_panel_after_title()

    # --- 8. 直播模式: viewers get the 嘉宾 marks, never the 黑名单 card, and no 黑名单 name shows. ---
    window._set_stream_mode(True)
    window.check_now()
    _wait(qapp, lambda: window.hit_card.isVisible())
    shown = window.stream._marks()
    assert window.like_card in shown and window.hit_card not in shown
    assert window._names_hidden(), "the 黑名单 page hides its names while 直播模式 is on"
    window._show_records_page()
    window._show_history_scan(0)
    table = window.history_table
    seats = [table.cellWidget(row, column) for row in range(table.rowCount()) for column in range(table.columnCount())]
    record = [label.text() for seat in seats if seat for label in seat.findChildren(type(window.history_empty.hint))]
    assert "示例坏人" not in record and any(text.startswith("示") and "*" in text for text in record), record
    assert "柠檬汽水" in record, "记录 masks the 黑名单 seat, not the others"
    window._hide_panel_after_title()
    window._set_stream_mode(False)

    # --- 9. Two 嘉宾 players and no 黑名单: the 嘉宾 scene and the music. -------------------------
    played: list = []
    window.music = ThemeMusic(play=played.append)
    # Their 组合's 玫瑰花边, with its wedding march (经典 greets in silence).
    window.store.set_combos([Combo(("心动小鹿", "心动星星"), Scenes(("lace",)))])
    window.store.remove_at(0)
    window._love_played = False
    window.check_now()
    _wait(qapp, lambda: window.love.playing() or window.panel.mode == "liked")
    assert window.panel.mode == "liked" and window.love.playing() and window.love.scene == "lace"
    assert played == [TUNES["lace"]]
    window.love.stop()
    window._hide_panel_after_title()

    # --- 10. 嘉宾场景: every scene previews, silent; 设置 › 声音 › 静音 is kept. ---------------------
    picker = GuestScenesDialog(window.store, ("like", window.store.like_index("心动小鹿")), parent=window)
    heard = len(played)
    # On 随机 the grid is greyed: 随机 off, the scenes take clicks.
    assert not picker.scenes.isEnabled()
    picker.random_box.click()
    for key in love_scenes.KEYS:
        picker.buttons[key].click()
        assert picker.preview.scene == key
        picker.preview.grab()
    picker.buttons["stars"].click()
    picker.play_button.click()
    picker._accept()
    assert picker.key == "stars" and len(played) == heard
    window.mute_box.click()
    assert Store(window.store.root).sound_muted is True
    # Every scene plays through over a real-size screen, the button left bare.
    stage = love_scenes.sample_stage()
    for key in love_scenes.KEYS:
        paint = love_scenes.load(key).make(stage)
        for t in (0.5, 2.0, 3.5):
            image = QImage(round(stage.width), round(stage.height), QImage.Format_ARGB32_Premultiplied)
            image.fill(0)
            painter = QPainter(image)
            paint(painter, t)
            painter.end()
            middle = stage.gap.center()
            assert image.pixelColor(round(middle.x()), round(stage.gap.top() + 60)).alpha() < 40, key

    # --- 11. 记录: the same lobby checked four times is one record, under today's heading. ---------
    window._show_records_page()
    window._reload_history()
    assert len(window.store.scans) == 1
    assert window.history_list.count() == 2, "today's heading and the lobby"
    window._show_history_scan(0)

    # --- 12. 设置: 环境测试 from 帮助, timed for real, and its report; then 导出日志. -----------------
    from blacklist_detect.ui_dialogs import FlowReportDialog

    window._show_settings_page()
    window.test_button.click()
    _wait(qapp, lambda: window.findChild(FlowReportDialog) is not None or window.setup.state == "failed")
    report = window.findChild(FlowReportDialog)
    assert report is not None, window.setup.message.text()
    test = window._flow_test
    assert test.right == 12 and test.glance_found and len(test.runs) == 3
    assert test.hotkey_total() > 0 and set(test.hotkey()) == {"capture", "find", "read"}
    assert report.headline.text().startswith("检查一次约")
    report.accept()
    from blacklist_detect import diagnostics

    real_export = diagnostics.export_logs
    monkeypatch.setattr(ui, "export_logs", lambda root, summary, report="": real_export(root, summary, tmp_path / "desk", report=report))
    import subprocess

    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: None)
    window._export_logs()
    exported = list((tmp_path / "desk").glob("*.txt"))
    assert len(exported) == 1
    text = exported[0].read_text(encoding="utf-8")
    assert "==== 最近一次环境测试 ====" in text
    for name in ("路人乙", "心动小鹿", "小林同学"):
        assert name not in text, "the log a friend sends holds no player's name"

    # --- 13. 清空数据: everything goes, the defaults come back. -----------------------------------
    monkeypatch.setattr(ui, "_confirm", lambda *_args: True)
    window._ask_reset()
    fresh = Store(window.store.root)
    assert fresh.entries == [] and fresh.likes == [] and fresh.scans == [] and fresh.player_name == ""
    assert fresh.sound_muted is False and fresh.scene_sounds == {}
    assert fresh.safe_mode is True and fresh.consented == []
    window._watch_timer.stop()
    window.close()
