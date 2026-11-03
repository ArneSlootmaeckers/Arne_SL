"""Stelt de pincode van de beheerder in, rechtstreeks in de database.

Pincodes beheren gaat normaal via het beheerscherm (tabblad "Pincodes"),
maar daarvoor moet je al als beheerder kunnen inloggen. Dit script is er
voor de allereerste keer, en om de beheerder weer binnen te laten als
niemand de pincode nog weet.

Interactief: python3 create_admin.py
Niet-interactief (bv. vanuit de Windows-installer):
python3 create_admin.py --pincode "..."
"""
from __future__ import annotations

import argparse
import getpass
import sys

from app.config import load_settings
from app.database import create_session_factory
from app.services import employee_service
from app.services.employee_service import MIN_PINCODE_LENGTH
from app.services.errors import DuplicatePincodeError


def main() -> None:
    parser = argparse.ArgumentParser(description="Stel de pincode van de beheerder in.")
    parser.add_argument(
        "--pincode", help=f"Pincode, min. {MIN_PINCODE_LENGTH} tekens (anders interactief gevraagd)"
    )
    args = parser.parse_args()

    settings = load_settings()
    db = create_session_factory(settings.database_url)()

    if args.pincode is not None:
        pincode = args.pincode.strip()
    else:
        pincode = getpass.getpass(f"Pincode van de beheerder (min. {MIN_PINCODE_LENGTH} tekens): ").strip()
        pincode_confirm = getpass.getpass("Herhaal pincode: ").strip()
        if pincode != pincode_confirm:
            print("Pincodes komen niet overeen.")
            sys.exit(1)
    if len(pincode) < MIN_PINCODE_LENGTH:
        print(f"Pincode moet minstens {MIN_PINCODE_LENGTH} tekens lang zijn.")
        sys.exit(1)

    try:
        employee_service.set_group_pincode(db, role="admin", pincode=pincode)
    except DuplicatePincodeError as exc:
        print(f"Fout: {exc}")
        sys.exit(1)
    finally:
        db.close()

    print("Pincode van de beheerder ingesteld. Log hiermee in op het beheerscherm.")


if __name__ == "__main__":
    main()
