"""Employee (staff) management: creation, updates, revocation. Role checks
(admin-only) live in the API layer (see app/dependencies.py require_role).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EmployeeModel
from app.security import hash_pincode, verify_pincode
from app.services.common import now_utc
from app.services.errors import DuplicatePincodeError, EmployeeNotFoundError

VALID_ROLES = {"admin", "supervisor"}


def _pincode_in_use(db: Session, pincode: str) -> bool:
    employees = db.execute(select(EmployeeModel).where(EmployeeModel.active.is_(True))).scalars()
    return any(verify_pincode(pincode, employee.pincode_hash) for employee in employees)


def list_employees(db: Session) -> list[EmployeeModel]:
    return list(db.execute(select(EmployeeModel).order_by(EmployeeModel.id)).scalars())


def create_employee(db: Session, *, name: str, pincode: str, role: str) -> EmployeeModel:
    if role not in VALID_ROLES:
        raise ValueError(f"Ongeldige rol: {role}")
    if _pincode_in_use(db, pincode):
        raise DuplicatePincodeError("Deze pincode is al in gebruik door een actieve medewerker.")

    employee = EmployeeModel(
        name=name, pincode_hash=hash_pincode(pincode), role=role,
        active=True, created_at=now_utc(),
    )
    db.add(employee)
    db.commit()
    return employee


def update_employee(
    db: Session,
    employee_id: int,
    *,
    name: str | None = None,
    role: str | None = None,
    active: bool | None = None,
    new_pincode: str | None = None,
) -> EmployeeModel:
    employee = db.get(EmployeeModel, employee_id)
    if employee is None:
        raise EmployeeNotFoundError("Medewerker niet gevonden.")

    if name is not None:
        employee.name = name
    if role is not None:
        if role not in VALID_ROLES:
            raise ValueError(f"Ongeldige rol: {role}")
        employee.role = role
    if new_pincode is not None:
        if _pincode_in_use(db, new_pincode):
            raise DuplicatePincodeError("Deze pincode is al in gebruik door een actieve medewerker.")
        employee.pincode_hash = hash_pincode(new_pincode)
    if active is not None:
        employee.active = active
        employee.revoked_at = None if active else now_utc()

    db.commit()
    return employee
