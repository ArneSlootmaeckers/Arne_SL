"""Pydantic request/response models for the API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.domain.status import Status, Verdict


class ScanRequest(BaseModel):
    wristband_id: str
    device_id: str


class ScanResponse(BaseModel):
    wristband_id: str
    status: Status
    requires_verdict: bool
    requires_practice_ack: bool
    expires_at: datetime | None = None


class VerdictRequest(BaseModel):
    device_id: str
    verdict: Verdict


class PracticeAckRequest(BaseModel):
    device_id: str


class GateScanRequest(BaseModel):
    wristband_id: str
    device_id: str


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


class EmployeeCreateRequest(BaseModel):
    name: str
    pincode: str
    role: str


class EmployeeUpdateRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    active: bool | None = None
    new_pincode: str | None = None


class EmployeeResponse(BaseModel):
    id: int
    name: str
    role: str
    active: bool

    model_config = {"from_attributes": True}


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
    employee_id: int | None
    detail: dict
