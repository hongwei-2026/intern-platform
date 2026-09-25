"""申请留言板模型。"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intern_platform.db.base import Base
from intern_platform.models.mixins import TimestampMixin


class ApplicationMessage(TimestampMixin, Base):
    __tablename__ = "application_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id"), nullable=False, index=True
    )
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    application = relationship("Application", back_populates="messages")
