"""Het eigen https-certificaat van de server.

Bij de eerste start maakt de server zelf een certificaat aan (geen
certificaatautoriteit of internet nodig) en bewaart het in `tls_dir`. De
Android-app vertrouwt het certificaat dat hij de eerste keer ziet en
weigert daarna elk ander ("pinnen"): een toestel in het netwerk dat zich
voordoet als de server, wordt zo niet vertrouwd. Daarom moet dit bestand
blijven bestaan, ook bij een herinstallatie.

Het certificaat hangt niet aan het IP-adres van de pc: de app vergelijkt
het certificaat zelf, dus een nieuw IP-adres via DHCP verandert niets.
"""
from __future__ import annotations

import datetime
import hashlib
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

CERT_FILENAME = "server.crt"
KEY_FILENAME = "server.key"
_VALIDITY_DAYS = 20 * 365


def ensure_certificate(tls_dir: Path) -> tuple[Path, Path]:
    """Geeft (certificaat, sleutel); maakt ze eerst aan als ze nog niet bestaan."""
    cert_path = tls_dir / CERT_FILENAME
    key_path = tls_dir / KEY_FILENAME
    if cert_path.is_file() and key_path.is_file():
        return cert_path, key_path

    tls_dir.mkdir(parents=True, exist_ok=True)
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Toelatingssysteem Sparkx")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=_VALIDITY_DAYS))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path


def certificate_fingerprint(tls_dir: Path) -> str | None:
    """Korte vingerafdruk (bv. "AB12 CD34 EF56 7890"): de eerste 8 bytes van
    de SHA-256 van het certificaat. De Android-app toont dezelfde code bij
    Instellingen, zodat je kan nakijken dat de telefoon de echte server
    vertrouwt. None als er (nog) geen certificaat is."""
    cert_path = tls_dir / CERT_FILENAME
    if not cert_path.is_file():
        return None
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    digest = hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest().upper()
    return " ".join(digest[i : i + 4] for i in range(0, 16, 4))
