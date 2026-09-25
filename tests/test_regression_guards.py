"""踩坑回归：邀请码隐私 / admin-of 一人一社 / 驳回后再申请 / 导师邀请码注册 / 主页可更新。

对应历史问题：
- 公开社区接口泄露 invite_code
- seed 导致社区管理员绑多社，组织台挤成「全站列表」
- 驳回后「已申请过」无法再次提交
- 导师须私下邀请码自助注册
- 社区主页字段 PATCH 不生效或公开页读到码
"""

from __future__ import annotations

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
from intern_platform.models.application import Application
from intern_platform.models.community import Community
from intern_platform.models.project import Project
from intern_platform.models.role import Role, UserRole
from intern_platform.models.user import User


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

    def _seed(db: Session) -> dict:
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
            ("student", "student@reg.local", "学生"),
            ("mentor", "mentor@reg.local", "导师"),
            ("community_admin", "admin@reg.local", "社区管"),
            ("committee", "committee@reg.local", "组委"),
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
            db.add(
                UserRole(user_id=u.id, role_id=roles[code].id, community_id=None)
            )

        kernel = Community(
            name="内核",
            slug="kernel",
            status="approved",
            description="内核社区简介",
            homepage_url="https://hust.openatom.club/",
            invite_code="KERNEL01",
            applicant_user_id=users["community_admin"].id,
        )
        mirror = Community(
            name="镜像",
            slug="mirror",
            status="approved",
            description="镜像社区",
            invite_code="MIRROR01",
            applicant_user_id=users["community_admin"].id,
        )
        db.add_all([kernel, mirror])
        db.flush()

        # 正确绑定：管理员只管 kernel；故意不给 mirror 管理权
        db.add(
            UserRole(
                user_id=users["community_admin"].id,
                role_id=roles["community_admin"].id,
                community_id=kernel.id,
            )
        )
        db.add(
            UserRole(
                user_id=users["mentor"].id,
                role_id=roles["mentor"].id,
                community_id=kernel.id,
            )
        )

        project = Project(
            community_id=kernel.id,
            mentor_id=users["mentor"].id,
            title="回归课题",
            quota=2,
            status="published",
        )
        db.add(project)
        db.flush()
        db.commit()
        return {
            "kernel_id": kernel.id,
            "mirror_id": mirror.id,
            "project_id": project.id,
            "student_id": users["student"].id,
            "mentor_id": users["mentor"].id,
            "admin_id": users["community_admin"].id,
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


def test_public_community_apis_strip_invite_code(client_and_db) -> None:
    client, _, _ = client_and_db
    listed = client.get("/api/v1/communities", params={"status": "approved"})
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert rows, "应有已准入社区"
    for row in rows:
        assert row.get("invite_code") in (None, ""), row

    detail = client.get("/api/v1/communities/kernel")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["slug"] == "kernel"
    assert body.get("invite_code") in (None, "")
    assert body["homepage_url"] == "https://hust.openatom.club/"


def test_admin_of_returns_only_bound_community_with_invite(client_and_db) -> None:
    client, _, ids = client_and_db
    token = _login(client, "admin@reg.local")
    resp = client.get("/api/v1/communities/admin-of", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) == 1, rows
    assert rows[0]["id"] == ids["kernel_id"]
    assert rows[0]["invite_code"] == "KERNEL01"


def test_committee_admin_of_empty_without_community_binding(client_and_db) -> None:
    client, _, _ = client_and_db
    token = _login(client, "committee@reg.local")
    resp = client.get("/api/v1/communities/admin-of", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


def test_student_cannot_access_admin_of(client_and_db) -> None:
    client, _, _ = client_and_db
    token = _login(client, "student@reg.local")
    resp = client.get("/api/v1/communities/admin-of", headers=_auth(token))
    assert resp.status_code == 403


def test_mentor_register_with_private_invite_code(client_and_db) -> None:
    client, _, ids = client_and_db
    email = f"new-mentor-{uuid.uuid4().hex[:8]}@reg.local"
    bad = client.post(
        "/api/v1/auth/register-mentor",
        json={
            "email": email,
            "password": "Demo@123456",
            "display_name": "新导师",
            "invite_code": "WRONGCOD",
        },
    )
    assert bad.status_code in (400, 404), bad.text

    ok = client.post(
        "/api/v1/auth/register-mentor",
        json={
            "email": email,
            "password": "Demo@123456",
            "display_name": "新导师",
            "invite_code": "KERNEL01",
        },
    )
    assert ok.status_code == 200, ok.text
    assert "access_token" in ok.json()

    # 登录后应能看到自己是导师（至少能登录）
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Demo@123456"},
    )
    assert login.status_code == 200, login.text
    me = client.get("/api/v1/auth/me", headers=_auth(login.json()["access_token"]))
    assert me.status_code == 200, me.text
    roles = {r["code"] for r in me.json().get("roles", [])}
    assert "mentor" in roles


def test_rejected_application_can_reapply(client_and_db) -> None:
    client, SessionLocal, ids = client_and_db
    student = _login(client, "student@reg.local")
    project_id = ids["project_id"]

    # 先造一条已驳回申请
    db = SessionLocal()
    try:
        app_row = Application(
            project_id=project_id,
            student_id=ids["student_id"],
            statement="first try",
            status="rejected",
            current_node="none",
            version=1,
        )
        db.add(app_row)
        db.commit()
        app_id = app_row.id
    finally:
        db.close()

    r = client.post(
        f"/api/v1/projects/{project_id}/applications",
        headers={
            **_auth(student),
            "X-Idempotency-Key": str(uuid.uuid4()),
        },
        json={
            "statement": "second try after reject",
            "submit": True,
            "extra_fields": {},
        },
    )
    assert r.status_code in (200, 201), r.text
    body = r.json()
    assert body["id"] == app_id
    assert body["status"] in ("submitted", "mentor_review", "draft")
    assert body["status"] != "rejected"


def test_community_admin_can_patch_homepage_fields(client_and_db) -> None:
    client, _, ids = client_and_db
    token = _login(client, "admin@reg.local")
    cid = ids["kernel_id"]
    r = client.patch(
        f"/api/v1/communities/{cid}",
        headers=_auth(token),
        json={
            "name": "内核社区",
            "description": "更新后的对外简介",
            "homepage_url": "https://example.com/org",
            "gitea_org_url": "https://git.example/org",
            "logo_url": "https://example.com/logo.png",
            "tags": ["内核", "驱动"],
            "intro_body": {
                "blocks": [
                    {"id": "t1", "type": "heading", "text": "我们做什么"},
                    {"id": "t2", "type": "paragraph", "text": "聚焦操作系统内核与驱动实践。"},
                ]
            },
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["description"] == "更新后的对外简介"
    assert data["homepage_url"] == "https://example.com/org"
    assert data["gitea_org_url"] == "https://git.example/org"
    assert data["tags"] == ["内核", "驱动"]
    assert data["intro_body"]["blocks"][0]["type"] == "heading"

    public = client.get("/api/v1/communities/kernel")
    assert public.status_code == 200
    pub = public.json()
    assert pub["description"] == "更新后的对外简介"
    assert pub["tags"] == ["内核", "驱动"]
    assert pub.get("invite_code") in (None, "")
    assert pub["intro_body"]["blocks"][1]["text"].startswith("聚焦")
