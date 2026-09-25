"""哈希链与账本序号测试。"""

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
from intern_platform.models.user import User
from intern_platform.models.workflow_event import WorkflowEvent
from intern_platform.repositories.audit_log import AuditLogRepository
from intern_platform.repositories.workflow_event import WorkflowEventRepository
from intern_platform.services.application_workflow import (
    ApplicationWorkflowService,
    TransitionContext,
)
from intern_platform.services.ledger import (
    GENESIS_HASH,
    compute_event_hash,
    verify_audit_chain,
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
        student = User(
            email="s@test.local",
            password_hash="x",
            display_name="S",
            auth_provider="local",
        )
        mentor = User(
            email="m@test.local",
            password_hash="x",
            display_name="M",
            auth_provider="local",
        )
        db.add_all([student, mentor])
        db.flush()
        community = Community(name="C", slug="c", status="approved")
        db.add(community)
        db.flush()
        project = Project(
            community_id=community.id,
            mentor_id=mentor.id,
            title="P",
            quota=1,
            status="published",
        )
        db.add(project)
        db.flush()
        db.add(
            Application(
                project_id=project.id,
                student_id=student.id,
                status="draft",
                current_node="none",
            )
        )
        db.commit()
        yield db
    finally:
        db.close()
        engine.dispose()


def test_compute_event_hash_canonical() -> None:
    a = compute_event_hash({"b": 1, "a": 2})
    b = compute_event_hash({"a": 2, "b": 1})
    assert a == b
    assert len(a) == 64
    assert a != compute_event_hash({"a": 2, "b": 3})


def test_audit_chain_links_and_verifies(session: Session) -> None:
    audits = AuditLogRepository(session)
    first = audits.create(
        action="ping",
        resource_type="system",
        resource_id="0",
        actor_id=None,
        actor_role="system",
        outcome="SUCCESS",
        request_id="r1",
        trace_id="t1",
    )
    second = audits.create(
        action="pong",
        resource_type="system",
        resource_id="0",
        actor_role="system",
        outcome="SUCCESS",
        request_id="r2",
        trace_id="t2",
    )
    session.commit()

    assert first.seq_no == 1
    assert first.prev_hash == GENESIS_HASH
    assert second.seq_no == 2
    assert second.prev_hash == first.event_hash

    ok, err = verify_audit_chain(session)
    assert ok is True
    assert err is None


def test_tamper_breaks_verify(session: Session) -> None:
    audits = AuditLogRepository(session)
    audits.create(
        action="ok",
        resource_type="system",
        resource_id="1",
        outcome="SUCCESS",
    )
    session.flush()
    row = session.scalar(select(AuditLog).limit(1))
    assert row is not None
    # 直接篡改（绕过仓库）破坏哈希链
    row.action = "tampered"
    session.commit()

    ok, err = verify_audit_chain(session)
    assert ok is False
    assert err is not None
    assert "event_hash mismatch" in err


def test_workflow_chain_per_aggregate(session: Session) -> None:
    events = WorkflowEventRepository(session)
    e1 = events.create(
        event_type="application.submit",
        aggregate_type="application",
        aggregate_id="1",
        payload={"n": 1},
        actor_id=1,
        actor_role="student",
    )
    e2 = events.create(
        event_type="application.start_mentor_review",
        aggregate_type="application",
        aggregate_id="1",
        payload={"n": 2},
        actor_id=2,
        actor_role="mentor",
    )
    other = events.create(
        event_type="application.submit",
        aggregate_type="application",
        aggregate_id="2",
        payload={"n": 1},
        actor_id=1,
        actor_role="student",
    )
    session.commit()

    assert e1.seq_no == 1 and e1.prev_hash == GENESIS_HASH
    assert e2.seq_no == 2 and e2.prev_hash == e1.event_hash
    assert other.seq_no == 1 and other.prev_hash == GENESIS_HASH


def test_transition_builds_valid_audit_chain(session: Session) -> None:
    app = session.scalar(select(Application).limit(1))
    assert app is not None
    svc = ApplicationWorkflowService(session)

    svc.transition(
        app,
        TransitionContext(
            actor_id=app.student_id,
            action="submit",
            actor_role="student",
            request_id="req-chain",
        ),
    )
    # 故意非法一次，也应进入审计链
    with pytest.raises(Exception):
        svc.transition(
            app,
            TransitionContext(
                actor_id=app.student_id,
                action="approve_committee",
                actor_role="committee",
                request_id="req-bad",
            ),
        )
    svc.transition(
        app,
        TransitionContext(
            actor_id=app.student_id,
            action="start_mentor_review",
            actor_role="mentor",
            request_id="req-2",
        ),
    )
    session.commit()

    ok, err = verify_audit_chain(session)
    assert ok is True, err
    outcomes = [r.outcome for r in session.scalars(select(AuditLog).order_by(AuditLog.seq_no))]
    assert outcomes == ["SUCCESS", "FAIL", "SUCCESS"]

    wf = list(
        session.scalars(
            select(WorkflowEvent)
            .where(WorkflowEvent.aggregate_id == str(app.id))
            .order_by(WorkflowEvent.seq_no)
        )
    )
    assert len(wf) == 2
    assert wf[0].prev_hash == GENESIS_HASH
    assert wf[1].prev_hash == wf[0].event_hash
