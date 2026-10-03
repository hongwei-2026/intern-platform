"""申请留言 / 进展 / 中期反馈服务。"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from intern_platform.dependencies.auth import AuthUser
from intern_platform.dependencies.ledger import LedgerRequestContext
from intern_platform.models.application import Application
from intern_platform.models.application_message import ApplicationMessage
from intern_platform.models.project import Project
from intern_platform.models.role import Role, UserRole
from intern_platform.repositories.audit_log import AuditLogRepository
from intern_platform.schemas.business import MessageCreate, MessageOut
from intern_platform.services.message_codec import (
    pack_deliverable_message,
    pack_message,
    unpack_deliverable,
    unpack_message,
)
from intern_platform.services.notification_service import NotificationService


def community_admin_ids(session: Session, community_id: int) -> list[int]:
    role = session.scalar(select(Role).where(Role.code == "community_admin"))
    if role is None:
        return []
    return list(
        session.scalars(
            select(UserRole.user_id).where(
                UserRole.role_id == role.id,
                UserRole.community_id == community_id,
            )
        ).all()
    )


def committee_user_ids(session: Session) -> list[int]:
    role = session.scalar(select(Role).where(Role.code == "committee"))
    if role is None:
        return []
    return list(session.scalars(select(UserRole.user_id).where(UserRole.role_id == role.id)).all())


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
        community_name = None
        if kind in ("feedback", "note") and not parsed.get("attachment_url"):
            _k, plain = unpack_message(msg.body)
            kind, text = _k, plain
        if kind == "official" and text.startswith("{"):
            try:
                obj = json.loads(text)
            except json.JSONDecodeError:
                obj = None
            if isinstance(obj, dict):
                community_name = str(obj.get("community") or "").strip() or None
                text = str(obj.get("text") or "").strip()
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
            community_name=community_name,
            reward_status=(str(parsed.get("decision") or "pending") if kind == "reward" else None),
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
        elif kind == "reward":
            if not is_student:
                raise PermissionError("仅学生可申请奖励")
            if app.status not in (
                "community_final_review",
                "committee_final_review",
                "completed",
            ):
                raise ValueError("导师验收通过后才能申请奖励")
            attachment = (body.attachment_url or "").strip()
            if not attachment:
                raise ValueError("请上传 ZIP，证明相关 Issue 和 PR 已经关闭")
            prior = self.session.scalars(
                select(ApplicationMessage).where(ApplicationMessage.application_id == app.id)
            ).all()
            for old in prior:
                old_kind, _plain = unpack_message(old.body)
                if old_kind != "reward":
                    continue
                decision = str(unpack_deliverable(old.body).get("decision") or "pending")
                if decision != "rejected":
                    raise ValueError("已经申请过奖励，不能重复提交")
            lines = [line.strip() for line in (body.body or "").splitlines() if line.strip()]
            contacted = any(
                line.startswith(prefix) and line.removeprefix(prefix).strip()
                for line in lines
                for prefix in ("手机：", "邮箱：", "其他联系方式：")
            )
            if not contacted:
                raise ValueError("请至少填写一项联系方式")
            packed = pack_deliverable_message(
                "reward",
                text=body.body,
                attachment_url=attachment,
                attachment_name=(body.attachment_name or "").strip(),
            )
        elif kind == "official":
            project = self.session.get(Project, app.project_id)
            if project is None or not auth.has_community_role(
                "community_admin", project.community_id
            ):
                raise PermissionError("仅本社区管理员可发官方通知")
            if app.status in ("draft", "submitted", "mentor_review", "rejected", "withdrawn"):
                raise ValueError("申请与开发对接由导师负责，社区只在入选后发送正式通知")
            packed = pack_message(kind, body.body)
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

    def decide_reward(
        self, auth: AuthUser, application_id: int, decision: str, note: str | None
    ) -> None:
        """社区通过或驳回学生的奖励申请，并通知学生。"""
        app = self.session.get(Application, application_id)
        if app is None:
            raise LookupError("申请不存在")
        project = self.session.get(Project, app.project_id)
        if project is None or not auth.has_community_role("community_admin", project.community_id):
            raise PermissionError("仅本社区可处理奖励申请")
        if decision not in ("approved", "rejected"):
            raise ValueError("只能通过或驳回")
        reason = (note or "").strip()
        if decision == "rejected" and not reason:
            raise ValueError("驳回时请写下原因")
        messages = self.session.scalars(
            select(ApplicationMessage)
            .where(ApplicationMessage.application_id == app.id)
            .order_by(ApplicationMessage.id.desc())
        ).all()
        target = None
        parsed: dict = {}
        for msg in messages:
            parsed = unpack_deliverable(msg.body)
            if parsed.get("kind") == "reward" and str(parsed.get("decision") or "pending") == "pending":
                target = msg
                break
        if target is None:
            raise LookupError("没有待处理的奖励申请")
        payload = {
            "text": str(parsed.get("text") or ""),
            "design_doc_url": str(parsed.get("design_doc_url") or ""),
            "code_url": str(parsed.get("code_url") or ""),
            "attachment_url": str(parsed.get("attachment_url") or ""),
            "attachment_name": str(parsed.get("attachment_name") or ""),
            "decision": decision,
            "decision_note": reason,
        }
        target.body = pack_message("reward", json.dumps(payload, ensure_ascii=False))
        self.session.add(target)
        title = "社区已通过奖励申请" if decision == "approved" else "社区驳回了奖励申请"
        detail = reason or "请等待社区通知发放。"
        NotificationService(self.session).create(
            user_id=app.student_id,
            title=title,
            body=f"「{project.title}」{detail}",
            kind="app_reward_result",
            project_id=app.project_id,
            application_id=app.id,
        )
        self.session.commit()

    def _notify(
        self, app: Application, auth: AuthUser, kind: str, text: str
    ) -> None:
        project = self.session.get(Project, app.project_id)
        title_map = {
            "progress": "学生更新了实习进展",
            "midterm": "学生提交了中期反馈",
            "acceptance": "学生提交了验收材料",
            "feedback": "导师回复了反馈",
            "official": "社区发来重要通知",
            "reward": "学生提交了奖励申请",
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
        elif kind == "reward" and project is not None:
            for user_id in community_admin_ids(self.session, project.community_id):
                ns.create(
                    user_id=user_id,
                    title=title,
                    body=body,
                    kind="app_reward",
                    project_id=app.project_id,
                    application_id=app.id,
                )
        elif kind in ("feedback", "official"):
            ns.create(
                user_id=app.student_id,
                title=title,
                body=body,
                kind="app_feedback" if kind == "feedback" else "app_official",
                project_id=app.project_id,
                application_id=app.id,
            )
