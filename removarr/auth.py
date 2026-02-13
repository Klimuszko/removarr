from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from .models import AdminUser, SessionToken

PBKDF2_ITERS = 210_000
SESSION_DAYS = 30
COOKIE_NAME = "removarr_session"

def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")

def _b64d(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERS, dklen=32)
    return f"pbkdf2_sha256${PBKDF2_ITERS}${_b64(salt)}${_b64(dk)}"

def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters_s, salt_s, dk_s = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iters = int(iters_s)
        salt = _b64d(salt_s)
        dk_expected = _b64d(dk_s)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters, dklen=len(dk_expected))
        return hmac.compare_digest(dk, dk_expected)
    except Exception:
        return False

def has_admin(db: Session) -> bool:
    return db.execute(select(AdminUser.id)).first() is not None

def create_admin(db: Session, username: str, password: str) -> None:
    if has_admin(db):
        raise ValueError("Admin already exists")
    user = AdminUser(username=username, password_hash=hash_password(password))
    db.add(user)
    db.commit()

def login(db: Session, username: str, password: str) -> str:
    row = db.execute(select(AdminUser).where(AdminUser.username == username)).scalars().first()
    if not row or not verify_password(password, row.password_hash):
        raise ValueError("Invalid credentials")

    token = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=SESSION_DAYS)
    db.add(SessionToken(token=token, expires_at=exp))
    db.commit()
    return token

def logout(db: Session, token: str) -> None:
    db.execute(delete(SessionToken).where(SessionToken.token == token))
    db.commit()

def validate_session(db: Session, token: str) -> bool:
    now = datetime.now(timezone.utc)
    row = db.execute(select(SessionToken).where(SessionToken.token == token)).scalars().first()
    if not row:
        return False
    if row.expires_at <= now:
        db.execute(delete(SessionToken).where(SessionToken.token == token))
        db.commit()
        return False
    return True
