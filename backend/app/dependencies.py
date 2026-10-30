"""FastAPI dependencies: DB sessions, settings, and auth/role guards."""
from __future__ import annotations

from typing import Iterator

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.hardware.gate_controller import GateController
from app.models import EmployeeModel, PairedDeviceModel
from app.services.auth_service import get_current_employee
from app.services.errors import DeviceNotPairedError, SessionExpiredError, PermissionDeniedError
from app.services.pairing_service import authenticate_device
from app.services.rate_limit import AttemptLimiter


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


def get_login_limiter(request: Request) -> AttemptLimiter:
    return request.app.state.login_limiter


def get_pairing_limiter(request: Request) -> AttemptLimiter:
    return request.app.state.pairing_limiter


def client_address(request: Request) -> str:
    return request.client.host if request.client else "onbekend"


def require_paired_device(
    db: Session = Depends(get_db),
    x_device_token: str | None = Header(default=None),
) -> PairedDeviceModel:
    """Enkel een gekoppeld toestel mag scannen of een oordeel geven. Het
    toestel-id komt uit de sleutel, nooit uit wat het toestel zelf meestuurt."""
    if not x_device_token:
        raise DeviceNotPairedError("Dit toestel is niet gekoppeld. Vraag een koppelcode aan een beheerder.")
    return authenticate_device(db, token=x_device_token)


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
