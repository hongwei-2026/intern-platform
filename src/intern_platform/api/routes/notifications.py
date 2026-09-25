"""通知 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from intern_platform.db.session import get_db
from intern_platform.dependencies.auth import AuthUser, get_current_user
from intern_platform.schemas.notification import NotificationListOut
from intern_platform.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListOut)
def list_notifications(
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationListOut:
    return NotificationService(db).list_for_user(auth.id)


@router.post("/{notification_id}/read")
def mark_one_read(
    notification_id: int,
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    n = NotificationService(db).mark_read(auth.id, notification_id)
    return {"updated": n}


@router.post("/read-all")
def mark_all_read(
    auth: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    n = NotificationService(db).mark_read(auth.id)
    return {"updated": n}
