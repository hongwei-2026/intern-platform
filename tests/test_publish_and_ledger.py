"""发布、审核流水和结项名单。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from intern_platform.db.base import Base
from intern_platform.db.session import get_db
import intern_platform.models  # noqa: F401
from intern_platform.dependencies.auth import hash_password
from intern_platform.models.application import Application
from intern_platform.models.community import Community
from intern_platform.models.notification import Notification
from intern_platform.models.project import Project
from intern_platform.models.review_record import ReviewRecord
from intern_platform.models.role import Role, UserRole
from intern_platform.models.user import User
from intern_platform.services.ledger import verify_audit_chain


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
        roles = {}
        for code, name in [
            ("student", "学生"),
            ("mentor", "导师"),
            ("community_admin", "社区管理员"),
            ("committee", "组委会"),
        ]:
            role = Role(code=code, name=name)
            db.add(role)
            db.flush()
            roles[code] = role
        pwd = hash_password("Demo@123456")
        users = {}
        for code, email, name in [
            ("student", "student@flow.local", "学生"),
            ("mentor", "mentor@flow.local", "导师"),
            ("community_admin", "admin@flow.local", "社区管"),
            ("committee", "committee@flow.local", "组委"),
        ]:
            user = User(
                email=email,
                password_hash=pwd,
                display_name=name,
                auth_provider="local",
            )
            db.add(user)
            db.flush()
            users[code] = user
            db.add(UserRole(user_id=user.id, role_id=roles[code].id, community_id=None))
        community = Community(
            name="流水社区",
            slug="flow",
            status="approved",
            invite_code="FLOW01",
            applicant_user_id=users["community_admin"].id,
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
        db.commit()
        return {
            "community_id": community.id,
            "mentor_id": users["mentor"].id,
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


def _token(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Demo@123456"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_create_project_publishes_and_notifies_only_mentor(client_and_db):
    client, SessionLocal, ids = client_and_db
    admin = _token(client, "admin@flow.local")
    created = client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {admin}"},
        json={
            "community_id": ids["community_id"],
            "mentor_id": ids["mentor_id"],
            "title": "直接发布课题",
            "quota": 1,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "published"
    project_id = created.json()["id"]

    public = client.get("/api/v1/projects", params={"status": "published"})
    assert public.status_code == 200
    assert any(item["id"] == project_id for item in public.json())

    mentor = _token(client, "mentor@flow.local")
    student = _token(client, "student@flow.local")
    mentor_notes = client.get(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {mentor}"},
    ).json()["items"]
    student_notes = client.get(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {student}"},
    ).json()["items"]
    assert any(item["kind"] == "project_published" for item in mentor_notes)
    assert all(item["kind"] != "project_published" for item in student_notes)


def test_unpublish_hides_project_from_public_list(client_and_db):
    client, _session_local, ids = client_and_db
    admin = _token(client, "admin@flow.local")
    created = client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {admin}"},
        json={
            "community_id": ids["community_id"],
            "mentor_id": ids["mentor_id"],
            "title": "待下架课题",
            "quota": 1,
        },
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    hidden = client.post(
        f"/api/v1/projects/{project_id}/unpublish",
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["status"] == "offline"

    public = client.get("/api/v1/projects", params={"status": "published"})
    assert all(item["id"] != project_id for item in public.json())
    anonymous = client.get(
        "/api/v1/projects",
        params={"status": "offline", "community_id": ids["community_id"]},
    )
    assert anonymous.status_code == 401
    gone = client.get(f"/api/v1/projects/{project_id}")
    assert gone.status_code == 404

    admin_list = client.get(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {admin}"},
        params={"status": "offline", "community_id": ids["community_id"]},
    )
    assert admin_list.status_code == 200
    assert any(item["id"] == project_id for item in admin_list.json())

    again = client.post(
        f"/api/v1/projects/{project_id}/publish",
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert again.status_code == 200, again.text
    assert again.json()["status"] == "published"


def test_student_email_cannot_open_org(client_and_db):
    client, _session_local, _ids = client_and_db
    committee = _token(client, "committee@flow.local")
    resp = client.post(
        "/api/v1/communities",
        headers={"Authorization": f"Bearer {committee}"},
        json={
            "name": "重复邮箱社区",
            "slug": "dup-mail",
            "admin_name": "学生本人",
            "admin_email": "student@flow.local",
        },
    )
    assert resp.status_code == 400
    assert "邮箱" in resp.text


def test_pending_communities_are_not_public(client_and_db):
    client, _session_local, _ids = client_and_db
    hidden = client.get("/api/v1/communities", params={"status": "pending"})
    assert hidden.status_code == 403
    open_list = client.get("/api/v1/communities", params={"status": "approved"})
    assert open_list.status_code == 200


def test_audit_chain_stays_valid_after_login(client_and_db):
    client, SessionLocal, _ids = client_and_db
    _token(client, "student@flow.local")
    _token(client, "mentor@flow.local")
    db = SessionLocal()
    try:
        ok, error = verify_audit_chain(db)
        assert ok, error
    finally:
        db.close()


def test_mentor_final_shows_on_committee_roster(client_and_db):
    client, SessionLocal, ids = client_and_db
    db = SessionLocal()
    try:
        project = Project(
            community_id=ids["community_id"],
            mentor_id=ids["mentor_id"],
            title="已结项课题",
            quota=1,
            status="published",
        )
        db.add(project)
        db.flush()
        app = Application(
            project_id=project.id,
            student_id=ids["student_id"],
            status="community_final_review",
            current_node="community",
        )
        db.add(app)
        db.flush()
        db.add(
            ReviewRecord(
                application_id=app.id,
                seq_no=1,
                from_status="mentor_final_review",
                to_status="community_final_review",
                action="approve_mentor_final",
                actor_id=ids["mentor_id"],
                actor_role="mentor",
                created_at=datetime(2026, 9, 29, tzinfo=timezone.utc),
            )
        )
        db.commit()
        app_id = app.id
    finally:
        db.close()

    committee = _token(client, "committee@flow.local")
    resp = client.get(
        "/api/v1/committee/completions",
        params={"month": "2026-09"},
        headers={"Authorization": f"Bearer {committee}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "2026-09" in body["months"]
    assert any(item["application_id"] == app_id for item in body["items"])
    notes = db_notes(SessionLocal, ids["student_id"])
    assert all(item.kind != "committee_roster" for item in notes)


def db_notes(session_local, user_id: int) -> list[Notification]:
    db = session_local()
    try:
        return list(
            db.scalars(select(Notification).where(Notification.user_id == user_id)).all()
        )
    finally:
        db.close()
