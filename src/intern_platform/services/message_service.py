"""申请留言 / 进展 / 中期反馈服务。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from intern_platform.dependencies.auth import AuthUser
from intern_platform.dependencies.ledger import LedgerRequestContext
from intern_platform.models.application import Application
from intern_platform.models.application_message import ApplicationMessage
from intern_platform.models.project import Project
from intern_platform.repositories.audit_log import AuditLogRepository
from intern_platform.schemas.business import MessageCreate, MessageOut
from intern_platform.services.message_codec import (
    pack_deliverable_message,
    pack_message,
    unpack_deliverable,
    unpack_message,
)
from intern_platform.services.notification_service import NotificationService

# 学生可写进展/中期：导师通过名额预留后即可（不必等社区/组委会）
_STUDENT_LOG_STATUSES = frozenset(
    {
        "community_review",
        "committee_review",
        "selected",
        "in_progress",
        "final_rejected",
        "final_submitted",
        "mentor_final_review",
        "committee_final_review",
    }
)


class MessageService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.audits = AuditLogRepository(session)

    def _can_access(self, auth: AuthUser, app: Application) -> bool:
        if app.student_id == auth.id or auth.has_role("committee"):
            return True
        project = self.session.get(Project, app.project_id)
        if project is None:
            return False
        if project.mentor_id == auth.id:
            return True
        return auth.has_community_role("community_admin", project.community_id)

    def _to_out(self, msg: ApplicationMessage) -> MessageOut:
        parsed = unpack_deliverable(msg.body)
        kind = str(parsed.get("kind") or "note")
        text = str(parsed.get("text") or "")
        # 非结构化旧留言：unpack_deliverable 已把全文放进 text
        if kind in ("feedback", "note") and not parsed.get("attachment_url"):
            _k, plain = unpack_message(msg.body)
            kind, text = _k, plain
        return MessageOut(
            id=msg.id,
            application_id=msg.application_id,
            sender_id=msg.sender_id,
            body=text,
            kind=kind,
            design_doc_url=str(parsed.get("design_doc_url") or "") or None,
            code_url=str(parsed.get("code_url") or "") or None,
            attachment_url=str(parsed.get("attachment_url") or "") or None,
            attachment_name=str(parsed.get("attachment_name") or "") or None,
            created_at=msg.created_at,
        )

    def list_messages(self, auth: AuthUser, application_id: int) -> list[MessageOut]:
        app = self.session.get(Application, application_id)
        if app is None:
            raise LookupError("申请不存在")
        if not self._can_access(auth, app):
            raise PermissionError("无权查看进展与反馈")
        stmt = (
            select(ApplicationMessage)
            .where(ApplicationMessage.application_id == application_id)
            .order_by(ApplicationMessage.id.asc())
        )
        return [self._to_out(r) for r in self.session.scalars(stmt).all()]

    def post(
        self,
        auth: AuthUser,
        application_id: int,
        body: MessageCreate,
        ledger: LedgerRequestContext,
    ) -> MessageOut:
        app = self.session.get(Application, application_id)
        if app is None:
            raise LookupError("申请不存在")
        if not self._can_access(auth, app):
            raise PermissionError("无权发布")

        kind = (body.kind or "note").strip() or "note"
        is_student = app.student_id == auth.id
        is_staff = auth.has_role("mentor", "community_admin", "committee") or (
            not is_student and self._can_access(auth, app)
        )

        if kind in ("progress", "midterm", "acceptance"):
            if not is_student:
                raise PermissionError("仅学生可提交进展或验收材料说明")
            if app.status not in _STUDENT_LOG_STATUSES:
                raise ValueError("当前尚未进入开发阶段（需导师通过并预留名额后）")
            design = (body.design_doc_url or "").strip() or "暂无"
            code = (body.code_url or "").strip() or "暂无"
            packed = pack_deliverable_message(
                kind,
                text=body.body,
                design_doc_url=design,
                code_url=code,
                attachment_url=(body.attachment_url or "").strip(),
                attachment_name=(body.attachment_name or "").strip(),
            )
        elif kind == "feedback":
            if not is_staff:
                raise PermissionError("仅导师/组织侧可写反馈")
            # 名额预留后导师应可随时留言（开发指导）
            if app.status in (
                "draft",
                "submitted",
                "withdrawn",
                "completed",
            ):
                raise ValueError("当前状态不可发送导师留言")
            packed = pack_message(kind, body.body)
        elif kind != "note":
            raise ValueError("不支持的留言类型")
        else:
            packed = pack_message(kind, body.body)

        if not packed.strip():
            raise ValueError("内容不能为空")

        msg = ApplicationMessage(
            application_id=application_id,
            sender_id=auth.id,
            body=packed,
        )
        self.session.add(msg)
        self.session.flush()
        self.audits.create(
            actor_id=auth.id,
            actor_role=auth.primary_actor_role(
                "student", "mentor", "community_admin", "committee"
            ),
            action=f"application.message.{kind}",
            resource_type="application",
            resource_id=application_id,
            after={"message_id": msg.id, "kind": kind},
            outcome="SUCCESS",
            request_id=ledger.request_id,
            trace_id=ledger.trace_id,
            ip=ledger.ip,
            user_agent=ledger.user_agent,
        )

        self._notify(app, auth, kind, body.body.strip())

        self.session.commit()
        self.session.refresh(msg)
        return self._to_out(msg)

    def _notify(
        self, app: Application, auth: AuthUser, kind: str, text: str
    ) -> None:
        project = self.session.get(Project, app.project_id)
        title_map = {
            "progress": "学生更新了实习进展",
            "midterm": "学生提交了中期反馈",
            "acceptance": "学生提交了验收材料",
            "feedback": "导师回复了反馈",
        }
        title = title_map.get(kind)
        if not title:
            return
        snippet = text[:180] + ("…" if len(text) > 180 else "")
        proj_name = project.title if project else f"项目#{app.project_id}"
        body = f"「{proj_name}」{snippet}"
        ns = NotificationService(self.session)
        if kind in ("progress", "midterm", "acceptance") and project and project.mentor_id:
            ns.create(
                user_id=project.mentor_id,
                title=title,
                body=body,
                kind=f"app_{kind}",
                project_id=app.project_id,
                application_id=app.id,
            )
        elif kind == "feedback":
            ns.create(
                user_id=app.student_id,
                title=title,
                body=body,
                kind="app_feedback",
                project_id=app.project_id,
                application_id=app.id,
            )
