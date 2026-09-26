"""Gate hardware abstraction for the high-platform turnstile.

The physical gate is not chosen yet, so the rest of the system only ever
talks to this interface. Swapping in a real relay/GPIO controller later
means adding one more implementation here, nothing else changes.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("gate_controller")


class GateController(ABC):
    @abstractmethod
    def trigger_access(self, allowed: bool, *, wristband_id: str) -> None:
        """React to an access decision (e.g. open the gate)."""


class DummyGateController(GateController):
    """Logs the decision only; no physical gate is connected yet."""

    def trigger_access(self, allowed: bool, *, wristband_id: str) -> None:
        actie = "OPENEN" if allowed else "GESLOTEN houden"
        logger.info("Hekje %s voor bandje %s", actie, wristband_id)


def create_gate_controller(name: str) -> GateController:
    if name == "dummy":
        return DummyGateController()
    raise ValueError(f"Onbekende gate_controller-implementatie: {name}")
