from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tenant, User
from app.security import resolve_token_user


BearerHeader = Header(default=None, alias="Authorization")


def extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token format")
    return parts[1].strip()


def get_user_from_token_or_401(db: Session, token: str) -> User:
    user = resolve_token_user(db, token)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user


def get_current_user(
    authorization: str | None = BearerHeader,
    db: Session = Depends(get_db),
) -> User:
    token = extract_bearer_token(authorization)
    return get_user_from_token_or_401(db, token)


def get_current_tenant(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Tenant:
    tenant = db.get(Tenant, user.tenant_id)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant is inactive")
    return tenant


def get_current_user_from_token_query(
    token: str = Query(...),
    db: Session = Depends(get_db),
) -> User:
    return get_user_from_token_or_401(db, token)
