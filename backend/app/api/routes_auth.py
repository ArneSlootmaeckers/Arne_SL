"""Login/logout for the admin screen (personal pincode, sliding-timeout session)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.dependencies import client_address, get_db, get_login_limiter, require_employee
from app.models import EmployeeModel
from app.schemas import LoginRequest, LoginResponse
from app.services import auth_service
from app.services.common import log_event
from app.services.employee_service import MIN_PINCODE_LENGTH
from app.services.errors import InvalidPincodeError
from app.services.rate_limit import AttemptLimiter

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    limiter: AttemptLimiter = Depends(get_login_limiter),
) -> LoginResponse:
    client = client_address(request)
    limiter.check(client)
    try:
        token, employee = auth_service.login(db, pincode=payload.pincode, source="admin", client=client)
    except InvalidPincodeError:
        if limiter.record_failure(client):
            log_event(db, event_type="INLOGGEN_GEBLOKKEERD", source="admin", detail={"ip": client})
            db.commit()
        raise
    limiter.reset(client)
    return LoginResponse(
        token=token, employee_id=employee.id, name=employee.name, role=employee.role,
        # Pincodes van vóór de minimumlengte blijven werken, maar het
        # beheerscherm vraagt dan om ze te vervangen.
        short_pincode=len(payload.pincode) < MIN_PINCODE_LENGTH,
    )


@router.post("/logout")
def logout(db: Session = Depends(get_db), authorization: str | None = Header(default=None)) -> dict:
    if authorization and authorization.startswith("Bearer "):
        auth_service.logout(db, token=authorization.removeprefix("Bearer "), source="admin")
    return {"ok": True}


@router.get("/me")
def me(employee: EmployeeModel = Depends(require_employee)) -> dict:
    return {"id": employee.id, "name": employee.name, "role": employee.role}
