#!/usr/bin/env python3
"""Transform platformops main.py into deps + routers + slim main with auth middleware."""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "apps" / "api" / "platformops"


def main() -> None:
    src_path = ROOT / "main.py"
    # Prefer backup if already transformed once
    backup = Path("/tmp/platformops_split_backup/main.py")
    src = backup.read_text() if backup.exists() else src_path.read_text()

    # --- deps.py ---
    (ROOT / "deps.py").write_text(
        '''from __future__ import annotations

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
'''
    )

    multi_idx = src.find("# ── Multiuser auth")
    if multi_idx < 0:
        multi_idx = src.find("Multiuser auth")
    if multi_idx < 0:
        raise SystemExit("multiuser marker not found in backup main.py")

    head = src[:multi_idx]
    ops_lines = head.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(ops_lines):
        line = ops_lines[i]
        if line.startswith("app = FastAPI"):
            while i < len(ops_lines) and not ops_lines[i].startswith("def _get_cluster"):
                i += 1
            continue
        if line.startswith("@app.on_event"):
            while i < len(ops_lines) and not ops_lines[i].startswith("def _get_cluster"):
                i += 1
            continue
        if line.startswith("from fastapi.middleware.cors"):
            i += 1
            continue
        if "app.add_middleware" in line:
            # skip middleware block
            while i < len(ops_lines) and ops_lines[i].strip() != ")":
                i += 1
            i += 1
            continue
        out.append(line.replace("@app.", "@router."))
        i += 1

    ops_text = "".join(out)
    ops_text = ops_text.replace(
        "from fastapi import Body, Depends, FastAPI, HTTPException",
        "from fastapi import APIRouter, Body, Depends, HTTPException",
    )
    ops_text = ops_text.replace("from fastapi import Body, Depends, FastAPI, HTTPException, Header",
                                "from fastapi import APIRouter, Body, Depends, HTTPException, Header")
    ops_text = ops_text.replace("from .db import get_db, init_db", "from .db import get_db")
    # drop unused FastAPI import leftovers
    ops_text = re.sub(r"from fastapi import FastAPI\n", "", ops_text)

    if "router = APIRouter()" not in ops_text:
        ops_text = ops_text.replace(
            "def _get_cluster",
            "router = APIRouter(tags=[\"ops\"])\n\n\ndef _get_cluster",
            1,
        )

    # Ensure APIRouter imported
    if "APIRouter" not in ops_text.split("def _get_cluster")[0]:
        ops_text = "from fastapi import APIRouter, Body, Depends, HTTPException\n" + ops_text

    routers_dir = ROOT / "routers"
    routers_dir.mkdir(exist_ok=True)
    (routers_dir / "__init__.py").write_text('"""HTTP routers for PlatformOps API."""\n')
    (routers_dir / "ops.py").write_text(ops_text)

    # auth_users router
    (routers_dir / "auth_users.py").write_text(
        '''from __future__ import annotations

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
'''
    )

    users_path = ROOT / "orchestrator" / "users.py"
    users_py = users_path.read_text()
    if "def user_to_dict" not in users_py:
        users_path.write_text(
            users_py
            + '''

def user_to_dict(user: UserInfo, *, invite_token: str = "") -> dict[str, Any]:
    """Public alias for API serialization."""
    return _user_out(user, invite_token=invite_token)
'''
        )

    (ROOT / "main.py").write_text(
        '''from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from .db import SessionLocal, init_db
from .deps import bearer_token, is_public_path
from .orchestrator import users as user_mgmt
from .orchestrator.users import ensure_bootstrap_admin
from .routers import auth_users, ops

app = FastAPI(title="PlatformOps", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuthBoundaryMiddleware(BaseHTTPMiddleware):
    """Enforce bearer auth on /api/* and /PlatformIO/* except public paths."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or is_public_path(path):
            return await call_next(request)
        if path.startswith("/api/") or path.startswith("/PlatformIO/"):
            token = bearer_token(request.headers.get("authorization"))
            db = SessionLocal()
            try:
                user = user_mgmt.session_user(db, token)
                if not user:
                    return JSONResponse(status_code=401, content={"detail": "Authentication required"})
                request.state.user = user
            finally:
                db.close()
        return await call_next(request)


app.add_middleware(AuthBoundaryMiddleware)

app.include_router(auth_users.router)
app.include_router(ops.router)


@app.on_event("startup")
def startup() -> None:
    init_db()
    db = SessionLocal()
    try:
        ensure_bootstrap_admin(db)
    finally:
        db.close()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "platformops-api"}


dist_path = "/app/dist"
if os.path.exists(dist_path):
    app.mount("/assets", StaticFiles(directory=f"{dist_path}/assets"), name="static")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
            raise HTTPException(status_code=404)
        return FileResponse(f"{dist_path}/index.html")
'''
    )

    for p in [
        ROOT / "deps.py",
        ROOT / "main.py",
        routers_dir / "auth_users.py",
        routers_dir / "ops.py",
    ]:
        try:
            ast.parse(p.read_text())
            print("AST OK", p.relative_to(ROOT.parent.parent.parent), "lines", len(p.read_text().splitlines()))
        except SyntaxError as e:
            print("SYNTAX FAIL", p, e)
            raise


if __name__ == "__main__":
    main()
