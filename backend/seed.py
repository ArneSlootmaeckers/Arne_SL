"""Demo seed script: test wristbands + demo pincodes for the three groups.

For demo/development only — never run this against a production database:
the pincodes below are fixed and printed to the console.

Run from the backend/ directory: python3 seed.py
"""
from __future__ import annotations

from app.config import load_settings
from app.database import create_session_factory
from app.models import WristbandModel
from app.services import employee_service
from app.services.common import now_utc
from app.services.employee_service import GROUP_LABELS
from app.services.errors import DuplicatePincodeError

TEST_WRISTBANDS = ["TEST-001", "TEST-002", "TEST-003", "TEST-004", "TEST-005"]
# Eén pincode per groep (zie employee_service).
DEMO_PINCODES = {"admin": "123456", "supervisor": "567890", "student": "135790"}


def main() -> None:
    settings = load_settings()
    db = create_session_factory(settings.database_url)()

    for wristband_id in TEST_WRISTBANDS:
        if db.get(WristbandModel, wristband_id) is None:
            db.add(WristbandModel(id=wristband_id, first_seen_at=now_utc()))
    db.commit()
    print(f"Testbandjes aangemaakt: {', '.join(TEST_WRISTBANDS)}")

    for role, pincode in DEMO_PINCODES.items():
        try:
            employee_service.set_group_pincode(db, role=role, pincode=pincode)
            print(f"Demo-pincode voor {GROUP_LABELS[role]}: {pincode}")
        except DuplicatePincodeError:
            print(f"Demo-pincode voor {GROUP_LABELS[role]} niet ingesteld: al in gebruik door een andere groep.")

    db.close()
    print(
        "\nWAARSCHUWING: dit zijn demo-gegevens met vaste, publiek bekende pincodes. "
        "Gebruik dit script nooit op een productieserver."
    )


if __name__ == "__main__":
    main()
