"""Multiuser system distilled from cPlatform UserMgmnt (roles, invite, session)."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import smtplib
import uuid
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuthSession, InviteToken, UserInfo
from ..settings import settings

ROLES = ("System_Admin", "Operational", "Management")
STATUSES = ("active", "pending", "disabled")


def _send_invite_email(*, recipient: str, recipient_name: str, token: str) -> tuple[bool, str]:
    """Deliver an invitation when SMTP is configured; never expose credentials."""
    if not settings.smtp_host:
        return False, "SMTP is not configured"
    invite_url = f"{settings.public_base_url.rstrip('/')}/#/invite/{token}"
    message = EmailMessage()
    message["Subject"] = "PlatformOps invitation"
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message.set_content(
        f"Hello {recipient_name or recipient},\n\n"
        f"You have been invited to PlatformOps. Activate your account here:\n{invite_url}\n\n"
        "If you did not expect this invitation, ignore this message."
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
            if settings.smtp_starttls:
                client.starttls()
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password)
            client.send_message(message)
        return True, "Invitation email sent"
    except Exception as exc:
        return False, f"Invitation created but email delivery failed: {exc}"


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    if not stored or not password:
        return False
    try:
        algo, salt, digest = stored.split("$", 2)
        if algo != "pbkdf2_sha256":
            return False
        check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()
        return hmac.compare_digest(check, digest)
    except Exception:
        return False


def _new_user_id() -> str:
    return uuid.uuid4().hex[:8]


def _session_info_dict(user: UserInfo) -> dict[str, Any]:
    try:
        return json.loads(user.session_info or "{}")
    except Exception:
        return {}


def _permissions_json_list(value: str | None) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        parsed = []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item).strip()]


def _permissions_list(user: UserInfo) -> list[str]:
    return _permissions_json_list(user.permissions)


def _user_out(user: UserInfo, *, invite_token: str = "", password_never: bool = True) -> dict[str, Any]:
    last_login = user.last_login_at.strftime("%d-%b-%y %H:%M") if user.last_login_at else "—"
    last_login_ts = int(user.last_login_at.timestamp()) if user.last_login_at else 0
    return {
        "user_id": user.user_id,
        "user_name": user.user_name or "",
        "user_email": user.user_email,
        "user_role": user.user_role,
        "user_number": user.user_number or "",
        "permissions": _permissions_list(user),
        "status": user.status,
        "login_count": user.login_count or 0,
        "last_login": last_login,
        "last_login_ts": last_login_ts,
        "created_at": user.created_at.isoformat() if user.created_at else "",
        "session_info": _session_info_dict(user),
        "invite_token": invite_token,
        "invite_link": (
            f"{settings.public_base_url.rstrip('/')}/#/invite/{invite_token}" if invite_token else ""
        ),
    }


def ensure_bootstrap_admin(db: Session) -> UserInfo | None:
    """Create the bootstrap administrator only when no administrator exists.

    Startup must never reset a real operator's password, role, name, or status.
    Credential rotation belongs to the authenticated user-management workflow.
    """
    email = (settings.bootstrap_admin_email or "admin").strip().lower()
    name = (settings.bootstrap_admin_name or "admin").strip() or "admin"
    password = settings.bootstrap_admin_password or "admin"

    administrator = db.scalar(select(UserInfo).where(UserInfo.user_role == "System_Admin"))
    if administrator:
        return administrator

    identity_owner = get_user_by_email(db, email) or db.scalar(
        select(UserInfo).where(UserInfo.user_name == name)
    )
    if identity_owner:
        raise RuntimeError(
            "Bootstrap administrator identity is already used by a non-admin account; "
            "configure a unique PLATFORMOPS_BOOTSTRAP_ADMIN_EMAIL."
        )

    user = UserInfo(
        user_id=_new_user_id(),
        user_email=email,
        user_name=name,
        user_role="System_Admin",
        user_number="",
        status="active",
        password_hash=_hash_password(password),
        login_count=0,
        session_info="{}",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session) -> list[dict[str, Any]]:
    users = db.scalars(select(UserInfo).order_by(UserInfo.created_at.desc())).all()
    out: list[dict[str, Any]] = []
    for user in users:
        token = ""
        if user.status == "pending":
            invite = db.scalar(
                select(InviteToken)
                .where(
                    InviteToken.user_email == user.user_email,
                    InviteToken.is_used == 0,
                    InviteToken.is_revoked == 0,
                )
                .order_by(InviteToken.created_at.desc())
            )
            if invite:
                token = invite.token
        out.append(_user_out(user, invite_token=token))
    return out


def get_user_by_email(db: Session, email: str) -> UserInfo | None:
    return db.scalar(select(UserInfo).where(UserInfo.user_email == email.strip().lower()))


def get_user_by_login(db: Session, identifier: str) -> UserInfo | None:
    """Resolve login by email or username (case-insensitive)."""
    ident = (identifier or "").strip()
    if not ident:
        return None
    lower = ident.lower()
    user = get_user_by_email(db, lower)
    if user:
        return user
    # username match
    users = db.scalars(select(UserInfo)).all()
    for u in users:
        if (u.user_name or "").strip().lower() == lower:
            return u
    return None


def get_user_by_id(db: Session, user_id: str) -> UserInfo | None:
    return db.scalar(select(UserInfo).where(UserInfo.user_id == user_id))


def create_user(
    db: Session,
    *,
    user_name: str,
    user_email: str,
    password: str,
    user_role: str,
    user_number: str = "",
    permissions: list[str] | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    email = user_email.strip().lower()
    role = user_role if user_role in ROLES else "Operational"
    if not email or "@" not in email:
        return False, "Invalid email address.", None
    if get_user_by_email(db, email):
        return False, "User email already exists.", None
    count = len(db.scalars(select(UserInfo)).all())
    if count >= int(settings.max_users or 50):
        return False, "Maximum user count reached.", None
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters.", None
    user = UserInfo(
        user_id=_new_user_id(),
        user_email=email,
        user_name=user_name.strip() or email.split("@")[0],
        user_role=role,
        user_number=(user_number or "").strip(),
        permissions=json.dumps(permissions or []),
        status="active",
        password_hash=_hash_password(password),
        login_count=0,
        session_info="{}",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return True, f"User {user.user_name} added successfully.", _user_out(user)


def update_user(
    db: Session,
    user_id: str,
    *,
    user_name: str | None = None,
    user_role: str | None = None,
    user_number: str | None = None,
    password: str | None = None,
    status: str | None = None,
    permissions: list[str] | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    user = get_user_by_id(db, user_id)
    if not user:
        return False, "User does not exist.", None
    if user_name is not None:
        user.user_name = user_name.strip()
    if user_role is not None and user_role in ROLES:
        user.user_role = user_role
    if user_number is not None:
        user.user_number = user_number.strip()
    if status is not None and status in STATUSES:
        user.status = status
    if permissions is not None:
        user.permissions = json.dumps([str(item) for item in permissions if str(item).strip()])
    if password:
        if len(password) < 8:
            return False, "Password must be at least 8 characters.", None
        user.password_hash = _hash_password(password)
    db.commit()
    db.refresh(user)
    return True, f"User {user.user_name} updated.", _user_out(user)


def delete_user(db: Session, user_id: str, *, initiated_by: str = "") -> tuple[bool, str]:
    user = get_user_by_id(db, user_id)
    if not user:
        return False, "User does not exist."
    if user.user_role == "System_Admin":
        admins = [
            u
            for u in db.scalars(select(UserInfo).where(UserInfo.user_role == "System_Admin")).all()
            if u.status == "active"
        ]
        if len(admins) <= 1:
            return False, "Cannot delete the last System_Admin."
    email = user.user_email
    # purge sessions + invites
    for sess in db.scalars(select(AuthSession).where(AuthSession.user_id == user.user_id)).all():
        db.delete(sess)
    for inv in db.scalars(select(InviteToken).where(InviteToken.user_email == email)).all():
        db.delete(inv)
    db.delete(user)
    db.commit()
    return True, f'User "{email}" deleted successfully.'


def invite_user(
    db: Session,
    *,
    name: str,
    user_email: str,
    phone: str = "",
    role: str = "Operational",
    permissions: list[str] | None = None,
    invited_by: str = "system",
) -> tuple[bool, str, dict[str, Any] | None]:
    email = user_email.strip().lower()
    role = role if role in ROLES else "Operational"
    if not email or "@" not in email:
        return False, "Invalid email.", None
    existing = get_user_by_email(db, email)
    if existing and existing.status == "active":
        return False, "Active user already exists for this email.", None
    if existing and existing.status == "pending":
        # refresh invite
        for inv in db.scalars(
            select(InviteToken).where(
                InviteToken.user_email == email,
                InviteToken.is_used == 0,
                InviteToken.is_revoked == 0,
            )
        ).all():
            inv.is_revoked = 1
    else:
        count = len(db.scalars(select(UserInfo)).all())
        if count >= int(settings.max_users or 50):
            return False, "Maximum user count reached.", None
        existing = UserInfo(
            user_id=_new_user_id(),
            user_email=email,
            user_name=name.strip() or email.split("@")[0],
            user_role=role,
            user_number=(phone or "").strip(),
            permissions=json.dumps(permissions or []),
            status="pending",
            password_hash="",
            login_count=0,
            session_info="{}",
        )
        db.add(existing)
        db.flush()

    if permissions is not None:
        existing.permissions = json.dumps([str(item) for item in permissions if str(item).strip()])

    token = secrets.token_urlsafe(24)
    invite = InviteToken(
        token=token,
        user_name=existing.user_name,
        user_email=email,
        user_role=role,
        user_number=(phone or existing.user_number or "").strip(),
        permissions=json.dumps(permissions or []),
        invited_by=invited_by,
        is_used=0,
        is_revoked=0,
    )
    db.add(invite)
    db.commit()
    db.refresh(existing)
    delivered, delivery_message = _send_invite_email(
        recipient=email,
        recipient_name=existing.user_name,
        token=token,
    )
    if settings.smtp_host and not delivered:
        return True, delivery_message, _user_out(existing, invite_token=token)
    message = f"Invite created for {email}."
    if delivered:
        message = f"Invite created and emailed to {email}."
    return True, message, _user_out(existing, invite_token=token)


def resend_invites(db: Session, emails: list[str], invited_by: str) -> dict[str, int]:
    sent = 0
    skipped = 0
    for raw in emails:
        email = raw.strip().lower()
        user = get_user_by_email(db, email)
        if not user or user.status != "pending":
            skipped += 1
            continue
        ok, _, _ = invite_user(
            db,
            name=user.user_name,
            user_email=email,
            phone=user.user_number,
            role=user.user_role,
            invited_by=invited_by,
        )
        if ok:
            sent += 1
        else:
            skipped += 1
    return {"sent_count": sent, "skipped_count": skipped}


def revoke_pending(db: Session, user_email: str) -> tuple[bool, str]:
    email = user_email.strip().lower()
    user = get_user_by_email(db, email)
    if not user:
        return False, "User not found."
    if user.status != "pending":
        return False, "Only pending invites can be revoked this way."
    for inv in db.scalars(select(InviteToken).where(InviteToken.user_email == email)).all():
        db.delete(inv)
    db.delete(user)
    db.commit()
    return True, f"Invite for {email} revoked."


def get_invite(db: Session, token: str) -> dict[str, Any]:
    invite = db.scalar(select(InviteToken).where(InviteToken.token == token))
    if not invite:
        return {"state": "invalid", "invite": None}
    if invite.is_revoked:
        return {"state": "revoked", "invite": None}
    if invite.is_used:
        return {"state": "used", "invite": None}
    age = datetime.utcnow() - (invite.created_at or datetime.utcnow())
    if age > timedelta(days=30):
        return {"state": "expired", "invite": None}
    return {
        "state": "valid",
        "invite": {
            "token": invite.token,
            "user_name": invite.user_name,
            "user_email": invite.user_email,
            "user_role": invite.user_role,
            "permissions": _permissions_json_list(invite.permissions),
            "invited_by": invite.invited_by,
            "expires_in_days": max(0, 30 - age.days),
        },
    }


def accept_invite(db: Session, token: str, password: str) -> tuple[bool, str, dict[str, Any] | None]:
    preview = get_invite(db, token)
    if preview["state"] != "valid":
        return False, f"Invite is {preview['state']}.", None
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters.", None
    invite = db.scalar(select(InviteToken).where(InviteToken.token == token))
    if not invite:
        return False, "Invite not found.", None
    user = get_user_by_email(db, invite.user_email)
    if not user:
        return False, "Pending user record missing.", None
    user.status = "active"
    user.password_hash = _hash_password(password)
    user.user_role = invite.user_role or user.user_role
    user.permissions = json.dumps(_permissions_json_list(invite.permissions))
    invite.is_used = 1
    db.commit()
    db.refresh(user)
    return True, "Invite accepted. You can sign in.", _user_out(user)


def login(db: Session, email: str, password: str) -> tuple[bool, str, dict[str, Any] | None]:
    # `email` field accepts username or email
    user = get_user_by_login(db, email)
    if not user:
        return False, "Invalid username or password.", None
    if user.status != "active":
        return False, f"Account is {user.status}; complete invite or contact admin.", None
    if not _verify_password(password, user.password_hash):
        return False, "Invalid username or password.", None
    user.login_count = (user.login_count or 0) + 1
    user.last_login_at = datetime.utcnow()
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(hours=int(settings.auth_session_hours or 72))
    db.add(AuthSession(token=token, user_id=user.user_id, expires_at=expires))
    db.commit()
    db.refresh(user)
    return True, "Login successful.", {
        "token": token,
        "expires_at": expires.isoformat(),
        "user": _user_out(user),
    }


def logout(db: Session, token: str) -> None:
    sess = db.scalar(select(AuthSession).where(AuthSession.token == token))
    if sess:
        db.delete(sess)
        db.commit()


def session_user(db: Session, token: str | None) -> UserInfo | None:
    if not token:
        return None
    sess = db.scalar(select(AuthSession).where(AuthSession.token == token))
    if not sess:
        return None
    if sess.expires_at and sess.expires_at < datetime.utcnow():
        db.delete(sess)
        db.commit()
        return None
    return get_user_by_id(db, sess.user_id)


def update_last_visited(db: Session, user: UserInfo, snapshot: dict[str, Any]) -> dict[str, Any]:
    info = _session_info_dict(user)
    info["last_visited"] = {
        "view": snapshot.get("view"),
        "cluster_name": snapshot.get("cluster_name"),
        "node_name": snapshot.get("node_name"),
        "service_name": snapshot.get("service_name"),
        "updated_at": datetime.utcnow().isoformat(),
    }
    user.session_info = json.dumps(info)
    db.commit()
    db.refresh(user)
    return _user_out(user)


def user_to_dict(user: UserInfo, *, invite_token: str = "") -> dict[str, Any]:
    """Public alias for API serialization."""
    return _user_out(user, invite_token=invite_token)
