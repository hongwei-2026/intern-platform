"""申请留言路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from intern_platform.db.session import get_db
from intern_platform.dependencies.auth import AuthUser, get_current_user
from intern_platform.dependencies.ledger import LedgerRequestContext, get_ledger_context
from intern_platform.schemas.business import MessageCreate, MessageOut
from intern_platform.services.message_service import MessageService

router = APIRouter(tags=["messages"])


@router.get("/applications/{application_id}/messages", response_model=list[MessageOut])
def list_messages(
    application_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MessageOut]:
    try:
        rows = MessageService(db).list_messages(auth, application_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return rows


@router.post(
    "/applications/{application_id}/messages",
    response_model=MessageOut,
    status_code=201,
)
def post_message(
    application_id: int,
    body: MessageCreate,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> MessageOut:
    try:
        row = MessageService(db).post(auth, application_id, body, ledger)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return row
