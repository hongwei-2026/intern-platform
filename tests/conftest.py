"""共享测试夹具。"""

from __future__ import annotations

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
from intern_platform.models.community_extension import CommunityExtension
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
            UserRole(
                user_id=users["mentor"].id,
                role_id=roles["mentor"].id,
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
            "community_id": community.id,
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
