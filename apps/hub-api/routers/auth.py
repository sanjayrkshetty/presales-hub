"""Authentication endpoints — login, refresh, logout, me."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.config import settings
from core.security import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    verify_password,
)
from db.database import get_db
from lib.dependencies import CurrentUser
from middleware.rate_limit import limiter
from models.user import RefreshToken, User

router = APIRouter(prefix="/auth", tags=["auth"])

_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15

_REFRESH_COOKIE = "refresh_token"
_COOKIE_OPTS: dict = dict(
    httponly=True,
    samesite="lax",
    secure=settings.ENVIRONMENT == "production",
    max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86_400,
)


# ── Request / Response schemas ────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    tenant_id: Optional[str]
    roles: list[str]
    is_active: bool
    permissions: list[str]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
@limiter.limit("20/minute")
def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    user = db.query(User).filter(User.email == body.email).first()

    # Check lockout before password verification to prevent timing oracle
    if user and user.locked_until:
        if datetime.utcnow() < user.locked_until:
            remaining = int((user.locked_until - datetime.utcnow()).total_seconds() // 60) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account locked. Try again in {remaining} minute(s).",
            )
        else:
            # Lockout expired — reset
            user.failed_login_count = 0
            user.locked_until = None

    if not user or not verify_password(body.password, user.hashed_password):
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= _MAX_FAILED_ATTEMPTS:
                user.locked_until = datetime.utcnow() + timedelta(minutes=_LOCKOUT_MINUTES)
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    user.failed_login_count = 0
    user.locked_until = None

    access_token = create_access_token(
        user_id=user.id, email=user.email, roles=user.roles, tenant_id=user.tenant_id,
    )
    raw_refresh, token_hash = create_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    db.add(RefreshToken(
        user_id=user.id,
        tenant_id=user.tenant_id,
        token_hash=token_hash,
        expires_at=expires_at,
    ))
    user.last_login_at = datetime.utcnow()
    db.commit()

    response.set_cookie(_REFRESH_COOKIE, raw_refresh, **_COOKIE_OPTS)
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    refresh_token: Annotated[Optional[str], Cookie()] = None,
) -> TokenResponse:
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

    token_hash = hash_refresh_token(refresh_token)
    stored = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash, RefreshToken.revoked.is_(False))
        .first()
    )

    if not stored:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked or not found")

    if stored.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user = db.get(User, stored.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or disabled")

    # Rotate: revoke old token, issue new one
    stored.revoked = True
    stored.revoked_at = datetime.utcnow()

    raw_refresh, new_hash = create_refresh_token()
    new_expires = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db.add(RefreshToken(
        user_id=user.id,
        tenant_id=user.tenant_id,
        token_hash=new_hash,
        expires_at=new_expires,
    ))
    db.commit()

    access_token = create_access_token(
        user_id=user.id, email=user.email, roles=user.roles, tenant_id=user.tenant_id,
    )
    response.set_cookie(_REFRESH_COOKIE, raw_refresh, **_COOKIE_OPTS)
    return TokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    refresh_token: Annotated[Optional[str], Cookie()] = None,
) -> None:
    if refresh_token:
        token_hash = hash_refresh_token(refresh_token)
        stored = (
            db.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash, RefreshToken.revoked.is_(False))
            .first()
        )
        if stored:
            stored.revoked = True
            stored.revoked_at = datetime.utcnow()
            db.commit()
    response.delete_cookie(_REFRESH_COOKIE)


@router.get("/me", response_model=UserResponse)
def me(current_user: CurrentUser) -> UserResponse:
    from integration_fabric.rbac.enforcer import AccessContext, RBACEnforcer
    enforcer = RBACEnforcer()
    ctx = AccessContext(
        user_id=current_user.id,
        roles=current_user.roles,
        tenant_id=current_user.tenant_id,
    )
    perms = sorted(enforcer.effective_permissions(ctx))

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        tenant_id=current_user.tenant_id,
        roles=current_user.roles,
        is_active=current_user.is_active,
        permissions=perms,
    )
