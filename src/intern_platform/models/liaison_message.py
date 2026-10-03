"""社区对接消息：对学生是通知记录，对导师和组委会是来回对话。"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from intern_platform.db.base import Base
from intern_platform.models.mixins import CreatedAtMixin


class LiaisonMessage(CreatedAtMixin, Base):
    __tablename__ = "liaison_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("communities.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)  # student | mentor | committee
    peer_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id"), nullable=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
