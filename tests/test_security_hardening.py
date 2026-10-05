"""第二轮安全加固：邀请码提权、空社区赋权、上传归属、改密吊销、流水。"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from intern_platform.dependencies.auth import verify_password
from intern_platform.models.audit_log import AuditLog
from intern_platform.models.community import Community
from intern_platform.models.user import User
from intern_platform.services.ledger import verify_audit_chain


def _idem() -> str:
    return str(uuid.uuid4())


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login(client, email: str, password: str = "Demo@123456") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_invite_cannot_join_as_community_admin(client_and_db) -> None:
    client, SessionLocal, ids = client_and_db
    community_id = ids["community_id"]
    db = SessionLocal()
    try:
        community = db.get(Community, community_id)
        assert community is not None
        community.invite_code = "ABCD-EFGH"
        db.commit()
        code = community.invite_code
    finally:
        db.close()

    student = _login(client, "student@test.local")
    r = client.post(
        "/api/v1/communities/join",
        headers={**_auth(student), "X-Idempotency-Key": _idem()},
        json={"invite_code": code, "as_role": "community_admin"},
    )
    assert r.status_code in (400, 422), r.text


def test_grant_null_scoped_admin_rejected(client_and_db) -> None:
    client, SessionLocal, _ = client_and_db
    committee = _login(client, "committee@test.local")
    db = SessionLocal()
    try:
        student = db.scalar(select(User).where(User.email == "student@test.local"))
        assert student is not None
        uid = student.id
    finally:
        db.close()

    r = client.post(
        "/api/v1/auth/roles",
        headers={**_auth(committee), "X-Idempotency-Key": _idem()},
        json={"user_id": uid, "role_code": "community_admin", "community_id": None},
    )
    assert r.status_code == 400, r.text


def test_cannot_attach_other_user_upload(client_and_db) -> None:
    client, SessionLocal, ids = client_and_db
    project_id = ids["project_id"]
    student = _login(client, "student@test.local")
    db = SessionLocal()
    try:
        me = db.scalar(select(User).where(User.email == "student@test.local"))
        assert me is not None
        other_id = me.id + 99
    finally:
        db.close()

    r = client.post(
        f"/api/v1/projects/{project_id}/applications",
        headers={**_auth(student), "X-Idempotency-Key": _idem()},
        json={
            "statement": "stolen file",
            "extra_fields": {
                "resume_pdf": f"/api/v1/uploads/files/u{other_id}/x.pdf",
                "design_pdf": f"/api/v1/uploads/files/u{other_id}/y.pdf",
            },
            "submit": False,
        },
    )
    assert r.status_code == 400
    assert "本人" in r.text or "上传" in r.text


def test_password_change_revokes_old_token_and_audits(client_and_db) -> None:
    client, SessionLocal, _ = client_and_db
    email = f"pwrev_{uuid.uuid4().hex[:8]}@test.local"
    old_pw = "OldPass@123456"
    new_pw = "NewPass@654321"

    reg = client.post(
        "/api/v1/auth/register",
        headers={"X-Idempotency-Key": _idem()},
        json={
            "email": email,
            "password": old_pw,
            "display_name": "pwrev",
        },
    )
    assert reg.status_code == 200, reg.text
    old_token = reg.json()["access_token"]

    r = client.post(
        "/api/v1/auth/me/password",
        headers={**_auth(old_token), "X-Idempotency-Key": _idem()},
        json={"old_password": old_pw, "new_password": new_pw},
    )
    assert r.status_code == 200, r.text

    me = client.get("/api/v1/auth/me", headers=_auth(old_token))
    assert me.status_code == 401

    new_token = _login(client, email, new_pw)
    me2 = client.get("/api/v1/auth/me", headers=_auth(new_token))
    assert me2.status_code == 200

    db = SessionLocal()
    try:
        rows = list(
            db.scalars(
                select(AuditLog)
                .where(AuditLog.action == "auth.password_change")
                .order_by(AuditLog.seq_no.desc())
            ).all()
        )
        assert rows
        assert rows[0].outcome == "SUCCESS"
        ok, err = verify_audit_chain(db)
        assert ok is True, err
    finally:
        db.close()


def test_org_admin_gets_random_password(client_and_db) -> None:
    client, SessionLocal, _ = client_and_db
    committee = _login(client, "committee@test.local")
    email = f"orgpw_{uuid.uuid4().hex[:8]}@test.local"
    r = client.post(
        "/api/v1/communities",
        headers={**_auth(committee), "X-Idempotency-Key": _idem()},
        json={
            "name": "随机密码社区",
            "slug": f"rnd-{uuid.uuid4().hex[:6]}",
            "description": "sec",
            "admin_name": "组织员",
            "admin_email": email,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    pw = body.get("admin_initial_password")
    assert pw and pw != "Demo@123456"
    assert len(pw) >= 10

    bad = client.post("/api/v1/auth/login", json={"email": email, "password": "Demo@123456"})
    assert bad.status_code == 401
    ok = client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert ok.status_code == 200

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        assert verify_password(pw, user.password_hash)
        assert not verify_password("Demo@123456", user.password_hash)
        provision = db.scalar(
            select(AuditLog).where(AuditLog.action == "community.admin_provision")
        )
        assert provision is not None
    finally:
        db.close()
