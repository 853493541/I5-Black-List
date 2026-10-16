"""场景管理: every 场景's 配乐, and which one the 场景 hotkey plays, in a dialog opened from the 嘉宾 page.

On the left, the hotkey, set the way 检查's is (the window's hotkey box), what it does under it, and what is
wrong with a key pressed for it; then every scene in love_scenes.SCENES by name with its dot, the list
嘉宾场景 (ui_guest_scenes) has in a grid; past the height of what is beside it, the list scrolls. A click on a
name shows one: it plays beside the list over the fake-name sample lobby; the dialog opens on the one shown
last, still, at its best moment, as a scene takes up to a second to make. The spot at a scene's end is the
hotkey's: ✓ on the 场景 it plays (at once over the game, with no check: MainWindow.play_quick_scene), and a
click on another's gives it the hotkey. A ♪ is a 场景 that plays one of the player's songs.

Under the preview, the shown 场景's 配乐: its 音量 and ▶ 播放 (the scene from its start with its music, ⏸ 暂停
while it plays), then on the left under it its choices (SoundChoices: 默认, its own, and up to three songs of
the player's, each 上传 from a file, a part of it picked in 选择片段 when it is longer than a 场景's sound may
be; one is chosen, a click on 默认 back to it), each with its ▶, ⏸ and a moving wave while it plays.

The preview plays only while it can be seen, its window not minimized, and the app is in front: behind the
game it would paint 30 times a second for nothing. The page lives on in EffectsDialog, made once with the
window: × and Esc close it, which rests the preview and stops a sound ▶ started.
"""

from __future__ import annotations

import itertools
import shutil
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFontMetrics, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from blacklist_detect import love_scenes, sound_import
from blacklist_detect.paths import custom_sound_dir
from blacklist_detect.sound_import import CLIP_S, SoundImportError
from blacklist_detect.storage import MAX_SONGS
from blacklist_detect.ui_kit import _SCROLL_BAR, IconButton, Modal
from blacklist_detect.ui_love_pick import SceneList, ScenePreview
from blacklist_detect.ui_music import TUNES, VOLUME_STEP, tune_seconds
from blacklist_detect.ui_sound_trim import SoundTrimDialog, _glyph
from blacklist_detect.ui_soundwave import SoundWave, pause_icon
from blacklist_detect.ui_theme import THEME, _dialog_style, chinese_family, chinese_font

# What ▶ 播放 started, as against a row's sound (its file, "" for 默认).
_SCENE = "scene"


class _Clock:
    """The preview's clock, as QElapsedTimer's start, isValid and elapsed (ms), that can also stand still: hold
    stops it where it is, go goes on from there."""

    def __init__(self) -> None:
        self._began: float | None = None
        self._held: float | None = None

    def start(self) -> None:
        self._began, self._held = time.monotonic(), None

    def isValid(self) -> bool:  # noqa: N802
        return self._began is not None

    def elapsed(self) -> int:
        if self._began is None:
            return 0
        return round(1000 * (self._held if self._held is not None else time.monotonic() - self._began))

    def hold(self) -> None:
        if self._began is not None and self._held is None:
            self._held = time.monotonic() - self._began

    def go(self) -> None:
        if self._held is not None:
            self._began, self._held = time.monotonic() - self._held, None

    @property
    def held(self) -> bool:
        return self._held is not None


class _Preview(ScenePreview):
    """场景管理's preview, which ▶ 播放's 暂停 holds still where the scene is (hold), to go on from there (go)."""

    def __init__(self, width: int) -> None:
        super().__init__(width=width)
        self._clock = _Clock()

    @property
    def held(self) -> bool:
        return self._clock.held

    def hold(self) -> None:
        self._clock.hold()
        self.pause()
        self.update()

    def go(self, run: bool = True) -> None:  # noqa: FBT001, FBT002
        """On from where it was held; run: playing now, else once it is in sight again (resume)."""
        self._clock.go()
        if run:
            self.resume(from_start=False)


class _ListScroll(QScrollArea):
    """The scene list, as tall as the room it is given (_HotkeySide keeps room for every scene): past that,
    while a note under the hotkey shows, it scrolls. Its scroll bar's room is kept beside the names."""

    def __init__(self, scenes: SceneList) -> None:
        super().__init__()
        self.setObjectName("sceneScroll")
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)
        # On the card's own colour, as 嘉宾场景's grid (ui_theme's rule for these names).
        self.viewport().setAutoFillBackground(False)
        scenes.setObjectName("sceneList")
        self.setWidget(scenes)
        self.setFixedWidth(scenes.minimumWidth() + _SCROLL_BAR + 4)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Ignored)

    def sizeHint(self) -> QSize:
        return QSize(self.width(), 0)

    def minimumSizeHint(self) -> QSize:
        return QSize(self.width(), 0)


class _HotkeySide(QWidget):
    """The page's left: 快捷键 and its box, what the hotkey does, a note about it while there is one, and the
    scene list. At least as tall as the hotkey's rows and every scene, so no scene is scrolled away; a note
    takes its room from the list, and the dialog keeps its size as one comes and goes."""

    # Between the hotkey's rows, and from them to the list.
    GAP = 4
    LIST_GAP = 12

    def __init__(self, hotkey_box: QLineEdit, scroll: _ListScroll) -> None:
        super().__init__()
        self.scroll = scroll
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(self.LIST_GAP)
        rows = QVBoxLayout()
        rows.setSpacing(self.GAP)
        column.addLayout(rows)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.label = QLabel("快捷键")
        self.label.setObjectName("rowLabel")
        row.addWidget(self.label)
        self.box = hotkey_box
        row.addWidget(hotkey_box)
        row.addStretch(1)
        rows.addLayout(row)
        self.hint = QLabel("按快捷键，在当前窗口播放勾选的场景")
        self.hint.setObjectName("rowHint")
        self.hint.setWordWrap(True)
        self.hint.setFixedWidth(scroll.width())
        rows.addWidget(self.hint)
        # What is wrong with a key pressed for the hotkey, as 检查 says it: underlined, a warning.
        self.note = QLabel("")
        self.note.setObjectName("rowHint")
        self.note.setProperty("tone", "warn")
        self.note.setWordWrap(True)
        self.note.setFixedWidth(scroll.width())
        self.note.hide()
        rows.addWidget(self.note)
        column.addWidget(scroll, 1)
        self.keep_room()

    def keep_room(self) -> None:
        """A minimum of its own, which the layouts hold to also when they measure height for width (its notes
        wrap): the hotkey's row, the line under it, the gaps and every scene, in the style's sizes."""
        self.ensurePolished()
        row = max(self.label.sizeHint().height(), self.box.sizeHint().height())
        hint = self.hint.heightForWidth(self.hint.width())
        room = row + self.GAP + hint + self.LIST_GAP + self.scroll.widget().minimumSizeHint().height()
        if room != self.minimumHeight():
            self.setMinimumHeight(room)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        self.keep_room()


def _button(text: str, action, primary: bool = False) -> QPushButton:  # noqa: ANN001
    button = QPushButton(text)
    if primary:
        button.setObjectName("primary")
    button.setAutoDefault(False)
    button.setCursor(Qt.PointingHandCursor)
    button.clicked.connect(lambda: action())
    return button


class _Choice(QRadioButton):
    """A sound to choose, its words cut in the middle when its room is too narrow for them, whole in its
    tooltip then."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.full = ""
        self.setFont(chinese_font())
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def set_full(self, text: str) -> None:
        self.full = text
        self.setAccessibleName(text)
        self.updateGeometry()
        self._fit()

    def _room(self) -> int:
        """How wide the words may be: the button less its circle and the gap after it."""
        return self.width() - (super().sizeHint().width() - self.fontMetrics().horizontalAdvance(self.text()))

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        words = self.fontMetrics().horizontalAdvance(self.full) - self.fontMetrics().horizontalAdvance(self.text())
        return QSize(hint.width() + words + 2, hint.height())

    def minimumSizeHint(self) -> QSize:
        # Six "…" wide, cut that far; a shorter name (默认) only as wide as it is, its ▶ right after it.
        least = min(self.fontMetrics().horizontalAdvance("…") * 6, self.sizeHint().width())
        return QSize(least, super().minimumSizeHint().height())

    def _fit(self) -> None:
        shown = self.fontMetrics().elidedText(self.full, Qt.ElideMiddle, max(1, self._room() - 2))
        if shown != self.text():
            self.setText(shown)
        self.setToolTip(self.full if shown != self.full else "")

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._fit()


class _Listen(IconButton):
    """▶ beside a sound, ⏸ in the accent while it plays (set_playing)."""

    playing = False

    def __init__(self) -> None:
        super().__init__("play", "播放")

    def set_playing(self, on: bool) -> None:  # noqa: FBT001
        if on != self.playing:
            self.playing = on
            self.refresh()

    def refresh(self) -> None:
        if self.playing:
            self.setIcon(pause_icon(16, THEME["accent"]))
        else:
            super().refresh()


class SoundChoices(QWidget):
    """场景管理's 配乐: what the shown 场景 may play, one of them chosen like a radio button. 默认 first (the scene's
    own, with its length; 经典's is none, 默认（无声）), then each of the player's songs, its name and length, up to MAX_SONGS. Each
    has ▶ (play(file), "" for 默认) and each song ✕ (delete(file)); a click on one, or ↑ and ↓, chooses it
    (chose(file)), and nothing plays by itself. While a row's sound plays (set_playing) its ▶ is ⏸ and a wave
    moves right after it; paused, it is ▶ again, to go on. 上传 sits at the right end of 默认's row, off once
    there are MAX_SONGS songs; a click on 默认 goes back to it. Its rows are made once and
    shown as there are songs, so after a ✕ the next song is under it: a second click as quick as a double-click's
    deletes nothing."""

    chose = Signal(str)
    play = Signal(str)
    delete = Signal(str)

    def __init__(self, upload, parent: QWidget | None = None) -> None:  # noqa: ANN001
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        # By row: 默认, then a song in each. files[row] is the file of the song shown there, "" for 默认.
        self.files = [""] * (1 + MAX_SONGS)
        self.choices: list[_Choice] = []
        self.play_buttons: list[_Listen] = []
        self.delete_buttons: list[IconButton] = []
        self.waves: list[SoundWave] = []
        self._lines: list[QHBoxLayout] = []
        # When a ✕ last deleted a song (time.monotonic()).
        self._deleted_at = 0.0
        # Whether 默认 plays anything, and whether 静音 is on: under it no ▶ can be pressed, as 选择片段's 试听.
        self._sounds = True
        self._muted = False
        # The row whose sound ▶ started, None for none, and whether it waits paused.
        self._playing: int | None = None
        self._paused = False
        self.upload_button = _button("上传", upload)
        self.upload_button.setAccessibleName("上传配乐")
        for row in range(1 + MAX_SONGS):
            # Each row packed on the left from its name, as 配乐's above; its wave right after its ▶, in room kept
            # while it is still, so nothing on the row moves as it starts: a second click to pause lands on ⏸, not ✕.
            line = QHBoxLayout()
            line.setSpacing(6)
            column.addLayout(line)
            self._lines.append(line)
            choice = _Choice()
            choice.clicked.connect(lambda _checked=False, row=row: self.chose.emit(self.files[row]))
            choice.installEventFilter(self)
            self.group.addButton(choice)
            line.addWidget(choice)
            listen = _Listen()
            listen.clicked.connect(lambda _checked=False, row=row: self.play.emit(self.files[row]))
            line.addWidget(listen)
            wave = SoundWave()
            line.addWidget(wave, 0, Qt.AlignVCenter)
            self.waves.append(wave)
            self.choices.append(choice)
            self.play_buttons.append(listen)
            if row:
                gone = IconButton("close", "删掉这首")
                gone.clicked.connect(lambda _checked=False, row=row: self._gone(row))
                line.addWidget(gone)
                self.delete_buttons.append(gone)
            line.addStretch(1)
            if not row:
                # At the row's right end, under ▶ 播放's.
                line.addWidget(self.upload_button)

    def set_sounds(self, default: str, sounds: bool, songs: list[dict], chosen: str, room: int = 0) -> None:
        """default: what 默认 is called; sounds: whether it plays anything. songs: the 场景's, oldest first, each
        {"file", "name", "length"}; chosen: the file of the one it plays, "" for 默认. room: how many songs' rows
        the page keeps room for (EffectsPage puts that room at its foot, not between the rows)."""
        self.files = ["", *(song["file"] for song in songs[:MAX_SONGS])] + [""] * (MAX_SONGS - min(len(songs), MAX_SONGS))
        self.choices[0].set_full(default)
        self._sounds = sounds
        self._sync_play()
        for row, song in enumerate(songs[:MAX_SONGS], 1):
            self.choices[row].set_full(f"{song.get('name') or Path(song['file']).stem} · {song.get('length', CLIP_S):.1f} 秒")
        for row in range(1, 1 + MAX_SONGS):
            shown = row <= len(songs)
            for widget in (self.choices[row], self.play_buttons[row], self.delete_buttons[row - 1]):
                widget.setVisible(shown)
            # A row with no song takes no room, its wave's neither.
            self.waves[row].keep_room(shown)
        picked = self.files.index(chosen) if chosen and chosen in self.files else 0
        self.choices[picked].setChecked(True)
        full = len(songs) >= MAX_SONGS
        self.upload_button.setEnabled(not full)
        self.upload_button.setToolTip(f"最多 {MAX_SONGS} 首，先删掉一首" if full else "")
        # Each row's own layout measured anew now, not once it is next laid out: the page keeps its size by
        # what this says it needs (EffectsPage._sync_rows), and a row's layout keeps its last measure until then.
        for line in self._lines:
            line.invalidate()
        self.updateGeometry()

    def song_row_height(self) -> int:
        """How much taller a song's row makes 配乐: the tallest of its choice, ▶ and ✕, and the gap above it."""
        parts = (self.choices[1], self.play_buttons[1], self.delete_buttons[0])
        return max(part.sizeHint().height() for part in parts) + self.layout().spacing()

    def set_muted(self, muted: bool) -> None:
        """设置's 静音 on or off: under it every ▶ is off, saying 已静音."""
        self._muted = muted
        self._sync_play()

    def set_playing(self, file: str | None, paused: bool = False) -> None:  # noqa: FBT001, FBT002
        """The row of file ("" for 默认) as ▶ started its sound: playing, ⏸ and its wave moving, or paused, ▶ to go
        on where it stopped; None: every row ▶, no wave."""
        self._playing = self.files.index(file) if file is not None and file in self.files else None
        self._paused = paused
        self._sync_play()

    def _sync_play(self) -> None:
        for row, button in enumerate(self.play_buttons):
            mine = row == self._playing and not self._muted
            playing = mine and not self._paused
            button.setEnabled(not self._muted and (row > 0 or self._sounds))
            button.set_playing(playing)
            tip = "已静音" if self._muted else "暂停" if playing else "接着播放" if mine else "播放"
            button.setToolTip(tip)
            button.setAccessibleName(tip)
            self.waves[row].run(playing)

    def chosen(self) -> str:
        """The file of the one checked, "" for 默认."""
        return self.files[self.choices.index(self.group.checkedButton())] if self.group.checkedButton() else ""

    def _gone(self, row: int) -> None:
        """✕ on a row: its song deleted, unless a song was only just: the second click of a double-click would
        delete the one that moved up under it."""
        if time.monotonic() - self._deleted_at < QApplication.doubleClickInterval() / 1000:
            return
        self._deleted_at = time.monotonic()
        self.delete.emit(self.files[row])

    def eventFilter(self, watched, event) -> bool:  # noqa: ANN001
        # ↑ and ↓ choose the row above or below, as a click does, not only move to it.
        if watched in self.choices and event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key_Up, Qt.Key_Down):
            shown = [choice for choice in self.choices if not choice.isHidden()]
            at = shown.index(watched) + (1 if event.key() == Qt.Key_Down else -1)
            if 0 <= at < len(shown):
                shown[at].setFocus(Qt.FocusReason.OtherFocusReason)
                shown[at].click()
            return True
        return super().eventFilter(watched, event)

    def changeEvent(self, event) -> None:  # noqa: ANN001
        super().changeEvent(event)
        if event.type() in (QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
            # The icons in the theme's colours, as the window's style changes.
            for button in (*self.play_buttons, *self.delete_buttons):
                button.refresh()


class EffectsPage(QWidget):
    """What 场景管理 shows. scenes.key is the 场景 shown, store.quick_scene the hotkey's; hotkey_box is the
    window's box for the 场景 hotkey.

    One sound at a time plays from its ▶s: ▶ 播放's (the scene and its music) or a row's. While one plays its
    ▶ is ⏸ 暂停, which stops it where it is, the scene held still, and ▶ goes on with both from there (winsound
    cannot pause: the sound from that moment on is played). It ends by itself after its length; another ▶,
    another 场景 shown, 静音, closing the dialog or minimizing its window ends it too, every ▶ ▶ again."""

    # The preview's width, the sample lobby's shape kept: as wide as 嘉宾场景's.
    PREVIEW_W = 448

    def __init__(self, store, music, hotkey_box: QLineEdit, parent: QWidget | None = None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.store = store
        self.music = music
        # What ▶ started: _SCENE for ▶ 播放, a row's file ("" for 默认), None for nothing. It plays, or with
        # _paused_at it waits paused that many seconds in. _began: when it would have started, played on from
        # its start (time.monotonic()); _length: how long it plays; _music_s: how long 播放's music is.
        self._what: str | None = None
        self._paused_at: float | None = None
        self._began = 0.0
        self._length = 0.0
        self._music_s = 0.0
        self._sounding = False
        # ▶ 播放 pressed, its scene not started yet (its pictures being made): its music starts as it does.
        self._starting = False
        # Its end, timed from its length: winsound says nothing as a sound ends.
        self._end = QTimer(self)
        self._end.setSingleShot(True)
        self._end.timeout.connect(lambda: self._settle(stop=False))
        self.held = False
        # The 场景 a note about its 配乐 was said for: it goes as another is shown.
        self._told = ""
        self._held_text = ""
        body = QHBoxLayout(self)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(20)
        # On the left the hotkey, shared by every 场景, over the list whose spots say which one it plays.
        self.scenes = SceneList(store.quick_scene, marks=True)
        self.scenes.picked.connect(self._pick)
        self.scenes.ticked.connect(self.give_hotkey)
        self.scene_scroll = _ListScroll(self.scenes)
        self.left = _HotkeySide(hotkey_box, self.scene_scroll)
        self.hotkey_hint = self.left.hint
        self.note = self.left.note
        body.addWidget(self.left)
        side = QVBoxLayout()
        side.setSpacing(16)
        body.addLayout(side)
        self.preview = _Preview(self.PREVIEW_W)
        self.preview.started.connect(self._scene_started)
        side.addWidget(self.preview)
        # The shown 场景's 配乐 right under the preview: its 音量 and ▶ 播放, then its choices.
        below = QWidget()
        below.setFixedWidth(self.PREVIEW_W)
        rows = QGridLayout(below)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setHorizontalSpacing(16)
        rows.setVerticalSpacing(12)
        rows.setColumnStretch(1, 1)
        label = QLabel("配乐")
        label.setObjectName("rowLabel")
        rows.addWidget(label, 0, 0)
        # 音量: how loud this 场景 is, in its steps; let go, a moment of it at that.
        volume = QHBoxLayout()
        volume.setSpacing(10)
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100 // VOLUME_STEP)
        self.volume_slider.setPageStep(2)
        self.volume_slider.setFixedWidth(180)
        self.volume_slider.setCursor(Qt.PointingHandCursor)
        self.volume_slider.setAccessibleName("配乐音量")
        self.volume_slider.setToolTip("音量")
        self.volume_slider.valueChanged.connect(self._on_volume)
        self.volume_slider.sliderReleased.connect(self._volume_set)
        volume.addWidget(self.volume_slider)
        self.volume_label = QLabel("100%")
        self.volume_label.setObjectName("rowLabel")
        self.volume_label.setFixedWidth(QFontMetrics(chinese_font()).horizontalAdvance("100%") + 4)
        volume.addWidget(self.volume_label)
        # That nothing is heard, under 设置's 静音.
        self.level_note = QLabel("")
        self.level_note.setObjectName("rowHint")
        volume.addWidget(self.level_note)
        volume.addStretch(1)
        # ▶ 播放: the scene from its start in the preview, with its music; ⏸ 暂停 while it plays.
        self.play_button = _button("播放", self.play_preview, primary=True)
        self.play_button.setAccessibleName("播放场景和配乐")
        self.play_button.setIconSize(QSize(12, 12))
        self._paint_play()
        volume.addWidget(self.play_button)
        rows.addLayout(volume, 0, 1)
        # 默认 and the player's songs, one chosen, with 上传 at the right.
        self.sounds = SoundChoices(self.upload)
        self.sounds.chose.connect(self._choose)
        self.sounds.play.connect(self._listen)
        self.sounds.delete.connect(self._delete)
        self.upload_button = self.sounds.upload_button
        # On the left, under 配乐 itself.
        rows.addWidget(self.sounds, 1, 0, 1, 2)
        # What became of a 配乐 uploaded, under them. Its room is kept while it is hidden.
        self.sound_note = QLabel(" ")
        self.sound_note.setObjectName("rowHint")
        self.sound_note.setWordWrap(True)
        policy = self.sound_note.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        self.sound_note.setSizePolicy(policy)
        self.sound_note.hide()
        rows.addWidget(self.sound_note, 2, 0, 1, 2)
        # The room kept for songs another 场景 has (_sync_rows): here at the foot, not between the songs.
        self.spare = QWidget()
        self.spare.setFixedHeight(0)
        rows.addWidget(self.spare, 3, 0, 1, 2)
        self.below = below
        side.addWidget(below)
        side.addStretch(1)
        self._sync_marks()
        self._sync_rows()
        QGuiApplication.instance().applicationStateChanged.connect(self._app_state)

    def select(self, key: str) -> None:
        """Show this scene, still, ✓ and ♪ as the store has them (after 清空数据), without saving."""
        self._settle()
        self.scenes.select(key)
        self._sync_marks()
        self._sync_rows()
        if self.isVisible():
            self.preview.show_still(self.scenes.key)

    def _pick(self, key: str) -> None:
        """A click on a scene: it is shown, and plays quietly, the music ▶ started stopped. A play over the
        game keeps its music; the hotkey's 场景 stays as it was. One not made yet is made just after the click
        is seen."""
        self._settle()
        self.preview.show_scene(self.scenes.key)
        if self._told and self._told != self.scenes.key:
            self._tell("")
        self._sync_rows()

    def give_hotkey(self, key: str) -> None:
        """A click on a scene's spot: the hotkey plays that 场景 from now on; the one shown stays."""
        self.store.quick_scene = key
        self.store.save_settings()
        self._sync_marks()

    def play_preview(self) -> None:
        """▶ 播放: the scene from its start in the preview, with its music, which takes over from a play's
        over the game; while they play, 暂停, and ▶ again goes on with them from where they were."""
        if self._what == _SCENE:
            self._toggle()
            return
        self._settle()
        self._starting = True
        self.preview.show_scene(self.scenes.key, now=True)

    def _scene_started(self) -> None:
        """The preview's scene started: ▶ 播放's music with it, unless it is a click's, which plays quietly."""
        if not self._starting:
            return
        self._starting = False
        key = self.scenes.key
        started = self.music is not None and bool(self.music.preview(key))
        self._music_s = tune_seconds(self.music.tune_of(key)) if started else 0.0
        self._run(_SCENE, 0.0, max(love_scenes.load(self.preview.scene).DURATION, self._music_s), started)

    # What ▶ started: one sound at a time, played, paused and played on.
    @property
    def sounding(self) -> bool:
        """The music playing is the one a ▶ here started, which stops as the page goes out of sight. The window
        sets it False as the music becomes another's (a lobby's, the 场景 hotkey's): every ▶ is ▶ again."""
        return self._sounding

    @sounding.setter
    def sounding(self, on: bool) -> None:
        if on:
            self._sounding = True
        else:
            self._settle(stop=False)

    def _run(self, what: str, at: float, length: float, sounding: bool) -> None:  # noqa: FBT001
        """what plays from at seconds in, to its end after length."""
        self._what, self._paused_at, self._sounding = what, None, sounding
        self._began = time.monotonic() - at
        self._length = length
        self._end.start(max(0, round((length - at) * 1000)))
        self._show_playing()

    def _toggle(self) -> None:
        """⏸ on what plays: stopped where it is, 播放's scene held still there. ▶ on it paused: on from there."""
        if self._paused_at is None:
            at = min(time.monotonic() - self._began, self._length)
            if self._sounding and self.music is not None:
                self.music.stop()
            self._sounding = False
            self._end.stop()
            if self._what == _SCENE:
                self.preview.hold()
            self._paused_at = at
            self._show_playing()
            return
        what, at = self._what, self._paused_at
        if what == _SCENE:
            self.preview.go(run=self._seen())
            started = self.music is not None and at < self._music_s and bool(self.music.preview(self.scenes.key, at=at))
        else:
            started = self._song(what, at)
            if not started:
                self._settle()
                return
        self._run(what, at, self._length, started)

    def _settle(self, stop: bool = True) -> None:  # noqa: FBT001, FBT002
        """Nothing a ▶ here started plays or waits paused: 播放 and every row's ▶ are ▶ again, no wave moves,
        a scene held still goes on, and with stop the music a ▶ started is stopped."""
        if stop and self._sounding and self.music is not None:
            self.music.stop()
        held = self.preview.held
        self._what, self._paused_at, self._sounding, self._starting = None, None, False, False
        self._end.stop()
        if held:
            self.preview.go(run=self._seen())
        self._show_playing()

    def _show_playing(self) -> None:
        """播放 and each row's ▶ as what a ▶ started is now: ⏸ 暂停 on the one playing, ▶ on the rest."""
        muted = self.music is not None and self.music.muted
        playing = self._what == _SCENE and self._paused_at is None
        self.play_button.setText("暂停" if playing else "播放")
        self.play_button.setAccessibleName("暂停场景和配乐" if playing else "播放场景和配乐")
        if muted:
            tip = "已静音"
        elif playing:
            tip = "暂停"
        else:
            tip = "接着播放" if self._what == _SCENE else "从头播放，带配乐"
        self.play_button.setToolTip(tip)
        self._paint_play()
        self.sounds.set_playing(None if self._what in (None, _SCENE) else self._what, self._paused_at is not None)

    def say(self, text: str, held: bool = False) -> None:
        """A note under the hotkey. held: it is about the hotkey as it stands (another program has its key,
        检查 the one it would have), and goes once that is no longer so; one about a key just pressed stays."""
        self.held = held
        self._held_text = text if held else ""
        self.note.setText(text)
        self.note.setVisible(bool(text))

    def _tell(self, text: str, warn: bool = False) -> None:  # noqa: FBT001, FBT002
        """A note about the shown 场景's 配乐, underlined when it is a warning: it goes as another 场景 is shown."""
        self._told = self.scenes.key if text else ""
        # Hidden, a line's room is kept, so the dialog keeps its height as a note comes and goes.
        self.sound_note.setText(text or " ")
        self.sound_note.setProperty("tone", "warn" if warn else "")
        self.sound_note.style().unpolish(self.sound_note)
        self.sound_note.style().polish(self.sound_note)
        self.sound_note.setVisible(bool(text))

    def forget_said(self) -> None:
        """Opened again: a note about a key once pressed or a 配乐 once uploaded is old news and goes; one about
        the hotkey as it stands (held) stays."""
        self._tell("")
        self.say(self._held_text, held=self.held)

    # The shown 场景's sound.
    def _own(self, key: str) -> Path | None:
        """The song this 场景 plays, while it is there; None for 默认."""
        own = self.store.scene_sound(key)[0]
        return own if own is not None and own.is_file() else None

    def _sync_marks(self) -> None:
        owned = [key for key in self.scenes.buttons if self._own(key) is not None]
        self.scenes.set_marks(self.store.quick_scene, owned)

    def _sync_rows(self) -> None:
        """配乐 and its 音量 as they are for the 场景 shown. The page keeps room for as many songs as any 场景 has,
        at its foot, so the dialog keeps its size as one after another is shown while a note about a 配乐 stays
        right under the songs this one has."""
        key = self.scenes.key
        songs = self.store.scene_songs(key)
        own = self._own(key)
        room = max(len(self.store.scene_songs(scene)) for scene in self.scenes.buttons)
        spare = max(0, room - len(songs)) * self.sounds.song_row_height()
        # What shrinks goes first: the dialog grows with what it shows and does not shrink back by itself.
        if spare < self.spare.height():
            self.spare.setFixedHeight(spare)
        default = f"默认 · {tune_seconds(TUNES[key]):.1f} 秒" if key in TUNES else "默认（无声）"
        self.sounds.set_sounds(default, key in TUNES, songs, own.name if own else "", room)
        self.spare.setFixedHeight(spare)
        # The 音量 as it plays: 1 to 4% (an old 声音 folded in) stands at 0 but says what is heard.
        volume = self.store.scene_sound(key)[1]
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(volume // VOLUME_STEP)
        self.volume_slider.blockSignals(False)
        self.volume_slider.setEnabled(bool(songs) or key in TUNES)
        self.volume_label.setText(f"{volume}%")
        self.volume_label.setEnabled(self.volume_slider.isEnabled())
        self.sync_sound()

    def sync_sound(self) -> None:
        """The note beside 音量, ▶ 播放 and the ▶ of each sound as 设置's 静音 is now: that nothing is heard, and
        nothing a ▶ started plays on."""
        muted = self.music is not None and self.music.muted
        if muted and self._what is not None:
            self._settle()
        self.level_note.setText("已静音" if muted and self.volume_slider.isEnabled() else "")
        self.play_button.setEnabled(not muted)
        self.sounds.set_muted(muted)
        self._show_playing()

    def _paint_play(self) -> None:
        """▶ on 播放, ⏸ while it plays, in the colour of its words, as the theme has it."""
        playing = self._what == _SCENE and self._paused_at is None
        self.play_button.setIcon(_glyph("pause" if playing else "play", 12, THEME["on_accent"]))

    def _on_volume(self, step: int) -> None:
        """音量 moved: the shown 场景 plays this loud from now on. Dragged, it is saved and heard once let go
        (_volume_set); moved with the keys, the wheel or a click beside the handle, at once."""
        key = self.scenes.key
        self.store.set_scene_volume(key, step * VOLUME_STEP)
        self.volume_label.setText(f"{step * VOLUME_STEP}%")
        self.sync_sound()
        if not self.volume_slider.isSliderDown():
            self._volume_set()

    def _volume_set(self) -> None:
        """The 音量 chosen: saved, and a moment of the 场景's sound at it, unless 静音."""
        self.store.save_settings()
        if self.music is not None and not self.music.muted:
            self.sounding = False
            self.music.taste(self.scenes.key)

    def _choose(self, file: str) -> None:
        """A click on 默认 or a song: the 场景 plays it from now on. Nothing plays now: ▶ does."""
        self.store.choose_scene_song(self.scenes.key, file)
        self._sync_marks()
        self._sync_rows()

    def _listen(self, file: str) -> None:
        """▶ beside 默认 or a song: it whole, at the 场景's 音量, chosen or not, in place of whatever a ▶ here
        started; ⏸ while it plays, and ▶ again on from there. It stops as the page goes."""
        if self.music is None:
            return
        if self._what == file:
            self._toggle()
            return
        # The new sound takes the last one's place, or stops it if it has none to play.
        self._settle(stop=False)
        if self._song(file, 0.0):
            self._run(file, 0.0, tune_seconds(self._song_path(file)), True)

    def _song_path(self, file: str) -> Path | None:
        """Where a row's sound is: the player's song, or for 默认 ("") the scene's own (经典's none)."""
        return custom_sound_dir(self.store.root) / file if file else TUNES.get(self.scenes.key)

    def _song(self, file: str, at: float) -> bool:
        """A row's sound from at seconds on; False when nothing plays (静音, 0%, 经典's 默认)."""
        return self.music.song(self.scenes.key, self._song_path(file), at=at)

    def _delete(self, file: str) -> None:
        """✕ beside a song: it gone, its file and its copies too, and 默认 played if it was the one chosen."""
        own = custom_sound_dir(self.store.root) / file
        if self.music is not None:
            # Nothing playing holds it.
            self.music.stop()
            self.music.drop(own)
        self.sounding = False
        try:
            own.unlink(missing_ok=True)
        except OSError:
            pass  # Held by something else: the next song for this 场景 takes another name.
        self.store.remove_scene_song(self.scenes.key, file)
        self._sync_marks()
        self._sync_rows()

    def upload(self) -> None:
        """上传: a sound or video of the player's, one more song for the shown 场景 (up to MAX_SONGS), the one it
        plays from then on. One longer than a 场景's sound may be is cut to the part picked in 选择片段; either way
        it is kept as the app's own, and nothing plays."""
        key = self.scenes.key
        if len(self.store.scene_songs(key)) >= MAX_SONGS:
            return
        name = dict(love_scenes.SCENES).get(key, key)
        if sound_import.available():
            title, kinds = f"给「{name}」上传配乐", f"声音或视频 ({sound_import.FILTER})"
        else:
            title, kinds = f"给「{name}」上传配乐（这台电脑只能用 WAV）", f"WAV 声音 ({sound_import.WAV_FILTER})"
        path, _kind = QFileDialog.getOpenFileName(self, title, "", kinds)
        if not path:
            return
        source = Path(path)
        self._tell("正在读取…")
        self.sound_note.repaint()
        # The window paints on while a video is read, seconds maybe, but takes no clicks: the sound is the
        # shown 场景's, and nothing (another 场景, 上传 again, 清空数据) may change under it meanwhile.
        window = self.window()
        window.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            decoded = sound_import.decode(source)
        except SoundImportError as error:
            self._tell(str(error), warn=True)
            return
        finally:
            QApplication.restoreOverrideCursor()
            window.setEnabled(True)
        self._tell("")
        start, length = 0.0, CLIP_S
        if decoded.seconds > CLIP_S:
            picked = self._trim(decoded, key, source.name)
            if picked is None:
                return
            start, length = picked
        self._keep(decoded, key, source.name, start, length)

    def _trim(self, decoded, key: str, name: str) -> tuple[float, float] | None:  # noqa: ANN001
        """选择片段 on a long sound: the part picked, or None when it is closed. It plays the sound from a moment
        to its end at the 场景's level (a new file each time: winsound may still hold the last), and its 试听
        the part as the 场景 will (made as save_clip makes it, at the 场景's level), from a folder of the
        page's own that goes with the dialog. A part save_clip would refuse (a silent one) is told there, at
        试听 and at 确定."""
        folder = Path(tempfile.mkdtemp(prefix="blacklist_detect_trial_"))
        songs = itertools.count()

        def play(at: float) -> str:
            if self.music is None:
                return ""
            self.music.stop()
            self.sounding = False
            for old in folder.glob("song-*.wav"):
                try:
                    old.unlink()
                except OSError:
                    pass  # Still held: it goes with the folder.
            level = self.music.level(key)
            if level <= 0:
                return ""
            try:
                song = sound_import.save_rest(decoded, at, folder / f"song-{next(songs)}.wav", level)
            except SoundImportError as error:
                return str(error)
            self.music.play_file(song)
            return ""

        def check(start: float, length: float) -> str:
            try:
                sound_import.save_clip(decoded, "trial", folder, start, length)
            except SoundImportError as error:
                return str(error)
            return ""

        def preview(start: float, length: float) -> str:
            if self.music is None:
                return ""
            self.music.stop()
            self.sounding = False
            try:
                clip = sound_import.save_clip(decoded, "trial", folder, start, length)
            except SoundImportError as error:
                return str(error)
            self.music.trial(clip.path, key)
            return ""

        def stop() -> None:
            if self.music is not None:
                self.music.stop()

        # 静音, or the 场景's 音量 at 0%: nothing would be heard, so nothing plays.
        muted = self.music is None or self.music.muted or self.music.level(key) <= 0
        quiet = "已静音" if self.music is None or self.music.muted else "音量为 0%"
        dialog = SoundTrimDialog(
            decoded.samples, sound_import.RATE, name, preview, stop, self.window(), CLIP_S, muted=muted, check=check, play=play,
            muted_tip=quiet,
        )
        try:
            accepted = dialog.exec() == QDialog.Accepted
        finally:
            stop()
            shutil.rmtree(folder, ignore_errors=True)
        return dialog.selection() if accepted else None

    def _keep(self, decoded, key: str, name: str, start: float, length: float) -> None:  # noqa: ANN001
        """The part picked kept as one more of the 场景's songs, the one it plays, under a name no file has
        (song_name: winsound may still hold one deleted), its 音量 as it was. Nothing plays by itself: ▶, 试听 in
        选择片段, or 音量's slider, plays it when the player asks."""
        folder = custom_sound_dir(self.store.root)
        if self.music is not None:
            self.music.stop()
        self.sounding = False
        try:
            kept = sound_import.save_clip(decoded, sound_import.song_name(key, folder), folder, start, length)
        except SoundImportError as error:
            self._tell(str(error), warn=True)
            return
        self.store.add_scene_song(
            key, {"file": kept.path.name, "name": name, "start": round(kept.start_s, 3), "length": round(kept.length_s, 3)}
        )
        self._sync_marks()
        self._sync_rows()

    def _seen(self) -> bool:
        """On screen: 场景管理 open, over a window that is not minimized."""
        window = self.window()
        host = window.parentWidget()
        return self.isVisible() and not window.isMinimized() and not (host is not None and host.window().isMinimized())

    def _show(self) -> None:
        """Back in sight: a scene playing plays again from its start, or, while ▶ 播放's plays on, where it is
        with its music; one paused stays where it was, and a still stays still."""
        if not self.preview.held:
            self.preview.resume(from_start=self._what != _SCENE)

    def _app_state(self, state) -> None:  # noqa: ANN001
        """With the game in front, the preview rests; it plays again as the app comes back."""
        if state != Qt.ApplicationState.ApplicationActive:
            self.preview.pause()
        elif self._seen():
            self._show()

    def showEvent(self, event) -> None:  # noqa: ANN001
        """Opened: the shown scene still, at its best moment, nothing made (a scene takes up to a second to make);
        a click on one in the list, or ▶, plays it. Its window back from minimized, it goes on as it was."""
        super().showEvent(event)
        if not event.spontaneous():
            self.preview.show_still(self.scenes.key)
        elif self._seen():
            self._show()

    def changeEvent(self, event) -> None:  # noqa: ANN001
        super().changeEvent(event)
        if event.type() in (QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
            self._paint_play()

    def hideEvent(self, event) -> None:  # noqa: ANN001
        self._settle()
        self.preview.rest()
        super().hideEvent(event)


class EffectsDialog(Modal):
    """场景管理: the page in a dialog of its own, made once with the window and opened again and again from
    the 嘉宾 page, the page and what it shows kept between. It has no buttons at its foot: × and Esc close it,
    which rests the preview and stops a sound ▶ started (the page's hideEvent). It opens with the scene
    list in focus, never the hotkey box, which would take the next key pressed for the 场景 hotkey."""

    def __init__(self, page: EffectsPage, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.page = page
        self.frame("场景管理").addWidget(page)
        # Its window minimized with it open, the preview rests; restored, it plays again.
        if parent is not None:
            parent.window().installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:  # noqa: ANN001
        if event.type() == QEvent.Type.WindowStateChange and watched is self.parentWidget().window():
            if watched.isMinimized():
                # Nothing a ▶ started plays on behind it.
                self.page._settle()
                self.page.preview.pause()
            elif self.page._seen():
                self.page._show()
        return super().eventFilter(watched, event)

    def restyle(self) -> None:
        """In the theme as it is now: 浅色 or 深色 may have changed since it was made, or while it is open (跟随系统).
        The same one is not set again, which would style every widget in it anew."""
        style = _dialog_style(chinese_family())
        if style != self.styleSheet():
            self.setStyleSheet(style)
            self.page._paint_play()

    def setVisible(self, visible: bool) -> None:  # noqa: FBT001
        if visible and not self.isVisible():
            self.restyle()
            self.page.forget_said()
            # Room for every scene in the theme's fonts, before the card is measured to fit the screen.
            self.page.left.keep_room()
            self.page.scenes.buttons[self.page.scenes.key].setFocus(Qt.FocusReason.OtherFocusReason)
        super().setVisible(visible)
