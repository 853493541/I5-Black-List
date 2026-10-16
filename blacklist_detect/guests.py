"""Which 嘉宾场景 greet the 嘉宾 in a lobby. No UI imports.

A combination whose 嘉宾 are all in the lobby wins, the one with the most of them first (the earlier
one on a tie); other 嘉宾 there with it don't stop it. Else the 嘉宾 highest on the list with scenes
ticked decides: the list shows the newest first, and the player orders it. Else the highest on 随机:
any scene. One on 不放 asks for none and the next in line decides; with every one there on 不放, no
scene plays for them. Then 我 (the player's own 场景) decides, unless a 黑名单 player is there: the
warning is the news then (lobby_scene).
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
    present = list(present)
    if not present:
        return default
    return _listed(likes, combos, present, known)[1]


def lobby_scene(
    likes: list[Entry],
    combos: Iterable[Combo],
    present: Iterable[Entry],
    me: Scenes,
    blacklisted: bool,
    known: Callable[[str], bool] = _plays,
) -> tuple[str, str | tuple[str, ...]]:
    """Who greets a lobby with a 场景, and the choice as love_scenes.choose takes it: ("combo", ...) for
    a 组合 there, ("guest", ...) for the top 嘉宾 there, ("me", ...) for 我's own, or ("", "off").

    A 组合 or 嘉宾 asking for one wins, a 黑名单 player there too or not. With every one there on 不放,
    or none there, 我 decides (me), unless a 黑名单 player is there (blacklisted): no 场景 then."""
    who, choice = _listed(likes, combos, present, known)
    if who or blacklisted or me.off:
        return who, choice
    return "me", _choice(_asked(me, known))


def _listed(
    likes: list[Entry], combos: Iterable[Combo], present: Iterable[Entry], known: Callable[[str], bool]
) -> tuple[str, str | tuple[str, ...]]:
    """The 组合's or the top 嘉宾's choice for the 嘉宾 present, ("", "off") with none asking for one."""
    here = {fold(like.name) for like in present}
    found = []
    for combo in combos:
        members = {fold(name) for name in combo.names}
        if len(members) >= 2 and members <= here:
            found.append((len(members), combo))
    # The most 嘉宾 first; sorted keeps the earlier first on a tie.
    for _size, combo in sorted(found, key=lambda pair: -pair[0]):
        if not combo.scenes.off:
            return "combo", _choice(_asked(combo.scenes, known))
    on = [like for like in reversed(likes) if fold(like.name) in here and not like.scenes.off]
    for like in on:
        keys = _asked(like.scenes, known)
        if keys:
            return "guest", _choice(keys)
    return ("guest", "random") if on else ("", "off")


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
