"""申请状态迁移服务：单事务写 review + audit + workflow。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from intern_platform.models.application import Application
from intern_platform.repositories.audit_log import AuditLogRepository
from intern_platform.repositories.review_record import ReviewRecordRepository
from intern_platform.repositories.workflow_event import WorkflowEventRepository
from intern_platform.services.state_machine import (
    STATUS_NODE,
    ApplicationStatus,
    IllegalTransitionError,
    resolve_transition,
)


class OptimisticLockError(Exception):
    """乐观锁冲突：applications.version 不匹配。"""

    def __init__(self, application_id: int, expected: int, actual: int) -> None:
        self.application_id = application_id
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"乐观锁冲突: application_id={application_id} "
            f"expected_version={expected} actual_version={actual}"
        )


@dataclass(frozen=True)
class TransitionContext:
    actor_id: int
    action: str
    actor_role: str = "unknown"
    comment: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    idempotency_key: str | None = None
    trace_id: str | None = None
    ip: str | None = None
    user_agent: str | None = None
    expected_version: int | None = None


@dataclass(frozen=True)
class TransitionResult:
    application: Application
    from_status: str
    to_status: str
    action: str
    idempotent_replay: bool = False
    mail_sent: bool | None = None
    mail_hint: str | None = None


def _ensure_ids(ctx: TransitionContext) -> TransitionContext:
    """保证 request_id / trace_id 始终有值并持久化。"""
    request_id = ctx.request_id or str(uuid4())
    trace_id = ctx.trace_id or request_id
    if request_id == ctx.request_id and trace_id == ctx.trace_id:
        return ctx
    return TransitionContext(
        actor_id=ctx.actor_id,
        action=ctx.action,
        actor_role=ctx.actor_role,
        comment=ctx.comment,
        request_id=request_id,
        correlation_id=ctx.correlation_id or request_id,
        causation_id=ctx.causation_id,
        idempotency_key=ctx.idempotency_key,
        trace_id=trace_id,
        ip=ctx.ip,
        user_agent=ctx.user_agent,
        expected_version=ctx.expected_version,
    )


class ApplicationWorkflowService:
    """集中状态机 + 企业级审计流水。"""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.reviews = ReviewRecordRepository(session)
        self.audits = AuditLogRepository(session)
        self.events = WorkflowEventRepository(session)

    def _write_fail_audit(
        self,
        application: Application,
        ctx: TransitionContext,
        *,
        action_name: str,
        before: dict[str, Any],
        detail: dict[str, Any] | None = None,
    ) -> None:
        after = detail
        self.audits.create(
            actor_id=ctx.actor_id,
            actor_role=ctx.actor_role,
            action=action_name,
            resource_type="application",
            resource_id=application.id,
            before=before,
            after=after,
            outcome="FAIL",
            request_id=ctx.request_id,
            trace_id=ctx.trace_id,
            idempotency_key=None,
            ip=ctx.ip,
            user_agent=ctx.user_agent,
        )
        self.session.flush()

    def transition(
        self,
        application: Application,
        ctx: TransitionContext,
    ) -> TransitionResult:
        ctx = _ensure_ids(ctx)

        # 幂等：同 idempotency_key 已成功写入 review_records 则直接回放
        if ctx.idempotency_key:
            existing = self.reviews.get_by_idempotency_key(ctx.idempotency_key)
            if existing is not None:
                return TransitionResult(
                    application=application,
                    from_status=existing.from_status,
                    to_status=existing.to_status,
                    action=existing.action,
                    idempotent_replay=True,
                )

        from_status = application.status
        correlation_id = ctx.correlation_id or ctx.request_id
        before_base: dict[str, Any] = {
            "status": application.status,
            "current_node": application.current_node,
            "version": application.version,
        }

        # 乐观锁
        if ctx.expected_version is not None and ctx.expected_version != application.version:
            self._write_fail_audit(
                application,
                ctx,
                action_name=f"application.{ctx.action}",
                before=before_base,
                detail={
                    "reason": "optimistic_lock",
                    "expected_version": ctx.expected_version,
                    "actual_version": application.version,
                },
            )
            raise OptimisticLockError(
                application.id, ctx.expected_version, application.version
            )

        try:
            to_status = resolve_transition(from_status, ctx.action)
        except IllegalTransitionError as exc:
            self._write_fail_audit(
                application,
                ctx,
                action_name=f"application.{ctx.action}",
                before=before_base,
            )
            raise exc

        before: dict[str, Any] = {
            "status": application.status,
            "current_node": application.current_node,
            "version": application.version,
        }

        application.status = to_status.value
        application.current_node = STATUS_NODE[to_status]
        application.version = int(application.version or 0) + 1

        after: dict[str, Any] = {
            "status": application.status,
            "current_node": application.current_node,
            "version": application.version,
        }

        self.reviews.create(
            application_id=application.id,
            from_status=from_status,
            to_status=to_status.value,
            action=ctx.action,
            actor_id=ctx.actor_id,
            actor_role=ctx.actor_role,
            comment=ctx.comment,
            request_id=ctx.request_id,
            idempotency_key=ctx.idempotency_key,
        )

        self.audits.create(
            actor_id=ctx.actor_id,
            actor_role=ctx.actor_role,
            action=f"application.{ctx.action}",
            resource_type="application",
            resource_id=application.id,
            before=before,
            after=after,
            outcome="SUCCESS",
            request_id=ctx.request_id,
            trace_id=ctx.trace_id,
            idempotency_key=ctx.idempotency_key,
            ip=ctx.ip,
            user_agent=ctx.user_agent,
        )

        self.events.create(
            event_type=f"application.{ctx.action}",
            aggregate_type="application",
            aggregate_id=application.id,
            payload={
                "from_status": from_status,
                "to_status": to_status.value,
                "action": ctx.action,
                "actor_id": ctx.actor_id,
                "actor_role": ctx.actor_role,
                "comment": ctx.comment,
                "version": application.version,
            },
            request_id=ctx.request_id,
            causation_id=ctx.causation_id,
            correlation_id=correlation_id,
            idempotency_key=ctx.idempotency_key,
            actor_id=ctx.actor_id,
            actor_role=ctx.actor_role,
        )

        self.session.flush()
        return TransitionResult(
            application=application,
            from_status=from_status,
            to_status=to_status.value,
            action=ctx.action,
        )

    def transition_by_id(
        self,
        application_id: int,
        ctx: TransitionContext,
        *,
        commit: bool = True,
    ) -> TransitionResult:
        application = self.session.get(Application, application_id)
        if application is None:
            raise LookupError(f"申请不存在: id={application_id}")
        try:
            result = self.transition(application, ctx)
        except (IllegalTransitionError, OptimisticLockError):
            if commit:
                self.session.commit()
            raise
        if commit:
            self.session.commit()
        return result


__all__ = [
    "ApplicationStatus",
    "ApplicationWorkflowService",
    "IllegalTransitionError",
    "OptimisticLockError",
    "TransitionContext",
    "TransitionResult",
]
