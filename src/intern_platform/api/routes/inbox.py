"""导师 / 社区管理员待审队列。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from intern_platform.db.session import get_db
from intern_platform.dependencies.auth import AuthUser, get_current_user
from intern_platform.schemas.business import ApplicationOut
from intern_platform.services.application_presenters import application_to_out
from intern_platform.services.application_service import ApplicationService
from intern_platform.services.mentor_updates import acknowledge_update, attach_update_flags

router = APIRouter(tags=["inbox"])


@router.get("/mentor/inbox", response_model=list[ApplicationOut])
def mentor_inbox(
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApplicationOut]:
    if not auth.has_role("mentor", "community_admin", "committee"):
        raise HTTPException(status_code=403, detail="仅组织端角色可查看待审队列")
    rows = ApplicationService(db).list_inbox(auth)
    outs = [application_to_out(r) for r in rows]
    if auth.has_role("mentor"):
        attach_update_flags(db, auth.id, outs)
    return outs


@router.post("/mentor/inbox/{application_id}/ack-update")
def ack_student_update(
    application_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    if not auth.has_role("mentor"):
        raise HTTPException(status_code=403, detail="仅导师可以清除更新标记")
    try:
        acknowledge_update(db, auth.id, application_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"ok": True}
