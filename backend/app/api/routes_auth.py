"""Login/logout for the admin screen (personal pincode, sliding-timeout session)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_employee
from app.models import EmployeeModel
from app.schemas import LoginRequest, LoginResponse
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    token, employee = auth_service.login(db, pincode=payload.pincode, source="admin")
    return LoginResponse(token=token, employee_id=employee.id, name=employee.name, role=employee.role)


@router.post("/logout")
def logout(db: Session = Depends(get_db), authorization: str | None = Header(default=None)) -> dict:
    if authorization and authorization.startswith("Bearer "):
        auth_service.logout(db, token=authorization.removeprefix("Bearer "), source="admin")
    return {"ok": True}


@router.get("/me")
def me(employee: EmployeeModel = Depends(require_employee)) -> dict:
    return {"id": employee.id, "name": employee.name, "role": employee.role}
