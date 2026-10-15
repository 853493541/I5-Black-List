"""Several 场景 per 嘉宾 and per 组合: ticked in 选择场景, or 不放, saved and read back (the old one-theme form
too), and which a lobby gets."""

import json
import random

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from blacklist_detect.guests import lobby_choice, ticked  # noqa: E402
from blacklist_detect.love_scenes import KEYS, choose  # noqa: E402
from blacklist_detect.model import Combo, Entry, Scenes  # noqa: E402
from blacklist_detect.pipeline import CheckResult, NameSlot  # noqa: E402
from blacklist_detect.storage import Store  # noqa: E402

OFF = Scenes(off=True)


@pytest.fixture(scope="module")
def qapp():  # noqa: ANN201
    return QApplication.instance() or QApplication([])


# Choosing one -------------------------------------------------------------------------------------


def test_several_ticked_play_one_of_them_never_the_last_twice_in_a_row():
    rng = random.Random(4)
    last, seen = "", []
    for _ in range(60):
        scene = choose(("ice", "stars", "cyber"), last, rng)
        assert scene in ("ice", "stars", "cyber") and scene != last
        seen.append(scene)
        last = scene
    assert set(seen) == {"ice", "stars", "cyber"}
    # One ticked: that one, again and again.
    assert [choose(("ice",), "ice", rng) for _ in range(3)] == ["ice"] * 3
    assert choose("ice", "ice", rng) == "ice"


def test_a_ticked_scene_this_version_does_not_have_is_left_out():
    rng = random.Random(1)
    # 香槟 is 天使 now; 缎带 is gone.
    assert {choose(("champagne", "ribbon", "ice"), "ice", rng) for _ in range(20)} == {"angel"}
    # None left: any scene, but the last.
    assert {choose(("ribbon", "gone"), "classic", rng) for _ in range(200)} == set(KEYS) - {"classic"}
    # Any scene, none ticked: never the last twice either.
    picks = [choose("random", "lace", rng) for _ in range(200)]
    assert "lace" not in picks and set(picks) == set(KEYS) - {"lace"}
    assert choose("off", "", rng) == ""


# Who decides in a lobby ---------------------------------------------------------------------------

LIKES = [
    Entry("小明", scenes=Scenes(("cyber", "ice"))),
    Entry("小红"),
    Entry("阿星", scenes=Scenes(("angel",))),
    Entry("不要场景的人", scenes=OFF),
    Entry("新来的"),
]


def _here(*names: str) -> list[Entry]:
    return [like for like in LIKES if like.name in names]


def test_several_ticked_come_as_a_choice_of_them():
    assert lobby_choice(LIKES, [], _here("小明", "小红"), "classic") == ("cyber", "ice")
    assert ticked(Scenes(("champagne", "angel", "ribbon"))) == ("angel",)


def test_a_guest_on_no_scene_is_passed_over_and_the_next_decides():
    # 不要场景的人 is above 阿星: 阿星 decides.
    assert lobby_choice(LIKES, [], _here("阿星", "不要场景的人"), "classic") == "angel"
    # Above 小红, who ticked none: any scene.
    assert lobby_choice(LIKES, [], _here("小红", "不要场景的人"), "classic") == "random"
    # Every one there on 不放: no scene.
    assert lobby_choice(LIKES, [], _here("不要场景的人"), "classic") == "off"


def test_the_top_guest_with_scenes_ticked_comes_before_one_with_none():
    # 新来的 tops the list with none ticked; 小明 below has his: his.
    assert lobby_choice(LIKES, [], _here("新来的", "小明"), "classic") == ("cyber", "ice")
    # 新来的 and 小红, none ticked either: any scene.
    assert lobby_choice(LIKES, [], _here("新来的", "小红"), "classic") == "random"


def test_a_combination_on_no_scene_gives_way_to_the_next_in_line():
    combos = [
        Combo(("小明", "小红", "阿星"), OFF),
        Combo(("小明", "小红"), Scenes(("lace", "stars"))),
        Combo(("阿星", "不要场景的人"), OFF),
        Combo(("小红", "新来的"), Scenes()),
    ]
    # The biggest is on 不放: the next combination there decides.
    assert lobby_choice(LIKES, combos, _here("小明", "小红", "阿星"), "classic") == ("lace", "stars")
    # A combination on 不放 alone: the list decides.
    assert lobby_choice(LIKES, combos, _here("阿星", "不要场景的人"), "classic") == "angel"
    # One with none ticked: any scene, even with 小明's own there.
    assert lobby_choice(LIKES, combos, _here("小红", "新来的", "阿星"), "classic") == "random"
    # Everyone and every combination there on 不放: no scene.
    only = [Combo(("不要场景的人", "也不要的人"), Scenes(("ice",)))]
    nobody = [Entry("不要场景的人", scenes=OFF), Entry("也不要的人", scenes=OFF)]
    assert lobby_choice(nobody, [Combo(("不要场景的人", "也不要的人"), OFF)], nobody, "classic") == "off"
    assert lobby_choice(nobody, only, nobody, "classic") == "ice"


# Saved and read back ------------------------------------------------------------------------------


def test_the_old_one_theme_form_is_read(tmp_path):
    (tmp_path / "likes.json").write_text(
        json.dumps(
            {
                "likes": [
                    {"name": "小明", "theme": "cyber"},
                    {"name": "小红", "theme": ""},
                    {"name": "阿星", "theme": "champagne"},
                    {"name": "新来的"},
                ],
                "combos": [{"names": ["小明", "小红"], "theme": "equation"}, {"names": ["小红", "阿星"], "theme": ""}],
            }
        ),
        encoding="utf-8",
    )
    store = Store(tmp_path)
    assert [like.scenes for like in store.likes] == [Scenes(("cyber",)), Scenes(), Scenes(("angel",)), Scenes()]
    assert [combo.scenes for combo in store.combos] == [Scenes(("equation",)), Scenes()]
    assert store.load_warning == ""


def test_the_new_form_is_saved_and_read_back(tmp_path):
    store = Store(tmp_path)
    store.add_like("小明", scenes=Scenes(("cyber", "ice", "cyber")))
    store.add_like("小红", scenes=Scenes(("lace",), off=True))
    store.add_like("阿星")
    store.set_combos([Combo(("小明", "小红"), Scenes(("stars", "neon"))), Combo(("小红", "阿星"), OFF)])
    saved = json.loads((tmp_path / "likes.json").read_text(encoding="utf-8"))
    assert saved["likes"][0]["scenes"] == ["cyber", "ice"] and saved["likes"][1]["no_scene"] is True
    assert "theme" not in saved["likes"][0]
    again = Store(tmp_path)
    # Each once; 不放 keeps its ticks for 放场景.
    assert [like.scenes for like in again.likes] == [Scenes(("cyber", "ice")), Scenes(("lace",), True), Scenes()]
    assert [combo.scenes for combo in again.combos] == [Scenes(("stars", "neon")), OFF]


@pytest.mark.parametrize(
    "scenes, off, kept",
    [
        (None, None, Scenes()),
        ("ice", "yes", Scenes()),
        ([1, None, {"a": 1}, "", "  ice  ", "ice"], 1, Scenes(("ice",))),
        ({"ice": True}, [], Scenes()),
        (["x" * 500], True, Scenes(("x" * 40,), off=True)),
    ],
)
def test_bad_scenes_never_lose_the_list(tmp_path, scenes, off, kept):
    (tmp_path / "likes.json").write_text(
        json.dumps({"likes": [{"name": "小明", "scenes": scenes, "no_scene": off}], "combos": [{"names": ["小明", "小红"], "scenes": scenes}]}),
        encoding="utf-8",
    )
    store = Store(tmp_path)
    assert store.load_warning == "" and [like.name for like in store.likes] == ["小明"] and len(store.combos) == 1
    assert store.likes[0].scenes == kept and store.combos[0].scenes == Scenes(kept.keys)


def test_a_scene_dropped_since_is_skipped_in_a_lobby(tmp_path):
    (tmp_path / "likes.json").write_text(json.dumps({"likes": [{"name": "小明", "scenes": ["ribbon", "ice"]}]}), encoding="utf-8")
    store = Store(tmp_path)
    assert lobby_choice(store.likes, [], store.likes, "classic") == "ice"
    store.update_like(0, "小明", scenes=Scenes(("ribbon",)))
    assert lobby_choice(store.likes, [], store.likes, "classic") == "random"


# The window ---------------------------------------------------------------------------------------


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    from blacklist_detect.ui import MainWindow
    from blacklist_detect.ui_music import ThemeMusic

    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    made = MainWindow()
    # The marks over the game: 完整模式 and 自动检查, agreed to once.
    made.store.consented = ["full", "auto"]
    made._on_display_mode("full")
    made._on_auto_mode("auto")
    made._watch_timer.stop()
    made.store.disclaimer_accepted = True
    tunes: list = []
    made.music = ThemeMusic(play=tunes.append, sounds=made.store.scene_sound)
    made.tunes = tunes
    made._live_check = True
    yield made
    made.notice.hide()
    made.love.stop()
    made.close()


def _lobby(*names: str) -> CheckResult:
    screen = QApplication.primaryScreen().availableGeometry()
    left = screen.left() + screen.width() // 2 - 90
    button = (left, screen.top() + 300, left + 180, screen.top() + 360)
    slots = [NameSlot(index, (100 * index, 100, 100 * index + 80, 130), name, name, False, 0.9, False) for index, name in enumerate(names)]
    return CheckResult(True, "", names=slots, button_box=button)


def _check(window, *names: str) -> None:  # noqa: ANN001
    result = _lobby(*names)
    window._hide_panel_after_title()
    window.love.stop()
    window._love_played = False
    window.music._last_lobby = frozenset()
    window._on_lobby_placed(result.button_box)
    window._show_panel(result)


def test_a_lobby_plays_one_of_the_ticked_never_the_same_twice_in_a_row(window):
    window.store.add_like("小明", scenes=Scenes(("ice", "stars")))
    played = []
    for _ in range(6):
        _check(window, "小明")
        assert window.love.playing()
        played.append(window.love.scene)
    assert set(played) == {"ice", "stars"} and all(a != b for a, b in zip(played, played[1:], strict=False))
    # The marks wear the look of the one playing.
    from blacklist_detect.ui_overlay import love_look

    assert window.like_card.look == love_look(played[-1])


@pytest.mark.parametrize("scenes", [Scenes(("ice", "stars", "angel")), Scenes()])
def test_in_safe_mode_each_lobby_draws_its_own_music_never_the_same_twice_in_a_row(window, scenes):
    from pathlib import Path

    # 安全模式 shows no scene over the game: the music is all a lobby gets of it.
    window._on_display_mode("safe")
    window.store.add_like("小明", scenes=scenes)
    for _ in range(10):
        _check(window, "小明")
        assert not window.love.playing()
    heard = [Path(tune).name for tune in window.tunes if tune]
    assert len(set(heard)) > 1 and all(a != b for a, b in zip(heard, heard[1:], strict=False))


def test_a_lobby_with_everyone_on_no_scene_shows_the_marks_and_plays_nothing(window):
    window.store.add_like("小明", scenes=Scenes(("ice",), off=True))
    window.store.add_like("小红", scenes=OFF)
    _check(window, "小明", "小红")
    assert window._lobby_choice == "off" and not window.love.playing()
    assert window.panel.mode == "liked" and window.like_card.isVisible()
    assert not any(window.tunes), "no scene, no sound"
    # Back on 放场景, its own again.
    window.store.update_like(0, "小明", scenes=Scenes(("ice",)))
    _check(window, "小明")
    assert window.love.scene == "ice"


def _sounds(window) -> list[str]:  # noqa: ANN001
    from pathlib import Path

    return [Path(tune).name for tune in window.tunes if tune]


def test_the_same_lobby_checked_again_keeps_its_scene_and_plays_no_other_music(window):
    # 经典 (no sound) drawn: 冰蓝极光 just played.
    window.store.add_like("小明", scenes=Scenes(("classic", "ice")))
    window.love._last = "ice"
    _check(window, "小明")
    assert window.love.scene == "classic" and not _sounds(window)
    result = _lobby("小明")
    window._on_lobby_placed(result.button_box)
    window._show_panel(result)
    assert window.love.scene == "classic" and window.love._last == "classic"
    assert not _sounds(window), "another scene's music over 经典"


def test_a_lobby_checked_again_with_one_more_guest_plays_the_music_of_the_scene_shown(window):
    from blacklist_detect.ui_overlay import love_look

    window.store.add_like("小明", scenes=Scenes(("ice", "stars")))
    window.store.add_like("小红", scenes=Scenes(("ice", "stars")))
    _check(window, "小明")
    shown = window.love.scene
    assert _sounds(window) == [f"theme-{shown}.wav"]
    # 检查 pressed again with the marks up (it stops the scene), and it reads 小红 too.
    window.love.stop()
    result = _lobby("小明", "小红")
    window._on_lobby_placed(result.button_box)
    window._show_panel(result)
    assert window.love.scene == shown and window.like_card.look == love_look(shown)
    assert set(_sounds(window)) == {f"theme-{shown}.wav"}


def test_in_safe_mode_a_silent_scene_greets_the_lobby_and_checking_again_plays_no_other(window):
    window._on_display_mode("safe")
    window.store.add_like("小明", scenes=Scenes(("classic", "ice")))
    # Draws 经典 for the first check, 冰蓝极光 when asked again.
    order = ["classic", "ice"]
    window.love._rng = type("Rng", (), {"choice": staticmethod(lambda pool: order.pop(0) if order[0] in pool else pool[0])})()
    _check(window, "小明")
    window._show_panel(_lobby("小明"))
    assert not _sounds(window)


def test_with_a_blacklist_player_too_several_ticked_dress_the_marks_as_classic(window):
    from blacklist_detect.pipeline import Hit
    from blacklist_detect.ui_overlay import love_look

    window.store.add_like("小明", scenes=Scenes(("ice", "stars")))
    result = _lobby("小明", "坏人")
    result = CheckResult(True, "", names=result.names, hits=[Hit(1, "坏人", "坏人", "", False, "", ())], button_box=result.button_box)
    window._on_lobby_placed(result.button_box)
    window._show_panel(result)
    assert window.panel.mode == "both" and window.panel.look is love_look("classic") and not window.love.playing()


# 选择场景 -------------------------------------------------------------------------------------------


def test_the_picker_ticks_without_moving_the_highlight(qapp):
    from blacklist_detect.ui_love_pick import ScenePicker

    picker = ScenePicker(Scenes(("champagne", "ice")), "心动小鹿")
    # 放场景 first, the default; the first ticked highlighted and playing; 香槟 ticked as 天使.
    assert list(picker.mode.buttons) == ["on", "off"] and [b.text() for b in picker.mode.buttons.values()] == ["放场景", "不放"]
    assert picker.mode.current() == "on" and picker.key == "angel" and picker.preview.scene == "angel"
    assert picker.scenes.chosen() == ("ice", "angel") and picker.hint.text() == "都不选：每次随机放一个"
    assert not picker.has_changes()
    # A click on a box ticks it; the highlight stays.
    stars = picker.buttons["stars"]
    stars.resize(200, stars.H)
    QTest.mouseClick(stars, Qt.LeftButton, Qt.NoModifier, QPoint(stars.width() - 24, stars.height() // 2))
    assert picker.scenes.chosen() == ("ice", "stars", "angel") and picker.key == "angel" and not stars.isChecked()
    # A click on the name highlights it and plays it.
    QTest.mouseClick(stars, Qt.LeftButton, Qt.NoModifier, QPoint(40, stars.height() // 2))
    assert picker.key == "stars" and picker.preview.scene == "stars" and stars.chosen
    # Space on one ticks or unticks it.
    QTest.keyClick(picker.buttons["ice"], Qt.Key_Space)
    assert picker.scenes.chosen() == ("stars", "angel") and picker.key == "stars"
    assert picker.has_changes() and picker.value() == Scenes(("stars", "angel"))
    for button in picker.buttons.values():
        button.grab()
    picker.done(QDialog.Rejected)


def test_no_scene_greys_the_list_and_keeps_the_ticks(qapp):
    from blacklist_detect.ui_love_pick import ScenePicker

    picker = ScenePicker(Scenes(("ice",)))
    picker.mode.buttons["off"].click()
    assert not picker.scenes.isEnabled() and picker.hint.isHidden()
    assert picker.value() == Scenes(("ice",), off=True)
    picker.buttons["ice"].grab()
    picker.mode.buttons["on"].click()
    assert picker.scenes.isEnabled() and not picker.hint.isHidden() and picker.value() == Scenes(("ice",))
    # Opened on 不放, it starts greyed.
    off = ScenePicker(OFF)
    assert not off.scenes.isEnabled() and off.hint.isHidden()
    # None ticked: 经典 highlighted, nothing ticked.
    picker = ScenePicker(Scenes())
    assert picker.key == "classic" and picker.scenes.chosen() == () and picker.value() == Scenes()
    picker.done(QDialog.Rejected)


def test_the_scene_row_says_what_is_ticked(qapp, monkeypatch):
    from blacklist_detect.ui_guests import ThemeField, scenes_said
    from blacklist_detect.ui_love_pick import ScenePicker

    field = ThemeField(Scenes(("ice",)), "小明")
    size = field.picture.size()
    assert field.name.text() == "冰蓝极光" and field.toolTip() == ""

    def answer(scenes: Scenes, result: int = QDialog.Accepted):  # noqa: ANN202
        def run(picker) -> int:  # noqa: ANN001
            picker.scenes.set_chosen(scenes.keys)
            picker.mode.set_current("off" if scenes.off else "on")
            picker.done(result)
            return result

        return run

    for scenes, words in (
        (Scenes(("ice", "stars", "cyber")), "3个场景 · 随机"),
        (Scenes(), "全部场景 · 随机"),
        (Scenes(("ice", "stars"), off=True), "不放场景"),
        (Scenes(("lace",)), "玫瑰花边"),
    ):
        monkeypatch.setattr(ScenePicker, "exec", answer(scenes))
        field.change_button.click()
        assert field.value() == scenes and field.name.text() == words, words
        # One picture, a stack or none: the row keeps its size.
        assert field.picture.size() == size and not field.picture.pixmap().isNull()
    field.change_button.click()
    monkeypatch.setattr(ScenePicker, "exec", answer(Scenes(("ice", "stars"))))
    field.change_button.click()
    assert field.toolTip() == "冰蓝极光、星河许愿"
    # 取消 changes nothing.
    monkeypatch.setattr(ScenePicker, "exec", answer(Scenes(("claw",)), QDialog.Rejected))
    field.change_button.click()
    assert field.value() == Scenes(("ice", "stars"))
    # The list says it in a word or two.
    assert [scenes_said(s) for s in (Scenes(("ice",)), Scenes(("ice", "lace")), Scenes(), OFF, Scenes(("ribbon",)))] == [
        "冰蓝极光", "2个场景", "全部随机", "不放", "全部随机",
    ]  # fmt: skip


def test_the_guest_list_shows_each_one_s_scenes(window):
    page, store = window.likes_page, window.store
    store.add_like("小明", scenes=Scenes(("ice", "stars")))
    store.add_like("小红", scenes=OFF)
    store.add_like("阿星", scenes=Scenes(("angel",)))
    store.set_combos([Combo(("小明", "小红"), Scenes(("lace", "neon", "claw"))), Combo(("小红", "阿星"), OFF)])
    page.refresh()
    cells = [page.table.item(row, 2).text() for row in range(page.table.rowCount())]
    assert cells == ["3个场景", "不放", "金色传说", "不放", "2个场景"]
    assert page.table.horizontalHeaderItem(2).text() == "场景"


def test_the_guest_dialog_saves_the_scenes_ticked(window, monkeypatch):
    from blacklist_detect.ui_likes import LikeDialog
    from blacklist_detect.ui_love_pick import ScenePicker

    def tick(picker) -> int:  # noqa: ANN001
        picker.scenes.set_chosen(("ice", "fluffy"))
        picker.accept()
        return picker.result()

    def edit(dialog) -> int:  # noqa: ANN001
        dialog.name_edit.setText("小明")
        monkeypatch.setattr(ScenePicker, "exec", tick)
        dialog.theme_field.change_button.click()
        assert dialog.has_changes()
        dialog._accept()
        return dialog.result()

    monkeypatch.setattr(LikeDialog, "exec", edit)
    window.likes_page.add_one()
    assert window.store.likes[0].scenes == Scenes(("ice", "fluffy"))
    assert Store(window.store.root).likes[0].scenes == Scenes(("ice", "fluffy"))


# 场景, not 特效 ------------------------------------------------------------------------------------


def _words(root) -> list[str]:  # noqa: ANN001
    """Everything a player reads on root and in it: texts, tips and the names a screen reader says."""
    from PySide6.QtWidgets import QAbstractButton, QLabel, QLineEdit, QWidget

    said = []
    for widget in [root, *root.findChildren(QWidget)]:
        said += [widget.toolTip(), widget.accessibleName(), widget.accessibleDescription(), widget.windowTitle()]
        if isinstance(widget, QAbstractButton | QLabel):
            said.append(widget.text())
        if isinstance(widget, QLineEdit):
            said.append(widget.placeholderText())
    return said


def test_the_player_reads_scene_never_effect(window):
    from blacklist_detect import livehime
    from blacklist_detect.ui_guests import ComboDialog
    from blacklist_detect.ui_likes import LikeDialog
    from blacklist_detect.ui_love_pick import ScenePicker

    window.store.add_like("小明")
    window.store.add_like("小红")
    assert window._tab_buttons[window.effects_tab].name() == "场景管理"
    for root in (window, LikeDialog(parent=window), ComboDialog(window.store.likes, parent=window), ScenePicker(parent=window)):
        assert not [words for words in _words(root) if "特效" in words], root
    # 直播姬's own scenes are said to be 直播姬's.
    assert all("直播姬场景" in words for words in livehime.WORDS.values() if "场景" in words)
