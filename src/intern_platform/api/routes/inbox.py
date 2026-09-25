"""导师 / 社区管理员待审队列。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from intern_platform.db.session import get_db
from intern_platform.dependencies.auth import AuthUser, get_current_user
from intern_platform.schemas.business import ApplicationOut
from intern_platform.services.application_presenters import application_to_out
from intern_platform.services.application_service import ApplicationService

router = APIRouter(tags=["inbox"])


@router.get("/mentor/inbox", response_model=list[ApplicationOut])
def mentor_inbox(
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApplicationOut]:
    if not auth.has_role("mentor", "community_admin", "committee"):
        raise HTTPException(status_code=403, detail="仅组织端角色可查看待审队列")
    rows = ApplicationService(db).list_inbox(auth)
    return [application_to_out(r) for r in rows]
