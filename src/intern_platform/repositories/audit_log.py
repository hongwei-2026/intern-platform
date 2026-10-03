"""系统审计仓库（APPEND-ONLY，无 update/delete）。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from intern_platform.models.audit_log import AuditLog
from intern_platform.models.mixins import utcnow
from intern_platform.repositories.base import AppendOnlyRepository
from intern_platform.services.ledger import (
    build_audit_hash_payload,
    compute_event_hash,
    next_audit_link,
)


class AuditLogRepository(AppendOnlyRepository[AuditLog]):
    model = AuditLog

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def create(
        self,
        *,
        action: str,
        resource_type: str,
        resource_id: str | int,
        actor_id: int | None = None,
        actor_role: str | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        outcome: str = "SUCCESS",
        request_id: str | None = None,
        trace_id: str | None = None,
        idempotency_key: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        created_at = utcnow()
        seq_no, prev_hash = next_audit_link(self.session)
        before_json = (
            json.dumps(before, ensure_ascii=False) if before is not None else None
        )
        after_json = json.dumps(after, ensure_ascii=False) if after is not None else None
        resource_id_str = str(resource_id)
        payload = build_audit_hash_payload(
            seq_no=seq_no,
            prev_hash=prev_hash,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id_str,
            actor_id=actor_id,
            actor_role=actor_role,
            outcome=outcome,
            request_id=request_id,
            trace_id=trace_id,
            before_json=before_json,
            after_json=after_json,
            created_at=created_at,
        )
        event_hash = compute_event_hash(payload)
        return self.insert(
            AuditLog(
                seq_no=seq_no,
                actor_id=actor_id,
                actor_role=actor_role,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id_str,
                before_json=before_json,
                after_json=after_json,
                outcome=outcome,
                request_id=request_id,
                trace_id=trace_id,
                idempotency_key=idempotency_key,
                event_hash=event_hash,
                prev_hash=prev_hash,
                ip=ip,
                user_agent=user_agent,
                created_at=created_at,
            )
        )

    def get_by_idempotency_key(self, idempotency_key: str) -> AuditLog | None:
        stmt = select(AuditLog).where(AuditLog.idempotency_key == idempotency_key)
        return self.session.scalar(stmt)

    def list_by_resource(self, resource_type: str, resource_id: str | int) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.resource_type == resource_type,
                AuditLog.resource_id == str(resource_id),
            )
            .order_by(AuditLog.seq_no.asc(), AuditLog.id.asc())
        )
        return list(self.session.scalars(stmt).all())
