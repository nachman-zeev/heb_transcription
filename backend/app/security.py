from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ApiToken, User


def _sha256_hex(value: str) -> str:
    pepper = get_settings().token_hash_pepper
    material = value if not pepper else f"{value}:{pepper}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def create_password_hash(password: str) -> tuple[str, str]:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return salt, digest.hex()


def verify_password(password: str, salt: str, password_hash: str) -> bool:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return hmac.compare_digest(digest.hex(), password_hash)


def issue_access_token(db: Session, user: User) -> tuple[str, datetime]:
    settings = get_settings()
    raw_token = secrets.token_urlsafe(48)
    token_hash = _sha256_hex(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.token_ttl_hours)

    token = ApiToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at)
    db.add(token)
    db.commit()
    return raw_token, expires_at


def revoke_token(db: Session, raw_token: str) -> None:
    token_hash = _sha256_hex(raw_token)
    token = db.scalar(select(ApiToken).where(ApiToken.token_hash == token_hash, ApiToken.revoked_at.is_(None)))
    if token:
        token.revoked_at = datetime.now(timezone.utc)
        db.add(token)
        db.commit()


def resolve_token_user(db: Session, raw_token: str) -> User | None:
    token_hash = _sha256_hex(raw_token)
    now = datetime.now(timezone.utc)
    token = db.scalar(
        select(ApiToken).where(
            ApiToken.token_hash == token_hash,
            ApiToken.revoked_at.is_(None),
            ApiToken.expires_at > now,
        )
    )
    if token is None:
        return None
    return db.get(User, token.user_id)
