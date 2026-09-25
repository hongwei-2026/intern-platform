"""公示公告模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from intern_platform.db.base import Base


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    community_id: Mapped[int | None] = mapped_column(ForeignKey("communities.id"))
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id"))
    published_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    is_public: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
