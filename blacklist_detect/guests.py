"""Which 嘉宾场景 greet the 嘉宾 in a lobby. No UI imports.

A combination whose 嘉宾 are all in the lobby wins, the one with the most of them first (the earlier
one on a tie); other 嘉宾 there with it don't stop it. Else the 嘉宾 highest on the list with scenes
ticked decides: the list shows the newest first, and the player orders it. Else the highest on 随机:
any scene. One on 不放 asks for none and the next in line decides; with every one there on 不放, no
scene plays.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from blacklist_detect import love_scenes
from blacklist_detect.match import fold
from blacklist_detect.model import Combo, Entry, Scenes


def _plays(key: str) -> bool:
    return key in love_scenes.KEYS


def ticked(scenes: Scenes, known: Callable[[str], bool] = _plays) -> tuple[str, ...]:
    """The scenes ticked that this version plays, each once: one replaced is its replacement, one it no
    longer has is left out."""
    return tuple(dict.fromkeys(key for key in map(love_scenes.shown, scenes.keys) if known(key)))


def lobby_choice(
    likes: list[Entry],
    combos: Iterable[Combo],
    present: Iterable[Entry],
    default: str,
    known: Callable[[str], bool] = _plays,
) -> str | tuple[str, ...]:
    """The 嘉宾场景 choice for a lobby with these 嘉宾 present, as love_scenes.choose takes it: a key,
    keys to pick one of, "random" (any scene), or "off" when each one there is on 不放.

    likes is 嘉宾 as saved (the last is the top of the list); default is the choice with none of them
    here ("classic"); known says whether a scene is one this version plays, so ticked ones it no
    longer has are left out, and a set left with none is as if on 随机. One on 随机 is 随机 whatever
    it has ticked."""
    here = {fold(like.name) for like in present}
    if not here:
        return default
    found = []
    for combo in combos:
        members = {fold(name) for name in combo.names}
        if len(members) >= 2 and members <= here:
            found.append((len(members), combo))
    # The most 嘉宾 first; sorted keeps the earlier first on a tie.
    for _size, combo in sorted(found, key=lambda pair: -pair[0]):
        if not combo.scenes.off:
            return _choice(_asked(combo.scenes, known))
    on = [like for like in reversed(likes) if fold(like.name) in here and not like.scenes.off]
    for like in on:
        keys = _asked(like.scenes, known)
        if keys:
            return _choice(keys)
    return "random" if on else "off"


def _asked(scenes: Scenes, known: Callable[[str], bool]) -> tuple[str, ...]:
    """The scenes asked for by ticks: none on 随机, its ticks kept but not used."""
    return () if scenes.random else ticked(scenes, known)


def _choice(keys: tuple[str, ...]) -> str | tuple[str, ...]:
    """Scenes ticked as a choice: the one, the several, or any for none."""
    if not keys:
        return "random"
    return keys[0] if len(keys) == 1 else keys


def members(combo: Combo, likes: list[Entry]) -> list[tuple[str, bool]]:
    """A combination's 嘉宾 as shown, each with whether they are still on 嘉宾."""
    by_key = {fold(like.name): like for like in likes}
    return [(by_key[fold(name)].shown(), True) if fold(name) in by_key else (name, False) for name in combo.names]
