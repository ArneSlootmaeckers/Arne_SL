"""Pincode hashing and session token generation."""
from __future__ import annotations

import secrets

import bcrypt


def hash_pincode(pincode: str) -> str:
    return bcrypt.hashpw(pincode.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_pincode(pincode: str, pincode_hash: str) -> bool:
    return bcrypt.checkpw(pincode.encode("utf-8"), pincode_hash.encode("utf-8"))


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)
