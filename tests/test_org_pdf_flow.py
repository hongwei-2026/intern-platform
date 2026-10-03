"""组织入驻 / 组织码 / PDF 申请 / 资料保存。"""

from __future__ import annotations

import re
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from intern_platform.db.base import Base
from intern_platform.db.session import get_db
import intern_platform.models  # noqa: F401
from intern_platform.dependencies.auth import hash_password
from intern_platform.models.community import Community
from intern_platform.models.community_extension import CommunityExtension
from intern_platform.models.project import Project
from intern_platform.models.role import Role, UserRole
from intern_platform.models.user import User
from intern_platform.services.community_service import _gen_invite_code

PDF_SCHEMA = (
    '{"type":"object","required":["resume_pdf","design_pdf"],'
    '"properties":{"resume_pdf":{"type":"string"},"design_pdf":{"type":"string"}}}'
)
MIN_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.fixture()
def client_and_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _seed(db: Session) -> dict[str, int]:
        roles: dict[str, Role] = {}
        for code, name in [
            ("student", "学生"),
            ("mentor", "导师"),
            ("community_admin", "社区管理员"),
            ("committee", "组委会"),
        ]:
            r = Role(code=code, name=name)
            db.add(r)
            db.flush()
            roles[code] = r

        pwd = hash_password("Demo@123456")
        users: dict[str, User] = {}
        for code, email, name in [
            ("student", "student@test.local", "学生"),
            ("mentor", "mentor@test.local", "导师"),
            ("community_admin", "admin@test.local", "社区管"),
            ("committee", "committee@test.local", "组委"),
            ("joiner", "joiner@test.local", "待加入导师"),
        ]:
            u = User(
                email=email,
                password_hash=pwd,
                display_name=name,
                auth_provider="local",
            )
            db.add(u)
            db.flush()
            users[code] = u
            if code == "joiner":
                continue
            role_code = code
            db.add(
                UserRole(
                    user_id=u.id,
                    role_id=roles[role_code].id,
                    community_id=None,
                )
            )

        community = Community(
            name="内核",
            slug="kernel",
            status="approved",
            applicant_user_id=users["community_admin"].id,
            invite_code="KERNEL-TEST",
        )
        db.add(community)
        db.flush()
        db.add(
            UserRole(
                user_id=users["community_admin"].id,
                role_id=roles["community_admin"].id,
                community_id=community.id,
            )
        )
        db.add(
            UserRole(
                user_id=users["mentor"].id,
                role_id=roles["mentor"].id,
                community_id=community.id,
            )
        )
        db.add(
            CommunityExtension(
                community_id=community.id,
                application_schema=PDF_SCHEMA,
            )
        )
        project = Project(
            community_id=community.id,
            mentor_id=users["mentor"].id,
            title="PDF Apply Demo",
            quota=2,
            status="published",
        )
        db.add(project)
        db.commit()
        return {
            "project_id": project.id,
            "community_id": community.id,
            "student_id": users["student"].id,
        }

    db0 = SessionLocal()
    ids = _seed(db0)
    db0.close()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, SessionLocal, ids
    app.dependency_overrides.clear()
    engine.dispose()


def _login(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Demo@123456"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _idem() -> str:
    return str(uuid.uuid4())


def test_invite_code_ascii_only_for_cjk_name() -> None:
    code = _gen_invite_code("新测试社区")
    assert re.fullmatch(r"[A-Z0-9]{3,6}-[A-Z0-9]{4}", code), code
    assert all(ord(ch) < 128 for ch in code)


def test_save_profile_ok(client_and_db) -> None:
    client, _, _ = client_and_db
    token = _login(client, "student@test.local")
    r = client.patch(
        "/api/v1/auth/me",
        headers=_auth(token),
        json={"display_name": "学生甲", "bio": "ci-profile", "school": "HUST"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["display_name"] == "学生甲"
    assert body["bio"] == "ci-profile"


def test_pdf_upload_reject_non_pdf(client_and_db) -> None:
    client, _, _ = client_and_db
    token = _login(client, "student@test.local")
    r = client.post(
        "/api/v1/uploads/pdf",
        headers=_auth(token),
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 400


def test_pdf_upload_and_apply(client_and_db) -> None:
    client, _, ids = client_and_db
    token = _login(client, "student@test.local")
    headers = _auth(token)

    up1 = client.post(
        "/api/v1/uploads/pdf",
        headers=headers,
        files={"file": ("resume.pdf", MIN_PDF, "application/pdf")},
    )
    up2 = client.post(
        "/api/v1/uploads/pdf",
        headers=headers,
        files={"file": ("design.pdf", MIN_PDF, "application/pdf")},
    )
    assert up1.status_code == 200, up1.text
    assert up2.status_code == 200, up2.text
    resume_url = up1.json()["url"]
    design_url = up2.json()["url"]
    assert resume_url.startswith("/api/v1/uploads/files/")

    got = client.get(resume_url, headers=headers)
    assert got.status_code == 200
    assert got.content.startswith(b"%PDF")
    blocked = client.get(resume_url)
    assert blocked.status_code == 401

    r = client.post(
        f"/api/v1/projects/{ids['project_id']}/applications",
        headers={**headers, "X-Idempotency-Key": _idem()},
        json={
            "statement": "ci apply with pdfs",
            "attachment_url": resume_url,
            "extra_fields": {"resume_pdf": resume_url, "design_pdf": design_url},
            "submit": True,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "mentor_review"
    assert body.get("resume_pdf") == resume_url
    assert body.get("design_pdf") == design_url

    mentor = _login(client, "mentor@test.local")
    inbox = client.get("/api/v1/mentor/inbox", headers=_auth(mentor))
    assert inbox.status_code == 200, inbox.text
    row = next(a for a in inbox.json() if a["id"] == body["id"])
    assert row["resume_pdf"] == resume_url
    assert row["design_pdf"] == design_url
    assert row.get("student_name")

    reject = client.post(
        f"/api/v1/applications/{body['id']}/reviews",
        headers={**_auth(mentor), "X-Idempotency-Key": _idem()},
        json={"decision": "reject", "comment": "ci reject", "version": row["version"]},
    )
    assert reject.status_code == 200, reject.text
    assert reject.json()["to_status"] == "rejected"

    # 未通过后可再次申请
    again = client.post(
        f"/api/v1/projects/{ids['project_id']}/applications",
        headers={**headers, "X-Idempotency-Key": _idem()},
        json={
            "statement": "reapply after reject",
            "attachment_url": resume_url,
            "extra_fields": {"resume_pdf": resume_url, "design_pdf": design_url},
            "submit": True,
        },
    )
    assert again.status_code == 201, again.text
    assert again.json()["id"] == body["id"]
    assert again.json()["status"] == "mentor_review"


def test_mentor_reject_from_submitted(client_and_db) -> None:
    """历史数据可能停在 submitted；导师应能直接拒绝。"""
    from intern_platform.services.review_usecase import resolve_actions

    actions = resolve_actions(
        decision="reject",
        status_value="submitted",
        actor_role="mentor",
    )
    assert actions == ["start_mentor_review", "reject"]

    approve = resolve_actions(
        decision="approve",
        status_value="submitted",
        actor_role="mentor",
    )
    assert approve == ["start_mentor_review", "approve_mentor"]


def test_apply_without_pdfs_rejected(client_and_db) -> None:
    client, _, ids = client_and_db
    token = _login(client, "student@test.local")
    r = client.post(
        f"/api/v1/projects/{ids['project_id']}/applications",
        headers={**_auth(token), "X-Idempotency-Key": _idem()},
        json={
            "statement": "missing pdfs",
            "extra_fields": {},
            "submit": True,
        },
    )
    assert r.status_code == 400


def test_org_settle_approve_join_and_mine(client_and_db) -> None:
    client, _, _ = client_and_db
    admin = _login(client, "admin@test.local")
    committee = _login(client, "committee@test.local")
    joiner = _login(client, "joiner@test.local")

    create = client.post(
        "/api/v1/communities",
        headers=_auth(admin),
        json={
            "name": "新测试社区",
            "slug": f"ci-org-{uuid.uuid4().hex[:6]}",
            "description": "ci settle",
        },
    )
    assert create.status_code == 201, create.text
    cid = create.json()["id"]
    assert create.json()["status"] == "pending"
    assert create.json().get("invite_code") in (None, "")

    review = client.post(
        f"/api/v1/communities/{cid}/review",
        headers={**_auth(committee), "X-Idempotency-Key": _idem()},
        json={"decision": "approve", "comment": "ci ok"},
    )
    assert review.status_code == 200, review.text
    invite = review.json()["invite_code"]
    assert invite
    assert all(ord(ch) < 128 for ch in invite)
    assert review.json()["status"] == "approved"

    public = client.get("/api/v1/communities", params={"status": "approved"})
    assert public.status_code == 200
    row = next(c for c in public.json() if c["id"] == cid)
    assert row.get("invite_code") is None

    join = client.post(
        "/api/v1/communities/join",
        headers=_auth(joiner),
        json={"invite_code": invite, "as_role": "mentor"},
    )
    assert join.status_code == 200, join.text
    assert join.json()["community_id"] == cid
    assert join.json()["role"] == "mentor"

    mine = client.get("/api/v1/communities/mine", headers=_auth(joiner))
    assert mine.status_code == 200, mine.text
    mine_row = next(c for c in mine.json() if c["id"] == cid)
    assert mine_row["invite_code"] == invite

    bad = client.post(
        "/api/v1/communities/join",
        headers=_auth(joiner),
        json={"invite_code": "NO-SUCH-CODE", "as_role": "mentor"},
    )
    assert bad.status_code == 404
