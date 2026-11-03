"""Pydantic request/response models for the API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.status import Status, Verdict


class ScanRequest(BaseModel):
    wristband_id: str


class ScanResponse(BaseModel):
    wristband_id: str
    status: Status
    requires_verdict: bool
    requires_practice_ack: bool
    expires_at: datetime | None = None
    # Ingevuld zodra de status al vaststaat (GESLAAGD/NIET_GESLAAGD): het
    # hostscherm doet dan meteen ook de Ski Jump-toegangscontrole, zonder
    # apart scherm/scan aan de Ski Jump zelf.
    ski_jump_toegestaan: bool | None = None
    ski_jump_reden: str | None = None


class VerdictResponse(BaseModel):
    status: Status
    ski_jump_toegestaan: bool | None = None
    ski_jump_reden: str | None = None


class VerdictRequest(BaseModel):
    verdict: Verdict


class DeviceNameRequest(BaseModel):
    name: str = Field(max_length=40)


class PairRequest(BaseModel):
    code: str = Field(max_length=16)
    name: str = Field(default="", max_length=40)


class PairResponse(BaseModel):
    device_id: str
    token: str


class PairingCodeResponse(BaseModel):
    code: str
    expires_at: datetime


class PairedDeviceResponse(BaseModel):
    device_id: str
    name: str | None
    paired_at: datetime
    last_seen_at: datetime


class GateScanRequest(BaseModel):
    wristband_id: str


class GateScanResponse(BaseModel):
    wristband_id: str
    status: Status
    allowed: bool
    reason: str | None = None


class LoginRequest(BaseModel):
    pincode: str


class LoginResponse(BaseModel):
    token: str
    employee_id: int
    name: str
    role: str
    short_pincode: bool = False


class GroupPincodeRequest(BaseModel):
    pincode: str = Field(max_length=64)


class GroupResponse(BaseModel):
    role: str
    label: str
    active: bool


class ManualStatusRequest(BaseModel):
    status: Status
    reason: str | None = None


class WristbandStatusResponse(BaseModel):
    wristband_id: str
    status: Status


class EventResponse(BaseModel):
    id: int
    timestamp: datetime
    event_type: str
    wristband_id: str | None
    source: str
    # Leesbare naam van het toestel achter `source`, als die ingesteld is.
    device_name: str | None = None
    employee_id: int | None
    group: str | None = None
    detail: dict
