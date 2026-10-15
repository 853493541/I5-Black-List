"""嘉宾音乐: each 嘉宾场景 theme's own few seconds of sound, played as it greets 嘉宾 players in a lobby.

Every scene in love_scenes.SCENES but 经典, which greets in silence, has one (TUNES), made for it, its
accents on the scene's moments. build/theme_tunes.py plays 冰蓝极光's, 星河许愿's, 赛博朋克's two and
毛茸茸保护协会's; build/wedding_tunes.py the wedding tunes 玫瑰花边 (the Bridal Chorus on organ), 金色传说
(church bells) and 数学公式 (Pachelbel's Canon on harp) keep. No recording is used for those, so a stream can carry them. 演说家遇袭's is the 指挥家's music from
模仿者狂欢 with the 演说家遇袭 notice's sound in it at its strike (build/ambush_tune.py): the game's own
recording, the user's choice made knowing NetEase owns it.

The sound follows the theme. 场景管理 gives each 场景 its own 音量, and may give it the player's own sound
instead (经典 too), converted once as it was added into a tune like these (paths.custom_sound_dir);
设置 › 常规 › 声音 › 静音 silences every sound. winsound plays at the system volume only, from a file, so a
quieter one is a copy of the tune with its samples scaled (scaled_tune), kept in a folder of the app's own
(paths.app_dir).
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import time
import wave
from collections.abc import Callable
from pathlib import Path

import numpy as np

from blacklist_detect.paths import app_dir

ASSETS = Path(__file__).resolve().parent / "assets"
# Each scene's sound, by the scene's key. 经典 has none: it greets in silence.
TUNES: dict[str, Path] = {
    "lace": ASSETS / "wedding-organ.wav",
    "ice": ASSETS / "theme-ice.wav",
    "stars": ASSETS / "theme-stars.wav",
    "cyber": ASSETS / "theme-cyber.wav",
    "neon": ASSETS / "theme-neon.wav",
    "angel": ASSETS / "wedding-bells.wav",
    "equation": ASSETS / "wedding-canon.wav",
    "fluffy": ASSETS / "theme-fluffy.wav",
    "claw": ASSETS / "ambush.wav",
}
# A 场景's 音量 in 场景管理: how loud, in steps of this many percent, 100 (each tune as made) by default.
VOLUME_STEP = 5
# What 音量's slider plays as it is let go: a moment of the 场景's sound, this long, fading out.
SAMPLE_S = 1.5
SAMPLE_FADE_S = 0.25
# The same 嘉宾 players found again this soon are the same lobby, checked again: no second tune.
SAME_LOBBY_S = 60.0
# A quieter copy's name: volume, the tune's name, its file's size and time, and for a moment its length.
_COPY = re.compile(r"(\d+)-(.+)-(\d+)-(\d+)(-\d+ms)?\.wav")


def sound_dir() -> Path:
    """The folder the quieter copies are kept in, away from the lists."""
    return app_dir() / "sounds"


def scaled_tune(path: Path, volume: int, folder: Path, seconds: float | None = None) -> Path | None:
    """The tune at volume percent of its loudness, and with seconds only its start, fading out: a copy
    with its samples scaled, made once in folder and named for the file and the volume. The whole tune at
    100% is the file itself. None when no copy can be made: better nothing than a tune too loud. As one is
    made, the same tune's copies of that length at another volume, its copies of an older file (an update
    rewrites every tune, a player's own sound is replaced) and copies left half written are dropped, so the
    folder holds each tune as it is now, at its own volume."""
    if volume >= 100 and seconds is None:
        return path
    try:
        stat = path.stat()
        length = f"-{round(seconds * 1000)}ms" if seconds is not None else ""
        current = f"{stat.st_size}-{stat.st_mtime_ns}"
        made = folder / f"{volume}-{path.stem}-{current}{length}.wav"
        if made.is_file():
            return made
        with wave.open(str(path)) as source:
            params = source.getparams()
            if params.sampwidth != 2:
                return None
            frames = params.nframes if seconds is None else min(params.nframes, round(seconds * params.framerate))
            samples = np.frombuffer(source.readframes(frames), dtype="<i2").astype(np.float64)
        samples *= volume / 100
        if seconds is not None:
            fade = min(len(samples) // params.nchannels, round(SAMPLE_FADE_S * params.framerate))
            samples[len(samples) - fade * params.nchannels :] *= np.repeat(np.linspace(1.0, 0.0, fade), params.nchannels)
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.iterdir():
            # A .part (or anything else no copy's name) goes; another tune's copy stays.
            copy = _COPY.fullmatch(old.name)
            if copy is None:
                stale = True
            elif copy[2] != path.stem:
                stale = False
            else:
                stale = f"{copy[3]}-{copy[4]}" != current or (copy[5] or "") == length
            if stale:
                try:
                    old.unlink()
                except OSError:
                    pass  # Playing still: it goes with the next one made.
        part = made.with_suffix(".part")
        try:
            with wave.open(str(part), "wb") as copy:
                copy.setparams(params)
                copy.writeframes(np.clip(np.rint(samples), -32768, 32767).astype("<i2").tobytes())
            part.replace(made)
        except (OSError, wave.Error):
            part.unlink(missing_ok=True)
            raise
        return made
    except (OSError, EOFError, wave.Error):
        return None


# Only the app as the player runs it makes a sound: run_app turns it on (allow_sound). Tests, tools/ui_shots.py,
# the release check and any script that builds the window stay silent, unless BLACKLIST_DETECT_SOUND=1 asks for
# real sound to hear one.
AUDIBLE = os.environ.get("BLACKLIST_DETECT_SOUND") == "1"


def allow_sound() -> None:
    """The app is running for the player: its tunes play from now on."""
    global AUDIBLE
    AUDIBLE = True


def play_tune(path: Path | None) -> None:
    """Start a tune at the system volume without waiting for it, or with None stop whatever plays. Silent
    unless the app runs for the player (AUDIBLE)."""
    if sys.platform != "win32" or not AUDIBLE:
        return
    try:
        import winsound

        if path is None:
            winsound.PlaySound(None, 0)
        elif path.is_file():
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass


class ThemeMusic:
    """Plays a theme's sound, once per lobby, at the 场景's own 音量 (level), or nothing while muted. folder:
    where the quieter copies go (sound_dir when None). sounds: each 场景's own sound by its key, the player's
    file (None for the scene's own) and 音量 in percent (Store.scene_sound); with none, every scene plays its
    own as made."""

    def __init__(
        self,
        play: Callable[[Path | None], None] = play_tune,
        clock: Callable[[], float] = time.monotonic,
        folder: Path | None = None,
        sounds: Callable[[str], tuple[Path | None, int]] | None = None,
    ) -> None:
        self._play = play
        self._clock = clock
        self._folder = folder
        self._sounds = sounds
        self._last_lobby: frozenset[str] = frozenset()
        self._last_at = float("-inf")
        self.muted = False

    def pick(self, scene: str) -> str:
        """The tune for a scene: the player's own or the scene's, or "" for none (经典, with none of the
        player's)."""
        return scene if self._tune(scene) is not None else ""

    def level(self, scene: str) -> int:
        """How loud a scene's sound plays, in percent of its loudness: the 场景's own 音量."""
        return self._own(scene)[1]

    def _own(self, scene: str) -> tuple[Path | None, int]:
        if self._sounds is None or not scene:
            return None, 100
        return self._sounds(scene)

    def _tune(self, scene: str) -> Path | None:
        """The file a scene's sound is in: the player's own while it is there, else the scene's."""
        own = self._own(scene)[0]
        return own if own is not None and own.is_file() else TUNES.get(scene)

    def audible(self) -> bool:
        return not self.muted

    def lobby(self, likes: list[str], scene: str) -> str:
        """A lobby with these 嘉宾 players, greeted by this scene: play its sound, unless one just
        greeted them. A scene with no sound (经典, or at 0%) greets them too: checked again, the lobby
        gets no other scene's."""
        if not likes or not self.audible():
            return ""
        players = frozenset(likes)
        now = self._clock()
        if players == self._last_lobby and now - self._last_at < SAME_LOBBY_S:
            return ""
        self._last_lobby, self._last_at = players, now
        if not self.pick(scene) or self.level(scene) <= 0:
            return ""
        return self.preview(scene)

    def preview(self, scene: str) -> str:
        """Play a scene's sound now; with none, or muted, stop whatever is playing."""
        tune = self.pick(scene)
        return tune if self._start(self._tune(tune), self.level(tune)) else ""

    def taste(self, scene: str) -> bool:
        """A moment of a 场景's sound as loud as it plays, for its 音量 in 场景管理."""
        return self._start(self._tune(scene), self.level(scene), SAMPLE_S)

    def trial(self, path: Path, scene: str) -> bool:
        """A sound not yet a 场景's (选择片段's 试听), as loud as that 场景 plays: its quieter copy is made
        in a folder beside it, the caller's own, not with the tunes' (making one drops whatever else is
        in its folder)."""
        level = self.level(scene)
        tune = scaled_tune(path, level, path.parent / "copies") if not self.muted and level > 0 else None
        self._play(tune)
        return tune is not None

    def play_file(self, path: Path) -> bool:
        """A file as it is, made as loud as it should be by the caller (选择片段's song from a moment on),
        unless muted."""
        tune = None if self.muted else path
        self._play(tune)
        return tune is not None

    def _start(self, tune: Path | None, volume: int, seconds: float | None = None) -> bool:
        if tune is not None and not self.muted and volume > 0:
            tune = scaled_tune(tune, volume, self._folder or sound_dir(), seconds)
        else:
            tune = None
        self._play(tune)
        return tune is not None

    def stop(self) -> None:
        self._play(None)

    def drop(self, tune: Path) -> None:
        """Drop the quieter copies made of this tune, those of every other kept (forget drops them all): a
        player's own sound replaced or put back to the 场景's own leaves none of it behind. One still playing
        goes with the next copy made."""
        try:
            copies = list((self._folder or sound_dir()).iterdir())
        except OSError:
            return
        for old in copies:
            copy = _COPY.fullmatch(old.name)
            if copy is not None and copy[2] == tune.stem:
                try:
                    old.unlink()
                except OSError:
                    pass

    def forget(self) -> None:
        """Stop, and drop every quieter copy made: 清空数据 leaves none of the player's own sounds behind.
        The scenes' own are made again as they are next played."""
        self.stop()
        shutil.rmtree(self._folder or sound_dir(), ignore_errors=True)
