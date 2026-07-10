from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import bearer_token, require_admin, require_user
from ..orchestrator import users as user_mgmt
from ..orchestrator.llm import llm_status
from ..schemas import (
    InviteAcceptRequest,
    LastVisitedUpdate,
    LoginOut,
    LoginRequest,
    UserCreate,
    UserInviteCreate,
    UserInviteResend,
    UserInviteRevoke,
    UserOut,
    UserUpdate,
)

router = APIRouter(tags=["auth-users"])


@router.get("/api/llm/status")
def api_llm_status() -> dict:
    return llm_status()


@router.post("/api/auth/login", response_model=LoginOut)
def api_login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    ok, msg, data = user_mgmt.login(db, payload.email, payload.password)
    if not ok or not data:
        raise HTTPException(status_code=401, detail=msg)
    return data


@router.post("/api/auth/logout")
def api_logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> dict:
    token = bearer_token(authorization)
    if token:
        user_mgmt.logout(db, token)
    return {"ok": True}


@router.get("/api/auth/me", response_model=UserOut)
def api_me(user=Depends(require_user)) -> dict:
    return user_mgmt.user_to_dict(user)


@router.post("/api/auth/last-visited", response_model=UserOut)
def api_last_visited(
    payload: LastVisitedUpdate,
    user=Depends(require_user),
    db: Session = Depends(get_db),
) -> dict:
    return user_mgmt.update_last_visited(db, user, payload.model_dump())


@router.get("/api/auth/invite/{token}")
def api_invite_preview(token: str, db: Session = Depends(get_db)) -> dict:
    return user_mgmt.get_invite(db, token)


@router.post("/api/auth/invite/{token}/accept", response_model=UserOut)
def api_invite_accept(token: str, payload: InviteAcceptRequest, db: Session = Depends(get_db)) -> dict:
    ok, msg, data = user_mgmt.accept_invite(db, token, payload.password)
    if not ok or not data:
        raise HTTPException(status_code=400, detail=msg)
    return data


@router.get("/api/users", response_model=list[UserOut])
def api_list_users(_admin=Depends(require_admin), db: Session = Depends(get_db)) -> list:
    return user_mgmt.list_users(db)


@router.post("/api/users", response_model=UserOut)
def api_create_user(
    payload: UserCreate,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    ok, msg, data = user_mgmt.create_user(
        db,
        user_name=payload.user_name,
        user_email=payload.user_email,
        password=payload.password,
        user_role=payload.user_role,
        user_number=payload.user_number,
    )
    if not ok or not data:
        raise HTTPException(status_code=400, detail=msg)
    return data


@router.put("/api/users/{user_id}", response_model=UserOut)
def api_update_user(
    user_id: str,
    payload: UserUpdate,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    ok, msg, data = user_mgmt.update_user(
        db,
        user_id,
        user_name=payload.user_name,
        user_role=payload.user_role,
        user_number=payload.user_number,
        password=payload.password,
        status=payload.status,
    )
    if not ok or not data:
        raise HTTPException(status_code=400, detail=msg)
    return data


@router.delete("/api/users/{user_id}")
def api_delete_user(user_id: str, admin=Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    ok, msg = user_mgmt.delete_user(db, user_id, initiated_by=admin.user_email)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}


@router.post("/api/users/invite", response_model=UserOut)
def api_invite_user(
    payload: UserInviteCreate,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    ok, msg, data = user_mgmt.invite_user(
        db,
        name=payload.user_name,
        user_email=payload.user_email,
        phone=payload.user_number,
        role=payload.user_role,
        permissions=payload.permissions,
        invited_by=admin.user_email,
    )
    if not ok or not data:
        raise HTTPException(status_code=400, detail=msg)
    return data


@router.post("/api/users/invite/resend")
def api_resend_invites(
    payload: UserInviteResend,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    return user_mgmt.resend_invites(db, payload.emails, invited_by=admin.user_email)


@router.post("/api/users/invite/revoke")
def api_revoke_invite(
    payload: UserInviteRevoke,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    ok, msg = user_mgmt.revoke_pending(db, payload.user_email)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}
