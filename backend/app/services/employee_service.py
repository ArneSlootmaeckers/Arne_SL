"""Pincodes per groep. Het systeem bewaart geen personeelsgegevens: er zijn
drie groepen (beheerder, vaste medewerkers, studenten), elk met één eigen
pincode, en de "naam" van een account is gewoon het label van die groep.
Wat elke groep mag, staat in de API-laag (zie app/dependencies.py
require_role en app/api/routes_admin.py).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EmployeeModel
from app.security import hash_pincode, verify_pincode
from app.services.common import now_utc
from app.services.errors import DuplicatePincodeError, PermissionDeniedError, WeakPincodeError

# Rolcodes zoals ze in de database staan ("supervisor" = vaste medewerkers,
# zo blijven bestaande installaties werken), met het label dat overal getoond
# wordt. In deze volgorde op het beheerscherm.
GROUP_LABELS = {
    "admin": "Beheerder",
    "supervisor": "Vaste medewerkers",
    "student": "Studenten",
}
VALID_ROLES = set(GROUP_LABELS)
# Samen met de blokkering na 5 foute pogingen (zie rate_limit) maakt dit
# raden onbegonnen werk. Bestaande, kortere pincodes blijven werken tot ze
# gewijzigd worden.
MIN_PINCODE_LENGTH = 6


def _check_role(role: str) -> None:
    if role not in VALID_ROLES:
        raise ValueError(f"Ongeldige groep: {role}")


def _check_pincode_length(pincode: str) -> None:
    if len(pincode) < MIN_PINCODE_LENGTH:
        raise WeakPincodeError(f"Een pincode moet minstens {MIN_PINCODE_LENGTH} tekens lang zijn.")


def _active_accounts(db: Session, role: str) -> list[EmployeeModel]:
    stmt = select(EmployeeModel).where(EmployeeModel.role == role, EmployeeModel.active.is_(True))
    return list(db.execute(stmt.order_by(EmployeeModel.id)).scalars())


def _pincode_used_by_other_group(db: Session, pincode: str, role: str) -> bool:
    # Twee groepen met dezelfde pincode: dan is bij het inloggen niet te
    # zeggen welke groep het is.
    stmt = select(EmployeeModel).where(EmployeeModel.active.is_(True), EmployeeModel.role != role)
    return any(verify_pincode(pincode, employee.pincode_hash) for employee in db.execute(stmt).scalars())


def group_overview(db: Session) -> list[dict]:
    return [
        {"role": role, "label": label, "active": bool(_active_accounts(db, role))}
        for role, label in GROUP_LABELS.items()
    ]


def set_group_pincode(db: Session, *, role: str, pincode: str) -> EmployeeModel:
    """Stelt de (enige) pincode van een groep in. Oudere accounts van die
    groep (bv. persoonlijke pincodes van vroeger) werken daarna niet meer."""
    _check_role(role)
    _check_pincode_length(pincode)
    if _pincode_used_by_other_group(db, pincode, role):
        raise DuplicatePincodeError("Deze pincode is al in gebruik door een andere groep.")

    accounts = _active_accounts(db, role)
    now = now_utc()
    if accounts:
        account = accounts[0]
        for older in accounts[1:]:
            older.active = False
            older.revoked_at = now
    else:
        account = EmployeeModel(role=role, active=True, created_at=now)
        db.add(account)
    account.name = GROUP_LABELS[role]
    account.pincode_hash = hash_pincode(pincode)
    db.commit()
    return account


def disable_group(db: Session, *, role: str) -> None:
    """Niemand van deze groep kan nog inloggen, tot er een nieuwe pincode is."""
    _check_role(role)
    if role == "admin":
        # Anders kan niemand er nog in om het terug aan te zetten.
        raise PermissionDeniedError("De beheerder kan niet uitgezet worden.")
    now = now_utc()
    for account in _active_accounts(db, role):
        account.active = False
        account.revoked_at = now
    db.commit()


def anonymise_accounts(db: Session) -> int:
    """Vervangt namen van vroegere, persoonlijke accounts door het label van
    hun groep, zodat er geen personeelsgegevens in de database blijven.
    Draait bij elke start; doet niets meer zodra alles al een label heeft."""
    changed = 0
    for account in db.execute(select(EmployeeModel)).scalars():
        label = GROUP_LABELS.get(account.role, "Onbekende groep")
        if account.name != label:
            account.name = label
            changed += 1
    if changed:
        db.commit()
    return changed


def group_labels_by_account(db: Session) -> dict[int, str]:
    """{account-id: groepslabel}, om in de logs te tonen welke groep iets deed."""
    return {
        account.id: GROUP_LABELS.get(account.role, account.role)
        for account in db.execute(select(EmployeeModel)).scalars()
    }
