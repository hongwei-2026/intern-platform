"""安全修复回归：transitions 角色、附件白名单、创建导师不改密、邀请码等。"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from intern_platform.dependencies.auth import hash_password, verify_password
from intern_platform.models.role import Role, UserRole
from intern_platform.models.user import User
from intern_platform.services.upload_urls import is_safe_upload_url


def _idem() -> str:
    return str(uuid.uuid4())


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login(client, email: str, password: str = "Demo@123456") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_upload_url_whitelist() -> None:
    assert is_safe_upload_url("/api/v1/uploads/files/u1/a.pdf")
    assert is_safe_upload_url("/api/v1/uploads/files/u1/a.pdf", owner_user_id=1)
    assert not is_safe_upload_url("/api/v1/uploads/files/u2/a.pdf", owner_user_id=1)
    assert not is_safe_upload_url(
        "https://webhook.site/x/uploads/files/resume.pdf"
    )
    assert not is_safe_upload_url("javascript:alert(1)")
    assert not is_safe_upload_url("/uploads/files/u1/a.pdf")


def test_student_cannot_self_approve(client_and_db) -> None:
    client, _, ids = client_and_db
    app_id = ids["application_id"]
    student = _login(client, "student@test.local")
    client.post(
        f"/api/v1/applications/{app_id}/submit",
        headers={**_auth(student), "X-Idempotency-Key": _idem()},
    )
    for action in (
        "approve_mentor",
        "approve_community",
        "approve_committee",
        "approve_mentor_final",
        "submit_community_final",
        "approve_committee_final",
    ):
        r = client.post(
            f"/api/v1/applications/{app_id}/transitions",
            headers={**_auth(student), "X-Idempotency-Key": _idem()},
            json={"action": action},
        )
        assert r.status_code == 403, (action, r.text)


def test_reject_external_resume_url(client_and_db) -> None:
    client, _, ids = client_and_db
    project_id = ids["project_id"]
    student = _login(client, "student@test.local")
    r = client.post(
        f"/api/v1/projects/{project_id}/applications",
        headers={**_auth(student), "X-Idempotency-Key": _idem()},
        json={
            "statement": "ext resume",
            "extra_fields": {
                "resume_pdf": "https://evil.example/uploads/files/x.pdf",
                "design_pdf": "/api/v1/uploads/files/u1/ok.pdf",
            },
            "submit": False,
        },
    )
    assert r.status_code == 400
    assert "本站" in r.text or "resume" in r.text.lower() or "上传" in r.text


def test_reject_javascript_attachment(client_and_db) -> None:
    client, SessionLocal, ids = client_and_db
    app_id = ids["application_id"]
    student = _login(client, "student@test.local")
    mentor = _login(client, "mentor@test.local")
    client.post(
        f"/api/v1/applications/{app_id}/submit",
        headers={**_auth(student), "X-Idempotency-Key": _idem()},
    )
    client.post(
        f"/api/v1/applications/{app_id}/reviews",
        headers={**_auth(mentor), "X-Idempotency-Key": _idem()},
        json={"decision": "approve"},
    )
    r = client.post(
        f"/api/v1/applications/{app_id}/messages",
        headers={**_auth(student), "X-Idempotency-Key": _idem()},
        json={
            "body": "progress",
            "kind": "progress",
            "attachment_url": "javascript:void(1)",
            "attachment_name": "clickme.zip",
        },
    )
    assert r.status_code == 400


def test_create_mentor_does_not_reset_password(client_and_db) -> None:
    client, SessionLocal, ids = client_and_db
    community_id = ids["community_id"]
    admin = _login(client, "admin@test.local")
    email = f"pwkeep_{uuid.uuid4().hex[:8]}@test.local"
    old_pw = "OldPass@123456"
    new_pw = "NewPass@654321"

    db = SessionLocal()
    try:
        user = User(
            email=email,
            password_hash=hash_password(old_pw),
            display_name="keep-me",
            auth_provider="local",
        )
        db.add(user)
        db.commit()
        uid = user.id
    finally:
        db.close()

    r = client.post(
        f"/api/v1/communities/{community_id}/mentors",
        headers={**_auth(admin), "X-Idempotency-Key": _idem()},
        json={"email": email, "password": new_pw, "display_name": "hijack"},
    )
    assert r.status_code == 201, r.text

    bad = client.post("/api/v1/auth/login", json={"email": email, "password": new_pw})
    assert bad.status_code == 401
    ok = client.post("/api/v1/auth/login", json={"email": email, "password": old_pw})
    assert ok.status_code == 200

    db = SessionLocal()
    try:
        user = db.get(User, uid)
        assert user is not None
        assert user.display_name == "keep-me"
        assert verify_password(old_pw, user.password_hash)
    finally:
        db.close()


def test_community_approve_no_global_admin(client_and_db) -> None:
    client, SessionLocal, ids = client_and_db
    committee = _login(client, "committee@test.local")
    student = _login(client, "student@test.local")

    slug = f"sec-{uuid.uuid4().hex[:6]}"
    r = client.post(
        "/api/v1/communities",
        headers={**_auth(student), "X-Idempotency-Key": _idem()},
        json={
            "name": "安全测试社区",
            "slug": slug,
            "description": "scope check",
        },
    )
    assert r.status_code == 201, r.text
    cid = r.json()["id"]

    r = client.post(
        f"/api/v1/communities/{cid}/review",
        headers={**_auth(committee), "X-Idempotency-Key": _idem()},
        json={"decision": "approve", "comment": "ok"},
    )
    assert r.status_code == 200, r.text

    me = client.get("/api/v1/auth/me", headers=_auth(student))
    assert me.status_code == 200
    roles = me.json().get("roles") or []
    admin_roles = [x for x in roles if x.get("code") == "community_admin"]
    assert admin_roles
    assert all(x.get("community_id") == cid for x in admin_roles)

    db = SessionLocal()
    try:
        admin_role = db.scalar(select(Role).where(Role.code == "community_admin"))
        assert admin_role is not None
        null_rows = list(
            db.scalars(
                select(UserRole).where(
                    UserRole.user_id == me.json()["id"],
                    UserRole.role_id == admin_role.id,
                    UserRole.community_id.is_(None),
                )
            ).all()
        )
        assert null_rows == []
    finally:
        db.close()
