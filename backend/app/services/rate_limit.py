"""Remt het raden van pincodes en koppelcodes af: na `max_failures` foute
pogingen vanaf hetzelfde adres binnen `window_seconds` is dat adres
`block_seconds` geblokkeerd.

Bewust in het geheugen (niet in de database): na een herstart van de server
begint de telling opnieuw, wat geen probleem is -- herstarten duurt langer
dan een paar pogingen, en zo kan een volle blokkering nooit "blijven hangen".
"""
from __future__ import annotations

import math
import threading
import time
from collections import defaultdict

from app.services.errors import TooManyAttemptsError


class AttemptLimiter:
    def __init__(
        self, *, max_failures: int = 5, window_seconds: float = 300, block_seconds: float = 300,
        clock=time.monotonic,
    ) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self._clock = clock
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._blocked_until: dict[str, float] = {}
        # De gewone (niet-async) API-routes draaien in een threadpool.
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        """Gooit TooManyAttemptsError zolang `key` geblokkeerd is."""
        with self._lock:
            until = self._blocked_until.get(key)
            if until is None:
                return
            remaining = until - self._clock()
            if remaining <= 0:
                del self._blocked_until[key]
                return
        minutes = max(1, math.ceil(remaining / 60))
        raise TooManyAttemptsError(
            f"Te veel foute pogingen. Probeer opnieuw over {minutes} "
            f"{'minuut' if minutes == 1 else 'minuten'}."
        )

    def record_failure(self, key: str) -> bool:
        """Telt een foute poging; True als `key` daardoor nu geblokkeerd is."""
        with self._lock:
            now = self._clock()
            recent = [t for t in self._failures[key] if now - t < self.window_seconds]
            recent.append(now)
            if len(recent) >= self.max_failures:
                self._blocked_until[key] = now + self.block_seconds
                self._failures.pop(key, None)
                return True
            self._failures[key] = recent
            return False

    def reset(self, key: str) -> None:
        """Na een geslaagde poging begint de telling opnieuw."""
        with self._lock:
            self._failures.pop(key, None)
