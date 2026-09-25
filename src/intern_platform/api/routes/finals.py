"""结项路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from intern_platform.db.session import get_db
from intern_platform.dependencies.auth import AuthUser, get_current_user, require_roles
from intern_platform.dependencies.ledger import (
    LedgerRequestContext,
    get_ledger_context,
    require_idempotency_key,
)
from intern_platform.schemas.business import (
    ApplicationOut,
    FinalOut,
    FinalUpsert,
    ReviewRequest,
    ReviewResponse,
)
from intern_platform.services.final_service import FinalService
from intern_platform.services.review_usecase import ReviewDecision, ReviewUseCase
from intern_platform.services.state_machine import IllegalTransitionError

router = APIRouter(tags=["finals"])


@router.put("/applications/{application_id}/final", response_model=FinalOut)
def upsert_final(
    application_id: int,
    body: FinalUpsert,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FinalOut:
    try:
        row = FinalService(db).upsert(auth, application_id, body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FinalOut.model_validate(row)


@router.post("/applications/{application_id}/final/submit", response_model=ApplicationOut)
def submit_final(
    application_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> ApplicationOut:
    key = require_idempotency_key(ledger.idempotency_key)
    try:
        app = FinalService(db).submit(auth, application_id, ledger, key)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IllegalTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    from intern_platform.services.application_presenters import application_to_out

    return application_to_out(app)


@router.post(
    "/applications/{application_id}/final/reviews",
    response_model=ReviewResponse,
)
def review_final(
    application_id: int,
    body: ReviewRequest,
    auth: AuthUser = Depends(require_roles("mentor", "committee")),
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
            is_final=True,
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
