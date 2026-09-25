"""分社区扩展配置。"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intern_platform.db.base import Base
from intern_platform.models.mixins import TimestampMixin


class CommunityExtension(TimestampMixin, Base):
    __tablename__ = "community_extensions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    community_id: Mapped[int] = mapped_column(
        ForeignKey("communities.id"), unique=True, nullable=False
    )
    profile_blocks: Mapped[str | None] = mapped_column(Text)
    application_schema: Mapped[str | None] = mapped_column(Text)
    final_schema: Mapped[str | None] = mapped_column(Text)
    enabled_modules: Mapped[str | None] = mapped_column(Text)

    community = relationship("Community", back_populates="extension")
