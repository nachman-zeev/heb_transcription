from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models import Tenant, User
from app.schemas import (
    AuthResponse,
    BootstrapRequest,
    GenericMessage,
    LoginRequest,
    MeResponse,
)
from app.security import create_password_hash, issue_access_token, revoke_token, verify_password


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/bootstrap", response_model=GenericMessage)
def bootstrap(payload: BootstrapRequest, db: Session = Depends(get_db)) -> GenericMessage:
    existing_users = db.scalar(select(User.id).limit(1))
    if existing_users:
        raise HTTPException(status_code=400, detail="Bootstrap already completed")

    tenant = Tenant(name=payload.tenant_name)
    db.add(tenant)
    db.flush()

    salt, password_hash = create_password_hash(payload.password)
    user = User(
        tenant_id=tenant.id,
        email=payload.email.lower().strip(),
        password_hash=password_hash,
        password_salt=salt,
    )
    db.add(user)
    db.commit()

    return GenericMessage(message="Bootstrap completed")


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    tenant = db.scalar(select(Tenant).where(Tenant.name == payload.tenant_name.strip()))
    if not tenant:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user = db.scalar(
        select(User).where(
            User.tenant_id == tenant.id,
            User.email == payload.email.lower().strip(),
        )
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(payload.password, user.password_salt, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token, expires_at = issue_access_token(db, user)
    return AuthResponse(
        access_token=token,
        expires_at=expires_at,
        tenant_id=user.tenant_id,
        user_id=user.id,
    )


@router.post("/logout", response_model=GenericMessage)
def logout(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> GenericMessage:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        revoke_token(db, token)
    return GenericMessage(message="Logged out")


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MeResponse:
    tenant = db.get(Tenant, user.tenant_id)
    return MeResponse(
        tenant_id=user.tenant_id,
        tenant_name=tenant.name if tenant else "unknown",
        user_id=user.id,
        email=user.email,
    )
