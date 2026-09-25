"""状态机与工作流服务测试。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from intern_platform.db.base import Base
import intern_platform.models  # noqa: F401
from intern_platform.models.application import Application
from intern_platform.models.audit_log import AuditLog
from intern_platform.models.community import Community
from intern_platform.models.project import Project
from intern_platform.models.review_record import ReviewRecord
from intern_platform.models.user import User
from intern_platform.models.workflow_event import WorkflowEvent
from intern_platform.services.application_workflow import (
    ApplicationWorkflowService,
    TransitionContext,
)
from intern_platform.services.state_machine import (
    IllegalTransitionError,
    allowed_actions,
    resolve_transition,
)


@pytest.fixture()
def session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = SessionLocal()
    try:
        user = User(
            email="student@test.local",
            password_hash="x",
            display_name="学生",
            auth_provider="local",
        )
        mentor = User(
            email="mentor@test.local",
            password_hash="x",
            display_name="导师",
            auth_provider="local",
        )
        db.add_all([user, mentor])
        db.flush()
        community = Community(
            name="测试社区",
            slug="test",
            status="approved",
            applicant_user_id=user.id,
        )
        db.add(community)
        db.flush()
        project = Project(
            community_id=community.id,
            mentor_id=mentor.id,
            title="测试项目",
            quota=1,
            status="published",
        )
        db.add(project)
        db.flush()
        app = Application(
            project_id=project.id,
            student_id=user.id,
            statement="hello",
            status="draft",
            current_node="none",
        )
        db.add(app)
        db.commit()
        yield db
    finally:
        db.close()
        engine.dispose()


def test_resolve_legal_and_illegal() -> None:
    assert resolve_transition("draft", "submit").value == "submitted"
    with pytest.raises(IllegalTransitionError):
        resolve_transition("draft", "approve_mentor")
    assert "submit" in allowed_actions("draft")


def test_transition_writes_three_ledgers(session: Session) -> None:
    app = session.scalar(select(Application).limit(1))
    assert app is not None
    svc = ApplicationWorkflowService(session)
    result = svc.transition(
        app,
        TransitionContext(
            actor_id=app.student_id,
            action="submit",
            actor_role="student",
            request_id="req-1",
            idempotency_key="idem-1",
            trace_id="trace-1",
        ),
    )
    session.commit()

    assert result.to_status == "submitted"
    assert result.idempotent_replay is False

    reviews = list(session.scalars(select(ReviewRecord)).all())
    audits = list(session.scalars(select(AuditLog)).all())
    events = list(session.scalars(select(WorkflowEvent)).all())
    assert len(reviews) == 1
    assert reviews[0].seq_no == 1
    assert reviews[0].actor_role == "student"
    assert reviews[0].decision_code == "SUBMIT"
    assert reviews[0].request_id == "req-1"
    assert len(audits) == 1
    assert audits[0].outcome == "SUCCESS"
    assert audits[0].trace_id == "trace-1"
    assert audits[0].seq_no == 1
    assert len(audits[0].event_hash) == 64
    assert audits[0].prev_hash == "0" * 64
    assert len(events) == 1
    assert events[0].seq_no == 1
    assert events[0].correlation_id == "req-1"


def test_idempotent_replay_no_double_write(session: Session) -> None:
    app = session.scalar(select(Application).limit(1))
    assert app is not None
    svc = ApplicationWorkflowService(session)
    ctx = TransitionContext(
        actor_id=app.student_id,
        action="submit",
        actor_role="student",
        idempotency_key="same-key",
        request_id="req-a",
    )
    first = svc.transition(app, ctx)
    session.commit()
    second = svc.transition(app, ctx)
    session.commit()

    assert first.idempotent_replay is False
    assert second.idempotent_replay is True
    assert second.to_status == "submitted"
    assert len(list(session.scalars(select(ReviewRecord)).all())) == 1
    assert len(list(session.scalars(select(AuditLog)).all())) == 1


def test_illegal_transition_writes_fail_audit(session: Session) -> None:
    app = session.scalar(select(Application).limit(1))
    assert app is not None
    svc = ApplicationWorkflowService(session)
    with pytest.raises(IllegalTransitionError):
        svc.transition(
            app,
            TransitionContext(
                actor_id=app.student_id,
                action="approve_mentor",
                actor_role="mentor",
                request_id="req-fail",
                trace_id="trace-fail",
            ),
        )
    session.commit()

    assert app.status == "draft"
    assert len(list(session.scalars(select(ReviewRecord)).all())) == 0
    audits = list(session.scalars(select(AuditLog)).all())
    assert len(audits) == 1
    assert audits[0].outcome == "FAIL"
    assert audits[0].action == "application.approve_mentor"
    assert len(list(session.scalars(select(WorkflowEvent)).all())) == 0
