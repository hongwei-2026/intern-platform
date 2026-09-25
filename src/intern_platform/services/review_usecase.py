"""审核用例：decision + 节点 + 角色 → 状态机 action，并做资源范围校验。"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from intern_platform.dependencies.auth import AuthUser
from intern_platform.dependencies.ledger import LedgerRequestContext
from intern_platform.models.application import Application
from intern_platform.models.project import Project
from intern_platform.repositories.audit_log import AuditLogRepository
from intern_platform.services.application_workflow import (
    ApplicationWorkflowService,
    OptimisticLockError,
    TransitionContext,
    TransitionResult,
)
from intern_platform.services.state_machine import IllegalTransitionError


class AuthorizationError(PermissionError):
    """资源范围或角色不匹配。"""


@dataclass(frozen=True)
class ReviewDecision:
    decision: str  # approve | reject
    comment: str | None = None
    expected_version: int | None = None
    is_final: bool = False


def _load_application(session: Session, application_id: int) -> Application:
    app = session.get(
        Application,
        application_id,
        options=(joinedload(Application.project).joinedload(Project.community),),
    )
    if app is None:
        raise LookupError(f"申请不存在: id={application_id}")
    return app


def resolve_actions(
    *,
    decision: str,
    status_value: str,
    actor_role: str,
    is_final: bool = False,
) -> list[str]:
    """将业务决策映射为状态机 action 序列（不改 TRANSITION_MAP）。"""
    decision = decision.lower()
    if is_final:
        if decision == "approve":
            if actor_role != "mentor" and actor_role != "committee":
                raise AuthorizationError("结项审核角色无效")
            if status_value == "final_submitted":
                if actor_role != "mentor":
                    raise AuthorizationError("仅导师可从 final_submitted 启动结项审")
                return ["start_mentor_final", "approve_mentor_final"]
            if status_value == "mentor_final_review":
                if actor_role != "mentor":
                    raise AuthorizationError("当前节点需导师结项审")
                return ["approve_mentor_final"]
            if status_value == "committee_final_review":
                if actor_role != "committee":
                    raise AuthorizationError("当前节点需组委会结项审")
                return ["approve_committee_final"]
            raise AuthorizationError(f"当前状态不可结项通过: {status_value}")
        if decision == "reject":
            if status_value in ("mentor_final_review",) and actor_role == "mentor":
                return ["reject_final"]
            if status_value in ("committee_final_review",) and actor_role == "committee":
                return ["reject_final"]
            raise AuthorizationError("当前节点/角色不可结项驳回")
        raise AuthorizationError(f"未知 decision: {decision}")

    # 选拔审核
    if decision == "approve":
        if actor_role == "mentor":
            if status_value == "submitted":
                return ["start_mentor_review", "approve_mentor"]
            if status_value == "mentor_review":
                return ["approve_mentor"]
            raise AuthorizationError(f"导师不可在状态 {status_value} 通过")
        if actor_role == "community_admin":
            if status_value == "community_review":
                return ["approve_community"]
            raise AuthorizationError(f"社区管理员不可在状态 {status_value} 通过")
        if actor_role == "committee":
            if status_value == "committee_review":
                return ["approve_committee"]
            raise AuthorizationError(f"组委会不可在状态 {status_value} 通过")
        raise AuthorizationError("无审核角色")

    if decision == "reject":
        if actor_role == "mentor" and status_value == "submitted":
            # 已提交但尚未进入导师审：先切入节点再驳回
            return ["start_mentor_review", "reject"]
        if actor_role == "mentor" and status_value == "mentor_review":
            return ["reject"]
        if actor_role == "community_admin" and status_value == "community_review":
            return ["reject"]
        if actor_role == "committee" and status_value == "committee_review":
            return ["reject"]
        raise AuthorizationError("当前申请状态不支持此操作，请刷新页面后重试")

    raise AuthorizationError(f"未知 decision: {decision}")


class ReviewUseCase:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.workflow = ApplicationWorkflowService(session)
        self.audits = AuditLogRepository(session)

    def assert_resource_scope(
        self,
        auth: AuthUser,
        application: Application,
        actor_role: str,
    ) -> None:
        project = application.project
        if project is None:
            project = self.session.get(Project, application.project_id)
        if project is None:
            raise LookupError("项目不存在")

        if actor_role == "mentor":
            if project.mentor_id != auth.id:
                raise AuthorizationError("仅项目导师可审核")
            return
        if actor_role == "community_admin":
            if not auth.has_community_role("community_admin", project.community_id):
                raise AuthorizationError("仅同社区管理员可审核")
            return
        if actor_role == "committee":
            if not auth.has_role("committee"):
                raise AuthorizationError("需要组委会角色")
            return
        raise AuthorizationError(f"不支持的审核角色: {actor_role}")

    def pick_actor_role(
        self,
        auth: AuthUser,
        *,
        status_value: str,
        is_final: bool = False,
    ) -> str:
        if is_final:
            if status_value in ("final_submitted", "mentor_final_review") and auth.has_role(
                "mentor"
            ):
                return "mentor"
            if status_value == "committee_final_review" and auth.has_role("committee"):
                return "committee"
            return auth.primary_actor_role("mentor", "committee")

        if status_value in ("submitted", "mentor_review") and auth.has_role("mentor"):
            return "mentor"
        if status_value == "community_review" and (
            auth.has_role("community_admin") or auth.has_role("committee")
        ):
            # 组委会可代审时仍用 community_admin 语义？严格按角色：优先社区管理员
            if auth.has_role("community_admin"):
                return "community_admin"
            return "committee"
        if status_value == "committee_review" and auth.has_role("committee"):
            return "committee"
        return auth.primary_actor_role("mentor", "community_admin", "committee")

    def _pending_designs(self, project_id: int) -> list[Application]:
        from sqlalchemy import select

        return list(
            self.session.scalars(
                select(Application)
                .where(
                    Application.project_id == project_id,
                    Application.status.in_(("submitted", "mentor_review")),
                )
                .order_by(Application.created_at.asc(), Application.id.asc())
            ).all()
        )

    def _assert_design_slot(self, application: Application) -> None:
        from intern_platform.services.project_presenters import seat_taken_count

        project = application.project or self.session.get(Project, application.project_id)
        if project is None:
            return
        quota = int(project.quota or 0)
        taken = seat_taken_count(self.session, project.id)
        if taken >= quota:
            raise AuthorizationError("人选已满，设计文档审核已关闭，不能再通过")
        pending = self._pending_designs(project.id)
        window = max(0, quota - taken)
        allowed_ids = {row.id for row in pending[:window]}
        if application.id not in allowed_ids:
            raise AuthorizationError("请先审核更早提交的设计文档，超出名额的稍后排队")

    def _close_design_reviews_if_full(self, application: Application, auth: AuthUser) -> None:
        from intern_platform.services.notification_service import NotificationService
        from intern_platform.services.project_presenters import seat_taken_count

        project = application.project or self.session.get(Project, application.project_id)
        if project is None:
            return
        if seat_taken_count(self.session, project.id) < int(project.quota or 0):
            return
        note = "人选已满，设计文档审核已关闭"
        for row in self._pending_designs(project.id):
            try:
                if row.status == "submitted":
                    self.workflow.transition(
                        row,
                        TransitionContext(
                            actor_id=auth.id,
                            action="start_mentor_review",
                            actor_role="mentor",
                            comment="系统：进入导师审核",
                            request_id=f"close-start-{row.id}",
                            correlation_id=f"close-start-{row.id}",
                            idempotency_key=f"close-start-{row.id}-v{row.version}",
                            trace_id=f"close-{row.id}",
                        ),
                    )
                self.workflow.transition(
                    row,
                    TransitionContext(
                        actor_id=auth.id,
                        action="reject",
                        actor_role="mentor",
                        comment=note,
                        request_id=f"close-reject-{row.id}",
                        correlation_id=f"close-reject-{row.id}",
                        idempotency_key=f"close-reject-{row.id}-v{row.version}",
                        trace_id=f"close-{row.id}",
                    ),
                )
                NotificationService(self.session).create(
                    user_id=row.student_id,
                    title="设计审核已关闭",
                    body=f"「{project.title}」{note}，未能入选。",
                    kind="app_full",
                    project_id=project.id,
                    application_id=row.id,
                )
            except Exception:
                continue

    def review(
        self,
        *,
        application_id: int,
        auth: AuthUser,
        decision: ReviewDecision,
        ledger: LedgerRequestContext,
        idempotency_key: str,
        commit: bool = True,
    ) -> TransitionResult:
        application = _load_application(self.session, application_id)

        # 幂等回放优先：已成功落账则直接返回，避免节点已变导致误 403
        existing = self.workflow.reviews.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return TransitionResult(
                application=application,
                from_status=existing.from_status,
                to_status=existing.to_status,
                action=existing.action,
                idempotent_replay=True,
            )

        actor_role = self.pick_actor_role(
            auth, status_value=application.status, is_final=decision.is_final
        )

        try:
            self.assert_resource_scope(auth, application, actor_role)
            if (
                decision.decision == "approve"
                and not decision.is_final
                and actor_role == "mentor"
                and application.status in ("submitted", "mentor_review")
            ):
                self._assert_design_slot(application)
            actions = resolve_actions(
                decision=decision.decision,
                status_value=application.status,
                actor_role=actor_role,
                is_final=decision.is_final,
            )
        except AuthorizationError as exc:
            self.audits.create(
                actor_id=auth.id,
                actor_role=actor_role,
                action="application.review",
                resource_type="application",
                resource_id=application_id,
                before={
                    "status": application.status,
                    "current_node": application.current_node,
                },
                after={"reason": str(exc)},
                outcome="FAIL",
                request_id=ledger.request_id,
                trace_id=ledger.trace_id,
                ip=ledger.ip,
                user_agent=ledger.user_agent,
            )
            if commit:
                self.session.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
            ) from exc

        last: TransitionResult | None = None
        for idx, action in enumerate(actions):
            key = idempotency_key if idx == 0 else f"{idempotency_key}#{idx}"
            ctx = TransitionContext(
                actor_id=auth.id,
                action=action,
                actor_role=actor_role,
                comment=decision.comment,
                request_id=ledger.request_id,
                correlation_id=ledger.request_id,
                idempotency_key=key,
                trace_id=ledger.trace_id,
                ip=ledger.ip,
                user_agent=ledger.user_agent,
                expected_version=(
                    decision.expected_version if idx == 0 else application.version
                ),
            )
            try:
                last = self.workflow.transition(application, ctx)
                # 刷新本地引用
                application = last.application
            except IllegalTransitionError as exc:
                if commit:
                    self.session.commit()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail=str(exc)
                ) from exc
            except OptimisticLockError as exc:
                if commit:
                    self.session.commit()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail=str(exc)
                ) from exc

        assert last is not None
        if (
            not last.idempotent_replay
            and not decision.is_final
            and last.action in ("approve_mentor", "approve_community", "approve_committee")
            and actor_role == "mentor"
        ):
            self._close_design_reviews_if_full(application, auth)

        # 审核意见同步为「导师留言」，学生在申请详情置顶区可见
        if (
            not last.idempotent_replay
            and decision.comment
            and str(decision.comment).strip()
        ):
            from intern_platform.models.application_message import ApplicationMessage
            from intern_platform.services.message_codec import pack_message

            self.session.add(
                ApplicationMessage(
                    application_id=application.id,
                    sender_id=auth.id,
                    body=pack_message("feedback", str(decision.comment).strip()),
                )
            )

        if commit:
            self.session.commit()

        # 站内通知 + 拒绝时发邮件（幂等回放不重复）
        mail_sent: bool | None = None
        mail_hint: str | None = None
        if not last.idempotent_replay:
            try:
                from intern_platform.models.user import User
                from intern_platform.services.notification_service import NotificationService

                student = self.session.get(User, application.student_id)
                project = application.project or self.session.get(Project, application.project_id)
                title = project.title if project else f"项目 #{application.project_id}"
                if student is not None:
                    mail_sent, mail_hint = NotificationService(self.session).notify_review_result(
                        student=student,
                        project_title=title,
                        application_id=application.id,
                        project_id=application.project_id,
                        decision=decision.decision,
                        to_status=last.to_status,
                        comment=decision.comment,
                    )
                    # 有审核意见时再发一条「导师留言」类通知，方便学生点进详情
                    if decision.comment and str(decision.comment).strip():
                        snippet = str(decision.comment).strip()
                        if len(snippet) > 120:
                            snippet = snippet[:120] + "…"
                        NotificationService(self.session).create(
                            user_id=student.id,
                            title="导师回复了反馈",
                            body=f"「{title}」{snippet}",
                            kind="app_feedback",
                            project_id=application.project_id,
                            application_id=application.id,
                        )
                    if commit:
                        self.session.commit()
            except Exception:  # noqa: BLE001
                mail_hint = "站内通知发送异常，请检查服务日志"
                pass

        return TransitionResult(
            application=last.application,
            from_status=last.from_status,
            to_status=last.to_status,
            action=last.action,
            idempotent_replay=last.idempotent_replay,
            mail_sent=mail_sent,
            mail_hint=mail_hint,
        )
