"""Demo seed script: test wristbands + a demo admin and supervisor.

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
from app.services.errors import DuplicatePincodeError

TEST_WRISTBANDS = ["TEST-001", "TEST-002", "TEST-003", "TEST-004", "TEST-005"]
DEMO_ADMIN_PINCODE = "1234"
DEMO_SUPERVISOR_PINCODE = "5678"


def main() -> None:
    settings = load_settings()
    db = create_session_factory(settings.database_url)()

    for wristband_id in TEST_WRISTBANDS:
        if db.get(WristbandModel, wristband_id) is None:
            db.add(WristbandModel(id=wristband_id, first_seen_at=now_utc()))
    db.commit()
    print(f"Testbandjes aangemaakt: {', '.join(TEST_WRISTBANDS)}")

    try:
        employee_service.create_employee(db, name="Demo Admin", pincode=DEMO_ADMIN_PINCODE, role="admin")
        print(f"Demo-admin aangemaakt (pincode: {DEMO_ADMIN_PINCODE})")
    except DuplicatePincodeError:
        print("Demo-admin niet aangemaakt: pincode is al in gebruik (waarschijnlijk al aanwezig).")

    try:
        employee_service.create_employee(
            db, name="Demo Supervisor", pincode=DEMO_SUPERVISOR_PINCODE, role="supervisor"
        )
        print(f"Demo-supervisor aangemaakt (pincode: {DEMO_SUPERVISOR_PINCODE})")
    except DuplicatePincodeError:
        print("Demo-supervisor niet aangemaakt: pincode is al in gebruik (waarschijnlijk al aanwezig).")

    db.close()
    print(
        "\nWAARSCHUWING: dit zijn demo-gegevens met vaste, publiek bekende pincodes. "
        "Gebruik dit script nooit op een productieserver."
    )


if __name__ == "__main__":
    main()
