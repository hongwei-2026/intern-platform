"""站内通知。"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from intern_platform.db.base import Base
from intern_platform.models.mixins import TimestampMixin


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, default="review")
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id"))
    is_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
