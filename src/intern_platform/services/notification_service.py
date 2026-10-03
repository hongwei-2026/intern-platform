"""站内通知服务。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from intern_platform.models.notification import Notification
from intern_platform.models.role import Role, UserRole
from intern_platform.models.user import User
from intern_platform.schemas.notification import NotificationListOut, NotificationOut
from intern_platform.services.mail_service import send_reject_mail


class NotificationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        user_id: int,
        title: str,
        body: str | None = None,
        kind: str = "review",
        project_id: int | None = None,
        application_id: int | None = None,
        commit: bool = False,
    ) -> Notification:
        row = Notification(
            user_id=user_id,
            title=title,
            body=body,
            kind=kind,
            project_id=project_id,
            application_id=application_id,
            is_read=0,
        )
        self.session.add(row)
        self.session.flush()
        if commit:
            self.session.commit()
            self.session.refresh(row)
        return row

    def list_for_user(self, user_id: int, *, limit: int = 30) -> NotificationListOut:
        unread = self.session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == 0)
        )
        rows = list(
            self.session.scalars(
                select(Notification)
                .where(Notification.user_id == user_id)
                .order_by(Notification.id.desc())
                .limit(limit)
            ).all()
        )
        return NotificationListOut(
            items=[NotificationOut.model_validate(r) for r in rows],
            unread_count=int(unread or 0),
        )

    def mark_read(self, user_id: int, notification_id: int | None = None) -> int:
        stmt = select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read == 0,
        )
        if notification_id is not None:
            stmt = stmt.where(Notification.id == notification_id)
        rows = list(self.session.scalars(stmt).all())
        for row in rows:
            row.is_read = 1
            self.session.add(row)
        self.session.commit()
        return len(rows)

    def notify_students(self, *, title: str, body: str | None, kind: str) -> int:
        """给全部学生发同一条站内通知。调用方负责提交事务。"""
        role = self.session.scalar(select(Role).where(Role.code == "student"))
        if role is None:
            return 0
        user_ids = set(self.session.scalars(select(UserRole.user_id).where(UserRole.role_id == role.id)).all())
        for user_id in user_ids:
            self.create(user_id=user_id, title=title, body=body, kind=kind)
        return len(user_ids)

    def notify_review_result(
        self,
        *,
        student: User,
        project_title: str,
        application_id: int,
        project_id: int,
        decision: str,
        to_status: str,
        comment: str | None = None,
    ) -> tuple[bool | None, str | None]:
        """返回 (mail_sent, mail_hint)。approve 时 mail_sent 为 None。"""
        decision = decision.lower()
        if decision == "reject":
            title = f"申请未通过：{project_title}"
            body = (
                f"很抱歉，您申请的项目「{project_title}」未通过审核。"
                + (f"\n导师备注：{comment}" if comment else "")
                + "\n您可以登录平台查看详情，或修改材料后再次申请该项目。"
            )
            self.create(
                user_id=student.id,
                title=title,
                body=body,
                kind="review_reject",
                project_id=project_id,
                application_id=application_id,
            )
            sent = send_reject_mail(user=student, project_title=project_title)
            # 邮件为可选能力：未配置 SMTP 时仅站内通知，不再提示导师配邮箱
            return bool(sent), None

        status_zh = {
            "mentor_review": "导师审核中",
            "community_review": "社区审核中",
            "committee_review": "组委会审核中",
            "selected": "已中选",
            "rejected": "未通过",
            "withdrawn": "已放弃/取消接取",
            "in_progress": "开发中",
            "final_submitted": "已提交验收",
            "mentor_final_review": "导师验收中",
            "community_final_review": "导师已通过验收，待社区报送组委会",
            "committee_final_review": "组委会已接收结项",
            "final_rejected": "验收失败",
            "completed": "已结项（社区报送后组委会已自动接收）",
        }.get(to_status, to_status)
        title = f"审核有进展：{project_title}"
        body = f"项目「{project_title}」申请进度更新为：{status_zh}。"
        if comment:
            body += f"\n备注：{comment}"
        self.create(
            user_id=student.id,
            title=title,
            body=body,
            kind="review_progress",
            project_id=project_id,
            application_id=application_id,
        )
        return None, None
