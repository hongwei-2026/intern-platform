"""结项提交模型。"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intern_platform.db.base import Base
from intern_platform.models.mixins import TimestampMixin


class FinalSubmission(TimestampMixin, Base):
    __tablename__ = "final_submissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id"), unique=True, nullable=False
    )
    pr_mr_url: Mapped[str] = mapped_column(String(512), nullable=False)
    report_url: Mapped[str | None] = mapped_column(String(512))
    report_text: Mapped[str | None] = mapped_column(Text)
    extra_fields: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")

    application = relationship("Application", back_populates="final_submission")
