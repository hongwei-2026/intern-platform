"""公示服务。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from intern_platform.dependencies.auth import AuthUser
from intern_platform.dependencies.ledger import LedgerRequestContext
from intern_platform.models.announcement import Announcement
from intern_platform.models.mixins import utcnow
from intern_platform.repositories.audit_log import AuditLogRepository
from intern_platform.schemas.business import AnnouncementCreate


class AnnouncementService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.audits = AuditLogRepository(session)

    def list_public(self, type_: str | None = None) -> list[Announcement]:
        stmt = (
            select(Announcement)
            .where(Announcement.is_public == 1)
            .order_by(Announcement.id.desc())
        )
        if type_:
            stmt = stmt.where(Announcement.type == type_)
        return list(self.session.scalars(stmt).all())

    def publish(
        self,
        auth: AuthUser,
        body: AnnouncementCreate,
        ledger: LedgerRequestContext,
    ) -> Announcement:
        if not auth.has_role("committee"):
            raise PermissionError("仅组委会可发布公示")
        row = Announcement(
            type=body.type,
            title=body.title,
            body=body.body,
            community_id=body.community_id,
            project_id=body.project_id,
            application_id=body.application_id,
            published_by=auth.id,
            published_at=utcnow(),
            is_public=1 if body.is_public else 0,
        )
        self.session.add(row)
        self.session.flush()
        self.audits.create(
            actor_id=auth.id,
            actor_role="committee",
            action="announcement.publish",
            resource_type="announcement",
            resource_id=row.id,
            after={"type": row.type, "title": row.title},
            outcome="SUCCESS",
            request_id=ledger.request_id,
            trace_id=ledger.trace_id,
            ip=ledger.ip,
            user_agent=ledger.user_agent,
        )
        self.session.commit()
        self.session.refresh(row)
        return row
