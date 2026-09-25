"""任务3主链路集成测试：鉴权 + 审核流水 + 幂等 + 非法迁移 + 越权。"""

from __future__ import annotations

import uuid

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
from intern_platform.models.audit_log import AuditLog
from intern_platform.models.community import Community
from intern_platform.models.community_extension import CommunityExtension
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

    def _seed(db: Session) -> dict[str, int]:
        roles = {}
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
        users = {}
        for code, email, name in [
            ("student", "student@test.local", "学生"),
            ("mentor", "mentor@test.local", "导师"),
            ("community_admin", "admin@test.local", "社区管"),
            ("committee", "committee@test.local", "组委"),
            ("outsider", "outsider@test.local", "外人"),
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
            role_code = "student" if code == "outsider" else code
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
            CommunityExtension(
                community_id=community.id,
                application_schema=(
                    '{"type":"object","properties":{"note":{"type":"string"}}}'
                ),
            )
        )
        project = Project(
            community_id=community.id,
            mentor_id=users["mentor"].id,
            title="Demo",
            quota=1,
            status="published",
        )
        db.add(project)
        db.flush()
        app_row = Application(
            project_id=project.id,
            student_id=users["student"].id,
            statement="want",
            status="draft",
            current_node="none",
            version=0,
        )
        db.add(app_row)
        db.commit()
        return {
            "application_id": app_row.id,
            "project_id": project.id,
            "student_id": users["student"].id,
            "mentor_id": users["mentor"].id,
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


def test_full_path_draft_to_completed_writes_ledger(client_and_db) -> None:
    client, SessionLocal, ids = client_and_db
    app_id = ids["application_id"]

    student = _login(client, "student@test.local")
    mentor = _login(client, "mentor@test.local")
    admin = _login(client, "admin@test.local")
    committee = _login(client, "committee@test.local")

    # submit draft → mentor_review
    r = client.post(
        f"/api/v1/applications/{app_id}/submit",
        headers={**_auth(student), "X-Idempotency-Key": _idem()},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "mentor_review"

    def review(token: str, decision: str = "approve") -> dict:
        resp = client.post(
            f"/api/v1/applications/{app_id}/reviews",
            headers={**_auth(token), "X-Idempotency-Key": _idem()},
            json={"decision": decision, "comment": "ok"},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()

    review(mentor)
    review(admin)
    review(committee)

    r = client.post(
        f"/api/v1/applications/{app_id}/start-progress",
        headers={**_auth(student), "X-Idempotency-Key": _idem()},
    )
    assert r.status_code == 200
    assert r.json()["to_status"] == "in_progress"

    r = client.put(
        f"/api/v1/applications/{app_id}/final",
        headers=_auth(student),
        json={"pr_mr_url": "https://git.example/mr/1", "report_text": "done"},
    )
    assert r.status_code == 200, r.text

    r = client.post(
        f"/api/v1/applications/{app_id}/final/submit",
        headers={**_auth(student), "X-Idempotency-Key": _idem()},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "mentor_final_review"

    r = client.post(
        f"/api/v1/applications/{app_id}/final/reviews",
        headers={**_auth(mentor), "X-Idempotency-Key": _idem()},
        json={"decision": "approve"},
    )
    assert r.status_code == 200, r.text

    r = client.post(
        f"/api/v1/applications/{app_id}/final/reviews",
        headers={**_auth(committee), "X-Idempotency-Key": _idem()},
        json={"decision": "approve"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["to_status"] == "completed"

    db = SessionLocal()
    try:
        app_row = db.get(Application, app_id)
        assert app_row is not None
        assert app_row.status == "completed"
        assert app_row.version > 0
        reviews = list(db.scalars(select(ReviewRecord)).all())
        assert len(reviews) >= 10
        audits = list(db.scalars(select(AuditLog)).all())
        assert any(a.outcome == "SUCCESS" for a in audits)
        ok, err = verify_audit_chain(db)
        assert ok, err
    finally:
        db.close()


def test_idempotent_replay_no_double_review(client_and_db) -> None:
    client, SessionLocal, ids = client_and_db
    app_id = ids["application_id"]
    student = _login(client, "student@test.local")
    mentor = _login(client, "mentor@test.local")

    client.post(
        f"/api/v1/applications/{app_id}/submit",
        headers={**_auth(student), "X-Idempotency-Key": _idem()},
    )
    key = _idem()
    r1 = client.post(
        f"/api/v1/applications/{app_id}/reviews",
        headers={**_auth(mentor), "X-Idempotency-Key": key},
        json={"decision": "approve"},
    )
    r2 = client.post(
        f"/api/v1/applications/{app_id}/reviews",
        headers={**_auth(mentor), "X-Idempotency-Key": key},
        json={"decision": "approve"},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json()["idempotent_replay"] is True

    db = SessionLocal()
    try:
        # submit+start (2) + approve_mentor (1)；回放不加
        count = len(list(db.scalars(select(ReviewRecord)).all()))
        assert count == 3
        assert r2.json()["to_status"] == "community_review"
    finally:
        db.close()


def test_illegal_transition_writes_fail_audit(client_and_db) -> None:
    client, SessionLocal, ids = client_and_db
    app_id = ids["application_id"]
    student = _login(client, "student@test.local")

    r = client.post(
        f"/api/v1/applications/{app_id}/transitions",
        headers={**_auth(student), "X-Idempotency-Key": _idem()},
        json={"action": "approve_committee"},
    )
    assert r.status_code == 409

    db = SessionLocal()
    try:
        fails = list(
            db.scalars(select(AuditLog).where(AuditLog.outcome == "FAIL")).all()
        )
        assert len(fails) >= 1
        assert any("approve_committee" in (a.action or "") for a in fails)
        assert db.get(Application, app_id).status == "draft"
    finally:
        db.close()


def test_unauthorized_review_403(client_and_db) -> None:
    client, _, ids = client_and_db
    app_id = ids["application_id"]
    student = _login(client, "student@test.local")
    outsider = _login(client, "outsider@test.local")

    client.post(
        f"/api/v1/applications/{app_id}/submit",
        headers={**_auth(student), "X-Idempotency-Key": _idem()},
    )
    r = client.post(
        f"/api/v1/applications/{app_id}/reviews",
        headers={**_auth(outsider), "X-Idempotency-Key": _idem()},
        json={"decision": "approve"},
    )
    assert r.status_code == 403


def test_missing_idempotency_key_400(client_and_db) -> None:
    client, _, ids = client_and_db
    app_id = ids["application_id"]
    student = _login(client, "student@test.local")
    r = client.post(
        f"/api/v1/applications/{app_id}/transitions",
        headers=_auth(student),
        json={"action": "submit"},
    )
    assert r.status_code == 400
