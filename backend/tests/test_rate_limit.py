"""AttemptLimiter: blokkering na te veel foute pogingen, en weer vrij na afloop."""
from __future__ import annotations

import pytest

from app.services.errors import TooManyAttemptsError
from app.services.rate_limit import AttemptLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_blocks_after_max_failures_and_unblocks_later():
    clock = FakeClock()
    limiter = AttemptLimiter(max_failures=3, window_seconds=60, block_seconds=120, clock=clock)

    assert limiter.record_failure("a") is False
    assert limiter.record_failure("a") is False
    assert limiter.record_failure("a") is True
    with pytest.raises(TooManyAttemptsError, match="2 minuten"):
        limiter.check("a")
    limiter.check("b")  # een ander adres heeft er geen last van

    clock.now = 121
    limiter.check("a")
    assert limiter.record_failure("a") is False  # telling begint opnieuw


def test_old_failures_fall_out_of_the_window():
    clock = FakeClock()
    limiter = AttemptLimiter(max_failures=3, window_seconds=60, block_seconds=120, clock=clock)

    limiter.record_failure("a")
    limiter.record_failure("a")
    clock.now = 61
    assert limiter.record_failure("a") is False
    limiter.check("a")
