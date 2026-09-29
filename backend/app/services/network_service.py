"""Bepaalt op welk(e) IP-adres(sen) deze pc bereikbaar is op het lokale netwerk,
zodat het beheerscherm kan tonen wat er in de telefoon-app ingevuld moet worden."""
from __future__ import annotations

import ipaddress
import socket


def _primary_ipv4() -> str | None:
    # Een UDP-"connect" verstuurt niets: het laat enkel het besturingssysteem
    # kiezen via welke netwerkkaart het zou routeren -- werkt dus ook zonder
    # internet, zolang er een route naar een privéadres bestaat.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.254.254.254", 1))
            return sock.getsockname()[0]
    except OSError:
        return None


def _all_ipv4() -> list[str]:
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return []
    return [info[4][0] for info in infos]


def _is_usable(address: str) -> bool:
    try:
        ip = ipaddress.IPv4Address(address)
    except ValueError:
        return False
    return not (ip.is_loopback or ip.is_link_local or ip.is_unspecified)


def local_ipv4_addresses() -> list[str]:
    """Bruikbare LAN-adressen van deze pc, het meest waarschijnlijke eerst."""
    candidates = [_primary_ipv4(), *_all_ipv4()]
    result: list[str] = []
    for address in candidates:
        if address and _is_usable(address) and address not in result:
            result.append(address)
    return result
