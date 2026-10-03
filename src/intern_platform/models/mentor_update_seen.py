"""导师已看过的进展 / 验收。只有点掉侧栏标记才写入。"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from intern_platform.db.base import Base


class MentorUpdateSeen(Base):
    __tablename__ = "mentor_update_seen"
    __table_args__ = (
        UniqueConstraint("mentor_id", "application_id", name="uq_mentor_update_seen"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    mentor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id"), nullable=False, index=True
    )
    message_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
