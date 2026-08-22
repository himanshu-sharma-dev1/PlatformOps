from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import bearer_token, require_admin, require_user
from ..orchestrator import users as user_mgmt
from ..orchestrator import record_event
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
    record_event(
        db,
        category="auth",
        message=f"User {data['user']['user_email']} signed in",
        metadata={"actor": data["user"]["user_email"], "action": "login", "outcome": "success"},
    )
    return data


@router.post("/api/auth/logout")
def api_logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> dict:
    token = bearer_token(authorization)
    if token:
        user = user_mgmt.session_user(db, token)
        user_mgmt.logout(db, token)
        record_event(
            db,
            category="auth",
            message="User signed out",
            metadata={
                "actor": user.user_email if user else "unknown",
                "action": "logout",
                "outcome": "success",
            },
        )
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
    updated = user_mgmt.update_last_visited(db, user, payload.model_dump())
    record_event(
        db,
        category="auth",
        message="User navigation state updated",
        metadata={"actor": user.user_email, "action": "last_visited", "outcome": "success"},
    )
    return updated


@router.get("/api/auth/invite/{token}")
def api_invite_preview(token: str, db: Session = Depends(get_db)) -> dict:
    return user_mgmt.get_invite(db, token)


@router.post("/api/auth/invite/{token}/accept", response_model=LoginOut)
def api_invite_accept(token: str, payload: InviteAcceptRequest, db: Session = Depends(get_db)) -> dict:
    ok, msg, data = user_mgmt.accept_invite(db, token, payload.password, payload.full_name)
    if not ok or not data:
        raise HTTPException(status_code=400, detail=msg)
    record_event(
        db,
        category="users",
        message=f"Invitation accepted for {data['user_email']}",
        metadata={"actor": data["user_email"], "action": "invite_accept", "outcome": "success"},
    )
    return {
        "token": data["token"],
        "expires_at": data["expires_at"],
        "user": data["user"],
    }


@router.get("/api/users", response_model=list[UserOut])
def api_list_users(_admin=Depends(require_admin), db: Session = Depends(get_db)) -> list:
    return user_mgmt.list_users(db)


@router.post("/api/users", response_model=UserOut)
def api_create_user(
    payload: UserCreate,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    ok, msg, data = user_mgmt.create_user(
        db,
        user_name=payload.user_name,
        user_email=payload.user_email,
        password=payload.password,
        user_role=payload.user_role,
        user_number=payload.user_number,
        permissions=payload.permissions,
    )
    if not ok or not data:
        raise HTTPException(status_code=400, detail=msg)
    record_event(
        db,
        category="users",
        message=f"User {data['user_email']} created",
        metadata={
            "actor": admin.user_email,
            "target": data["user_email"],
            "action": "create",
            "outcome": "success",
        },
    )
    return data


@router.put("/api/users/{user_id}", response_model=UserOut)
def api_update_user(
    user_id: str,
    payload: UserUpdate,
    admin=Depends(require_admin),
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
        permissions=payload.permissions,
    )
    if not ok or not data:
        raise HTTPException(status_code=400, detail=msg)
    record_event(
        db,
        category="users",
        message=f"User {data['user_email']} updated",
        metadata={
            "actor": admin.user_email,
            "target": data["user_email"],
            "action": "update",
            "outcome": "success",
            "fields": sorted(payload.model_fields_set - {"password"}),
            "password_changed": "password" in payload.model_fields_set,
        },
    )
    return data


@router.delete("/api/users/{user_id}")
def api_delete_user(user_id: str, admin=Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    ok, msg = user_mgmt.delete_user(db, user_id, initiated_by=admin.user_email)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    record_event(
        db,
        category="users",
        message=f"User {user_id} deleted",
        metadata={
            "actor": admin.user_email,
            "target_id": user_id,
            "action": "delete",
            "outcome": "success",
        },
    )
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
    record_event(
        db,
        category="users",
        message=f"Invitation created for {data['user_email']}",
        metadata={
            "actor": admin.user_email,
            "target": data["user_email"],
            "action": "invite",
            "outcome": "success",
        },
    )
    return data


@router.post("/api/users/invite/resend")
def api_resend_invites(
    payload: UserInviteResend,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    result = user_mgmt.resend_invites(db, payload.emails, invited_by=admin.user_email)
    record_event(
        db,
        category="users",
        message="Pending invitations resent",
        metadata={
            "actor": admin.user_email,
            "action": "invite_resend",
            "outcome": "success",
            "requested_count": len(payload.emails),
            **result,
        },
    )
    return result


@router.post("/api/users/invite/revoke")
def api_revoke_invite(
    payload: UserInviteRevoke,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    ok, msg = user_mgmt.revoke_pending(db, payload.user_email)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    record_event(
        db,
        category="users",
        message=f"Invitation revoked for {payload.user_email}",
        metadata={
            "actor": admin.user_email,
            "target": payload.user_email,
            "action": "invite_revoke",
            "outcome": "success",
        },
    )
    return {"ok": True, "message": msg}
