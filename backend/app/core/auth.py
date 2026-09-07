"""Secure authentication utilities for FraudLens."""
from __future__ import annotations

import logging
import secrets
import time
from typing import Optional

from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# Password hashing context using bcrypt.
#
# NOTE: keep bcrypt pinned to 4.0.x in backend/requirements.txt. passlib 1.7.4
# (last release) is incompatible with bcrypt >= 4.1: passlib cannot read the
# bcrypt version ("(trapped) error reading bcrypt version") and bcrypt >= 4.1
# raises "password cannot be longer than 72 bytes" instead of truncating the
# way passlib expects. See backend/requirements.txt.
#
# Registration validates the 72-byte bcrypt limit up front (app/api/v1/auth.py)
# so long passwords are rejected rather than silently truncated.
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def generate_token() -> str:
    """Generate a secure random token."""
    return secrets.token_hex(32)


# In-memory token store: token -> session data
# In production, use Redis or database sessions
_sessions: dict[str, dict] = {}


def create_session(token: str, user_id: str, email: str, name: str, role: str) -> None:
    """Store a session token."""
    _sessions[token] = {
        "user_id": user_id,
        "email": email,
        "name": name,
        "role": role,
        "created_at": time.time(),
    }


def get_session(token: str) -> Optional[dict]:
    """Get session data from token."""
    return _sessions.get(token)


def invalidate_session(token: str) -> bool:
    """Remove a session token. Returns True if it existed."""
    return _sessions.pop(token, None) is not None
