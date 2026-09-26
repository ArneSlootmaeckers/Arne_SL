"""Pincode login/logout and session handling with sliding inactivity timeout."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EmployeeModel, SessionModel
from app.security import generate_session_token, verify_pincode
from app.services.common import log_event, now_utc
from app.services.errors import InvalidPincodeError, SessionExpiredError


def login(db: Session, *, pincode: str, source: str) -> tuple[str, EmployeeModel]:
    employees = db.execute(select(EmployeeModel).where(EmployeeModel.active.is_(True))).scalars()
    for employee in employees:
        if verify_pincode(pincode, employee.pincode_hash):
            token = generate_session_token()
            now = now_utc()
            db.add(SessionModel(token=token, employee_id=employee.id, created_at=now, last_activity_at=now))
            log_event(db, event_type="INLOGGEN", employee_id=employee.id, source=source)
            db.commit()
            return token, employee

    log_event(db, event_type="INLOGGEN_MISLUKT", source=source)
    db.commit()
    raise InvalidPincodeError("Onjuiste pincode.")


def logout(db: Session, *, token: str, source: str) -> None:
    session = db.get(SessionModel, token)
    if session is not None:
        log_event(db, event_type="UITLOGGEN", employee_id=session.employee_id, source=source)
        db.delete(session)
        db.commit()


def get_current_employee(db: Session, *, token: str, inactivity_timeout_seconds: int) -> EmployeeModel:
    session = db.get(SessionModel, token)
    if session is None:
        raise SessionExpiredError("Niet ingelogd of sessie verlopen. Log opnieuw in.")

    now = now_utc()
    if (now - session.last_activity_at).total_seconds() > inactivity_timeout_seconds:
        db.delete(session)
        db.commit()
        raise SessionExpiredError("Sessie verlopen door inactiviteit. Log opnieuw in.")

    employee = db.get(EmployeeModel, session.employee_id)
    if employee is None or not employee.active:
        db.delete(session)
        db.commit()
        raise SessionExpiredError("Account is niet meer actief. Log opnieuw in.")

    session.last_activity_at = now
    db.commit()
    return employee
