"""Which 嘉宾特效 scene greets the 嘉宾 in a lobby. No UI imports.

A combination whose 嘉宾 are all in the lobby wins, the one with the most of them first (the earlier
one on a tie); other 嘉宾 there with it don't stop it. Else the 嘉宾 highest on the list with a theme of
their own decides: the list shows the newest first, and the player orders it. Else the default, 经典.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from blacklist_detect.match import fold
from blacklist_detect.model import Combo, Entry


def lobby_choice(
    likes: list[Entry],
    combos: Iterable[Combo],
    present: Iterable[Entry],
    default: str,
    known: Callable[[str], bool] = lambda _key: True,
) -> str:
    """The 嘉宾特效 choice for a lobby with these 嘉宾 present.

    likes is 嘉宾 as saved (the last is the top of the list); default is what plays when none of them
    picked one ("classic"); known says whether a theme is one this version plays, so a theme it no
    longer has gives way as if it were not picked."""
    here = {fold(like.name) for like in present}
    if not here:
        return default
    best: Combo | None = None
    for combo in combos:
        members = {fold(name) for name in combo.names}
        if len(members) < 2 or not members <= here or not known(combo.theme):
            continue
        if best is None or len(members) > len({fold(name) for name in best.names}):
            best = combo
    if best is not None:
        return best.theme
    for like in reversed(likes):
        if fold(like.name) in here and like.theme and known(like.theme):
            return like.theme
    return default


def members(combo: Combo, likes: list[Entry]) -> list[tuple[str, bool]]:
    """A combination's 嘉宾 as shown, each with whether they are still on 嘉宾."""
    by_key = {fold(like.name): like for like in likes}
    return [(by_key[fold(name)].shown(), True) if fold(name) in by_key else (name, False) for name in combo.names]
