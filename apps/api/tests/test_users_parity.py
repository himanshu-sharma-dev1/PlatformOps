"""Users/invitation parity tests using only an in-memory database."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from platformops.db import Base  # noqa: E402
from platformops.models import AuthSession, InviteToken, UserInfo  # noqa: E402
from platformops.orchestrator import users  # noqa: E402


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_user_create_matches_email_phone_role_and_password_contract(db: Session):
    ok, message, _ = users.create_user(
        db,
        user_name="Bad Email",
        user_email="invalid",
        password="x",
        user_role="Operational",
    )
    assert ok is False
    assert message == "Failure, Invalid email format."

    ok, message, _ = users.create_user(
        db,
        user_name="Bad Phone",
        user_email="phone@example.test",
        password="x",
        user_role="Operational",
        user_number="12ab",
    )
    assert ok is False
    assert message == "Failure, Invalid phone number format."

    ok, message, _ = users.create_user(
        db,
        user_name="Bad Role",
        user_email="role@example.test",
        password="x",
        user_role="Owner",
    )
    assert ok is False
    assert message == "Failure, Invalid Role Provided."

    ok, _, created = users.create_user(
        db,
        user_name="Legacy Password",
        user_email="legacy@example.test",
        password="x",
        user_role="Management",
        user_number="1234567890",
    )
    assert ok is True
    assert created["user_role"] == "Management"
    assert created["user_number"] == "1234567890"


def test_status_and_role_changes_apply_to_the_next_session_request(db: Session):
    ok, _, created = users.create_user(
        db,
        user_name="Operator",
        user_email="operator@example.test",
        password="secret",
        user_role="Operational",
    )
    assert ok and created
    ok, _, login = users.login(db, "operator@example.test", "secret")
    assert ok and login
    token = login["token"]
    assert users.session_user(db, token).user_role == "Operational"

    ok, _, updated = users.update_user(
        db,
        created["user_id"],
        user_role="Management",
    )
    assert ok and updated["user_role"] == "Management"
    assert users.session_user(db, token).user_role == "Management"

    ok, _, updated = users.update_user(db, created["user_id"], status="disabled")
    assert ok and updated["status"] == "disabled"
    assert users.session_user(db, token) is None
    assert db.scalar(select(AuthSession).where(AuthSession.token == token)) is None


def test_complete_invitation_resend_accept_and_terminal_states(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    deliveries: list[tuple[str, str]] = []

    def deliver(*, recipient: str, recipient_name: str, token: str):
        deliveries.append((recipient, token))
        return True, "sent"

    monkeypatch.setattr(users, "_send_invite_email", deliver)
    ok, _, pending = users.invite_user(
        db,
        name="Invited Operator",
        user_email="invitee@example.test",
        phone="1234567890",
        role="Operational",
        permissions=["monitoring.read"],
        invited_by="admin@example.test",
    )
    assert ok and pending
    first_token = deliveries[-1][1]
    assert users.get_invite(db, first_token)["state"] == "valid"

    result = users.resend_invites(db, ["invitee@example.test"], "admin@example.test")
    assert result == {"sent_count": 1, "skipped_count": 0}
    second_token = deliveries[-1][1]
    assert second_token != first_token
    assert users.get_invite(db, first_token)["state"] == "revoked"

    ok, message, accepted = users.accept_invite(
        db,
        second_token,
        "StrongPassword123!",
        "Accepted Full Name",
    )
    assert ok is True
    assert message == "Invite accepted. You can sign in."
    assert accepted["user_name"] == "Accepted Full Name"
    assert accepted["status"] == "active"
    assert accepted["token"]
    assert accepted["user"]["user_email"] == "invitee@example.test"
    assert users.session_user(db, accepted["token"]).user_email == "invitee@example.test"
    assert users.get_invite(db, second_token)["state"] == "used"

    ok, message, _ = users.accept_invite(
        db,
        second_token,
        "AnotherPassword123!",
        "Second Acceptance",
    )
    assert ok is False
    assert message == "Invite is used."
    assert db.scalars(select(UserInfo).where(UserInfo.user_email == "invitee@example.test")).all()


def test_expired_and_revoked_invites_have_deterministic_terminal_states(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(users, "_send_invite_email", lambda **_kwargs: (True, "sent"))
    ok, _, pending = users.invite_user(
        db,
        name="Expiry",
        user_email="expiry@example.test",
        role="Operational",
        invited_by="admin@example.test",
    )
    assert ok and pending
    token = pending["invite_token"]
    invite = db.scalar(select(InviteToken).where(InviteToken.token == token))
    invite.created_at = datetime.utcnow() - timedelta(days=31)
    db.commit()
    assert users.get_invite(db, token)["state"] == "expired"

    ok, message, _ = users.accept_invite(db, token, "password", "Expired User")
    assert ok is False
    assert message == "Invite is expired."

    ok, message = users.revoke_pending(db, "expiry@example.test")
    assert ok is True
    assert "revoked" in message
    assert users.get_invite(db, token)["state"] == "invalid"


def test_self_delete_purges_session_and_last_admin_guard_is_deterministic(db: Session):
    ok, _, first = users.create_user(
        db,
        user_name="First Admin",
        user_email="first-admin@example.test",
        password="admin",
        user_role="System_Admin",
    )
    assert ok and first
    ok, _, second = users.create_user(
        db,
        user_name="Second Admin",
        user_email="second-admin@example.test",
        password="admin",
        user_role="System_Admin",
    )
    assert ok and second
    ok, _, login = users.login(db, "first-admin@example.test", "admin")
    assert ok and login

    ok, message = users.delete_user(db, first["user_id"], initiated_by="first-admin@example.test")
    assert ok and "deleted successfully" in message
    assert users.session_user(db, login["token"]) is None
    assert db.scalar(select(UserInfo).where(UserInfo.user_id == first["user_id"])) is None

    ok, message = users.delete_user(db, second["user_id"], initiated_by="second-admin@example.test")
    assert ok is False
    assert message == "Cannot delete the last System_Admin."
