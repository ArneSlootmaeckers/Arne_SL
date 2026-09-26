"""Pure status domain logic for the wristband admission system.

No I/O, no database, no framework dependencies — fully unit-testable in isolation.
This module is the single source of truth for the status model in section 2
of the assignment.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class Status(str, Enum):
    NOG_NIET_GESPRONGEN = "NOG_NIET_GESPRONGEN"
    HERKANSING = "HERKANSING"
    GESLAAGD = "GESLAAGD"
    NIET_GESLAAGD = "NIET_GESLAAGD"


class Verdict(str, Enum):
    GROEN = "GROEN"
    ROOD = "ROOD"


class VerdictNotAllowedError(Exception):
    """Raised when a verdict is submitted for a status that no longer accepts one."""


@dataclass(frozen=True)
class VerdictResult:
    new_status: Status
    status_changed: bool
    is_practice_jump: bool


# Statuses for which the low platform still allows a jump (all except NIET_GESLAAGD).
_LOW_PLATFORM_ALLOWED = {Status.NOG_NIET_GESPRONGEN, Status.HERKANSING, Status.GESLAAGD}

# The transition table from section 2 of the assignment: (current status, verdict) -> next status.
_TRANSITIONS: dict[tuple[Status, Verdict], Status] = {
    (Status.NOG_NIET_GESPRONGEN, Verdict.GROEN): Status.GESLAAGD,
    (Status.NOG_NIET_GESPRONGEN, Verdict.ROOD): Status.HERKANSING,
    (Status.HERKANSING, Verdict.GROEN): Status.GESLAAGD,
    (Status.HERKANSING, Verdict.ROOD): Status.NIET_GESLAAGD,
    (Status.GESLAAGD, Verdict.GROEN): Status.GESLAAGD,
    (Status.GESLAAGD, Verdict.ROOD): Status.GESLAAGD,
}


def effective_status(stored_status: Status | None, stored_date: date | None, today: date) -> Status:
    """Apply the day-rollover rule: a stored status only counts for the day it was recorded on."""
    if stored_status is None or stored_date is None or stored_date != today:
        return Status.NOG_NIET_GESPRONGEN
    return stored_status


def apply_verdict(current_status: Status, verdict: Verdict) -> VerdictResult:
    """Compute the result of a host verdict against a wristband's current effective status.

    Raises VerdictNotAllowedError for NIET_GESLAAGD, which never accepts a verdict again
    for the rest of the day.
    """
    if current_status is Status.NIET_GESLAAGD:
        raise VerdictNotAllowedError(
            f"Status is {Status.NIET_GESLAAGD.value}: geen oordeel meer toegestaan vandaag."
        )

    new_status = _TRANSITIONS[(current_status, verdict)]
    is_practice_jump = current_status is Status.GESLAAGD
    return VerdictResult(
        new_status=new_status,
        status_changed=new_status != current_status,
        is_practice_jump=is_practice_jump,
    )


def can_jump_low_platform(status: Status) -> bool:
    """Whether a wristband with this status may still jump from the low platform."""
    return status in _LOW_PLATFORM_ALLOWED


def can_jump_high_platform(status: Status) -> bool:
    """Whether a wristband with this status may pass the high platform gate."""
    return status is Status.GESLAAGD


def is_valid_manual_status(value: str) -> bool:
    """Whether a string is one of the four valid statuses (for manual admin overrides)."""
    return value in Status.__members__
