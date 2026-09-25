"""项目模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intern_platform.db.base import Base
from intern_platform.models.mixins import TimestampMixin


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    community_id: Mapped[int] = mapped_column(
        ForeignKey("communities.id"), nullable=False, index=True
    )
    mentor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    tech_stack: Mapped[str | None] = mapped_column(Text)  # JSON 数组字符串
    difficulty: Mapped[str | None] = mapped_column(String(32))
    quota: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    repo_url: Mapped[str | None] = mapped_column(String(512))
    apply_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)

    community = relationship("Community", back_populates="projects")
    applications = relationship("Application", back_populates="project")
