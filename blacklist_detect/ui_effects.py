"""特效管理: every 特效's sound, and which one the 特效 hotkey plays.

Every scene in love_scenes.SCENES is listed by name with its dot, as in 选择特效 (ui_love_pick.SceneList).
A click shows one: it plays beside the list over the fake-name sample lobby, as big as the page allows, and
▶ plays it from its start with its music. The list's ✓ is the 特效 the hotkey plays, which 快捷键放这个 makes
the one shown; a ♪ is a 特效 with the player's own sound.

Under the preview, the shown 特效's 声音 (its own, or the player's: 上传 a file, a part of it picked in
选择片段 when it is longer than a 特效's sound may be, and 恢复默认 to go back), its 音量 on top of 设置's
声音, and the hotkey, set the way 检查's is (the window's hotkey box), with 播放, which plays the shown 特效
the way the hotkey plays its own: at once over the game, with no check (MainWindow.play_quick_scene).

The preview plays only while it can be seen, its window not minimized, and the app is in front: behind the
game it would paint 30 times a second for nothing.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QFontMetrics, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from blacklist_detect import love_scenes, sound_import
from blacklist_detect.love_scenes import DESIGN
from blacklist_detect.paths import custom_sound_dir
from blacklist_detect.sound_import import CLIP_S, SoundImportError
from blacklist_detect.ui_love_pick import SceneList, ScenePreview
from blacklist_detect.ui_music import TUNES, VOLUME_STEP
from blacklist_detect.ui_sound_trim import SoundTrimDialog
from blacklist_detect.ui_theme import GAP, _page, chinese_font


class _Fitted(QWidget):
    """The preview as big as it fits, the lobby's shape kept, at the top left, and what goes under it
    (below) right under it. The preview keeps the most room below has needed, so it does not jump
    as a note under the hotkey comes and goes."""

    MIN_W = 320

    def __init__(self, preview: ScenePreview, below: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.preview = preview
        self.below = below
        preview.setParent(self)
        below.setParent(self)
        # Its box and 播放 grow once they are styled, after the first place: placed again then.
        below.installEventFilter(self)
        self._under = 0
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(QSize(self.MIN_W, self._tall(self.MIN_W)))

    def _tall(self, width: int) -> int:
        return round(width * DESIGN[1] / DESIGN[0]) + GAP + self.below.sizeHint().height()

    def sizeHint(self) -> QSize:
        return QSize(ScenePreview.WIDTH, self._tall(ScenePreview.WIDTH))

    def place(self) -> None:
        under = self.below.sizeHint().height()
        self._under = max(self._under, under)
        room = max(1, self.height() - self._under - GAP)
        self.preview.set_width(max(1, min(self.width(), int(room * DESIGN[0] / DESIGN[1]))))
        self.preview.move(0, 0)
        self.below.setGeometry(0, self.preview.height() + GAP, self.width(), under)

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self.place()

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        self.place()

    def eventFilter(self, watched, event) -> bool:  # noqa: ANN001
        if watched is self.below and event.type() == QEvent.Type.LayoutRequest:
            self.place()
        return super().eventFilter(watched, event)


class _Elided(QLabel):
    """One line cut in the middle when its room is too narrow for it, whole in its tooltip then."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.full = ""
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    def set_full(self, text: str) -> None:
        self.full = text
        self.updateGeometry()
        self._fit()

    def sizeHint(self) -> QSize:
        return QSize(self.fontMetrics().horizontalAdvance(self.full) + 2, super().sizeHint().height())

    def minimumSizeHint(self) -> QSize:
        return QSize(self.fontMetrics().horizontalAdvance("…") * 4, super().minimumSizeHint().height())

    def _fit(self) -> None:
        shown = self.fontMetrics().elidedText(self.full, Qt.ElideMiddle, max(1, self.width()))
        self.setText(shown)
        self.setToolTip(self.full if shown != self.full else "")

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._fit()


def _button(text: str, action, primary: bool = False) -> QPushButton:  # noqa: ANN001
    button = QPushButton(text)
    if primary:
        button.setObjectName("primary")
    button.setAutoDefault(False)
    button.setCursor(Qt.PointingHandCursor)
    button.clicked.connect(lambda: action())
    return button


class EffectsPage(QWidget):
    """The 特效 page. scenes.key is the 特效 shown, store.quick_scene the hotkey's; hotkey_box is the
    window's box for the 特效 hotkey, and play(key) what 播放 does with the one shown. sounding: the music
    playing is the one ▶ started, which stops as the page goes out of sight."""

    def __init__(self, store, music, hotkey_box: QLineEdit, play, parent: QWidget | None = None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.store = store
        self.music = music
        self.sounding = False
        self.held = False
        # The 特效 a note about its sound was said for: it goes as another is shown, and a note about the
        # hotkey as it stands (held) comes back.
        self._told = ""
        self._held_text = ""
        outer = QVBoxLayout(self)
        _page(outer)
        body = QHBoxLayout()
        body.setSpacing(20)
        outer.addLayout(body, 1)
        self.scenes = SceneList(store.quick_scene, marks=True)
        self.scenes.picked.connect(self._pick)
        body.addWidget(self.scenes, 0, Qt.AlignTop)
        self.preview = ScenePreview(play=self.play_preview)
        # The shown 特效's 声音 and 音量, then the hotkey and 播放, right under the preview.
        below = QWidget()
        rows = QGridLayout(below)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setHorizontalSpacing(12)
        rows.setVerticalSpacing(6)
        rows.setColumnStretch(1, 1)
        for row, name in enumerate(("声音", "音量", "快捷键")):
            label = QLabel(name)
            label.setObjectName("rowLabel")
            rows.addWidget(label, row, 0)
        # 声音: what it plays, its own or the player's, with 上传 (替换) and 恢复默认.
        sound = QHBoxLayout()
        sound.setSpacing(10)
        self.sound_text = _Elided()
        self.sound_text.setObjectName("rowLabel")
        sound.addWidget(self.sound_text)
        self.upload_button = _button("上传", self.upload)
        self.upload_button.setAccessibleName("上传声音")
        sound.addWidget(self.upload_button)
        self.reset_button = _button("恢复默认", self.restore)
        self.reset_button.setAccessibleName("恢复默认声音")
        sound.addWidget(self.reset_button)
        sound.addStretch(1)
        rows.addLayout(sound, 0, 1)
        # 音量: how loud this 特效 is of 设置's 声音, in its steps; let go, a moment of it at that.
        volume = QHBoxLayout()
        volume.setSpacing(10)
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100 // VOLUME_STEP)
        self.volume_slider.setPageStep(2)
        self.volume_slider.setFixedWidth(180)
        self.volume_slider.setCursor(Qt.PointingHandCursor)
        self.volume_slider.setAccessibleName("特效音量")
        self.volume_slider.valueChanged.connect(self._on_volume)
        self.volume_slider.sliderReleased.connect(self._volume_set)
        volume.addWidget(self.volume_slider)
        self.volume_label = QLabel("100%")
        self.volume_label.setObjectName("rowLabel")
        self.volume_label.setFixedWidth(QFontMetrics(chinese_font()).horizontalAdvance("100%") + 4)
        volume.addWidget(self.volume_label)
        # How loud it is heard, 设置's 声音 taken in, or that nothing is.
        self.level_note = QLabel("")
        self.level_note.setObjectName("rowHint")
        volume.addWidget(self.level_note)
        volume.addStretch(1)
        rows.addLayout(volume, 1, 1)
        hotkey = QHBoxLayout()
        hotkey.setSpacing(10)
        hotkey.addWidget(hotkey_box)
        self.assign_button = _button("快捷键放这个", self.assign)
        self.assign_button.setToolTip("按快捷键时放这个特效")
        hotkey.addWidget(self.assign_button)
        self.play_button = _button("播放", lambda: play(self.scenes.key), primary=True)
        hotkey.addWidget(self.play_button)
        hotkey.addStretch(1)
        rows.addLayout(hotkey, 2, 1)
        # What is wrong with a key pressed for the hotkey, as 检查 says it, why 播放 played nothing, or what
        # became of a sound uploaded, under them. Its room is kept while it is hidden.
        self.note = QLabel("")
        self.note.setObjectName("rowHint")
        self.note.setWordWrap(True)
        policy = self.note.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        self.note.setSizePolicy(policy)
        self.note.hide()
        rows.addWidget(self.note, 3, 1)
        self.stage = _Fitted(self.preview, below)
        body.addWidget(self.stage, 1)
        self._sync_marks()
        self._sync_rows()
        QGuiApplication.instance().applicationStateChanged.connect(self._app_state)

    def select(self, key: str) -> None:
        """Show this scene, ✓ and ♪ as the store has them (after 清空数据), without saving."""
        self.scenes.select(key)
        self._sync_marks()
        self._sync_rows()
        if self.isVisible():
            self.preview.show_scene(self.scenes.key)

    def _pick(self, key: str) -> None:
        """A click on a scene: it is shown, and plays quietly, the music ▶ started stopped. A play over the
        game keeps its music; the hotkey's 特效 stays as it was."""
        self.preview.show_scene(self.scenes.key)
        if self.sounding and self.music is not None:
            self.music.stop()
        self.sounding = False
        if self._told and self._told != self.scenes.key:
            self._tell("")
        self._sync_rows()

    def assign(self) -> None:
        """快捷键放这个: the hotkey plays the shown 特效 from now on."""
        self.store.quick_scene = self.scenes.key
        self.store.save_settings()
        self._sync_marks()
        self._sync_rows()

    def play_preview(self) -> None:
        """▶: the scene from its start in the preview, with its music, which takes over from a play's
        over the game."""
        self.preview.show_scene(self.scenes.key)
        if self.music is not None:
            self.music.preview(self.scenes.key)
            self.sounding = True

    def say(self, text: str, held: bool = False) -> None:
        """held: the note is about the hotkey as it stands (another program has its key, 检查 the one it
        would have), and goes once that is no longer so; one about a key just pressed, or 播放's, stays."""
        self.held = held
        self._told = ""
        self._held_text = text if held else ""
        self._note(text)

    def _tell(self, text: str) -> None:
        """A note about the shown 特效's sound, over one about the hotkey as it stands: it goes as another
        特效 is shown, and that one comes back."""
        self._told = self.scenes.key if text else ""
        self._note(text or self._held_text)

    def _note(self, text: str) -> None:
        self.note.setText(text)
        self.note.setVisible(bool(text))
        self.stage.below.layout().activate()
        self.stage.place()

    # The shown 特效's sound.
    def _entry(self, key: str) -> dict:
        return dict(self.store.scene_sounds.get(key) or {})

    def _own(self, key: str) -> Path | None:
        """The player's own sound for this 特效, while it is there."""
        own = self.store.scene_sound(key)[0]
        return own if own is not None and own.is_file() else None

    def _set_entry(self, key: str, entry: dict) -> None:
        """A 特效's entry, or none when it is all default (100%, its own sound): as the store saves them."""
        if entry.get("file") or entry.get("volume", 100) != 100:
            self.store.scene_sounds[key] = entry
        else:
            self.store.scene_sounds.pop(key, None)

    def _sync_marks(self) -> None:
        owned = [key for key in self.scenes.buttons if self._own(key) is not None]
        self.scenes.set_marks(self.store.quick_scene, owned)

    def _sync_rows(self) -> None:
        """声音, 音量 and 快捷键放这个 as they are for the 特效 shown."""
        key = self.scenes.key
        entry = self._entry(key)
        own = self._own(key) is not None
        if own:
            self.sound_text.set_full(f"自定义 · {entry.get('name') or Path(entry['file']).stem} · {entry.get('length', CLIP_S):.1f} 秒")
        else:
            self.sound_text.set_full("默认" if key in TUNES else "默认 · 无")
        self.upload_button.setText("替换" if own else "上传")
        self.reset_button.setVisible(own)
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(self.store.scene_sound(key)[1] // VOLUME_STEP)
        self.volume_slider.blockSignals(False)
        self.volume_slider.setEnabled(own or key in TUNES)
        self.volume_label.setText(f"{self.volume_slider.value() * VOLUME_STEP}%")
        self.volume_label.setEnabled(self.volume_slider.isEnabled())
        self.assign_button.setEnabled(key != self.store.quick_scene)
        self.sync_sound()

    def sync_sound(self) -> None:
        """The note beside 音量 as 设置's 声音 and 静音 are now: how loud it is heard, or that nothing is."""
        text = ""
        if self.music is not None and self.volume_slider.isEnabled():
            if self.music.muted:
                text = "已静音"
            elif self.music.volume < 100:
                text = f"实际 {self.music.level(self.scenes.key)}%"
        self.level_note.setText(text)

    def _on_volume(self, step: int) -> None:
        """音量 moved: the shown 特效 plays this loud from now on. Dragged, it is saved and heard once let go
        (_volume_set); moved with the keys, the wheel or a click beside the handle, at once."""
        key = self.scenes.key
        entry = self._entry(key)
        entry["volume"] = step * VOLUME_STEP
        self._set_entry(key, entry)
        self.volume_label.setText(f"{entry['volume']}%")
        self.sync_sound()
        if not self.volume_slider.isSliderDown():
            self._volume_set()

    def _volume_set(self) -> None:
        """The 音量 chosen: saved, and a moment of the 特效's sound at it, unless 静音."""
        self.store.save_settings()
        if self.music is not None and not self.music.muted:
            self.sounding = False
            self.music.taste(self.scenes.key)

    def upload(self) -> None:
        """上传 (替换): a sound or video of the player's for the shown 特效. One longer than a 特效's sound
        may be is cut to the part picked in 选择片段; either way it is kept as the app's own, played once."""
        key = self.scenes.key
        name = dict(love_scenes.SCENES).get(key, key)
        if sound_import.available():
            title, kinds = f"给「{name}」上传声音", f"声音或视频 ({sound_import.FILTER})"
        else:
            title, kinds = f"给「{name}」上传声音（这台电脑只能用 WAV）", f"WAV 声音 ({sound_import.WAV_FILTER})"
        path, _kind = QFileDialog.getOpenFileName(self, title, "", kinds)
        if not path:
            return
        source = Path(path)
        self._tell("正在读取…")
        self.note.repaint()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            decoded = sound_import.decode(source)
        except SoundImportError as error:
            self._tell(str(error))
            return
        finally:
            QApplication.restoreOverrideCursor()
        self._tell("")
        start, length = 0.0, CLIP_S
        if decoded.seconds > CLIP_S:
            picked = self._trim(decoded, key, source.name)
            if picked is None:
                return
            start, length = picked
        self._keep(decoded, key, source.name, start, length)

    def _trim(self, decoded, key: str, name: str) -> tuple[float, float] | None:  # noqa: ANN001
        """选择片段 on a long sound: the part picked, or None when it is closed. Its 试听 plays the part as the
        特效 will (made as save_clip makes it, at the 特效's level), from a folder of the page's own that goes
        with the dialog."""
        folder = Path(tempfile.mkdtemp(prefix="blacklist_detect_trial_"))

        def preview(start: float, length: float) -> None:
            if self.music is None:
                return
            self.music.stop()
            self.sounding = False
            try:
                clip = sound_import.save_clip(decoded, "trial", folder, start, length)
            except SoundImportError:
                return
            self.music.trial(clip.path, key)

        def stop() -> None:
            if self.music is not None:
                self.music.stop()

        muted = self.music is None or self.music.muted
        dialog = SoundTrimDialog(decoded.samples, sound_import.RATE, name, preview, stop, self.window(), CLIP_S, muted=muted)
        try:
            accepted = dialog.exec() == QDialog.Accepted
        finally:
            stop()
            shutil.rmtree(folder, ignore_errors=True)
        return dialog.selection() if accepted else None

    def _keep(self, decoded, key: str, name: str, start: float, length: float) -> None:  # noqa: ANN001
        """The part picked kept as the 特效's sound, its 音量 as it was, and played once unless 静音."""
        folder = custom_sound_dir(self.store.root)
        if self.music is not None:
            # Nothing playing holds the sound it replaces, and its quieter copies go with it.
            self.music.stop()
            self.music.drop(folder / f"{key}.wav")
        self.sounding = False
        try:
            kept = sound_import.save_clip(decoded, key, folder, start, length)
        except SoundImportError as error:
            self._tell(str(error))
            return
        entry = self._entry(key)
        self._set_entry(key, {
            "volume": entry.get("volume", 100), "file": kept.path.name, "name": name,
            "start": round(kept.start_s, 3), "length": round(kept.length_s, 3),
        })  # fmt: skip
        self.store.save_settings()
        self._sync_marks()
        self._sync_rows()
        if self.music is not None and not self.music.muted:
            self.music.taste(key)

    def restore(self) -> None:
        """恢复默认: the 特效's own sound again (经典's none), the player's file and its copies gone, its 音量 kept."""
        key = self.scenes.key
        entry = self._entry(key)
        if not entry.get("file"):
            return
        own = custom_sound_dir(self.store.root) / entry["file"]
        if self.music is not None:
            self.music.stop()
            self.music.drop(own)
        self.sounding = False
        try:
            own.unlink(missing_ok=True)
        except OSError:
            pass  # Held by something else: the next upload for this 特效 takes its place.
        self._set_entry(key, {"volume": entry.get("volume", 100)})
        self.store.save_settings()
        self._sync_marks()
        self._sync_rows()

    def _seen(self) -> bool:
        """On screen: this page the one shown, in a window that is not minimized."""
        return self.isVisible() and not self.window().isMinimized()

    def _show(self) -> None:
        """The shown scene from its start; made again only when it changed (演说家遇袭 takes over a second).
        While ▶'s music plays on, it goes on where the music is instead."""
        if self.preview.scene == self.scenes.key:
            self.preview.resume(from_start=not self.sounding)
        else:
            self.preview.show_scene(self.scenes.key)

    def _app_state(self, state) -> None:  # noqa: ANN001
        """With the game in front, the preview rests; it plays again as the app comes back."""
        if state != Qt.ApplicationState.ApplicationActive:
            self.preview.pause()
        elif self._seen():
            self._show()

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        if self._seen():
            self._show()

    def hideEvent(self, event) -> None:  # noqa: ANN001
        self.preview.pause()
        if self.sounding and self.music is not None:
            self.music.stop()
        self.sounding = False
        super().hideEvent(event)
