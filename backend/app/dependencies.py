"""FastAPI dependencies: DB sessions, settings, and auth/role guards."""
from __future__ import annotations

from typing import Iterator

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.hardware.gate_controller import GateController
from app.models import EmployeeModel
from app.services.auth_service import get_current_employee
from app.services.errors import SessionExpiredError, PermissionDeniedError


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_gate_controller(request: Request) -> GateController:
    return request.app.state.gate_controller


def require_employee(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    authorization: str | None = Header(default=None),
) -> EmployeeModel:
    if authorization is None or not authorization.startswith("Bearer "):
        raise SessionExpiredError("Niet ingelogd.")
    token = authorization.removeprefix("Bearer ")
    return get_current_employee(
        db, token=token, inactivity_timeout_seconds=settings.session_inactivity_timeout_seconds
    )


def require_role(*roles: str):
    def _dependency(employee: EmployeeModel = Depends(require_employee)) -> EmployeeModel:
        if employee.role not in roles:
            raise PermissionDeniedError("Onvoldoende rechten voor deze actie.")
        return employee

    return _dependency
