"""工作流域事件仓库（APPEND-ONLY）。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from intern_platform.models.mixins import utcnow
from intern_platform.models.workflow_event import WorkflowEvent
from intern_platform.repositories.base import AppendOnlyRepository
from intern_platform.services.ledger import (
    build_workflow_hash_payload,
    compute_event_hash,
    get_prev_hash_workflow,
    next_seq_workflow,
)


class WorkflowEventRepository(AppendOnlyRepository[WorkflowEvent]):
    model = WorkflowEvent

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def create(
        self,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str | int,
        payload: dict[str, Any] | None = None,
        request_id: str | None = None,
        causation_id: str | None = None,
        correlation_id: str | None = None,
        idempotency_key: str | None = None,
        actor_id: int | None = None,
        actor_role: str | None = None,
    ) -> WorkflowEvent:
        occurred_at = utcnow()
        aggregate_id_str = str(aggregate_id)
        seq_no = next_seq_workflow(self.session, aggregate_type, aggregate_id_str)
        prev_hash = get_prev_hash_workflow(self.session, aggregate_type, aggregate_id_str)
        payload_json = (
            json.dumps(payload, ensure_ascii=False) if payload is not None else None
        )
        hash_payload = build_workflow_hash_payload(
            seq_no=seq_no,
            prev_hash=prev_hash,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id_str,
            payload_json=payload_json,
            actor_id=actor_id,
            actor_role=actor_role,
            request_id=request_id,
            occurred_at=occurred_at,
        )
        event_hash = compute_event_hash(hash_payload)
        return self.insert(
            WorkflowEvent(
                seq_no=seq_no,
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id_str,
                payload_json=payload_json,
                occurred_at=occurred_at,
                request_id=request_id,
                causation_id=causation_id,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
                actor_id=actor_id,
                actor_role=actor_role,
                event_hash=event_hash,
                prev_hash=prev_hash,
            )
        )

    def get_by_idempotency_key(self, idempotency_key: str) -> WorkflowEvent | None:
        stmt = select(WorkflowEvent).where(
            WorkflowEvent.idempotency_key == idempotency_key
        )
        return self.session.scalar(stmt)

    def list_by_aggregate(
        self, aggregate_type: str, aggregate_id: str | int
    ) -> list[WorkflowEvent]:
        stmt = (
            select(WorkflowEvent)
            .where(
                WorkflowEvent.aggregate_type == aggregate_type,
                WorkflowEvent.aggregate_id == str(aggregate_id),
            )
            .order_by(WorkflowEvent.seq_no.asc(), WorkflowEvent.id.asc())
        )
        return list(self.session.scalars(stmt).all())
