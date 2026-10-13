"""心动音乐: a few seconds of wedding music when two or more 心动 players are in one lobby.

The tune is Wagner's Bridal Chorus (1850, public domain) in three takes: church organ, music box
and 8-bit. build/wedding_tunes.py plays them into the WAV files, so no recording is used and a
stream can carry them. One take is picked at random each time, never the same one twice running.
"""

from __future__ import annotations

import random
import sys
import time
from collections.abc import Callable
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"
TUNES = tuple(ASSETS / name for name in ("wedding-organ.wav", "wedding-music-box.wav", "wedding-8bit.wav"))
# The same 心动 players found again this soon are the same lobby, checked again: no second tune.
SAME_LOBBY_S = 60.0


def play_tune(path: Path) -> None:
    """Start a tune at the system volume without waiting for it. It cuts off any sound still
    playing, the chime included, as Windows plays one at a time."""
    if sys.platform != "win32" or not path.is_file():
        return
    try:
        import winsound

        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass


class WeddingMusic:
    """Picks and plays the tunes, once per lobby."""

    def __init__(
        self,
        play: Callable[[Path], None] = play_tune,
        rng: random.Random | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._play = play
        self._rng = rng or random.Random()
        self._clock = clock
        self._last_tune: Path | None = None
        self._last_lobby: frozenset[str] = frozenset()
        self._last_at = float("-inf")

    def pick(self) -> Path:
        """Any tune but the one just played."""
        choices = [tune for tune in TUNES if tune != self._last_tune] or list(TUNES)
        self._last_tune = self._rng.choice(choices)
        return self._last_tune

    def lobby(self, likes: list[str]) -> Path | None:
        """A lobby with these 心动 players: play, if there are two or more and not just now for them."""
        if len(likes) < 2:
            return None
        players = frozenset(likes)
        now = self._clock()
        if players == self._last_lobby and now - self._last_at < SAME_LOBBY_S:
            return None
        self._last_lobby, self._last_at = players, now
        tune = self.pick()
        self._play(tune)
        return tune

    def preview(self) -> Path:
        """▶ in 设置: one of the tunes, now."""
        tune = self.pick()
        self._play(tune)
        return tune
