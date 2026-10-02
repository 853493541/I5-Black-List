"""Decide when a seen lobby title should become one full name check."""

from __future__ import annotations

GLANCE_INTERVAL_MS = 400
RETRY_COOLDOWN_S = 1.0
_CLAIM_S = 30.0


class LobbyWatch:
    """Fire on the title, then stay quiet until it leaves.

    A full check that does not find the lobby can try again after a short
    cooldown. A check that does find it waits until the title is gone.
    """

    def __init__(self, cooldown: float = RETRY_COOLDOWN_S) -> None:
        self.cooldown = cooldown
        self._held = False
        self._next = 0.0

    def wants_check(self, present: bool, now: float) -> bool:
        if not present:
            self._held = False
            self._next = 0.0
            return False
        if self._held or now < self._next:
            return False
        return True

    def arm(self, now: float) -> None:
        """Hold the trigger until the check reports back."""
        self._next = now + _CLAIM_S

    def hold(self) -> None:
        """The lobby was read. Ignore the title until it disappears."""
        self._held = True

    def retry_after(self, now: float) -> None:
        """The title was on screen, but this was not the lobby yet."""
        self._held = False
        self._next = now + self.cooldown
