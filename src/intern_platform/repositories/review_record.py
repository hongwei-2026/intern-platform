"""审核流水仓库（APPEND-ONLY）。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from intern_platform.models.mixins import utcnow
from intern_platform.models.review_record import ReviewRecord
from intern_platform.repositories.base import AppendOnlyRepository
from intern_platform.services.ledger import decision_code_for, next_seq_review


class ReviewRecordRepository(AppendOnlyRepository[ReviewRecord]):
    model = ReviewRecord

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def create(
        self,
        *,
        application_id: int,
        from_status: str,
        to_status: str,
        action: str,
        actor_id: int,
        actor_role: str,
        comment: str | None = None,
        request_id: str | None = None,
        idempotency_key: str | None = None,
        decision_code: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> ReviewRecord:
        seq_no = next_seq_review(self.session, application_id)
        return self.insert(
            ReviewRecord(
                application_id=application_id,
                seq_no=seq_no,
                from_status=from_status,
                to_status=to_status,
                action=action,
                decision_code=decision_code or decision_code_for(action),
                actor_id=actor_id,
                actor_role=actor_role,
                comment=comment,
                request_id=request_id,
                idempotency_key=idempotency_key,
                meta_json=(
                    json.dumps(meta, ensure_ascii=False) if meta is not None else None
                ),
                created_at=utcnow(),
            )
        )

    def get_by_idempotency_key(self, idempotency_key: str) -> ReviewRecord | None:
        stmt = select(ReviewRecord).where(
            ReviewRecord.idempotency_key == idempotency_key
        )
        return self.session.scalar(stmt)

    def list_by_application(self, application_id: int) -> list[ReviewRecord]:
        stmt = (
            select(ReviewRecord)
            .where(ReviewRecord.application_id == application_id)
            .order_by(ReviewRecord.seq_no.asc(), ReviewRecord.id.asc())
        )
        return list(self.session.scalars(stmt).all())
