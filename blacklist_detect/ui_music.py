"""心动音乐: a few seconds of wedding music for 心动 players in one lobby (as many as 心动人数 says).

Five tunes, all public domain: Wagner's Bridal Chorus (1850) as church organ, music box and 8-bit,
Pachelbel's Canon on harp, and church bells. build/wedding_tunes.py plays them into the WAV files,
so no recording is used and a stream can carry them. 设置 picks one, 随机 (a different one each
time), or 关闭.
"""

from __future__ import annotations

import random
import sys
import time
from collections.abc import Callable
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"
# (key, name in 设置, file), in the order 设置 lists them.
TUNE_LIST: tuple[tuple[str, str, str], ...] = (
    ("organ", "婚礼进行曲 · 管风琴", "wedding-organ.wav"),
    ("music-box", "婚礼进行曲 · 八音盒", "wedding-music-box.wav"),
    ("8bit", "婚礼进行曲 · 8-bit", "wedding-8bit.wav"),
    ("canon", "卡农 · 竖琴", "wedding-canon.wav"),
    ("bells", "婚礼钟声", "wedding-bells.wav"),
)
KEYS = tuple(key for key, _name, _file in TUNE_LIST)
TUNES = {key: ASSETS / file for key, _name, file in TUNE_LIST}
# The same 心动 players found again this soon are the same lobby, checked again: no second tune.
SAME_LOBBY_S = 60.0


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


class WeddingMusic:
    """Picks and plays the tunes, once per lobby."""

    def __init__(
        self,
        play: Callable[[Path | None], None] = play_tune,
        rng: random.Random | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._play = play
        self._rng = rng or random.Random()
        self._clock = clock
        self._last_tune = ""
        self._last_lobby: frozenset[str] = frozenset()
        self._last_at = float("-inf")

    def pick(self, choice: str) -> str:
        """The tune for a 心动特效 choice: its key, "random" (any but the one just played), or "off" ("")."""
        if choice in TUNES:
            return choice
        if choice != "random":
            return ""
        pool = [key for key in KEYS if key != self._last_tune] or list(KEYS)
        return self._rng.choice(pool)

    def lobby(self, likes: list[str], choice: str) -> str:
        """A lobby with these 心动 players, as many as 心动特效 plays for: play, unless it just did
        for them."""
        if not likes or not self.pick(choice):
            return ""
        players = frozenset(likes)
        now = self._clock()
        if players == self._last_lobby and now - self._last_at < SAME_LOBBY_S:
            return ""
        self._last_lobby, self._last_at = players, now
        return self.preview(choice)

    def preview(self, choice: str) -> str:
        """Play the tune for a choice now; 关闭 stops whatever is playing."""
        tune = self.pick(choice)
        self._last_tune = tune or self._last_tune
        self._play(TUNES[tune] if tune else None)
        return tune

    def stop(self) -> None:
        self._play(None)
