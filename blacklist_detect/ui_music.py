"""嘉宾音乐: each 嘉宾特效 theme's own few seconds of sound, played as it greets 嘉宾 players in a lobby.

Every scene in love_scenes.SCENES but 经典, which greets in silence, has one (TUNES), made for it, its
accents on the scene's moments. build/theme_tunes.py plays 冰蓝极光's, 星河许愿's, 赛博朋克's two and
毛茸茸保护协会's; build/wedding_tunes.py the wedding tunes 玫瑰花边 (the Bridal Chorus on organ), 金色传说
(church bells) and 数学公式 (Pachelbel's Canon on harp) keep. No recording is used for those, so a stream can carry them. 演说家遇袭's is the 指挥家's music from
模仿者狂欢 with the 演说家遇袭 notice's sound in it at its strike (build/ambush_tune.py): the game's own
recording, the user's choice made knowing NetEase owns it.

The sound follows the theme. 设置 › 常规 › 声音 sets how loud every sound is, or 静音 none: winsound plays at
the system volume only, from a file, so a quieter one is a copy of the tune with its samples scaled
(scaled_tune), kept in a folder of the app's own (paths.app_dir).
"""

from __future__ import annotations

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
# 声音 in 设置 › 常规: how loud, in steps of this many percent, 100 (each tune as made) by default.
VOLUME_STEP = 5
# What 声音's slider plays as it is let go: 玫瑰花边's organ (经典 has no sound), this long, fading out.
SAMPLE_TUNE = "lace"
SAMPLE_S = 1.5
SAMPLE_FADE_S = 0.25
# The same 嘉宾 players found again this soon are the same lobby, checked again: no second tune.
SAME_LOBBY_S = 60.0


def sound_dir() -> Path:
    """The folder the quieter copies are kept in, away from the lists."""
    return app_dir() / "sounds"


def scaled_tune(path: Path, volume: int, folder: Path, seconds: float | None = None) -> Path | None:
    """The tune at volume percent of its loudness, and with seconds only its start, fading out: a copy
    with its samples scaled, made once in folder and named for the file and the volume. The whole tune at
    100% is the file itself. None when no copy can be made: better nothing than a tune too loud. Copies at
    another volume are dropped as one is made, so the folder holds one volume's."""
    if volume >= 100 and seconds is None:
        return path
    try:
        stat = path.stat()
        length = f"-{round(seconds * 1000)}ms" if seconds is not None else ""
        made = folder / f"{volume}-{path.stem}-{stat.st_size}-{stat.st_mtime_ns}{length}.wav"
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
        for old in folder.glob("*.wav"):
            if not old.name.startswith(f"{volume}-"):
                try:
                    old.unlink()
                except OSError:
                    pass  # Playing still: it goes with the next one made.
        part = made.with_suffix(".part")
        with wave.open(str(part), "wb") as copy:
            copy.setparams(params)
            copy.writeframes(np.clip(np.rint(samples), -32768, 32767).astype("<i2").tobytes())
        part.replace(made)
        return made
    except (OSError, EOFError, wave.Error):
        return None


def play_tune(path: Path | None) -> None:
    """Start a tune at the system volume without waiting for it, or with None stop whatever plays."""
    if sys.platform != "win32":
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
    """Plays a theme's sound, once per lobby, at 设置's 声音: volume percent of its loudness, or nothing
    while muted. folder: where the quieter copies go (sound_dir when None)."""

    def __init__(
        self,
        play: Callable[[Path | None], None] = play_tune,
        clock: Callable[[], float] = time.monotonic,
        folder: Path | None = None,
    ) -> None:
        self._play = play
        self._clock = clock
        self._folder = folder
        self._last_lobby: frozenset[str] = frozenset()
        self._last_at = float("-inf")
        self.volume = 100
        self.muted = False

    @staticmethod
    def pick(scene: str) -> str:
        """The tune for a scene: its own, or "" for none (a scene with none)."""
        return scene if scene in TUNES else ""

    def audible(self) -> bool:
        return not self.muted and self.volume > 0

    def lobby(self, likes: list[str], scene: str) -> str:
        """A lobby with these 嘉宾 players, greeted by this scene: play its sound, unless it just did
        for them."""
        if not likes or not self.pick(scene) or not self.audible():
            return ""
        players = frozenset(likes)
        now = self._clock()
        if players == self._last_lobby and now - self._last_at < SAME_LOBBY_S:
            return ""
        self._last_lobby, self._last_at = players, now
        return self.preview(scene)

    def preview(self, scene: str) -> str:
        """Play a scene's sound now; with none, or muted, stop whatever is playing."""
        tune = self.pick(scene)
        return tune if self._start(TUNES[tune] if tune else None) else ""

    def sample(self) -> bool:
        """A moment of 玫瑰花边's sound at this volume, for 声音's slider let go."""
        return self._start(TUNES[SAMPLE_TUNE], SAMPLE_S)

    def _start(self, tune: Path | None, seconds: float | None = None) -> bool:
        if tune is not None and self.audible():
            tune = scaled_tune(tune, self.volume, self._folder or sound_dir(), seconds)
        else:
            tune = None
        self._play(tune)
        return tune is not None

    def stop(self) -> None:
        self._play(None)
