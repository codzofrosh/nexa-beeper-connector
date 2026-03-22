"""Authentication helpers for the sidecar service."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets


PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 200_000
SESSION_TOKEN_BYTES = 32


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256."""
    if not password:
        raise ValueError("Password cannot be empty")

    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return (
        f"pbkdf2_{PBKDF2_ALGORITHM}$"
        f"{PBKDF2_ITERATIONS}$"
        f"{base64.b64encode(salt).decode('ascii')}$"
        f"{base64.b64encode(derived).decode('ascii')}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored PBKDF2 hash."""
    try:
        scheme, iterations, salt_b64, hash_b64 = stored_hash.split("$", 3)
    except ValueError:
        return False

    if scheme != f"pbkdf2_{PBKDF2_ALGORITHM}":
        return False

    derived = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        base64.b64decode(salt_b64),
        int(iterations),
    )
    return hmac.compare_digest(
        base64.b64encode(derived).decode("ascii"),
        hash_b64,
    )


def create_session_token() -> str:
    """Create a random bearer-style session token."""
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)
