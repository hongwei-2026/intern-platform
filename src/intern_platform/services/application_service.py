"""申请服务（创建/更新/提交；状态变更走工作流）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from intern_platform.dependencies.auth import AuthUser
from intern_platform.dependencies.ledger import LedgerRequestContext
from intern_platform.models.application import Application
from intern_platform.models.community_extension import CommunityExtension
from intern_platform.models.project import Project
from intern_platform.schemas.business import ApplicationCreate, ApplicationUpdate
from intern_platform.services.application_workflow import (
    ApplicationWorkflowService,
    TransitionContext,
)
from intern_platform.services.project_presenters import seat_taken_count
from intern_platform.services.schema_validate import dumps_extra, validate_extra_fields


class ApplicationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.workflow = ApplicationWorkflowService(session)

    def _extension_for_project(self, project: Project) -> CommunityExtension | None:
        return self.session.scalar(
            select(CommunityExtension).where(
                CommunityExtension.community_id == project.community_id
            )
        )

    def create(
        self,
        auth: AuthUser,
        project_id: int,
        body: ApplicationCreate,
        ledger: LedgerRequestContext,
        idempotency_key: str | None = None,
    ) -> Application:
        project = self.session.get(Project, project_id)
        if project is None:
            raise LookupError("项目不存在")
        if project.status != "published":
            raise ValueError("项目未上线，不可申请")
        if auth.has_role("mentor", "community_admin", "committee"):
            raise PermissionError("组织侧账号（导师/社区/组委会）不可申请项目，请使用学生账号")

        # 导师通过后即预留名额；满员则禁止新申请，避免白做材料
        taken = seat_taken_count(self.session, project_id)
        existing = self.session.scalar(
            select(Application).where(
                Application.project_id == project_id,
                Application.student_id == auth.id,
            )
        )
        reopenable = ("rejected", "final_rejected", "withdrawn", "draft")
        already_holds_seat = bool(
            existing
            and existing.status
            in (
                "community_review",
                "committee_review",
                "selected",
                "in_progress",
                "final_submitted",
                "mentor_final_review",
                "committee_final_review",
                "final_rejected",
                "completed",
            )
        )
        if taken >= int(project.quota or 0) and not already_holds_seat:
            raise ValueError(
                f"该项目人选已满（{taken}/{project.quota}），不能再提交设计文档。"
            )

        if existing and existing.status not in reopenable:
            raise ValueError(
                f"已对该项目提交过申请（当前状态：{existing.status}），"
                "审核中或实习进行中不可重复提交；未通过后可点「再次申请」"
            )

        ext = self._extension_for_project(project)
        if body.submit:
            validate_extra_fields(
                ext.application_schema if ext else None, body.extra_fields
            )

        try:
            if existing:
                # 复用同一条申请记录（再次申请 / 继续草稿）
                if existing.status in ("rejected", "final_rejected", "withdrawn"):
                    existing.status = "draft"
                    existing.current_node = "none"
                existing.statement = body.statement
                existing.attachment_url = body.attachment_url
                existing.extra_fields = dumps_extra(body.extra_fields)
                existing.version = int(existing.version or 0) + 1
                self.session.add(existing)
                self.session.flush()
                app = existing
            else:
                app = Application(
                    project_id=project_id,
                    student_id=auth.id,
                    statement=body.statement,
                    attachment_url=body.attachment_url,
                    extra_fields=dumps_extra(body.extra_fields),
                    status="draft",
                    current_node="none",
                    version=0,
                )
                self.session.add(app)
                self.session.flush()

            if body.submit:
                # 每次提交使用独立幂等键，避免再次申请撞上旧流水
                import uuid as _uuid

                base = idempotency_key or f"submit-app-{app.id}"
                key = f"{base}-v{app.version}-{_uuid.uuid4().hex[:8]}"
                self.workflow.transition(
                    app,
                    TransitionContext(
                        actor_id=auth.id,
                        action="submit",
                        actor_role="student",
                        request_id=ledger.request_id,
                        correlation_id=ledger.request_id,
                        idempotency_key=f"{key}:submit",
                        trace_id=ledger.trace_id,
                        ip=ledger.ip,
                        user_agent=ledger.user_agent,
                    ),
                )
                self.workflow.transition(
                    app,
                    TransitionContext(
                        actor_id=auth.id,
                        action="start_mentor_review",
                        actor_role="student",
                        request_id=ledger.request_id,
                        correlation_id=ledger.request_id,
                        idempotency_key=f"{key}:start",
                        trace_id=ledger.trace_id,
                        ip=ledger.ip,
                        user_agent=ledger.user_agent,
                    ),
                )

            self.session.commit()
            self.session.refresh(app)
            return app
        except Exception:
            self.session.rollback()
            raise

    def list_mine(self, auth: AuthUser) -> list[Application]:
        stmt = (
            select(Application)
            .where(Application.student_id == auth.id)
            .options(
                joinedload(Application.project),
                joinedload(Application.student),
                joinedload(Application.review_records),
            )
            .order_by(Application.id.desc())
        )
        return list(self.session.scalars(stmt).unique().all())

    def list_inbox(self, auth: AuthUser) -> list[Application]:
        """当前角色待处理申请队列（导师 / 社区管理员 / 组委会）。"""
        stmt = (
            select(Application)
            .join(Project, Project.id == Application.project_id)
            .options(
                joinedload(Application.project),
                joinedload(Application.student),
                joinedload(Application.review_records),
            )
            .order_by(Application.id.desc())
        )
        if auth.has_role("committee"):
            stmt = stmt.where(
                Application.status.in_(
                    ("committee_review", "mentor_final_review", "committee_final_review")
                )
            )
        elif auth.has_role("community_admin"):
            community_ids = auth.community_ids_for("community_admin")
            has_global = any(
                r.code == "community_admin" and r.community_id is None for r in auth.roles
            )
            stmt = stmt.where(Application.status == "community_review")
            if community_ids and not has_global:
                stmt = stmt.where(Project.community_id.in_(community_ids))
            elif not community_ids and not has_global:
                return []
        elif auth.has_role("mentor"):
            stmt = stmt.where(
                Project.mentor_id == auth.id,
                Application.status != "draft",
            )
        else:
            return []
        rows = list(self.session.scalars(stmt).unique().all())
        # 历史数据可能停在 submitted：导师打开队列时自动切入导师审节点，避免「不可驳回」
        if auth.has_role("mentor"):
            changed = False
            for app in rows:
                if app.status != "submitted":
                    continue
                if app.project is None or app.project.mentor_id != auth.id:
                    continue
                try:
                    self.workflow.transition(
                        app,
                        TransitionContext(
                            actor_id=auth.id,
                            action="start_mentor_review",
                            actor_role="mentor",
                            comment="系统：进入导师审核",
                            request_id=f"auto-start-{app.id}",
                            correlation_id=f"auto-start-{app.id}",
                            idempotency_key=f"auto-start-mentor-{app.id}-v{app.version}",
                            trace_id=f"auto-start-{app.id}",
                        ),
                    )
                    changed = True
                except Exception:  # noqa: BLE001
                    continue
            if changed:
                self.session.commit()
                rows = list(self.session.scalars(stmt).unique().all())
        return rows

    def get(self, application_id: int) -> Application | None:
        return self.session.get(
            Application,
            application_id,
            options=(
                joinedload(Application.project),
                joinedload(Application.student),
                joinedload(Application.review_records),
            ),
        )

    def get_mine_for_project(self, auth: AuthUser, project_id: int) -> Application | None:
        stmt = (
            select(Application)
            .where(
                Application.project_id == project_id,
                Application.student_id == auth.id,
            )
            .options(
                joinedload(Application.project),
                joinedload(Application.review_records),
            )
        )
        return self.session.scalars(stmt).unique().first()

    def can_view(self, auth: AuthUser, app: Application) -> bool:
        if app.student_id == auth.id:
            return True
        if auth.has_role("committee"):
            return True
        project = app.project or self.session.get(Project, app.project_id)
        if project is None:
            return False
        if project.mentor_id == auth.id:
            return True
        return auth.has_community_role("community_admin", project.community_id)

    def update(self, auth: AuthUser, application_id: int, body: ApplicationUpdate) -> Application:
        app = self.get(application_id)
        if app is None:
            raise LookupError("申请不存在")
        if app.student_id != auth.id:
            raise PermissionError("仅本人可修改申请")
        if app.status != "draft":
            raise ValueError("仅 draft 可修改")
        project = self.session.get(Project, app.project_id)
        assert project is not None
        ext = self._extension_for_project(project)
        data = body.model_dump(exclude_unset=True)
        if "extra_fields" in data:
            validate_extra_fields(
                ext.application_schema if ext else None, data["extra_fields"]
            )
            data["extra_fields"] = dumps_extra(data["extra_fields"])
        for key, value in data.items():
            setattr(app, key, value)
        self.session.commit()
        self.session.refresh(app)
        return app

    def submit_for_review(
        self,
        auth: AuthUser,
        application_id: int,
        ledger: LedgerRequestContext,
        idempotency_key: str,
    ) -> Application:
        app = self.get(application_id)
        if app is None:
            raise LookupError("申请不存在")
        if app.student_id != auth.id:
            raise PermissionError("仅本人可提交")
        project = self.session.get(Project, app.project_id)
        assert project is not None
        ext = self._extension_for_project(project)
        extra = None
        if app.extra_fields:
            import json

            extra = json.loads(app.extra_fields)
        validate_extra_fields(ext.application_schema if ext else None, extra)

        if app.status == "draft":
            try:
                self.workflow.transition(
                    app,
                    TransitionContext(
                        actor_id=auth.id,
                        action="submit",
                        actor_role="student",
                        request_id=ledger.request_id,
                        idempotency_key=f"{idempotency_key}:submit",
                        trace_id=ledger.trace_id,
                        ip=ledger.ip,
                        user_agent=ledger.user_agent,
                    ),
                )
            except Exception:
                self.session.commit()
                raise
        if app.status == "submitted":
            try:
                self.workflow.transition(
                    app,
                    TransitionContext(
                        actor_id=auth.id,
                        action="start_mentor_review",
                        actor_role="student",
                        request_id=ledger.request_id,
                        idempotency_key=f"{idempotency_key}:start",
                        trace_id=ledger.trace_id,
                        ip=ledger.ip,
                        user_agent=ledger.user_agent,
                    ),
                )
            except Exception:
                self.session.commit()
                raise
        self.session.commit()
        self.session.refresh(app)
        return app
