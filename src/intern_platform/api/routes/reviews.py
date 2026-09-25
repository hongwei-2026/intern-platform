"""三级审核路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from intern_platform.db.session import get_db
from intern_platform.dependencies.auth import AuthUser, require_roles
from intern_platform.dependencies.ledger import (
    LedgerRequestContext,
    get_ledger_context,
    require_idempotency_key,
)
from intern_platform.schemas.business import ReviewRequest, ReviewResponse
from intern_platform.services.review_usecase import ReviewDecision, ReviewUseCase

router = APIRouter(tags=["reviews"])


@router.post(
    "/applications/{application_id}/reviews",
    response_model=ReviewResponse,
)
def review_application(
    application_id: int,
    body: ReviewRequest,
    auth: AuthUser = Depends(require_roles("mentor", "community_admin", "committee")),
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> ReviewResponse:
    key = require_idempotency_key(body.idempotency_key or ledger.idempotency_key)
    result = ReviewUseCase(db).review(
        application_id=application_id,
        auth=auth,
        decision=ReviewDecision(
            decision=body.decision,
            comment=body.comment,
            expected_version=body.version,
            is_final=False,
        ),
        ledger=ledger,
        idempotency_key=key,
        commit=True,
    )
    return ReviewResponse(
        application_id=result.application.id,
        from_status=result.from_status,
        to_status=result.to_status,
        action=result.action,
        idempotent_replay=result.idempotent_replay,
        version=result.application.version,
        mail_sent=result.mail_sent,
        mail_hint=result.mail_hint,
    )
