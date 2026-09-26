"""Cushion-clear ("kussen vrij") sensor abstraction.

Out of scope for this project (section 10 of the assignment): a future light
barrier at the airbag's exit would block the next scan until the cushion is
clear. This is only the extension point — always a no-op dummy for now,
gated by config.cushion_sensor_enabled (currently unused by any caller).
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class CushionSensor(ABC):
    @abstractmethod
    def is_clear(self) -> bool:
        """Whether the airbag is currently clear of the previous jumper."""


class DummyCushionSensor(CushionSensor):
    def is_clear(self) -> bool:
        return True


def create_cushion_sensor(enabled: bool) -> CushionSensor:
    return DummyCushionSensor()
