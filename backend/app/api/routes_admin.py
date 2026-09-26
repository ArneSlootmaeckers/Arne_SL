"""Admin screen API: employee management, manual overrides, logs, report."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_db, get_settings, require_role
from app.domain.calendar import local_today
from app.models import DailyStatusModel, EmployeeModel
from app.schemas import (
    EmployeeCreateRequest,
    EmployeeResponse,
    EmployeeUpdateRequest,
    EventResponse,
    ManualStatusRequest,
    WristbandStatusResponse,
)
from app.services import employee_service, log_service, report_service
from app.services.common import get_or_create_wristband, log_event, now_utc, read_effective_status

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/employees", response_model=list[EmployeeResponse])
def list_employees(
    db: Session = Depends(get_db), _: EmployeeModel = Depends(require_role("admin"))
) -> list[EmployeeModel]:
    return employee_service.list_employees(db)


@router.post("/employees", response_model=EmployeeResponse)
def create_employee(
    payload: EmployeeCreateRequest,
    db: Session = Depends(get_db),
    _: EmployeeModel = Depends(require_role("admin")),
) -> EmployeeModel:
    return employee_service.create_employee(db, name=payload.name, pincode=payload.pincode, role=payload.role)


@router.patch("/employees/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int,
    payload: EmployeeUpdateRequest,
    db: Session = Depends(get_db),
    _: EmployeeModel = Depends(require_role("admin")),
) -> EmployeeModel:
    return employee_service.update_employee(
        db, employee_id,
        name=payload.name, role=payload.role, active=payload.active, new_pincode=payload.new_pincode,
    )


@router.get("/wristbands/{wristband_id}", response_model=WristbandStatusResponse)
def get_wristband_status(
    wristband_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: EmployeeModel = Depends(require_role("admin", "supervisor")),
) -> WristbandStatusResponse:
    today = local_today(now_utc(), settings.tz)
    status, _ = read_effective_status(db, wristband_id, today)
    return WristbandStatusResponse(wristband_id=wristband_id, status=status)


@router.post("/wristbands/{wristband_id}/status", response_model=WristbandStatusResponse)
def set_wristband_status(
    wristband_id: str,
    payload: ManualStatusRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    employee: EmployeeModel = Depends(require_role("admin", "supervisor")),
) -> WristbandStatusResponse:
    today = local_today(now_utc(), settings.tz)
    get_or_create_wristband(db, wristband_id)
    old_status, row = read_effective_status(db, wristband_id, today)

    if row is None:
        row = DailyStatusModel(wristband_id=wristband_id, status_date=today)
        db.add(row)
    row.status = payload.status.value
    row.updated_at = now_utc()
    row.updated_by_employee_id = employee.id
    row.reason = payload.reason

    log_event(
        db, event_type="HANDMATIGE_WIJZIGING", wristband_id=wristband_id, source="admin",
        employee_id=employee.id,
        detail={
            "oude_status": old_status.value,
            "nieuwe_status": payload.status.value,
            "reden": payload.reason,
        },
    )
    db.commit()
    return WristbandStatusResponse(wristband_id=wristband_id, status=payload.status)


@router.get("/logs", response_model=list[EventResponse])
def get_logs(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: EmployeeModel = Depends(require_role("admin", "supervisor")),
    event_date: date | None = None,
    wristband_id: str | None = None,
    employee_id: int | None = None,
    event_type: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    events = log_service.query_events(
        db, tz=settings.tz, event_date=event_date, wristband_id=wristband_id,
        employee_id=employee_id, event_type=event_type, limit=limit, offset=offset,
    )
    return [log_service.event_to_dict(event) for event in events]


@router.get("/logs/export.csv")
def export_logs_csv(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: EmployeeModel = Depends(require_role("admin", "supervisor")),
    event_date: date | None = None,
    wristband_id: str | None = None,
    employee_id: int | None = None,
    event_type: str | None = None,
) -> Response:
    events = log_service.query_events(
        db, tz=settings.tz, event_date=event_date, wristband_id=wristband_id,
        employee_id=employee_id, event_type=event_type, limit=100_000, offset=0,
    )
    csv_content = log_service.events_to_csv(events)
    return Response(
        content=csv_content, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=logs.csv"},
    )


@router.get("/report")
def get_report(
    report_date: date,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: EmployeeModel = Depends(require_role("admin", "supervisor")),
) -> dict:
    return report_service.daily_report(db, report_date=report_date, tz=settings.tz)


@router.post("/logs/purge")
def purge_logs(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: EmployeeModel = Depends(require_role("admin")),
) -> dict:
    count = log_service.purge_old_events(db, settings.log_retention_days)
    return {"verwijderd": count}
