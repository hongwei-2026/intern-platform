"""通知 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str | None = None
    kind: str
    project_id: int | None = None
    application_id: int | None = None
    is_read: int = 0
    created_at: datetime | None = None


class NotificationListOut(BaseModel):
    items: list[NotificationOut] = Field(default_factory=list)
    unread_count: int = 0
