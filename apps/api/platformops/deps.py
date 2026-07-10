from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .orchestrator import users as user_mgmt

PUBLIC_EXACT = {
    "/api/health",
    "/api/llm/status",
    "/api/auth/login",
}
PUBLIC_PREFIXES = (
    "/api/auth/invite/",
    "/assets/",
    "/docs",
    "/openapi.json",
    "/redoc",
)


def is_public_path(path: str) -> bool:
    if path in PUBLIC_EXACT:
        return True
    for p in PUBLIC_PREFIXES:
        if path.startswith(p):
            return True
    if not path.startswith("/api/") and not path.startswith("/PlatformIO/"):
        return True
    return False


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return authorization.strip() or None


def require_user(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    token = bearer_token(authorization)
    user = user_mgmt.session_user(db, token)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_admin(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    user = require_user(db=db, authorization=authorization)
    if user.user_role != "System_Admin":
        raise HTTPException(status_code=403, detail="System_Admin role required")
    return user
