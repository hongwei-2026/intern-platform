"""公示路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from intern_platform.db.session import get_db
from intern_platform.dependencies.auth import AuthUser, require_roles
from intern_platform.dependencies.ledger import LedgerRequestContext, get_ledger_context
from intern_platform.schemas.business import AnnouncementCreate, AnnouncementOut
from intern_platform.services.announcement_service import AnnouncementService

router = APIRouter(prefix="/announcements", tags=["announcements"])


@router.get("", response_model=list[AnnouncementOut])
def list_announcements(
    type: str | None = Query(default=None, alias="type"),
    db: Session = Depends(get_db),
) -> list[AnnouncementOut]:
    rows = AnnouncementService(db).list_public(type_=type)
    return [AnnouncementOut.model_validate(r) for r in rows]


@router.post("", response_model=AnnouncementOut, status_code=201)
def create_announcement(
    body: AnnouncementCreate,
    auth: AuthUser = Depends(require_roles("committee")),
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> AnnouncementOut:
    try:
        row = AnnouncementService(db).publish(auth, body, ledger)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return AnnouncementOut.model_validate(row)


@router.put("/{announcement_id}", response_model=AnnouncementOut)
def revise_announcement(
    announcement_id: int,
    body: AnnouncementCreate,
    auth: AuthUser = Depends(require_roles("committee")),
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> AnnouncementOut:
    try:
        row = AnnouncementService(db).revise(auth, announcement_id, body, ledger)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AnnouncementOut.model_validate(row)


@router.delete("/{announcement_id}", status_code=204)
def withdraw_announcement(
    announcement_id: int,
    auth: AuthUser = Depends(require_roles("committee")),
    db: Session = Depends(get_db),
    ledger: LedgerRequestContext = Depends(get_ledger_context),
) -> None:
    try:
        AnnouncementService(db).withdraw(auth, announcement_id, ledger)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
