from __future__ import annotations

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
