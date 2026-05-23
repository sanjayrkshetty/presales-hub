"""FastAPI injectable dependencies for authentication and authorisation."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from core.security import decode_access_token
from db.database import get_db
from models.user import User

_bearer = HTTPBearer(auto_error=False)


def _extract_token(
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
    access_token: Annotated[Optional[str], Cookie()] = None,
) -> str:
    """Accept token from Authorization Bearer header OR access_token cookie."""
    raw: Optional[str] = None
    if creds and creds.credentials:
        raw = creds.credentials
    elif access_token:
        raw = access_token
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return raw


def get_current_user(
    token: Annotated[str, Depends(_extract_token)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub", "")
        if not user_id:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise credentials_exc
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(permission: str):
    """Dependency factory — raises 403 if current user lacks the permission."""
    from integration_fabric.rbac.enforcer import AccessContext, RBACEnforcer
    enforcer = RBACEnforcer()

    def _check(user: CurrentUser) -> User:
        ctx = AccessContext(user_id=user.id, roles=user.roles, tenant_id=user.tenant_id)
        if not enforcer.has_permission(ctx, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission}",
            )
        return user

    return Depends(_check)
