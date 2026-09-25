"""结项服务。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from intern_platform.dependencies.auth import AuthUser
from intern_platform.dependencies.ledger import LedgerRequestContext
from intern_platform.models.application import Application
from intern_platform.models.community_extension import CommunityExtension
from intern_platform.models.final_submission import FinalSubmission
from intern_platform.models.project import Project
from intern_platform.schemas.business import FinalUpsert
from intern_platform.services.application_workflow import (
    ApplicationWorkflowService,
    TransitionContext,
)
from intern_platform.services.schema_validate import dumps_extra, validate_extra_fields

# 验收审核中（不可再交）
_ACCEPTANCE_PENDING = frozenset(
    {"final_submitted", "mentor_final_review", "committee_final_review"}
)
_CAN_EDIT_FINAL = frozenset(
    {
        "community_review",
        "committee_review",
        "selected",
        "in_progress",
        "final_rejected",
    }
)


class FinalService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.workflow = ApplicationWorkflowService(session)

    def upsert(self, auth: AuthUser, application_id: int, body: FinalUpsert) -> FinalSubmission:
        app = self.session.get(Application, application_id)
        if app is None:
            raise LookupError("申请不存在")
        if app.student_id != auth.id:
            raise PermissionError("仅本人可编辑结项材料")
        if app.status in _ACCEPTANCE_PENDING:
            raise ValueError("验收审核中，暂不可修改结项材料")
        if app.status not in _CAN_EDIT_FINAL:
            raise ValueError(f"当前状态不可编辑结项: {app.status}")

        project = self.session.get(Project, app.project_id)
        assert project is not None
        ext = self.session.scalar(
            select(CommunityExtension).where(
                CommunityExtension.community_id == project.community_id
            )
        )
        validate_extra_fields(ext.final_schema if ext else None, body.extra_fields)

        row = self.session.scalar(
            select(FinalSubmission).where(FinalSubmission.application_id == application_id)
        )
        if row is None:
            row = FinalSubmission(
                application_id=application_id,
                pr_mr_url=body.pr_mr_url,
                report_url=body.report_url,
                report_text=body.report_text,
                extra_fields=dumps_extra(body.extra_fields),
                status="draft",
            )
            self.session.add(row)
        else:
            row.pr_mr_url = body.pr_mr_url
            row.report_url = body.report_url
            row.report_text = body.report_text
            row.extra_fields = dumps_extra(body.extra_fields)
        self.session.commit()
        self.session.refresh(row)
        return row

    def submit(
        self,
        auth: AuthUser,
        application_id: int,
        ledger: LedgerRequestContext,
        idempotency_key: str,
    ) -> Application:
        app = self.session.get(Application, application_id)
        if app is None:
            raise LookupError("申请不存在")
        if app.student_id != auth.id:
            raise PermissionError("仅本人可提交结项")
        final = self.session.scalar(
            select(FinalSubmission).where(FinalSubmission.application_id == application_id)
        )
        if final is None or not final.pr_mr_url:
            raise ValueError("请先保存结项材料（含 pr_mr_url）")

        if app.status in _ACCEPTANCE_PENDING:
            raise ValueError("已有验收在审核中，请等待审完（未通过后方可再次提交）")

        def _tx(action: str, suffix: str) -> None:
            self.workflow.transition(
                app,
                TransitionContext(
                    actor_id=auth.id,
                    action=action,
                    actor_role="student",
                    request_id=ledger.request_id,
                    idempotency_key=f"{idempotency_key}:{suffix}",
                    trace_id=ledger.trace_id,
                    ip=ledger.ip,
                    user_agent=ledger.user_agent,
                ),
            )

        if app.status in ("community_review", "committee_review", "selected"):
            _tx("start_progress", "start_progress")
        if app.status not in ("in_progress", "final_rejected"):
            raise ValueError(f"当前状态不可提交验收: {app.status}")
        _tx("submit_final", "submit_final")
        _tx("start_mentor_final", "start_mentor_final")

        final.status = "submitted"
        self.session.commit()
        self.session.refresh(app)
        return app
