"""Beheerscherm-API. Wie wat mag:

- beheerder ("admin"): alles, ook pincodes, telefoons koppelen en afsluiten;
- vaste medewerkers ("supervisor"): bandjes opzoeken en corrigeren, logs,
  dagoverzicht;
- studenten ("student"): enkel een bandje opzoeken.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app import tls
from app.config import Settings
from app.dependencies import get_db, get_settings, require_role
from app.domain.calendar import local_today
from app.models import DailyStatusModel, EmployeeModel
from app.schemas import (
    EventResponse,
    GroupPincodeRequest,
    GroupResponse,
    ManualStatusRequest,
    PairedDeviceResponse,
    PairingCodeResponse,
    WristbandStatusResponse,
)
from app.services import (
    device_service,
    employee_service,
    log_service,
    network_service,
    pairing_service,
    report_service,
)
from app.services.common import get_or_create_wristband, log_event, now_utc, read_effective_status

router = APIRouter(prefix="/api/admin", tags=["admin"])

Group = Literal["admin", "supervisor", "student"]


@router.get("/pincodes", response_model=list[GroupResponse])
def list_groups(
    db: Session = Depends(get_db), _: EmployeeModel = Depends(require_role("admin"))
) -> list[dict]:
    return employee_service.group_overview(db)


@router.put("/pincodes/{role}", response_model=GroupResponse)
def set_group_pincode(
    role: Group,
    payload: GroupPincodeRequest,
    db: Session = Depends(get_db),
    employee: EmployeeModel = Depends(require_role("admin")),
) -> GroupResponse:
    employee_service.set_group_pincode(db, role=role, pincode=payload.pincode)
    label = employee_service.GROUP_LABELS[role]
    log_event(db, event_type="PINCODE_INGESTELD", source="admin", employee_id=employee.id, detail={"groep": label})
    db.commit()
    return GroupResponse(role=role, label=label, active=True)


@router.delete("/pincodes/{role}")
def disable_group(
    role: Group,
    db: Session = Depends(get_db),
    employee: EmployeeModel = Depends(require_role("admin")),
) -> dict:
    employee_service.disable_group(db, role=role)
    log_event(
        db, event_type="GROEP_UITGEZET", source="admin", employee_id=employee.id,
        detail={"groep": employee_service.GROUP_LABELS[role]},
    )
    db.commit()
    return {"ok": True}


@router.get("/wristbands/{wristband_id}", response_model=WristbandStatusResponse)
def get_wristband_status(
    wristband_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: EmployeeModel = Depends(require_role("admin", "supervisor", "student")),
) -> WristbandStatusResponse:
    today = local_today(now_utc(), settings.tz)
    status, _ = read_effective_status(db, wristband_id, today)
    return WristbandStatusResponse(wristband_id=wristband_id, status=status)


@router.get("/wristbands/{wristband_id}/history", response_model=list[EventResponse])
def get_wristband_history(
    wristband_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: EmployeeModel = Depends(require_role("admin", "supervisor", "student")),
) -> list[dict]:
    """De geschiedenis van vandaag voor één bandje, voor wie het bandje
    opzoekt -- ook studenten, die verder geen logs mogen bekijken."""
    events = log_service.query_events(
        db, tz=settings.tz, event_date=local_today(now_utc(), settings.tz), wristband_id=wristband_id, limit=100,
    )
    names = device_service.device_names(db)
    labels = employee_service.group_labels_by_account(db)
    return [log_service.event_to_dict(event, names, labels) for event in events]


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
    role: Group | None = None,
    event_type: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    events = log_service.query_events(
        db, tz=settings.tz, event_date=event_date, wristband_id=wristband_id,
        employee_id=employee_id, role=role, event_type=event_type, limit=limit, offset=offset,
    )
    names = device_service.device_names(db)
    labels = employee_service.group_labels_by_account(db)
    return [log_service.event_to_dict(event, names, labels) for event in events]


@router.get("/logs/export.csv")
def export_logs_csv(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: EmployeeModel = Depends(require_role("admin", "supervisor")),
    event_date: date | None = None,
    wristband_id: str | None = None,
    employee_id: int | None = None,
    role: Group | None = None,
    event_type: str | None = None,
) -> Response:
    events = log_service.query_events(
        db, tz=settings.tz, event_date=event_date, wristband_id=wristband_id,
        employee_id=employee_id, role=role, event_type=event_type, limit=100_000, offset=0,
    )
    csv_content = log_service.events_to_csv(
        events, device_service.device_names(db), employee_service.group_labels_by_account(db)
    )
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


@router.get("/network")
def get_network_info(
    settings: Settings = Depends(get_settings),
    _: EmployeeModel = Depends(require_role("admin")),
) -> dict:
    return {
        "port": settings.port,
        "addresses": network_service.local_ipv4_addresses(),
        "certificate_fingerprint": tls.certificate_fingerprint(Path(settings.tls_dir)),
    }


@router.post("/pairing-codes", response_model=PairingCodeResponse)
def create_pairing_code(
    db: Session = Depends(get_db),
    employee: EmployeeModel = Depends(require_role("admin")),
) -> PairingCodeResponse:
    code = pairing_service.create_pairing_code(db, employee_id=employee.id)
    return PairingCodeResponse(code=code.code, expires_at=code.expires_at)


@router.get("/devices", response_model=list[PairedDeviceResponse])
def list_devices(
    db: Session = Depends(get_db), _: EmployeeModel = Depends(require_role("admin"))
) -> list[dict]:
    return pairing_service.list_paired_devices(db)


@router.delete("/devices/{device_id}")
def unpair_device(
    device_id: str,
    db: Session = Depends(get_db),
    employee: EmployeeModel = Depends(require_role("admin")),
) -> dict:
    pairing_service.unpair_device(db, device_id=device_id, employee_id=employee.id)
    return {"ok": True}


@router.post("/shutdown")
def shutdown_application(
    request: Request,
    db: Session = Depends(get_db),
    employee: EmployeeModel = Depends(require_role("admin")),
) -> dict:
    """Sluit de server netjes af (zelfde effect als Ctrl+C): zet uvicorn's
    eigen `should_exit`-vlag in plaats van een OS-signaal te sturen, want dat
    laatste geeft op Windows geen nette shutdown van de FastAPI-lifespan.
    Vereist dat de server via `run.py` gestart is (zie backend/run.py) —
    anders bestaat deze verwijzing niet.
    """
    server = getattr(request.app.state, "uvicorn_server", None)
    if server is None:
        raise HTTPException(
            status_code=503,
            detail="Kan niet afsluiten: de server is niet gestart via run.py.",
        )
    log_event(db, event_type="SYSTEEM_AFSLUITEN", source="admin", employee_id=employee.id)
    db.commit()
    server.should_exit = True
    return {"ok": True}
