"""Command-line script to create the very first admin account.

Employee management normally goes through the admin screen, but creating
an employee there requires being logged in as an admin already — so the
first one has to be created directly against the database.

Interactief: python3 create_admin.py
Niet-interactief (bv. vanuit de Windows-installer): python3 create_admin.py
--name "..." --pincode "..."
"""
from __future__ import annotations

import argparse
import getpass
import sys

from app.config import load_settings
from app.database import create_session_factory
from app.services import employee_service
from app.services.errors import DuplicatePincodeError


def main() -> None:
    parser = argparse.ArgumentParser(description="Maak de allereerste admin aan.")
    parser.add_argument("--name", help="Naam van de nieuwe admin (anders interactief gevraagd)")
    parser.add_argument("--pincode", help="Pincode, min. 4 tekens (anders interactief gevraagd)")
    args = parser.parse_args()

    settings = load_settings()
    db = create_session_factory(settings.database_url)()

    name = (args.name or input("Naam van de nieuwe admin: ")).strip()
    if not name:
        print("Naam mag niet leeg zijn.")
        sys.exit(1)

    if args.pincode is not None:
        pincode = args.pincode.strip()
    else:
        pincode = getpass.getpass("Pincode (min. 4 tekens): ").strip()
        pincode_confirm = getpass.getpass("Herhaal pincode: ").strip()
        if pincode != pincode_confirm:
            print("Pincodes komen niet overeen.")
            sys.exit(1)
    if len(pincode) < 4:
        print("Pincode moet minstens 4 tekens lang zijn.")
        sys.exit(1)

    try:
        employee = employee_service.create_employee(db, name=name, pincode=pincode, role="admin")
    except DuplicatePincodeError as exc:
        print(f"Fout: {exc}")
        sys.exit(1)
    finally:
        db.close()

    print(f"Admin '{employee.name}' aangemaakt (id={employee.id}). Log hiermee in op /admin/.")


if __name__ == "__main__":
    main()
