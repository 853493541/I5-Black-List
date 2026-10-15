"""嘉宾音乐: each 嘉宾特效 theme's own few seconds of sound, played as it greets 嘉宾 players in a lobby.

Every scene in love_scenes.SCENES but 经典, which greets in silence, has one (TUNES), made for it, its
accents on the scene's moments. build/theme_tunes.py plays 冰蓝极光's, 星河许愿's, 赛博朋克's two and
毛茸茸保护协会's; build/wedding_tunes.py the wedding tunes 玫瑰花边 (the Bridal Chorus on organ), 可我觉得很神圣啊
(church bells) and 数学公式 (Pachelbel's Canon on harp) keep. No recording is used for those, so a stream can carry them. 遇袭's is the 指挥家's music from
模仿者狂欢 with the 演说家遇袭 notice's sound in it at its strike (build/ambush_tune.py): the game's own
recording, the user's choice made knowing NetEase owns it.

The sound follows the theme: 音乐 in 嘉宾特效 only turns it on (跟随特效) or off (无).
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from pathlib import Path

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
# 音乐's choices in 嘉宾特效, its default first: the theme's own sound, or none.
MUSIC_CHOICES = (("theme", "跟随特效"), ("off", "无"))
# The same 嘉宾 players found again this soon are the same lobby, checked again: no second tune.
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


class ThemeMusic:
    """Plays a theme's sound, once per lobby."""

    def __init__(self, play: Callable[[Path | None], None] = play_tune, clock: Callable[[], float] = time.monotonic) -> None:
        self._play = play
        self._clock = clock
        self._last_lobby: frozenset[str] = frozenset()
        self._last_at = float("-inf")

    @staticmethod
    def pick(scene: str) -> str:
        """The tune for a scene: its own, or "" for none (无, or a scene with none)."""
        return scene if scene in TUNES else ""

    def lobby(self, likes: list[str], scene: str) -> str:
        """A lobby with these 嘉宾 players, greeted by this scene: play its sound, unless it just did
        for them."""
        if not likes or not self.pick(scene):
            return ""
        players = frozenset(likes)
        now = self._clock()
        if players == self._last_lobby and now - self._last_at < SAME_LOBBY_S:
            return ""
        self._last_lobby, self._last_at = players, now
        return self.preview(scene)

    def preview(self, scene: str) -> str:
        """Play a scene's sound now; with none, stop whatever is playing."""
        tune = self.pick(scene)
        self._play(TUNES[tune] if tune else None)
        return tune

    def stop(self) -> None:
        self._play(None)
