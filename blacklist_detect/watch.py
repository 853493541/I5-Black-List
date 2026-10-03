"""Decide when a seen lobby title should become one full name check."""

from __future__ import annotations

GLANCE_INTERVAL_MS = 400
RETRY_COOLDOWN_S = 1.0
_CLAIM_S = 30.0
# One missed glance is not the lobby leaving. The title must stay gone this long.
ABSENCE_S = 1.0


class LobbyWatch:
    """Fire once when the title appears, then wait until it has really left.

    A blink of the title does not start another check. The title has to stay
    gone for a second, which is the same pause used before the panel hides.
    """

    def __init__(self, cooldown: float = RETRY_COOLDOWN_S) -> None:
        self.cooldown = cooldown
        self._held = False
        self._next = 0.0
        self._gone_at: float | None = None

    def wants_check(self, present: bool, now: float) -> bool:
        if not present:
            if self._held:
                if self._gone_at is None:
                    self._gone_at = now
                elif now - self._gone_at >= ABSENCE_S:
                    self._held = False
                    self._next = 0.0
                    self._gone_at = None
            return False
        self._gone_at = None
        if self._held or now < self._next:
            return False
        return True

    def arm(self, now: float) -> None:
        """Hold the trigger until the check reports back."""
        self._next = now + _CLAIM_S

    def hold(self) -> None:
        """This appearance was already checked. Wait until the title leaves."""
        self._held = True
        self._gone_at = None

    def retry_after(self, now: float) -> None:
        """The check never started. Try once the cooldown has passed."""
        self._held = False
        self._gone_at = None
        self._next = now + self.cooldown
